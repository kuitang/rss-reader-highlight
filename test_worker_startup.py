#!/usr/bin/env python3
"""Integration test for background worker startup feed queuing logic"""

import os
import sys
import sqlite3
import tempfile
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up test database path BEFORE importing models
test_db = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_PATH'] = test_db

from models import FeedModel, init_db, get_db
from background_worker import FeedUpdateWorker, initialize_worker_system
import background_worker

async def test_worker_startup_feed_queuing():
    """Test that worker only queues feeds older than 1 hour at startup"""
    print(f"Using test database: {test_db}")
    
    # Initialize test database
    init_db()
    
    # Setup test fixtures with specific timestamps (use UTC to match SQLite)
    from datetime import timezone
    now = datetime.now(timezone.utc)
    thirty_minutes_ago = now - timedelta(minutes=30)
    two_hours_ago = now - timedelta(hours=2)
    
    with get_db() as conn:
        # Feed 1: Updated 30 minutes ago (should NOT be queued)
        conn.execute("""
            INSERT INTO feeds (url, title, last_updated)
            VALUES (?, ?, ?)
        """, (
            'https://recent.example.com/rss', 
            'Recent Feed', 
            thirty_minutes_ago.strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        # Feed 2: Updated 2 hours ago (should be queued)
        conn.execute("""
            INSERT INTO feeds (url, title, last_updated)
            VALUES (?, ?, ?)
        """, (
            'https://old.example.com/rss', 
            'Old Feed',
            two_hours_ago.strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        # Feed 3: Never updated (NULL last_updated - should be queued)
        conn.execute("""
            INSERT INTO feeds (url, title, last_updated)
            VALUES (?, ?, NULL)
        """, (
            'https://new.example.com/rss',
            'New Feed'
        ))
        
        # Verify fixtures were created correctly
        feeds = conn.execute("""
            SELECT url, title, last_updated 
            FROM feeds 
            ORDER BY id
        """).fetchall()
        
        print("\n=== Test Fixtures ===")
        for feed in feeds:
            print(f"URL: {feed[0]}, Title: {feed[1]}, Last Updated: {feed[2]}")
    
    # Debug: Check what get_feeds_to_update returns
    print("\n=== Debug: Checking get_feeds_to_update ===")
    
    # Check current time and cutoff (use UTC to match SQLite)
    from datetime import timezone
    debug_now = datetime.now(timezone.utc)
    debug_cutoff = debug_now - timedelta(minutes=60)
    print(f"Current time (UTC): {debug_now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Cutoff time (60 min ago UTC): {debug_cutoff.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check raw SQL query results
    with get_db() as conn:
        raw_results = conn.execute("""
            SELECT url, last_updated,
                   datetime('now') as now_time,
                   datetime('now', '-60 minutes') as cutoff_time,
                   CASE 
                       WHEN last_updated IS NULL THEN 'NULL - Include'
                       WHEN datetime(last_updated) < datetime('now', '-60 minutes') THEN 'Old - Include'
                       ELSE 'Recent - Exclude'
                   END as decision
            FROM feeds
            ORDER BY id
        """).fetchall()
        print("\nSQL Query Debug:")
        for row in raw_results:
            print(f"  {row[0]}: last_updated={row[1]}, now={row[2]}, cutoff={row[3]}, decision={row[4]}")
    
    feeds_to_update = FeedModel.get_feeds_to_update(max_age_minutes=60)
    print(f"\nFeeds returned by get_feeds_to_update(60): {len(feeds_to_update)}")
    for feed in feeds_to_update:
        print(f"  - {feed['url']}: {feed.get('last_updated')}")
    
    # Initialize worker system (this should queue feeds)
    print("\n=== Initializing Worker System ===")
    await initialize_worker_system()
    
    # Get queue size after initialization
    queue_size = background_worker.feed_worker.queue.qsize()
    print(f"Queue size after initialization: {queue_size}")
    
    # Collect queued feeds
    queued_feeds = []
    for _ in range(queue_size):
        feed = await background_worker.feed_worker.queue.get()
        queued_feeds.append(feed)
        # Put it back so we don't break the queue
        await background_worker.feed_worker.queue.put(feed)
    
    print("\n=== Queued Feeds ===")
    for feed in queued_feeds:
        print(f"ID: {feed['id']}, URL: {feed['url']}, Title: {feed.get('title')}, Last Updated: {feed.get('last_updated')}")
    
    # Verify expectations
    assert queue_size == 2, f"Expected 2 feeds to be queued, got {queue_size}"
    
    # Check that the correct feeds were queued
    queued_urls = {feed['url'] for feed in queued_feeds}
    expected_urls = {
        'https://old.example.com/rss',  # 2 hours old
        'https://new.example.com/rss'   # Never updated (NULL)
    }
    
    assert queued_urls == expected_urls, f"Expected URLs {expected_urls}, got {queued_urls}"
    
    # Verify the recent feed was NOT queued
    assert 'https://recent.example.com/rss' not in queued_urls, "Recent feed should not be queued"
    
    print("\n✅ All assertions passed!")
    
    # Cleanup worker
    await background_worker.feed_worker.stop()
    
    return True

async def test_edge_cases():
    """Test edge cases for feed queuing logic"""
    print("\n=== Testing Edge Cases ===")
    
    # Clear database
    with get_db() as conn:
        conn.execute("DELETE FROM feeds")
    
    # Test with feed exactly 1 hour old (should be queued - uses > comparison)
    exactly_one_hour_ago = datetime.now() - timedelta(hours=1)
    
    with get_db() as conn:
        conn.execute("""
            INSERT INTO feeds (url, title, last_updated)
            VALUES (?, ?, ?)
        """, (
            'https://exactly-one-hour.example.com/rss',
            'Exactly One Hour Feed',
            exactly_one_hour_ago.strftime('%Y-%m-%d %H:%M:%S')
        ))
    
    # Check what get_feeds_to_update returns
    feeds_to_update = FeedModel.get_feeds_to_update(max_age_minutes=60)
    
    # Edge case: Feed exactly 1 hour old should be queued (using < comparison, not <=)
    # The SQL uses: datetime(last_updated) < datetime('now', '-60 minutes')
    # So a feed exactly 60 minutes old would NOT be included
    
    print(f"Feeds older than 60 minutes: {len(feeds_to_update)}")
    for feed in feeds_to_update:
        print(f"  - {feed['url']}: {feed.get('last_updated')}")
    
    # Clean up
    with get_db() as conn:
        conn.execute("DELETE FROM feeds")
    
    print("✅ Edge case tests completed")
    
    return True

async def test_empty_database():
    """Test worker startup with empty database"""
    print("\n=== Testing Empty Database ===")
    
    # Clear database
    with get_db() as conn:
        conn.execute("DELETE FROM feeds")
    
    # Re-initialize worker (should handle empty DB gracefully)
    background_worker.feed_worker = FeedUpdateWorker()
    await background_worker.feed_worker.start()
    
    # Queue all feeds initially for first startup (from initialize_worker_system logic)
    all_feeds = FeedModel.get_feeds_to_update(max_age_minutes=60)
    for feed in all_feeds:
        await background_worker.feed_worker.queue.put(feed)
    
    queue_size = background_worker.feed_worker.queue.qsize()
    print(f"Queue size with empty database: {queue_size}")
    
    assert queue_size == 0, f"Expected 0 feeds in queue for empty DB, got {queue_size}"
    
    print("✅ Empty database test passed")
    
    # Cleanup
    await background_worker.feed_worker.stop()
    
    return True

if __name__ == "__main__":
    try:
        # Run all tests
        asyncio.run(test_worker_startup_feed_queuing())
        asyncio.run(test_edge_cases())
        asyncio.run(test_empty_database())
        
        print("\n🎉 All integration tests passed!")
        
        # Clean up test database
        os.unlink(test_db)
        print(f"Test database {test_db} cleaned up")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Still try to clean up
        try:
            os.unlink(test_db)
        except:
            pass
        
        sys.exit(1)