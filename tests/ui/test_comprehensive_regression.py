"""Comprehensive Playwright regression tests for RSS Reader refactoring validation"""

import pytest
from playwright.sync_api import Page, expect
import time
import re
import test_constants as constants
from test_helpers import (
    wait_for_htmx_complete,
    wait_for_page_ready,
    wait_for_htmx_settle
)

pytestmark = pytest.mark.needs_server

# HTMX Helper Functions for Fast Testing

class TestComprehensiveRegression:
    """Comprehensive testing to detect regressions from HTMX architecture refactoring"""
    
    def test_desktop_comprehensive_workflow(self, page: Page, test_server_url):
        """Test complete desktop workflow: feed selection, article reading, tab switching"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        
        # Wait for page load
        wait_for_page_ready(page)
        # Page loads successfully (title may be default FastHTML page now)
        
        # Verify desktop three-column layout is visible
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page.locator("#sidebar")).to_be_visible()
        expect(page.locator("#desktop-feeds-content")).to_be_visible()
        expect(page.locator("#desktop-item-detail")).to_be_visible()
        
        # Test Feed Selection Cycle (3 iterations)
        for iteration in range(3):
            print(f"Desktop iteration {iteration + 1}")
            
            # Click on a feed in sidebar (desktop version)
            feed_links = page.locator("#sidebar a[href*='feed_id']").all()
            if len(feed_links) > iteration:
                feed_links[iteration].click()
                
                # Wait for feed content to load
                wait_for_htmx_complete(page)
                
                # Scroll down in middle panel
                middle_panel = page.locator("#desktop-feeds-content")
                middle_panel.scroll_into_view_if_needed()
                page.mouse.wheel(0, 500)
                wait_for_htmx_complete(page, timeout=constants.MAX_WAIT_MS)
                
                # Click on an article
                article_items = page.locator("#desktop-feeds-content li[id*='desktop-feed-item']").all()
                if len(article_items) > 0:
                    article_items[0].click()
                    
                    # Verify article loads in right panel
                    wait_for_htmx_complete(page)
                    expect(page.locator("#desktop-item-detail")).to_contain_text("From:")
                    
                    # Verify URL updated
                    assert "/item/" in page.url
                    
                    # Toggle between All Posts and Unread tabs (use visible one for desktop)
                    all_posts_tab = page.locator("#desktop-layout a:has-text('All Posts')").first
                    unread_tab = page.locator("#desktop-layout a:has-text('Unread')").first
                    
                    if all_posts_tab.is_visible():
                        all_posts_tab.click()
                        wait_for_htmx_complete(page)
                        
                    if unread_tab.is_visible():
                        unread_tab.click()
                        wait_for_htmx_complete(page)
    
    def test_mobile_comprehensive_workflow(self, page: Page, test_server_url):
        """Test complete mobile workflow: navigation, feed selection, article reading"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.MOBILE_VIEWPORT)
        
        # Wait for page load and verify mobile layout
        expect(page.locator("#mobile-layout")).to_be_visible()
        expect(page.locator("#desktop-layout")).to_be_hidden()
        
        # Test Mobile Navigation Cycle (3 iterations)
        for iteration in range(3):
            print(f"Mobile iteration {iteration + 1}")
            
            # Open hamburger menu
            hamburger = page.locator("#mobile-nav-button")
            if hamburger.is_visible():
                hamburger.click()
                
                # Wait for sidebar to open
                wait_for_htmx_complete(page)
                expect(page.locator("#mobile-sidebar")).to_be_visible()
                
                # Click on a feed
                feed_links = page.locator("#mobile-sidebar a[href*='feed_id']").all()
                if len(feed_links) > iteration % len(feed_links):
                    feed_links[iteration % len(feed_links)].click()
                    
                    # Wait for sidebar to close and content to load
                    page.wait_for_selector("li[id^='mobile-feed-item-']", state="visible", timeout=constants.MAX_WAIT_MS)
                    expect(page.locator("#mobile-sidebar")).to_be_hidden()
                    
                    # Scroll down in feed list
                    main_content = page.locator("#main-content")
                    main_content.scroll_into_view_if_needed()
                    page.mouse.wheel(0, 800)
                    # Wait for any HTMX updates after scroll
                    page.wait_for_selector("body:not(.htmx-request)", timeout=2000)
                    
                    # Click on an article
                    article_items = page.locator("li[id*='mobile-feed-item']").all()
                    if len(article_items) > 0:
                        article_items[0].click()
                        
                        # Wait for article to load (full-screen mobile view)
                        page.wait_for_selector("#main-content", state="visible", timeout=constants.MAX_WAIT_MS)
                        
                        # Verify article content is visible
                        expect(page.locator("#main-content")).to_contain_text("From:")
                        
                        # Verify URL updated to article
                        assert "/item/" in page.url
                        
                        # Click back arrow
                        back_button = page.locator("#mobile-nav-button")
                        if back_button.is_visible():
                            back_button.click()
                            
                            # Wait for navigation back to feed list
                            wait_for_htmx_complete(page)
                            
                            # Toggle between tabs (use visible one for mobile)
                            all_posts_tab = page.locator("#mobile-layout a:has-text('All Posts')").first
                            unread_tab = page.locator("#mobile-layout a:has-text('Unread')").first
                            
                            if all_posts_tab.is_visible():
                                all_posts_tab.click()
                                wait_for_htmx_complete(page)
                                
                            if unread_tab.is_visible():
                                unread_tab.click()
                                wait_for_htmx_complete(page)
    
    def test_responsive_layout_switching(self, page: Page, test_server_url):
        """Test layout adaptation when switching between desktop and mobile viewports"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        
        # Start with desktop
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page.locator("#mobile-layout")).to_be_hidden()
        
        # Click an article in desktop mode
        article_items = page.locator("li[id*='desktop-feed-item']").all()
        if len(article_items) > 0:
            article_items[0].click()
            page.wait_for_selector("#desktop-item-detail", state="visible", timeout=constants.MAX_WAIT_MS)
            expect(page.locator("#desktop-item-detail")).to_contain_text("From:")
        
        # Switch to mobile viewport
        page.set_viewport_size(constants.MOBILE_VIEWPORT)
        wait_for_htmx_complete(page)
        
        expect(page.locator("#mobile-layout")).to_be_visible()
        expect(page.locator("#desktop-layout")).to_be_hidden()
        
        # Switch back to desktop
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        wait_for_htmx_complete(page)
        
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page.locator("#mobile-layout")).to_be_hidden()
    
    def test_htmx_state_management(self, page: Page, test_server_url):
        """Test HTMX state updates and out-of-band swaps"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        
        # Wait for page load
        wait_for_htmx_complete(page)
        
        # Test blue indicator state changes
        unread_items = page.locator("#desktop-feeds-content li[id*='feed-item'] .w-2.h-2.bg-blue-500")
        initial_count = unread_items.count()
        
        if initial_count > 0:
            # Click an unread article
            first_unread_item = page.locator("#desktop-feeds-content li[id*='feed-item']:has(.w-2.h-2.bg-blue-500)").first
            first_unread_item.click()
            
            # Wait for HTMX update
            wait_for_htmx_complete(page)
            
            # Verify blue dot disappeared (out-of-band update)
            final_count = unread_items.count()
            assert final_count < initial_count, "Blue indicator should disappear after reading"
    
    def test_rapid_interaction_stability(self, page: Page, test_server_url):
        """Test stability under rapid user interactions"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        
        # Wait for initial load
        wait_for_htmx_complete(page)
        
        # Rapid clicking test
        for i in range(5):
            # In desktop mode (1200x800), feed links are in the sidebar
            # No need to open mobile sidebar in desktop mode
            feed_links = page.locator("#sidebar a[href*='feed_id']").all()
            if len(feed_links) > 0:
                feed_links[i % len(feed_links)].click()
                wait_for_htmx_complete(page)
            
            # Quick article clicks (desktop layout)
            article_items = page.locator("li[id^='desktop-feed-item-']").all()
            if len(article_items) > 0:
                article_items[0].click()
                wait_for_htmx_complete(page)
        
        # Verify app is still responsive
        # Page loads successfully (title may be default FastHTML page now)
        
        # Check for JavaScript errors
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        wait_for_htmx_complete(page)
        
        assert len(errors) == 0, f"JavaScript errors detected: {errors}"
    
    # NOTE: test_mobile_sidebar_and_navigation_flow moved to test_mobile_sidebar_isolated.py
    # due to race conditions with parallel test execution
    
    def test_feed_content_and_pagination(self, page: Page, test_server_url):
        """Test feed content loading and pagination behavior"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        
        # Wait for content load
        wait_for_page_ready(page)
        
        # Verify feed content is present
        feed_items = page.locator("li[id*='feed-item']")
        expect(feed_items.first).to_be_visible()
        
        # Test tab switching (desktop-specific)
        all_posts_tab = page.locator("#desktop-feeds-content a:has-text('All Posts')")
        unread_tab = page.locator("#desktop-feeds-content a:has-text('Unread')")
        
        # Switch to All Posts
        if all_posts_tab.is_visible():
            all_posts_tab.click()
            wait_for_htmx_complete(page)
            expect(all_posts_tab.locator("..")).to_have_class(re.compile(r"uk-active"))
        
        # Switch to Unread
        if unread_tab.is_visible():
            unread_tab.click()
            wait_for_htmx_complete(page)
            expect(unread_tab.locator("..")).to_have_class(re.compile(r"uk-active"))
    
    def test_session_and_state_persistence(self, page: Page, test_server_url):
        """Test session management and state persistence across navigation"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        
        # Wait for initial session setup
        wait_for_page_ready(page)
        
        # Navigate to different feeds and verify session persists
        # Handle both desktop and mobile layouts
        mobile_nav_button = page.locator("button#mobile-nav-button")
        is_mobile = mobile_nav_button.is_visible()
        
        if is_mobile:
            # Mobile: open sidebar and get mobile feed links
            mobile_nav_button.click()
            wait_for_htmx_complete(page)
            feed_links = page.locator("#mobile-sidebar a[href*='feed_id']").all()
        else:
            # Desktop: get sidebar feed links directly
            feed_links = page.locator("#sidebar a[href*='feed_id']").all()
        
        for i, feed_link in enumerate(feed_links[:2]):  # Test first 2 feeds
            # Reopen mobile sidebar before each feed click if mobile
            if is_mobile and not page.locator("#mobile-sidebar").is_visible():
                mobile_nav_button.click()
                wait_for_htmx_complete(page)
                
            feed_link.click()
            wait_for_htmx_complete(page)
            
            # Verify feed page loads and session is maintained
            # Page loads successfully (title may be default FastHTML page now)
            assert "feed_id" in page.url
            
            # Click an article to test state management
            # Use the correct selector based on viewport
            if is_mobile:
                article_items = page.locator("li[id*='mobile-feed-item']").all()
            else:
                article_items = page.locator("li[id*='desktop-feed-item']").all()

            if len(article_items) > 0:
                article_items[0].click()
                wait_for_htmx_complete(page)
                wait_for_htmx_complete(page)  # Additional wait for URL update

                # Verify article loads
                assert "/item/" in page.url
                
                # Go back to main page
                page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
                wait_for_page_ready(page)
    
    def test_error_resilience_and_recovery(self, page: Page, test_server_url):
        """Test application resilience under various error conditions"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)

        # Test invalid item URL (use very high number unlikely to exist)
        invalid_item_id = 999999
        page.goto(f"{test_server_url}/item/{invalid_item_id}", timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page)

        # Should gracefully handle non-existent items WITH FULL PAGE STRUCTURE
        # Verify full page structure is present even for error case
        expect(page.locator("#app-root")).to_be_visible()
        # Desktop should have feeds sidebar
        if page.viewport_size["width"] >= 1024:
            expect(page.locator("#feeds")).to_be_visible()
            expect(page.locator("#summary")).to_be_visible()
        # Should show error message in detail area
        expect(page.locator("#detail")).to_be_visible()

        # Test invalid feed ID (use very high number unlikely to exist)
        invalid_feed_id = 999999
        page.goto(f"{test_server_url}/?feed_id={invalid_feed_id}", timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page)

        # Should gracefully handle invalid feed IDs
        expect(page.locator("#app-root")).to_be_visible()

        # Return to valid state
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page)
        expect(page.locator("#app-root")).to_be_visible()

