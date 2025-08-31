"""Optimized integration tests: HTTP-only, targeting workflows that broke during development"""

import pytest
import httpx
import time
import os
import subprocess
import sys
from bs4 import BeautifulSoup
from contextlib import contextmanager
from unittest.mock import patch, Mock

TEST_PORT = 5006
TEST_URL = f"http://localhost:{TEST_PORT}"
TEST_DB_PATH = "data/test_optimized.db"

@contextmanager
def test_server():
    """Lightweight test server for HTTP integration testing"""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    os.makedirs(os.path.dirname(TEST_DB_PATH), exist_ok=True)
    
    # Create a proper startup script
    startup_script = f"""
import os
import sys
sys.path.insert(0, '{os.getcwd()}')

# Set database path before any imports
os.environ['RSS_DB_PATH'] = '{TEST_DB_PATH}'

# Import models and override DB_PATH
import models
models.DB_PATH = '{TEST_DB_PATH}'

# Initialize database
models.init_db()

# Import and start app
from app import app
import uvicorn

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port={TEST_PORT}, log_level='error')
"""
    
    # Write startup script to file
    script_path = f"test_server_{TEST_PORT}.py"
    with open(script_path, 'w') as f:
        f.write(startup_script)
    
    try:
        # Start server process
        process = subprocess.Popen([
            sys.executable, script_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server startup with retries
        server_started = False
        for attempt in range(12):  # 12 attempts, 1 second each
            time.sleep(1)
            try:
                response = httpx.get(f"{TEST_URL}/", timeout=3)
                if response.status_code == 200:
                    server_started = True
                    break
            except:
                continue
        
        if not server_started:
            stdout, stderr = process.communicate(timeout=5)
            print(f"Server startup failed. STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            raise Exception("Failed to start test server after 12 seconds")
        
        yield TEST_URL
        
    finally:
        # Cleanup
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        # Remove startup script
        if os.path.exists(script_path):
            os.remove(script_path)
            
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

def parse_html(content):
    return BeautifulSoup(content, 'html.parser')

class TestCriticalHTTPWorkflows:
    """Test workflows that actually broke during development - HTTP verification only"""
    
    def test_fresh_start_complete_flow(self):
        """Test: Empty DB → Default feeds setup → Session creation → Articles display
        
        This was the core issue: 'No posts available' despite feeds existing.
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
                    if len(feed_links) >= 3:  # 3 default feeds
                        feeds_loaded = True
                        break
                
                assert feeds_loaded, "Default feeds should be created and visible"
                
                # 3. Should have substantial articles (not "No posts available")
                articles = soup.find_all('li', id=lambda x: x and x.startswith('feed-item-'))
                assert len(articles) >= 15, f"Should have 15+ articles, got {len(articles)}"
                
                # 4. Should show pagination (indicates substantial content)
                pagination = soup.find(string=lambda s: s and 'Showing' in s and 'posts' in s)
                assert pagination is not None, "Should have pagination info"
                
            finally:
                client.close()
    
    def test_session_persistence_across_requests(self):
        """Test: Session creation → Cookie persistence → Data consistency
        
        Sessions weren't persisting initially.
        """
        with test_server() as server_url:
            client = httpx.Client(timeout=30)
            
            try:
                # First request creates session
                resp1 = client.get(f"{server_url}/")
                soup1 = parse_html(resp1.text)
                
                # Wait for content
                time.sleep(3)
                resp1_content = client.get(f"{server_url}/")
                soup1_content = parse_html(resp1_content.text)
                feeds1 = soup1_content.find_all('a', href=lambda h: h and 'feed_id' in h)
                
                # Second request should maintain session
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
                # Wait for content
                time.sleep(5)
                
                # Test various parameter combinations
                test_urls = [
                    "/",                           # Basic
                    "/?page=2",                   # Pagination
                    "/?unread=1",                 # Filtering
                    "/?feed_id=1",                # Feed filtering
                    "/?feed_id=1&page=2",         # Feed + pagination
                    "/?unread=1&page=2",          # Unread + pagination
                    "/?feed_id=1&unread=1&page=2" # All parameters
                ]
                
                for test_url in test_urls:
                    resp = client.get(f"{server_url}{test_url}")
                    assert resp.status_code == 200, f"Failed: {test_url}"
                    
                    soup = parse_html(resp.text)
                    assert soup.find('title', string='RSS Reader'), f"Invalid response for {test_url}"
                    
                    # Should have proper structure
                    assert soup.find('h3'), f"Missing content structure for {test_url}"
                
            finally:
                client.close()
    
    def test_article_reading_state_via_http(self):
        """Test: Article detail → Read marking → Response structure
        
        Tests the HTMX endpoint that marks articles as read.
        """
        with test_server() as server_url:
            client = httpx.Client(timeout=30)
            
            try:
                # Get main page and find articles
                time.sleep(5)
                resp = client.get(f"{server_url}/")
                soup = parse_html(resp.text)
                
                articles = soup.find_all('li', id=lambda x: x and x.startswith('feed-item-'))
                
                if len(articles) > 0:
                    # Extract article ID
                    article_id = articles[0].get('id').replace('feed-item-', '')
                    
                    # Test article detail endpoint
                    detail_resp = client.get(f"{server_url}/item/{article_id}")
                    assert detail_resp.status_code == 200
                    
                    detail_soup = parse_html(detail_resp.text)
                    
                    # Should have article detail structure
                    assert detail_soup.find('strong'), "Should have article title"
                    assert detail_soup.find('time'), "Should have timestamp"
                    assert detail_soup.find(string='From:'), "Should have source info"
                    
                    # Test with unread_view parameter (our HTMX logic)
                    unread_detail_resp = client.get(f"{server_url}/item/{article_id}?unread_view=true")
                    assert unread_detail_resp.status_code == 200
                
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

if __name__ == "__main__":
    pytest.main([__file__, "-v"])