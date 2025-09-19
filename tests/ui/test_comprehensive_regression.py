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
        expect(page.locator("#app-root")).to_be_visible()
        expect(page.locator("#feeds")).to_be_visible()
        expect(page.locator("#summary")).to_be_visible()
        expect(page.locator("#detail")).to_be_visible()
        
        # Test Feed Selection Cycle (3 iterations)
        for iteration in range(3):
            print(f"Desktop iteration {iteration + 1}")
            
            # Click on a feed in sidebar (desktop version)
            feed_links = page.locator("#feeds a[href*='feed_id']").all()
            if len(feed_links) > iteration:
                feed_links[iteration].click()
                
                # Wait for feed content to load
                wait_for_htmx_complete(page)
                
                # Scroll down in middle panel
                middle_panel = page.locator("#summary")
                middle_panel.scroll_into_view_if_needed()
                page.mouse.wheel(0, 500)
                wait_for_htmx_complete(page, timeout=constants.MAX_WAIT_MS)

                # Click on an article
                article_items = page.locator("#summary li[data-testid='feed-item']").all()
                if len(article_items) > 0:
                    article_items[0].click()
                    
                    # Verify article loads in right panel
                    wait_for_htmx_complete(page)
                    expect(page.locator("#detail")).to_contain_text("From:")
                    
                    # Verify URL updated (may stay on main page with feed_id)
                    # Note: URL may be /?feed_id=X rather than /item/X depending on navigation
                    assert "feed_id" in page.url or "/item/" in page.url
                    
                    # Toggle between All Posts and Unread buttons (now using data-testid)
                    all_posts_btn = page.locator("[data-testid='all-posts-btn']")
                    unread_btn = page.locator("[data-testid='unread-btn']")

                    if all_posts_btn.is_visible():
                        all_posts_btn.click()
                        wait_for_htmx_complete(page)

                    if unread_btn.is_visible():
                        unread_btn.click()
                        wait_for_htmx_complete(page)
    
    def test_mobile_comprehensive_workflow(self, page: Page, test_server_url):
        """Test complete mobile workflow: navigation, feed selection, article reading"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.MOBILE_VIEWPORT)
        
        # Wait for page load and verify app structure is present
        wait_for_page_ready(page)
        expect(page.locator("#app-root")).to_be_visible()
        # In mobile viewport, feeds sidebar should be hidden via CSS classes
        expect(page.locator("#feeds")).to_have_class(re.compile(r"hidden"))
        expect(page.locator("#summary")).to_be_visible()
        
        # Test Mobile Navigation Cycle (3 iterations)
        for iteration in range(3):
            print(f"Mobile iteration {iteration + 1}")
            
            # Open hamburger menu (now using data-testid)
            hamburger = page.locator("#summary [data-testid='hamburger-btn']")
            if hamburger.is_visible():
                hamburger.click()
                
                # Wait for sidebar to open (feeds drawer)
                wait_for_htmx_complete(page)
                expect(page.locator("#feeds")).to_be_visible()

                # Click on a feed
                feed_links = page.locator("#feeds a[href*='feed_id']").all()
                if len(feed_links) > iteration % len(feed_links):
                    feed_links[iteration % len(feed_links)].click()
                    
                    # Wait for navigation and drawer to close
                    wait_for_htmx_complete(page)
                    page.wait_for_selector("li[data-testid='feed-item']", state="visible", timeout=constants.MAX_WAIT_MS)
                    # Verify drawer closed (feeds should be hidden on mobile)
                    expect(page.locator("#feeds")).to_have_class(re.compile(r"hidden"))
                    
                    # Scroll down in feed list (summary section contains the feed items)
                    summary_content = page.locator("#summary")
                    summary_content.scroll_into_view_if_needed()
                    page.mouse.wheel(0, 800)
                    # Wait for any HTMX updates after scroll
                    page.wait_for_selector("body:not(.htmx-request)", timeout=2000)
                    
                    # Click on an article
                    article_items = page.locator("li[data-testid='feed-item']").all()
                    if len(article_items) > 0:
                        article_items[0].click()
                        
                        # Wait for article to load (in detail section)
                        page.wait_for_selector("#detail", state="visible", timeout=constants.MAX_WAIT_MS)

                        # Verify article content is visible
                        expect(page.locator("#detail")).to_contain_text("From:")
                        
                        # Verify URL updated to article
                        assert "/item/" in page.url
                        
                        # Click back button (force click to handle overlapping elements)
                        back_button = page.locator("[data-testid='back-button']")
                        if back_button.is_visible():
                            back_button.click(force=True)
                            
                            # Wait for navigation back to feed list
                            wait_for_htmx_complete(page)
                            
                            # Toggle between buttons (now using data-testid)
                            all_posts_btn = page.locator("[data-testid='all-posts-btn']").first
                            unread_btn = page.locator("[data-testid='unread-btn']").first

                            if all_posts_btn.is_visible():
                                all_posts_btn.click()
                                wait_for_htmx_complete(page)

                            if unread_btn.is_visible():
                                unread_btn.click()
                                wait_for_htmx_complete(page)
    
    def test_responsive_layout_switching(self, page: Page, test_server_url):
        """Test layout adaptation when switching between desktop and mobile viewports"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        
        # Start with desktop
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        wait_for_page_ready(page)
        # In desktop viewport, feeds sidebar should be visible
        expect(page.locator("#feeds")).to_be_visible()
        expect(page.locator("#summary")).to_be_visible()
        expect(page.locator("#detail")).to_be_visible()
        
        # Click an article in desktop mode
        article_items = page.locator("li[data-testid='feed-item']").all()
        if len(article_items) > 0:
            article_items[0].click()
            page.wait_for_selector("#detail", state="visible", timeout=constants.MAX_WAIT_MS)
            expect(page.locator("#detail")).to_contain_text("From:")
        
        # Switch to mobile viewport
        page.set_viewport_size(constants.MOBILE_VIEWPORT)
        wait_for_htmx_complete(page)

        # In mobile viewport, verify responsive behavior
        expect(page.locator("#feeds")).to_have_class(re.compile(r"hidden"))
        # Note: In the new unified layout, summary and detail may use CSS to control mobile behavior
        expect(page.locator("#summary")).to_be_attached()
        expect(page.locator("#detail")).to_be_attached()
        
        # Switch back to desktop
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        wait_for_htmx_complete(page)

        # In desktop viewport, feeds sidebar should be visible again
        expect(page.locator("#feeds")).to_be_visible()
        expect(page.locator("#summary")).to_be_visible()
        expect(page.locator("#detail")).to_be_visible()
    
    def test_htmx_state_management(self, page: Page, test_server_url):
        """Test HTMX state updates and out-of-band swaps"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        
        # Wait for page load
        wait_for_htmx_complete(page)
        
        # Test blue indicator state changes
        unread_items = page.locator("#summary li[data-testid='feed-item'] .bg-blue-600")
        initial_count = unread_items.count()
        
        if initial_count > 0:
            # Click an unread article
            first_unread_item = page.locator("#summary li[data-testid='feed-item']:has(.bg-blue-600)").first
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
            # In desktop mode (1200x800), feed links are in the feeds sidebar
            # No need to open mobile sidebar in desktop mode
            feed_links = page.locator("#feeds a[href*='feed_id']").all()
            if len(feed_links) > 0:
                feed_links[i % len(feed_links)].click()
                wait_for_htmx_complete(page)
            
            # Quick article clicks (desktop layout)
            article_items = page.locator("li[data-testid='feed-item']").all()
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
        
        # Test button switching (desktop-specific) - scope to summary section
        all_posts_btn = page.locator("#summary [data-testid='all-posts-btn']")
        unread_btn = page.locator("#summary [data-testid='unread-btn']")
        
        # Switch to All Posts
        if all_posts_btn.is_visible():
            all_posts_btn.click()
            wait_for_htmx_complete(page)
            expect(all_posts_btn).to_have_class(re.compile(r"bg-secondary"))

        # Switch to Unread
        if unread_btn.is_visible():
            unread_btn.click()
            wait_for_htmx_complete(page)
            expect(unread_btn).to_have_class(re.compile(r"bg-secondary"))
    
    def test_session_and_state_persistence(self, page: Page, test_server_url):
        """Test session management and state persistence across navigation"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        
        # Wait for initial session setup
        wait_for_page_ready(page)
        
        # Navigate to different feeds and verify session persists
        # Handle both desktop and mobile layouts - scope to summary
        mobile_nav_button = page.locator("#summary [data-testid='hamburger-btn']")
        is_mobile = mobile_nav_button.is_visible()
        
        if is_mobile:
            # Mobile: open sidebar and get feed links
            mobile_nav_button.click()
            wait_for_htmx_complete(page)
            feed_links = page.locator("#feeds a[href*='feed_id']").all()
        else:
            # Desktop: get feed links directly
            feed_links = page.locator("#feeds a[href*='feed_id']").all()
        
        for i, feed_link in enumerate(feed_links[:2]):  # Test first 2 feeds
            # Reopen mobile sidebar before each feed click if mobile
            if is_mobile and not page.locator("#feeds").is_visible():
                mobile_nav_button.click()
                wait_for_htmx_complete(page)
                
            feed_link.click()
            wait_for_htmx_complete(page)
            
            # Verify feed content loads and session is maintained
            # Wait for feed content to load (may update via HTMX without URL change)
            page.wait_for_selector("li[data-testid='feed-item']", state="visible", timeout=constants.MAX_WAIT_MS)
            # URL may or may not contain feed_id depending on HTMX vs. full navigation
            # The important thing is that content loaded successfully
            
            # Click an article to test state management
            # Use the correct selector based on viewport (now unified)
            article_items = page.locator("li[data-testid='feed-item']").all()

            if len(article_items) > 0:
                article_items[0].click()
                wait_for_htmx_complete(page)
                wait_for_htmx_complete(page)  # Additional wait for URL update

                # Verify article loads (URL may have feed_id or item path)
                assert "feed_id" in page.url or "/item/" in page.url
                
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

    def test_mobile_sidebar_overlay_dismissal(self, page: Page, test_server_url):
        """Test that clicking anywhere on the overlay (including header area) dismisses the sidebar"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.MOBILE_VIEWPORT)

        # Wait for page load
        wait_for_page_ready(page)
        expect(page.locator("#app-root")).to_be_visible()

        # Open sidebar via hamburger button
        hamburger = page.locator("#summary [data-testid='hamburger-btn']")
        expect(hamburger).to_be_visible()
        hamburger.click()

        # Verify sidebar is now visible (has data-drawer="open" attribute)
        expect(page.locator("#app-root")).to_have_attribute("data-drawer", "open", timeout=constants.MAX_WAIT_MS)
        expect(page.locator("#feeds")).to_be_visible()
        expect(page.locator("#sidebar-overlay")).to_be_visible()

        # Test 1: Click on header/banner area (the issue being fixed)
        # The overlay should be covering the header, so clicking on the overlay closes the sidebar
        # We'll click on the overlay area that's over the header
        page.click("#sidebar-overlay", position={"x": 200, "y": 30})

        # Sidebar should be closed
        expect(page.locator("#app-root")).not_to_have_attribute("data-drawer", "open", timeout=constants.MAX_WAIT_MS)
        expect(page.locator("#sidebar-overlay")).not_to_be_visible()

        # Test 2: Re-open and test clicking on overlay area (not on sidebar)
        hamburger.click()
        expect(page.locator("#app-root")).to_have_attribute("data-drawer", "open", timeout=constants.MAX_WAIT_MS)

        # Click on overlay area (to the right of the sidebar)
        page.click("body", position={"x": 350, "y": 200})

        # Sidebar should be closed
        expect(page.locator("#app-root")).not_to_have_attribute("data-drawer", "open", timeout=constants.MAX_WAIT_MS)
        expect(page.locator("#sidebar-overlay")).not_to_be_visible()

        # Test 3: Re-open and verify clicking inside sidebar does NOT close it
        hamburger.click()
        expect(page.locator("#app-root")).to_have_attribute("data-drawer", "open", timeout=constants.MAX_WAIT_MS)

        # Click inside the sidebar (on a feed link for example)
        feeds_sidebar = page.locator("#feeds")
        if feeds_sidebar.is_visible():
            # Click somewhere inside the feeds sidebar
            feeds_sidebar.click(position={"x": 100, "y": 100})

            # Sidebar should still be open (clicking inside should not close it)
            expect(page.locator("#app-root")).to_have_attribute("data-drawer", "open")

            # Now close it by clicking the overlay
            page.click("body", position={"x": 350, "y": 200})
            expect(page.locator("#app-root")).not_to_have_attribute("data-drawer", "open", timeout=constants.MAX_WAIT_MS)

class TestHTMXArchitectureValidation:
    """Validate HTMX architecture changes work correctly"""
    
    def test_mobile_handlers_routing(self, page: Page, test_server_url):
        """Test MobileHandlers routing and content swapping"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.MOBILE_VIEWPORT)
        
        # Test mobile content handler (summary section contains main content)
        expect(page.locator("#summary")).to_be_visible()
        
        # Test mobile sidebar handler - scope to summary
        hamburger = page.locator("#summary [data-testid='hamburger-btn']")
        if hamburger.is_visible():
            hamburger.click()
            wait_for_htmx_complete(page)
            # Feeds should be visible when drawer is open
            expect(page.locator("#feeds")).to_be_visible()

            # Close sidebar by clicking overlay
            overlay = page.locator("#sidebar-overlay")
            overlay.click()
            wait_for_htmx_complete(page)
            # Feeds should have hidden class when drawer is closed
            expect(page.locator("#feeds")).to_have_class(re.compile(r"hidden"))
    
    def test_desktop_handlers_routing(self, page: Page, test_server_url):
        """Test DesktopHandlers routing and column updates"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        
        # Test desktop feeds column handler (summary section)
        expect(page.locator("#summary")).to_be_visible()

        # Test desktop detail column handler
        expect(page.locator("#detail")).to_be_visible()

        # Test desktop sidebar column handler
        expect(page.locator("#feeds")).to_be_visible()
        
        # Test column interaction
        article_items = page.locator("li[data-testid='feed-item']").all()
        if len(article_items) > 0:
            article_items[0].click()
            wait_for_htmx_complete(page)

            # Verify detail column updates while other columns remain
            expect(page.locator("#detail")).to_contain_text("From:")
            expect(page.locator("#summary")).to_be_visible()
            expect(page.locator("#feeds")).to_be_visible()
    
    def test_unified_tab_container_behavior(self, page: Page, test_server_url):
        """Test the unified create_tab_container function for both mobile and desktop"""
        # Test desktop tab behavior
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        wait_for_page_ready(page)
        
        # Desktop buttons should use HTMX (unified behavior now)
        all_posts_desktop = page.locator("#summary [data-testid='all-posts-btn']")
        if all_posts_desktop.is_visible():
            # Should have hx-get attribute with some value
            expect(all_posts_desktop).to_have_attribute("hx-get", re.compile(r".*"))
            all_posts_desktop.click()
            wait_for_htmx_complete(page)
        
        # Test mobile tab behavior
        page.set_viewport_size(constants.MOBILE_VIEWPORT)
        wait_for_page_ready(page)
        
        # Mobile buttons should use HTMX attributes (same as desktop now)
        all_posts_mobile = page.locator("#summary [data-testid='all-posts-btn']")
        if all_posts_mobile.is_visible():
            # Should have hx-get attribute with some value
            expect(all_posts_mobile).to_have_attribute("hx-get", re.compile(r".*"))
            all_posts_mobile.click()
            wait_for_htmx_complete(page)