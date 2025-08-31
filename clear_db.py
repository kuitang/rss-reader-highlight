#!/usr/bin/env python3
"""Script to clear/reset the RSS Reader database"""

import os
import sqlite3
from models import DB_PATH, init_db

def clear_database():
    """Remove database file and reinitialize empty database"""
    
    print("🗑️  Clearing RSS Reader database...")
    
    # Remove database file if it exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"✅ Deleted database file: {DB_PATH}")
    else:
        print(f"ℹ️  Database file not found: {DB_PATH}")
    
    # Reinitialize empty database with schema
    print("🔄 Reinitializing database schema...")
    init_db()
    
    # Verify database is empty
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        
        tables = ['feeds', 'feed_items', 'sessions', 'user_feeds', 'folders', 'user_items']
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {count} records")
    
    print("\n🎉 Database cleared successfully!")
    print("\nNext steps:")
    print("1. Start the RSS Reader application: python app.py")
    print("2. Visit http://localhost:5001 in your browser") 
    print("3. Default feeds will be automatically set up on first visit")
    print("4. New session will be subscribed to all default feeds")

if __name__ == "__main__":
    # Confirmation prompt
    response = input("⚠️  This will delete ALL RSS data. Continue? (y/N): ")
    
    if response.lower() in ['y', 'yes']:
        clear_database()
    else:
        print("❌ Operation cancelled")