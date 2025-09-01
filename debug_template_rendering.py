"""Debug the template rendering to see why some items show markdown instead of HTML"""

from playwright.sync_api import sync_playwright
import time

def debug_template_rendering():
    """Check what's actually being rendered in the page vs what should be rendered"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8080")
        page.wait_for_timeout(5000)
        
        print("🔍 DEBUG: Template Rendering vs Expected Output")
        
        # Find items with markdown in the page
        feed_items = page.locator("#main-content .js-filter li")
        
        for i in range(min(20, feed_items.count())):
            item = feed_items.nth(i)
            item_html = item.inner_html()
            item_text = item.inner_text()
            
            # Check if this item has markdown syntax in the rendered page
            if '![' in item_html and '](' in item_html:
                title = item_text.split('\n')[0]
                print(f"\n❌ ITEM WITH RAW MARKDOWN: '{title[:50]}...'")
                
                # Extract the markdown part
                start = item_html.find('![')
                end = item_html.find(')', start) + 1
                if start != -1 and end != -1:
                    markdown_snippet = item_html[start:end]
                    print(f"   Raw markdown found: {markdown_snippet}")
                
                # Find the description div specifically
                desc_div = item.locator('div').filter(has_text='![')
                if desc_div.count() > 0:
                    desc_html = desc_div.first.inner_html()
                    print(f"   Description div HTML: {desc_html[:150]}...")
                    
                    # Check if this div has prose classes
                    desc_classes = desc_div.first.get_attribute('class')
                    print(f"   Description classes: '{desc_classes}'")
                    
                    # This tells us if the CSS styling is applied correctly
                    if 'prose' in (desc_classes or ''):
                        print("   ✅ Has prose styling - CSS should render markdown")
                    else:
                        print("   ❌ Missing prose styling - images won't render")
                
                break  # Just analyze the first problematic item
        
        print("\nBrowser staying open for inspection...")
        time.sleep(10)
        browser.close()

if __name__ == "__main__":
    debug_template_rendering()