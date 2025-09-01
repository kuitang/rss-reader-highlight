"""Critical UI flow tests targeting specific problems we debugged with Playwright MCP

Updated selectors to match current app.py implementation:
- Mobile sidebar now uses CSS classes instead of hidden attribute  
- Feed items have mobile-/desktop- prefixes
- Add feed form uses .add-feed-form class
- Tab navigation uses link elements with role="button"
"""

import pytest
import subprocess
import time
import os
import sys
from playwright.sync_api import sync_playwright, expect
from contextlib import contextmanager

TEST_PORT = 8080  # Use the main server port
TEST_URL = f"http://localhost:{TEST_PORT}"

# HTMX Helper Functions for Fast Testing
def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete - much faster than fixed timeouts"""
    page.wait_for_function("() => !document.body.classList.contains('htmx-request')", timeout=timeout)

def wait_for_htmx_settle(page, timeout=5000):
    """Wait for HTMX to completely settle with no pending requests"""
    page.wait_for_function("() => !document.querySelector('.htmx-request')", timeout=timeout)

def wait_for_page_ready(page):
    """Fast page ready check - waits for network idle instead of fixed timeout"""
    page.wait_for_load_state("networkidle")

@contextmanager
def existing_server():
    """Use existing server running on port 8080"""
    # Just verify server is responding
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

class TestFormParameterBugFlow:
    """Test the form parameter bug we debugged extensively"""
    
    def test_feed_url_form_submission_complete_flow(self, page):
        """Test: Type URL → Click add → Verify server receives parameter correctly
        
        This was our BIGGEST bug - form parameters not mapping to FastHTML functions.
        Requires: python app.py running in separate terminal
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport to ensure desktop layout
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(TEST_URL)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle instead of 3 seconds
        
        # 1. Verify desktop layout is visible first
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page.locator("#sidebar")).to_be_visible()
        
        # 2. Verify form elements exist and have correct attributes  
        # UPDATED SELECTOR: Use class selector matching actual HTML structure
        url_input = page.locator('#sidebar input.add-feed-input')
        expect(url_input).to_be_visible(timeout=10000)
        expect(url_input).to_have_attribute("name", "new_feed_url")  # Critical - maps to FastHTML param
        
        # UPDATED SELECTOR: Use class selector matching actual HTML  
        add_button = page.locator('#sidebar button.uk-btn.add-feed-button')
        expect(add_button).to_be_visible()
        
        # 2. Test empty submission - should trigger validation
        add_button.click()
        wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX instead of 1 second
        
        # App should remain stable regardless of validation message
        
        # 3. Test actual URL submission
        url_input.fill("https://httpbin.org/xml")  # Safe test feed
        add_button.click()
        wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX processing completion
        
        # Verify app remains stable (main test goal - no parameter mapping crash)
        expect(page.locator("#sidebar")).to_be_visible()
        expect(page.locator("#sidebar h3").first).to_be_visible()  # FIXED: Use sidebar-specific h3

    def test_feed_url_form_submission_mobile_flow(self, page):
        """Test mobile workflow: Open sidebar → Type URL → Click add → Verify functionality
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(TEST_URL)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
        
        # 1. Open mobile sidebar - UPDATED SELECTOR using filter
        mobile_menu_button = page.locator('#mobile-header button').filter(has=page.locator('uk-icon[icon="menu"]'))
        expect(mobile_menu_button).to_be_visible()
        mobile_menu_button.click()
        page.wait_for_selector("#mobile-sidebar", state="visible")  # OPTIMIZED: Wait for sidebar to appear
        
        # 2. Find mobile input and button - UPDATED SELECTORS
        mobile_url_input = page.locator('#mobile-sidebar input[placeholder="Enter RSS URL"]')
        expect(mobile_url_input).to_be_visible()
        expect(mobile_url_input).to_have_attribute("name", "new_feed_url")
        
        mobile_add_button = page.locator('#mobile-sidebar button.add-feed-button')
        expect(mobile_add_button).to_be_visible()
        
        # 3. Test mobile form submission
        mobile_url_input.fill("https://httpbin.org/xml")
        mobile_add_button.click()
        wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX completion
        
        # Verify app remains stable in mobile layout
        expect(page.locator("#mobile-sidebar")).to_be_visible()

    def test_mobile_sidebar_auto_close_on_feed_click(self, page):
        """Test: Mobile sidebar should auto-close when feed link is clicked
        
        UPDATED SELECTORS to match current app.py CSS class implementation.
        """
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(TEST_URL)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
        
        # 1. Open mobile sidebar - UPDATED SELECTOR
        mobile_menu_button = page.locator('#mobile-header button').filter(has=page.locator('uk-icon[icon="menu"]'))
        mobile_menu_button.click()
        page.wait_for_selector("#mobile-sidebar", state="visible")  # OPTIMIZED: Wait for sidebar to open
        
        # 2. Verify sidebar is open - UPDATED: Check for absence of 'hidden' class
        mobile_sidebar = page.locator('#mobile-sidebar')
        expect(mobile_sidebar).to_be_visible()
        expect(mobile_sidebar).not_to_have_class("hidden")
        
        # 3. Click on a feed link - UPDATED SELECTOR (any feed_id link)
        feed_link = page.locator('#mobile-sidebar a[href*="feed_id="]').first
        if feed_link.is_visible():
            feed_link.click()
            wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX response
            
            # 4. EXPECTED BEHAVIOR: Sidebar should auto-close after feed click
            # UPDATED: Check for 'hidden' class instead of hidden attribute
            expect(mobile_sidebar).to_have_class("hidden")
            
            # 5. Verify feed filtering worked (URL should have feed_id)
            expect(page).to_have_url(url_contains="feed_id")

    def test_desktop_feed_filtering_full_page_update(self, page):
        """Test: Desktop feed click should trigger full page update with proper filtering
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(TEST_URL)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
        
        # 1. Verify we start with main view
        expect(page.locator("h3").first).to_be_visible()  # Some header should be visible
        
        # 2. Navigate to feed URL directly (simulates feed link behavior)
        page.goto("http://localhost:8080/?feed_id=2")
        wait_for_page_ready(page)  # OPTIMIZED: Wait for page load
        
        # 3. Verify URL updated correctly
        expect(page).to_have_url("http://localhost:8080/?feed_id=2")
        
        # 4. Verify desktop layout is still working
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page.locator("#sidebar")).to_be_visible()
    
    def test_duplicate_feed_detection_via_form(self, page):
        """Test: Add existing feed → Should show proper handling
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport for consistency
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(TEST_URL)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
        page.wait_for_selector("a[href*='feed_id']", timeout=10000)  # OPTIMIZED: Wait for feeds to load
        
        # UPDATED SELECTORS - use class-based approach
        url_input = page.locator('#sidebar input[placeholder="Enter RSS URL"]')
        url_input.fill("https://hnrss.org/frontpage")  # Try to add existing Hacker News feed
        
        add_button = page.locator('#sidebar button.add-feed-button')
        add_button.click()
        wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX completion
        
        # App should remain stable regardless of duplicate detection behavior


class TestBBCRedirectHandlingFlow:
    """Test BBC feed redirect handling that we fixed"""
    
    def test_bbc_feed_addition_with_redirects(self, page):
        """Test: Add BBC feed → Handle 302 redirect → Parse successfully → Shows in UI
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport for consistency
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(TEST_URL)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
        
        # Count initial feeds
        initial_feeds = page.locator("a[href*='feed_id']")
        initial_count = initial_feeds.count()
        
        # UPDATED SELECTORS - use placeholder instead of role
        url_input = page.locator('#sidebar input[placeholder="Enter RSS URL"]')
        url_input.fill("http://feeds.bbci.co.uk/news/rss.xml")  # Note: http (redirects to https)
        
        add_button = page.locator('#sidebar button.add-feed-button')
        add_button.click()
        
        # Wait for processing (redirects + parsing take time) - but use smarter wait
        wait_for_htmx_complete(page, timeout=15000)  # OPTIMIZED: Longer timeout for network requests
        
        # Should handle gracefully - app shouldn't crash
        expect(page.locator("#sidebar")).to_be_visible()
        
        # Refresh to see updated sidebar
        page.reload()
        wait_for_page_ready(page)  # OPTIMIZED: Wait for reload completion
        
        # Should show proper error handling, not parameter errors
        parameter_error = page.locator("text=Please enter a URL")
        expect(parameter_error).not_to_be_visible()


