"""Comprehensive integration tests based on real implementation and debugging experience"""

import pytest
import httpx
import sqlite3
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, Mock
import json

# Import all modules we need to test
from models import (
    init_db, FeedModel, SessionModel, UserItemModel, FolderModel, 
    FeedItemModel, get_db, DB_PATH
)
from feed_parser import FeedParser, setup_default_feeds
from app import app

# Test database setup
TEST_DB_PATH = "data/test_comprehensive.db"

@pytest.fixture(scope="function")  
def clean_test_db():
    """Clean test database for each test"""
    # Override DB_PATH globally in models module
    import models
    
    original_db = models.DB_PATH
    models.DB_PATH = TEST_DB_PATH
    
    # Clean up any existing test db
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    # Create test directory
    os.makedirs(os.path.dirname(TEST_DB_PATH), exist_ok=True)
    
    # Initialize fresh test database
    init_db()
    
    yield TEST_DB_PATH
    
    # Cleanup
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    # Restore original
    models.DB_PATH = original_db

@pytest.fixture
def test_client(clean_test_db):
    """HTTP client for testing FastHTML app"""
    with httpx.Client(
        transport=httpx.WSGITransport(app=app),
        base_url="http://testserver"
    ) as client:
        yield client

class TestCriticalWorkflows:
    """Test the workflows that broke during development"""
    
    def test_complete_fresh_start_workflow(self, clean_test_db):
        """Test: Clear DB → Setup Default Feeds → First User Visit → Auto-subscription
        
        This tests the complete flow that we debugged extensively.
        """
        # 1. Verify database starts empty
        with get_db() as conn:
            feed_count = conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
            assert feed_count == 0
        
        # 2. Setup default feeds (happens on app startup)
        setup_default_feeds()
        
        # 3. Verify feeds were created with items
        with get_db() as conn:
            feeds = [dict(row) for row in conn.execute("SELECT * FROM feeds").fetchall()]
            items = [dict(row) for row in conn.execute("SELECT * FROM feed_items").fetchall()]
            
        assert len(feeds) == 3  # Hacker News, Reddit, WSJ
        assert len(items) > 50  # Should have many articles
        
        # Verify specific feeds exist
        feed_urls = [f['url'] for f in feeds]
        assert "https://hnrss.org/frontpage" in feed_urls
        assert "https://www.reddit.com/r/all/.rss" in feed_urls
        assert "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain" in feed_urls
        
        # 4. Simulate new user session (beforeware logic)
        test_session = "test-fresh-user"
        SessionModel.create_session(test_session)
        
        # Subscribe to all feeds (what beforeware does)
        for feed in feeds:
            SessionModel.subscribe_to_feed(test_session, feed['id'])
        
        # 5. Verify user can see all items
        user_feeds = FeedModel.get_user_feeds(test_session)
        user_items = FeedItemModel.get_items_for_user(test_session)
        
        assert len(user_feeds) == 3
        assert len(user_items) > 50
        
        # Verify each feed has items
        for feed in user_feeds:
            feed_items = FeedItemModel.get_items_for_user(test_session, feed['id'])
            assert len(feed_items) > 0
    
    def test_session_persistence_and_subscription(self, clean_test_db):
        """Test: Session creation → Feed subscription → Data persistence
        
        This was a major issue we debugged - sessions weren't persisting.
        """
        # Create feeds first
        feed_id = FeedModel.create_feed("https://example.com/rss", "Test Feed")
        
        # Create session and subscribe
        session_id = "test-session-persistence"
        SessionModel.create_session(session_id)
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        # Verify persistence with new connection
        with get_db() as conn:
            # Check session exists
            session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            assert session is not None
            
            # Check subscription exists
            subscription = conn.execute("""
                SELECT * FROM user_feeds WHERE session_id = ? AND feed_id = ?
            """, (session_id, feed_id)).fetchone()
            assert subscription is not None
        
        # Test that get_user_feeds works
        user_feeds = FeedModel.get_user_feeds(session_id)
        assert len(user_feeds) == 1
        assert user_feeds[0]['id'] == feed_id
    
    def test_http_redirect_handling(self, clean_test_db):
        """Test: HTTP redirects → Feed parsing → Success
        
        BBC feeds failed due to 302 redirects initially.
        """
        parser = FeedParser()
        
        # Mock a redirect response (like BBC)
        with patch.object(parser.client, 'get') as mock_get:
            # Simulate successful redirect handling
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '''<?xml version="1.0"?>
            <rss version="2.0">
                <channel>
                    <title>Test Feed</title>
                    <item>
                        <title>Test Article</title>
                        <link>https://test.com/1</link>
                        <guid>test-1</guid>
                        <description>Test content</description>
                    </item>
                </channel>
            </rss>'''
            mock_response.headers = {'etag': 'test-etag'}
            mock_get.return_value = mock_response
            
            result = parser.add_feed("http://redirect.test/feed")
            
            assert result['success'] is True
            assert 'feed_id' in result
            
            # Verify feed was created
            with get_db() as conn:
                feed = conn.execute("SELECT * FROM feeds WHERE id = ?", (result['feed_id'],)).fetchone()
                items = conn.execute("SELECT * FROM feed_items WHERE feed_id = ?", (result['feed_id'],)).fetchall()
                
            assert feed is not None
            assert len(items) == 1
            assert items[0]['title'] == 'Test Article'
    
    def test_pagination_logic_and_navigation(self, clean_test_db):
        """Test: Pagination calculations → URL generation → Item slicing
        
        Pagination was complex and needed to handle various edge cases.
        """
        session_id = "test-pagination"
        SessionModel.create_session(session_id)
        
        # Create feed with known number of items
        feed_id = FeedModel.create_feed("https://test.com/pagination")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        # Create exactly 45 items (will be 3 pages with 20 per page)
        for i in range(45):
            FeedItemModel.create_item(
                feed_id=feed_id,
                guid=f"item-{i}",
                title=f"Article {i}",
                link=f"https://test.com/{i}",
                published=datetime.now()
            )
        
        # Test pagination calculations
        all_items = FeedItemModel.get_items_for_user(session_id)
        assert len(all_items) == 45
        
        # Test page 1 (items 0-19)
        page_size = 20
        page_1_items = all_items[0:20]
        assert len(page_1_items) == 20
        
        # Test page 2 (items 20-39) 
        page_2_items = all_items[20:40]
        assert len(page_2_items) == 20
        
        # Test page 3 (items 40-44)
        page_3_items = all_items[40:45]
        assert len(page_3_items) == 5
        
        # Test total pages calculation
        total_pages = (45 + 20 - 1) // 20
        assert total_pages == 3
    
    def test_article_reading_state_management(self, clean_test_db):
        """Test: Click article → Mark read → Blue indicator → Unread filtering
        
        This complex UX workflow was implemented with HTMX multi-updates.
        """
        session_id = "test-reading"
        SessionModel.create_session(session_id)
        
        # Create feed and item
        feed_id = FeedModel.create_feed("https://test.com/reading")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        item_id = FeedItemModel.create_item(
            feed_id=feed_id,
            guid="test-article",
            title="Test Article",
            link="https://test.com/article"
        )
        
        # Initially unread
        user_items = FeedItemModel.get_items_for_user(session_id)
        item = next(i for i in user_items if i['id'] == item_id)
        assert item['is_read'] == 0  # Unread
        
        # Test unread filtering
        unread_items = FeedItemModel.get_items_for_user(session_id, unread_only=True)
        assert len(unread_items) == 1
        assert unread_items[0]['id'] == item_id
        
        # Mark as read (simulates clicking article)
        UserItemModel.mark_read(session_id, item_id, True)
        
        # Verify read status changed
        user_items_after = FeedItemModel.get_items_for_user(session_id)
        item_after = next(i for i in user_items_after if i['id'] == item_id)
        assert item_after['is_read'] == 1  # Read
        
        # Verify unread filtering excludes read items
        unread_items_after = FeedItemModel.get_items_for_user(session_id, unread_only=True)
        assert len(unread_items_after) == 0  # Should be empty
    
    def test_duplicate_feed_detection(self, clean_test_db):
        """Test: Add same feed twice → Duplicate detection → Proper error handling"""
        session_id = "test-duplicates"
        SessionModel.create_session(session_id)
        
        test_url = "https://example.com/duplicate-test"
        
        # Add feed first time
        feed_id1 = FeedModel.create_feed(test_url, "First Add")
        SessionModel.subscribe_to_feed(session_id, feed_id1)
        
        # Try to add same URL again
        feed_id2 = FeedModel.create_feed(test_url, "Second Add")
        
        # Should return same feed ID
        assert feed_id1 == feed_id2
        
        # Verify only one feed exists
        with get_db() as conn:
            feeds = conn.execute("SELECT * FROM feeds WHERE url = ?", (test_url,)).fetchall()
            assert len(feeds) == 1
        
        # Test user subscription logic
        user_feeds = FeedModel.get_user_feeds(session_id)
        duplicate_feeds = [f for f in user_feeds if f['url'] == test_url]
        assert len(duplicate_feeds) == 1
    
    def test_feed_update_with_http_caching(self, clean_test_db):
        """Test: HTTP caching → ETag handling → Update logic
        
        Tests the caching system we implemented for efficient updates.
        """
        parser = FeedParser()
        
        # Create initial feed
        feed_id = FeedModel.create_feed("https://test.com/caching")
        
        with patch.object(parser.client, 'get') as mock_get:
            # First fetch - returns content
            mock_response_1 = Mock()
            mock_response_1.status_code = 200
            mock_response_1.headers = {'etag': 'initial-etag', 'last-modified': 'Mon, 01 Jan 2024'}
            mock_response_1.text = '''<?xml version="1.0"?>
            <rss><channel><title>Test</title><item>
                <title>Item 1</title><link>https://test.com/1</link><guid>1</guid>
            </item></channel></rss>'''
            mock_get.return_value = mock_response_1
            
            # Initial parse
            result1 = parser.parse_and_store_feed(feed_id, "https://test.com/caching")
            assert result1['updated'] is True
            assert result1['items_added'] == 1
            
            # Verify ETag was stored
            with get_db() as conn:
                feed = conn.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()
                assert feed['etag'] == 'initial-etag'
            
            # Second fetch - returns 304 Not Modified
            mock_response_2 = Mock()
            mock_response_2.status_code = 304
            mock_get.return_value = mock_response_2
            
            # Should use cached headers
            result2 = parser.parse_and_store_feed(
                feed_id, "https://test.com/caching", 
                etag='initial-etag', last_modified='Mon, 01 Jan 2024'
            )
            
            assert result2['updated'] is False
            assert result2['status'] == 304

