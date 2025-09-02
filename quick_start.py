#!/usr/bin/env python3
"""Quick start script for minimal mode testing"""

import os
import subprocess
import sys

def main():
    """Start RSS reader in minimal mode for fast testing"""
    print("🚀 Starting RSS Reader in MINIMAL MODE...")
    print("⚡ Fast startup with Hacker News + ClaudeAI feeds only")
    print("📊 Database: data/minimal.db (fresh copy from seed)")
    print()
    
    # Set environment variable and start app
    env = os.environ.copy()
    env['MINIMAL_MODE'] = 'true'
    
    try:
        # Start the app
        subprocess.run([sys.executable, 'app.py'], env=env)
    except KeyboardInterrupt:
        print("\n👋 Shutting down minimal RSS Reader")

if __name__ == "__main__":
    main()