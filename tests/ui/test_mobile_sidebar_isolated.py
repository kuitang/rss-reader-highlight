"""
Mobile sidebar navigation test - isolated due to race conditions

This test is sensitive to DOM state from parallel test execution:
- Search bar expansion state from other tests
- Mobile sidebar open/close state  
- Viewport size changes from desktop tests
- Article vs list view navigation state

Runs perfectly in isolation, fails in parallel due to shared browser context pollution.
Rather than complex cleanup logic, simpler to run this test separately.
"""

import pytest
from playwright.sync_api import Page, expect
import time

pytestmark = pytest.mark.needs_server

# HTMX Helper Functions
def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete"""
    page.wait_for_function("() => !document.body.classList.contains('htmx-request')", timeout=timeout)

def wait_for_page_ready(page):
    """Wait for page ready state"""
    page.wait_for_load_state("networkidle")


class TestMobileSidebarIsolated:
    """Mobile sidebar tests that need isolation from parallel execution"""
    
    def test_mobile_sidebar_and_navigation_flow(self, page: Page, test_server_url):
        """Test mobile-specific navigation patterns"""
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(test_server_url)
        wait_for_page_ready(page)
        
        # Ensure mobile layout and JavaScript are ready
        expect(page.locator("#mobile-layout")).to_be_visible()
        expect(page.locator("#mobile-nav-button")).to_be_visible()
        page.wait_for_timeout(500)  # Ensure JS is loaded
        
        # Test sidebar open/close cycle
        for i in range(3):
            # Open sidebar with hamburger
            hamburger = page.locator("#mobile-nav-button")
            if hamburger.is_visible():
                hamburger.click()
                page.wait_for_selector("#mobile-sidebar", state="visible")  # Wait for sidebar to become visible
                
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
                        page.wait_for_timeout(500)  # Additional wait for URL update
                        assert "/item/" in page.url
                        
                        # Navigate back
                        back_button = page.locator("#mobile-nav-button")
                        if back_button.is_visible():
                            back_button.click()
                            wait_for_htmx_complete(page)


if __name__ == "__main__":
    # Can run this file directly for testing
    pytest.main([__file__, "-v", "--tb=short"])