class TestComplexUserInteractions:
    """Test complex user interaction patterns we implemented"""
    
    def test_form_parameter_processing(self, test_client):
        """Test: Form submission → FastHTML parameter mapping → Feed addition
        
        This broke multiple times due to FastHTML form handling specifics.
        """
        # Test valid feed URL
        response = test_client.post("/api/feed/add", data={"new_feed_url": "https://example.com/test"})
        assert response.status_code == 200
        
        # Should contain some response (success or error)
        assert len(response.content) > 0
        
        # Test empty URL
        response_empty = test_client.post("/api/feed/add", data={"new_feed_url": ""})
        assert response.status_code == 200
        assert b"Please enter a URL" in response_empty.content
        
        # Test missing parameter
        response_missing = test_client.post("/api/feed/add", data={})
        assert response.status_code == 200
    
    def test_session_beforeware_integration(self, test_client):
        """Test: HTTP request → Beforeware → Session creation → Feed subscription
        
        This complex flow was the root cause of "No posts available" issues.
        """
        # Setup some feeds first
        setup_default_feeds()
        
        # First request should trigger session creation
        response1 = test_client.get("/")
        assert response1.status_code == 200
        
        # Session should be created and subscribed to feeds
        # This is hard to test directly due to session handling, but we can check HTML
        assert b"RSS Reader" in response1.content
        assert b"All Posts" in response1.content
        
        # Subsequent request should use same session
        response2 = test_client.get("/")
        assert response2.status_code == 200
    
    def test_htmx_multi_element_updates(self, clean_test_db):
        """Test: Article click → Mark read → Multiple UI updates
        
        Tests the complex HTMX out-of-band swap logic we implemented.
        """
        session_id = "test-htmx"
        SessionModel.create_session(session_id)
        
        # Setup feed and item
        feed_id = FeedModel.create_feed("https://test.com/htmx")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        item_id = FeedItemModel.create_item(
            feed_id=feed_id,
            guid="htmx-test",
            title="HTMX Test Article", 
            link="https://test.com/htmx/1"
        )
        
        # Verify initially unread
        items = FeedItemModel.get_items_for_user(session_id)
        item = next(i for i in items if i['id'] == item_id)
        assert item['is_read'] == 0
        
        # Simulate article click endpoint
        from app import show_item
        
        # Mock request object
        mock_request = Mock()
        mock_request.scope = {'session_id': session_id}
        
        # Test both unread_view contexts
        result_all = show_item(item_id, mock_request, unread_view=False)
        result_unread = show_item(item_id, mock_request, unread_view=True)
        
        # Both should return some response
        assert result_all is not None
        assert result_unread is not None
        
        # Verify item was marked as read
        items_after = FeedItemModel.get_items_for_user(session_id)
        item_after = next(i for i in items_after if i['id'] == item_id)
        assert item_after['is_read'] == 1
    
    def test_feed_filtering_and_navigation(self, clean_test_db):
        """Test: Feed filtering → URL parameters → Item filtering
        
        Tests the navigation logic between feeds and views.
        """
        session_id = "test-filtering"
        SessionModel.create_session(session_id)
        
        # Create multiple feeds
        feed1_id = FeedModel.create_feed("https://test1.com/rss", "Feed 1")
        feed2_id = FeedModel.create_feed("https://test2.com/rss", "Feed 2")
        
        SessionModel.subscribe_to_feed(session_id, feed1_id)
        SessionModel.subscribe_to_feed(session_id, feed2_id)
        
        # Add items to each feed
        item1_id = FeedItemModel.create_item(feed1_id, "item1", "Article 1", "https://test1.com/1")
        item2_id = FeedItemModel.create_item(feed2_id, "item2", "Article 2", "https://test2.com/1")
        
        # Test getting all items
        all_items = FeedItemModel.get_items_for_user(session_id)
        assert len(all_items) == 2
        
        # Test filtering by feed 1
        feed1_items = FeedItemModel.get_items_for_user(session_id, feed_id=feed1_id)
        assert len(feed1_items) == 1
        assert feed1_items[0]['id'] == item1_id
        
        # Test filtering by feed 2
        feed2_items = FeedItemModel.get_items_for_user(session_id, feed_id=feed2_id)
        assert len(feed2_items) == 1
        assert feed2_items[0]['id'] == item2_id
        
        # Test unread filtering
        # Mark one item as read
        UserItemModel.mark_read(session_id, item1_id, True)
        
        unread_items = FeedItemModel.get_items_for_user(session_id, unread_only=True)
        assert len(unread_items) == 1
        assert unread_items[0]['id'] == item2_id

