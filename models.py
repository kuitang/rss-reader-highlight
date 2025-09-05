"""Database models and operations for RSS Reader"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict
from contextlib import contextmanager

# Database path selection based on mode
MINIMAL_MODE = os.environ.get("MINIMAL_MODE", "false").lower() == "true"

# Use DATABASE_PATH from environment if set, otherwise fall back to default
if MINIMAL_MODE:
    # MINIMAL MODE: Process-specific database copied from seed (no network calls)
    import os
    pid = os.getpid()
    DB_PATH = f"data/minimal.{pid}.db"
    print(f"🚨 WARNING: MINIMAL_MODE ignores DATABASE_PATH environment variable!")
    print(f"🚨 WARNING: Using process-specific database with pre-populated articles: {DB_PATH}")
else:
    DB_PATH = os.environ.get("DATABASE_PATH", "data/rss.db")

def init_db():
    """Initialize database with required tables"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # In minimal mode, copy fresh seed database with pre-populated articles (no network calls)
    if MINIMAL_MODE:
        seed_path = "data/minimal_seed.db"
        if os.path.exists(seed_path):
            # Always overwrite for fresh state (minimal mode should be predictable)
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
            import shutil
            shutil.copy2(seed_path, DB_PATH)
            # Ensure copied database is writable (seed may be write-protected)
            os.chmod(DB_PATH, 0o644)
            print(f"✅ Copied minimal database with articles from {seed_path} to {DB_PATH}")
            return
        else:
            raise FileNotFoundError(f"Minimal seed database not found at {seed_path} - create it by copying articles from normal database")
    
    # Normal database initialization
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        -- Global feeds table
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            description TEXT,
            last_updated TIMESTAMP,
            etag TEXT,
            last_modified TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- RSS/Atom feed items
        CREATE TABLE IF NOT EXISTS feed_items (
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
        
        -- Browser sessions
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- User's subscribed feeds (session-specific)
        CREATE TABLE IF NOT EXISTS user_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            feed_id INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE,
            FOREIGN KEY (feed_id) REFERENCES feeds (id) ON DELETE CASCADE,
            UNIQUE (session_id, feed_id)
        );
        
        -- User folders
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
        );
        
        -- User item status (read/unread, starred, folder assignments)
        CREATE TABLE IF NOT EXISTS user_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            is_read BOOLEAN DEFAULT FALSE,
            starred BOOLEAN DEFAULT FALSE,
            folder_id INTEGER,
            marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE,
            FOREIGN KEY (item_id) REFERENCES feed_items (id) ON DELETE CASCADE,
            FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE SET NULL,
            UNIQUE (session_id, item_id)
        );
        
        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_feed_items_feed_id ON feed_items(feed_id);
        CREATE INDEX IF NOT EXISTS idx_feed_items_published ON feed_items(published DESC);
        CREATE INDEX IF NOT EXISTS idx_user_feeds_session ON user_feeds(session_id);
        CREATE INDEX IF NOT EXISTS idx_user_items_session ON user_items(session_id);
        CREATE INDEX IF NOT EXISTS idx_user_items_read ON user_items(is_read);
        CREATE INDEX IF NOT EXISTS idx_feeds_last_updated ON feeds(last_updated);
        """)

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()  # Commit all changes
    except Exception as e:
        conn.rollback()  # Rollback on error
        raise
    finally:
        conn.close()

class FeedModel:
    @staticmethod
    def create_feed(url: str, title: str = None, description: str = None) -> int:
        """Create or get existing feed"""
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO feeds (url, title, description) VALUES (?, ?, ?)",
                (url, title, description)
            )
            if cursor.rowcount > 0:
                return cursor.lastrowid
            else:
                return conn.execute("SELECT id FROM feeds WHERE url = ?", (url,)).fetchone()[0]
    
    @staticmethod
    def update_feed(feed_id: int, title: str = None, description: str = None, 
                   etag: str = None, last_modified: str = None):
        """Update feed metadata"""
        with get_db() as conn:
            conn.execute("""
                UPDATE feeds 
                SET title = COALESCE(?, title),
                    description = COALESCE(?, description),
                    etag = ?, 
                    last_modified = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (title, description, etag, last_modified, feed_id))
    
    @staticmethod
    def get_feeds_to_update(max_age_minutes: int = 1) -> List[Dict]:
        """Get feeds that need updating"""
        with get_db() as conn:
            return [dict(row) for row in conn.execute("""
                SELECT * FROM feeds 
                WHERE last_updated IS NULL 
                   OR datetime(last_updated) < datetime('now', '-{} minutes')
            """.format(max_age_minutes)).fetchall()]
    
    @staticmethod
    def get_user_feeds(session_id: str) -> List[Dict]:
        """Get feeds for a specific session"""
        with get_db() as conn:
            return [dict(row) for row in conn.execute("""
                SELECT f.*, uf.added_at as subscribed_at
                FROM feeds f
                JOIN user_feeds uf ON f.id = uf.feed_id
                WHERE uf.session_id = ?
                ORDER BY f.title
            """, (session_id,)).fetchall()]
    
    @staticmethod
    def get_feed_name_for_user(session_id: str, feed_id: int) -> Optional[str]:
        """Get single feed name for user - optimized single-row query"""
        with get_db() as conn:
            result = conn.execute("""
                SELECT f.title
                FROM feeds f
                JOIN user_feeds uf ON f.id = uf.feed_id
                WHERE uf.session_id = ? AND f.id = ?
            """, (session_id, feed_id)).fetchone()
            return result[0] if result else None
    
    @staticmethod
    def user_has_feed_url(session_id: str, url: str) -> Optional[Dict]:
        """Check if user is subscribed to feed with URL - optimized single-row query"""
        with get_db() as conn:
            result = conn.execute("""
                SELECT f.*, uf.added_at as subscribed_at
                FROM feeds f
                JOIN user_feeds uf ON f.id = uf.feed_id
                WHERE uf.session_id = ? AND f.url = ?
            """, (session_id, url)).fetchone()
            return dict(result) if result else None
    
    @staticmethod
    def feed_exists_by_url(url: str) -> bool:
        """Check if a feed with the given URL already exists"""
        with get_db() as conn:
            result = conn.execute("SELECT 1 FROM feeds WHERE url = ? LIMIT 1", (url,)).fetchone()
            return result is not None
    
    @staticmethod
    def cleanup_duplicate_feeds() -> Dict[str, int]:
        """Clean up duplicate feeds by URL, keeping the one with most recent update"""
        with get_db() as conn:
            # Find all URLs that have duplicates
            duplicate_urls = conn.execute("""
                SELECT url, COUNT(*) as count
                FROM feeds 
                GROUP BY url 
                HAVING count > 1
            """).fetchall()
            
            feeds_removed = 0
            subscriptions_migrated = 0
            
            for url_row in duplicate_urls:
                url = url_row[0]
                
                # Get all feeds for this URL, ordered by last_updated (most recent first, NULLs last)
                duplicate_feeds = conn.execute("""
                    SELECT id, url, title, last_updated
                    FROM feeds 
                    WHERE url = ?
                    ORDER BY 
                        CASE WHEN last_updated IS NULL THEN 1 ELSE 0 END,
                        last_updated DESC
                """, (url,)).fetchall()
                
                if len(duplicate_feeds) <= 1:
                    continue
                    
                # Keep the first one (most recent), remove the rest
                keep_feed_id = duplicate_feeds[0][0]
                remove_feed_ids = [feed[0] for feed in duplicate_feeds[1:]]
                
                # Migrate user subscriptions from feeds being removed to the kept feed
                for remove_id in remove_feed_ids:
                    # Get all user subscriptions to the feed being removed
                    subscriptions = conn.execute("""
                        SELECT session_id FROM user_feeds WHERE feed_id = ?
                    """, (remove_id,)).fetchall()
                    
                    for sub in subscriptions:
                        session_id = sub[0]
                        # Move subscription to kept feed (ignore if already exists)
                        conn.execute("""
                            INSERT OR IGNORE INTO user_feeds (session_id, feed_id) 
                            VALUES (?, ?)
                        """, (session_id, keep_feed_id))
                        subscriptions_migrated += 1
                    
                    # Remove the old user subscriptions
                    conn.execute("DELETE FROM user_feeds WHERE feed_id = ?", (remove_id,))
                    
                    # Remove the duplicate feed (CASCADE will handle feed_items)
                    conn.execute("DELETE FROM feeds WHERE id = ?", (remove_id,))
                    feeds_removed += 1
            
            return {
                'duplicate_urls_found': len(duplicate_urls),
                'feeds_removed': feeds_removed,
                'subscriptions_migrated': subscriptions_migrated
            }

