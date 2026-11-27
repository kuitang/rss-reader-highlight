"""Test for unified chrome component responsive behavior"""

import pytest
from playwright.sync_api import Page, expect
from test_constants import MINIMAL_WAIT_MS, DESKTOP_VIEWPORT, MOBILE_VIEWPORT_ALT, MAX_WAIT_MS, DESKTOP_VIEWPORT_ALT
from test_helpers import (
    wait_for_viewport_transition,
    wait_for_element_transition
)


class TestUnifiedChromeResponsive:
    """Test the unified chrome component across mobile and desktop viewports"""

    def test_chrome_responsive_behavior(self, page: Page, test_server_url: str):
        """Test that chrome appears correctly and doesn't scroll in both views"""

        # Start with desktop viewport
        page.set_viewport_size(DESKTOP_VIEWPORT)
        page.goto(test_server_url)
        page.wait_for_load_state("networkidle")

        # Desktop view assertions
        header = page.locator("#summary #universal-header")
        for width in (1280, 800, 390):
            page.set_viewport_size({"width": width, "height": 800})
            expect(header).to_be_visible()
            expect(header.locator("h1")).to_have_text("All Feeds")
            expect(header.locator(".hamburger-btn")).to_be_visible(visible=width < 1024)
            expect(header.locator("#icon-bar")).to_be_visible(visible=width > 480)
            start_y = header.bounding_box()["y"]
            page.locator("#summary").evaluate("el => el.scrollTop = 200")
            assert header.bounding_box()["y"] == start_y

    def test_chrome_transitions_smoothly(self, page: Page, test_server_url: str):
        page.goto(test_server_url)
        for width in (1280, 800, 390, 1280):
            page.set_viewport_size({"width": width, "height": 800})
            header = page.locator("#summary #universal-header")
            expect(header).to_be_visible()
            expect(header.locator(".hamburger-btn")).to_be_visible(visible=width < 1024)
            expect(header.locator("#icon-bar")).to_be_visible(visible=width > 480)

    def test_chrome_action_buttons_consistent(self, page: Page, test_server_url: str):
        """Test that action buttons work consistently in both views"""

        page.goto(test_server_url)
        page.wait_for_load_state("networkidle")

        # Test in desktop view first
        page.set_viewport_size(DESKTOP_VIEWPORT)

        # Click "All Posts" in desktop
        page.locator("#summary #icon-bar button[title='All Posts']").first.click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/?unread=0")

        # Go back to unread
        page.locator("#summary #icon-bar button[title='Unread']").first.click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/")

        # Switch to mobile and test same functionality
        page.set_viewport_size({"width": 600, "height": 820})
        wait_for_viewport_transition(page)

        # Click "All Posts" in mobile
        page.locator("#summary #icon-bar button[title='All Posts']").first.click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/?unread=0")

        # Go back to unread
        page.locator("#summary #icon-bar button[title='Unread']").first.click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/")

    def test_feed_name_changes_both_views(self, page: Page, test_server_url: str):
        """Test that feed name updates correctly when switching feeds"""

        page.goto(test_server_url)
        page.wait_for_load_state("networkidle")

        # Desktop view - verify initial feed name
        page.set_viewport_size(DESKTOP_VIEWPORT)
        desktop_feed_name = page.locator("#summary #universal-header h1")
        expect(desktop_feed_name).to_contain_text("All Feeds")

        # Click on a specific feed in desktop sidebar (if available)
        feed_link = page.locator("#feeds a[href*='feed_id']").first
        if feed_link.count() > 0:
            feed_text = feed_link.inner_text()
            feed_link.click()
            page.wait_for_load_state("networkidle")

            # Verify desktop chrome shows the selected feed name
            expect(desktop_feed_name).not_to_contain_text("All Feeds")

        # Mobile view - verify feed name is also shown
        page.set_viewport_size({"width": 600, "height": 820})
        wait_for_viewport_transition(page)

        mobile_feed_name = page.locator("#summary #universal-header h1")
        expect(mobile_feed_name).to_be_visible()

        # If we clicked a feed, verify mobile shows same feed name
        if feed_link.count() > 0:
            expect(mobile_feed_name).not_to_contain_text("All Feeds")
        else:
            expect(mobile_feed_name).to_contain_text("All Feeds")

    def test_search_functionality_both_views(self, page: Page, test_server_url: str):
        """Test that search works in both desktop and mobile chrome"""

        page.goto(test_server_url)
        page.wait_for_load_state("networkidle")

        # Desktop search test
        page.set_viewport_size(DESKTOP_VIEWPORT)

        # Click search button
        page.locator("#summary #icon-bar button[title='Search']").first.click()
        # Wait for search bar transition

        # Search bar should appear, icon bar should hide
        expect(page.locator("#summary #search-bar")).to_be_visible()
        expect(page.locator("#summary #icon-bar")).to_be_hidden()

        # Type in search
        search_input = page.locator("#summary #search-input")
        expect(search_input).to_be_visible()
        search_input.fill("Claude")

        # Close search
        page.locator("#summary #search-bar button[title='Close search']").click()
        expect(page.locator("#summary #search-bar")).to_be_hidden()
        expect(page.locator("#summary #icon-bar")).to_be_visible()

        # Mobile search test
        page.set_viewport_size({"width": 600, "height": 820})
        wait_for_viewport_transition(page)

        # Click search button
        page.locator("#summary #icon-bar button[title='Search']").first.click()
        # Wait for search bar transition

        # Search bar should appear, icon bar should hide
        expect(page.locator("#summary #search-bar")).to_be_visible()
        expect(page.locator("#summary #icon-bar")).to_be_hidden()

        # Type in search
        mobile_search_input = page.locator("#summary #search-input")
        expect(mobile_search_input).to_be_visible()
        mobile_search_input.fill("Hacker")

        # Close search
        page.locator("#summary #search-bar button[title='Close search']").click()
        expect(page.locator("#summary #search-bar")).to_be_hidden()
        expect(page.locator("#summary #icon-bar")).to_be_visible()