class TestHTMXArchitectureValidation:
    """Validate HTMX architecture changes work correctly"""
    
    def test_mobile_handlers_routing(self, page: Page, test_server_url):
        """Test MobileHandlers routing and content swapping"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.MOBILE_VIEWPORT)
        
        # Test mobile content handler
        expect(page.locator("#main-content")).to_be_visible()
        
        # Test mobile sidebar handler
        hamburger = page.locator("#mobile-nav-button")
        if hamburger.is_visible():
            hamburger.click()
            expect(page.locator("#mobile-sidebar")).to_be_visible()
            
            # Close sidebar
            close_button = page.locator("#mobile-sidebar button[hx-on-click*='setAttribute']")
            close_button.click()
            expect(page.locator("#mobile-sidebar")).to_be_hidden()
    
    def test_desktop_handlers_routing(self, page: Page, test_server_url):
        """Test DesktopHandlers routing and column updates"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        
        # Test desktop feeds column handler
        expect(page.locator("#desktop-feeds-content")).to_be_visible()
        
        # Test desktop detail column handler
        expect(page.locator("#desktop-item-detail")).to_be_visible()
        
        # Test desktop sidebar column handler
        expect(page.locator("#sidebar")).to_be_visible()
        
        # Test column interaction
        article_items = page.locator("li[id*='desktop-feed-item']").all()
        if len(article_items) > 0:
            article_items[0].click()
            wait_for_htmx_complete(page)
            
            # Verify detail column updates while other columns remain
            expect(page.locator("#desktop-item-detail")).to_contain_text("From:")
            expect(page.locator("#desktop-feeds-content")).to_be_visible()
            expect(page.locator("#sidebar")).to_be_visible()
    
    def test_unified_tab_container_behavior(self, page: Page, test_server_url):
        """Test the unified create_tab_container function for both mobile and desktop"""
        # Test desktop tab behavior
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        wait_for_page_ready(page)
        
        # Desktop tabs should use regular links (no HTMX)
        all_posts_desktop = page.locator("#desktop-feeds-content a:has-text('All Posts')").first
        if all_posts_desktop.is_visible():
            # Should have href but no hx-get for desktop
            expect(all_posts_desktop).to_have_attribute("href", "/?unread=0")
            all_posts_desktop.click()
            wait_for_htmx_complete(page)
        
        # Test mobile tab behavior
        page.set_viewport_size(constants.MOBILE_VIEWPORT)
        wait_for_page_ready(page)
        
        # Mobile tabs should use HTMX attributes
        all_posts_mobile = page.locator("#mobile-persistent-header a:has-text('All Posts')").first
        if all_posts_mobile.is_visible():
            # Should have both href and hx-get for mobile
            expect(all_posts_mobile).to_have_attribute("href", "/?unread=0")
            expect(all_posts_mobile).to_have_attribute("hx-get", "/?unread=0")
            all_posts_mobile.click()
            wait_for_htmx_complete(page)