"""Test for All Posts vs Unread view bug - regression test"""

import pytest
import tempfile
import os
from models import init_db, get_db, SessionModel, FeedModel, FeedItemModel, UserItemModel

class TestAllPostsVsUnreadViewBug:
    """Regression test for the All Posts view bug"""
    
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
        
        yield tmp_db
        
        models.DB_PATH = original_db
        if os.path.exists(tmp_db):
            os.unlink(tmp_db)
    
    def test_all_posts_should_show_read_and_unread_items(self, temp_db):
        """CRITICAL: All Posts view should show ALL items, Unread view should filter
        
        Bug: All Posts view was hiding read articles like Unread view.
        """
        session_id = "all-posts-test"
        SessionModel.create_session(session_id)
        
        # Create feed and items
        feed_id = FeedModel.create_feed("https://allposts.test", "All Posts Test Feed")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        # Create 3 items
        item1_id = FeedItemModel.create_item(feed_id, "item1", "Article 1", "https://test.com/1")
        item2_id = FeedItemModel.create_item(feed_id, "item2", "Article 2", "https://test.com/2")  
        item3_id = FeedItemModel.create_item(feed_id, "item3", "Article 3", "https://test.com/3")
        
        # Mark one as read
        UserItemModel.mark_read(session_id, item2_id, True)
        
        # TEST 1: All Posts view (unread_only=False) should show ALL 3 items
        all_items = FeedItemModel.get_items_for_user(session_id, feed_id, unread_only=False)
        assert len(all_items) == 3, f"All Posts should show all 3 items, got {len(all_items)}"
        
        # Verify we have both read and unread items
        read_items = [item for item in all_items if item['is_read'] == 1]
        unread_items = [item for item in all_items if item['is_read'] == 0]
        
        assert len(read_items) == 1, f"Should have 1 read item, got {len(read_items)}"
        assert len(unread_items) == 2, f"Should have 2 unread items, got {len(unread_items)}"
        assert read_items[0]['id'] == item2_id, "Article 2 should be marked as read"
        
        # TEST 2: Unread view (unread_only=True) should show only 2 unread items  
        unread_only_items = FeedItemModel.get_items_for_user(session_id, feed_id, unread_only=True)
        assert len(unread_only_items) == 2, f"Unread view should show 2 items, got {len(unread_only_items)}"
        
        # Should not contain the read item
        unread_item_ids = [item['id'] for item in unread_only_items]
        assert item2_id not in unread_item_ids, "Read item should not appear in unread view"
        assert item1_id in unread_item_ids, "Unread item 1 should appear in unread view"
        assert item3_id in unread_item_ids, "Unread item 3 should appear in unread view"
    
    def test_multiple_read_items_in_all_posts_view(self, temp_db):
        """Test: Multiple read items → All Posts shows all → Unread shows none"""
        session_id = "multi-read-test"
        SessionModel.create_session(session_id)
        
        feed_id = FeedModel.create_feed("https://multiread.test", "Multi Read Test")
        SessionModel.subscribe_to_feed(session_id, feed_id)
        
        # Create 5 items
        item_ids = []
        for i in range(5):
            item_id = FeedItemModel.create_item(feed_id, f"multi-{i}", f"Article {i}", f"https://test.com/{i}")
            item_ids.append(item_id)
        
        # Mark 3 as read, leave 2 unread
        UserItemModel.mark_read(session_id, item_ids[0], True)
        UserItemModel.mark_read(session_id, item_ids[2], True) 
        UserItemModel.mark_read(session_id, item_ids[4], True)
        # item_ids[1] and item_ids[3] remain unread
        
        # All Posts should show all 5
        all_items = FeedItemModel.get_items_for_user(session_id, feed_id, unread_only=False)
        assert len(all_items) == 5, "All Posts should show all 5 items"
        
        # Unread should show only 2
        unread_items = FeedItemModel.get_items_for_user(session_id, feed_id, unread_only=True)
        assert len(unread_items) == 2, "Unread should show only 2 unread items"
        
        unread_ids = [item['id'] for item in unread_items]
        assert item_ids[1] in unread_ids, "Item 1 should be unread"
        assert item_ids[3] in unread_ids, "Item 3 should be unread"
        assert item_ids[0] not in unread_ids, "Item 0 should not appear in unread (is read)"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])