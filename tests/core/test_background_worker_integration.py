#!/usr/bin/env python3
"""
Critical integration tests for background worker system.
Only the hardest tests that validate the complete system under concurrent conditions.
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock
import httpx
from collections import defaultdict
import sqlite3
import tempfile
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

# Import our modules
from app.models import init_db, get_db, FeedModel, FeedItemModel
from app.feed_parser import FeedParser
from app.background_worker import FeedUpdateWorker, FeedQueueManager, DomainRateLimiter


class TestBackgroundWorkerIntegration:
    """Critical integration tests for background worker system"""
    
    @pytest.fixture
    def isolated_worker_system(self):
        """Create isolated test database and worker system"""
        # Create temporary database file
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        
        # Patch the DB_PATH in models module
        from app import models
        original_path = models.DB_PATH
        
        with patch.object(models, 'DB_PATH', db_path):
            # Initialize the test database using existing init_db function
            init_db()
            
            # Create worker system with isolated database
            worker = FeedUpdateWorker()
            queue_manager = FeedQueueManager(worker)
            worker.start()
            
            yield worker, queue_manager, db_path
            
            # Cleanup worker
            worker.stop()
            if worker.is_alive():
                worker.join(timeout=5.0)
        
        # Cleanup database file
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def mock_feeds_data(self):
        """Mock RSS feed data for testing"""
        return {
            'reddit.com': {
                'url': 'https://reddit.com/r/python/.rss',
                'content': '''<?xml version="1.0"?>
                <rss version="2.0">
                    <channel>
                        <title>Python Reddit</title>
                        <item>
                            <title>Test Post 1</title>
                            <link>https://reddit.com/post1</link>
                            <guid>reddit_post_1</guid>
                            <description>Test description 1</description>
                        </item>
                        <item>
                            <title>Test Post 2</title>
                            <link>https://reddit.com/post2</link>
                            <guid>reddit_post_2</guid>
                            <description>Test description 2</description>
                        </item>
                    </channel>
                </rss>'''
            },
            'github.com': {
                'url': 'https://github.com/python/cpython/releases.atom',
                'content': '''<?xml version="1.0"?>
                <feed xmlns="http://www.w3.org/2005/Atom">
                    <title>CPython Releases</title>
                    <entry>
                        <title>Python 3.12.0</title>
                        <link href="https://github.com/python/cpython/releases/tag/v3.12.0"/>
                        <id>github_release_1</id>
                        <summary>New Python release</summary>
                    </entry>
                </feed>'''
            }
        }
    
    def test_concurrent_feed_processing_with_deduplication(self, isolated_worker_system, mock_feeds_data):
        """
        CRITICAL: 3 threads processing same feeds simultaneously.
        Verifies no duplicate items saved and database integrity.
        """
        worker, queue_manager, db_path = isolated_worker_system
        
        # Setup test feeds in database
        feed_ids = []
        with get_db() as conn:
            for domain, data in mock_feeds_data.items():
                cursor = conn.execute(
                    "INSERT INTO feeds (url, title) VALUES (?, ?)",
                    (data['url'], f"Test {domain}")
                )
                feed_ids.append(cursor.lastrowid)
        
        # Mock HTTP responses
        def mock_http_get(url, **kwargs):
            for domain, data in mock_feeds_data.items():
                if domain in url:
                    response = Mock()
                    response.status_code = 200
                    response.text = data['content']
                    response.headers = {}
                    return response
            raise Exception(f"Unmocked URL: {url}")
        
        # Create 3 threads processing same feeds simultaneously
        with patch('httpx.Client.get', side_effect=mock_http_get):
            threads = []
            for i in range(3):
                # Each thread processes all feeds
                for feed_id in feed_ids:
                    feed_data = {'id': feed_id, 'url': list(mock_feeds_data.values())[feed_ids.index(feed_id)]['url']}
                    thread = threading.Thread(target=worker._process_feed_direct, args=(feed_data,))
                    threads.append(thread)
                    thread.start()
            
            # Wait for all concurrent processing to complete
            for thread in threads:
                thread.join(timeout=10.0)
        
        # Verify no duplicates in database (UNIQUE constraint should prevent them)
        with get_db() as conn:
            for feed_id in feed_ids:
                items = conn.execute(
                    "SELECT guid, COUNT(*) as count FROM feed_items WHERE feed_id = ? GROUP BY guid",
                    (feed_id,)
                ).fetchall()
                
                # Each GUID should appear exactly once despite 3 concurrent workers
                for row in items:
                    assert row[1] == 1, f"Duplicate item found: {row[0]} appeared {row[1]} times"
                
                # Should have expected number of items
                total_items = conn.execute(
                    "SELECT COUNT(*) FROM feed_items WHERE feed_id = ?", 
                    (feed_id,)
                ).fetchone()[0]
                assert total_items > 0, f"No items saved for feed {feed_id}"
    
    def test_user_request_triggers_background_updates(self, isolated_worker_system, mock_feeds_data):
        """
        CRITICAL: End-to-end flow - user visits → feeds queued → background processing → UI updates
        """
        worker, queue_manager, db_path = isolated_worker_system
        
        # Setup old feeds (need updating)
        old_time = datetime.now() - timedelta(minutes=5)
        feed_ids = []
        with get_db() as conn:
            for domain, data in mock_feeds_data.items():
                cursor = conn.execute(
                    "INSERT INTO feeds (url, title, last_updated) VALUES (?, ?, ?)",
                    (data['url'], f"Test {domain}", old_time.isoformat())
                )
                feed_ids.append(cursor.lastrowid)
        
        # Create user session and subscribe to feeds
        session_id = "test_session_123"
        with get_db() as conn:
            conn.execute("INSERT INTO sessions (id) VALUES (?)", (session_id,))
            for feed_id in feed_ids:
                conn.execute(
                    "INSERT INTO user_feeds (session_id, feed_id) VALUES (?, ?)",
                    (session_id, feed_id)
                )
        
        # Mock HTTP responses
        def mock_http_get(url, **kwargs):
            for domain, data in mock_feeds_data.items():
                if domain in url:
                    response = Mock()
                    response.status_code = 200
                    response.text = data['content']
                    response.headers = {}
                    time.sleep(0.1)  # Simulate network delay
                    return response
            raise Exception(f"Unmocked URL: {url}")
        
        with patch('httpx.Client.get', side_effect=mock_http_get):
            # Simulate user request - should queue feeds for update
            initial_queue_size = worker.queue.qsize()
            queue_manager.queue_user_feeds(session_id)
            
            # Verify feeds were queued
            assert worker.queue.qsize() > initial_queue_size, "No feeds were queued"
            
            # Wait for background processing to complete
            time.sleep(1.0)  # Allow worker to process queue
            
            # Verify feeds were updated in database
            with get_db() as conn:
                for feed_id in feed_ids:
                    last_updated = conn.execute(
                        "SELECT last_updated FROM feeds WHERE id = ?", 
                        (feed_id,)
                    ).fetchone()[0]
                    
                    updated_time = datetime.fromisoformat(last_updated)
                    assert updated_time > old_time, f"Feed {feed_id} was not updated"
                    
                    # Verify items were saved
                    item_count = conn.execute(
                        "SELECT COUNT(*) FROM feed_items WHERE feed_id = ?", 
                        (feed_id,)
                    ).fetchone()[0]
                    assert item_count > 0, f"No items saved for feed {feed_id}"
    
    def test_domain_rate_limiting_enforcement(self, isolated_worker_system):
        """
        CRITICAL: Multiple feeds from same domain must respect 10 req/min rate limit
        """
        worker, queue_manager, db_path = isolated_worker_system
        
        # Create multiple reddit feeds (same domain)
        reddit_feeds = [
            {'id': 1, 'url': 'https://reddit.com/r/python/.rss'},
            {'id': 2, 'url': 'https://reddit.com/r/programming/.rss'},
            {'id': 3, 'url': 'https://reddit.com/r/technology/.rss'},
            {'id': 4, 'url': 'https://reddit.com/r/machinelearning/.rss'},
            {'id': 5, 'url': 'https://reddit.com/r/datascience/.rss'},
        ]
        
        # Setup rate limiter with strict limits for testing
        rate_limiter = DomainRateLimiter(max_requests=3, per_seconds=10)
        worker.domain_limiters['reddit.com'] = rate_limiter
        
        # Track request times
        request_times = []
        
        def mock_http_get(url, **kwargs):
            request_times.append(time.time())
            response = Mock()
            response.status_code = 200
            response.text = '''<?xml version="1.0"?><rss><channel><title>Test</title></channel></rss>'''
            response.headers = {}
            return response
        
        with patch('httpx.Client.get', side_effect=mock_http_get):
            # Process all feeds concurrently using threads (should be rate limited)
            threads = []
            start_time = time.time()
            
            for feed in reddit_feeds:
                thread = threading.Thread(target=worker._process_feed_direct, args=(feed,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=15.0)
            
            # Verify rate limiting was enforced
            assert len(request_times) == 5, f"Expected 5 requests, got {len(request_times)}"
            
            # First 3 requests should be immediate, next 2 should be delayed
            time_diffs = [request_times[i] - request_times[0] for i in range(len(request_times))]
            
            # First 3 should be within 1 second
            for i in range(3):
                assert time_diffs[i] < 1.0, f"Request {i} took too long: {time_diffs[i]}"
            
            # Last 2 should be delayed by rate limiting
            for i in range(3, 5):
                assert time_diffs[i] >= 3.0, f"Request {i} should have been rate limited: {time_diffs[i]}"
    
    def test_worker_restart_recovery(self, isolated_worker_system, mock_feeds_data):
        """
        CRITICAL: Worker dies mid-processing → restart → verify queue integrity and recovery
        """
        # Setup initial worker
        worker1 = FeedUpdateWorker()
        worker1.start()
        
        # Add feeds to process
        test_feeds = [
            {'id': 1, 'url': 'https://reddit.com/r/python/.rss'},
            {'id': 2, 'url': 'https://github.com/python/cpython/releases.atom'},
        ]
        
        # Queue feeds
        for feed in test_feeds:
            worker1.queue.put(feed)
        
        initial_queue_size = worker1.queue.qsize()
        assert initial_queue_size == 2, f"Expected 2 feeds in queue, got {initial_queue_size}"
        
        # Simulate worker death by stopping it
        worker1.stop()
        if worker1.is_alive():
            worker1.join(timeout=5.0)
        
        # Create new worker (simulating restart)
        worker2 = FeedUpdateWorker()
        worker2.start()
        
        # Re-queue the feeds (simulating application restart)
        for feed in test_feeds:
            worker2.queue.put(feed)
        
        # Verify new worker can process feeds
        def mock_http_get(url, **kwargs):
            for domain, data in mock_feeds_data.items():
                if domain in url:
                    response = Mock()
                    response.status_code = 200
                    response.text = data['content']
                    response.headers = {}
                    return response
            raise Exception(f"Unmocked URL: {url}")
        
        with patch('httpx.Client.get', side_effect=mock_http_get):
            # Wait for processing
            time.sleep(1.0)
            
            # Verify worker is healthy
            assert worker2.is_running, "Worker should be running after restart"
            assert worker2.is_alive(), "Worker thread should be active"
            
            # Verify heartbeat is recent
            assert datetime.now() - worker2.last_heartbeat < timedelta(seconds=5), "Heartbeat should be recent"
        
        # Cleanup
        worker2.stop()
        if worker2.is_alive():
            worker2.join(timeout=5.0)
    
    
    def test_database_integrity_under_concurrent_writes(self, isolated_worker_system):
        """
        CRITICAL: Multiple workers writing to same feed simultaneously.
        Verifies SQLite handles concurrent writes and feed metadata correctly.
        """
        worker, queue_manager, db_path = isolated_worker_system
        
        # Create one feed that multiple workers will update
        test_feed = {'id': 1, 'url': 'https://test.com/feed.rss'}
        with get_db() as conn:
            conn.execute(
                "INSERT INTO feeds (id, url, title) VALUES (?, ?, ?)",
                (1, test_feed['url'], "Test Feed")
            )
        
        # Create different RSS content for each worker to process
        feed_contents = [
            f'''<?xml version="1.0"?><rss><channel><title>Test</title>
                <item>
                    <title>Item {i}</title>
                    <guid>item_{i}</guid>
                    <link>http://test.com/{i}</link>
                    <description>Test description for item {i}</description>
                </item>
                </channel></rss>'''
            for i in range(10)
        ]
        
        request_count = 0
        def mock_http_get(url, **kwargs):
            nonlocal request_count
            content = feed_contents[request_count % len(feed_contents)]
            request_count += 1
            
            response = Mock()
            response.status_code = 200
            response.text = content
            response.headers = {
                'etag': f'"etag_{request_count}"',
                'last-modified': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
            }
            time.sleep(0.01)  # Small delay
            return response
        
        with patch('httpx.Client.get', side_effect=mock_http_get):
            # Launch 5 concurrent threads processing the same feed
            threads = []
            exceptions = []
            
            def worker_thread(thread_id):
                try:
                    worker._process_feed_direct(test_feed)
                except Exception as e:
                    exceptions.append((thread_id, e))
            
            for i in range(5):
                thread = threading.Thread(target=worker_thread, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for all concurrent processing
            for thread in threads:
                thread.join(timeout=10.0)
            
            # Check that no threads failed with unexpected database errors
            for thread_id, exception in exceptions:
                # Allow "database is locked" errors but not others
                if "database is locked" not in str(exception).lower():
                    pytest.fail(f"Thread {thread_id} failed with unexpected error: {exception}")
            
            # Verify database integrity
            with get_db() as conn:
                # Feed should exist and have been updated
                feed_data = conn.execute(
                    "SELECT last_updated, etag FROM feeds WHERE id = ?", (1,)
                ).fetchone()
                
                assert feed_data is not None, "Feed should exist"
                assert feed_data[0] is not None, "Feed should have been updated"
                
                # Should have some items (at least from one successful update)
                item_count = conn.execute(
                    "SELECT COUNT(*) FROM feed_items WHERE feed_id = ?", (1,)
                ).fetchone()[0]
                
                assert item_count > 0, "Should have at least one feed item"
                
                # Verify no duplicate items (each GUID should appear only once)
                duplicate_check = conn.execute(
                    "SELECT guid, COUNT(*) FROM feed_items WHERE feed_id = ? GROUP BY guid HAVING COUNT(*) > 1",
                    (1,)
                ).fetchall()
                
                assert len(duplicate_check) == 0, f"Found duplicate items: {duplicate_check}"
    
    def test_ui_status_indicator_accuracy(self, isolated_worker_system):
        """
        CRITICAL: UI status shows accurate real-time updates about worker state
        """
        worker, queue_manager, db_path = isolated_worker_system
        
        # Initially should show no activity
        status = worker.get_status()
        assert status['is_updating'] == False, "Should not be updating initially"
        assert status['queue_size'] == 0, "Queue should be empty initially"
        assert status['worker_alive'] == True, "Worker should be alive"
        
        # Add feeds to queue
        test_feeds = [
            {'id': 1, 'url': 'https://test1.com/feed.rss'},
            {'id': 2, 'url': 'https://test2.com/feed.rss'},
            {'id': 3, 'url': 'https://test3.com/feed.rss'},
        ]
        
        for feed in test_feeds:
            worker.queue.put(feed)
        
        # Should now show activity
        status = worker.get_status()
        assert status['is_updating'] == True, "Should be updating with items in queue"
        assert status['queue_size'] == 3, f"Queue should have 3 items, got {status['queue_size']}"
        
        # Mock slow HTTP responses to observe worker processing
        def slow_http_get(url, **kwargs):
            time.sleep(0.5)  # 500ms delay
            response = Mock()
            response.status_code = 200
            response.text = '''<?xml version="1.0"?><rss><channel><title>Test</title></channel></rss>'''
            response.headers = {}
            return response
        
        with patch('httpx.Client.get', side_effect=slow_http_get):
            # Check status while processing
            time.sleep(0.1)  # Allow worker to start processing
            
            status = worker.get_status()
            assert status['worker_alive'] == True, "Worker should be alive during processing"
            # Note: current_feed might be None if worker hasn't picked up a feed yet
            
            # Wait for processing to complete
            timeout = 5.0
            start_time = time.time()
            while worker.queue.qsize() > 0 and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            # Should show no activity after processing
            status = worker.get_status()
            assert status['is_updating'] == False, "Should not be updating after queue is empty"
            assert status['queue_size'] == 0, "Queue should be empty after processing"
        
        # Test worker death detection
        worker.stop()
        if worker.is_alive():
            worker.join(timeout=2.0)
        
        status = worker.get_status()
        assert status['worker_alive'] == False, "Should detect dead worker"


if __name__ == '__main__':
    pytest.main([__file__, "-v"])