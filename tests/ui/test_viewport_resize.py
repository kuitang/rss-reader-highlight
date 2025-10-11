"""Test viewport resize behavior - mobile to desktop transition"""

import pytest
from playwright.sync_api import Page, expect
from tests.ui.conftest import (
    wait_for_htmx_complete, wait_for_page_ready, wait_for_sidebar_open,
    TIMEOUT_PAGE_LOAD, TIMEOUT_ANIMATION, TIMEOUT_ELEMENT_VISIBLE
)

pytestmark = pytest.mark.needs_server


class TestViewportResize:
    """Test responsive behavior when resizing viewport"""

    def test_mobile_to_desktop_resize_with_sidebar_open(self, page: Page, test_server_url):
        """CRITICAL: Resizing from mobile to desktop with sidebar open should not block clicks

        BUG: When sidebar is open on mobile and you resize to desktop, the overlay
        stays visible and blocks all clicks, making the app grey and unusable.

        FIX: Overlay has lg:!hidden class to force hide on desktop.
        """
        # Start in mobile viewport
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(test_server_url, timeout=TIMEOUT_PAGE_LOAD)
        wait_for_page_ready(page)

        # Open sidebar on mobile
        menu_button = page.locator('#nav-button')
        menu_button.click()
        wait_for_sidebar_open(page, timeout=TIMEOUT_ANIMATION)

        # Verify sidebar is open
        sidebar_open = page.evaluate("document.getElementById('sidebar')?.classList.contains('left-0')")
        assert sidebar_open, "Sidebar should be open (have left-0 class)"

        # Verify overlay is visible on mobile
        overlay_visible = page.evaluate("""() => {
            const overlay = document.getElementById('sidebar-overlay');
            return window.getComputedStyle(overlay).display === 'block';
        }""")
        assert overlay_visible, "Overlay should be visible on mobile"

        # Resize to desktop WITH SIDEBAR STILL OPEN
        page.set_viewport_size({"width": 1400, "height": 900})
        # Wait for CSS media query to apply (overlay should hide on desktop)
        page.wait_for_function(
            """() => {
                const overlay = document.getElementById('sidebar-overlay');
                return window.getComputedStyle(overlay).display === 'none';
            }""",
            timeout=TIMEOUT_ANIMATION
        )

        # CRITICAL CHECK: Overlay should be hidden on desktop
        overlay_hidden = page.evaluate("""() => {
            const overlay = document.getElementById('sidebar-overlay');
            const display = window.getComputedStyle(overlay).display;
            return display === 'none';
        }""")
        assert overlay_hidden, \
            "❌ CRITICAL BUG: Overlay should be hidden on desktop! " \
            "lg:!hidden class should force display:none even if 'block' class exists"

        # CRITICAL CHECK: App should be clickable
        feed_items = page.locator("li[id^='feed-item-']")
        expect(feed_items.first).to_be_visible(timeout=5000)

        # Try to click a feed item - this should NOT be blocked by overlay
        try:
            feed_items.first.click(timeout=3000)
            wait_for_htmx_complete(page)
            print("✅ Click successful - app is responsive after resize")
        except Exception as e:
            pytest.fail(f"❌ CRITICAL BUG: Cannot click after resize! Overlay blocking clicks: {e}")

        # Verify sidebar is in desktop mode (static position)
        sidebar_position = page.evaluate("""() => {
            const sidebar = document.getElementById('sidebar');
            return window.getComputedStyle(sidebar).position;
        }""")
        assert sidebar_position == 'static', \
            f"Sidebar should be position:static on desktop, got {sidebar_position}"

    def test_desktop_to_mobile_resize(self, page: Page, test_server_url):
        """Test resizing from desktop to mobile - sidebar should behave correctly"""
        # Start in desktop viewport
        page.set_viewport_size({"width": 1400, "height": 900})
        page.goto(test_server_url, timeout=TIMEOUT_PAGE_LOAD)
        wait_for_page_ready(page)

        # Verify desktop layout
        sidebar_visible = page.locator('#sidebar').is_visible()
        assert sidebar_visible, "Sidebar should be visible on desktop"

        # Resize to mobile
        page.set_viewport_size({"width": 390, "height": 844})
        # Wait for sidebar to move off-screen
        page.wait_for_function(
            """() => {
                const sidebar = document.getElementById('sidebar');
                return window.getComputedStyle(sidebar).left.startsWith('-');
            }""",
            timeout=TIMEOUT_ANIMATION
        )

        # Sidebar should be hidden off-screen on mobile
        sidebar_position = page.evaluate("""() => {
            const sidebar = document.getElementById('sidebar');
            return window.getComputedStyle(sidebar).left;
        }""")
        assert sidebar_position.startswith('-'), \
            f"Sidebar should be off-screen on mobile (negative left), got {sidebar_position}"

        # Overlay should be hidden
        overlay_hidden = page.evaluate("""() => {
            const overlay = document.getElementById('sidebar-overlay');
            return window.getComputedStyle(overlay).display === 'none';
        }""")
        assert overlay_hidden, "Overlay should be hidden when sidebar is closed"

    def test_mobile_padding_removed(self, page: Page, test_server_url):
        """Test that mobile view has no horizontal padding on feed list"""
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(test_server_url, wait_until="domcontentloaded", timeout=TIMEOUT_PAGE_LOAD)
        wait_for_page_ready(page)

        # Check feed list padding
        feed_padding = page.evaluate("""() => {
            const feedList = document.getElementById('feed-list');
            const styles = window.getComputedStyle(feedList);
            return {
                left: styles.paddingLeft,
                right: styles.paddingRight
            };
        }""")

        assert feed_padding['left'] == '0px', \
            f"Mobile feed list should have 0px left padding, got {feed_padding['left']}"
        assert feed_padding['right'] == '0px', \
            f"Mobile feed list should have 0px right padding, got {feed_padding['right']}"

        print("✅ Mobile feed list has no horizontal padding (matches production)")

    def test_desktop_padding_preserved(self, page: Page, test_server_url):
        """Test that desktop view has correct horizontal padding"""
        page.set_viewport_size({"width": 1400, "height": 900})
        page.goto(test_server_url, wait_until="domcontentloaded", timeout=TIMEOUT_PAGE_LOAD)
        wait_for_page_ready(page)

        # Check feed list padding on desktop
        feed_padding = page.evaluate("""() => {
            const feedList = document.getElementById('feed-list');
            const articleDetail = document.getElementById('article-detail');

            const feedStyles = window.getComputedStyle(feedList);
            const articleStyles = window.getComputedStyle(articleDetail);

            return {
                feed: {
                    left: feedStyles.paddingLeft,
                    right: feedStyles.paddingRight
                },
                article: {
                    left: articleStyles.paddingLeft,
                    right: articleStyles.paddingRight
                }
            };
        }""")

        # Desktop should have padding
        assert feed_padding['feed']['left'] == '16px', \
            f"Desktop feed list should have 16px left padding (lg:px-4), got {feed_padding['feed']['left']}"
        assert feed_padding['feed']['right'] == '16px', \
            f"Desktop feed list should have 16px right padding (lg:px-4), got {feed_padding['feed']['right']}"

        assert feed_padding['article']['left'] == '24px', \
            f"Desktop article should have 24px left padding (lg:px-6), got {feed_padding['article']['left']}"
        assert feed_padding['article']['right'] == '24px', \
            f"Desktop article should have 24px right padding (lg:px-6), got {feed_padding['article']['right']}"

        print("✅ Desktop padding matches production (feed: 16px, article: 24px)")

    def test_multiple_resize_cycles(self, page: Page, test_server_url):
        """Test multiple resize cycles to ensure no state pollution"""
        page.goto(test_server_url, wait_until="domcontentloaded", timeout=TIMEOUT_PAGE_LOAD)
        wait_for_page_ready(page)

        # Cycle through viewports multiple times
        viewports = [
            {"width": 390, "height": 844},   # Mobile
            {"width": 1400, "height": 900},  # Desktop
            {"width": 390, "height": 844},   # Mobile again
            {"width": 1400, "height": 900},  # Desktop again
        ]

        for i, viewport in enumerate(viewports):
            page.set_viewport_size(viewport)
            # Wait for overlay display to settle after viewport change
            page.wait_for_function(
                """() => {
                    const overlay = document.getElementById('sidebar-overlay');
                    if (!overlay) return false;
                    // Overlay should be hidden regardless of viewport
                    return window.getComputedStyle(overlay).display === 'none';
                }""",
                timeout=TIMEOUT_ANIMATION
            )

            is_mobile = viewport['width'] < 1024

            # Check overlay visibility
            overlay_display = page.evaluate("""() => {
                const overlay = document.getElementById('sidebar-overlay');
                return window.getComputedStyle(overlay).display;
            }""")

            if is_mobile:
                # On mobile, overlay should be hidden (unless sidebar is open)
                assert overlay_display == 'none', \
                    f"Cycle {i+1} (mobile): Overlay should be hidden, got {overlay_display}"
            else:
                # On desktop, overlay should ALWAYS be hidden (lg:!hidden)
                assert overlay_display == 'none', \
                    f"Cycle {i+1} (desktop): Overlay should be hidden, got {overlay_display}"

            # App should be clickable
            feed_items = page.locator("li[id^='feed-item-']")
            expect(feed_items.first).to_be_visible(timeout=TIMEOUT_ELEMENT_VISIBLE)

        print("✅ All resize cycles successful - no state pollution")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
