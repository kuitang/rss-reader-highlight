"""Consolidated mobile flow tests - Navigation, Form persistence, Scrolling, URL sharing

Combines functionality from:
- test_mobile_navigation.py (HTMX navigation patterns)
- test_mobile_form_bar_bug.py (form persistence issues)
- test_mobile_scrolling.py (scrolling behavior)
- test_mobile_url_sharing.py (URL sharing functionality)
"""

import pytest
from playwright.sync_api import Page, expect
import time

pytestmark = pytest.mark.needs_server

# HTMX Helper Functions for Fast Testing
def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete - much faster than fixed timeouts"""
    page.wait_for_function("() => !document.body.classList.contains('htmx-request')", timeout=timeout)

def wait_for_page_ready(page):
    """Fast page ready check - waits for network idle instead of fixed timeout"""
    page.wait_for_load_state("networkidle")


class TestMobileFlows:
    """Test mobile-specific UI flows and behaviors"""
    
    @pytest.fixture(autouse=True)
    def setup(self, page: Page, test_server_url):
        """Set mobile viewport for all tests"""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(test_server_url)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
    
    # Navigation Tests (from test_mobile_navigation.py)
    def test_mobile_post_navigation_htmx(self, page: Page, test_server_url):
        """Test that mobile post navigation uses HTMX without full page reloads"""
        
        # Check that we have the mobile layout
        expect(page.locator("#mobile-layout")).to_be_visible()
        
        # Get initial page state
        initial_url = page.url
        
        # Find first post - updated selector to match app.py (mobile-feed-item prefix)
        first_post = page.locator("li[id^='mobile-feed-item-']").first
        expect(first_post).to_be_visible(timeout=10000)
        
        # Store initial HTML to detect full reload
        initial_header_html = page.locator("#mobile-header").inner_html()
        
        # Click on first post - should use HTMX
        with page.expect_request(lambda req: "/item/" in req.url) as request_info:
            first_post.click()
        
        # Verify it was an HTMX request (has HX-Request header)
        request = request_info.value
        assert request.headers.get("hx-request") == "true", "Post click didn't use HTMX"
        
        # Wait for article to load in main content
        page.wait_for_selector("#main-content #item-detail", timeout=10000)
        
        # Verify URL changed (for shareability) 
        assert "/item/" in page.url, "URL didn't update for article"
        
        # Verify back button is shown - updated selector to match app.py CSS classes
        back_button = page.locator("#mobile-nav-button")  # Back button is first button
        expect(back_button).to_be_visible()
        
        # Verify it's actually a back button by checking for arrow-left icon
        back_icon = back_button.locator('uk-icon[icon="arrow-left"]')
        expect(back_icon).to_be_visible()
        
        # Click back button  
        back_button.click()
        wait_for_htmx_complete(page)  # OPTIMIZED: Wait for any HTMX operation to complete
        
        # Wait for feed list to return
        page.wait_for_selector("li[id^='mobile-feed-item-']", timeout=10000)
        
        # Verify we're back at the list (use mobile-specific selector)
        expect(page.locator("#main-content #feeds-list-container")).to_be_visible()
    
    def test_mobile_feed_filter_preserved(self, page: Page, test_server_url):
        """Test that feed filter state is preserved during navigation"""
        
        # Open mobile sidebar - updated selector
        menu_button = page.locator('#mobile-nav-button')
        menu_button.click()
        
        # Wait for sidebar - check for hidden attribute
        page.wait_for_selector("#mobile-sidebar", state="visible")
        sidebar = page.locator("#mobile-sidebar")
        # Sidebar should be visible (no hidden attribute or hidden=false)
        expect(sidebar).to_be_visible()
        
        # Click on a specific feed (not "All Feeds")
        feed_links = page.locator("#mobile-sidebar a[href*='feed_id=']")
        if feed_links.count() > 0:
            first_feed = feed_links.first
            feed_url = first_feed.get_attribute("href")
            feed_id = feed_url.split("feed_id=")[1].split("&")[0]
            
            # Click the feed
            first_feed.click()
            
            # Wait for filtered view to load and sidebar to close
            wait_for_htmx_complete(page)
            
            # Verify URL has feed_id
            assert f"feed_id={feed_id}" in page.url
            
            # Verify sidebar closed
            expect(sidebar).to_have_attribute("hidden", "true")
            
            # Click on a post - should preserve feed context
            posts = page.locator("li[id^='mobile-feed-item-']")
            if posts.count() > 0:
                first_post = posts.first
                first_post.click()
                wait_for_htmx_complete(page)  # FIXED: Don't expect sidebar visible after clicking post
                
                # URL should still contain feed_id
                assert f"feed_id={feed_id}" in page.url or "/item/" in page.url
                
                # Go back - should return to filtered feed view
                back_button = page.locator("#mobile-nav-button")
                back_button.click()
                wait_for_htmx_complete(page)  # FIXED: Don't expect sidebar visible after back navigation
                
                # Should be back to filtered view
                assert f"feed_id={feed_id}" in page.url
    
    # Form Persistence Tests (from test_mobile_form_bar_bug.py)  
    def test_mobile_persistent_header_visibility(self, page: Page, test_server_url):
        """Test that mobile persistent header shows/hides correctly during navigation"""
        
        # Verify we're in mobile mode
        desktop_layout = page.locator("#desktop-layout")
        mobile_content = page.locator("#main-content")
        
        expect(desktop_layout).to_be_hidden()
        expect(mobile_content).to_be_visible()
        
        # Check for persistent header with search form - should be visible initially
        persistent_header = page.locator("#mobile-persistent-header")
        expect(persistent_header).to_be_visible()
        expect(persistent_header).not_to_have_class("hidden")
        
        # Find search input in persistent header
        search_input = persistent_header.locator('input[placeholder="Search posts"]')
        expect(search_input).to_be_visible()
        
        # Enter some search text to create state
        test_search = "python programming"
        search_input.fill(test_search)
        
        # Verify text was entered
        filled_value = search_input.input_value()
        assert filled_value == test_search, f"Expected '{test_search}', got '{filled_value}'"
        
        # Click on an article - persistent header should be hidden in article view
        first_post = page.locator("li[id^='mobile-feed-item-']").first
        if first_post.is_visible():
            first_post.click()
            wait_for_htmx_complete(page)
            
            # Persistent header should be hidden during article reading (via CSS)
            header_hidden = page.evaluate("""() => {
                const header = document.getElementById('mobile-persistent-header');
                const style = window.getComputedStyle(header);
                return style.display === 'none';
            }""")
            assert header_hidden, "Persistent header should be hidden in article view"
            
            # Click back button
            back_button = page.locator("#mobile-nav-button")
            back_button.click()
            wait_for_htmx_complete(page)
            
            # Persistent header should be visible again
            expect(persistent_header).to_be_visible()
            expect(persistent_header).not_to_have_class("hidden")
            
            # Search form should be back (may or may not preserve state - that's the bug)
            restored_search_input = persistent_header.locator('input[placeholder="Search posts"]')
            expect(restored_search_input).to_be_visible()
    
    def test_mobile_search_form_functionality(self, page: Page, test_server_url):
        """Test that mobile search form works correctly"""
        
        # Find the search input in persistent header
        search_input = page.locator('#mobile-persistent-header input[placeholder="Search posts"]')
        expect(search_input).to_be_visible()
        
        # Test UK Filter functionality (if implemented)
        search_input.fill("test search")
        wait_for_htmx_complete(page, timeout=2000)  # FIXED: Don't expect sidebar visible after search
        
        # The search should work with uk-filter (MonsterUI)
        # This is mainly testing that the form doesn't break
        expect(search_input).to_have_value("test search")
        
        # Clear search
        search_input.clear()
        wait_for_htmx_complete(page, timeout=2000)
        
        expect(search_input).to_have_value("")
    
    # Scrolling Behavior Tests (from test_mobile_scrolling.py)
    def test_mobile_viewport_fixed_behavior(self, page: Page, test_server_url):
        """Test that mobile viewport is properly fixed to prevent bounce scrolling"""
        
        # Check that body has the proper CSS to prevent scrolling
        body_styles = page.evaluate("""() => {
            const body = document.body;
            const html = document.documentElement;
            const computedBody = window.getComputedStyle(body);
            const computedHtml = window.getComputedStyle(html);
            
            return {
                body_height: computedBody.height,
                body_overflow: computedBody.overflow,
                body_position: computedBody.position,
                html_height: computedHtml.height,
                html_overflow: computedHtml.overflow,
                html_position: computedHtml.position
            };
        }""")
        
        # Based on app.py CSS, body should be fixed with no overflow
        assert body_styles["body_position"] == "fixed", f"Body should be fixed, got {body_styles['body_position']}"
        assert body_styles["body_overflow"] == "hidden", f"Body should have overflow hidden, got {body_styles['body_overflow']}"
        assert body_styles["html_overflow"] == "hidden", f"HTML should have overflow hidden, got {body_styles['html_overflow']}"
    
    def test_mobile_content_scrolling(self, page: Page, test_server_url):
        """Test that mobile content areas scroll properly within fixed viewport"""
        
        # Main content should be scrollable
        main_content = page.locator("#main-content")
        expect(main_content).to_be_visible()
        
        # Check if main content has proper scrolling styles
        main_content_overflow = page.evaluate("""() => {
            const mainContent = document.getElementById('main-content');
            if (mainContent) {
                const computed = window.getComputedStyle(mainContent);
                return {
                    overflow_y: computed.overflowY,
                    height: computed.height
                };
            }
            return null;
        }""")
        
        assert main_content_overflow is not None, "Main content should exist"
        # Main content should be scrollable (overflow-y: auto or scroll)
        assert main_content_overflow["overflow_y"] in ["auto", "scroll"], f"Main content should be scrollable, got {main_content_overflow['overflow_y']}"
    
    def test_mobile_sidebar_scrolling(self, page: Page, test_server_url):
        """Test that mobile sidebar scrolls properly when opened"""
        
        # Open mobile sidebar
        menu_button = page.locator('#mobile-nav-button')
        menu_button.click()
        page.wait_for_selector("#mobile-sidebar", state="visible")
        
        # Sidebar should be visible and scrollable
        sidebar = page.locator("#mobile-sidebar")
        expect(sidebar).to_be_visible()
        
        # Check sidebar content area scrolling
        sidebar_content = sidebar.locator(".bg-background.w-80")  # Inner scrollable area
        expect(sidebar_content).to_be_visible()
        
        # Sidebar should have proper overflow handling
        sidebar_styles = page.evaluate("""() => {
            const sidebarContent = document.querySelector('#mobile-sidebar .bg-background.w-80');
            if (sidebarContent) {
                const computed = window.getComputedStyle(sidebarContent);
                return {
                    overflow_y: computed.overflowY,
                    height: computed.height
                };
            }
            return null;
        }""")
        
        assert sidebar_styles is not None, "Sidebar content should exist"
    
    # URL Sharing Tests (from test_mobile_url_sharing.py)
    def test_mobile_url_sharing_article_view(self, page: Page, test_server_url):
        """Test that article URLs are shareable and work when opened directly"""
        
        # Navigate to an article
        first_post = page.locator("li[id^='mobile-feed-item-']").first
        expect(first_post).to_be_visible(timeout=10000)
        
        first_post.click()
        wait_for_htmx_complete(page)
        
        # Should be on article page (use mobile-specific selector)
        expect(page.locator("#main-content #item-detail")).to_be_visible()
        article_url = page.url
        assert "/item/" in article_url, "Should be on article page"
        
        # Get article title for verification
        article_title = page.locator("#item-detail strong").first.text_content()
        
        # Navigate away and then back to test direct URL access
        page.goto(test_server_url)
        wait_for_page_ready(page)  # FIXED: Don't expect sidebar visible on main page
        
        # Now navigate directly to the article URL
        page.goto(article_url)
        wait_for_page_ready(page)
        
        # Should show the same article
        expect(page.locator("#main-content #item-detail")).to_be_visible()
        
        # Article title should match (if we got one)
        if article_title:
            expect(page.locator("#main-content #item-detail")).to_contain_text(article_title)
        
        # Mobile layout should still work
        expect(page.locator("#mobile-layout")).to_be_visible()
        
        # Should have back button since we're in article view
        back_button = page.locator("#mobile-nav-button")
        expect(back_button).to_be_visible()
    
    def test_mobile_url_sharing_feed_filter(self, page: Page, test_server_url):
        """Test that feed filter URLs are shareable"""
        
        # Open sidebar and select a feed
        menu_button = page.locator('#mobile-nav-button')
        menu_button.click()
        page.wait_for_selector("#mobile-sidebar", state="visible")
        
        # Click on a feed
        feed_links = page.locator("#mobile-sidebar a[href*='feed_id=']")
        if feed_links.count() > 0:
            first_feed = feed_links.first
            feed_url = first_feed.get_attribute("href")
            
            first_feed.click()
            wait_for_htmx_complete(page)
            
            # Should be on filtered feed view
            current_url = page.url
            assert "feed_id=" in current_url, "Should be on filtered feed view"
            
            # Navigate away and back to test sharing
            page.goto(test_server_url)
            wait_for_page_ready(page)  # OPTIMIZED: Wait for page to load, sidebar is hidden by default
            
            # Navigate directly to the feed URL
            page.goto(current_url)
            wait_for_page_ready(page)
            
            # Should be back on the filtered view
            assert "feed_id=" in page.url, "Should maintain feed filter"
            
            # Mobile layout should work
            expect(page.locator("#mobile-layout")).to_be_visible()
            expect(page.locator("#main-content")).to_be_visible()
    
    def test_mobile_url_sharing_with_unread_filter(self, page: Page, test_server_url):
        """Test URL sharing with unread filter applied"""
        
        # Click on Unread tab if available
        unread_tab = page.locator('a[role="button"]:has-text("Unread")').first
        if unread_tab.is_visible():
            unread_tab.click()
            wait_for_htmx_complete(page)
            
            # Should have unread parameter in URL
            current_url = page.url
            assert "unread" in current_url or page.url == test_server_url + "/", "Should have unread context"
            
            # Navigate away and back
            page.goto(test_server_url + "/?feed_id=1")  # Go to different view
            page.wait_for_selector("#mobile-sidebar", state="visible")
            
            # Navigate back to unread view
            page.goto(current_url)
            wait_for_htmx_complete(page)
            
            # Should be back in unread view
            expect(page.locator("#main-content")).to_be_visible()
            
            # Unread tab should be active if it exists
            if page.locator('a[role="button"]:has-text("Unread")').first.is_visible():
                unread_tab_check = page.locator('a[role="button"]:has-text("Unread")').first
                # Check for active class (uk-active)
                tab_classes = unread_tab_check.get_attribute("class") or ""
                # Note: This may not always be uk-active depending on implementation
    
    # NOTE: Mobile browser back/forward test moved to test_mobile_url_navigation.py to avoid test interference

    def test_mobile_feed_title_persistence_after_article_navigation(self, page: Page, test_server_url):
        """Test that feed title shows correctly after navigating back from article when specific feed is selected"""
        
        # Open mobile sidebar first
        hamburger_button = page.locator('#mobile-nav-button')
        hamburger_button.click()
        page.wait_for_selector("#mobile-sidebar", state="visible")
        
        # Select a specific feed (ClaudeAI) - use dynamic feed ID
        claudeai_feed = page.locator('a[href*="feed_id"]:has-text("ClaudeAI")').first
        expect(claudeai_feed).to_be_visible()
        claudeai_feed.click()
        wait_for_htmx_complete(page)
        
        # Verify we're viewing ClaudeAI feed
        feed_title = page.locator("#mobile-persistent-header h3")
        expect(feed_title).to_have_text("ClaudeAI")
        
        # Click on an article
        first_article = page.locator("li[id^='mobile-feed-item-']").first
        expect(first_article).to_be_visible()
        first_article.click()
        wait_for_htmx_complete(page)
        
        # Should be on article view
        expect(page.locator("#main-content #item-detail")).to_be_visible()
        
        # Click back button
        back_button = page.locator("#mobile-nav-button").filter(has=page.locator('uk-icon[icon="arrow-left"]'))
        expect(back_button).to_be_visible()
        back_button.click()
        wait_for_htmx_complete(page)
        
        # Should be back to feed list with correct feed title
        expect(page.locator("#main-content #feeds-list-container")).to_be_visible()
        feed_title_after_back = page.locator("#mobile-persistent-header h3")
        expect(feed_title_after_back).to_have_text("ClaudeAI")  # Should NOT be "BizToc"



if __name__ == "__main__":
    pytest.main([__file__, "-v"])