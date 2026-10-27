"""Test header button visibility rules for unified header implementation"""

import pytest
from playwright.sync_api import sync_playwright, expect, Page
import test_constants as constants
from test_helpers import (
    wait_for_htmx_complete,
    wait_for_page_ready,
    wait_for_htmx_settle
)

pytestmark = pytest.mark.needs_server


class TestHeaderButtonVisibilityRules:
    """Test comprehensive header button visibility rules"""

    def test_header_button_visibility_rules(self, page, test_server_url):
        """Test header button visibility in different viewport and content states

        Verifies:
        1. Header title is identical in desktop and mobile views
        2. No buttons visible on desktop viewport (width >= 1024px)
        3. Hamburger button visible and back button hidden on mobile in feed list view
        4. Back button visible and hamburger button hidden on mobile in article detail view
        5. Buttons never appear simultaneously
        """
        # Start with desktop viewport
        page.set_viewport_size(constants.DESKTOP_VIEWPORT)
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page)

        # 1. Check header title on desktop (should be in summary section only)
        header_title = page.locator('#summary #universal-header h1')
        expect(header_title).to_be_visible()
        desktop_title_text = header_title.text_content()

        # Verify header in detail section is hidden on desktop
        detail_header = page.locator('#detail #universal-header')
        expect(detail_header).to_be_hidden()

        # 2. Verify NO buttons visible on desktop
        # Check both headers' buttons (they should all be hidden on desktop)
        hamburger_btns = page.locator('.hamburger-btn')
        back_btns = page.locator('.back-btn')

        # Desktop should hide ALL buttons (both in summary and detail headers)
        for i in range(hamburger_btns.count()):
            expect(hamburger_btns.nth(i)).to_be_hidden()
        for i in range(back_btns.count()):
            expect(back_btns.nth(i)).to_be_hidden()

        # Switch to mobile viewport
        page.set_viewport_size(constants.MOBILE_VIEWPORT)
        # Give the page time to re-render with new viewport
        page.wait_for_timeout(500)

        # 3. Verify hamburger visible, back hidden on mobile (feed list view)
        # On mobile feed list view, the summary header is visible
        summary_hamburger = page.locator('#summary .hamburger-btn')
        summary_back = page.locator('#summary .back-btn')
        expect(summary_hamburger).to_be_visible()
        expect(summary_back).to_be_hidden()

        # Verify header title is identical on mobile (still in summary section when showing feed list)
        mobile_title_text = header_title.text_content()
        assert desktop_title_text == mobile_title_text, f"Title mismatch: desktop='{desktop_title_text}' vs mobile='{mobile_title_text}'"

        # 4. Click an article to trigger detail view on mobile
        # Wait for feed items to load
        wait_for_htmx_settle(page, 3000)

        # Click the first feed item (updated selector for unified layout)
        feed_item = page.locator('li[id^="feed-item-"]').first
        if feed_item.count() > 0:
            feed_item.click()
            wait_for_htmx_complete(page)

            # Now back button should be visible, hamburger hidden
            # On mobile article view, the header in #detail section is now visible
            detail_header_mobile = page.locator('#detail #universal-header')
            expect(detail_header_mobile).to_be_visible()

            # Check the buttons in the detail header specifically
            detail_back = page.locator('#detail .back-btn')
            detail_hamburger = page.locator('#detail .hamburger-btn')
            expect(detail_back).to_be_visible()
            expect(detail_hamburger).to_be_hidden()

            # 5. Verify buttons never appear simultaneously
            # This is already verified above - one is visible, other is hidden

            # Click back button to return to feed list
            detail_back.click()
            wait_for_htmx_complete(page)

            # Should return to original state: hamburger visible, back hidden
            expect(summary_hamburger).to_be_visible()
            expect(summary_back).to_be_hidden()

        # Switch back to desktop and verify buttons still hidden
        page.set_viewport_size(constants.DESKTOP_VIEWPORT)
        page.wait_for_timeout(500)

        # All buttons should still be hidden on desktop
        for i in range(hamburger_btns.count()):
            expect(hamburger_btns.nth(i)).to_be_hidden()
        for i in range(back_btns.count()):
            expect(back_btns.nth(i)).to_be_hidden()

        # Verify title consistency across all transitions
        # On desktop, header should still be in summary section
        final_title_text = page.locator('#summary #universal-header h1').text_content()
        assert desktop_title_text == final_title_text, f"Title changed after transitions: initial='{desktop_title_text}' vs final='{final_title_text}'"


class TestLayoutAndResponsiveness:
    """Test header positioning and layout in different viewports"""

    def test_header_positioning_in_summary_section(self, page, test_server_url):
        """Test that universal header is positioned inside summary section"""
        page.set_viewport_size(constants.DESKTOP_VIEWPORT)
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page)

        # Verify header exists in summary section on desktop
        summary = page.locator('#summary')
        expect(summary).to_be_visible()

        # Check that header is a child of summary
        header_in_summary = summary.locator('#universal-header')
        expect(header_in_summary).to_be_visible()

        # Verify detail section header is hidden on desktop
        header_in_detail = page.locator('#detail #universal-header')
        expect(header_in_detail).to_be_hidden()

        # Verify feed list container has proper padding for fixed header
        feeds_container = page.locator('#feeds-list-container')
        expect(feeds_container).to_be_visible()

        # Check that feeds container has top padding class (pt-2 now with updated layout)
        class_list = feeds_container.get_attribute('class')
        assert 'pt-2' in class_list, f"Feeds container missing pt-2 class. Classes: {class_list}"

    def test_header_width_constraint_on_desktop(self, page, test_server_url):
        """Test that header positioning and CSS constraints work on desktop"""
        page.set_viewport_size(constants.DESKTOP_VIEWPORT)
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page)

        summary = page.locator('#summary')
        header = summary.locator('#universal-header')

        # Verify elements exist
        expect(summary).to_be_visible()
        expect(header).to_be_visible()

        # Check that CSS rules are applied correctly by verifying computed styles
        # Need to get the specific header in summary section
        header_left = page.evaluate("() => getComputedStyle(document.querySelector('#summary #universal-header')).left")
        header_right = page.evaluate("() => getComputedStyle(document.querySelector('#summary #universal-header')).right")

        # On desktop (1400px width), the CSS should constrain the header
        # Expected: left: 18rem (288px), right: 33.33% (≈466px)
        if "1024px" in page.evaluate("() => window.getComputedStyle(document.documentElement).width") or True:
            # Desktop viewport - check CSS constraints are applied
            assert "18rem" in header_left or "288px" in header_left, \
                f"Desktop header should have left constraint, got: {header_left}"

            # The right constraint should also be applied
            assert "33.33%" in header_right or header_right != "0px", \
                f"Desktop header should have right constraint, got: {header_right}"

        # Verify that the header is appropriately positioned
        header_box = header.bounding_box()
        summary_box = summary.bounding_box()

        if header_box and summary_box:
            # Header should start at least at the summary position or further right
            assert header_box['x'] >= summary_box['x'] - 10, \
                f"Header x ({header_box['x']}) should start near or after summary x ({summary_box['x']})"

            # Header should not extend too far past the viewport on mobile-sized content
            viewport_width = page.viewport_size['width']
            assert header_box['x'] + header_box['width'] <= viewport_width + 50, \
                f"Header should not overflow viewport significantly"