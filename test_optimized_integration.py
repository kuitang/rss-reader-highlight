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
    
    # Start minimal server
    process = subprocess.Popen([
        sys.executable, "-c", f"""
import os, sys
os.environ['RSS_DB_PATH'] = '{TEST_DB_PATH}'
sys.path.insert(0, '.')

import models
models.DB_PATH = '{TEST_DB_PATH}'

from app import serve
serve(port={TEST_PORT}, host='127.0.0.1', reload=False)
"""
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    time.sleep(6)
    
    try:
        # Verify server started
        response = httpx.get(f"{TEST_URL}/", timeout=5)
        if response.status_code != 200:
            raise Exception("Server failed to start")
        yield TEST_URL
    except:
        process.terminate()
        raise
    finally:
        process.terminate()
        process.wait(timeout=3)
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

if __name__ == "__main__":
    pytest.main([__file__, "-v"])