"""Test to debug the add feed flow and identify what's broken"""

from playwright.sync_api import sync_playwright
import time

def test_add_feed_flow():
    """Debug the add feed flow step by step"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Set mobile viewport to test mobile add feed flow
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8080")
        page.wait_for_timeout(5000)
        
        print("🔧 DEBUGGING ADD FEED FLOW")
        
        print("=== STEP 1: Open mobile sidebar ===")
        
        # Find and click hamburger menu 
        hamburger_button = page.locator('#mobile-header button[onclick*="mobile-sidebar"]')
        if hamburger_button.is_visible():
            hamburger_button.click()
            page.wait_for_timeout(1000)
            print("✓ Clicked hamburger menu")
        else:
            print("❌ Hamburger menu not found")
            browser.close()
            return False
            
        # Verify sidebar opened
        sidebar = page.locator("#mobile-sidebar")
        sidebar_visible = not sidebar.get_attribute("hidden")
        print(f"✓ Sidebar visible: {sidebar_visible}")
        
        if not sidebar_visible:
            print("❌ Sidebar did not open")
            browser.close()
            return False
        
        print("=== STEP 2: Find add feed form ===")
        
        # Look for the add feed input in sidebar
        feed_input = page.locator('#mobile-sidebar input[placeholder*="RSS"]')
        input_found = feed_input.is_visible()
        print(f"✓ Feed input found: {input_found}")
        
        if input_found:
            input_name = feed_input.get_attribute("name")
            input_id = feed_input.get_attribute("id")
            print(f"✓ Input attributes: name='{input_name}', id='{input_id}'")
        
        # Look for the add button
        add_button = page.locator('#mobile-sidebar button[hx-post="/api/feed/add"]')
        button_found = add_button.is_visible()
        print(f"✓ Add button found: {button_found}")
        
        if button_found:
            button_include = add_button.get_attribute("hx-include")
            button_target = add_button.get_attribute("hx-target")
            print(f"✓ Button attributes: hx-include='{button_include}', hx-target='{button_target}'")
        
        print("=== STEP 3: Test adding a feed ===")
        
        if input_found and button_found:
            # Enter a test RSS URL
            test_url = "https://httpbin.org/xml"
            feed_input.fill(test_url)
            print(f"✓ Entered test URL: {test_url}")
            
            # Take screenshot before clicking
            page.screenshot(path="debug_add_feed_before.png")
            
            # Click add button
            add_button.click()
            print("✓ Clicked add button")
            
            # Wait for response
            page.wait_for_timeout(5000)
            
            # Take screenshot after clicking
            page.screenshot(path="debug_add_feed_after.png")
            
            # Check for any error messages or success indicators
            error_text = page.locator('text="Error"').first
            success_text = page.locator('text="successful"').first
            
            has_error = error_text.is_visible() if error_text else False
            has_success = success_text.is_visible() if success_text else False
            
            print(f"✓ Error visible: {has_error}")
            print(f"✓ Success visible: {has_success}")
            
            # Check if feed was added to sidebar
            new_feed_item = page.locator('#mobile-sidebar a[href*="feed_id"]').last
            feed_added = new_feed_item.is_visible() if new_feed_item else False
            print(f"✓ New feed item visible: {feed_added}")
            
            # Check console for any JavaScript errors
            console_messages = []
            page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
            
            print("=== STEP 4: Check for issues ===")
            
            if console_messages:
                print("Console messages:")
                for msg in console_messages:
                    print(f"  {msg}")
            else:
                print("✓ No console errors")
                
            # Overall assessment
            if has_error:
                print("❌ ADD FEED FLOW HAS ERRORS")
                return False
            elif feed_added or has_success:
                print("✅ ADD FEED FLOW WORKING")
                return True
            else:
                print("⚠️ ADD FEED FLOW: Unclear result")
                return False
        else:
            print("❌ Cannot test - missing form elements")
            return False
        
        print("Browser staying open for inspection...")
        time.sleep(10)
        browser.close()

if __name__ == "__main__":
    success = test_add_feed_flow()
    if success:
        print("\n✅ Add feed flow is working")
    else:
        print("\n❌ Add feed flow has issues")
    exit(0 if success else 1)