"""Test desktop add feed flow to isolate the issue"""

from playwright.sync_api import sync_playwright
import time

def test_desktop_add_feed():
    """Test desktop add feed to see if issue is mobile-specific"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Set desktop viewport
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto("http://localhost:8080")
        page.wait_for_timeout(5000)
        
        print("🖥️ TESTING DESKTOP ADD FEED FLOW")
        
        # Find desktop add feed form
        desktop_input = page.locator('#sidebar input[name="new_feed_url"]')
        desktop_button = page.locator('#sidebar button[hx-post="/api/feed/add"]')
        
        input_visible = desktop_input.is_visible()
        button_visible = desktop_button.is_visible()
        
        print(f"✓ Desktop input visible: {input_visible}")
        print(f"✓ Desktop button visible: {button_visible}")
        
        if input_visible and button_visible:
            # Check button configuration
            button_include = desktop_button.get_attribute("hx-include")
            button_target = desktop_button.get_attribute("hx-target")
            
            print(f"✓ Button hx-include: '{button_include}'")
            print(f"✓ Button hx-target: '{button_target}'")
            
            # Test with a valid RSS feed
            test_url = "https://feeds.feedburner.com/oreilly/radar"
            desktop_input.fill(test_url)
            print(f"✓ Entered URL: {test_url}")
            
            # Click and wait
            desktop_button.click()
            page.wait_for_timeout(5000)  # Wait longer for network request
            
            # Check server logs vs what we see in page
            page.screenshot(path="debug_desktop_add_feed.png")
            
            return True
        else:
            print("❌ Desktop form elements not found")
            return False
        
        browser.close()

if __name__ == "__main__":
    test_desktop_add_feed()