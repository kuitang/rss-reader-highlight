"""Test add feed flow edge cases to find what's broken"""

from playwright.sync_api import sync_playwright
import time

def test_add_feed_edge_cases():
    """Test various add feed scenarios to find issues"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8080")
        page.wait_for_timeout(5000)
        
        print("🧪 TESTING ADD FEED EDGE CASES")
        
        # Open sidebar
        hamburger = page.locator('#mobile-header button[onclick*="mobile-sidebar"]')
        hamburger.click()
        page.wait_for_timeout(1000)
        
        feed_input = page.locator('#mobile-sidebar input[name="new_feed_url"]')
        add_button = page.locator('#mobile-sidebar button[hx-post="/api/feed/add"]')
        
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
            page.wait_for_timeout(3000)
            
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
        
        print("Browser staying open for manual testing...")
        time.sleep(15)
        browser.close()

if __name__ == "__main__":
    test_add_feed_edge_cases()