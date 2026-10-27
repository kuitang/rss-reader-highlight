"""Regression tests for critical bug fixes"""

import pytest
from playwright.sync_api import Page, expect
import re
import test_constants as constants
from test_helpers import wait_for_htmx_complete, wait_for_page_ready

pytestmark = pytest.mark.needs_server


class TestRegressionFixes:
    """Test cases for critical bug fixes that were identified and resolved"""

    def test_header_persistence_on_feed_click(self, page: Page, test_server_url):
        """Test that header persists when clicking on feeds"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)

        # Test in desktop viewport
        page.set_viewport_size(constants.DESKTOP_VIEWPORT)
        wait_for_page_ready(page)

        # Check header is initially visible
        header = page.locator("#summary h1").first  # Header should be in summary section
        expect(header).to_be_visible()
        initial_header_text = header.text_content()

        # Click on a feed link
        feed_link = page.locator("#feeds a[href*='feed_id']").first
        if feed_link.is_visible():
            feed_link.click()
            wait_for_htmx_complete(page)

            # Header should still be visible
            header_after = page.locator("#summary h1").first
            expect(header_after).to_be_visible()

            # Header text may change but element should persist
            expect(header_after.text_content()).not_to_be_empty()

        # Test in mobile viewport
        page.set_viewport_size(constants.MOBILE_VIEWPORT)
        wait_for_page_ready(page)

        # Open mobile sidebar
        hamburger = page.locator("button.hamburger-btn").first
        if hamburger.is_visible():
            hamburger.click()
            page.wait_for_selector("#feeds", state="visible")

            # Click on a feed in mobile
            mobile_feed = page.locator("#feeds a[href*='feed_id']").first
            if mobile_feed.is_visible():
                mobile_feed.click()
                wait_for_htmx_complete(page)

                # Header should still be visible in mobile
                mobile_header = page.locator("#summary h1").first
                expect(mobile_header).to_be_visible()

    def test_unread_parameter_preservation(self, page: Page, test_server_url):
        """Test that unread parameter is preserved when clicking feeds"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.DESKTOP_VIEWPORT)
        wait_for_page_ready(page)

        # Click on Unread button to filter
        unread_btn = page.locator("button:has-text('Unread')").first
        if unread_btn.is_visible():
            unread_btn.click()
            wait_for_htmx_complete(page)

            # URL should have unread=1
            expect(page).to_have_url(re.compile(r".*unread=1.*"))

            # Click on a feed - unread should be preserved
            feed_link = page.locator("#feeds a[href*='feed_id']").first
            if feed_link.is_visible():
                href = feed_link.get_attribute("href")
                # Feed link should include unread parameter
                assert "unread=1" in href, f"Feed link missing unread parameter: {href}"

                feed_link.click()
                wait_for_htmx_complete(page)

                # URL should still have unread=1
                expect(page).to_have_url(re.compile(r".*unread=1.*"))

    def test_mobile_sidebar_opacity(self, page: Page, test_server_url):
        """Test that mobile sidebar has full opacity and proper z-index"""
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        page.set_viewport_size(constants.MOBILE_VIEWPORT)
        wait_for_page_ready(page)

        # Open mobile sidebar
        hamburger = page.locator("button.hamburger-btn").first
        if hamburger.is_visible():
            hamburger.click()
            page.wait_for_selector("#feeds", state="visible")

            # Check sidebar has full opacity
            sidebar_opacity = page.evaluate("""
                () => {
                    const sidebar = document.getElementById('feeds');
                    const style = window.getComputedStyle(sidebar);
                    return {
                        opacity: style.opacity,
                        zIndex: style.zIndex
                    };
                }
            """)

            assert sidebar_opacity['opacity'] == '1', f"Sidebar opacity should be 1, got {sidebar_opacity['opacity']}"
            assert sidebar_opacity['zIndex'] == '50', f"Sidebar z-index should be 50, got {sidebar_opacity['zIndex']}"

    def test_mobile_sidebar_opacity_dark_mode(self, page: Page, test_server_url):
        """Test mobile sidebar opacity in dark mode"""
        # Enable dark mode via browser preference
        context = page.context
        browser = context.browser
        dark_context = browser.new_context(color_scheme='dark')
        dark_page = dark_context.new_page()

        dark_page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        dark_page.set_viewport_size(constants.MOBILE_VIEWPORT)
        wait_for_page_ready(dark_page)

        # Open mobile sidebar
        hamburger = dark_page.locator("button.hamburger-btn").first
        if hamburger.is_visible():
            hamburger.click()
            dark_page.wait_for_selector("#feeds", state="visible")

            # Check sidebar has full opacity in dark mode
            sidebar_opacity = dark_page.evaluate("""
                () => {
                    const sidebar = document.getElementById('feeds');
                    const style = window.getComputedStyle(sidebar);
                    return {
                        opacity: style.opacity,
                        background: style.background
                    };
                }
            """)

            assert sidebar_opacity['opacity'] == '1', f"Dark mode: Sidebar opacity should be 1, got {sidebar_opacity['opacity']}"

        dark_context.close()