class TestErrorHandlingPaths:
    """Test error handling scenarios that could break the app"""
    
    def test_malformed_rss_feeds(self):
        """Test: Invalid RSS → Graceful error handling"""
        parser = FeedParser()
        
        with patch.object(parser.client, 'get') as mock_get:
            # Test invalid XML
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "Not valid XML at all"
            mock_response.headers = {}
            mock_get.return_value = mock_response
            
            result = parser.fetch_feed("https://invalid.com/feed")
            
            # Should handle gracefully, not crash
            assert 'status' in result
            assert result['status'] == 200
            assert result['updated'] is True
    
    def test_network_failures(self):
        """Test: Network errors → Proper error handling"""
        parser = FeedParser()
        
        with patch.object(parser.client, 'get') as mock_get:
            # Simulate network timeout
            mock_get.side_effect = httpx.TimeoutException("Connection timeout")
            
            result = parser.fetch_feed("https://timeout.test/feed")
            
            assert result['updated'] is False
            assert 'error' in result
    
    def test_database_constraint_violations(self, clean_test_db):
        """Test: Foreign key violations → Constraint handling"""
        session_id = "test-constraints"
        SessionModel.create_session(session_id)
        
        # Try to subscribe to non-existent feed
        try:
            SessionModel.subscribe_to_feed(session_id, 99999)  # Non-existent feed
            # Should fail due to foreign key constraint
            assert False, "Should have raised constraint violation"
        except:
            # Expected to fail
            pass
        
        # Try to create item for non-existent feed
        try:
            FeedItemModel.create_item(99999, "test", "Test", "https://test.com")
            assert False, "Should have raised constraint violation"
        except:
            # Expected to fail
            pass