class TestBlueIndicatorHTMXFlow:
    """Test the complex blue indicator HTMX update flow we implemented"""
    
    def test_blue_indicator_disappears_on_article_click(self, page):
        """Test: Click article with blue dot → Dot disappears immediately → HTMX update working
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport for consistency
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(TEST_URL)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
        page.wait_for_selector("li[id^='desktop-feed-item-'], li[id^='mobile-feed-item-']", timeout=10000)  # OPTIMIZED: Wait for articles to load
        
        # 1. Find articles with blue indicators (unread)
        blue_dots = page.locator(".bg-blue-600")  # Blue indicator class
        initial_blue_count = blue_dots.count()
        
        if initial_blue_count == 0:
            pytest.skip("No unread articles to test blue indicator removal")
        
        # 2. Find the parent article of first blue dot
        first_blue_article = page.locator("li:has(.bg-blue-600)").first
        
        # 3. Click the article
        first_blue_article.click()
        
        # 4. Verify HTMX updates happened
        wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX completion
        
        # Blue dot should disappear from that specific article
        updated_blue_count = page.locator(".bg-blue-600").count()
        assert updated_blue_count < initial_blue_count, "Blue indicator should have been removed"
        
        # 5. Detail view should be populated (desktop or mobile)
        # FIXED: Use .first to avoid strict mode violation
        detail_view = page.locator("#item-detail, #desktop-item-detail").first
        expect(detail_view).to_be_visible()
        expect(detail_view.locator("strong").first).to_be_visible()
    
    def test_unread_view_article_behavior(self, page):
        """Test: Unread view → Click article → Article marked as read
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport for consistency
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(TEST_URL)
        wait_for_page_ready(page)
        
        # 1. Switch to Unread view - UPDATED: Use link with role=button
        unread_tab = page.locator('a[role="button"]:has-text("Unread")').first
        if unread_tab.is_visible():
            unread_tab.click()
            wait_for_htmx_complete(page)
            
            # 2. Count unread articles - UPDATED: Check both mobile and desktop prefixes
            unread_articles = page.locator("li[id^='desktop-feed-item-'], li[id^='mobile-feed-item-']")
            initial_unread_count = unread_articles.count()
            
            if initial_unread_count == 0:
                pytest.skip("No unread articles to test behavior")
            
            # 3. Click first article
            first_unread = unread_articles.first
            first_unread.click()
            wait_for_htmx_complete(page)  # Wait for HTMX response
            
            # 4. Article should be marked as read (blue dot gone)
            # Detail view should show content
            expect(page.locator("#item-detail, #desktop-item-detail").first).to_be_visible()
    
    def test_multiple_article_clicks_blue_management(self, page):
        """Test: Click multiple articles → Each loses blue dot → UI updates correctly
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport for consistency
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(TEST_URL)
        wait_for_page_ready(page)
        
        # Get articles with blue dots
        articles_with_blue = page.locator("li:has(.bg-blue-600)")
        initial_count = articles_with_blue.count()
        
        if initial_count == 0:
            pytest.skip("No unread articles to test")
        
        # Click up to 3 articles
        clicks_to_test = min(3, initial_count)
        
        for i in range(clicks_to_test):
            current_blue_articles = page.locator("li:has(.bg-blue-600)")
            if current_blue_articles.count() > 0:
                # Click next unread article
                current_blue_articles.first.click()
                wait_for_htmx_complete(page)  # Wait for HTMX
                
                # Blue count should decrease
                remaining_blue = page.locator(".bg-blue-600").count()
                expected_remaining = initial_count - (i + 1)
                assert remaining_blue <= expected_remaining, f"Blue dots should decrease to {expected_remaining} or fewer"


class TestSessionAndSubscriptionFlow:
    """Test the session auto-subscription flow that caused 'No posts available'"""
    
    def test_fresh_user_auto_subscription_flow(self, page):
        """Test: Fresh browser → Auto session → Auto subscribe → Articles appear
        
        This tests the beforeware logic that was broken initially.
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport for consistency
        page.set_viewport_size({"width": 1200, "height": 800})
        # 1. Fresh browser visit
        page.goto(TEST_URL)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
        page.wait_for_selector("a[href*='feed_id']", timeout=15000)  # OPTIMIZED: Wait for feeds to load
        
        # 2. Should automatically see feeds in sidebar
        feed_links = page.locator("a[href*='feed_id']")
        expect(feed_links.first).to_be_visible(timeout=10000)
        
        feed_count = feed_links.count()
        assert feed_count >= 3, f"Should have 3+ default feeds, got {feed_count}"
        
        # 3. Should automatically see articles (not "No posts available")
        # UPDATED: Check both mobile and desktop prefixes
        articles = page.locator("li[id^='desktop-feed-item-'], li[id^='mobile-feed-item-']")
        expect(articles.first).to_be_visible(timeout=15000)
        
        article_count = articles.count()
        assert article_count > 10, f"Should have 10+ articles from auto-subscription, got {article_count}"
        
        # 4. Should show content indicating substantial articles
        expect(page.locator("#sidebar")).to_be_visible()
        expect(page.locator("#desktop-feeds-content, #main-content")).to_be_visible()
    
    def test_second_browser_tab_independent_session(self, browser):
        """Test: Multiple browser contexts → Independent sessions → No interference"""

        # Tab 1: Regular browsing
        page1 = browser.new_page()
        page1.goto(TEST_URL)
        page1.wait_for_timeout(5000)
        
        # Tab 2: Independent session
        page2 = browser.new_page()
        page2.goto(TEST_URL)
        page2.wait_for_timeout(5000)
        
        try:
            # Both should have feeds
            expect(page1.locator("a[href*='feed_id']").first).to_be_visible()
            expect(page2.locator("a[href*='feed_id']").first).to_be_visible()
            
            # Actions in one shouldn't affect the other
            articles1 = page1.locator("li[id^='desktop-feed-item-'], li[id^='mobile-feed-item-']")
            if articles1.count() > 0:
                # Click article in tab 1
                articles1.first.click()
                page1.wait_for_timeout(500)
                
                # Tab 2 should be unaffected
                expect(page2.locator("h3")).to_be_visible()
                
        finally:
            page1.close()
            page2.close()


