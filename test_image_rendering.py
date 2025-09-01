"""Test to verify image rendering works correctly in feed listings after the fix"""

from playwright.sync_api import sync_playwright
import time

def test_image_rendering():
    """Test that images render correctly in feed listings"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Set desktop viewport to check both layouts
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto("http://localhost:8080")
        page.wait_for_timeout(5000)
        
        print("🖼️ TESTING IMAGE RENDERING IN FEED LISTINGS")
        
        # Test desktop layout first
        print("=== DESKTOP LAYOUT TEST ===")
        desktop_layout = page.locator("#desktop-layout")
        if desktop_layout.is_visible():
            print("✓ Desktop layout active")
            
            # Look for images in desktop feed listings
            desktop_feed_items = page.locator("#desktop-feeds-content .js-filter li")
            desktop_item_count = desktop_feed_items.count()
            print(f"✓ Found {desktop_item_count} desktop feed items")
            
            # Check for images in desktop listings
            desktop_images = page.locator("#desktop-feeds-content .js-filter img")
            desktop_image_count = desktop_images.count()
            print(f"✓ Found {desktop_image_count} images in desktop feed listings")
            
            if desktop_image_count > 0:
                # Check first image properties
                first_desktop_img = desktop_images.first
                img_src = first_desktop_img.get_attribute('src')
                img_alt = first_desktop_img.get_attribute('alt')
                img_visible = first_desktop_img.is_visible()
                print(f"✓ First desktop image: visible={img_visible}, src='{img_src[:50]}...', alt='{img_alt}'")
                
                # Check if image has proper responsive styling
                img_classes = first_desktop_img.get_attribute('class') or ""
                print(f"✓ Desktop image classes: '{img_classes}'")
        
        # Test mobile layout
        print("\n=== MOBILE LAYOUT TEST ===")
        page.set_viewport_size({"width": 375, "height": 667})
        page.wait_for_timeout(2000)
        
        # Look for images in mobile feed listings  
        mobile_feed_items = page.locator("#main-content .js-filter li")
        mobile_item_count = mobile_feed_items.count()
        print(f"✓ Found {mobile_item_count} mobile feed items")
        
        # Check for images in mobile listings
        mobile_images = page.locator("#main-content .js-filter img")
        mobile_image_count = mobile_images.count()
        print(f"✓ Found {mobile_image_count} images in mobile feed listings")
        
        if mobile_image_count > 0:
            # Check first image properties
            first_mobile_img = mobile_images.first
            img_src = first_mobile_img.get_attribute('src')
            img_alt = first_mobile_img.get_attribute('alt')
            img_visible = first_mobile_img.is_visible()
            print(f"✓ First mobile image: visible={img_visible}, src='{img_src[:50]}...', alt='{img_alt}'")
            
            # Check responsive behavior
            img_width = first_mobile_img.bounding_box()['width']
            viewport_width = 375
            is_responsive = img_width <= viewport_width
            print(f"✓ Mobile image responsive: {is_responsive} (width: {img_width}px vs viewport: {viewport_width}px)")
        
        # Test clicking an item with image to verify detail view
        print("\n=== DETAIL VIEW IMAGE TEST ===")
        if mobile_feed_items.count() > 0:
            first_item = mobile_feed_items.first
            first_item.click()
            page.wait_for_timeout(3000)
            
            # Check for images in detail view
            detail_images = page.locator("#main-content .prose img")
            detail_image_count = detail_images.count()
            print(f"✓ Found {detail_image_count} images in article detail view")
            
            if detail_image_count > 0:
                detail_img = detail_images.first
                detail_img_visible = detail_img.is_visible()
                detail_img_src = detail_img.get_attribute('src')
                print(f"✓ Detail view image: visible={detail_img_visible}, src='{detail_img_src[:50]}...'")
        
        # Take screenshots for visual verification
        page.screenshot(path="debug_image_rendering_mobile.png")
        print("✓ Screenshot saved: debug_image_rendering_mobile.png")
        
        # Switch back to desktop for desktop screenshot
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto("http://localhost:8080")  # Refresh to desktop layout
        page.wait_for_timeout(3000)
        page.screenshot(path="debug_image_rendering_desktop.png")
        print("✓ Screenshot saved: debug_image_rendering_desktop.png")
        
        # Summary
        total_images = desktop_image_count + mobile_image_count + detail_image_count
        print(f"\n📊 IMAGE RENDERING SUMMARY:")
        print(f"   Desktop listings: {desktop_image_count} images")
        print(f"   Mobile listings: {mobile_image_count} images")
        print(f"   Detail view: {detail_image_count} images")
        print(f"   Total images found: {total_images}")
        
        if total_images > 0:
            print("✅ Images are being rendered in the application!")
        else:
            print("❌ No images found - may need to check feed data or styling")
        
        print("Keeping browser open for 10 seconds for manual inspection...")
        time.sleep(10)
        browser.close()
        
        return total_images > 0

if __name__ == "__main__":
    success = test_image_rendering()
    if success:
        print("\n🎉 IMAGE RENDERING TEST PASSED!")
    else:
        print("\n❌ Image rendering needs investigation")
    exit(0 if success else 1)