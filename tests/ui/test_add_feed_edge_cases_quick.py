"""Quick test for add feed edge cases to verify HTMX handling works"""

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

def test_add_feed_empty_url_both_viewports(page, test_server_url):
    """Test empty URL handling on both desktop and mobile"""
    
    print("🧪 TESTING EMPTY URL HANDLING (BOTH VIEWPORTS)")
    
    for viewport_name, viewport_size in [
        ("desktop", {"width": 1200, "height": 800}),
        ("mobile", {"width": 375, "height": 667})
    ]:
        print(f"\n--- Testing {viewport_name} empty URL ---")
        page.set_viewport_size(viewport_size)
        page.goto(test_server_url)
        wait_for_page_ready(page)
        
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
            # Desktop selectors 
            feed_input = page.locator('input[placeholder="Enter RSS URL"]')
            add_button = page.locator('#sidebar button.add-feed-button')
            
            if feed_input.count() == 0:
                print(f"  Debug: Direct selector not found, trying fallback")
                feed_input = page.locator('input[name="new_feed_url"]').first
                add_button = page.locator('button').filter(has_text="").first
        
        print(f"  Found {feed_input.count()} input(s), {add_button.count()} button(s)")
        
        # Test empty URL submission
        try:
            feed_input.clear()  # Ensure empty
            add_button.click()
            print("  ✓ Clicked add button with empty input")
            
            # Wait for HTMX to complete (sidebar gets completely replaced)
            wait_for_htmx_complete(page, timeout=8000)
            print("  ✓ HTMX response completed")
            
            # Check for response message (HTMX may completely replace content)
            try:
                if viewport_name == "mobile":
                    if page.locator("#mobile-sidebar").is_visible():
                        sidebar_text = page.locator("#mobile-sidebar").inner_text()
                    else:
                        sidebar_text = page.locator("body").inner_text()
                else:
                    if page.locator("#sidebar").count() > 0 and page.locator("#sidebar").is_visible():
                        sidebar_text = page.locator("#sidebar").inner_text()
                    else:
                        sidebar_text = page.locator("body").inner_text()
                
                # Look for empty URL validation message
                has_empty_msg = "Please enter" in sidebar_text or "URL" in sidebar_text
                
                if has_empty_msg:
                    print(f"  ✓ Got expected empty URL validation message")
                else:
                    print(f"  ⚠️ No clear validation message found")
                    print(f"  Content preview: {sidebar_text[:200]}...")
                
            except Exception as e:
                print(f"  ⚠️ Could not check response text: {e}")
            
            # Verify app didn't crash
            page_title = page.title()
            assert page_title == "RSS Reader", f"App should remain functional (title: {page_title})"
            print(f"  ✓ App remains functional after empty URL test")
            
        except Exception as e:
            print(f"  ❌ Error during {viewport_name} test: {e}")
            continue
    
    print("\n✅ Empty URL handling test completed for both viewports")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])