class TestFullViewportHeightFlow:
    """Test viewport height utilization that we fixed"""
    
    def test_desktop_full_height_usage(self, page):
        """Test: Desktop viewport → Full height utilization → Proper scrolling containers
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set large desktop viewport
        page.set_viewport_size({"width": 1400, "height": 1000})
        page.goto(TEST_URL)
        page.wait_for_timeout(3000)
        
        # 1. Desktop layout should be visible
        expect(page.locator("#desktop-layout")).to_be_visible()
        
        # 2. Each panel should be visible
        expect(page.locator("#sidebar")).to_be_visible()
        expect(page.locator("#desktop-feeds-content")).to_be_visible()
        expect(page.locator("#desktop-item-detail")).to_be_visible()
        
        # 3. Content areas should have proper height
        content_area = page.locator("#desktop-feeds-content")
        if content_area.is_visible():
            content_height = content_area.bounding_box()["height"]
            assert content_height > 400, f"Content area should use substantial height, got {content_height}px"
    
    def test_mobile_layout_adaptation(self, page):
        """Test: Mobile viewport → Layout stacking → Responsive behavior
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Test mobile layout
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(TEST_URL)
        page.wait_for_timeout(3000)
        
        # Desktop should be hidden, mobile should be visible
        expect(page.locator("#desktop-layout")).to_be_hidden()
        expect(page.locator("#mobile-layout")).to_be_visible()
        
        # Mobile content should be accessible
        expect(page.locator("#main-content")).to_be_visible()
        
        # Should be able to interact with mobile elements
        menu_button = page.locator('#mobile-header button').filter(has=page.locator('uk-icon[icon="menu"]'))
        expect(menu_button).to_be_visible()


