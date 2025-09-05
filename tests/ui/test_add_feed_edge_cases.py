"""Test add feed flow edge cases to find what's broken"""

import pytest
from playwright.sync_api import sync_playwright, expect
import time

# HTMX Helper Functions for Fast Testing
def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete - much faster than fixed timeouts"""
    page.wait_for_function("() => !document.body.classList.contains('htmx-request')", timeout=timeout)

def wait_for_page_ready(page):
    """Fast page ready check - waits for network idle instead of fixed timeout"""
    page.wait_for_load_state("networkidle")

def test_add_feed_edge_cases(page):
    """Test various add feed scenarios to find issues"""
        
    # Set mobile viewport
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto("http://localhost:8080")
    wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle instead of 5 seconds
    
    print("🧪 TESTING ADD FEED EDGE CASES")
    
    # Open sidebar - updated selector to match current app.py
    hamburger = page.locator('#mobile-header button').filter(has=page.locator('uk-icon[icon="menu"]'))
    hamburger.click()
    page.wait_for_selector("#mobile-sidebar", state="visible")  # OPTIMIZED: Wait for sidebar to appear
    
    feed_input = page.locator('#mobile-sidebar input[name="new_feed_url"]')
    add_button = page.locator('#mobile-sidebar button.add-feed-button')  # Updated selector to match current app.py
    
    test_cases = [
        ("", "Empty URL"),
        ("not-a-url", "Invalid URL"),
        ("https://httpbin.org/status/404", "404 URL"),
        ("https://httpbin.org/html", "Non-RSS URL"),
        ("https://httpbin.org/xml", "Valid XML (should work)"),
    ]
    
    for test_url, description in test_cases:
        print(f"\n--- TESTING: {description} ---")
        print(f"URL: '{test_url}'")
        
        # Clear and enter URL
        feed_input.clear()
        if test_url:
            feed_input.fill(test_url)
        
        # Click add button
        add_button.click()
        wait_for_htmx_complete(page, timeout=8000)  # OPTIMIZED: Wait for HTMX response instead of 3 seconds
        
        # Check for any response in sidebar
        sidebar_text = page.locator("#mobile-sidebar").inner_text()
        
        # Look for specific messages
        has_error_msg = "Error" in sidebar_text or "Failed" in sidebar_text
        has_success_msg = "success" in sidebar_text.lower() or "added" in sidebar_text.lower()
        has_duplicate_msg = "Already subscribed" in sidebar_text
        has_empty_msg = "Please enter" in sidebar_text
        
        print(f"  Error message: {has_error_msg}")
        print(f"  Success message: {has_success_msg}")
        print(f"  Duplicate message: {has_duplicate_msg}")
        print(f"  Empty URL message: {has_empty_msg}")
        
        if has_error_msg or has_success_msg or has_duplicate_msg or has_empty_msg:
            print(f"  ✓ Got expected response for {description}")
        else:
            print(f"  ❌ No clear response for {description}")
            print(f"  Sidebar text preview: {sidebar_text[:200]}...")
    
    print("\n=== OVERALL ADD FEED FLOW ASSESSMENT ===")
    print("All test cases completed - check individual results above")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])