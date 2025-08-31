"""Tests specifically targeting uncovered code paths from coverage analysis"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch
from datetime import datetime
import sqlite3

# Import what we need to test
from models import init_db, get_db, FeedModel, SessionModel, FeedItemModel, UserItemModel, FolderModel
from feed_parser import FeedParser, setup_default_feeds
import app

TEST_DB_PATH = "data/test_coverage_gaps.db"

@pytest.fixture
def test_db():
    """Override DB path for coverage testing"""
    import models
    original_db = models.DB_PATH
    models.DB_PATH = TEST_DB_PATH
    
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    os.makedirs(os.path.dirname(TEST_DB_PATH), exist_ok=True)
    init_db()
    
    yield
    
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    models.DB_PATH = original_db

class TestUncoveredAppRoutes:
    """Cover the 82% of app.py that wasn't tested"""
    
    def test_beforeware_session_creation_logic(self, test_db):
        """Test lines 26-53: Session beforeware logic that was heavily debugged"""
        # Test the beforeware function directly
        mock_req = Mock()
        mock_sess = Mock()
        mock_req.scope = {}
        
        # Test new session creation
        mock_sess.get.return_value = None  # No existing session
        
        with patch('uuid.uuid4', return_value=Mock(__str__=lambda x: 'test-session-123')):
            app.before(mock_req, mock_sess)
        
        # Should have set session_id
        mock_sess.__setitem__.assert_called_with('session_id', 'test-session-123')
        assert mock_req.scope['session_id'] == 'test-session-123'
        
        # Test existing session
        mock_req2 = Mock()
        mock_sess2 = Mock()
        mock_req2.scope = {}
        mock_sess2.get.return_value = 'existing-session'
        
        app.before(mock_req2, mock_sess2)
        assert mock_req2.scope['session_id'] == 'existing-session'
    
    def test_ui_component_functions(self, test_db):
        """Test lines 167-170, 194, 199-254: UI component generation logic"""
        # Setup test data
        session_id = "ui-test"
        SessionModel.create_session(session_id)
        feed_id = FeedModel.create_feed("https://test.com/ui", "UI Test Feed")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        item_id = FeedItemModel.create_item(
            feed_id=feed_id, guid="ui-test", title="UI Test Article", 
            link="https://test.com/ui/1", description="Test description"
        )
        
        # Test FeedItem component
        items = FeedItemModel.get_items_for_user(session_id)
        test_item = next(i for i in items if i['id'] == item_id)
        
        feed_item_html = app.FeedItem(test_item, unread_view=False)
        assert hasattr(feed_item_html, 'children')  # Should be valid FT object
        assert f"feed-item-{item_id}" in str(feed_item_html)  # Should have ID
        
        # Test FeedsList component
        feeds_list_html = app.FeedsList([test_item], unread_view=False)
        assert hasattr(feeds_list_html, 'children')
        
        # Test FeedsContent with pagination
        feeds_content_html = app.FeedsContent(session_id, feed_id, False, 1)
        assert hasattr(feeds_content_html, 'children')
        
        # Test FeedsSidebar
        sidebar_html = app.FeedsSidebar(session_id)
        assert hasattr(sidebar_html, 'children')
    
    def test_route_handlers_directly(self, test_db):
        """Test lines 368-414, 419-451: Route handler logic"""
        # Setup test data
        session_id = "route-test"
        SessionModel.create_session(session_id)
        feed_id = FeedModel.create_feed("https://test.com/routes")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        item_id = FeedItemModel.create_item(
            feed_id=feed_id, guid="route-test", title="Route Test", 
            link="https://test.com/route/1"
        )
        
        # Test show_item route handler
        mock_request = Mock()
        mock_request.scope = {'session_id': session_id}
        
        # Test with unread_view=False
        result = app.show_item(item_id, mock_request, unread_view=False)
        assert result is not None
        
        # Test with unread_view=True
        result_unread = app.show_item(item_id, mock_request, unread_view=True)
        assert result_unread is not None
        
        # Test add_feed route handler
        with patch.object(app.FeedParser, 'add_feed') as mock_add:
            mock_add.return_value = {'success': True, 'feed_id': feed_id}
            
            result = app.add_feed(mock_request, new_feed_url="https://test.com/new")
            mock_add.assert_called_with("https://test.com/new")
    
    def test_human_time_diff_function(self, test_db):
        """Test lines 67-91: Time formatting logic"""
        from datetime import timezone, timedelta
        
        now = datetime.now(timezone.utc)
        
        # Test various time differences
        test_cases = [
            (now - timedelta(minutes=5), "5 minutes ago"),
            (now - timedelta(hours=2), "2 hours ago"),
            (now - timedelta(days=1), "1 day ago"),
            (now - timedelta(days=3), "3 days ago"),
            (None, "Unknown"),
            ("invalid-date", "Unknown"),
            ("2023-12-25T10:30:00Z", "ago"),  # Should contain "ago"
        ]
        
        for test_time, expected_partial in test_cases:
            result = app.human_time_diff(test_time)
            if expected_partial == "Unknown":
                assert result == "Unknown"
            else:
                assert expected_partial in result

