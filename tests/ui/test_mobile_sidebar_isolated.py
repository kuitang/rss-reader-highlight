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
from tests.ui.conftest import wait_for_htmx_complete, wait_for_page_ready

pytestmark = pytest.mark.needs_server

# HTMX Helper Functions
def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete"""
    page.wait_for_function("() => !document.querySelector('.htmx-request, .htmx-swapping, .htmx-settling') && !window.articleTransitioning", timeout=timeout)

def wait_for_page_ready(page):
    """Wait for page ready state"""
    page.wait_for_load_state("networkidle")


class TestMobileSidebarIsolated:
    """Mobile sidebar tests that need isolation from parallel execution"""
    
    def test_mobile_sidebar_and_navigation_flow(self, page: Page, test_server_url):
        """Test mobile-specific navigation patterns"""
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(test_server_url, timeout=5000)
        # Wait for specific mobile layout element
        page.wait_for_selector("#main-layout", state="visible", timeout=5000)
        wait_for_page_ready(page)
        
        # Ensure mobile layout and JavaScript are ready
        expect(page.locator("#main-layout")).to_be_visible()
        expect(page.locator("#nav-button")).to_be_visible()
        wait_for_htmx_complete(page)  # Ensure JS is loaded
        
        # Test sidebar open/close cycle
        for i in range(3):
            # Open sidebar with hamburger
            hamburger = page.locator("#nav-button")
            if hamburger.is_visible():
                hamburger.click()
                page.wait_for_selector("#sidebar", state="visible")  # Wait for sidebar to become visible
                
                # Select different feed each iteration
                feed_links = page.locator("#sidebar a[href*='feed_id']").all()
                if len(feed_links) > i % len(feed_links):
                    feed_links[i % len(feed_links)].click()
                    
                    # Verify sidebar closes and content updates
                    wait_for_htmx_complete(page)
                    # Sidebar is off-screen (has -left-full class), not hidden in DOM
                    page.wait_for_function("() => document.getElementById('sidebar')?.classList.contains('-left-full')", timeout=2000)
                    
                    # Test article navigation
                    article_items = page.locator("li[id*='feed-item']").all()
                    if len(article_items) > 0:
                        article_items[0].click()
                        
                        # Verify full-screen article view
                        wait_for_htmx_complete(page)
                        wait_for_htmx_complete(page)  # Additional wait for URL update
                        assert "/item/" in page.url
                        
                        # Navigate back
                        back_button = page.locator("#nav-button")
                        if back_button.is_visible():
                            back_button.click()
                            wait_for_htmx_complete(page)


if __name__ == "__main__":
    # Can run this file directly for testing
    pytest.main([__file__, "-v", "--tb=short"])