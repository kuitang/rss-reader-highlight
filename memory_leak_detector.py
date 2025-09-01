#!/usr/bin/env python3
"""
Memory leak detection script for RSS reader background worker
"""

import psutil
import time
import gc
import sys
import threading
from collections import defaultdict
import tracemalloc
import sqlite3
from background_worker import FeedUpdateWorker, FeedQueueManager
from models import init_db, FeedModel

def monitor_memory_usage(duration_minutes=10, check_interval_seconds=30):
    """Monitor memory usage over time to detect leaks"""
    print(f"=== MEMORY LEAK DETECTION ===")
    print(f"Monitoring for {duration_minutes} minutes, checking every {check_interval_seconds} seconds")
    
    # Start memory tracing
    tracemalloc.start()
    process = psutil.Process()
    
    # Initialize database and worker
    init_db()
    worker = FeedUpdateWorker()
    queue_manager = FeedQueueManager(worker)
    worker.start()
    
    # Get some test feeds
    test_feeds = FeedModel.get_feeds_to_update(max_age_minutes=1440)  # All feeds
    print(f"Found {len(test_feeds)} feeds to test with")
    
    baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
    print(f"Baseline memory: {baseline_memory:.1f}MB")
    
    memory_readings = []
    feed_processing_count = 0
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    try:
        while time.time() < end_time:
            # Queue a feed for processing
            if test_feeds:
                feed = test_feeds[feed_processing_count % len(test_feeds)]
                worker.queue.put(feed)
                feed_processing_count += 1
                print(f"Queued feed #{feed_processing_count}: {feed['title'][:50]}...")
            
            # Wait for processing
            time.sleep(check_interval_seconds)
            
            # Check memory usage
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = current_memory - baseline_memory
            
            # Get tracemalloc snapshot
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')
            top_memory = sum(stat.size for stat in top_stats[:10]) / 1024 / 1024  # MB
            
            memory_readings.append({
                'time': time.time() - start_time,
                'memory_mb': current_memory,
                'increase_mb': memory_increase,
                'queue_size': worker.queue.qsize(),
                'feeds_processed': feed_processing_count,
                'top_objects_mb': top_memory
            })
            
            print(f"[{int(time.time() - start_time)}s] Memory: {current_memory:.1f}MB (▲{memory_increase:+.1f}MB), Queue: {worker.queue.qsize()}, Processed: {feed_processing_count}")
            
            # Check for memory leak pattern
            if len(memory_readings) >= 3:
                recent_increases = [r['increase_mb'] for r in memory_readings[-3:]]
                if all(inc > 5.0 for inc in recent_increases):  # Consistent 5MB+ increases
                    print("⚠️  POTENTIAL MEMORY LEAK DETECTED!")
                    print(f"Recent memory increases: {recent_increases}")
    
    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped by user")
    
    finally:
        # Stop worker
        worker.stop()
        if worker.is_alive():
            worker.join(timeout=5.0)
        
        print(f"\n=== MEMORY LEAK ANALYSIS ===")
        print(f"Baseline memory: {baseline_memory:.1f}MB")
        
        if memory_readings:
            final_memory = memory_readings[-1]['memory_mb']
            total_increase = final_memory - baseline_memory
            max_memory = max(r['memory_mb'] for r in memory_readings)
            avg_memory = sum(r['memory_mb'] for r in memory_readings) / len(memory_readings)
            
            print(f"Final memory: {final_memory:.1f}MB")
            print(f"Total increase: {total_increase:+.1f}MB")
            print(f"Peak memory: {max_memory:.1f}MB")
            print(f"Average memory: {avg_memory:.1f}MB")
            print(f"Feeds processed: {feed_processing_count}")
            
            # Analyze trend
            if len(memory_readings) >= 5:
                early_avg = sum(r['memory_mb'] for r in memory_readings[:3]) / 3
                late_avg = sum(r['memory_mb'] for r in memory_readings[-3:]) / 3
                trend = late_avg - early_avg
                
                print(f"Memory trend: {trend:+.1f}MB ({early_avg:.1f}MB → {late_avg:.1f}MB)")
                
                if trend > 10.0:
                    print("❌ MEMORY LEAK CONFIRMED: Upward trend >10MB")
                elif trend > 5.0:
                    print("⚠️  POTENTIAL LEAK: Upward trend >5MB")
                elif abs(trend) < 2.0:
                    print("✅ STABLE: Memory usage stable")
                else:
                    print("✅ DECREASING: Memory usage trending down")
        
        # Final tracemalloc analysis
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        print(f"\n=== TOP MEMORY CONSUMERS ===")
        for index, stat in enumerate(top_stats[:10]):
            print(f"{index+1}. {stat.traceback.format()[-1]}: {stat.size/1024/1024:.1f}MB ({stat.count} objects)")

def test_single_large_feed():
    """Test memory usage with a single large feed"""
    print(f"\n=== LARGE FEED MEMORY TEST ===")
    
    init_db()
    worker = FeedUpdateWorker()
    queue_manager = FeedQueueManager(worker)
    
    # Create test feed with large content
    large_feed = {
        'id': 999,
        'url': 'https://techcrunch.com/feed/',  # Known large feed
        'title': 'TechCrunch Test Feed',
        'last_updated': None,
        'etag': None,
        'last_modified': None
    }
    
    process = psutil.Process()
    memory_before = process.memory_info().rss / 1024 / 1024
    
    print(f"Memory before processing: {memory_before:.1f}MB")
    
    # Process feed directly (synchronous test)
    worker._process_feed_direct(large_feed)
    
    memory_after = process.memory_info().rss / 1024 / 1024
    memory_diff = memory_after - memory_before
    
    print(f"Memory after processing: {memory_after:.1f}MB")
    print(f"Memory difference: {memory_diff:+.1f}MB")
    
    # Force garbage collection
    collected = gc.collect()
    memory_final = process.memory_info().rss / 1024 / 1024
    gc_effect = memory_final - memory_after
    
    print(f"After gc.collect(): {memory_final:.1f}MB (▲{gc_effect:+.1f}MB, collected {collected} objects)")
    
    if abs(memory_diff) < 1.0:
        print("✅ GOOD: Minimal memory impact")
    elif memory_diff > 5.0:
        print("❌ PROBLEM: Significant memory increase")
    else:
        print("⚠️  MODERATE: Some memory increase")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "single":
        test_single_large_feed()
    else:
        monitor_memory_usage(duration_minutes=5, check_interval_seconds=15)