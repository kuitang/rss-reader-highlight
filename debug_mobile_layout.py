"""Debug script to understand the mobile layout issue"""

from playwright.sync_api import sync_playwright
import time

def debug_mobile_layout():
    """Debug what's happening with mobile layout"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Show browser 
        page = browser.new_page()
        
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8080")
        page.wait_for_timeout(5000)  # Wait for full load
        
        print("=== DEBUG: Mobile Layout Analysis ===")
        
        # Check all main layout elements
        desktop_layout = page.locator("#desktop-layout")
        mobile_content = page.locator("#main-content")
        mobile_header = page.locator("#mobile-header")
        
        print(f"Desktop layout exists: {desktop_layout.count()}")
        print(f"Desktop layout visible: {desktop_layout.is_visible()}")
        
        print(f"Mobile content exists: {mobile_content.count()}")
        print(f"Mobile content visible: {mobile_content.is_visible()}")
        print(f"Mobile content classes: {mobile_content.get_attribute('class')}")
        
        print(f"Mobile header exists: {mobile_header.count()}")
        print(f"Mobile header visible: {mobile_header.is_visible()}")
        
        # Take screenshot
        page.screenshot(path="debug_mobile_layout.png")
        
        # Check what content is actually visible
        visible_text = page.locator("body").inner_text()
        print(f"Visible text preview: {visible_text[:200]}...")
        
        # Check for search input specifically
        search_inputs = page.locator('input[placeholder*="Search"]')
        print(f"Found {search_inputs.count()} search inputs")
        
        if search_inputs.count() > 0:
            for i in range(search_inputs.count()):
                input_elem = search_inputs.nth(i)
                print(f"  Search input {i}: visible={input_elem.is_visible()}, placeholder='{input_elem.get_attribute('placeholder')}'")
        
        # Wait to examine manually if needed
        print("Browser will stay open for 10 seconds for manual inspection...")
        time.sleep(10)
        
        browser.close()

if __name__ == "__main__":
    debug_mobile_layout()