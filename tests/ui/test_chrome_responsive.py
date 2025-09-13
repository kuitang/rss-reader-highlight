"""Test for unified chrome component responsive behavior"""

import pytest
from playwright.sync_api import Page, expect


class TestUnifiedChromeResponsive:
    """Test the unified chrome component across mobile and desktop viewports"""

    def test_chrome_responsive_behavior(self, page: Page, test_server_url: str):
        """Test that chrome appears correctly and doesn't scroll in both views"""

        # Start with desktop viewport
        page.set_viewport_size({"width": 1400, "height": 900})
        page.goto(test_server_url)
        page.wait_for_load_state("networkidle")

        # Desktop view assertions
        desktop_chrome = page.locator("#desktop-chrome-container")
        mobile_header = page.locator("#mobile-top-bar")

        # Desktop chrome should be visible
        expect(desktop_chrome).to_be_visible()
        expect(mobile_header).to_be_hidden()

        # Check desktop chrome has feed name and action buttons
        desktop_feed_name = desktop_chrome.locator("h3")
        expect(desktop_feed_name).to_be_visible()
        expect(desktop_feed_name).to_contain_text("All Feeds")
        expect(page.locator("#desktop-icon-bar")).to_be_visible()

        # Verify desktop chrome has the three action buttons
        desktop_buttons = page.locator("#desktop-icon-bar button")
        expect(desktop_buttons).to_have_count(3)

        # Test scrolling in desktop - chrome should stay fixed
        feeds_content = page.locator("#desktop-feeds-content")
        initial_chrome_position = desktop_chrome.bounding_box()["y"]

        # Scroll the feeds content
        feeds_content.evaluate("el => el.scrollTop = 200")
        page.wait_for_timeout(100)  # Small wait for scroll

        # Chrome should remain in same position (not scroll)
        scrolled_chrome_position = desktop_chrome.bounding_box()["y"]
        assert initial_chrome_position == scrolled_chrome_position, "Desktop chrome should not scroll"

        # Switch to mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.wait_for_timeout(500)  # Wait for responsive transition

        # Mobile view assertions
        expect(desktop_chrome).to_be_hidden()
        expect(mobile_header).to_be_visible()

        # Check mobile header has hamburger button AND feed name
        mobile_nav_button = page.locator("#mobile-nav-button")
        expect(mobile_nav_button).to_be_visible()

        # Verify hamburger icon is present
        expect(mobile_nav_button.locator('[icon="menu"]')).to_be_visible()

        # Check mobile ALSO has feed name displayed
        mobile_feed_name = mobile_header.locator("h3")
        expect(mobile_feed_name).to_be_visible()
        expect(mobile_feed_name).to_contain_text("All Feeds")

        # Check mobile has the same action buttons
        expect(page.locator("#mobile-icon-bar")).to_be_visible()
        mobile_buttons = page.locator("#mobile-icon-bar button")
        expect(mobile_buttons).to_have_count(3)

        # Test scrolling in mobile - header should stay fixed
        main_content = page.locator("#main-content")
        initial_header_position = mobile_header.bounding_box()["y"]

        # Scroll the main content
        main_content.evaluate("el => el.scrollTop = 200")
        page.wait_for_timeout(100)  # Small wait for scroll

        # Mobile header should remain fixed at top
        scrolled_header_position = mobile_header.bounding_box()["y"]
        assert initial_header_position == scrolled_header_position, "Mobile header should stay fixed"
        assert scrolled_header_position == 0, "Mobile header should be at top of viewport"

    def test_chrome_transitions_smoothly(self, page: Page, test_server_url: str):
        """Test smooth transitions between mobile and desktop chrome"""

        page.goto(test_server_url)
        page.wait_for_load_state("networkidle")

        # Test multiple viewport changes
        viewports = [
            {"width": 1400, "height": 900, "expect_desktop": True},
            {"width": 800, "height": 600, "expect_desktop": False},
            {"width": 1200, "height": 800, "expect_desktop": True},
            {"width": 375, "height": 667, "expect_desktop": False},
        ]

        for viewport in viewports:
            page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
            page.wait_for_timeout(300)  # Wait for transition

            desktop_chrome = page.locator("#desktop-chrome-container")
            mobile_header = page.locator("#mobile-top-bar")

            if viewport["expect_desktop"]:
                expect(desktop_chrome).to_be_visible()
                expect(mobile_header).to_be_hidden()
                # Verify desktop chrome content
                expect(desktop_chrome.locator("h3")).to_be_visible()
                expect(page.locator("#desktop-icon-bar")).to_be_visible()
            else:
                expect(desktop_chrome).to_be_hidden()
                expect(mobile_header).to_be_visible()
                # Verify mobile chrome content
                expect(page.locator("#mobile-nav-button")).to_be_visible()
                expect(page.locator("#mobile-icon-bar")).to_be_visible()

    def test_chrome_action_buttons_consistent(self, page: Page, test_server_url: str):
        """Test that action buttons work consistently in both views"""

        page.goto(test_server_url)
        page.wait_for_load_state("networkidle")

        # Test in desktop view first
        page.set_viewport_size({"width": 1400, "height": 900})

        # Click "All Posts" in desktop
        page.locator("#desktop-icon-bar button[title='All Posts']").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/?unread=0")

        # Go back to unread
        page.locator("#desktop-icon-bar button[title='Unread']").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/")

        # Switch to mobile and test same functionality
        page.set_viewport_size({"width": 375, "height": 667})
        page.wait_for_timeout(300)

        # Click "All Posts" in mobile
        page.locator("#mobile-icon-bar button[title='All Posts']").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/?unread=0")

        # Go back to unread
        page.locator("#mobile-icon-bar button[title='Unread']").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/")

    def test_feed_name_changes_both_views(self, page: Page, test_server_url: str):
        """Test that feed name updates correctly when switching feeds"""

        page.goto(test_server_url)
        page.wait_for_load_state("networkidle")

        # Desktop view - verify initial feed name
        page.set_viewport_size({"width": 1400, "height": 900})
        desktop_feed_name = page.locator("#desktop-chrome-container h3")
        expect(desktop_feed_name).to_contain_text("All Feeds")

        # Click on a specific feed in desktop sidebar (if available)
        feed_link = page.locator("#sidebar a[href*='feed_id']").first
        if feed_link.count() > 0:
            feed_text = feed_link.inner_text()
            feed_link.click()
            page.wait_for_load_state("networkidle")

            # Verify desktop chrome shows the selected feed name
            expect(desktop_feed_name).not_to_contain_text("All Feeds")

        # Mobile view - verify feed name is also shown
        page.set_viewport_size({"width": 375, "height": 667})
        page.wait_for_timeout(300)

        mobile_feed_name = page.locator("#mobile-top-bar h3")
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
        page.set_viewport_size({"width": 1400, "height": 900})

        # Click search button
        page.locator("#desktop-icon-bar button[title='Search']").click()
        page.wait_for_timeout(100)

        # Search bar should appear, icon bar should hide
        expect(page.locator("#desktop-search-bar")).to_be_visible()
        expect(page.locator("#desktop-icon-bar")).to_be_hidden()

        # Type in search
        search_input = page.locator("#desktop-search-input")
        expect(search_input).to_be_visible()
        search_input.fill("Claude")

        # Close search
        page.locator("#desktop-search-bar button[title='Close search']").click()
        expect(page.locator("#desktop-search-bar")).to_be_hidden()
        expect(page.locator("#desktop-icon-bar")).to_be_visible()

        # Mobile search test
        page.set_viewport_size({"width": 375, "height": 667})
        page.wait_for_timeout(300)

        # Click search button
        page.locator("#mobile-icon-bar button[title='Search']").click()
        page.wait_for_timeout(100)

        # Search bar should appear, icon bar should hide
        expect(page.locator("#mobile-search-bar")).to_be_visible()
        expect(page.locator("#mobile-icon-bar")).to_be_hidden()

        # Type in search
        mobile_search_input = page.locator("#mobile-search-input")
        expect(mobile_search_input).to_be_visible()
        mobile_search_input.fill("Hacker")

        # Close search
        page.locator("#mobile-search-bar button[title='Close search']").click()
        expect(page.locator("#mobile-search-bar")).to_be_hidden()
        expect(page.locator("#mobile-icon-bar")).to_be_visible()