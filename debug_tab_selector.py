"""Debug the tab selector issue"""

from playwright.sync_api import sync_playwright
import time

def debug_tab_selector():
    """Debug what's happening with tab selector"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  
        page = browser.new_page()
        
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8080")
        page.wait_for_timeout(5000)
        
        print("=== DEBUG: Tab Selector Analysis ===")
        
        # Check persistent header
        persistent_header = page.locator("#mobile-persistent-header")
        print(f"Persistent header exists: {persistent_header.count()}")
        print(f"Persistent header visible: {persistent_header.is_visible()}")
        
        # Check what's actually inside the persistent header
        if persistent_header.count() > 0:
            header_html = persistent_header.inner_html()
            print(f"Header HTML: {header_html[:500]}...")
            
        # Try different tab selectors
        selectors = [
            ".uk-tab",
            "[uk-tab]", 
            ".uk-tab li",
            "ul.uk-tab",
            "[role='tablist']",
            "li a[role='button']"
        ]
        
        for selector in selectors:
            elements = persistent_header.locator(selector)
            count = elements.count()
            print(f"Selector '{selector}': found {count} elements")
            
            if count > 0:
                try:
                    visible = elements.first.is_visible()
                    text = elements.first.inner_text()
                    print(f"  First element visible: {visible}, text: '{text}'")
                except:
                    print(f"  Could not get visibility/text")
        
        # Take screenshot
        page.screenshot(path="debug_tab_selector.png")
        
        print("Browser will stay open for 10 seconds...")
        time.sleep(10)
        
        browser.close()

if __name__ == "__main__":
    debug_tab_selector()