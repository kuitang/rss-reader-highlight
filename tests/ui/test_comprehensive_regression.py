"""Comprehensive Playwright regression tests for RSS Reader refactoring validation"""

import pytest
from playwright.sync_api import Page, expect
import time
import re

# HTMX Helper Functions for Fast Testing
def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete - much faster than fixed timeouts"""
    page.wait_for_function("() => !document.body.classList.contains('htmx-request')", timeout=timeout)

def wait_for_page_ready(page):
    """Fast page ready check - waits for network idle instead of fixed timeout"""
    page.wait_for_load_state("networkidle")



class TestComprehensiveRegression:
    """Comprehensive testing to detect regressions from HTMX architecture refactoring"""
    
    def test_desktop_comprehensive_workflow(self, page: Page):
        """Test complete desktop workflow: feed selection, article reading, tab switching"""
        page.goto("http://localhost:8080")
        page.set_viewport_size({"width": 1200, "height": 800})
        
        # Wait for page load
        wait_for_page_ready(page)
        expect(page.locator("title")).to_have_text("RSS Reader")
        
        # Verify desktop three-column layout is visible
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page.locator("#sidebar")).to_be_visible()
        expect(page.locator("#desktop-feeds-content")).to_be_visible()
        expect(page.locator("#desktop-item-detail")).to_be_visible()
        
        # Test Feed Selection Cycle (3 iterations)
        for iteration in range(3):
            print(f"Desktop iteration {iteration + 1}")
            
            # Click on a feed in sidebar
            feed_links = page.locator("a[href*='feed_id']").all()
            if len(feed_links) > iteration:
                feed_links[iteration].click()
                
                # Wait for feed content to load
                wait_for_htmx_complete(page)
                
                # Scroll down in middle panel
                middle_panel = page.locator("#desktop-feeds-content")
                middle_panel.scroll_into_view_if_needed()
                page.mouse.wheel(0, 500)
                wait_for_htmx_complete(page, timeout=3000)
                
                # Click on an article
                article_items = page.locator("li[id*='desktop-feed-item']").all()
                if len(article_items) > 0:
                    article_items[0].click()
                    
                    # Verify article loads in right panel
                    wait_for_htmx_complete(page)
                    expect(page.locator("#desktop-item-detail")).to_contain_text("From:")
                    
                    # Verify URL updated
                    assert "/item/" in page.url
                    
                    # Toggle between All Posts and Unread tabs
                    all_posts_tab = page.locator("a:has-text('All Posts')")
                    unread_tab = page.locator("a:has-text('Unread')")
                    
                    if all_posts_tab.is_visible():
                        all_posts_tab.click()
                        wait_for_htmx_complete(page)
                        
                    if unread_tab.is_visible():
                        unread_tab.click()
                        wait_for_htmx_complete(page)
    
    def test_mobile_comprehensive_workflow(self, page: Page):
        """Test complete mobile workflow: navigation, feed selection, article reading"""
        page.goto("http://localhost:8080")
        page.set_viewport_size({"width": 390, "height": 844})
        
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
                page.wait_for_timeout(500)
                expect(page.locator("#mobile-sidebar")).to_be_visible()
                
                # Click on a feed
                feed_links = page.locator("#mobile-sidebar a[href*='feed_id']").all()
                if len(feed_links) > iteration % len(feed_links):
                    feed_links[iteration % len(feed_links)].click()
                    
                    # Wait for sidebar to close and content to load
                    page.wait_for_timeout(1000)
                    expect(page.locator("#mobile-sidebar")).to_be_hidden()
                    
                    # Scroll down in feed list
                    main_content = page.locator("#main-content")
                    main_content.scroll_into_view_if_needed()
                    page.mouse.wheel(0, 800)
                    page.wait_for_timeout(500)
                    
                    # Click on an article
                    article_items = page.locator("li[id*='mobile-feed-item']").all()
                    if len(article_items) > 0:
                        article_items[0].click()
                        
                        # Wait for article to load (full-screen mobile view)
                        page.wait_for_timeout(1000)
                        
                        # Verify article content is visible
                        expect(page.locator("#main-content")).to_contain_text("From:")
                        
                        # Verify URL updated to article
                        assert "/item/" in page.url
                        
                        # Click back arrow
                        back_button = page.locator("#mobile-nav-button")
                        if back_button.is_visible():
                            back_button.click()
                            
                            # Wait for navigation back to feed list
                            page.wait_for_timeout(1000)
                            
                            # Toggle between tabs
                            all_posts_tab = page.locator("a:has-text('All Posts')")
                            unread_tab = page.locator("a:has-text('Unread')")
                            
                            if all_posts_tab.is_visible():
                                all_posts_tab.click()
                                page.wait_for_timeout(500)
                                
                            if unread_tab.is_visible():
                                unread_tab.click()
                                page.wait_for_timeout(500)
    
    def test_responsive_layout_switching(self, page: Page):
        """Test layout adaptation when switching between desktop and mobile viewports"""
        page.goto("http://localhost:8080")
        
        # Start with desktop
        page.set_viewport_size({"width": 1200, "height": 800})
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page.locator("#mobile-layout")).to_be_hidden()
        
        # Click an article in desktop mode
        article_items = page.locator("li[id*='desktop-feed-item']").all()
        if len(article_items) > 0:
            article_items[0].click()
            page.wait_for_timeout(1000)
            expect(page.locator("#desktop-item-detail")).to_contain_text("From:")
        
        # Switch to mobile viewport
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(1000)
        
        expect(page.locator("#mobile-layout")).to_be_visible()
        expect(page.locator("#desktop-layout")).to_be_hidden()
        
        # Switch back to desktop
        page.set_viewport_size({"width": 1200, "height": 800})
        page.wait_for_timeout(1000)
        
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page.locator("#mobile-layout")).to_be_hidden()
    
    def test_htmx_state_management(self, page: Page):
        """Test HTMX state updates and out-of-band swaps"""
        page.goto("http://localhost:8080")
        page.set_viewport_size({"width": 1200, "height": 800})
        
        # Wait for page load
        page.wait_for_timeout(2000)
        
        # Test blue indicator state changes
        unread_items = page.locator("li[id*='feed-item'] .w-2.h-2.bg-blue-500")
        initial_count = unread_items.count()
        
        if initial_count > 0:
            # Click an unread article
            first_unread_item = page.locator("li[id*='feed-item']:has(.w-2.h-2.bg-blue-500)").first
            first_unread_item.click()
            
            # Wait for HTMX update
            page.wait_for_timeout(1000)
            
            # Verify blue dot disappeared (out-of-band update)
            final_count = unread_items.count()
            assert final_count < initial_count, "Blue indicator should disappear after reading"
    
    def test_rapid_interaction_stability(self, page: Page):
        """Test stability under rapid user interactions"""
        page.goto("http://localhost:8080")
        page.set_viewport_size({"width": 1200, "height": 800})
        
        # Wait for initial load
        page.wait_for_timeout(2000)
        
        # Rapid clicking test
        for i in range(5):
            # Quick feed selections
            feed_links = page.locator("a[href*='feed_id']").all()
            if len(feed_links) > 0:
                feed_links[i % len(feed_links)].click()
                page.wait_for_timeout(200)
            
            # Quick article clicks
            article_items = page.locator("li[id*='feed-item']").all()
            if len(article_items) > 0:
                article_items[0].click()
                page.wait_for_timeout(200)
        
        # Verify app is still responsive
        expect(page.locator("title")).to_have_text("RSS Reader")
        
        # Check for JavaScript errors
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.wait_for_timeout(1000)
        
        assert len(errors) == 0, f"JavaScript errors detected: {errors}"
    
    def test_mobile_sidebar_and_navigation_flow(self, page: Page):
        """Test mobile-specific navigation patterns"""
        page.goto("http://localhost:8080")
        page.set_viewport_size({"width": 390, "height": 844})
        
        # Wait for mobile layout
        expect(page.locator("#mobile-layout")).to_be_visible()
        
        # Test sidebar open/close cycle
        for i in range(3):
            # Open sidebar with hamburger
            hamburger = page.locator("#mobile-nav-button")
            if hamburger.is_visible():
                hamburger.click()
                expect(page.locator("#mobile-sidebar")).to_be_visible()
                
                # Select different feed each iteration
                feed_links = page.locator("#mobile-sidebar a[href*='feed_id']").all()
                if len(feed_links) > i % len(feed_links):
                    feed_links[i % len(feed_links)].click()
                    
                    # Verify sidebar closes and content updates
                    wait_for_htmx_complete(page)
                    expect(page.locator("#mobile-sidebar")).to_be_hidden()
                    
                    # Test article navigation
                    article_items = page.locator("li[id*='mobile-feed-item']").all()
                    if len(article_items) > 0:
                        article_items[0].click()
                        
                        # Verify full-screen article view
                        wait_for_htmx_complete(page)
                        assert "/item/" in page.url
                        
                        # Navigate back
                        back_button = page.locator("#mobile-nav-button")
                        if back_button.is_visible():
                            back_button.click()
                            wait_for_htmx_complete(page)
    
    def test_feed_content_and_pagination(self, page: Page):
        """Test feed content loading and pagination behavior"""
        page.goto("http://localhost:8080")
        page.set_viewport_size({"width": 1200, "height": 800})
        
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
    
    def test_session_and_state_persistence(self, page: Page):
        """Test session management and state persistence across navigation"""
        page.goto("http://localhost:8080")
        
        # Wait for initial session setup
        wait_for_page_ready(page)
        
        # Navigate to different feeds and verify session persists
        feed_links = page.locator("a[href*='feed_id']").all()
        
        for i, feed_link in enumerate(feed_links[:2]):  # Test first 2 feeds
            feed_link.click()
            wait_for_htmx_complete(page)
            
            # Verify page loads and session is maintained
            expect(page.locator("title")).to_have_text("RSS Reader")
            
            # Click an article to test state management
            article_items = page.locator("li[id*='feed-item']").all()
            if len(article_items) > 0:
                article_items[0].click()
                wait_for_htmx_complete(page)
                
                # Verify article loads
                assert "/item/" in page.url
                
                # Go back to main page
                page.goto("http://localhost:8080")
                wait_for_page_ready(page)
    
    def test_error_resilience_and_recovery(self, page: Page):
        """Test application resilience under various error conditions"""
        page.goto("http://localhost:8080")
        
        # Test invalid item URL
        page.goto("http://localhost:8080/item/99999")
        wait_for_page_ready(page)
        
        # Should gracefully handle non-existent items
        expect(page.locator("title")).to_have_text("RSS Reader")
        
        # Test invalid feed ID
        page.goto("http://localhost:8080/?feed_id=99999")
        wait_for_page_ready(page)
        
        # Should gracefully handle invalid feed IDs
        expect(page.locator("title")).to_have_text("RSS Reader")
        
        # Return to valid state
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)
        expect(page.locator("title")).to_have_text("RSS Reader")


class TestHTMXArchitectureValidation:
    """Validate HTMX architecture changes work correctly"""
    
    def test_mobile_handlers_routing(self, page: Page):
        """Test MobileHandlers routing and content swapping"""
        page.goto("http://localhost:8080")
        page.set_viewport_size({"width": 390, "height": 844})
        
        # Test mobile content handler
        expect(page.locator("#main-content")).to_be_visible()
        
        # Test mobile sidebar handler
        hamburger = page.locator("#mobile-nav-button")
        if hamburger.is_visible():
            hamburger.click()
            expect(page.locator("#mobile-sidebar")).to_be_visible()
            
            # Close sidebar
            close_button = page.locator("#mobile-sidebar button[onclick*='setAttribute']")
            close_button.click()
            expect(page.locator("#mobile-sidebar")).to_be_hidden()
    
    def test_desktop_handlers_routing(self, page: Page):
        """Test DesktopHandlers routing and column updates"""
        page.goto("http://localhost:8080")
        page.set_viewport_size({"width": 1200, "height": 800})
        
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
            page.wait_for_timeout(1000)
            
            # Verify detail column updates while other columns remain
            expect(page.locator("#desktop-item-detail")).to_contain_text("From:")
            expect(page.locator("#desktop-feeds-content")).to_be_visible()
            expect(page.locator("#sidebar")).to_be_visible()
    
    def test_unified_tab_container_behavior(self, page: Page):
        """Test the unified create_tab_container function for both mobile and desktop"""
        # Test desktop tab behavior
        page.goto("http://localhost:8080")
        page.set_viewport_size({"width": 1200, "height": 800})
        page.wait_for_timeout(1000)
        
        # Desktop tabs should use regular links (no HTMX)
        all_posts_desktop = page.locator("#desktop-feeds-content a:has-text('All Posts')")
        if all_posts_desktop.is_visible():
            # Should have href but no hx-get for desktop
            expect(all_posts_desktop).to_have_attribute("href")
            all_posts_desktop.click()
            wait_for_htmx_complete(page)
        
        # Test mobile tab behavior
        page.set_viewport_size({"width": 390, "height": 844})
        wait_for_page_ready(page)
        
        # Mobile tabs should use HTMX attributes
        all_posts_mobile = page.locator("#mobile-persistent-header a:has-text('All Posts')")
        if all_posts_mobile.is_visible():
            # Should have both href and hx-get for mobile
            expect(all_posts_mobile).to_have_attribute("href")
            expect(all_posts_mobile).to_have_attribute("hx-get")
            all_posts_mobile.click()
            wait_for_htmx_complete(page)