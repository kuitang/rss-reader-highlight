"""Simple test to verify the mobile form bar fix works"""

from playwright.sync_api import sync_playwright
import time

def test_mobile_fix():
    """Simple test to verify mobile form bar persistence fix"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8080")
        page.wait_for_timeout(5000)
        
        print("🧪 TESTING MOBILE FORM BAR FIX")
        print("=== STEP 1: Verify persistent header structure ===")
        
        # Check new persistent header exists
        persistent_header = page.locator("#mobile-persistent-header")
        print(f"✓ Persistent header found: {persistent_header.is_visible()}")
        
        # Check search form in persistent header  
        persistent_search = page.locator("#mobile-persistent-search")
        print(f"✓ Persistent search form found: {persistent_search.is_visible()}")
        
        # Check tabs in persistent header
        tabs = persistent_header.locator("li a[role='button']")
        print(f"✓ Navigation tabs found: {tabs.count()} tabs")
        
        print("=== STEP 2: Enter search text ===")
        search_text = "test persistence"
        persistent_search.fill(search_text)
        current_value = persistent_search.input_value()
        print(f"✓ Entered text: '{current_value}'")
        
        print("=== STEP 3: Navigate to article ===")
        first_article = page.locator('#main-content .js-filter li').first
        if first_article.is_visible():
            article_text = first_article.inner_text()
            article_title = article_text.split('\n')[0]
            print(f"✓ Clicking article: '{article_title[:50]}...'")
            
            first_article.click()
            page.wait_for_timeout(3000)
            
            # Check if article loaded
            article_content = page.locator('#main-content .prose')
            print(f"✓ Article loaded: {article_content.is_visible()}")
            
            print("=== STEP 4: Verify persistence after navigation ===")
            
            # CRITICAL TEST: Persistent header should still be there
            header_still_visible = persistent_header.is_visible()
            print(f"✓ Persistent header still visible: {header_still_visible}")
            
            # CRITICAL TEST: Search form should still be there
            search_still_visible = persistent_search.is_visible()  
            print(f"✓ Search form still visible: {search_still_visible}")
            
            # CRITICAL TEST: Search value should be preserved
            if search_still_visible:
                preserved_value = persistent_search.input_value()
                value_preserved = (preserved_value == search_text)
                print(f"✓ Search value preserved: {value_preserved} ('{preserved_value}')")
            else:
                print("❌ Cannot check search value - form not visible")
                
            # CRITICAL TEST: Tabs should still be there
            tabs_still_visible = tabs.first.is_visible() if tabs.count() > 0 else False
            print(f"✓ Navigation tabs still visible: {tabs_still_visible}")
            
            print("=== STEP 5: Test back navigation ===")
            back_button = page.locator('#mobile-header button[hx-get="/"]')
            if back_button.is_visible():
                back_button.click()
                page.wait_for_timeout(2000)
                print("✓ Clicked back button")
                
                # Check if back to list
                article_list = page.locator('#main-content .js-filter')
                print(f"✓ Back to article list: {article_list.is_visible()}")
                
                # Final persistence check
                final_header_visible = persistent_header.is_visible()
                final_search_visible = persistent_search.is_visible()
                final_search_value = persistent_search.input_value() if final_search_visible else ""
                final_value_preserved = (final_search_value == search_text)
                
                print(f"✓ Final header visible: {final_header_visible}")
                print(f"✓ Final search visible: {final_search_visible}")
                print(f"✓ Final search preserved: {final_value_preserved} ('{final_search_value}')")
                
                # Overall test result
                all_passed = (
                    header_still_visible and 
                    search_still_visible and 
                    value_preserved and 
                    tabs_still_visible and
                    final_header_visible and
                    final_search_visible and
                    final_value_preserved
                )
                
                if all_passed:
                    print("\n🎉 SUCCESS: Mobile form bar bug is FIXED!")
                    print("- ✅ Search form remains visible during navigation")
                    print("- ✅ Search state is preserved across article views") 
                    print("- ✅ Navigation tabs remain persistent")
                    print("- ✅ Back navigation works correctly")
                else:
                    print("\n❌ FAILURE: Some persistence checks failed")
                    
                return all_passed
            else:
                print("❌ Back button not found")
                return False
        else:
            print("❌ No articles found to test with")
            return False
        
        print("Keeping browser open for 10 seconds...")
        time.sleep(10)
        browser.close()

if __name__ == "__main__":
    success = test_mobile_fix()
    if success:
        print("\n✅ MOBILE FORM BAR BUG FIX VERIFIED!")
    else:
        print("\n❌ Fix verification failed")
    exit(0 if success else 1)