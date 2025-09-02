#!/usr/bin/env python3
"""Create minimal seed database with real data from existing database"""

import os
import sqlite3
import shutil
from models import DB_PATH, init_db

MINIMAL_SEED_PATH = "data/minimal_seed.db"

def create_minimal_seed_database():
    """Create a minimal seed database by copying real data from the main database"""
    
    # Check if main database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Main database not found at {DB_PATH}")
        print("Please run the application normally first to create data")
        return False
    
    print(f"📊 Creating minimal seed database from {DB_PATH}...")
    
    # Create minimal seed database
    os.makedirs(os.path.dirname(MINIMAL_SEED_PATH), exist_ok=True)
    
    # Remove existing seed if it exists
    if os.path.exists(MINIMAL_SEED_PATH):
        os.remove(MINIMAL_SEED_PATH)
    
    # Initialize empty minimal database with schema
    with sqlite3.connect(MINIMAL_SEED_PATH) as minimal_conn:
        minimal_conn.row_factory = sqlite3.Row
        
        # Copy schema from main database
        with sqlite3.connect(DB_PATH) as main_conn:
            main_conn.row_factory = sqlite3.Row
            
            # Get schema
            schema_query = "SELECT sql FROM sqlite_master WHERE type='table' OR type='index'"
            schema_statements = [row[0] for row in main_conn.execute(schema_query).fetchall() if row[0]]
            
            # Create tables and indexes
            for statement in schema_statements:
                if statement:  # Skip None statements
                    minimal_conn.execute(statement)
    
    # Copy specific feeds and their data
    target_feeds = [
        "https://hnrss.org/frontpage",  # Hacker News
        "https://www.reddit.com/r/ClaudeAI/.rss"  # ClaudeAI subreddit
    ]
    
    with sqlite3.connect(DB_PATH) as main_conn, sqlite3.connect(MINIMAL_SEED_PATH) as minimal_conn:
        main_conn.row_factory = sqlite3.Row
        minimal_conn.row_factory = sqlite3.Row
        
        feeds_copied = 0
        articles_copied = 0
        
        for feed_url in target_feeds:
            # Find feed in main database
            feed_row = main_conn.execute(
                "SELECT * FROM feeds WHERE url = ?", (feed_url,)
            ).fetchone()
            
            if not feed_row:
                print(f"⚠️  Feed not found in main database: {feed_url}")
                continue
            
            # Copy feed record
            minimal_conn.execute("""
                INSERT INTO feeds (id, url, title, description, last_updated, etag, last_modified, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, tuple(feed_row))
            feeds_copied += 1
            
            feed_id = feed_row['id']
            print(f"✅ Copied feed: {feed_row['title']}")
            
            # Copy recent articles for this feed (limit to 10 most recent)
            articles = main_conn.execute("""
                SELECT * FROM feed_items 
                WHERE feed_id = ? 
                ORDER BY published DESC, created_at DESC 
                LIMIT 10
            """, (feed_id,)).fetchall()
            
            for article in articles:
                minimal_conn.execute("""
                    INSERT INTO feed_items (id, feed_id, guid, title, link, description, content, published, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, tuple(article))
                articles_copied += 1
        
        # Create a test session with subscriptions
        test_session_id = "test-session-minimal"
        minimal_conn.execute("""
            INSERT OR REPLACE INTO sessions (id, created_at, last_accessed) 
            VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (test_session_id,))
        
        # Subscribe test session to both feeds
        for feed_url in target_feeds:
            feed_row = minimal_conn.execute(
                "SELECT id FROM feeds WHERE url = ?", (feed_url,)
            ).fetchone()
            if feed_row:
                minimal_conn.execute("""
                    INSERT OR IGNORE INTO user_feeds (session_id, feed_id) 
                    VALUES (?, ?)
                """, (test_session_id, feed_row['id']))
        
        # Add some sample user_items (mix of read/unread)
        items = minimal_conn.execute("SELECT id FROM feed_items LIMIT 8").fetchall()
        for i, item in enumerate(items):
            is_read = i % 3 == 0  # Every 3rd item is read
            starred = i % 5 == 0   # Every 5th item is starred
            
            minimal_conn.execute("""
                INSERT OR IGNORE INTO user_items (session_id, item_id, is_read, starred)
                VALUES (?, ?, ?, ?)
            """, (test_session_id, item['id'], is_read, starred))
    
    print(f"🎉 Minimal seed database created!")
    print(f"📈 Stats: {feeds_copied} feeds, {articles_copied} articles")
    print(f"💾 Saved to: {MINIMAL_SEED_PATH}")
    
    return True

def copy_fresh_minimal_database():
    """Copy fresh minimal database from seed for development restart"""
    minimal_db_path = "data/minimal.db"
    
    if not os.path.exists(MINIMAL_SEED_PATH):
        print(f"❌ Seed database not found at {MINIMAL_SEED_PATH}")
        print("Run: python create_minimal_db.py to create it first")
        return False
    
    # Copy seed to active minimal database
    shutil.copy2(MINIMAL_SEED_PATH, minimal_db_path)
    print(f"✅ Copied fresh minimal database to {minimal_db_path}")
    
    return True

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--copy":
        # Just copy existing seed to minimal.db
        success = copy_fresh_minimal_database()
    else:
        # Create new seed database from main database
        success = create_minimal_seed_database()
    
    if not success:
        sys.exit(1)