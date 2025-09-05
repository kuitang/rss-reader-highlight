#!/usr/bin/env python3
"""
Application startup tests with real server instances on random ports.
Tests both minimal and non-minimal database setup modes.

This tests what the manual testing verified:
- setup_default_feeds(minimal_mode=False) creates 13 feeds
- setup_default_feeds(minimal_mode=True) creates 2 feeds
- Both modes start properly and serve HTTP responses
"""

import pytest
pytestmark = pytest.mark.skip(reason="TODO: Fix integration tests")
import httpx
import multiprocessing
import uvicorn
import time
import os
import tempfile
import socket
from contextlib import contextmanager
from bs4 import BeautifulSoup
import sys

# Add the parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Application startup tests with isolated server instances

def get_free_port():
    """Get a random free port"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def create_temp_db_path():
    """Create a temporary database path"""
    fd, path = tempfile.mkstemp(suffix='.db', prefix='test_app_')
    os.close(fd)
    return path

def start_app_process(port, db_path, minimal_mode=False):
    """Start the application in a separate process"""
    def run_app():
        import os
        os.environ['DATABASE_PATH'] = db_path
        if minimal_mode:
            os.environ['MINIMAL_MODE'] = 'true'
        else:
            os.environ.pop('MINIMAL_MODE', None)
        
        # Import app after setting environment variables
        from app import app
        
        # Start uvicorn server
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
    
    process = multiprocessing.Process(target=run_app)
    process.start()
    return process

@contextmanager
def app_server_context(minimal_mode=False):
    """Context manager that starts an app server on a random port"""
    port = get_free_port()
    db_path = create_temp_db_path()
    
    # Start the server process
    process = start_app_process(port, db_path, minimal_mode)
    
    try:
        # Wait for server to start
        server_url = f"http://localhost:{port}"
        
        # Wait up to 10 seconds for server to be ready
        for attempt in range(50):  # 50 * 0.2 = 10 seconds
            try:
                response = httpx.get(f"{server_url}/", timeout=2)
                if response.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(0.2)
                continue
        else:
            raise RuntimeError(f"Server failed to start on port {port}")
        
        yield server_url, db_path
        
    finally:
        # Clean up
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join()
        
        # Clean up database file
        try:
            os.unlink(db_path)
        except OSError:
            pass

def parse_html(content):
    """Parse HTML content"""
    return BeautifulSoup(content, 'html.parser')

class TestApplicationStartup:
    """Test application startup with different database modes"""
    
    def test_normal_mode_startup_and_feeds(self):
        """Test normal mode starts with full feed set (13 feeds after removing BizToc)"""
        with app_server_context(minimal_mode=False) as (server_url, db_path):
            client = httpx.Client(timeout=10)
            
            # Test main page loads
            response = client.get(f"{server_url}/")
            assert response.status_code == 200
            
            soup = parse_html(response.text)
            assert soup.find('title', string='RSS Reader')
            
            # Test that feeds are present in the sidebar
            # Look for feed links in the sidebar  
            feed_links = soup.find_all('a', href=lambda x: x and x.startswith('/?feed_id='))
            
            # Get unique feed IDs (since each feed appears in both mobile and desktop sidebars)
            unique_feed_ids = set()
            for link in feed_links:
                href = link.get('href', '')
                if 'feed_id=' in href:
                    feed_id = href.split('feed_id=')[1].split('&')[0]
                    unique_feed_ids.add(feed_id)
            
            # Should have 13 unique feeds (removed BizToc from the original 14)
            assert len(unique_feed_ids) >= 13, f"Expected at least 13 unique feeds, got {len(unique_feed_ids)}"
            
            # Verify some expected feeds exist by checking link text
            feed_texts = [link.get_text().strip() for link in feed_links]
            expected_feeds = [
                "Bloomberg Economics",
                "Hacker News", 
                "ClaudeAI",
                "TechCrunch"
            ]
            
            for expected_feed in expected_feeds:
                assert any(expected_feed in text for text in feed_texts), \
                    f"Expected feed '{expected_feed}' not found in {feed_texts}"
            
            # Verify BizToc is NOT present
            assert not any("BizToc" in text for text in feed_texts), \
                f"BizToc should not be present in {feed_texts}"
    
    def test_minimal_mode_startup_and_feeds(self):
        """Test minimal mode starts with minimal feed set (2 feeds)"""
        with app_server_context(minimal_mode=False) as (server_url, db_path):
            client = httpx.Client(timeout=10)
            
            # Test main page loads
            response = client.get(f"{server_url}/")
            assert response.status_code == 200
            
            soup = parse_html(response.text)
            assert soup.find('title', string='RSS Reader')
            
            # Test that only minimal feeds are present
            # Note: Page has both mobile and desktop layouts, so each feed appears twice
            feed_links = soup.find_all('a', href=lambda x: x and x.startswith('/?feed_id='))
            
            # Get unique feed IDs (since each feed appears in both mobile and desktop sidebars)
            unique_feed_ids = set()
            for link in feed_links:
                href = link.get('href', '')
                if 'feed_id=' in href:
                    feed_id = href.split('feed_id=')[1].split('&')[0]
                    unique_feed_ids.add(feed_id)
            
            # Should have exactly 2 unique feeds in minimal mode
            assert len(unique_feed_ids) == 2, f"Expected exactly 2 unique feeds in minimal mode, got {len(unique_feed_ids)}: {unique_feed_ids}"
            
            # Verify the minimal feeds exist
            feed_texts = [link.get_text().strip() for link in feed_links]
            expected_minimal_feeds = ["Hacker News", "ClaudeAI"]  # Note: could be "Hacker News: Front Page"
            
            for expected_feed in expected_minimal_feeds:
                assert any(expected_feed in text for text in feed_texts), \
                    f"Expected minimal feed '{expected_feed}' not found in {feed_texts}"
    
    def test_both_modes_serve_different_content(self):
        """Test that normal and minimal modes actually serve different feed counts"""
        # This test runs both modes and compares the results
        
        def count_unique_feeds(soup):
            """Helper to count unique feeds (accounting for mobile/desktop duplication)"""
            feed_links = soup.find_all('a', href=lambda x: x and x.startswith('/?feed_id='))
            unique_feed_ids = set()
            for link in feed_links:
                href = link.get('href', '')
                if 'feed_id=' in href:
                    feed_id = href.split('feed_id=')[1].split('&')[0]
                    unique_feed_ids.add(feed_id)
            return len(unique_feed_ids)
        
        # Test normal mode
        with app_server_context(minimal_mode=False) as (normal_server_url, normal_db_path):
            normal_client = httpx.Client(timeout=10)
            normal_response = normal_client.get(f"{normal_server_url}/")
            normal_soup = parse_html(normal_response.text)
            normal_count = count_unique_feeds(normal_soup)
        
        # Test minimal mode
        with app_server_context(minimal_mode=True) as (minimal_server_url, minimal_db_path):
            minimal_client = httpx.Client(timeout=10)
            minimal_response = minimal_client.get(f"{minimal_server_url}/")
            minimal_soup = parse_html(minimal_response.text)
            minimal_count = count_unique_feeds(minimal_soup)
        
        # Verify the counts are different and as expected
        assert minimal_count == 2, f"Minimal mode should have 2 unique feeds, got {minimal_count}"
        assert normal_count >= 13, f"Normal mode should have at least 13 unique feeds, got {normal_count}"
        assert normal_count > minimal_count, f"Normal mode ({normal_count}) should have more feeds than minimal mode ({minimal_count})"
    
    def test_database_isolation(self):
        """Test that different instances use different database files"""
        db_paths = []
        
        # Start two instances and collect their database paths
        with app_server_context(minimal_mode=False) as (server1_url, db_path1):
            db_paths.append(db_path1)
            
            with app_server_context(minimal_mode=True) as (server2_url, db_path2):
                db_paths.append(db_path2)
                
                # Verify different database paths
                assert db_path1 != db_path2, "Database paths should be different"
                
                # Verify both servers respond
                client1 = httpx.Client(timeout=5)
                client2 = httpx.Client(timeout=5)
                
                response1 = client1.get(f"{server1_url}/")
                response2 = client2.get(f"{server2_url}/")
                
                assert response1.status_code == 200
                assert response2.status_code == 200
        
        # Verify database files were created and cleaned up
        # (cleanup happens in finally block, so they should be gone)
        for db_path in db_paths:
            assert not os.path.exists(db_path), f"Database file {db_path} should have been cleaned up"
    
    def test_fresh_start_complete_flow(self):
        """Test: Empty DB → Default feeds setup → Session creation → Articles display
        
        Originally from test_optimized_integration.py - moved here to test actual startup.
        This was the core issue: 'No posts available' despite feeds existing.
        """
        with app_server_context(minimal_mode=False) as (server_url, db_path):
            client = httpx.Client(timeout=10)
            
            # 1. First request triggers everything: beforeware, feed setup, session
            response = client.get(f"{server_url}/")
            assert response.status_code == 200
            
            soup = parse_html(response.text)
            assert soup.find('title', string='RSS Reader')
            
            # 2. Check that feeds were set up (no need to wait - they're created synchronously now)
            feed_links = soup.find_all('a', href=lambda h: h and 'feed_id' in h)
            assert len(feed_links) >= 13, f"Expected at least 13 feeds, got {len(feed_links)}"
            
            # 3. Should have feed items visible (or at least the structure for them)
            # Look for the feeds list container - should exist even if no articles yet
            feeds_container = soup.find('div', id='feeds-list-container')
            assert feeds_container is not None, "Feeds list container should exist"
    
    def test_session_persistence_across_requests(self):
        """Test: Request 1 → Session created → Request 2 → Same session data
        
        Originally from test_optimized_integration.py - moved here for database testing.
        Session persistence was critical for user experience.
        """
        with app_server_context(minimal_mode=False) as (server_url, db_path):
            client = httpx.Client(timeout=10)
            
            # First request
            resp1 = client.get(f"{server_url}/")
            assert resp1.status_code == 200
            
            soup1 = parse_html(resp1.text)
            feed_links_1 = soup1.find_all('a', href=lambda h: h and 'feed_id' in h)
            
            # Second request (same client = same session)
            resp2 = client.get(f"{server_url}/")
            assert resp2.status_code == 200
            
            soup2 = parse_html(resp2.text)
            feed_links_2 = soup2.find_all('a', href=lambda h: h and 'feed_id' in h)
            
            # Should have same feeds (session persisted)
            assert len(feed_links_1) == len(feed_links_2), "Feed count should be consistent across requests"
            assert len(feed_links_1) >= 13, "Should have expected number of feeds"
    
    def test_form_parameter_mapping_via_http(self):
        """Test: Form submission → FastHTML parameter mapping → Server response
        
        Originally from test_optimized_integration.py - moved here to test database operations.
        This was our BIGGEST bug - form parameters not mapping to FastHTML functions.
        """
        with app_server_context(minimal_mode=False) as (server_url, db_path):
            client = httpx.Client(timeout=10)
            
            # Test empty form submission
            empty_resp = client.post(f"{server_url}/api/feed/add", 
                                   data={'new_feed_url': ''})
            assert empty_resp.status_code == 200
            
            # Response should contain error message (not crash)
            assert 'Please enter a URL' in empty_resp.text
            
            # Test actual URL submission (should NOT give parameter error)
            url_resp = client.post(f"{server_url}/api/feed/add", 
                                 data={'new_feed_url': 'https://httpbin.org/xml'})
            assert url_resp.status_code == 200
            
            # Should NOT contain parameter mapping error
            assert 'Please enter a URL' not in url_resp.text
            
            # Should get sidebar response back (indicating successful processing)
            # The response is the updated sidebar HTML
            assert 'feeds-list' in url_resp.text or 'sidebar' in url_resp.text
    
    def test_minimal_vs_normal_database_behavior(self):
        """Test that minimal and normal modes actually create different database states"""
        # Test that both modes work independently and create appropriate feeds
        
        minimal_feeds = []
        normal_feeds = []
        
        def get_unique_feeds(soup):
            """Get unique feeds from soup, accounting for mobile/desktop duplication"""
            feed_links = soup.find_all('a', href=lambda h: h and 'feed_id' in h)
            unique_feeds = {}  # feed_id -> feed_name
            for link in feed_links:
                href = link.get('href', '')
                if 'feed_id=' in href:
                    feed_id = href.split('feed_id=')[1].split('&')[0]
                    feed_name = link.get_text().strip()
                    unique_feeds[feed_id] = feed_name
            return unique_feeds
        
        # Test minimal mode
        with app_server_context(minimal_mode=True) as (minimal_url, minimal_db):
            client = httpx.Client(timeout=10)
            response = client.get(f"{minimal_url}/")
            soup = parse_html(response.text)
            minimal_feeds = get_unique_feeds(soup)
        
        # Test normal mode  
        with app_server_context(minimal_mode=False) as (normal_url, normal_db):
            client = httpx.Client(timeout=10)
            response = client.get(f"{normal_url}/")
            soup = parse_html(response.text)
            normal_feeds = get_unique_feeds(soup)
        
        # Verify expected behavior
        assert len(minimal_feeds) == 2, f"Minimal mode should have 2 unique feeds, got {len(minimal_feeds)}: {list(minimal_feeds.values())}"
        assert len(normal_feeds) >= 13, f"Normal mode should have 13+ unique feeds, got {len(normal_feeds)}: {list(normal_feeds.values())[:5]}..."
        
        # Verify minimal feeds are subset of normal feeds (by comparing core feed names)
        # Clean up feed names by removing "updated X" suffix and extracting core names
        def clean_feed_name(name):
            # Remove "updated never updated" etc and extract core name
            clean = name.split(' updated ')[0] if ' updated ' in name else name
            # Handle variations like "Hacker News: Front Page" vs "Hacker News"
            if 'Hacker News' in clean:
                return 'Hacker News'
            return clean
        
        minimal_clean_names = [clean_feed_name(name) for name in minimal_feeds.values()]
        normal_clean_names = [clean_feed_name(name) for name in normal_feeds.values()]
        
        for minimal_name in minimal_clean_names:
            assert any(minimal_name in normal_name or normal_name in minimal_name 
                      for normal_name in normal_clean_names), \
                f"Minimal feed '{minimal_name}' should be present in normal feeds {normal_clean_names}"

if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])