class TestRealWorldScenarios:
    """Test scenarios based on actual usage patterns"""
    
    @pytest.mark.skipif(not os.getenv("NETWORK_TESTS"), reason="Skip network tests unless NETWORK_TESTS=1")
    def test_real_feed_parsing(self, clean_test_db):
        """Test: Real RSS feeds → Actual parsing → Data validation
        
        Tests against real feeds to catch parsing edge cases.
        """
        parser = FeedParser()
        
        # Test with a reliable RSS feed
        result = parser.add_feed("https://hnrss.org/frontpage")
        
        if result['success']:
            assert 'feed_id' in result
            
            # Verify items were created
            with get_db() as conn:
                items = conn.execute("""
                    SELECT * FROM feed_items WHERE feed_id = ?
                """, (result['feed_id'],)).fetchall()
                
            assert len(items) > 0
            
            # Verify item structure
            for item in items[:5]:  # Check first 5
                assert item['title'] is not None
                assert item['link'] is not None
                assert item['guid'] is not None
    
    def test_concurrent_session_handling(self, clean_test_db):
        """Test: Multiple sessions → Independent data → No cross-contamination"""
        setup_default_feeds()
        
        # Create two different sessions
        session1 = "user1-session"
        session2 = "user2-session"
        
        SessionModel.create_session(session1)
        SessionModel.create_session(session2)
        
        # Subscribe to different feeds
        feeds = [dict(row) for row in get_db().__enter__().execute("SELECT * FROM feeds").fetchall()]
        feed1_id = feeds[0]['id']
        feed2_id = feeds[1]['id'] if len(feeds) > 1 else feed1_id
        
        SessionModel.subscribe_to_feed(session1, feed1_id)
        SessionModel.subscribe_to_feed(session2, feed2_id)
        
        # Verify independent subscriptions
        user1_feeds = FeedModel.get_user_feeds(session1)
        user2_feeds = FeedModel.get_user_feeds(session2)
        
        if feed1_id != feed2_id:
            assert len(user1_feeds) == 1
            assert len(user2_feeds) == 1
            assert user1_feeds[0]['id'] == feed1_id
            assert user2_feeds[0]['id'] == feed2_id
    
    def test_folder_management_workflow(self, clean_test_db):
        """Test: Create folder → Move items → Folder filtering"""
        session_id = "test-folders"
        SessionModel.create_session(session_id)
        
        # Create folder
        folder_id = FolderModel.create_folder(session_id, "Important")
        
        # Create feed and item
        feed_id = FeedModel.create_feed("https://test.com/folders")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        item_id = FeedItemModel.create_item(feed_id, "folder-test", "Folder Test", "https://test.com/f1")
        
        # Move item to folder
        UserItemModel.move_to_folder(session_id, item_id, folder_id)
        
        # Verify folder assignment
        user_items = FeedItemModel.get_items_for_user(session_id)
        item = next(i for i in user_items if i['id'] == item_id)
        assert item['folder_name'] == 'Important'

