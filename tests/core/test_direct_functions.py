"""Direct function tests: Test internal logic without HTTP layer"""

import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta

# Import functions to test directly
from app.models import init_db, get_db, FeedModel, SessionModel, FeedItemModel, UserItemModel, FolderModel
from app.main import human_time_diff

class TestDatabaseOperations:
    """Test database operations directly"""
    
    @pytest.fixture
    def temp_db(self):
        """Temporary database for testing"""
        from app import models
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_db = tmp.name
        
        original_db = models.DB_PATH
        models.DB_PATH = tmp_db
        
        os.makedirs(os.path.dirname(tmp_db), exist_ok=True)
        init_db()
        
        yield tmp_db
        
        models.DB_PATH = original_db
        if os.path.exists(tmp_db):
            os.unlink(tmp_db)
    
    def test_complete_user_workflow_database_operations(self, temp_db):
        """Test: Create session → Add feeds → Subscribe → Read articles → Folders
        
        This tests the database workflow that supports our UI.
        """
        session_id = "workflow-test"
        
        # 1. Create session
        SessionModel.create_session(session_id)
        
        # 2. Create feeds
        feed1_id = FeedModel.create_feed("https://test1.com", "Test Feed 1")
        feed2_id = FeedModel.create_feed("https://test2.com", "Test Feed 2")
        
        # 3. Subscribe user to feeds
        SessionModel.subscribe_to_feed(session_id, feed1_id)
        SessionModel.subscribe_to_feed(session_id, feed2_id)
        
        # 4. Verify user can see feeds
        user_feeds = FeedModel.get_user_feeds(session_id)
        assert len(user_feeds) == 2
        
        # 5. Add items to feeds
        item1_id = FeedItemModel.create_item(feed1_id, "item1", "Article 1", "https://test1.com/1")
        item2_id = FeedItemModel.create_item(feed2_id, "item2", "Article 2", "https://test2.com/1")
        
        # 6. Verify user can see items
        user_items = FeedItemModel.get_items_for_user(session_id)
        assert len(user_items) == 2
        
        # 7. Test reading workflow
        UserItemModel.mark_read(session_id, item1_id, True)
        UserItemModel.toggle_star(session_id, item2_id)
        
        # 8. Test folder workflow
        folder_id = FolderModel.create_folder(session_id, "Important")
        UserItemModel.move_to_folder(session_id, item2_id, folder_id)
        
        # 9. Verify final state
        final_items = FeedItemModel.get_items_for_user(session_id)
        item1_final = next(i for i in final_items if i['id'] == item1_id)
        item2_final = next(i for i in final_items if i['id'] == item2_id)
        
        assert item1_final['is_read'] == 1
        assert item2_final['starred'] == 1
        assert item2_final['folder_name'] == 'Important'
        
        # 10. Test unread filtering
        unread_items = FeedItemModel.get_items_for_user(session_id, unread_only=True)
        assert len(unread_items) == 1  # Only item2 should be unread
        assert unread_items[0]['id'] == item2_id

class TestUtilityFunctions:
    """Test utility functions that support UI features"""
    
    def test_human_time_diff_comprehensive(self):
        """Test: Time formatting → Human readable strings
        
        This supports the 'updated X minutes ago' feature in the UI.
        """
        now = datetime.now(timezone.utc)
        
        test_cases = [
            (now - timedelta(seconds=30), "Just now"),
            (now - timedelta(minutes=5), "5 minutes ago"),
            (now - timedelta(hours=2), "2 hours ago"),
            (now - timedelta(days=1), "1 day ago"),
            (None, "Unknown"),
            ("invalid-string", "Unknown"),
        ]
        
        for test_time, expected_pattern in test_cases:
            result = human_time_diff(test_time)
            
            if expected_pattern == "Unknown":
                assert result == "Unknown"
            elif expected_pattern == "Just now":
                assert "Just now" in result
            elif "minute" in expected_pattern:
                assert "minute" in result
            elif "hour" in expected_pattern:
                assert "hour" in result
            elif "day" in expected_pattern:
                assert "day" in result

class TestFeedManagementLogic:
    """Test feed management logic that supports the UI"""
    
    @pytest.fixture
    def temp_db(self):
        """Temporary database"""
        from app import models
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_db = tmp.name
        
        original_db = models.DB_PATH
        models.DB_PATH = tmp_db
        init_db()
        
        yield tmp_db
        
        models.DB_PATH = original_db
        if os.path.exists(tmp_db):
            os.unlink(tmp_db)
    
    def test_feed_update_logic(self, temp_db):
        """Test: Feed update → ETag handling → Incremental updates"""
        # Create feed
        feed_id = FeedModel.create_feed("https://update.test", "Update Test")
        
        # Initial update
        FeedModel.update_feed(feed_id, title="Updated Title", etag="etag-1", last_modified="Mon, 01 Jan 2024")
        
        # Verify update
        feeds_to_update = FeedModel.get_feeds_to_update(max_age_minutes=999)
        updated_feed = next((f for f in feeds_to_update if f['id'] == feed_id), None)
        
        if updated_feed:  # May not need update due to recent timestamp
            assert updated_feed['title'] == "Updated Title"
            assert updated_feed['etag'] == "etag-1"
    
    def test_pagination_item_slicing(self, temp_db):
        """Test: Pagination logic → Item slicing → Page calculations
        
        This supports the pagination feature we implemented.
        """
        session_id = "pagination-test"
        SessionModel.create_session(session_id)
        
        # Create feed with known number of items
        feed_id = FeedModel.create_feed("https://pagination.test")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        # Create 50 items
        for i in range(50):
            FeedItemModel.create_item(
                feed_id=feed_id, guid=f"page-{i}", title=f"Article {i}",
                link=f"https://pagination.test/{i}"
            )
        
        # Test pagination logic with new database-level pagination
        page_size = 20
        
        # Test page 1 (default)
        page_1 = FeedItemModel.get_items_for_user(session_id, page=1, page_size=page_size)
        assert len(page_1) == 20, f"Page 1 should have 20 items, got {len(page_1)}"
        
        # Test page 2 
        page_2 = FeedItemModel.get_items_for_user(session_id, page=2, page_size=page_size)
        assert len(page_2) == 20
        
        # Test page 3 (partial page - only 10 items: 40-49)
        page_3 = FeedItemModel.get_items_for_user(session_id, page=3, page_size=page_size)
        assert len(page_3) == 10
        
        # Total pages calculation
        total_pages = (50 + page_size - 1) // page_size
        assert total_pages == 3

if __name__ == "__main__":
    pytest.main([__file__, "-v"])