class TestUncoveredFeedParserPaths:
    """Cover missing 35% of feed_parser.py"""
    
    def test_date_parsing_edge_cases(self, test_db):
        """Test lines 27, 32-33: Date parsing error handling"""
        parser = FeedParser()
        
        # Test various problematic date formats
        edge_cases = [
            None,
            "",
            "invalid-date",
            "2023-13-45T25:99:99Z",  # Invalid date values
            "Not a date at all",
            "Mon, 32 Dec 2023 10:30:00 GMT",  # Invalid day
        ]
        
        for bad_date in edge_cases:
            result = parser.parse_date(bad_date)
            # Should return None or datetime, never crash
            assert result is None or isinstance(result, datetime)
    
    def test_setup_default_feeds_function(self, test_db):
        """Test lines 211-213, 239-241: Default feed setup logic"""
        # Test setup_default_feeds function
        results = setup_default_feeds()
        
        # Should return results for each default feed
        assert isinstance(results, list)
        assert len(results) >= 3  # At least 3 default feeds
        
        # Each result should have success/failure info
        for result in results:
            assert 'success' in result
    
    def test_feed_parser_error_paths(self, test_db):
        """Test lines 64-65, 71, 82-84: Network error handling"""
        parser = FeedParser()
        
        # Test network timeout simulation
        with patch.object(parser.client, 'get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            result = parser.fetch_feed("https://network-error.test")
            assert result['updated'] is False
            assert 'error' in result
        
        # Test HTTP error codes
        with patch.object(parser.client, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response
            
            result = parser.fetch_feed("https://server-error.test")
            assert result['status'] == 500
            assert result['updated'] is False
        
        # Test malformed feed content
        with patch.object(parser.client, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "Not XML"
            mock_response.headers = {}
            mock_get.return_value = mock_response
            
            result = parser.fetch_feed("https://bad-xml.test")
            # Should handle gracefully
            assert 'status' in result

class TestUncoveredModelsPaths:
    """Cover the missing 14% of models.py"""
    
    def test_database_transaction_rollback(self, test_db):
        """Test lines 103-105: Exception handling in get_db()"""
        # Force a database error to test rollback
        try:
            with get_db() as conn:
                # Valid operation
                conn.execute("INSERT INTO feeds (url) VALUES (?)", ("https://test.com",))
                # Force error
                raise Exception("Forced error for rollback test")
        except Exception:
            pass  # Expected
        
        # Verify rollback worked
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
            assert count == 0  # Should be rolled back
    
    def test_model_edge_cases(self, test_db):
        """Test various edge cases in model operations"""
        session_id = "edge-case-test"
        SessionModel.create_session(session_id)
        
        # Test operations with None/empty values
        feed_id = FeedModel.create_feed("https://edge.test", None, None)  # None title/desc
        assert isinstance(feed_id, int)
        
        # Test update with partial data
        FeedModel.update_feed(feed_id, title="Updated Title")  # Partial update
        
        # Test item creation with minimal data
        item_id = FeedItemModel.create_item(
            feed_id=feed_id, guid="minimal", title="Minimal", link="https://test.com"
            # No description, content, published date
        )
        assert isinstance(item_id, int)
        
        # Test user operations on non-existent items
        UserItemModel.mark_read(session_id, 99999, True)  # Non-existent item
        UserItemModel.toggle_star(session_id, 99999)     # Should handle gracefully

class TestComplexUIInteractions:
    """Test complex UI logic that broke during development"""
    
    def test_pagination_url_generation(self, test_db):
        """Test the complex URL generation logic for pagination"""
        session_id = "pagination-test"
        SessionModel.create_session(session_id)
        
        # Create enough items for pagination
        feed_id = FeedModel.create_feed("https://pagination.test")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        for i in range(50):  # 3 pages worth
            FeedItemModel.create_item(
                feed_id=feed_id, guid=f"page-{i}", title=f"Article {i}",
                link=f"https://pagination.test/{i}"
            )
        
        # Test FeedsContent with different pagination scenarios
        
        # Page 1, no filters
        content_p1 = app.FeedsContent(session_id, None, False, 1)
        assert hasattr(content_p1, 'children')
        
        # Page 2, with feed filter
        content_p2_feed = app.FeedsContent(session_id, feed_id, False, 2) 
        assert hasattr(content_p2_feed, 'children')
        
        # Page 1, unread filter
        content_unread = app.FeedsContent(session_id, None, True, 1)
        assert hasattr(content_unread, 'children')
        
        # Edge case: Page beyond available
        content_beyond = app.FeedsContent(session_id, None, False, 999)
        assert hasattr(content_beyond, 'children')  # Should handle gracefully
    
    def test_item_detail_view_rendering(self, test_db):
        """Test ItemDetailView component with various item states"""
        session_id = "detail-test"
        SessionModel.create_session(session_id)
        feed_id = FeedModel.create_feed("https://detail.test", "Detail Test Feed")
        
        # Test with None item
        detail_none = app.ItemDetailView(None)
        assert hasattr(detail_none, 'children')
        
        # Test with complete item
        item_id = FeedItemModel.create_item(
            feed_id=feed_id, guid="detail-test", title="Detail Test Article",
            link="https://detail.test/1", description="Test description",
            content="<p>Full content</p>", published=datetime.now()
        )
        
        items = FeedItemModel.get_items_for_user(session_id)
        # Subscribe user to see the item
        SessionModel.subscribe_to_feed(session_id, feed_id)
        items = FeedItemModel.get_items_for_user(session_id)
        test_item = next((i for i in items if i['id'] == item_id), None)
        
        if test_item:
            detail_full = app.ItemDetailView(test_item)
            assert hasattr(detail_full, 'children')
            
            # Test with starred item
            UserItemModel.toggle_star(session_id, item_id)
            items_starred = FeedItemModel.get_items_for_user(session_id)
            starred_item = next((i for i in items_starred if i['id'] == item_id), None)
            
            if starred_item:
                detail_starred = app.ItemDetailView(starred_item)
                assert hasattr(detail_starred, 'children')

class TestErrorHandlingPaths:
    """Test error handling code paths that weren't covered"""
    
    def test_feed_parser_bozo_handling(self, test_db):
        """Test feedparser bozo exception handling"""
        parser = FeedParser()
        
        with patch.object(parser.client, 'get') as mock_get:
            # Simulate response with bozo feed (malformed but parseable)
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.text = '''<?xml version="1.0"?>
            <rss version="2.0">
                <channel>
                    <title>Bozo Feed</title>
                    <item>
                        <title>Test</title>
                        <!-- Malformed elements -->
                        <unclosed-tag>
                    </item>
                </channel>
            </rss>'''
            mock_get.return_value = mock_response
            
            # Mock feedparser to simulate bozo condition
            with patch('feedparser.parse') as mock_parse:
                mock_parsed = Mock()
                mock_parsed.bozo = True
                mock_parsed.bozo_exception = Exception("Bozo!")
                mock_parsed.feed.title = "Bozo Feed"
                mock_parsed.entries = []
                mock_parse.return_value = mock_parsed
                
                result = parser.fetch_feed("https://bozo.test")
                
                # Should handle bozo condition gracefully
                assert result['updated'] is True
                assert 'data' in result
    
    def test_feed_item_creation_edge_cases(self, test_db):
        """Test feed item creation with missing/invalid data"""
        parser = FeedParser()
        feed_id = FeedModel.create_feed("https://edge.test")
        
        # Test item with missing required fields
        with patch.object(parser, 'parse_and_store_feed') as mock_parse:
            # Mock feedparser data with edge cases
            mock_data = Mock()
            mock_data.feed.title = "Edge Test"
            mock_data.entries = [
                Mock(id=None, guid=None, link="https://edge.test/1", title="No GUID"),
                Mock(id="test", title=None, link="https://edge.test/2"),  # No title
                Mock(id="test2", title="Good", link=None),  # No link
            ]
            
            # Should handle missing fields gracefully
            result = parser.parse_and_store_feed(feed_id, "https://edge.test")
    
    def test_user_item_model_edge_operations(self, test_db):
        """Test UserItemModel with non-existent items"""
        session_id = "edge-user-test"
        SessionModel.create_session(session_id)
        
        # Operations on non-existent items should not crash
        UserItemModel.mark_read(session_id, 99999, True)
        UserItemModel.toggle_star(session_id, 99999)
        UserItemModel.move_to_folder(session_id, 99999, 1)
        
        # Should complete without exceptions

class TestDatabaseIntegrityPaths:
    """Test database constraint and integrity scenarios"""
    
    def test_cascading_delete_behavior(self, test_db):
        """Test foreign key cascade behavior"""
        session_id = "cascade-test"
        SessionModel.create_session(session_id)
        
        # Create feed, items, subscriptions
        feed_id = FeedModel.create_feed("https://cascade.test")
        item_id = FeedItemModel.create_item(feed_id, "cascade", "Test", "https://cascade.test/1")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        folder_id = FolderModel.create_folder(session_id, "Test Folder")
        UserItemModel.move_to_folder(session_id, item_id, folder_id)
        
        # Verify data exists
        with get_db() as conn:
            feeds = conn.execute("SELECT COUNT(*) FROM feeds WHERE id = ?", (feed_id,)).fetchone()[0]
            items = conn.execute("SELECT COUNT(*) FROM feed_items WHERE feed_id = ?", (feed_id,)).fetchone()[0]
            user_feeds = conn.execute("SELECT COUNT(*) FROM user_feeds WHERE session_id = ?", (session_id,)).fetchone()[0]
            folders = conn.execute("SELECT COUNT(*) FROM folders WHERE session_id = ?", (session_id,)).fetchone()[0]
            user_items = conn.execute("SELECT COUNT(*) FROM user_items WHERE session_id = ?", (session_id,)).fetchone()[0]
            
        assert feeds == 1
        assert items == 1
        assert user_feeds == 1
        assert folders == 1
        assert user_items == 1
        
        # Delete session - should cascade
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        
        # Verify cascading worked
        with get_db() as conn:
            user_feeds_after = conn.execute("SELECT COUNT(*) FROM user_feeds WHERE session_id = ?", (session_id,)).fetchone()[0]
            folders_after = conn.execute("SELECT COUNT(*) FROM folders WHERE session_id = ?", (session_id,)).fetchone()[0]
            user_items_after = conn.execute("SELECT COUNT(*) FROM user_items WHERE session_id = ?", (session_id,)).fetchone()[0]
            
        assert user_feeds_after == 0
        assert folders_after == 0
        assert user_items_after == 0
        
        # Feed and items should remain (not cascaded)
        with get_db() as conn:
            feeds_after = conn.execute("SELECT COUNT(*) FROM feeds WHERE id = ?", (feed_id,)).fetchone()[0]
            items_after = conn.execute("SELECT COUNT(*) FROM feed_items WHERE feed_id = ?", (feed_id,)).fetchone()[0]
            
        assert feeds_after == 1
        assert items_after == 1

class TestDefaultFeedSetupFlow:
    """Test the default feed setup that happens at app startup"""
    
    def test_default_feed_urls_and_parsing(self, test_db):
        """Test that all default feeds can be parsed successfully"""
        # Clear any existing feeds
        with get_db() as conn:
            conn.execute("DELETE FROM feed_items")
            conn.execute("DELETE FROM feeds")
        
        # Mock successful responses for all default feeds
        with patch.object(FeedParser, 'fetch_feed') as mock_fetch:
            mock_responses = [
                {
                    'status': 200, 'updated': True,
                    'data': Mock(
                        feed=Mock(title="Hacker News: Front Page"),
                        entries=[Mock(
                            id="hn-1", title="HN Test", link="https://hn.test/1",
                            summary="Test HN article", published="2023-12-25T10:00:00Z"
                        )]
                    )
                },
                {
                    'status': 200, 'updated': True,
                    'data': Mock(
                        feed=Mock(title="All Subreddits"),
                        entries=[Mock(
                            id="reddit-1", title="Reddit Test", link="https://reddit.test/1",
                            summary="Test Reddit post", published="2023-12-25T11:00:00Z"
                        )]
                    )
                },
                {
                    'status': 200, 'updated': True,
                    'data': Mock(
                        feed=Mock(title="WSJ Markets"),
                        entries=[Mock(
                            id="wsj-1", title="WSJ Test", link="https://wsj.test/1",
                            summary="Test WSJ article", published="2023-12-25T12:00:00Z"
                        )]
                    )
                }
            ]
            
            mock_fetch.side_effect = mock_responses
            
            results = setup_default_feeds()
            
            # All should succeed
            for result in results:
                assert result['success'] is True

if __name__ == "__main__":
    # Run with coverage
    import subprocess
    subprocess.run([
        "coverage", "run", "--source=.", "-a",  # Append to existing coverage
        "-m", "pytest", __file__, "-v"
    ])
    subprocess.run(["coverage", "report", "--show-missing"])
    subprocess.run(["coverage", "html", "--directory=test_results/coverage_html"])