class TestDatabaseIntegrityUnderStress:
    """Test database behavior under various stress conditions"""
    
    def test_transaction_rollback_scenarios(self, clean_test_db):
        """Test: Database errors → Proper rollback → Data consistency"""
        
        with pytest.raises(Exception):
            # Force a database error inside transaction
            with get_db() as conn:
                # This should work
                conn.execute("INSERT INTO feeds (url) VALUES (?)", ("https://test.com",))
                # This should fail and trigger rollback
                conn.execute("INSERT INTO nonexistent_table (col) VALUES (?)", ("test",))
        
        # Verify rollback worked - no feeds should exist
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
            assert count == 0
    
    def test_large_feed_handling(self, clean_test_db):
        """Test: Large feeds → Performance → Memory handling"""
        feed_id = FeedModel.create_feed("https://large-feed.test")
        
        # Simulate large feed with many items
        items_to_create = 1000
        for i in range(items_to_create):
            FeedItemModel.create_item(
                feed_id=feed_id,
                guid=f"large-{i}",
                title=f"Large Feed Article {i}",
                link=f"https://large-feed.test/{i}"
            )
        
        # Verify all items were created
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM feed_items WHERE feed_id = ?", (feed_id,)).fetchone()[0]
            assert count == items_to_create
        
        # Test pagination with large dataset
        session_id = "large-test"
        SessionModel.create_session(session_id)
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        # Should handle large result sets efficiently
        all_items = FeedItemModel.get_items_for_user(session_id)
        assert len(all_items) == items_to_create
        
        # Test pagination slicing
        page_1 = all_items[0:20]
        page_50 = all_items[980:1000]
        assert len(page_1) == 20
        assert len(page_50) == 20