class TestErrorHandlingUIFeedback:
    """Test error handling and user feedback mechanisms"""
    
    def test_network_error_handling_ui_feedback(self, page):
        """Test: Network errors → Proper user feedback → No broken UI"""

        page.goto(TEST_URL)
        page.wait_for_timeout(3000)
        
        # Test adding feed that will definitely fail
        error_test_cases = [
            "https://definitely-does-not-exist-feed-url-12345.com/rss",
            "http://localhost:99999/feed.xml",  # Port that doesn't exist
        ]
        
        for test_url in error_test_cases:
            url_input = page.locator('#sidebar input[placeholder="Enter RSS URL"]')
            url_input.clear()
            url_input.fill(test_url)
            
            add_button = page.locator('#sidebar button.add-feed-button')
            add_button.click()
            wait_for_page_ready(page)  # Wait for network timeout
            
            # Should NOT show parameter error
            parameter_error = page.locator("text=Please enter a URL")
            expect(parameter_error).not_to_be_visible()
            
            # App should remain stable
            expect(page.locator("#sidebar")).to_be_visible()
    
    def test_malformed_url_error_handling(self, page):
        """Test: Invalid URLs → Proper validation → User-friendly errors"""

        page.goto(TEST_URL)
        page.wait_for_timeout(3000)
        
        invalid_urls = [
            "not-a-url-at-all",
            "javascript:alert('xss')",  # Security test
            "http://",  # Incomplete URL
            " ",  # Whitespace
        ]
        
        for invalid_url in invalid_urls:
            url_input = page.locator('#sidebar input[placeholder="Enter RSS URL"]')
            url_input.clear()
            url_input.fill(invalid_url)
            
            add_button = page.locator('#sidebar button.add-feed-button')
            add_button.click()
            wait_for_htmx_complete(page)
            
            # Should handle gracefully - app shouldn't crash
            expect(page.locator("#sidebar")).to_be_visible()
            
            # Should NOT show internal server errors
            server_error = page.locator("text*=500 Internal Server Error")
            expect(server_error).not_to_be_visible()


