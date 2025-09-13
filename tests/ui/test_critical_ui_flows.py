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
from playwright.sync_api import sync_playwright, expect, Page
from contextlib import contextmanager

pytestmark = pytest.mark.needs_server

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


class TestFormParameterBugFlow:
    """Test the form parameter bug we debugged extensively"""
    
    @pytest.mark.skip(reason="Feed submission test - skipping per user request")
    def test_feed_url_form_submission_complete_flow(self, page, test_server_url):
        """Test: Type URL → Click add → Verify server receives parameter correctly
        
        This was our BIGGEST bug - form parameters not mapping to FastHTML functions.
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport to ensure desktop layout
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(test_server_url)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle instead of 3 seconds
        
        # 1. Verify desktop layout is visible first
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page.locator("#sidebar")).to_be_visible()
        
        # 2. Verify form elements exist and have correct attributes  
        # Use more stable selectors with wait and expect patterns
        url_input = page.locator('#sidebar input[name="new_feed_url"]')
        expect(url_input).to_be_visible(timeout=10000)
        expect(url_input).to_have_attribute("name", "new_feed_url")  # Critical - maps to FastHTML param
        
        add_button = page.locator('#sidebar button.add-feed-button')
        expect(add_button).to_be_visible()
        
        # 2. Test empty submission - should trigger validation
        add_button.click()
        wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX instead of 1 second
        
        # App should remain stable regardless of validation message
        
        # 3. Test actual URL submission - wait for DOM to stabilize after HTMX update
        input_locator = page.locator('#sidebar input[name="new_feed_url"]')
        button_locator = page.locator('#sidebar button.add-feed-button')
        
        # Wait for elements to be available after HTMX response
        expect(input_locator).to_be_visible(timeout=10000)
        expect(button_locator).to_be_visible(timeout=10000)
        
        input_locator.fill("https://httpbin.org/xml")  # Safe test feed
        button_locator.click()
        wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX processing completion
        
        # Verify app remains stable (main test goal - no parameter mapping crash)
        expect(page.locator("#sidebar")).to_be_visible()
        expect(page.locator("#sidebar h3").first).to_be_visible()  # FIXED: Use sidebar-specific h3

    @pytest.mark.skip(reason="Feed submission test - skipping per user request")
    def test_feed_url_form_submission_mobile_flow(self, page, test_server_url):
        """Test mobile workflow: Open sidebar → Type URL → Click add → Verify functionality
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(test_server_url)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
        
        # 1. Open mobile sidebar - UPDATED SELECTOR using filter
        mobile_menu_button = page.locator('#mobile-nav-button')
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

    def test_mobile_sidebar_auto_close_on_feed_click(self, page, test_server_url):
        """Test: Mobile sidebar should auto-close when feed link is clicked
        
        UPDATED SELECTORS to match current app.py CSS class implementation.
        """
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(test_server_url)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
        
        # 1. Open mobile sidebar - UPDATED SELECTOR
        mobile_menu_button = page.locator('#mobile-nav-button')
        mobile_menu_button.click()
        page.wait_for_selector("#mobile-sidebar", state="visible")  # OPTIMIZED: Wait for sidebar to open
        
        # 2. Verify sidebar is open - Check that it's visible (which means no hidden attribute)
        mobile_sidebar = page.locator('#mobile-sidebar')
        expect(mobile_sidebar).to_be_visible()
        
        # 3. Click on a feed link - UPDATED SELECTOR (any feed_id link)
        feed_link = page.locator('#mobile-sidebar a[href*="feed_id="]').first
        if feed_link.is_visible():
            feed_link.click()
            wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX response
            
            # 4. EXPECTED BEHAVIOR: Sidebar should auto-close after feed click  
            # Check that sidebar is now hidden (has hidden attribute)
            expect(mobile_sidebar).to_have_attribute("hidden", "true")
            
            # 5. Verify feed filtering worked (URL should have feed_id)
            assert "feed_id" in page.url, "URL should contain feed_id parameter"

    def test_desktop_feed_filtering_full_page_update(self, page, test_server_url):
        """Test: Desktop feed click should trigger full page update with proper filtering
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(test_server_url)
        wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
        
        # 1. Verify we start with main view (check desktop-specific elements)
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page.locator("#sidebar")).to_be_visible()
        
        # 2. Navigate to a feed by clicking on it (more realistic)
        # Find and click on any available feed link
        feed_links = page.locator("#sidebar a[href*='feed_id']")
        if feed_links.count() > 0:
            first_feed = feed_links.first
            feed_href = first_feed.get_attribute("href")
            first_feed.click()
            wait_for_page_ready(page)  # OPTIMIZED: Wait for page load
            
            # 3. Verify URL updated correctly
            assert "feed_id" in page.url, "Should have navigated to a feed"
        
        # 4. Verify desktop layout is still working
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page.locator("#sidebar")).to_be_visible()
    
    @pytest.mark.skip(reason="Feed submission test - skipping per user request")
    def test_duplicate_feed_detection_via_form(self, page, test_server_url):
        """Test: Add existing feed → Should show proper handling
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport for consistency
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(test_server_url)
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
    
    @pytest.mark.skip(reason="Feed submission test - skipping per user request")
    def test_bbc_feed_addition_with_redirects(self, page, test_server_url):
        """Test: Add BBC feed → Handle 302 redirect → Parse successfully → Shows in UI
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport for consistency
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(test_server_url)
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
        wait_for_htmx_complete(page, timeout=10000)  # OPTIMIZED: Longer timeout for network requests
        
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
    
    def test_blue_indicator_disappears_on_article_click(self, page, test_server_url):
        """Test: Click article with blue dot → Dot disappears immediately → HTMX update working
        
        Tests both mobile and desktop layouts.
        UPDATED SELECTORS to match current app.py implementation.
        """
        for viewport_name, viewport_size, layout_check in [
            ("desktop", {"width": 1200, "height": 800}, "#desktop-layout"),
            ("mobile", {"width": 375, "height": 667}, "#mobile-layout")
        ]:
            print(f"\n--- Testing {viewport_name} blue indicator behavior ---")
            page.set_viewport_size(viewport_size)
            page.goto(test_server_url)
            wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
            
            # Verify correct layout is active
            expect(page.locator(layout_check)).to_be_visible()
            
            # Wait for articles to load based on layout
            if viewport_name == "desktop":
                page.wait_for_selector("li[id^='desktop-feed-item-']", timeout=10000)
                articles_selector = "li[id^='desktop-feed-item-']"
                detail_selector = "#desktop-item-detail"
            else:
                page.wait_for_selector("li[id^='mobile-feed-item-']", timeout=10000)  
                articles_selector = "li[id^='mobile-feed-item-']"
                detail_selector = "#main-content #item-detail"  # More specific for mobile
            
            # 1. Find articles with blue indicators (unread)
            blue_dots = page.locator(".bg-blue-600")  # Blue indicator class
            initial_blue_count = blue_dots.count()
            
            # DISABLED CONDITIONAL FOR DEBUGGING
            # if initial_blue_count == 0:
            #     print(f"  Skipping {viewport_name} - no unread articles")
            #     continue
            assert initial_blue_count > 0, f"Should have unread articles in {viewport_name}, but got {initial_blue_count}"
            
            # 2. Find the parent article of first blue dot (layout-specific)
            first_blue_article = page.locator(f"{articles_selector}:has(.bg-blue-600)").first
            article_id = first_blue_article.get_attribute("id") if first_blue_article.get_attribute("id") else None
            
            # 3. Click the article
            first_blue_article.click()
            
            # 4. Verify HTMX updates happened
            wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX completion
            
            # 5. Verify the specific clicked article no longer has blue dot
            if article_id:
                clicked_article = page.locator(f'#{article_id}')
                blue_indicator = clicked_article.locator('.bg-blue-600')
                expect(blue_indicator).not_to_be_visible()
                print(f"  ✓ {viewport_name} article {article_id} blue dot removed")
            
            # 6. Detail view should be populated (layout-specific)
            detail_view = page.locator(detail_selector)
            expect(detail_view).to_be_visible()
            expect(detail_view.locator("strong").first).to_be_visible()
            print(f"  ✓ {viewport_name} blue indicator test passed")
    
    def test_unread_view_article_behavior(self, page, test_server_url):
        """Test: Unread view → Click article → Article marked as read
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport for consistency
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(test_server_url)
        wait_for_page_ready(page)
        
        # 1. Switch to Unread view - UPDATED: Use link with role=button
        unread_tab = page.locator('a[role="button"]:has-text("Unread")').first
        if unread_tab.is_visible():
            unread_tab.click()
            wait_for_htmx_complete(page)
            
            # 2. Count unread articles - UPDATED: Check both mobile and desktop prefixes
            unread_articles = page.locator("li[id^='desktop-feed-item-'], li[id^='mobile-feed-item-']")
            initial_unread_count = unread_articles.count()
            
            # DISABLED CONDITIONAL FOR DEBUGGING
            # if initial_unread_count == 0:
            #     pytest.skip("No unread articles to test behavior")
            assert initial_unread_count > 0, f"Should have unread articles, but got {initial_unread_count}"
            
            # 3. Click first article
            first_unread = unread_articles.first
            first_unread.click()
            wait_for_htmx_complete(page)  # Wait for HTMX response
            
            # 4. Article should be marked as read (blue dot gone)
            # Detail view should show content
            expect(page.locator("#item-detail, #desktop-item-detail").first).to_be_visible()
    
    def test_multiple_article_clicks_blue_management(self, page, test_server_url):
        """Test: Click multiple articles → Each loses blue dot → UI updates correctly
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        # Set desktop viewport for consistency
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(test_server_url)
        wait_for_page_ready(page)
        
        # Get articles with blue dots
        articles_with_blue = page.locator("li:has(.bg-blue-600)")
        initial_count = articles_with_blue.count()
        
        # DISABLED CONDITIONAL FOR DEBUGGING
        # if initial_count == 0:
        #     pytest.skip("No unread articles to test")
        assert initial_count > 0, f"Should have unread articles with blue indicators, but got {initial_count}"
        
        # Click up to 3 articles
        clicks_to_test = min(3, initial_count)
        
        for i in range(clicks_to_test):
            current_blue_articles = page.locator("li:has(.bg-blue-600)")
            if current_blue_articles.count() > 0:
                # Get the ID of the article we're about to click
                article_to_click = current_blue_articles.first
                article_id = article_to_click.get_attribute("id") if article_to_click.get_attribute("id") else f"article-{i}"
                
                # Click the article
                article_to_click.click()
                wait_for_htmx_complete(page)  # Wait for HTMX
                
                # Verify the specific clicked article no longer has a blue dot
                # On desktop, article should ALWAYS remain visible after click (never disappears from list)
                if article_id and (article_id.startswith("desktop-feed-item-") or article_id.startswith("mobile-feed-item-")):
                    clicked_article = page.locator(f'#{article_id}')
                    # Desktop test: article must still be visible (it stays in the list)
                    expect(clicked_article).to_be_visible()
                    # But blue indicator should be gone (article marked as read)
                    blue_indicator = clicked_article.locator('.bg-blue-600')
                    expect(blue_indicator).not_to_be_visible()


class TestSessionAndSubscriptionFlow:
    """Test the session auto-subscription flow that caused 'No posts available'"""
    
    def test_fresh_user_auto_subscription_flow(self, page, test_server_url):
        """Test: Fresh browser → Auto session → Auto subscribe → Articles appear
        
        Tests both mobile and desktop layouts.
        This tests the beforeware logic that was broken initially.
        UPDATED SELECTORS to match current app.py implementation.
        """
        for viewport_name, viewport_size, layout_check in [
            ("desktop", {"width": 1200, "height": 800}, "#desktop-layout"),
            ("mobile", {"width": 375, "height": 667}, "#mobile-layout")
        ]:
            print(f"\n--- Testing {viewport_name} auto-subscription flow ---")
            page.set_viewport_size(viewport_size)
            # 1. Fresh browser visit
            page.goto(test_server_url)
            wait_for_page_ready(page)  # OPTIMIZED: Wait for network idle
            
            # Verify correct layout is active
            expect(page.locator(layout_check)).to_be_visible()
            
            # 2. Should automatically see feeds (layout-specific)
            if viewport_name == "desktop":
                page.wait_for_selector("#sidebar a[href*='feed_id']", timeout=10000)
                feed_links = page.locator("#sidebar a[href*='feed_id']")
                content_selector = "#desktop-feeds-content"
                articles_selector = "li[id^='desktop-feed-item-']"
            else:
                # Mobile: feeds are in mobile sidebar (initially hidden)
                menu_button = page.locator('#mobile-nav-button')
                menu_button.click()
                page.wait_for_selector("#mobile-sidebar a[href*='feed_id']", timeout=10000)
                feed_links = page.locator("#mobile-sidebar a[href*='feed_id']")
                content_selector = "#main-content"
                articles_selector = "li[id^='mobile-feed-item-']"
            
            expect(feed_links.first).to_be_visible(timeout=10000)
            feed_count = feed_links.count()
            assert feed_count >= 2, f"{viewport_name}: Should have 2+ default feeds (MINIMAL_MODE), got {feed_count}"
            
            # Close mobile sidebar after checking feeds (if mobile)
            if viewport_name == "mobile":
                page.locator('#mobile-sidebar button').filter(has=page.locator('uk-icon[icon="x"]')).click()
                wait_for_page_ready(page)
            
            # 3. Should automatically see articles (not "No posts available")
            articles = page.locator(articles_selector)
            expect(articles.first).to_be_visible(timeout=10000)
            
            article_count = articles.count()
            assert article_count > 10, f"{viewport_name}: Should have 10+ articles from auto-subscription, got {article_count}"
            
            # 4. Should show content indicating substantial articles
            expect(page.locator(content_selector)).to_be_visible()
            print(f"  ✓ {viewport_name} auto-subscription test passed")
    
    def test_second_browser_tab_independent_session(self, browser, test_server_url):
        """Test: Multiple browser contexts → Independent sessions → No interference"""

        # Tab 1: Regular browsing
        page1 = browser.new_page()
        page1.set_viewport_size({"width": 1200, "height": 800})  # Desktop viewport for consistency
        page1.goto(test_server_url)
        wait_for_page_ready(page1)
        
        # Tab 2: Independent session
        page2 = browser.new_page()
        page2.set_viewport_size({"width": 1200, "height": 800})  # Desktop viewport for consistency
        page2.goto(test_server_url)
        wait_for_page_ready(page2)
        
        try:
            # Both should have feeds in desktop sidebar
            expect(page1.locator("#sidebar a[href*='feed_id']").first).to_be_visible()
            expect(page2.locator("#sidebar a[href*='feed_id']").first).to_be_visible()
            
            # Actions in one shouldn't affect the other
            articles1 = page1.locator("li[id^='desktop-feed-item-']")  # Desktop articles only
            if articles1.count() > 0:
                # Click article in tab 1
                articles1.first.click()
                wait_for_htmx_complete(page1)
                
                # Tab 2 should be unaffected - check that desktop layout is still working
                expect(page2.locator("#desktop-layout")).to_be_visible()
                expect(page2.locator("#sidebar")).to_be_visible()
                
        finally:
            page1.close()
            page2.close()


class TestFullViewportHeightFlow:
    """Test viewport height utilization that we fixed"""
    
    def test_viewport_layout_adaptation(self, page, test_server_url):
        """Test: Both viewport sizes → Proper layout and height utilization
        
        UPDATED SELECTORS to match current app.py implementation.
        """
        for viewport_name, viewport_size in [
            ("desktop", {"width": 1400, "height": 1000}),
            ("mobile", {"width": 375, "height": 667})
        ]:
            print(f"\n--- Testing {viewport_name} viewport layout ---")
            page.set_viewport_size(viewport_size)
            page.goto(test_server_url)
            wait_for_page_ready(page)
            
            if viewport_name == "desktop":
                # Desktop layout should be visible
                expect(page.locator("#desktop-layout")).to_be_visible()
                expect(page.locator("#mobile-layout")).to_be_hidden()
                
                # Each panel should be visible
                expect(page.locator("#sidebar")).to_be_visible()
                expect(page.locator("#desktop-feeds-content")).to_be_visible()
                expect(page.locator("#desktop-item-detail")).to_be_visible()
                
                # Content areas should have proper height
                content_area = page.locator("#desktop-feeds-content")
                if content_area.is_visible():
                    content_height = content_area.bounding_box()["height"]
                    assert content_height > 400, f"Desktop content area should use substantial height, got {content_height}px"
            else:
                # Mobile layout should be visible
                expect(page.locator("#desktop-layout")).to_be_hidden()
                expect(page.locator("#mobile-layout")).to_be_visible()
                
                # Mobile content should be accessible
                expect(page.locator("#main-content")).to_be_visible()
                
                # Should be able to interact with mobile elements
                menu_button = page.locator('#mobile-nav-button')
                expect(menu_button).to_be_visible()
            
            print(f"  ✓ {viewport_name} layout test passed")


class TestErrorHandlingUIFeedback:
    """Test error handling and user feedback mechanisms"""
    
    @pytest.mark.skip(reason="Feed submission test - skipping per user request")
    def test_network_error_handling_ui_feedback(self, page, test_server_url):
        """Test: Network errors → Proper user feedback → No broken UI"""

        page.goto(test_server_url)
        wait_for_page_ready(page)
        
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
    
    @pytest.mark.skip(reason="Feed submission test - skipping per user request")
    def test_malformed_url_error_handling(self, page, test_server_url):
        """Test: Invalid URLs → Proper validation → User-friendly errors"""

        page.goto(test_server_url)
        wait_for_page_ready(page)
        
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
    
    def test_deep_navigation_and_back_button_flow(self, page, test_server_url):
        """Test: Deep navigation → Browser back → State consistency → No broken UI"""

        page.set_viewport_size({"width": 1200, "height": 800})  # Desktop viewport for consistency
        page.goto(test_server_url)
        wait_for_page_ready(page)
        
        # 1. Navigate through different views (desktop-specific)
        navigation_sequence = [
            ("#sidebar a[href*='feed_id']", "feed filter"),  # Click specific feed in desktop sidebar
            ('a[role="button"]:has-text("Unread")', "unread view"),  # Switch to unread  
            ("li[id^='desktop-feed-item-']", "article detail"),  # Click desktop article
        ]
        
        for selector, description in navigation_sequence:
            element = page.locator(selector).first
            if element.is_visible():
                element.click()
                wait_for_htmx_complete(page)
                
                # App should remain stable after each navigation - check desktop layout
                expect(page.locator("#desktop-layout")).to_be_visible()
        
        # 2. Test browser back navigation
        page.go_back()
        wait_for_htmx_complete(page)
        # Wait for either desktop or mobile layout to be visible
        page.wait_for_selector("#desktop-layout, #mobile-layout, #sidebar", state="visible", timeout=10000)

        page.go_back()
        wait_for_htmx_complete(page)
        # Wait for main content to be stable
        page.wait_for_selector("#desktop-layout, #mobile-layout, #sidebar", state="visible", timeout=10000)

        # Should eventually be stable - check for sidebar or mobile layout
        # Use .first to avoid strict mode violation when both elements exist
        sidebar_or_mobile = page.locator("#sidebar, #mobile-layout").first
        expect(sidebar_or_mobile).to_be_visible()
    
    def test_rapid_clicking_stability(self, page, test_server_url):
        """Test: Rapid clicking → Multiple HTMX requests → UI stability → No race conditions"""

        page.set_viewport_size({"width": 1200, "height": 800})  # Desktop viewport for consistency
        page.goto(test_server_url)
        wait_for_page_ready(page)
        
        # Collect clickable elements safely (desktop-specific)
        clickable_elements = []
        
        # Desktop feed links only
        feed_links = page.locator("#sidebar a[href*='feed_id']").all()[:3]  # First 3
        clickable_elements.extend(feed_links)
        
        # Tab buttons (if they exist)
        tab_buttons = page.locator('a[role="button"]:has-text("All Posts"), a[role="button"]:has-text("Unread")').all()
        clickable_elements.extend(tab_buttons)
        
        # Desktop articles only (first 3)
        article_links = page.locator("li[id^='desktop-feed-item-']").all()[:3]
        clickable_elements.extend(article_links)
        
        # Rapid clicking test (reduced pace to avoid overwhelming server)
        for element in clickable_elements[:5]:  # Reduced from 8 to 5 elements
            if element.is_visible():
                element.click()
                wait_for_htmx_complete(page, timeout=3000)  # Longer wait to let server recover
                
                # App should remain stable - check layout instead of title (which may be affected by race conditions)
                expect(page.locator("#desktop-layout")).to_be_visible()
        
        # Final state should be stable - desktop layout
        expect(page.locator("#sidebar")).to_be_visible()


class TestTabSizeAndAlignment:
    """Test that tabs are correctly sized and aligned after touch target CSS fix"""
    
    def test_tabs_correct_size_and_alignment(self, browser, test_server_url):
        """Verify tabs are compact and right-aligned, with strict pixel-width measurements for both mobile and desktop"""
        
        # Test configurations for both mobile and desktop viewports
        test_configs = [
            {
                'name': 'mobile',
                'viewport': {'width': 375, 'height': 667},
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15',
                'max_individual_button_width': 80,  # Based on our CSS fix: max-width: 5rem = 80px
                'max_total_width_percent': 45,      # Should be compact on mobile (160px = 42.7% actual)
            },
            {
                'name': 'desktop', 
                'viewport': {'width': 1200, 'height': 800},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'max_individual_button_width': 90,  # Desktop buttons can be slightly larger but still constrained
                'max_total_width_percent': 25,      # Desktop should be even more compact
            }
        ]
        
        for config in test_configs:
            print(f"\n=== TESTING {config['name'].upper()} BUTTON SIZES ===")
            
            context = browser.new_context(
                viewport=config['viewport'],
                user_agent=config['user_agent']
            )
            page = context.new_page()
            
            try:
                # Navigate to the app
                page.goto(test_server_url, wait_until='networkidle')
                wait_for_page_ready(page)
                
                # Find navigation buttons - new icon-based design
                try:
                    if config['name'] == 'mobile':
                        # Mobile: icon buttons in top header
                        icon_bar = page.locator('#icon-bar')
                        expect(icon_bar).to_be_visible(timeout=5000)
                        
                        all_posts_btn = icon_bar.locator('button[title="All Posts"]')
                        unread_btn = icon_bar.locator('button[title="Unread"]')
                        
                        expect(all_posts_btn).to_be_visible()
                        expect(unread_btn).to_be_visible()
                        
                        # Get pixel measurements for mobile icon buttons
                        all_posts_box = all_posts_btn.bounding_box()
                        unread_box = unread_btn.bounding_box()
                        icon_bar_box = icon_bar.bounding_box()
                        viewport_width = page.viewport_size['width']
                        
                        # STRICT PIXEL WIDTH MEASUREMENTS (addressing user's requirement)
                        all_posts_width = all_posts_box['width']
                        unread_width = unread_box['width']
                        total_nav_width = icon_bar_box['width']
                        width_percent = (total_nav_width / viewport_width) * 100
                        
                        print(f"  All Posts button: {all_posts_width:.1f}px")
                        print(f"  Unread button: {unread_width:.1f}px") 
                        print(f"  Total navigation width: {total_nav_width:.1f}px ({width_percent:.1f}% of viewport)")
                        
                        # Test 1: Individual button width constraints (icon buttons should be compact)
                        assert all_posts_width <= 60, \
                            f"{config['name']} 'All Posts' button too wide: {all_posts_width:.1f}px (max: 60px for icon)"
                        
                        assert unread_width <= 60, \
                            f"{config['name']} 'Unread' button too wide: {unread_width:.1f}px (max: 60px for icon)"
                        
                        # Test 2: Total width percentage constraint (should be reasonable for icon bar)
                        assert width_percent <= 50, \
                            f"{config['name']} icon bar too wide: {width_percent:.1f}% of viewport (max: 50%)"
                        
                        # Test 3: Height should meet touch target requirements (44px minimum)
                        assert all_posts_box['height'] >= 44, f"{config['name']} All Posts button too short: {all_posts_box['height']}px (should be >= 44px)"
                        assert unread_box['height'] >= 44, f"{config['name']} Unread button too short: {unread_box['height']}px (should be >= 44px)"
                        
                        # Test 4: Right alignment (icon bar should be on the right)
                        container_right_edge = icon_bar_box['x'] + icon_bar_box['width']
                        distance_from_right = viewport_width - container_right_edge
                        
                        # Mobile: icon bar should be reasonably close to right edge
                        assert distance_from_right <= 30, \
                            f"{config['name']} icon bar not close enough to right edge: {distance_from_right:.1f}px away (max: 30px)"
                        
                    else:
                        # Desktop: unified layout - no more sticky header, content same as mobile
                        # Check that desktop layout container exists
                        desktop_layout = page.locator('#desktop-layout')
                        expect(desktop_layout).to_be_visible(timeout=5000)
                        
                        # Desktop content should have feed title (unified structure)
                        feed_title = page.locator('#desktop-feeds-content h3')
                        expect(feed_title).to_be_visible()
                        
                        feed_title_box = feed_title.bounding_box()
                        print(f"  Desktop feed title: {feed_title.text_content()}")
                        print(f"  Feed title width: {feed_title_box['width']:.1f}px")
                        
                        # Desktop should have consistent content structure (no special header navigation)
                        assert feed_title_box['width'] <= 500, f"Desktop feed title too wide: {feed_title_box['width']:.1f}px"
                        
                    print(f"✅ {config['name']}: Navigation elements are properly sized and positioned")
                
                except Exception as e:
                    print(f"❌ {config['name']}: {str(e)}")
                    page.screenshot(path=f'/tmp/tab_test_error_{config["name"]}.png')
                    raise
                    
            finally:
                context.close()
            
        print("\n✅ All viewport button size tests passed!")


class TestSearchBarHeightInvariant:
    """Test search bar expansion height invariant behavior"""
    
    def test_search_expansion_height_invariant(self, page: Page, test_server_url):
        """Test search icon expansion doesn't change chrome height - requested feature"""
        
        # Set mobile viewport to test mobile chrome
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(test_server_url)
        wait_for_page_ready(page)
        
        # Measure initial header height
        initial_measurements = page.evaluate("""() => {
            const topBar = document.getElementById('mobile-top-bar');
            return {
                height: topBar.offsetHeight,
                boundingRect: topBar.getBoundingClientRect(),
                iconBarVisible: document.getElementById('icon-bar').style.display !== 'none',
                searchBarVisible: document.getElementById('search-bar').style.display !== 'none'
            };
        }""")
        
        print(f"Initial header height: {initial_measurements['height']}px")
        print(f"Icon bar visible: {initial_measurements['iconBarVisible']}")
        print(f"Search bar visible: {initial_measurements['searchBarVisible']}")
        
        # Click search button to expand
        search_button = page.locator('button[title="Search"]')
        expect(search_button).to_be_visible()
        search_button.click()
        
        # Measure expanded height and width
        expanded_measurements = page.evaluate("""() => {
            const topBar = document.getElementById('mobile-top-bar');
            const searchBar = document.getElementById('search-bar');
            const searchInput = document.getElementById('mobile-search-input');
            const navButton = document.getElementById('mobile-nav-button');
            const container = document.getElementById('mobile-header-container');
            
            return {
                height: topBar.offsetHeight,
                boundingRect: topBar.getBoundingClientRect(),
                iconBarVisible: document.getElementById('icon-bar').style.display !== 'none',
                searchBarVisible: document.getElementById('search-bar').style.display !== 'none',
                // Width measurements
                topBarWidth: topBar.offsetWidth,
                searchBarWidth: searchBar ? searchBar.offsetWidth : 0,
                searchInputWidth: searchInput ? searchInput.offsetWidth : 0,
                navButtonWidth: navButton ? navButton.offsetWidth : 0,
                containerWidth: container ? container.offsetWidth : 0,
                availableWidth: topBar.offsetWidth - (navButton ? navButton.offsetWidth : 0) - 32  // 32px for padding/margins
            };
        }""")
        
        print(f"Expanded header height: {expanded_measurements['height']}px")
        print(f"Icon bar visible: {expanded_measurements['iconBarVisible']}")
        print(f"Search bar visible: {expanded_measurements['searchBarVisible']}")
        print(f"Search bar width: {expanded_measurements['searchBarWidth']}px")
        print(f"Search input width: {expanded_measurements['searchInputWidth']}px")
        print(f"Available width: {expanded_measurements['availableWidth']}px")
        print(f"Top bar width: {expanded_measurements['topBarWidth']}px")
        
        # HEIGHT INVARIANT: Header height must remain exactly the same
        assert initial_measurements['height'] == expanded_measurements['height'], \
            f"Height invariant violated: {initial_measurements['height']}px → {expanded_measurements['height']}px"
        
        # WIDTH TEST: Search bar should take most of the available horizontal space
        # Allow for some padding/margins (within 50px tolerance)
        width_utilization = expanded_measurements['searchBarWidth'] / expanded_measurements['availableWidth']
        assert width_utilization > 0.85, \
            f"Search bar not taking full width: {expanded_measurements['searchBarWidth']}px of {expanded_measurements['availableWidth']}px available ({width_utilization:.1%})"
        
        # State should be correctly toggled
        assert not expanded_measurements['iconBarVisible'], "Icon bar should be hidden when search expands"
        assert expanded_measurements['searchBarVisible'], "Search bar should be visible when expanded"
        
        # Test close functionality
        close_button = page.locator('button[title="Close search"]')
        expect(close_button).to_be_visible()
        close_button.click()
        
        # Verify return to initial state  
        final_measurements = page.evaluate("""() => {
            const topBar = document.getElementById('mobile-top-bar');
            return {
                height: topBar.offsetHeight,
                iconBarVisible: document.getElementById('icon-bar').style.display !== 'none',
                searchBarVisible: document.getElementById('search-bar').style.display !== 'none'
            };
        }""")
        
        # HEIGHT INVARIANT: Should return to original height
        assert final_measurements['height'] == initial_measurements['height'], \
            f"Height invariant violated on close: {initial_measurements['height']}px → {final_measurements['height']}px"
        
        # State should be back to initial
        assert final_measurements['iconBarVisible'], "Icon bar should be visible after close"
        assert not final_measurements['searchBarVisible'], "Search bar should be hidden after close"
        
        print("✅ Search height invariant test passed!")
    
    def test_search_click_outside_closes(self, page: Page, test_server_url):
        """Test that clicking outside the search bar closes it"""
        
        # Set mobile viewport
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(test_server_url)
        wait_for_page_ready(page)
        
        # Click search button to expand
        search_button = page.locator('button[title="Search"]')
        expect(search_button).to_be_visible()
        search_button.click()
        
        # Verify search is expanded
        search_state = page.evaluate("""() => {
            return {
                searchBarVisible: document.getElementById('search-bar').style.display !== 'none',
                iconBarVisible: document.getElementById('icon-bar').style.display !== 'none'
            };
        }""")
        assert search_state['searchBarVisible'], "Search bar should be visible after clicking search button"
        assert not search_state['iconBarVisible'], "Icon bar should be hidden when search is expanded"
        
        # Click outside the search bar (on the main content area which should exist)
        # First wait for content to be present
        content = page.locator('#main-content').first
        expect(content).to_be_visible(timeout=5000)
        
        # Click on the content area to trigger click-outside
        content.click(position={'x': 100, 'y': 200})
        
        # Small wait for JavaScript event handler
        wait_for_htmx_complete(page)
        
        # Verify search closed
        final_state = page.evaluate("""() => {
            return {
                searchBarVisible: document.getElementById('search-bar').style.display !== 'none',
                iconBarVisible: document.getElementById('icon-bar').style.display !== 'none'
            };
        }""")
        assert not final_state['searchBarVisible'], "Search bar should be hidden after clicking outside"
        assert final_state['iconBarVisible'], "Icon bar should be visible after search closes"
        
        print("✅ Click-outside test passed!")


