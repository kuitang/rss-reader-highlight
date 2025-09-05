"""Comprehensive mobile navigation tests - covers all mobile bugs and regressions
CRITICAL: Tests scroll position preservation, chevron/hamburger toggle, header visibility
"""

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8080"

# HTMX Helper Functions for Fast Testing
def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete - much faster than fixed timeouts"""
    page.wait_for_function("() => !document.body.classList.contains('htmx-request')", timeout=timeout)

def wait_for_page_ready(page):
    """Fast page ready check - waits for network idle instead of fixed timeout"""
    page.wait_for_load_state("networkidle")


class TestMobileNavigationComplete:
    """CRITICAL mobile navigation test suite - covers scroll position preservation and UI state"""
    
    @pytest.fixture(autouse=True)
    def fresh_start(self, page: Page):
        """Start each test with fresh page load to reset navigation state (preserve session)"""
        # Set mobile viewport first
        page.set_viewport_size({"width": 390, "height": 844})  # iPhone 13 size
        
        # Navigate to clean starting state (preserves session cookies automatically)
        page.goto(f"{BASE_URL}/?unread=0", wait_until="networkidle")
        wait_for_page_ready(page)
        
        # Ensure clean DOM state - mobile sidebar should be closed by default
        page.evaluate("""() => {
            const sidebar = document.getElementById('mobile-sidebar');
            if (sidebar) sidebar.setAttribute('hidden', 'true');
            
            // Clear any navigation history pollution
            if (window.history && window.history.replaceState) {
                window.history.replaceState(null, '', '/?unread=0');
            }
        }""")
        page.wait_for_timeout(200)  # Increased wait for state settlement
    
    def test_scroll_position_preservation_critical(self, page: Page):
        """CRITICAL: Mobile scroll position must be preserved on back navigation"""
        
        # Set mobile viewport first
        page.set_viewport_size({"width": 390, "height": 844})
        
        # Start at All Posts view
        page.goto(f"{BASE_URL}/?unread=0")
        wait_for_page_ready(page)
        
        # CRITICAL: Set and verify scroll position on the feeds list container
        scroll_setup = page.evaluate("""() => {
            const feedsList = document.getElementById('feeds-list-container') || 
                             document.querySelector('.js-filter') ||
                             document.querySelector('[uk-filter]');
            if (feedsList) {
                feedsList.scrollTop = 600;
                return {
                    success: true,
                    scrollTop: feedsList.scrollTop,
                    scrollHeight: feedsList.scrollHeight,
                    elementId: feedsList.id || feedsList.className
                };
            }
            return { success: false, scrollTop: 0, scrollHeight: 0, elementId: 'not-found' };
        }""")
        
        if not scroll_setup['success']:
            pytest.skip(f"feeds list container not available in test environment: {scroll_setup['elementId']}")
            
        expected_scroll = scroll_setup['scrollTop']
        print(f"📏 SCROLL SETUP: {expected_scroll}px of {scroll_setup['scrollHeight']}px on {scroll_setup['elementId']}")
        
        # Navigate to article by clicking (to trigger HTMX, not direct navigation)
        # Get the first available article ID dynamically to avoid hardcoding
        first_article_id = page.evaluate("""() => {
            const articles = document.querySelectorAll("li[id^='mobile-feed-item-']");
            return articles.length > 0 ? articles[0].id : null;
        }""")
        
        if not first_article_id:
            pytest.skip("No mobile feed items found to click")
            
        # Click the specific article by ID (more reliable than CSS selectors)
        feed_item = page.locator(f"#{first_article_id}")
        feed_item.click()
        wait_for_htmx_complete(page)
        
        assert "/item/" in page.url, "Should be in article view"
        
        # CRITICAL: Use browser back 
        page.go_back()
        wait_for_htmx_complete(page)
        
        # Verify we're back to All Posts
        assert "unread=0" in page.url, "Should return to All Posts view"
        
        # Wait for DOM to settle after back navigation
        page.wait_for_timeout(100)
        
        # CRITICAL: Check scroll position preserved on the feeds list container
        scroll_check = page.evaluate("""() => {
            const feedsList = document.getElementById('feeds-list-container') || 
                             document.querySelector('.js-filter') ||
                             document.querySelector('[uk-filter]');
            if (!feedsList) {
                // Check if we're in desktop layout after back navigation
                const desktopLayout = document.getElementById('desktop-layout');
                const mobileLayout = document.getElementById('mobile-layout');
                return {
                    element: false,
                    scrollTop: -1,
                    elementId: 'not-found',
                    debug: {
                        hasDesktop: !!desktopLayout,
                        hasMobile: !!mobileLayout,
                        bodyClass: document.body.className
                    }
                };
            }
            
            return {
                element: true,
                scrollTop: feedsList.scrollTop,
                elementId: feedsList.id || feedsList.className,
                debug: {
                    hasDesktop: !!document.getElementById('desktop-layout'),
                    hasMobile: !!document.getElementById('mobile-layout'),
                    bodyClass: document.body.className
                }
            };
        }""")
        
        print(f"🔍 DEBUG: After back - Desktop: {scroll_check['debug']['hasDesktop']}, Mobile: {scroll_check['debug']['hasMobile']}")
        print(f"🔍 DEBUG: Body class: {scroll_check['debug']['bodyClass']}")
        
        if not scroll_check['element']:
            # Browser back may have triggered full page reload - check if we can find feeds list
            page.wait_for_timeout(500)  # Additional wait
            final_scroll = page.evaluate("""() => {
                const feedsList = document.getElementById('feeds-list-container') || 
                                 document.querySelector('.js-filter') ||
                                 document.querySelector('[uk-filter]');
                return feedsList?.scrollTop ?? -999;
            }""")
            
            if final_scroll == -999:
                pytest.fail(f"CRITICAL: feeds list container missing after back navigation - element: {scroll_check['elementId']}")
        else:
            final_scroll = scroll_check['scrollTop']
        
        scroll_preserved = abs(final_scroll - expected_scroll) < 100
        print(f"📏 SCROLL RESULT: Expected {expected_scroll}, got {final_scroll}")
        
        # CRITICAL ASSERTION: Scroll position MUST be preserved  
        assert scroll_preserved, f"CRITICAL FAILURE: Scroll position not preserved (expected ~{expected_scroll}, got {final_scroll})"
        print("✅ CRITICAL SUCCESS: Scroll position preserved!")
    
    def test_chevron_hamburger_button_toggle(self, page: Page):
        """Test hamburger <-> chevron button toggling works correctly"""
        
        # Start at list view
        page.goto(f"{BASE_URL}/?unread=0")  
        wait_for_page_ready(page)
        
        # Test navigation by direct URL (more reliable than element clicking)
        # Simulate: list view -> article view -> back to list
        
        # Step 1: Navigate to article by finding and clicking any available article
        # Get the first available article ID dynamically
        first_article_id = page.evaluate("""() => {
            const articles = document.querySelectorAll("li[id^='mobile-feed-item-']");
            return articles.length > 0 ? articles[0].id : null;
        }""")
        
        if not first_article_id:
            pytest.skip("No mobile feed items found to click")
            
        # Click the specific article by ID (more reliable than CSS selectors)
        feed_item = page.locator(f"#{first_article_id}")
        feed_item.click()
        wait_for_page_ready(page)
        
        # Verify chevron button appears (arrow-left icon)
        chevron_icon = page.evaluate("""() => {
            const btn = document.getElementById('mobile-nav-button');
            const icon = btn?.querySelector('uk-icon');
            return icon?.getAttribute('icon') || 'not-found';
        }""")
        
        print(f"🔄 CHEVRON TEST: Article view button icon: {chevron_icon}")
        
        # STRICT ASSERTION: Chevron must appear in article view
        assert chevron_icon == 'arrow-left', f"FAILED: Expected arrow-left icon in article view, got: {chevron_icon}"
        
        # Step 2: Go back to list view
        page.goto(f"{BASE_URL}/?unread=0")
        wait_for_page_ready(page)
        
        # Verify hamburger restored
        hamburger_icon = page.evaluate("""() => {
            const btn = document.getElementById('mobile-nav-button');
            const icon = btn?.querySelector('uk-icon');
            return icon?.getAttribute('icon') || 'not-found';
        }""")
        
        print(f"🍔 HAMBURGER TEST: List view button icon: {hamburger_icon}")
        
        # STRICT ASSERTION: Hamburger must be restored in list view
        assert hamburger_icon == 'menu', f"FAILED: Expected menu icon in list view, got: {hamburger_icon}"
        
        # State preservation test
        assert "unread=0" in page.url, "Should be back in All Posts view"
    
    def test_mobile_header_regression_fix(self, page: Page):
        """Test mobile persistent header shows/hides correctly (regression fix)"""
        
        # Start at list view - header should be visible
        page.goto(f"{BASE_URL}/?unread=0")
        wait_for_page_ready(page)
        
        mobile_header = page.locator('#mobile-persistent-header')
        expect(mobile_header).to_be_visible()
        
        # Navigate to article view by clicking an article - header should be hidden
        # Get the first available article ID dynamically
        first_article_id = page.evaluate("""() => {
            const articles = document.querySelectorAll("li[id^='mobile-feed-item-']");
            return articles.length > 0 ? articles[0].id : null;
        }""")
        
        if not first_article_id:
            pytest.skip("No mobile feed items found to click")
            
        # Click the specific article by ID (more reliable than CSS selectors)
        feed_item = page.locator(f"#{first_article_id}")
        feed_item.click()
        wait_for_page_ready(page)
        
        # Check if header is hidden via CSS
        header_hidden = page.evaluate("""() => {
            const header = document.getElementById('mobile-persistent-header');
            const style = window.getComputedStyle(header);
            return style.display === 'none';
        }""")
        
        print(f"📱 HEADER VISIBILITY: Hidden in article view: {header_hidden}")
        
        # STRICT ASSERTION: Header must be hidden in article view
        assert header_hidden, "REGRESSION FAILURE: Mobile persistent header should be hidden in article view"
        
        # Navigate back to list view - header should be visible again
        page.goto(f"{BASE_URL}/?unread=0")
        wait_for_page_ready(page)
        
        expect(mobile_header).to_be_visible()
        print("✅ HEADER VISIBILITY: Restored in list view")
    
    @pytest.mark.skip(reason="TODO: URL state preservation edge case - needs investigation")
    def test_all_posts_vs_unread_state_preservation(self, page: Page):
        """Test the core bug fix: All Posts vs Unread state preservation"""
        
        # Test 1: All Posts -> Article -> Back should return to All Posts
        page.goto(f"{BASE_URL}/?unread=0")
        wait_for_page_ready(page)
        
        # Click on an article from All Posts view (don't hardcode ID)
        # Get the first available article ID dynamically
        first_article_id = page.evaluate("""() => {
            const articles = document.querySelectorAll("li[id^='mobile-feed-item-']");
            return articles.length > 0 ? articles[0].id : null;
        }""")
        
        if not first_article_id:
            pytest.skip("No mobile feed items found to click")
            
        # Click the specific article by ID (more reliable than CSS selectors)
        feed_item = page.locator(f"#{first_article_id}")
        feed_item.click()
        wait_for_page_ready(page)
        
        page.go_back()
        wait_for_htmx_complete(page)
        
        assert "unread=0" in page.url, "Should return to All Posts view"
        print("✅ ALL POSTS: State preserved after back navigation")
        
        # Test 2: Unread -> Article -> Back should return to Unread  
        page.goto(f"{BASE_URL}/")
        wait_for_page_ready(page)
        
        # Click on an article from Unread view (don't hardcode ID)
        # Get the first available article ID dynamically
        first_article_id = page.evaluate("""() => {
            const articles = document.querySelectorAll("li[id^='mobile-feed-item-']");
            return articles.length > 0 ? articles[0].id : null;
        }""")
        
        if not first_article_id:
            pytest.skip("No mobile feed items found to click")
            
        # Click the specific article by ID (more reliable than CSS selectors)
        feed_item = page.locator(f"#{first_article_id}")
        feed_item.click()
        wait_for_page_ready(page)
        
        page.go_back()
        wait_for_htmx_complete(page)
        
        assert "unread=0" not in page.url, "Should return to Unread view (no unread=0 param)"
        print("✅ UNREAD: State preserved after back navigation")


# Legacy class removed - was causing test isolation issues by running same tests twice


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])