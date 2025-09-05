#!/usr/bin/env python3
"""
Test Docker container integration using existing test patterns.
Points existing tests to Docker container instead of local server.
"""

import asyncio
from playwright.sync_api import sync_playwright
import httpx
import time

DOCKER_URL = "http://localhost:8080"

# HTMX Helper Functions for Fast Testing  
def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete - much faster than fixed timeouts"""
    page.wait_for_function("() => !document.body.classList.contains('htmx-request')", timeout=timeout)

def test_docker_integration():
    """Test Docker container functionality"""
    print("=== DOCKER INTEGRATION TEST ===")
    
    # Test 1: HTTP API endpoints
    print("\n--- TEST 1: HTTP API Endpoints ---")
    import httpx
    with httpx.Client() as client:
        # Test main page
        response = client.get(f"{DOCKER_URL}/")
        print(f"✓ Main page: {response.status_code} ({len(response.text)} chars)")
        assert "RSS Reader" in response.text
        
        # Test item endpoint (use a likely ID)
        response = client.get(f"{DOCKER_URL}/item/1")
        print(f"✓ Item endpoint: {response.status_code} ({len(response.text)} chars)")
        
    # Test 2: Playwright UI testing (sync API)
    print("\n--- TEST 2: Playwright UI Testing ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Desktop functionality
        page.goto(DOCKER_URL)
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.wait_for_load_state("networkidle")
        
        desktop_visible = page.locator("#desktop-layout").is_visible()
        articles_count = page.locator("#desktop-feeds-content .js-filter li").count()
        print(f"✓ Desktop layout: {desktop_visible}, Articles: {articles_count}")
        
        # Test article click
        if articles_count > 0:
            first_article = page.locator("#desktop-feeds-content .js-filter li").first
            first_article.click()
            wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX response instead of 1 second
            
            detail_content = page.locator("#desktop-item-detail").inner_text()
            article_loaded = "Select a post to read" not in detail_content
            print(f"✓ Article loading: {article_loaded}")
        
        # Mobile functionality
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(DOCKER_URL)
        page.wait_for_load_state("networkidle")
        
        mobile_visible = page.locator("#main-content").is_visible()
        mobile_articles = page.locator("#main-content .js-filter li").count()
        print(f"✓ Mobile layout: {mobile_visible}, Articles: {mobile_articles}")
        
        browser.close()
    
    print("\n🎉 DOCKER INTEGRATION TESTS COMPLETED")
    return True

if __name__ == "__main__":
    success = test_docker_integration()
    exit(0 if success else 1)