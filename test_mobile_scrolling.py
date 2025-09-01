"""Test mobile scrolling functionality after the persistent header fix"""

from playwright.sync_api import sync_playwright
import time

def test_mobile_scrolling():
    """Test that mobile scrolling works properly with the new layout"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8080")
        page.wait_for_timeout(5000)
        
        print("📱 TESTING MOBILE SCROLLING")
        
        # Check initial scroll position
        initial_scroll = page.evaluate("document.querySelector('#main-content').scrollTop")
        print(f"✓ Initial scroll position: {initial_scroll}")
        
        # Get total content height vs viewport height
        content_height = page.evaluate("document.querySelector('#main-content').scrollHeight")
        viewport_height = page.evaluate("document.querySelector('#main-content').clientHeight")
        is_scrollable = content_height > viewport_height
        
        print(f"✓ Content height: {content_height}px")
        print(f"✓ Viewport height: {viewport_height}px") 
        print(f"✓ Is scrollable: {is_scrollable}")
        
        if is_scrollable:
            print("=== TESTING SCROLL BEHAVIOR ===")
            
            # Try to scroll down
            page.evaluate("document.querySelector('#main-content').scrollBy(0, 200)")
            page.wait_for_timeout(1000)
            
            # Check if scroll position changed
            after_scroll = page.evaluate("document.querySelector('#main-content').scrollTop")
            scroll_worked = after_scroll > initial_scroll
            
            print(f"✓ After scroll down: {after_scroll}")
            print(f"✓ Scroll worked: {scroll_worked}")
            
            if scroll_worked:
                # Try scrolling back up
                page.evaluate("document.querySelector('#main-content').scrollBy(0, -100)")
                page.wait_for_timeout(1000)
                
                final_scroll = page.evaluate("document.querySelector('#main-content').scrollTop")
                scroll_up_worked = final_scroll < after_scroll
                
                print(f"✓ After scroll up: {final_scroll}")
                print(f"✓ Scroll up worked: {scroll_up_worked}")
                
                # Test touch scrolling simulation
                print("=== TESTING TOUCH SCROLL SIMULATION ===")
                
                # Get a feed item to scroll with
                first_item = page.locator("#main-content .js-filter li").first
                if first_item.is_visible():
                    # Simulate touch scroll by dragging
                    item_box = first_item.bounding_box()
                    
                    # Start at middle of first item
                    start_x = item_box['x'] + item_box['width'] / 2
                    start_y = item_box['y'] + item_box['height'] / 2
                    
                    # Drag upward to scroll down
                    end_x = start_x
                    end_y = start_y - 150
                    
                    page.mouse.move(start_x, start_y)
                    page.mouse.down()
                    page.mouse.move(end_x, end_y)
                    page.mouse.up()
                    
                    page.wait_for_timeout(1000)
                    
                    touch_scroll_pos = page.evaluate("document.querySelector('#main-content').scrollTop")
                    touch_scroll_worked = touch_scroll_pos != final_scroll
                    
                    print(f"✓ After touch scroll: {touch_scroll_pos}")
                    print(f"✓ Touch scroll worked: {touch_scroll_worked}")
                    
                    return scroll_worked and scroll_up_worked and touch_scroll_worked
                else:
                    print("❌ No feed items found for touch scroll test")
                    return scroll_worked and scroll_up_worked
            else:
                print("❌ Basic scrolling failed")
                return False
        else:
            print("ℹ️ Content fits in viewport, no scrolling needed")
            return True
        
        print("Browser staying open for manual scroll testing...")
        time.sleep(15)
        browser.close()

if __name__ == "__main__":
    success = test_mobile_scrolling()
    if success:
        print("\n✅ MOBILE SCROLLING WORKS!")
    else:
        print("\n❌ Mobile scrolling is broken")
    exit(0 if success else 1)