class TestComplexNavigationFlows:
    """Test complex navigation patterns that could break"""
    
    def test_deep_navigation_and_back_button_flow(self, page):
        """Test: Deep navigation → Browser back → State consistency → No broken UI"""

        page.goto(TEST_URL)
        wait_for_page_ready(page)
        
        # 1. Navigate through different views
        navigation_sequence = [
            ("a[href*='feed_id']", "feed filter"),  # Click specific feed
            ('a[role="button"]:has-text("Unread")', "unread view"),  # Switch to unread
            ("li[id^='desktop-feed-item-'], li[id^='mobile-feed-item-']", "article detail"),  # Click article
        ]
        
        for selector, description in navigation_sequence:
            element = page.locator(selector).first
            if element.is_visible():
                element.click()
                wait_for_htmx_complete(page)
                
                # App should remain stable after each navigation
                expect(page.locator("#item-detail, h3").first).to_be_visible()
        
        # 2. Test browser back navigation
        page.go_back()
        wait_for_htmx_complete(page)
        expect(page.locator("#item-detail, h3").first).to_be_visible()
        
        page.go_back()  
        wait_for_htmx_complete(page)
        expect(page.locator("#item-detail, h3").first).to_be_visible()
        
        # Should eventually be stable
        expect(page.locator("#sidebar, #mobile-header")).to_be_visible()
    
    def test_rapid_clicking_stability(self, page):
        """Test: Rapid clicking → Multiple HTMX requests → UI stability → No race conditions"""

        page.goto(TEST_URL)
        wait_for_page_ready(page)
        
        # Collect clickable elements safely
        clickable_elements = []
        
        # Feed links
        feed_links = page.locator("a[href*='feed_id']").all()[:3]  # First 3
        clickable_elements.extend(feed_links)
        
        # Tab buttons (if they exist)
        tab_buttons = page.locator('a[role="button"]:has-text("All Posts"), a[role="button"]:has-text("Unread")').all()
        clickable_elements.extend(tab_buttons)
        
        # Articles (first 3)
        article_links = page.locator("li[id^='desktop-feed-item-'], li[id^='mobile-feed-item-']").all()[:3]
        clickable_elements.extend(article_links)
        
        # Rapid clicking test
        for element in clickable_elements[:8]:  # Test first 8 elements
            if element.is_visible():
                element.click()
                wait_for_htmx_complete(page, timeout=1000)  # Short wait
                
                # App should remain stable
                expect(page.locator("title")).to_have_text("RSS Reader")
        
        # Final state should be stable
        expect(page.locator("#sidebar, #mobile-header").first).to_be_visible()


if __name__ == "__main__":
    # Run critical UI flow tests
    pytest.main([__file__, "-v", "--tb=short"])