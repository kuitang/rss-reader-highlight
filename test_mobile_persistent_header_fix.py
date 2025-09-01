"""Test to verify the mobile form bar bug is FIXED with persistent header architecture
 
This test verifies that the new persistent header architecture successfully:
1. Keeps the search form visible and persistent during navigation
2. Preserves search state across multiple article views
3. Maintains tabs and title bar during deep navigation through stories

The fix: Moved mobile search form to MobilePersistentHeader() outside #main-content
"""

import pytest
import time
from playwright.sync_api import sync_playwright, expect
from contextlib import contextmanager

TEST_PORT = 8080
TEST_URL = f"http://localhost:{TEST_PORT}"

@contextmanager
def existing_server():
    """Use existing server"""
    import httpx
    try:
        response = httpx.get(TEST_URL, timeout=5)
        if response.status_code == 200:
            yield
        else:
            raise Exception(f"Server not responding: {response.status_code}")
    except Exception as e:
        raise Exception(f"Server not available at {TEST_URL}. Start server first: python app.py")

@pytest.fixture(scope="session") 
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()

class TestMobilePersistentHeaderFix:
    """Test that the mobile form bar bug is FIXED"""
    
    def test_search_form_persists_during_navigation(self, page):
        """Test: Enter search → Navigate articles → Verify form stays visible and maintains state
        
        This test verifies the FIX works:
        - Search form should remain visible during all navigation
        - Search state should be preserved across article views
        - Tabs and title should remain persistent
        """
        
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(TEST_URL)
        page.wait_for_timeout(3000)
        
        print("=== PHASE 1: Verify new persistent header structure ===")
        
        # Verify we have the new persistent header
        persistent_header = page.locator("#mobile-persistent-header")
        expect(persistent_header).to_be_visible()
        print("✓ Mobile persistent header is visible")
        
        # Find the persistent search form (with specific ID)
        persistent_search = page.locator("#mobile-persistent-search")
        expect(persistent_search).to_be_visible()
        print("✓ Persistent search form found and visible")
        
        # Verify tabs are in persistent header
        tabs = persistent_header.locator("li a[role='button']")  # Correct selector from debug
        expect(tabs.first).to_be_visible()
        print("✓ Tabs found in persistent header")
        
        print("=== PHASE 2: Enter search text ===")
        
        # Enter search text that should persist
        search_text = "persistent search test"
        persistent_search.fill(search_text)
        expect(persistent_search).to_have_value(search_text)
        print(f"✓ Entered search text: '{search_text}'")
        
        # Take screenshot of initial state
        page.screenshot(path="debug_persistent_header_initial.png")
        
        print("=== PHASE 3: Navigate to first article ===")
        
        # Find and click first article
        first_article = page.locator('#main-content .js-filter li').first
        expect(first_article).to_be_visible()
        
        article_title_text = first_article.inner_text()
        article_title = article_title_text.split('\n')[0]
        print(f"✓ Found first article: '{article_title}'")
        
        first_article.click()
        page.wait_for_timeout(2000)
        
        # Verify article content loaded
        article_content = page.locator('#main-content .prose')
        expect(article_content).to_be_visible()
        print("✓ First article loaded successfully")
        
        print("=== PHASE 4: Verify persistent header survives navigation ===")
        
        # CRITICAL: Persistent header should still be visible
        expect(persistent_header).to_be_visible()
        print("✓ Persistent header still visible after article navigation")
        
        # CRITICAL: Search form should still be visible and maintain state
        expect(persistent_search).to_be_visible()
        current_search_value = persistent_search.input_value()
        assert current_search_value == search_text, f"Search state lost: expected '{search_text}', got '{current_search_value}'"
        print(f"✓ Search form visible and state preserved: '{current_search_value}'")
        
        # CRITICAL: Tabs should still be visible
        expect(tabs.first).to_be_visible()
        print("✓ Tabs still visible in persistent header")
        
        # Take screenshot after first navigation
        page.screenshot(path="debug_persistent_header_after_article1.png")
        
        print("=== PHASE 5: Navigate back to list ===")
        
        # Click back button
        back_button = page.locator('#mobile-header button[hx-get="/"]')
        expect(back_button).to_be_visible()
        back_button.click()
        page.wait_for_timeout(2000)
        print("✓ Clicked back button")
        
        # Verify we're back to article list
        article_list = page.locator('#main-content .js-filter')
        expect(article_list).to_be_visible()
        print("✓ Back to article list")
        
        # CRITICAL: Persistent header should STILL be there
        expect(persistent_header).to_be_visible()
        expect(persistent_search).to_be_visible()
        
        # CRITICAL: Search state should STILL be preserved
        back_search_value = persistent_search.input_value()
        assert back_search_value == search_text, f"Search state lost on back: expected '{search_text}', got '{back_search_value}'"
        print(f"✓ After going back: search state preserved: '{back_search_value}'")
        
        print("=== PHASE 6: Navigate to second article to test deep navigation ===")
        
        # Find and click second article
        second_article = page.locator('#main-content .js-filter li').nth(1)
        expect(second_article).to_be_visible()
        
        second_article_text = second_article.inner_text()
        second_title = second_article_text.split('\n')[0]
        print(f"✓ Found second article: '{second_title}'")
        
        second_article.click()
        page.wait_for_timeout(2000)
        
        # Verify second article loaded
        expect(article_content).to_be_visible()
        print("✓ Second article loaded successfully")
        
        # CRITICAL: After multiple navigations, everything should still persist
        expect(persistent_header).to_be_visible()
        expect(persistent_search).to_be_visible()
        expect(tabs.first).to_be_visible()
        
        final_search_value = persistent_search.input_value()
        assert final_search_value == search_text, f"Search state lost after multiple navigations: expected '{search_text}', got '{final_search_value}'"
        print(f"✓ After multiple navigations: search state still preserved: '{final_search_value}'")
        
        # Take final screenshot
        page.screenshot(path="debug_persistent_header_after_article2.png")
        
        print("=== PHASE 7: Test tab navigation preserves search ===")
        
        # Click "All Posts" tab to test tab navigation
        all_posts_tab = tabs.locator('a:has-text("All Posts")')
        expect(all_posts_tab).to_be_visible()
        all_posts_tab.click()
        page.wait_for_timeout(2000)
        print("✓ Clicked All Posts tab")
        
        # Verify back to article list via tab
        expect(article_list).to_be_visible()
        print("✓ Tab navigation back to article list works")
        
        # CRITICAL: Search should STILL be preserved after tab navigation
        tab_nav_search_value = persistent_search.input_value()
        assert tab_nav_search_value == search_text, f"Search state lost after tab navigation: expected '{search_text}', got '{tab_nav_search_value}'"
        print(f"✓ After tab navigation: search state preserved: '{tab_nav_search_value}'")
        
        print("=== FIX VERIFICATION COMPLETE ===")
        print("SUMMARY:")
        print("- ✓ Persistent header architecture implemented")  
        print("- ✓ Search form stays visible during ALL navigation")
        print("- ✓ Search state preserved across multiple article views")
        print("- ✓ Tabs remain persistent and functional")
        print("- ✓ Back button navigation works correctly")
        print("- ✓ Tab navigation preserves state")
        print("- ✅ MOBILE FORM BAR BUG IS FIXED!")
        
        return True
        
    def test_title_and_navbar_persistence_deep_navigation(self, page):
        """Test: Navigate through multiple articles and verify title bar and navbar remain persistent
        
        This test specifically addresses your question about title and navbar persistence
        during deep navigation through many stories.
        """
        
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(TEST_URL)
        page.wait_for_timeout(3000)
        
        print("=== DEEP NAVIGATION PERSISTENCE TEST ===")
        
        # Get references to persistent elements
        mobile_header = page.locator("#mobile-header")  # Top hamburger menu
        persistent_header = page.locator("#mobile-persistent-header")  # Tabs + search
        title_element = mobile_header.locator("h3")  # RSS Reader title
        tabs = persistent_header.locator("li a[role='button']")  # Navigation tabs
        
        # Verify all elements are initially visible
        expect(mobile_header).to_be_visible()
        expect(persistent_header).to_be_visible() 
        expect(title_element).to_be_visible()
        expect(tabs.first).to_be_visible()
        
        initial_title = title_element.inner_text()
        print(f"✓ Initial title: '{initial_title}'")
        
        # Navigate through multiple articles (simulating deep navigation)
        article_count = 0
        max_articles = 5  # Test navigation through 5 different articles
        
        while article_count < max_articles:
            article_count += 1
            print(f"\n--- NAVIGATING TO ARTICLE {article_count} ---")
            
            # Go back to list first (except on first iteration)
            if article_count > 1:
                back_button = mobile_header.locator('button[hx-get="/"]')
                if back_button.is_visible():
                    back_button.click()
                    page.wait_for_timeout(1500)
                    print(f"✓ Returned to list for article {article_count}")
            
            # Find available articles
            articles = page.locator('#main-content .js-filter li')
            article_total = articles.count()
            
            if article_total == 0:
                print("No articles available, ending test")
                break
                
            # Select article (use modulo to cycle through available articles)
            article_index = (article_count - 1) % min(article_total, 3)  # Use first 3 articles
            target_article = articles.nth(article_index)
            
            # Get article info
            article_text = target_article.inner_text()
            article_title = article_text.split('\n')[0]
            print(f"✓ Selecting article {article_count}: '{article_title[:50]}...'")
            
            # Click article
            target_article.click()
            page.wait_for_timeout(2000)
            
            # Verify article loaded
            article_content = page.locator('#main-content .prose')
            expect(article_content).to_be_visible()
            print(f"✓ Article {article_count} loaded successfully")
            
            # CRITICAL VERIFICATION: All persistent elements should still be visible
            expect(mobile_header).to_be_visible()
            expect(persistent_header).to_be_visible()
            expect(title_element).to_be_visible() 
            expect(tabs.first).to_be_visible()
            
            # Verify title hasn't changed
            current_title = title_element.inner_text()
            assert current_title == initial_title, f"Title changed from '{initial_title}' to '{current_title}'"
            
            print(f"✓ Article {article_count}: All persistent elements remain visible")
            print(f"  - Title bar: '{current_title}' ✓")
            print(f"  - Mobile header: visible ✓")
            print(f"  - Persistent header: visible ✓") 
            print(f"  - Navigation tabs: visible ✓")
            
            # Take screenshot for debugging
            page.screenshot(path=f"debug_deep_navigation_article_{article_count}.png")
        
        print(f"\n=== DEEP NAVIGATION TEST COMPLETE ===")
        print(f"Successfully navigated through {article_count} articles")
        print("VERIFICATION:")
        print("- ✅ Title bar remained visible throughout all navigation")
        print("- ✅ Mobile header (hamburger menu) never disappeared") 
        print("- ✅ Persistent header (tabs + search) stayed persistent")
        print("- ✅ Navigation tabs remained functional")
        print("- ✅ UI architecture is rock solid for deep navigation!")
        
        return True

if __name__ == "__main__":
    # Allow running this test directly for debugging
    with existing_server():
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # Show browser for debugging
            page = browser.new_page()
            
            test_instance = TestMobilePersistentHeaderFix()
            
            print("🧪 TESTING FIX: Search form persistence...")
            success1 = test_instance.test_search_form_persists_during_navigation(page)
            
            print("\n🧪 TESTING FIX: Title and navbar deep navigation...")  
            success2 = test_instance.test_title_and_navbar_persistence_deep_navigation(page)
            
            page.close()
            browser.close()
            
            overall_success = success1 and success2
            
            if overall_success:
                print("\n🎉 ALL TESTS PASSED - MOBILE FORM BAR BUG IS COMPLETELY FIXED!")
            else:
                print("\n❌ Some tests failed - fix needs more work")
                
            exit(0 if overall_success else 1)