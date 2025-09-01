"""Test to reproduce and debug the mobile form bar bug
 
The bug: Mobile scrolling fix breaks form bar preservation when clicking articles.
When you click an item, the search form gets scrolled/lost, then that part gets lost.

This test will:
1. Navigate to mobile view and verify search form exists
2. Enter text in the search form to create state 
3. Click an article to view details
4. Verify the search form is lost/replaced
5. Use back button to return to list
6. Verify search state is completely reset
"""

import pytest
import time
from playwright.sync_api import sync_playwright, expect
from contextlib import contextmanager

TEST_PORT = 8080
TEST_URL = f"http://localhost:{TEST_PORT}"

@contextmanager
def existing_server():
    """Use existing server - matches pattern from test_critical_ui_flows.py"""
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

class TestMobileFormBarBug:
    """Test the mobile form bar bug we need to debug"""
    
    def test_mobile_search_form_persistence_bug(self, page):
        """Test: Enter search text → Click article → Verify form is lost → Go back → Verify state reset
        
        This demonstrates the core bug: mobile scrolling fix's content replacement 
        strategy breaks search form state persistence.
        
        Expected behavior: Search form should persist and maintain state
        Actual behavior: Search form gets replaced and state is lost
        """
        
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(TEST_URL)
        page.wait_for_timeout(3000)
        
        print("=== PHASE 1: Verify initial mobile layout ===")
        
        # Verify we're in mobile mode (desktop should be hidden, mobile content working)
        desktop_layout = page.locator("#desktop-layout")
        mobile_content = page.locator("#main-content")
        
        expect(desktop_layout).to_be_hidden()
        # Note: mobile_content has overflow:hidden, so check for content instead
        expect(mobile_content).to_contain_text("All Feeds")
        
        print("✓ Mobile layout confirmed - desktop hidden, mobile content visible")
        
        # Find the visible search form - there are 2 inputs, we want the visible one
        search_inputs = page.locator('input[placeholder="Search posts"]')
        visible_search = None
        
        # Find the visible search input (debug showed there are 2)
        for i in range(search_inputs.count()):
            input_elem = search_inputs.nth(i) 
            if input_elem.is_visible():
                visible_search = input_elem
                break
        
        if not visible_search:
            raise Exception("No visible search input found")
            
        print("✓ Found visible search form in mobile content")
        
        print("=== PHASE 2: Enter search text to create state ===")
        
        # Enter some search text to create state that should be preserved
        search_text = "test search query"
        visible_search.fill(search_text)
        
        # Verify the text was entered
        expect(visible_search).to_have_value(search_text)
        print(f"✓ Entered search text: '{search_text}'")
        
        # Take screenshot of initial state for debugging
        page.screenshot(path="debug_mobile_initial_state.png")
        
        print("=== PHASE 3: Click article to trigger bug ===")
        
        # Find first article in the mobile feeds list
        # Based on FeedItem structure, articles should be Li elements with hx_target="#main-content"
        first_article = page.locator('#main-content .js-filter li').first
        expect(first_article).to_be_visible()
        
        article_title_text = first_article.inner_text()
        article_title = article_title_text.split('\n')[0]  # Get first line as title
        print(f"✓ Found first article: '{article_title}'")
        
        # Click the article - this should trigger the bug
        first_article.click()
        page.wait_for_timeout(2000)  # Wait for HTMX to complete
        
        print("✓ Clicked article, waiting for content to load...")
        
        # Take screenshot after click
        page.screenshot(path="debug_mobile_after_click.png")
        
        print("=== PHASE 4: Verify bug - search form should be lost ===")
        
        # Check if we're now in article detail view
        # The content should have changed to ItemDetailView
        try:
            # Look for article content indicators
            article_content = page.locator('#main-content .prose') # ItemDetailView uses prose class
            expect(article_content).to_be_visible()
            print("✓ Article detail view loaded")
        except:
            print("❌ Article detail view not detected - possible navigation issue")
            
        # CRITICAL TEST: Search form should be gone (this is the bug)
        search_inputs_after = page.locator('input[placeholder="Search posts"]')
        visible_search_after = None
        
        # Check if any search input is still visible
        for i in range(search_inputs_after.count()):
            input_elem = search_inputs_after.nth(i)
            if input_elem.is_visible():
                visible_search_after = input_elem
                break
        
        if visible_search_after:
            print("❌ BUG NOT REPRODUCED: Search form still visible (unexpected)")
            return False
        else:
            print("✓ BUG CONFIRMED: Search form is lost after clicking article")
            
        print("=== PHASE 5: Go back and verify state reset ===")
        
        # Look for back button and click it
        back_button = page.locator('#mobile-header button[hx-get="/"]')
        expect(back_button).to_be_visible()
        back_button.click()
        page.wait_for_timeout(2000)
        
        print("✓ Clicked back button, returning to list")
        
        # Take screenshot after going back
        page.screenshot(path="debug_mobile_after_back.png")
        
        # Verify search form is back but state is reset
        search_inputs_restored = page.locator('input[placeholder="Search posts"]')
        visible_search_restored = None
        
        # Find the visible search input again
        for i in range(search_inputs_restored.count()):
            input_elem = search_inputs_restored.nth(i)
            if input_elem.is_visible():
                visible_search_restored = input_elem
                break
        
        if not visible_search_restored:
            print("❌ Search form not restored after going back")
            return False
            
        print("✓ Search form restored after going back")
        
        # CRITICAL TEST: Search state should be lost (demonstrating the bug)
        current_value = visible_search_restored.input_value()
        if current_value == search_text:
            print("❌ BUG NOT REPRODUCED: Search state preserved (unexpected)")
            return False
        else:
            print(f"✓ BUG CONFIRMED: Search state lost - was '{search_text}', now '{current_value}'")
            
        print("=== BUG REPRODUCTION COMPLETE ===")
        print("SUMMARY:")
        print("- ✓ Search form exists initially")  
        print("- ✓ Search text can be entered")
        print("- ✓ Clicking article replaces entire content (loses form)")
        print("- ✓ Going back restores form but loses state")
        print("- ✓ This confirms the mobile form bar bug")
        
        return True
        
    def test_mobile_form_bar_scroll_position_bug(self, page):
        """Test the scroll position aspect of the bug
        
        Additional test: When clicking items, does the form bar get scrolled 
        out of view due to the mobile viewport fixes?
        """
        
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(TEST_URL)
        page.wait_for_timeout(3000)
        
        print("=== TESTING SCROLL POSITION BEHAVIOR ===")
        
        # Get initial scroll position and form position
        initial_scroll = page.evaluate("window.pageYOffset")
        print(f"Initial scroll position: {initial_scroll}")
        
        # Find search form
        search_input = page.locator('#main-content input[placeholder="Search posts"]')
        expect(search_input).to_be_visible()
        
        # Get form position in viewport
        form_box = search_input.bounding_box()
        print(f"Search form position: top={form_box['y']}, visible={form_box['y'] >= 0 and form_box['y'] < 667}")
        
        # Click article
        first_article = page.locator('#main-content .js-filter li').first
        first_article.click()
        page.wait_for_timeout(2000)
        
        # Check scroll behavior after click
        after_click_scroll = page.evaluate("window.pageYOffset") 
        print(f"Scroll position after click: {after_click_scroll}")
        
        # This test helps us understand if scrolling is part of the issue
        if after_click_scroll != initial_scroll:
            print("✓ Scroll position changed - this may contribute to form bar loss")
        else:
            print("✓ Scroll position unchanged - bug is purely content replacement")
            
        return True

if __name__ == "__main__":
    # Allow running this test directly for debugging
    with existing_server():
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # Show browser for debugging
            page = browser.new_page()
            
            test_instance = TestMobileFormBarBug()
            success = test_instance.test_mobile_search_form_persistence_bug(page)
            
            page.close()
            browser.close()
            
            if success:
                print("\n🎉 BUG SUCCESSFULLY REPRODUCED - Ready to fix!")
            else:
                print("\n❌ Could not reproduce bug - investigate further")
                
            exit(0 if success else 1)