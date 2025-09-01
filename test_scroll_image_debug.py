"""Debug image rendering by scrolling through many feed items to find patterns"""

from playwright.sync_api import sync_playwright
import time

def test_scroll_and_debug_images():
    """Scroll through feed items and debug image rendering patterns"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Set mobile viewport 
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8080")
        page.wait_for_timeout(5000)
        
        print("🔍 SCROLLING DEBUG: Image Rendering Patterns")
        
        # Get initial feed container
        feed_container = page.locator("#main-content .js-filter")
        
        # Count pages to scroll through
        page_count = 0
        max_pages = 5  # Scroll through multiple pages
        
        total_items_checked = 0
        items_with_images = 0
        items_with_markdown = 0
        items_with_html_tables = 0
        
        while page_count < max_pages:
            page_count += 1
            print(f"\n--- PAGE {page_count} ---")
            
            # Get current feed items
            feed_items = page.locator("#main-content .js-filter li")
            current_page_items = feed_items.count()
            print(f"Items on page {page_count}: {current_page_items}")
            
            # Analyze each item on this page
            for i in range(current_page_items):
                item = feed_items.nth(i)
                total_items_checked += 1
                
                # Get item HTML to analyze content structure
                item_html = item.inner_html()
                
                # Check for different content patterns
                has_img_tag = '<img' in item_html
                has_markdown_syntax = '![' in item_html and '](' in item_html  
                has_table_structure = '<table>' in item_html
                
                if has_img_tag:
                    items_with_images += 1
                    
                if has_markdown_syntax:
                    items_with_markdown += 1
                    
                if has_table_structure:
                    items_with_html_tables += 1
                
                # Get item title for reference
                item_text = item.inner_text()
                item_title = item_text.split('\n')[0][:50]
                
                # Report interesting cases
                if has_img_tag or has_markdown_syntax:
                    print(f"  Item {total_items_checked}: '{item_title}...'")
                    print(f"    - Has <img> tag: {has_img_tag}")
                    print(f"    - Has markdown ![]: {has_markdown_syntax}")
                    print(f"    - Has <table>: {has_table_structure}")
                    
                    if has_img_tag:
                        # Extract image info
                        img_element = item.locator('img').first
                        if img_element.is_visible():
                            img_src = img_element.get_attribute('src')
                            img_alt = img_element.get_attribute('alt')
                            print(f"    - Image: '{img_alt}' src='{img_src[:50]}...'")
            
            # Try to go to next page
            next_button = page.locator('button:has-text("›")')  # Next page button
            if next_button.is_visible():
                print(f"  ↓ Scrolling to page {page_count + 1}")
                next_button.click()
                page.wait_for_timeout(3000)
            else:
                print(f"  ⏹ No more pages available")
                break
        
        print(f"\n📊 SCROLL DEBUG SUMMARY:")
        print(f"  Total items analyzed: {total_items_checked}")
        print(f"  Items with <img> tags: {items_with_images} ({items_with_images/total_items_checked*100:.1f}%)")
        print(f"  Items with markdown ![]: {items_with_markdown} ({items_with_markdown/total_items_checked*100:.1f}%)")
        print(f"  Items with <table> HTML: {items_with_html_tables} ({items_with_html_tables/total_items_checked*100:.1f}%)")
        
        # Analysis
        print(f"\n🔍 PATTERN ANALYSIS:")
        if items_with_images > 0 and items_with_markdown > 0:
            print(f"  ❌ MIXED FORMAT ISSUE: Both rendered images AND raw markdown found")
            print(f"  🔧 CAUSE: Inconsistent processing in smart_truncate_html function")
        elif items_with_images > 0:
            print(f"  ✅ IMAGES WORKING: All image content is rendering properly")
        elif items_with_markdown > 0:
            print(f"  ❌ MARKDOWN NOT RENDERING: Images stuck in markdown format")
        else:
            print(f"  ℹ️ NO IMAGES: This batch of feed items doesn't contain images")
            
        if items_with_html_tables > 0:
            print(f"  📋 HTML TABLES: {items_with_html_tables} items use table-based layout")
            print(f"      → This indicates RSS feeds contain pre-formatted HTML")
        
        print("Browser staying open for manual inspection...")
        time.sleep(15)
        browser.close()
        
        return {
            'total_items': total_items_checked,
            'items_with_images': items_with_images,
            'items_with_markdown': items_with_markdown,
            'items_with_tables': items_with_html_tables
        }

if __name__ == "__main__":
    results = test_scroll_and_debug_images()
    
    if results['items_with_markdown'] > 0:
        print(f"\n❌ ISSUE CONFIRMED: {results['items_with_markdown']} items have unrendered markdown")
        print("Need to fix smart_truncate_html function")
    else:
        print(f"\n✅ NO ISSUES FOUND: All {results['items_with_images']} images rendering correctly")
    
    exit(0)