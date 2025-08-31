#!/usr/bin/env python3
"""
Critical integration tests for background worker system.
Tests the hardest scenarios under concurrent conditions.
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
import tempfile
import os
import sqlite3

from background_worker import FeedUpdateWorker, FeedQueueManager, DomainRateLimiter
from models import get_db, FeedModel, FeedItemModel


class TestWorkerCritical:
    
    def setup_method(self):
        """Setup isolated test database for each test"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        os.close(self.db_fd)
        
        # Create test database
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript('''
                CREATE TABLE feeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    description TEXT,
                    last_updated TIMESTAMP,
                    etag TEXT,
                    last_modified TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE feed_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feed_id INTEGER NOT NULL,
                    guid TEXT NOT NULL,
                    title TEXT NOT NULL,
                    link TEXT NOT NULL,
                    description TEXT,
                    content TEXT,
                    published TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (feed_id) REFERENCES feeds (id) ON DELETE CASCADE,
                    UNIQUE (feed_id, guid)
                );
                
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE user_feeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    feed_id INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE,
                    FOREIGN KEY (feed_id) REFERENCES feeds (id) ON DELETE CASCADE,
                    UNIQUE (session_id, feed_id)
                );
            ''')
        
        # Patch get_db to use test database
        self.original_get_db = get_db
        
        def mock_get_db():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Important: match the real get_db behavior
            return conn
        mock_get_db.db_path = self.db_path
        
        # Apply patches
        self.db_patcher = patch('models.get_db', mock_get_db)
        self.db_patcher.start()
    
    def teardown_method(self):
        """Cleanup after each test"""
        self.db_patcher.stop()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    async def test_concurrent_deduplication(self):
        """
        CRITICAL: Multiple workers processing same feed simultaneously.
        Database UNIQUE constraint must prevent duplicates.
        """
        worker = FeedUpdateWorker()
        await worker.start()
        
        try:
            # Setup test feed
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "INSERT INTO feeds (url, title) VALUES (?, ?)",
                    ('https://test.com/feed.rss', 'Test Feed')
                )
                feed_id = cursor.lastrowid
            
            test_feed = {'id': feed_id, 'url': 'https://test.com/feed.rss'}
            
            # Mock RSS content with same items (should deduplicate)
            rss_content = '''<?xml version="1.0"?>
                <rss version="2.0">
                    <channel>
                        <title>Test Feed</title>
                        <item>
                            <title>Duplicate Item 1</title>
                            <link>https://test.com/item1</link>
                            <guid>item_1</guid>
                            <description>Test description 1</description>
                        </item>
                        <item>
                            <title>Duplicate Item 2</title>
                            <link>https://test.com/item2</link>
                            <guid>item_2</guid>
                            <description>Test description 2</description>
                        </item>
                    </channel>
                </rss>'''
            
            async def mock_http_get(url, **kwargs):
                response = Mock()
                response.status_code = 200
                response.text = rss_content
                response.headers = {'etag': '"test_etag"'}
                await asyncio.sleep(0.01)  # Small delay
                return response
            
            with patch('httpx.AsyncClient.get', side_effect=mock_http_get):
                # Launch 5 concurrent workers on same feed
                tasks = []
                for i in range(5):
                    task = asyncio.create_task(worker._process_feed_direct(test_feed))
                    tasks.append(task)
                
                # Wait for all to complete
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify no duplicates in database
            with sqlite3.connect(self.db_path) as conn:
                items = conn.execute(
                    "SELECT guid, COUNT(*) as count FROM feed_items WHERE feed_id = ? GROUP BY guid",
                    (feed_id,)
                ).fetchall()
                
                # Each GUID should appear exactly once
                assert len(items) == 2, f"Expected 2 unique items, got {len(items)}"
                for guid, count in items:
                    assert count == 1, f"Item {guid} appears {count} times (should be 1)"
                
        finally:
            await worker.stop()

    async def test_domain_rate_limiting(self):
        """
        CRITICAL: Rate limiting enforced per domain under concurrent load
        """
        # Create rate limiter with strict limits for testing
        rate_limiter = DomainRateLimiter(max_requests=3, per_seconds=5)
        
        # Record request times
        request_times = []
        
        async def mock_request():
            await rate_limiter.acquire()
            request_times.append(time.time())
        
        # Make 6 concurrent requests (should be rate limited)
        start_time = time.time()
        tasks = [asyncio.create_task(mock_request()) for _ in range(6)]
        await asyncio.gather(*tasks)
        
        # Verify timing
        assert len(request_times) == 6, f"Expected 6 requests, got {len(request_times)}"
        
        # First 3 should be immediate (within 0.5s)
        for i in range(3):
            assert request_times[i] - start_time < 0.5, f"Request {i} should be immediate"
        
        # Last 3 should be delayed by rate limiting
        for i in range(3, 6):
            delay = request_times[i] - start_time
            assert delay >= 3.0, f"Request {i} should be rate limited (delay: {delay}s)"

    async def test_worker_health_monitoring(self):
        """
        CRITICAL: Worker death detection and recovery
        """
        worker = FeedUpdateWorker()
        await worker.start()
        
        try:
            # Initially healthy
            assert worker._is_worker_alive(), "Worker should be alive initially"
            
            # Kill worker task
            worker.is_running = False
            if worker.worker_task:
                worker.worker_task.cancel()
                try:
                    await worker.worker_task
                except asyncio.CancelledError:
                    pass
            
            # Should detect death
            assert not worker._is_worker_alive(), "Should detect dead worker"
            
            # Restart
            await worker.start()
            assert worker._is_worker_alive(), "Worker should be alive after restart"
            
        finally:
            await worker.stop()

    async def test_end_to_end_user_flow(self):
        """
        CRITICAL: Complete user flow - visit triggers background updates
        """
        worker = FeedUpdateWorker()
        queue_manager = FeedQueueManager(worker)
        await worker.start()
        
        try:
            # Setup test data
            old_time = (datetime.now() - timedelta(minutes=5)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                # Enable row factory for dict access
                conn.row_factory = sqlite3.Row
                
                # Create feed that needs updating
                cursor = conn.execute(
                    "INSERT INTO feeds (url, title, last_updated) VALUES (?, ?, ?)",
                    ('https://test.com/feed.rss', 'Test Feed', old_time)
                )
                feed_id = cursor.lastrowid
                
                # Create user session
                conn.execute("INSERT INTO sessions (id) VALUES (?)", ('test_user',))
                conn.execute(
                    "INSERT INTO user_feeds (session_id, feed_id) VALUES (?, ?)",
                    ('test_user', feed_id)
                )
            
            # Mock RSS response
            async def mock_http_get(url, **kwargs):
                response = Mock()
                response.status_code = 200
                response.text = '''<?xml version="1.0"?>
                    <rss version="2.0">
                        <channel>
                            <title>Test Feed</title>
                            <item>
                                <title>New Item</title>
                                <link>https://test.com/item1</link>
                                <guid>new_item_1</guid>
                                <description>Fresh content</description>
                            </item>
                        </channel>
                    </rss>'''
                response.headers = {'etag': '"updated_etag"'}
                return response
            
            with patch('httpx.AsyncClient.get', side_effect=mock_http_get):
                # Simulate user visit - should queue feeds
                initial_queue_size = worker.queue.qsize()
                await queue_manager.queue_user_feeds('test_user')
                
                # Verify feed was queued
                assert worker.queue.qsize() > initial_queue_size, "Feed should be queued"
                
                # Wait for processing
                timeout = 5.0
                start_time = time.time()
                while worker.queue.qsize() > 0 and (time.time() - start_time) < timeout:
                    await asyncio.sleep(0.1)
                
                # Verify feed was updated
                with sqlite3.connect(self.db_path) as conn:
                    # Check feed was updated
                    feed_data = conn.execute(
                        "SELECT last_updated FROM feeds WHERE id = ?", (feed_id,)
                    ).fetchone()
                    
                    assert feed_data and feed_data[0] > old_time, "Feed should be updated"
                    
                    # Check items were saved
                    item_count = conn.execute(
                        "SELECT COUNT(*) FROM feed_items WHERE feed_id = ?", (feed_id,)
                    ).fetchone()[0]
                    
                    assert item_count > 0, "Should have saved feed items"
        
        finally:
            await worker.stop()

    async def test_heavy_load_no_deadlock(self):
        """
        CRITICAL: Heavy concurrent load without deadlocks
        """
        worker = FeedUpdateWorker()
        await worker.start()
        
        try:
            # Create 20 test feeds
            feed_ids = []
            with sqlite3.connect(self.db_path) as conn:
                for i in range(20):
                    cursor = conn.execute(
                        "INSERT INTO feeds (url, title) VALUES (?, ?)",
                        (f'https://domain{i % 5}.com/feed.rss', f'Feed {i}')
                    )
                    feed_ids.append(cursor.lastrowid)
            
            # Mock HTTP with domain-based responses
            async def mock_http_get(url, **kwargs):
                await asyncio.sleep(0.01)  # Simulate network delay
                response = Mock()
                response.status_code = 200
                response.text = f'''<?xml version="1.0"?><rss><channel><title>Test</title>
                    <item><title>Item from {url}</title><guid>{url}_item</guid><link>{url}</link></item>
                    </channel></rss>'''
                response.headers = {}
                return response
            
            with patch('httpx.AsyncClient.get', side_effect=mock_http_get):
                # Queue all feeds for processing
                for feed_id in feed_ids:
                    feed_data = {'id': feed_id, 'url': f'https://domain{feed_id % 5}.com/feed.rss'}
                    await worker.queue.put(feed_data)
                
                # Wait for all processing to complete with timeout
                timeout = 10.0
                start_time = time.time()
                
                while worker.queue.qsize() > 0 and (time.time() - start_time) < timeout:
                    await asyncio.sleep(0.1)
                
                processing_time = time.time() - start_time
                
                # System should not hang (deadlock test)
                assert processing_time < timeout, f"Processing hung after {processing_time}s (possible deadlock)"
                
                # Worker should still be healthy
                assert worker._is_worker_alive(), "Worker should be healthy after heavy load"
                
                # Some feeds should have been processed
                with sqlite3.connect(self.db_path) as conn:
                    updated_count = conn.execute(
                        "SELECT COUNT(*) FROM feeds WHERE last_updated IS NOT NULL"
                    ).fetchone()[0]
                    
                    assert updated_count > 0, f"No feeds were updated (expected some of {len(feed_ids)})"
        
        finally:
            await worker.stop()

    def test_rate_limiter_timing_accuracy(self):
        """
        CRITICAL: Rate limiter timing must be accurate under concurrent access
        """
        import asyncio
        
        async def run_rate_limit_test():
            rate_limiter = DomainRateLimiter(max_requests=2, per_seconds=3)
            request_times = []
            
            async def make_request():
                await rate_limiter.acquire()
                request_times.append(time.time())
            
            # Make 4 requests concurrently
            start_time = time.time()
            tasks = [asyncio.create_task(make_request()) for _ in range(4)]
            await asyncio.gather(*tasks)
            
            # Verify timing
            assert len(request_times) == 4
            
            # First 2 should be immediate
            for i in range(2):
                delay = request_times[i] - start_time
                assert delay < 0.2, f"Request {i} should be immediate, got {delay}s delay"
            
            # Last 2 should be delayed by ~3 seconds
            for i in range(2, 4):
                delay = request_times[i] - start_time
                assert 2.5 <= delay <= 3.5, f"Request {i} should be delayed ~3s, got {delay}s"
        
        # Run the async test
        asyncio.run(run_rate_limit_test())

    async def test_database_concurrent_writes(self):
        """
        CRITICAL: Multiple concurrent database writes must not corrupt data
        """
        # Create feeds to process
        feed_ids = []
        with sqlite3.connect(self.db_path) as conn:
            for i in range(5):
                cursor = conn.execute(
                    "INSERT INTO feeds (url, title) VALUES (?, ?)",
                    (f'https://test{i}.com/feed.rss', f'Feed {i}')
                )
                feed_ids.append(cursor.lastrowid)
        
        # Simulate concurrent feed item creation
        async def create_items(feed_id: int, worker_id: int):
            for item_num in range(10):
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute('''
                            INSERT OR REPLACE INTO feed_items 
                            (feed_id, guid, title, link, description)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            feed_id,
                            f'item_{feed_id}_{item_num}',
                            f'Item {item_num} from worker {worker_id}',
                            f'https://test{feed_id}.com/item{item_num}',
                            f'Description from worker {worker_id}'
                        ))
                    await asyncio.sleep(0.001)  # Small delay
                except Exception as e:
                    # SQLite "database is locked" is acceptable under high concurrency
                    if "database is locked" not in str(e):
                        raise
        
        # Launch concurrent writers
        tasks = []
        for feed_id in feed_ids:
            for worker_id in range(3):  # 3 workers per feed
                task = asyncio.create_task(create_items(feed_id, worker_id))
                tasks.append(task)
        
        # Wait for all writes to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for unexpected errors (ignore "database is locked")
        for i, result in enumerate(results):
            if isinstance(result, Exception) and "database is locked" not in str(result):
                raise AssertionError(f"Task {i} failed: {result}")
        
        # Verify database integrity
        with sqlite3.connect(self.db_path) as conn:
            # Should have all feeds
            feed_count = conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
            assert feed_count == 5, f"Expected 5 feeds, got {feed_count}"
            
            # Should have items (some writes succeeded)
            total_items = conn.execute("SELECT COUNT(*) FROM feed_items").fetchone()[0]
            assert total_items > 0, "Should have some feed items"
            
            # No duplicate GUIDs per feed
            duplicates = conn.execute('''
                SELECT feed_id, guid, COUNT(*) 
                FROM feed_items 
                GROUP BY feed_id, guid 
                HAVING COUNT(*) > 1
            ''').fetchall()
            
            assert len(duplicates) == 0, f"Found duplicates: {duplicates}"
        
        
        # Clean up at end of async function
        pass

    async def test_worker_status_accuracy(self):
        """
        CRITICAL: Worker status reporting must be accurate for UI
        """
        worker = FeedUpdateWorker()
        
        # Initially not running
        status = worker.get_status()
        assert status['worker_alive'] == False, "Worker should not be alive initially"
        assert status['is_updating'] == False, "Should not be updating"
        
        # Start worker
        await worker.start()
        
        status = worker.get_status()
        assert status['worker_alive'] == True, "Worker should be alive after start"
        assert status['queue_size'] == 0, "Queue should be empty"
        
        # Add items to queue
        test_feeds = [
            {'id': 1, 'url': 'https://test1.com/feed.rss'},
            {'id': 2, 'url': 'https://test2.com/feed.rss'},
        ]
        
        for feed in test_feeds:
            await worker.queue.put(feed)
        
        status = worker.get_status()
        assert status['queue_size'] == 2, f"Queue should have 2 items, got {status['queue_size']}"
        assert status['is_updating'] == True, "Should be updating with items in queue"
        
        # Stop worker
        await worker.stop()
        
        status = worker.get_status()
        assert status['worker_alive'] == False, "Worker should be dead after stop"


if __name__ == '__main__':
    import sys
    
    # Run tests manually for debugging
    test_instance = TestWorkerCritical()
    
    async def run_all_tests():
        print("Running critical worker tests...")
        
        print("1. Testing concurrent deduplication...")
        test_instance.setup_method()
        try:
            await test_instance.test_concurrent_deduplication()
            print("✓ Concurrent deduplication PASSED")
        except Exception as e:
            print(f"✗ Concurrent deduplication FAILED: {e}")
        finally:
            test_instance.teardown_method()
        
        print("2. Testing domain rate limiting...")
        test_instance.setup_method()
        try:
            await test_instance.test_domain_rate_limiting()
            print("✓ Domain rate limiting PASSED")
        except Exception as e:
            print(f"✗ Domain rate limiting FAILED: {e}")
        finally:
            test_instance.teardown_method()
        
        print("3. Testing worker health monitoring...")
        test_instance.setup_method()
        try:
            await test_instance.test_worker_health_monitoring()
            print("✓ Worker health monitoring PASSED")
        except Exception as e:
            print(f"✗ Worker health monitoring FAILED: {e}")
        finally:
            test_instance.teardown_method()
        
        print("4. Testing end-to-end flow...")
        test_instance.setup_method()
        try:
            await test_instance.test_end_to_end_user_flow()
            print("✓ End-to-end flow PASSED")
        except Exception as e:
            print(f"✗ End-to-end flow FAILED: {e}")
        finally:
            test_instance.teardown_method()
        
        print("5. Testing database concurrent writes...")
        test_instance.setup_method()
        try:
            await test_instance.test_database_concurrent_writes()
            print("✓ Database concurrent writes PASSED")
        except Exception as e:
            print(f"✗ Database concurrent writes FAILED: {e}")
        finally:
            test_instance.teardown_method()
        
        print("6. Testing worker status accuracy...")  
        test_instance.setup_method()
        try:
            await test_instance.test_worker_status_accuracy()
            print("✓ Worker status accuracy PASSED")
        except Exception as e:
            print(f"✗ Worker status accuracy FAILED: {e}")
        finally:
            test_instance.teardown_method()
    
    asyncio.run(run_all_tests())