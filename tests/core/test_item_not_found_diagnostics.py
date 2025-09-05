"""Test item not found diagnostic pages by testing the diagnostic HTML generation directly"""
import pytest
import tempfile
import os
import sqlite3
import json
from unittest.mock import Mock

# Import the functions we need to test
from models import init_db, get_db, FeedModel, SessionModel, FeedItemModel, UserItemModel
from app import prepare_item_data


class TestItemNotFoundDiagnostics:
    """Test diagnostic HTML generation for non-existent items"""
    
    @pytest.fixture
    def temp_db(self):
        """Temporary database for testing"""
        import models
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_db = tmp.name
        
        original_db = models.DB_PATH
        models.DB_PATH = tmp_db
        
        os.makedirs(os.path.dirname(tmp_db), exist_ok=True)
        init_db()
        
        # Set up test data
        with get_db() as conn:
            # Create test session and feed
            conn.execute("INSERT INTO sessions (id) VALUES ('test-session-id')")
            conn.execute("INSERT INTO feeds (id, url, title, description) VALUES (1, 'http://example.com/feed.xml', 'Test Feed', 'Test Description')")
            conn.execute("INSERT INTO user_feeds (session_id, feed_id) VALUES ('test-session-id', 1)")
        
        yield tmp_db
        
        # Cleanup
        models.DB_PATH = original_db
        os.unlink(tmp_db)
    
    def test_item_not_found_diagnostic_generation(self, temp_db):
        """Test that we can generate diagnostic HTML when item is not found"""
        session_id = 'test-session-id'
        item_id = 999999  # Non-existent item
        
        # Test prepare_item_data returns None for non-existent item
        item_data = prepare_item_data(session_id, item_id, None, False)
        assert item_data.item is None
        
        # Test that we can execute the diagnostic query from the route
        diagnostic_result = None
        try:
            with get_db() as conn:
                diagnostic_result = conn.execute("""
                    SELECT fi.*, f.title as feed_title, 
                           COALESCE(ui.is_read, 0) as is_read,
                           COALESCE(ui.starred, 0) as starred,
                           fo.name as folder_name
                    FROM feed_items fi
                    JOIN feeds f ON fi.feed_id = f.id
                    JOIN user_feeds uf ON f.id = uf.feed_id AND uf.session_id = ?
                    LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
                    LEFT JOIN folders fo ON ui.folder_id = fo.id
                    WHERE fi.id = ?
                """, (session_id, session_id, item_id)).fetchone()
        except Exception as e:
            diagnostic_result = f"Query failed: {str(e)}"
        
        # Should get None result for non-existent item
        assert diagnostic_result is None
        
        # Test JSON serialization of None result
        json_result = json.dumps(diagnostic_result, indent=2, default=str)
        assert json_result == "null"
    
    def test_read_toggle_diagnostic_queries(self, temp_db):
        """Test diagnostic queries for read toggle with non-existent item"""
        session_id = 'test-session-id'
        item_id = 999999  # Non-existent item
        
        # Test Step 1 query - check current read status
        step1_result = None
        try:
            with get_db() as conn:
                step1_result = conn.execute("""
                    SELECT COALESCE(ui.is_read, 0) as current_read
                    FROM feed_items fi
                    LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
                    WHERE fi.id = ?
                """, (session_id, item_id)).fetchone()
        except Exception as e:
            step1_result = f"Query failed: {str(e)}"
        
        # Should get None for non-existent item
        assert step1_result is None
        
        # Test final query that would be used by get_item_for_user
        final_result = None
        try:
            with get_db() as conn:
                final_result = conn.execute("""
                    SELECT fi.*, f.title as feed_title, 
                           COALESCE(ui.is_read, 0) as is_read,
                           COALESCE(ui.starred, 0) as starred,
                           fo.name as folder_name
                    FROM feed_items fi
                    JOIN feeds f ON fi.feed_id = f.id
                    JOIN user_feeds uf ON f.id = uf.feed_id AND uf.session_id = ?
                    LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
                    LEFT JOIN folders fo ON ui.folder_id = fo.id
                    WHERE fi.id = ?
                """, (session_id, session_id, item_id)).fetchone()
        except Exception as e:
            final_result = f"Query failed: {str(e)}"
        
        # Should get None for non-existent item
        assert final_result is None
        
        # Test JSON serialization
        step1_json = json.dumps(step1_result, indent=2, default=str)
        final_json = json.dumps(final_result, indent=2, default=str)
        
        assert step1_json == "null"
        assert final_json == "null"
    
    def test_diagnostic_html_structure_components(self, temp_db):
        """Test that diagnostic HTML components can be generated"""
        from fasthtml.common import Div, H2, Details, Summary, Pre
        
        session_id = 'test-session-id'
        item_id = 999999
        
        # Test creating diagnostic HTML structure like in the route
        diagnostic_div = Div(
            H2("Item Not Found - Diagnostic Information", cls='text-red-600 font-bold mb-4'),
            
            Details(
                Summary("SQL Query Details"),
                Pre(f"""Query: get_item_for_user(session_id='{session_id}', item_id={item_id})

Executed SQL:
SELECT fi.*, f.title as feed_title, 
       COALESCE(ui.is_read, 0) as is_read,
       COALESCE(ui.starred, 0) as starred,
       fo.name as folder_name
FROM feed_items fi
JOIN feeds f ON fi.feed_id = f.id
JOIN user_feeds uf ON f.id = uf.feed_id AND uf.session_id = ?
LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
LEFT JOIN folders fo ON ui.folder_id = fo.id
WHERE fi.id = ?

Parameters: ('{session_id}', '{session_id}', {item_id})"""),
                Pre(f"Result: null")
            ),
            
            cls='border border-red-300 bg-red-50 p-4 m-4 rounded'
        )
        
        # Convert to string to verify structure
        html_string = str(diagnostic_div)
        
        # Check that essential diagnostic content is present
        assert 'Item Not Found - Diagnostic Information' in html_string
        assert 'SQL Query Details' in html_string
        assert 'get_item_for_user' in html_string
        # Check for HTML-encoded quotes in the output
        assert f'Parameters: (&#x27;{session_id}&#x27;, &#x27;{session_id}&#x27;, {item_id})' in html_string
        assert 'Result: null' in html_string
        
        # Check CSS classes
        assert 'text-red-600 font-bold mb-4' in html_string
        assert 'border border-red-300 bg-red-50 p-4 m-4 rounded' in html_string
        
        # Check HTML structure
        assert '<h2' in html_string
        assert '<details>' in html_string
        assert '<summary>' in html_string
        assert '<pre>' in html_string
    
    def test_toggle_read_function_behavior(self, temp_db):
        """Test that toggle_read_and_get_item returns None for non-existent items"""
        session_id = 'test-session-id'
        item_id = 999999  # Non-existent item
        
        # This should return None for non-existent item
        result = UserItemModel.toggle_read_and_get_item(session_id, item_id)
        assert result is None
    
    def test_get_item_for_user_behavior(self, temp_db):
        """Test that get_item_for_user returns None for non-existent items"""
        session_id = 'test-session-id'
        item_id = 999999  # Non-existent item
        
        # This should return None for non-existent item
        result = FeedItemModel.get_item_for_user(session_id, item_id)
        assert result is None
    
    def test_diagnostic_queries_with_valid_session_no_item(self, temp_db):
        """Test diagnostic queries work correctly with valid session but no item"""
        session_id = 'test-session-id'
        item_id = 999999  # Non-existent item
        
        # Verify session exists
        with get_db() as conn:
            session_exists = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
            assert session_exists is not None
            
            # Verify user has feeds
            user_feeds = conn.execute("SELECT COUNT(*) FROM user_feeds WHERE session_id = ?", (session_id,)).fetchone()[0]
            assert user_feeds > 0
            
            # But item doesn't exist
            item_exists = conn.execute("SELECT 1 FROM feed_items WHERE id = ?", (item_id,)).fetchone()
            assert item_exists is None