class FeedItemModel:
    @staticmethod
    def create_item(feed_id: int, guid: str, title: str, link: str, 
                   description: str = None, content: str = None, 
                   published: datetime = None) -> int:
        """Create feed item"""
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO feed_items 
                (feed_id, guid, title, link, description, content, published)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (feed_id, guid, title, link, description, content, published))
            return cursor.lastrowid
    
    @staticmethod
    def get_items_for_user(session_id: str, feed_id: int = None, unread_only: bool = False, page: int = 1, page_size: int = 20) -> List[Dict]:
        """Get feed items for user with read status - optimized with configurable limit"""
        query = """
            SELECT fi.*, f.title as feed_title, 
                   COALESCE(ui.is_read, 0) as is_read,
                   COALESCE(ui.starred, 0) as starred,
                   fo.name as folder_name
            FROM feed_items fi
            JOIN feeds f ON fi.feed_id = f.id
            JOIN user_feeds uf ON f.id = uf.feed_id AND uf.session_id = ?
            LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
            LEFT JOIN folders fo ON ui.folder_id = fo.id
        """
        
        params = [session_id, session_id]
        
        if feed_id:
            query += " WHERE fi.feed_id = ?"
            params.append(feed_id)
        
        if unread_only:
            query += " AND " if feed_id else " WHERE "
            query += "COALESCE(ui.is_read, 0) = 0"
        
        offset = (page - 1) * page_size
        query += f" ORDER BY fi.published DESC LIMIT {page_size} OFFSET {offset}"
        
        with get_db() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]
    
    @staticmethod
    def get_item_for_user(session_id: str, item_id: int) -> Dict:
        """Get single feed item for user with read status - optimized single-row query"""
        with get_db() as conn:
            result = conn.execute("""
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
            
            return dict(result) if result else None

class SessionModel:
    @staticmethod
    def create_session(session_id: str):
        """Create or update session"""
        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions (id, last_accessed) 
                VALUES (?, CURRENT_TIMESTAMP)
            """, (session_id,))
    
    @staticmethod
    def subscribe_to_feed(session_id: str, feed_id: int):
        """Subscribe user to feed"""
        with get_db() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO user_feeds (session_id, feed_id) 
                VALUES (?, ?)
            """, (session_id, feed_id))
    
    @staticmethod
    def unsubscribe_from_feed(session_id: str, feed_id: int):
        """Unsubscribe user from feed"""
        with get_db() as conn:
            conn.execute("""
                DELETE FROM user_feeds 
                WHERE session_id = ? AND feed_id = ?
            """, (session_id, feed_id))

class UserItemModel:
    @staticmethod
    def mark_read(session_id: str, item_id: int, is_read: bool = True):
        """Mark item as read/unread"""
        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_items (session_id, item_id, is_read, starred, folder_id)
                VALUES (?, ?, ?, 
                    COALESCE((SELECT starred FROM user_items WHERE session_id = ? AND item_id = ?), 0),
                    (SELECT folder_id FROM user_items WHERE session_id = ? AND item_id = ?)
                )
            """, (session_id, item_id, is_read, session_id, item_id, session_id, item_id))
    
    @staticmethod
    def toggle_star(session_id: str, item_id: int):
        """Toggle star status for item"""
        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_items (session_id, item_id, starred, is_read, folder_id)
                VALUES (?, ?, 
                    NOT COALESCE((SELECT starred FROM user_items WHERE session_id = ? AND item_id = ?), 0),
                    COALESCE((SELECT is_read FROM user_items WHERE session_id = ? AND item_id = ?), 0),
                    (SELECT folder_id FROM user_items WHERE session_id = ? AND item_id = ?)
                )
            """, (session_id, item_id, session_id, item_id, session_id, item_id, session_id, item_id))
    
    @staticmethod
    def toggle_star_and_get_item(session_id: str, item_id: int) -> Optional[Dict]:
        """Toggle star status and return updated item - optimized single transaction"""
        with get_db() as conn:
            # Toggle star
            conn.execute("""
                INSERT OR REPLACE INTO user_items (session_id, item_id, starred, is_read, folder_id)
                VALUES (?, ?, 
                    NOT COALESCE((SELECT starred FROM user_items WHERE session_id = ? AND item_id = ?), 0),
                    COALESCE((SELECT is_read FROM user_items WHERE session_id = ? AND item_id = ?), 0),
                    (SELECT folder_id FROM user_items WHERE session_id = ? AND item_id = ?)
                )
            """, (session_id, item_id, session_id, item_id, session_id, item_id, session_id, item_id))
            
            # Get updated item in same transaction
            result = conn.execute("""
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
            
            return dict(result) if result else None
    
    @staticmethod
    def toggle_read_and_get_item(session_id: str, item_id: int) -> Optional[Dict]:
        """Toggle read status and return updated item - optimized single transaction"""
        with get_db() as conn:
            # Get current read status and toggle it
            current_result = conn.execute("""
                SELECT COALESCE(ui.is_read, 0) as current_read
                FROM feed_items fi
                LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
                WHERE fi.id = ?
            """, (session_id, item_id)).fetchone()
            
            if not current_result:
                return None  # Item doesn't exist
            
            new_read_status = not current_result[0]
            
            # Update read status
            conn.execute("""
                INSERT OR REPLACE INTO user_items (session_id, item_id, is_read, starred, folder_id)
                VALUES (?, ?, ?, 
                        COALESCE((SELECT starred FROM user_items WHERE session_id = ? AND item_id = ?), 0),
                        (SELECT folder_id FROM user_items WHERE session_id = ? AND item_id = ?)
                )
            """, (session_id, item_id, new_read_status, session_id, item_id, session_id, item_id))
            
            # Get updated item in same transaction
            result = conn.execute("""
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
            
            return dict(result) if result else None
    
    @staticmethod
    def mark_read_and_get_item(session_id: str, item_id: int, is_read: bool = True) -> Optional[Dict]:
        """Mark item as read and return updated item - optimized single transaction"""
        with get_db() as conn:
            # Mark as read
            conn.execute("""
                INSERT OR REPLACE INTO user_items (session_id, item_id, is_read, starred, folder_id)
                VALUES (?, ?, ?, 
                        COALESCE((SELECT starred FROM user_items WHERE session_id = ? AND item_id = ?), 0),
                        (SELECT folder_id FROM user_items WHERE session_id = ? AND item_id = ?)
                )
            """, (session_id, item_id, is_read, session_id, item_id, session_id, item_id))
            
            # Get updated item in same transaction
            result = conn.execute("""
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
            
            return dict(result) if result else None
    
    @staticmethod
    def move_to_folder(session_id: str, item_id: int, folder_id: int):
        """Move item to folder"""
        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_items (session_id, item_id, folder_id, is_read, starred)
                VALUES (?, ?, ?, 
                    COALESCE((SELECT is_read FROM user_items WHERE session_id = ? AND item_id = ?), 0),
                    COALESCE((SELECT starred FROM user_items WHERE session_id = ? AND item_id = ?), 0)
                )
            """, (session_id, item_id, folder_id, session_id, item_id, session_id, item_id))

class FolderModel:
    @staticmethod
    def create_folder(session_id: str, name: str) -> int:
        """Create folder for user"""
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO folders (session_id, name) VALUES (?, ?)
            """, (session_id, name))
            return cursor.lastrowid
    
    @staticmethod
    def get_folders(session_id: str) -> List[Dict]:
        """Get all folders for user"""
        with get_db() as conn:
            return [dict(row) for row in conn.execute("""
                SELECT * FROM folders WHERE session_id = ? ORDER BY name
            """, (session_id,)).fetchall()]

# Initialize database on import
init_db()