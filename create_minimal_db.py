#!/usr/bin/env python3
"""Create minimal seed database for MINIMAL_MODE testing

This script creates a lightweight seed database with just 2 feeds (Hacker News + Claude AI)
and their recent articles. This allows tests to start instantly without network calls.
"""

import os
import sys
import sqlite3
import shutil
from datetime import datetime, timedelta
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_minimal_seed():
    """Create minimal seed database from current database"""
    
    source_db = "data/rss.db"
    target_db = "data/minimal_seed.db"
    
    # Check if source exists
    if not os.path.exists(source_db):
        print(f"❌ Source database {source_db} not found. Run the app first to populate it.")
        sys.exit(1)
    
    # Backup existing seed if present
    if os.path.exists(target_db):
        backup = f"{target_db}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(target_db, backup)
        print(f"📦 Backed up existing seed to {backup}")
    
    # Copy source to target
    shutil.copy2(source_db, target_db)
    print(f"📋 Copied {source_db} to {target_db}")
    
    # Now trim down to minimal set
    conn = sqlite3.connect(target_db)
    cursor = conn.cursor()
    
    try:
        # Keep only 2 feeds: Hacker News and Claude AI Reddit
        cursor.execute("""
            DELETE FROM feeds 
            WHERE url NOT IN (
                'https://hnrss.org/frontpage',
                'https://www.reddit.com/r/ClaudeAI/.rss'
            )
        """)
        
        # Get the feed IDs
        cursor.execute("SELECT id FROM feeds WHERE url = 'https://hnrss.org/frontpage'")
        hn_result = cursor.fetchone()
        hn_id = hn_result[0] if hn_result else None
        
        cursor.execute("SELECT id FROM feeds WHERE url = 'https://www.reddit.com/r/ClaudeAI/.rss'")
        claude_result = cursor.fetchone()
        claude_id = claude_result[0] if claude_result else None
        
        # Keep exactly 26 most recent articles from each feed
        if hn_id:
            cursor.execute("""
                DELETE FROM feed_items 
                WHERE feed_id = ? AND id NOT IN (
                    SELECT id FROM feed_items 
                    WHERE feed_id = ? 
                    ORDER BY published DESC 
                    LIMIT 26
                )
            """, (hn_id, hn_id))
        
        if claude_id:
            cursor.execute("""
                DELETE FROM feed_items 
                WHERE feed_id = ? AND id NOT IN (
                    SELECT id FROM feed_items 
                    WHERE feed_id = ? 
                    ORDER BY published DESC 
                    LIMIT 26
                )
            """, (claude_id, claude_id))
        
        # Delete orphaned items
        cursor.execute("""
            DELETE FROM feed_items 
            WHERE feed_id NOT IN (SELECT id FROM feeds)
        """)
        
        # Get final counts
        cursor.execute("SELECT COUNT(*) FROM feeds")
        feed_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM feed_items")
        item_count = cursor.fetchone()[0]
        
        # Show breakdown per feed
        cursor.execute("""
            SELECT f.title, f.url, COUNT(fi.id) as article_count
            FROM feeds f
            LEFT JOIN feed_items fi ON f.id = fi.feed_id
            GROUP BY f.id
        """)
        feed_stats = cursor.fetchall()
        
        # Clear all user-specific data (tests will create their own sessions)
        cursor.execute("DELETE FROM sessions")
        cursor.execute("DELETE FROM user_feeds")
        cursor.execute("DELETE FROM user_items")
        cursor.execute("DELETE FROM folders")
        
        conn.commit()
        
        # Vacuum to reduce file size (must be done outside transaction)
        conn.execute("VACUUM")
        
        # Get file size
        size_bytes = os.path.getsize(target_db)
        size_mb = size_bytes / (1024 * 1024)
        
        print(f"\n✅ Minimal seed database created successfully!")
        print(f"📊 Stats:")
        print(f"   - Total feeds: {feed_count}")
        print(f"   - Total articles: {item_count}")
        print(f"   - Size: {size_mb:.2f} MB")
        
        print(f"\n📰 Feed breakdown:")
        for title, url, count in feed_stats:
            print(f"   - {title or url}: {count} articles")
        print(f"\n🚀 Use MINIMAL_MODE=true to start with this seed database")
        
    except Exception as e:
        print(f"❌ Error creating minimal seed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    create_minimal_seed()