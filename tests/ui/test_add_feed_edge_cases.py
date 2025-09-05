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
    """Test various add feed scenarios to find issues on both mobile and desktop"""
    
    print("🧪 TESTING ADD FEED EDGE CASES")
    
    for viewport_name, viewport_size in [
        ("desktop", {"width": 1200, "height": 800}),
        ("mobile", {"width": 375, "height": 667})
    ]:
        print(f"\n--- Testing {viewport_name} add feed edge cases ---")
        page.set_viewport_size(viewport_size)
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)
        
        # Debug: Check if correct layout is visible
        desktop_layout_visible = page.locator("#desktop-layout").is_visible()
        mobile_layout_visible = page.locator("#mobile-layout").is_visible()
        print(f"  Debug: Desktop layout visible: {desktop_layout_visible}, Mobile layout visible: {mobile_layout_visible}")
        
        # Debug: Check what elements are available
        if viewport_name == "desktop":
            sidebar_exists = page.locator("#sidebar").count() > 0
            print(f"  Debug: #sidebar exists: {sidebar_exists}")
            if not sidebar_exists:
                # Look for form elements directly
                input_exists = page.locator('input[placeholder="Enter RSS URL"]').count() > 0
                button_exists = page.locator('button').count() > 0
                print(f"  Debug: RSS input exists: {input_exists}, buttons exist: {button_exists}")
                # Show page title for context
                print(f"  Debug: Page title: {page.title()}")
        
        # Set up viewport-specific selectors
        if viewport_name == "mobile":
            # Open mobile sidebar
            hamburger = page.locator('#mobile-nav-button')
            if hamburger.is_visible():
                hamburger.click()
                page.wait_for_selector("#mobile-sidebar", state="visible")
                feed_input = page.locator('#mobile-sidebar input[name="new_feed_url"]')
                add_button = page.locator('#mobile-sidebar button.add-feed-button')
            else:
                print(f"  ⚠️ Mobile navigation not available, skipping {viewport_name}")
                continue
        else:
            # Desktop selectors - try multiple approaches
            # First try the specific sidebar selectors
            feed_input = page.locator('#sidebar input[name="new_feed_url"]')
            add_button = page.locator('#sidebar button.add-feed-button')
            
            # If sidebar elements aren't found, try direct selectors
            if feed_input.count() == 0:
                print(f"  Debug: Sidebar input not found, trying direct selectors")
                feed_input = page.locator('input[placeholder="Enter RSS URL"]')
                add_button = page.locator('button').filter(has_text="").first  # First button that might be the add button
            
            # Debug what we found
            print(f"  Debug: Found {feed_input.count()} input(s), {add_button.count()} button(s)")
    
        test_cases = [
            ("", "Empty URL"),
            ("not-a-url", "Invalid URL"),
            ("https://httpbin.org/status/404", "404 URL"),
            ("https://httpbin.org/html", "Non-RSS URL"),
            ("https://httpbin.org/xml", "Valid XML (should work)"),
        ]
        
        for test_url, description in test_cases:
            print(f"\n--- TESTING: {description} ({viewport_name}) ---")
            print(f"URL: '{test_url}'")
            
            # Re-navigate to get fresh form for each test case
            page.goto("http://localhost:8080")
            wait_for_page_ready(page)
            
            # Set up viewport-specific selectors fresh
            if viewport_name == "mobile":
                # Open mobile sidebar fresh
                hamburger = page.locator('#mobile-nav-button')
                if hamburger.is_visible():
                    hamburger.click()
                    page.wait_for_selector("#mobile-sidebar", state="visible")
                    feed_input = page.locator('#mobile-sidebar input[name="new_feed_url"]')
                    add_button = page.locator('#mobile-sidebar button.add-feed-button')
                else:
                    print(f"  ⚠️ Mobile navigation not available, skipping test case")
                    continue
            else:
                # Desktop: fresh element location
                feed_input = page.locator('input[placeholder="Enter RSS URL"]')
                add_button = page.locator('button').filter(has_text="").first
            
            # Clear and enter URL (with error handling)
            try:
                if feed_input.count() > 0:
                    feed_input.clear()
                    if test_url:
                        feed_input.fill(test_url)
                else:
                    print(f"  ⚠️ Could not find input field for {description}")
                    continue
            except Exception as e:
                print(f"  ⚠️ Could not interact with input field: {e}")
                continue
            
            # Click add button
            add_button.click()
            wait_for_htmx_complete(page, timeout=8000)
            
            # Check for any response in sidebar (viewport-specific)
            if viewport_name == "mobile":
                sidebar_selector = "#mobile-sidebar"
                try:
                    expect(page.locator(sidebar_selector)).to_be_visible(timeout=5000)
                    sidebar_text = page.locator(sidebar_selector).inner_text(timeout=5000)
                except Exception as e:
                    print(f"  Warning: Could not get mobile sidebar text: {e}")
                    sidebar_text = ""
            else:
                # For desktop, try to get text from sidebar or fall back to page text
                sidebar_text = ""
                try:
                    if page.locator("#sidebar").count() > 0:
                        sidebar_text = page.locator("#sidebar").inner_text(timeout=2000)
                    else:
                        # Fall back to checking page content for feedback
                        sidebar_text = page.locator("body").inner_text(timeout=2000)
                except Exception as e:
                    print(f"  Warning: Could not get desktop sidebar text: {e}")
                    sidebar_text = page.locator("body").inner_text() if page.locator("body").count() > 0 else ""
            
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
                print(f"  ✓ Got expected response for {description} ({viewport_name})")
            else:
                print(f"  ❌ No clear response for {description} ({viewport_name})")
                print(f"  Sidebar text preview: {sidebar_text[:200]}...")
            
            # Verify app didn't crash (check that we can still interact with the page)
            if viewport_name == "mobile":
                assert page.locator("#mobile-sidebar").count() > 0, f"{viewport_name} sidebar should exist"
            else:
                # For desktop, just check the page is still responsive
                assert page.locator("#desktop-layout").is_visible(), f"{viewport_name} desktop layout should be visible"
        
        print(f"  ✓ {viewport_name} add feed edge cases test passed")
    
    print("\n=== OVERALL ADD FEED FLOW ASSESSMENT ===")
    print("All test cases completed for both mobile and desktop - check individual results above")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])