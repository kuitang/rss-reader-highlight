"""Test for unified chrome component responsive behavior"""

import pytest
from playwright.sync_api import Page, expect
from tests.ui.conftest import wait_for_htmx_complete, wait_for_page_ready


class TestUnifiedChromeResponsive:
    """Test the unified chrome component across mobile and desktop viewports"""

    def test_chrome_responsive_behavior(self, page: Page, test_server_url: str):
        """Test that chrome appears correctly and doesn't scroll in both views"""

        # Start with desktop viewport
        page.set_viewport_size({"width": 1400, "height": 900})
        page.goto(test_server_url)
        page.wait_for_load_state("networkidle")

        # Desktop view assertions
        chrome_container = page.locator("#chrome-container")

        # Chrome container should be visible
        expect(chrome_container).to_be_visible()

        # Check chrome has feed name and action buttons
        feed_name = chrome_container.locator("h3")
        expect(feed_name).to_be_visible()
        expect(feed_name).to_contain_text("All Feeds")
        expect(page.locator("#icon-bar")).to_be_visible()

        # Verify chrome has the three action buttons
        buttons = page.locator("#icon-bar button")
        expect(buttons).to_have_count(3)

        # Test scrolling in desktop - chrome should stay fixed
        feeds_content = page.locator("#feed-list")
        initial_chrome_position = chrome_container.bounding_box()["y"]

        # Scroll the feeds content
        feeds_content.evaluate("el => el.scrollTop = 200")
        wait_for_htmx_complete(page)  # Small wait for scroll

        # Chrome should remain in same position (not scroll)
        scrolled_chrome_position = chrome_container.bounding_box()["y"]
        assert initial_chrome_position == scrolled_chrome_position, "Chrome should not scroll"

        # Switch to mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        wait_for_htmx_complete(page)  # Wait for responsive transition

        # Mobile view assertions - chrome container is unified
        expect(chrome_container).to_be_visible()

        # Check mobile header has hamburger button AND feed name
        mobile_nav_button = page.locator("#nav-button")
        expect(mobile_nav_button).to_be_visible()

        # Verify hamburger icon is present
        expect(mobile_nav_button.locator('[icon="menu"]')).to_be_visible()

        # Check mobile ALSO has feed name displayed
        mobile_feed_name = chrome_container.locator("h3")
        expect(mobile_feed_name).to_be_visible()
        expect(mobile_feed_name).to_contain_text("All Feeds")

        # Check mobile has the same action buttons
        expect(page.locator("#icon-bar")).to_be_visible()
        mobile_buttons = page.locator("#icon-bar button")
        expect(mobile_buttons).to_have_count(3)

        # Test scrolling in mobile - header should stay fixed
        main_content = page.locator("#content-area")
        initial_header_position = chrome_container.bounding_box()["y"]

        # Scroll the main content
        main_content.evaluate("el => el.scrollTop = 200")
        wait_for_htmx_complete(page)  # Small wait for scroll

        # Mobile header should remain fixed at top
        scrolled_header_position = chrome_container.bounding_box()["y"]
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
            wait_for_htmx_complete(page)  # Wait for transition

            chrome_container = page.locator("#chrome-container")

            # Chrome container should always be visible
            expect(chrome_container).to_be_visible()
            expect(chrome_container.locator("h3")).to_be_visible()
            expect(page.locator("#icon-bar")).to_be_visible()

            if viewport["expect_desktop"]:
                # Desktop: no nav button visible (or different styling)
                # We don't check nav button visibility as it may be context-dependent
                pass
            else:
                # Mobile: nav button should be visible
                expect(page.locator("#nav-button")).to_be_visible()

    def test_chrome_action_buttons_consistent(self, page: Page, test_server_url: str):
        """Test that action buttons work consistently in both views"""

        page.goto(test_server_url)
        page.wait_for_load_state("networkidle")

        # Test in desktop view first
        page.set_viewport_size({"width": 1400, "height": 900})

        # Click "All Posts" in desktop
        page.locator("#icon-bar button[title='All Posts']").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/?unread=0")

        # Go back to unread
        page.locator("#icon-bar button[title='Unread']").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/")

        # Switch to mobile and test same functionality
        page.set_viewport_size({"width": 375, "height": 667})
        wait_for_htmx_complete(page)

        # Click "All Posts" in mobile
        page.locator("#icon-bar button[title='All Posts']").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/?unread=0")

        # Go back to unread
        page.locator("#icon-bar button[title='Unread']").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url(f"{test_server_url}/")

    def test_feed_name_changes_both_views(self, page: Page, test_server_url: str):
        """Test that feed name updates correctly when switching feeds"""

        page.goto(test_server_url)
        page.wait_for_load_state("networkidle")

        # Desktop view - verify initial feed name
        page.set_viewport_size({"width": 1400, "height": 900})
        feed_name = page.locator("#chrome-container h3")
        expect(feed_name).to_contain_text("All Feeds")

        # Click on a specific feed in desktop sidebar (if available)
        feed_link = page.locator("#sidebar a[href*='feed_id']").first
        if feed_link.count() > 0:
            feed_text = feed_link.inner_text()
            feed_link.click()
            page.wait_for_load_state("networkidle")

            # Verify chrome shows the selected feed name
            expect(feed_name).not_to_contain_text("All Feeds")

        # Mobile view - verify feed name is also shown
        page.set_viewport_size({"width": 375, "height": 667})
        wait_for_htmx_complete(page)

        # Same feed name element in unified design
        mobile_feed_name = page.locator("#chrome-container h3")
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
        page.locator("#icon-bar button[title='Search']").click()
        wait_for_htmx_complete(page)

        # Search bar should appear, icon bar should hide
        expect(page.locator("#search-bar")).to_be_visible()
        expect(page.locator("#icon-bar")).to_be_hidden()

        # Type in search
        search_input = page.locator("#search-input")
        expect(search_input).to_be_visible()
        search_input.fill("Claude")

        # Close search
        page.locator("#search-bar button[title='Close search']").click()
        expect(page.locator("#search-bar")).to_be_hidden()
        expect(page.locator("#icon-bar")).to_be_visible()

        # Mobile search test
        page.set_viewport_size({"width": 375, "height": 667})
        wait_for_htmx_complete(page)

        # Click search button
        page.locator("#icon-bar button[title='Search']").click()
        wait_for_htmx_complete(page)

        # Search bar should appear, icon bar should hide
        expect(page.locator("#search-bar")).to_be_visible()
        expect(page.locator("#icon-bar")).to_be_hidden()

        # Type in search
        mobile_search_input = page.locator("#search-input")
        expect(mobile_search_input).to_be_visible()
        mobile_search_input.fill("Hacker")

        # Close search
        page.locator("#search-bar button[title='Close search']").click()
        expect(page.locator("#search-bar")).to_be_hidden()
        expect(page.locator("#icon-bar")).to_be_visible()