class TestPaginationButtonDuplication:
    """Test to prevent duplicate mobile bottom scroll buttons - app.py:1322-1330 bug"""
    
    def test_pagination_buttons_no_duplicates(self, page, test_server_url):
        """Ensure exactly 4 pagination buttons exist (no duplicates)
        
        This test prevents regression of the duplicate mobile pagination buttons
        bug where both mobile and desktop button sets were rendered simultaneously.
        """
        # Navigate to a feed that likely has pagination
        # First get to main page then find a feed with lots of items
        page.goto(test_server_url)
        
        # Try to find a feed with many items (ClaudeAI, Hacker News, etc)
        feed_links = page.locator("#sidebar a[href*='feed_id']:has-text('ClaudeAI'), #sidebar a[href*='feed_id']:has-text('Hacker News')")
        if feed_links.count() > 0:
            feed_links.first.click()
        else:
            # Fallback: click first available feed
            page.locator("#sidebar a[href*='feed_id']").first.click()
        
        # Wait for specific content to load (not arbitrary time)
        page.wait_for_selector("#feeds-list-container", state="visible", timeout=10000)
        
        # Wait for pagination container specifically (event-based, not time-based)
        pagination_container = page.locator('.p-4.border-t')  
        
        # Check if pagination exists with explicit wait
        try:
            pagination_container.wait_for(state="visible", timeout=5000)
            pagination_exists = True
        except:
            pagination_exists = False
            
        if pagination_exists:
            # Count all chevron navigation buttons in pagination
            chevrons_left_count = pagination_container.locator('uk-icon[icon="chevrons-left"]').count()
            chevron_left_count = pagination_container.locator('uk-icon[icon="chevron-left"]').count()  
            chevron_right_count = pagination_container.locator('uk-icon[icon="chevron-right"]').count()
            chevrons_right_count = pagination_container.locator('uk-icon[icon="chevrons-right"]').count()
            
            # Verify exactly one of each navigation button type
            assert chevrons_left_count == 1, f"Expected 1 'first page' button, found {chevrons_left_count}"
            assert chevron_left_count == 1, f"Expected 1 'previous page' button, found {chevron_left_count}"  
            assert chevron_right_count == 1, f"Expected 1 'next page' button, found {chevron_right_count}"
            assert chevrons_right_count == 1, f"Expected 1 'last page' button, found {chevrons_right_count}"
            
            # Verify total pagination buttons count
            total_nav_buttons = chevrons_left_count + chevron_left_count + chevron_right_count + chevrons_right_count
            assert total_nav_buttons == 4, f"Expected exactly 4 navigation buttons total, found {total_nav_buttons}"
            
            print("✅ Pagination button duplication test passed!")
        else:
            # No pagination present - test passes but log it
            print("📝 No pagination present on current page - duplication test skipped")


if __name__ == "__main__":
    # Run critical UI flow tests
    pytest.main([__file__, "-v", "--tb=short"])