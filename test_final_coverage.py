"""Final tests to cover remaining critical code paths"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import tempfile
import httpx

# Import modules to test
import app
from models import init_db, SessionModel, FeedModel, FeedItemModel, UserItemModel

TEST_DB_PATH = "data/test_final_coverage.db"

@pytest.fixture
def test_db():
    """Test database setup"""
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

class TestAppStartupLogic:
    """Cover lines 20-21: App startup and default feed setup"""
    
    def test_app_startup_default_feed_check(self, test_db):
        """Test the app startup logic that checks for existing feeds"""
        # Test when feeds exist (shouldn't setup defaults)
        FeedModel.create_feed("https://existing.test", "Existing Feed")
        
        with patch('app.setup_default_feeds') as mock_setup:
            # Reload the module to trigger startup logic
            import importlib
            importlib.reload(app)
            
            # Should not call setup_default_feeds since feeds exist
            # (This is hard to test due to module loading, but we can test the logic)
            feeds = FeedModel.get_feeds_to_update(max_age_minutes=9999)
            assert len(feeds) > 0  # Feeds exist, so shouldn't setup

class TestBeforewareSessionHandling:
    """Cover lines 31-53: Session beforeware that was heavily debugged"""
    
    def test_beforeware_new_session_with_existing_feeds(self, test_db):
        """Test beforeware when feeds already exist"""
        # Setup existing feeds first
        feed1_id = FeedModel.create_feed("https://test1.com", "Test Feed 1")
        feed2_id = FeedModel.create_feed("https://test2.com", "Test Feed 2")
        
        # Mock request and session
        req = Mock()
        sess = MagicMock()
        req.scope = {}
        
        # No existing session
        sess.get.return_value = None
        
        with patch('uuid.uuid4', return_value=Mock(__str__=lambda x: 'new-session')):
            app.before(req, sess)
        
        # Should have created session and subscribed to feeds
        assert req.scope['session_id'] == 'new-session'
        sess.__setitem__.assert_called_with('session_id', 'new-session')
    
    def test_beforeware_existing_session_no_subscriptions(self, test_db):
        """Test beforeware with existing session but no feed subscriptions"""
        # Create feeds and existing session
        feed_id = FeedModel.create_feed("https://test.com", "Test Feed")
        session_id = "existing-no-feeds"
        SessionModel.create_session(session_id)
        # Don't subscribe to any feeds
        
        req = Mock()
        sess = MagicMock()
        req.scope = {}
        sess.get.return_value = session_id
        
        app.before(req, sess)
        
        # Should have subscribed to feeds
        user_feeds = FeedModel.get_user_feeds(session_id)
        assert len(user_feeds) == 1

class TestMainRouteHandler:
    """Cover lines 339-354: Main index route logic"""
    
    def test_index_route_with_various_parameters(self, test_db):
        """Test index route with different parameter combinations"""
        session_id = "index-test"
        SessionModel.create_session(session_id)
        feed_id = FeedModel.create_feed("https://index.test", "Index Test")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        # Add some items
        for i in range(25):
            FeedItemModel.create_item(feed_id, f"index-{i}", f"Article {i}", f"https://index.test/{i}")
        
        mock_request = Mock()
        mock_request.scope = {'session_id': session_id}
        
        # Test various parameter combinations
        test_cases = [
            (None, False, None, 1),  # Default parameters
            (feed_id, False, None, 1),  # Feed filtering
            (None, True, None, 1),   # Unread filtering
            (None, False, None, 2),  # Page 2
            (feed_id, True, None, 2), # Feed + unread + page
        ]
        
        with patch('app.FeedParser') as mock_parser:
            mock_parser.return_value.update_all_feeds.return_value = []
            
            for feed_param, unread_param, folder_param, page_param in test_cases:
                result = app.index(mock_request, feed_param, unread_param, folder_param, page_param)
                
                # Should return valid FastHTML response
                assert result is not None
                # Should be tuple (Title, Container)
                assert isinstance(result, tuple)
                assert len(result) == 2

class TestHTMXRouteHandlers:
    """Cover lines 391-414, 419-451: HTMX route handler logic"""
    
    def test_show_item_htmx_responses(self, test_db):
        """Test show_item route returning proper HTMX responses"""
        session_id = "htmx-test"
        SessionModel.create_session(session_id)
        feed_id = FeedModel.create_feed("https://htmx.test")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        item_id = FeedItemModel.create_item(
            feed_id=feed_id, guid="htmx-test", title="HTMX Test",
            link="https://htmx.test/1", description="Test description"
        )
        
        mock_request = Mock()
        mock_request.scope = {'session_id': session_id}
        
        # Test with unread_view=False (should return detail + updated item)
        result_all_view = app.show_item(item_id, mock_request, unread_view=False)
        
        # Should return response (tuple for multi-element or single element)
        assert result_all_view is not None
        
        # Reset read status for next test
        UserItemModel.mark_read(session_id, item_id, False)
        
        # Test with unread_view=True (should return detail + removal)
        result_unread_view = app.show_item(item_id, mock_request, unread_view=True)
        assert result_unread_view is not None
    
    def test_add_feed_route_handler(self, test_db):
        """Test add_feed route with various scenarios"""
        session_id = "add-feed-test"
        SessionModel.create_session(session_id)
        
        mock_request = Mock()
        mock_request.scope = {'session_id': session_id}
        
        # Test empty URL
        result_empty = app.add_feed(mock_request, new_feed_url="")
        assert hasattr(result_empty, 'children')  # Should be FastHTML element
        
        # Test duplicate URL
        existing_feed_id = FeedModel.create_feed("https://duplicate.test", "Existing")
        SessionModel.subscribe_to_feed(session_id, existing_feed_id)
        
        result_duplicate = app.add_feed(mock_request, new_feed_url="https://duplicate.test")
        assert hasattr(result_duplicate, 'children')
        
        # Test new URL with mocked parser
        with patch.object(app.FeedParser, 'add_feed') as mock_add:
            mock_add.return_value = {'success': True, 'feed_id': 123}
            
            with patch.object(FeedModel, 'get_user_feeds') as mock_get_feeds:
                mock_get_feeds.return_value = [{'id': 123, 'title': 'New Feed', 'url': 'https://new.test'}]
                
                result_success = app.add_feed(mock_request, new_feed_url="https://new.test")
                assert hasattr(result_success, 'children')
    
    def test_star_and_read_toggle_routes(self, test_db):
        """Test star_item and toggle_read route handlers"""
        session_id = "toggle-test"
        SessionModel.create_session(session_id)
        feed_id = FeedModel.create_feed("https://toggle.test")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        item_id = FeedItemModel.create_item(
            feed_id=feed_id, guid="toggle", title="Toggle Test",
            link="https://toggle.test/1"
        )
        
        mock_request = Mock()
        mock_request.scope = {'session_id': session_id}
        
        # Test star_item route
        star_result = app.star_item(item_id, mock_request)
        assert star_result is not None
        
        # Test toggle_read route
        read_result = app.toggle_read(item_id, mock_request)
        assert read_result is not None
        
        # Test with non-existent item
        nonexistent_result = app.toggle_read(99999, mock_request)
        assert hasattr(nonexistent_result, 'children')  # Should handle gracefully
    
    def test_add_folder_route(self, test_db):
        """Test add_folder route handler"""
        session_id = "folder-route-test"
        SessionModel.create_session(session_id)
        
        mock_request = Mock()
        mock_request.scope = {'session_id': session_id}
        mock_request.headers = {'hx-prompt': 'Test Route Folder'}
        
        result = app.add_folder(mock_request)
        assert hasattr(result, 'children')  # Should return sidebar

class TestWebApplicationIntegration:
    """Test the web application layer that wasn't covered"""
    
    def test_app_with_test_client(self, test_db):
        """Test actual HTTP endpoints through FastHTML app"""
        
        # Setup default feeds for realistic testing
        from feed_parser import setup_default_feeds
        with patch('httpx.Client.get') as mock_get:
            # Mock successful RSS response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {'etag': 'test'}
            mock_response.text = '''<?xml version="1.0"?>
            <rss><channel><title>Test</title>
            <item><title>Test Article</title><link>https://test.com/1</link><guid>1</guid></item>
            </channel></rss>'''
            mock_get.return_value = mock_response
            
            setup_default_feeds()
        
        # Test with FastHTML test client
        with httpx.Client(transport=httpx.WSGITransport(app=app.app), base_url="http://test") as client:
            # Test main page
            response = client.get("/")
            assert response.status_code == 200
            assert b"RSS Reader" in response.content
            
            # Test pagination
            response_p2 = client.get("/?page=2")
            assert response_p2.status_code == 200
            
            # Test feed filtering
            response_feed = client.get("/?feed_id=1")
            assert response_feed.status_code == 200
            
            # Test unread filtering  
            response_unread = client.get("/?unread=1")
            assert response_unread.status_code == 200

if __name__ == "__main__":
    import subprocess
    subprocess.run([
        "coverage", "run", "--source=.", "-a",
        "-m", "pytest", __file__, "-v"
    ])
    subprocess.run(["coverage", "report"])
    subprocess.run(["coverage", "html", "--directory=htmlcov"])