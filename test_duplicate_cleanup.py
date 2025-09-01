#!/usr/bin/env python3
"""Test script for duplicate feed detection and cleanup functionality"""

import os
import sys
import sqlite3
from datetime import datetime
import tempfile

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up test database path
test_db = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_PATH'] = test_db

from models import FeedModel, SessionModel, init_db, get_db

def test_duplicate_cleanup():
    """Test the duplicate feed cleanup functionality"""
    print(f"Using test database: {test_db}")
    
    # Initialize test database
    init_db()
    
    # Create some duplicate feeds manually
    with get_db() as conn:
        # Add the same URL multiple times with different timestamps
        conn.execute("""
            INSERT INTO feeds (url, title, last_updated)
            VALUES ('https://example.com/rss', 'Feed 1', '2023-01-01 00:00:00')
        """)
        
        conn.execute("""
            INSERT INTO feeds (url, title, last_updated) 
            VALUES ('https://example.com/rss', 'Feed 2', '2023-01-02 00:00:00')
        """)
        
        conn.execute("""
            INSERT INTO feeds (url, title, last_updated)
            VALUES ('https://example.com/rss', 'Feed 3', '2023-01-03 00:00:00')
        """)
        
        # Add another set of duplicates
        conn.execute("""
            INSERT INTO feeds (url, title, last_updated)
            VALUES ('https://other.com/feed', 'Other 1', '2023-02-01 00:00:00')
        """)
        
        conn.execute("""
            INSERT INTO feeds (url, title, last_updated)
            VALUES ('https://other.com/feed', 'Other 2', '2023-02-02 00:00:00')
        """)
        
        # Add a unique feed (no duplicates)
        conn.execute("""
            INSERT INTO feeds (url, title, last_updated)
            VALUES ('https://unique.com/rss', 'Unique Feed', '2023-03-01 00:00:00')
        """)
        
        # Create test sessions
        conn.execute("INSERT INTO sessions (id) VALUES ('session1')")
        conn.execute("INSERT INTO sessions (id) VALUES ('session2')")
        
        # Create user subscriptions to the duplicate feeds
        conn.execute("INSERT INTO user_feeds (session_id, feed_id) VALUES ('session1', 1)")
        conn.execute("INSERT INTO user_feeds (session_id, feed_id) VALUES ('session1', 2)")
        conn.execute("INSERT INTO user_feeds (session_id, feed_id) VALUES ('session2', 3)")
        conn.execute("INSERT INTO user_feeds (session_id, feed_id) VALUES ('session2', 4)")
        
        # Check initial state
        print("\n=== BEFORE CLEANUP ===")
        feeds = conn.execute("SELECT id, url, title, last_updated FROM feeds ORDER BY id").fetchall()
        print("Feeds:")
        for feed in feeds:
            print(f"  ID: {feed[0]}, URL: {feed[1]}, Title: {feed[2]}, Updated: {feed[3]}")
        
        subscriptions = conn.execute("""
            SELECT uf.session_id, uf.feed_id, f.title, f.url
            FROM user_feeds uf 
            JOIN feeds f ON uf.feed_id = f.id 
            ORDER BY uf.session_id, uf.feed_id
        """).fetchall()
        print("User subscriptions:")
        for sub in subscriptions:
            print(f"  Session: {sub[0]}, Feed ID: {sub[1]}, Title: {sub[2]}, URL: {sub[3]}")
    
    # Test cleanup_duplicate_feeds
    print("\n=== RUNNING CLEANUP ===")
    result = FeedModel.cleanup_duplicate_feeds()
    print(f"Cleanup result: {result}")
    
    # Check state after cleanup
    with get_db() as conn:
        print("\n=== AFTER CLEANUP ===")
        feeds = conn.execute("SELECT id, url, title, last_updated FROM feeds ORDER BY id").fetchall()
        print("Feeds:")
        for feed in feeds:
            print(f"  ID: {feed[0]}, URL: {feed[1]}, Title: {feed[2]}, Updated: {feed[3]}")
        
        subscriptions = conn.execute("""
            SELECT uf.session_id, uf.feed_id, f.title, f.url
            FROM user_feeds uf 
            JOIN feeds f ON uf.feed_id = f.id 
            ORDER BY uf.session_id, uf.feed_id
        """).fetchall()
        print("User subscriptions:")
        for sub in subscriptions:
            print(f"  Session: {sub[0]}, Feed ID: {sub[1]}, Title: {sub[2]}, URL: {sub[3]}")
    
    # Verify results
    assert result['duplicate_urls_found'] == 2, f"Expected 2 duplicate URLs, got {result['duplicate_urls_found']}"
    assert result['feeds_removed'] == 3, f"Expected 3 feeds removed, got {result['feeds_removed']}"
    assert result['subscriptions_migrated'] == 4, f"Expected 4 subscriptions migrated, got {result['subscriptions_migrated']}"
    
    # Verify final state
    with get_db() as conn:
        remaining_feeds = conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
        assert remaining_feeds == 3, f"Expected 3 remaining feeds, got {remaining_feeds}"
        
        # Check that the most recent feeds were kept
        example_feed = conn.execute("""
            SELECT title, last_updated FROM feeds WHERE url = 'https://example.com/rss'
        """).fetchone()
        assert example_feed[0] == 'Feed 3', f"Expected 'Feed 3' to be kept, got '{example_feed[0]}'"
        
        other_feed = conn.execute("""
            SELECT title, last_updated FROM feeds WHERE url = 'https://other.com/feed'
        """).fetchone()
        assert other_feed[0] == 'Other 2', f"Expected 'Other 2' to be kept, got '{other_feed[0]}'"
        
        # Check that all user subscriptions are preserved
        total_subs = conn.execute("SELECT COUNT(*) FROM user_feeds").fetchone()[0]
        assert total_subs == 4, f"Expected 4 user subscriptions, got {total_subs}"
    
    print("\n✅ All tests passed!")
    return True

def test_feed_exists():
    """Test the feed_exists_by_url functionality"""
    print("\n=== TESTING FEED EXISTS ===")
    
    # Should return False for non-existent feed
    exists = FeedModel.feed_exists_by_url('https://nonexistent.com/rss')
    assert not exists, "Should return False for non-existent feed"
    
    # Should return True for existing feed
    exists = FeedModel.feed_exists_by_url('https://unique.com/rss')
    assert exists, "Should return True for existing feed"
    
    print("✅ Feed exists tests passed!")
    return True

if __name__ == "__main__":
    try:
        test_duplicate_cleanup()
        test_feed_exists()
        print("\n🎉 All tests completed successfully!")
        
        # Clean up test database
        os.unlink(test_db)
        print(f"Test database {test_db} cleaned up")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)