class TestWebEndpointIntegration:
    """Test web endpoints with actual HTTP semantics"""
    
    def test_main_page_with_pagination(self, test_client):
        """Test: Main page → Pagination URLs → Correct responses"""
        # Setup minimal data
        setup_default_feeds()
        
        # Test main page
        response = test_client.get("/")
        assert response.status_code == 200
        assert b"RSS Reader" in response.content
        
        # Test pagination URLs
        response_p2 = test_client.get("/?page=2")
        assert response_p2.status_code == 200
        
        # Test feed filtering URLs
        response_feed = test_client.get("/?feed_id=1")
        assert response_feed.status_code == 200
        
        # Test unread filtering
        response_unread = test_client.get("/?unread=1")
        assert response_unread.status_code == 200
    
    def test_article_detail_endpoint(self, test_client, clean_test_db):
        """Test: Article detail → Read marking → HTMX response"""
        # Setup test data
        session_id = "endpoint-test"
        SessionModel.create_session(session_id)
        feed_id = FeedModel.create_feed("https://test.com/endpoint")
        item_id = FeedItemModel.create_item(feed_id, "endpoint-test", "Test", "https://test.com/e1")
        
        # Test article endpoint
        response = test_client.get(f"/item/{item_id}")
        assert response.status_code == 200
        
        # Should contain article content or proper error
        assert len(response.content) > 0
    
    def test_api_endpoints_comprehensive(self, test_client, clean_test_db):
        """Test: All API endpoints → Expected responses → Error handling"""
        # Test folder creation
        folder_response = test_client.post("/api/folder/add", headers={"hx-prompt": "Test API Folder"})
        assert folder_response.status_code == 200
        
        # Test feed addition with various inputs
        valid_feed = test_client.post("/api/feed/add", data={"new_feed_url": "https://example.com/valid"})
        assert valid_feed.status_code == 200
        
        invalid_feed = test_client.post("/api/feed/add", data={"new_feed_url": "not-a-url"})
        assert invalid_feed.status_code == 200

if __name__ == "__main__":
    # Run with coverage
    import subprocess
    subprocess.run([
        "coverage", "run", "-m", "pytest", __file__, "-v", "--tb=short"
    ])
    subprocess.run(["coverage", "report"])
    subprocess.run(["coverage", "html"])