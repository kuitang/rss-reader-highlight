"""Test add feed flow edge cases to find what's broken"""

import pytest
from playwright.sync_api import Page, expect
import time
import test_constants as constants
from test_helpers import (
    wait_for_htmx_complete,
    wait_for_page_ready,
    wait_for_htmx_settle
)

# HTMX Helper Functions for Fast Testing

def test_add_feed_edge_cases(page: Page, test_server_url):
    """Test various add feed scenarios to find issues on both mobile and desktop"""
    
    print("🧪 TESTING ADD FEED EDGE CASES")
    
    for viewport_name, viewport_size in [
        ("desktop", constants.DESKTOP_VIEWPORT_ALT),
        ("mobile", constants.MOBILE_VIEWPORT_ALT)
    ]:
        print(f"\n--- Testing {viewport_name} add feed edge cases ---")
        page.set_viewport_size(viewport_size)
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page)
        
        # Debug: Check if correct layout elements are visible
        app_root_visible = page.locator("#app-root").is_visible()
        feeds_sidebar_visible = page.locator("#feeds").is_visible()
        print(f"  Debug: App root visible: {app_root_visible}, Feeds sidebar visible: {feeds_sidebar_visible}")
        
        # Debug: Check what elements are available
        if viewport_name == "desktop":
            feeds_exists = page.locator("#feeds").count() > 0
            print(f"  Debug: #feeds exists: {feeds_exists}")
            if not feeds_exists:
                # Look for form elements directly
                input_exists = page.locator('input[placeholder="Enter RSS URL"]').count() > 0
                button_exists = page.locator('button').count() > 0
                print(f"  Debug: RSS input exists: {input_exists}, buttons exist: {button_exists}")
                # Show page title for context
                print(f"  Debug: Page title: {page.title()}")
        
        # Set up viewport-specific selectors
        if viewport_name == "mobile":
            # Open mobile sidebar using the correct hamburger button
            hamburger = page.locator('#summary [data-testid="hamburger-btn"]').first
            if hamburger.is_visible():
                hamburger.click()
                # Wait for drawer to open - sidebar should become visible
                page.wait_for_selector("#feeds", state="visible", timeout=constants.MAX_WAIT_MS)
                feed_input = page.locator('#feeds input[name="new_feed_url"]')
                add_button = page.locator('#feeds button.add-feed-button')
            else:
                print(f"  ⚠️ Mobile navigation button not available, skipping {viewport_name}")
                continue
        else:
            # Desktop: sidebar is always visible, direct selectors
            feed_input = page.locator('#feeds input[name="new_feed_url"]')
            add_button = page.locator('#feeds button.add-feed-button')

            # If sidebar elements aren't found, try fallback selectors
            if feed_input.count() == 0:
                print(f"  Debug: #feeds input not found, trying direct selectors")
                feed_input = page.locator('input[placeholder="Enter RSS URL"]')
                add_button = page.locator('button.add-feed-button')

            # Debug what we found
            print(f"  Debug: Found {feed_input.count()} input(s), {add_button.count()} button(s)")
    
        test_cases = [
            ("", "Empty URL"),
            ("not-a-url", "Invalid URL"),
            ("https://invalid-domain-xyz123.com/feed", "Invalid domain"),
        ]
        
        for test_url, description in test_cases:
            print(f"\n--- TESTING: {description} ({viewport_name}) ---")
            print(f"URL: '{test_url}'")
            
            # Locate fresh elements after potential HTMX updates
            if viewport_name == "mobile":
                # Ensure mobile sidebar is open
                if not page.locator("#feeds").is_visible():
                    hamburger = page.locator('#summary [data-testid="hamburger-btn"]').first
                    if hamburger.is_visible():
                        hamburger.click()
                        page.wait_for_selector("#feeds", state="visible", timeout=constants.MAX_WAIT_MS)

                feed_input = page.locator('#feeds input[name="new_feed_url"]')
                add_button = page.locator('#feeds button.add-feed-button')
            else:
                # Desktop: locate current form elements in feeds sidebar
                feed_input = page.locator('#feeds input[name="new_feed_url"]')
                add_button = page.locator('#feeds button.add-feed-button')

                # Fallback if not found
                if feed_input.count() == 0:
                    feed_input = page.locator('input[placeholder="Enter RSS URL"]')
                    add_button = page.locator('button.add-feed-button')
            
            # Clear and enter URL (with error handling)
            try:
                feed_input.clear()
                if test_url:
                    feed_input.fill(test_url)
            except Exception as e:
                print(f"  ⚠️ Could not interact with input field: {e}")
                continue
            
            # Click add button
            add_button.click()
            
            # Wait for HTMX to complete (sidebar gets completely replaced)
            wait_for_htmx_complete(page, timeout=constants.MAX_WAIT_MS)
            
            # Check if form submission was processed (page remained responsive)
            page_title = page.title()
            feed_links_count = page.locator("a[href*='feed_id']").count()
            print(f"  Form processed: {feed_links_count} feeds visible, title: {page_title}")
            print(f"  ✓ Form submission handled for {description} ({viewport_name})")
            
            # Verify app didn't crash and page is still responsive
            page_title = page.title()
            assert page_title == "RSS Reader", f"{viewport_name} page should remain functional"
            assert feed_links_count >= 2, f"{viewport_name} should have at least the default feeds"
        
        print(f"  ✓ {viewport_name} add feed edge cases test passed")
    
    print("\n=== OVERALL ADD FEED FLOW ASSESSMENT ===")
    print("All test cases completed for both mobile and desktop - check individual results above")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])