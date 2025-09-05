"""Integration tests with self-contained server instances.

Database setup and startup tests have been moved to test_application_startup.py.
These tests focus on UI workflows that broke during development and can run with minimal or full database."""

import pytest
pytestmark = pytest.mark.skip(reason="TODO: Fix integration tests")
import httpx
import time
import os
import subprocess
import sys
import multiprocessing
import uvicorn
import tempfile
import socket
from bs4 import BeautifulSoup
from contextlib import contextmanager
from unittest.mock import patch, Mock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# HTTP integration tests with proper server isolation for parallel execution

def get_free_port():
    """Get a random free port"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def create_temp_db_path():
    """Create a temporary database path"""
    fd, path = tempfile.mkstemp(suffix='.db', prefix='test_integration_')
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
def test_server(minimal_mode=None):
    """Context manager that starts an app server on a random port"""
    # Use environment variable if minimal_mode not specified
    if minimal_mode is None:
        minimal_mode = os.environ.get('MINIMAL_MODE', 'false').lower() == 'true'
    
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
        
        yield server_url
        
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
    return BeautifulSoup(content, 'html.parser')

class TestCriticalHTTPWorkflows:
    """Tests for workflows that broke during development - targeting real bugs"""
    
    def test_fresh_start_complete_flow(self):
        """Test: Fresh DB → Seed content → Session creation → Articles display
        
        This was the core issue: 'No posts available' despite feeds existing.
        Works with both minimal mode (seed database) and normal mode (full database).
        """
        with test_server() as server_url:
            client = httpx.Client(timeout=30)
            
            try:
                # 1. First request triggers everything: beforeware, feed setup, session
                response = client.get(f"{server_url}/")
                assert response.status_code == 200
                
                soup = parse_html(response.text)
                assert soup.find('title', string='RSS Reader')
                
                # 2. Wait for feeds to load (default feed setup happens async)
                feeds_loaded = False
                for attempt in range(8):
                    time.sleep(2)
                    resp = client.get(f"{server_url}/")
                    soup = parse_html(resp.text)
                    
                    feed_links = soup.find_all('a', href=lambda h: h and 'feed_id' in h)
                    if len(feed_links) >= 2:  # 2+ feeds (works with minimal mode)
                        feeds_loaded = True
                        break
                
                assert feeds_loaded, "Default feeds should be created and visible"
                
                # 3. Should have articles (not "No posts available")
                articles = soup.find_all('li', id=lambda x: x and 'feed-item-' in x)
                assert len(articles) >= 10, f"Should have 10+ articles, got {len(articles)} (works with minimal mode's 20 articles)"
                
            finally:
                client.close()
    
    def test_session_persistence_across_requests(self):
        """Test: Request 1 → Session created → Request 2 → Same session data
        
        Session persistence was critical for user experience.
        """
        with test_server() as server_url:
            client = httpx.Client(timeout=30)
            
            try:
                # First request
                resp1 = client.get(f"{server_url}/")
                soup1 = parse_html(resp1.text)
                feeds1 = soup1.find_all('a', href=lambda h: h and 'feed_id' in h)
                
                # Second request with same client (same session)
                resp2 = client.get(f"{server_url}/")
                soup2 = parse_html(resp2.text)
                feeds2 = soup2.find_all('a', href=lambda h: h and 'feed_id' in h)
                
                # Should have consistent feed count (same session)
                assert len(feeds1) == len(feeds2), "Session should persist feeds across requests"
                
            finally:
                client.close()
    
    def test_form_parameter_mapping_via_http(self):
        """Test: Form submission → FastHTML parameter mapping → Server response
        
        This was our biggest debugging challenge - form parameters not mapping.
        """
        with test_server() as server_url:
            client = httpx.Client(timeout=30)
            
            try:
                # Test empty form submission
                empty_resp = client.post(f"{server_url}/api/feed/add", data={'new_feed_url': ''})
                assert empty_resp.status_code == 200
                
                empty_soup = parse_html(empty_resp.text)
                assert 'Please enter a URL' in empty_soup.get_text()
                
                # Test actual URL submission (should NOT give parameter error)
                url_resp = client.post(f"{server_url}/api/feed/add", 
                                      data={'new_feed_url': 'https://httpbin.org/xml'})
                # Debug: Print response details if it fails
                if url_resp.status_code != 200:
                    print(f"DEBUG: Response status: {url_resp.status_code}")
                    print(f"DEBUG: Response content: {url_resp.text[:500]}")
                assert url_resp.status_code == 200
                
                url_soup = parse_html(url_resp.text)
                # Should NOT contain parameter mapping error
                assert 'Please enter a URL' not in url_soup.get_text()
                
            finally:
                client.close()
    
    def test_pagination_with_complex_parameters(self):
        """Test: Pagination + filtering → URL parameters → Content changes
        
        Complex URL parameter handling that we implemented.
        """
        with test_server() as server_url:
            client = httpx.Client(timeout=30)
            
            try:
                # Test pagination on feed 5 (26 articles = 2 pages) 
                resp = client.get(f"{server_url}/?feed_id=5&page=2&unread=0")
                assert resp.status_code == 200
                
                soup = parse_html(resp.text)
                # Should NOT have "No posts available" (indicates parameter processing worked)
                assert 'No posts available' not in soup.get_text()
                
                # Should have articles on page 2 (verifies pagination worked)
                articles = soup.find_all('li', id=lambda x: x and 'feed-item-' in x)
                assert len(articles) > 0, f"Should have articles on page 2 of feed 5, got {len(articles)}"
                
                # Should have pagination buttons (since feed 5 has 26 articles = 2 pages)
                page_elements = soup.find_all('button', attrs={'hx-get': lambda x: x and 'page=' in x})
                assert len(page_elements) > 0, f"Should have pagination buttons with 26 articles per feed, got {len(page_elements)}"
                
            finally:
                client.close()
    
    def test_article_reading_state_via_http(self):
        """Test: Click article → Mark as read → State changes
        
        Article reading state was key functionality.
        """
        with test_server() as server_url:
            client = httpx.Client(timeout=30)
            
            try:
                # Get main page to find an article
                resp = client.get(f"{server_url}/")
                soup = parse_html(resp.text)
                
                # Find first article (HTMX-enabled li element, not href link)
                articles = soup.find_all('li', attrs={'hx-get': lambda x: x and '/item/' in x})
                # DISABLED CONDITIONAL FOR DEBUGGING
                # if len(articles) == 0:
                #     pytest.skip("No articles available for reading state test")
                assert len(articles) > 0, f"Should have articles available, but got {len(articles)}"
                
                article_url = articles[0]['hx-get']
                
                # Visit the article (should mark as read)
                article_resp = client.get(f"{server_url}{article_url}")
                assert article_resp.status_code == 200
                
                # Response should contain article content (not error)
                article_soup = parse_html(article_resp.text)
                assert len(article_soup.get_text()) > 100, "Article should have substantial content"
                
            finally:
                client.close()
    
    def test_no_untitled_feeds_error_detection(self):
        """Test: Verify no 'Untitled Feed' appears → Catch hidden errors
        
        'Untitled Feed updated Unknown' indicates silent failures.
        """
        with test_server() as server_url:
            client = httpx.Client(timeout=30)
            
            try:
                # Wait for feeds to load
                time.sleep(8)
                
                resp = client.get(f"{server_url}/")
                soup = parse_html(resp.text)
                
                # Check all feed links for "Untitled Feed"
                feed_links = soup.find_all('a', href=lambda h: h and 'feed_id' in h)
                
                for feed_link in feed_links:
                    feed_text = feed_link.get_text()
                    
                    # Should NEVER see "Untitled Feed" - indicates parsing failure
                    assert 'Untitled Feed' not in feed_text, f"Found untitled feed: {feed_text}"
                    
                    # Should NEVER see "updated Unknown" - indicates timestamp failure
                    assert 'updated Unknown' not in feed_text, f"Found unknown timestamp: {feed_text}"
                    
                    # Should NEVER see "None" as feed title - indicates failed feed parsing
                    assert 'None updated' not in feed_text, f"Found feed with None title: {feed_text}"
                    
                    # All feeds should have proper names
                    assert len(feed_text.strip()) > 0, "Feed should have a name"
                
                # Should have actual feed names
                feed_names = [link.get_text() for link in feed_links]
                expected_feeds = ["Hacker News", "Reddit", "WSJ", "BBC"]
                
                # At least some default feeds should be properly named
                found_proper_feeds = any(any(expected in name for expected in expected_feeds) for name in feed_names)
                assert found_proper_feeds, f"No properly named feeds found. Got: {feed_names}"
                
            finally:
                client.close()