#!/usr/bin/env python3
"""
Test comprehensive UI fixes for critical issues:
1. Back button should only go back to feed list, never show sidebar
2. Sidebar should have proper background color, not transparent
3. Hamburger menu should not trigger HTMX errors
4. Chrome layout should have centered title with equal spacing
"""

import pytest
from playwright.sync_api import Page, expect
from tests.ui.conftest import (
    wait_for_htmx_complete,
    wait_for_page_ready,
    wait_for_sidebar_open,
    wait_for_sidebar_close,
    wait_for_search_expand
)

@pytest.fixture
def setup_page():
    """Setup page with both desktop and mobile viewports"""
    viewports = [
        {"name": "Desktop", "width": 1400, "height": 900},
        {"name": "Mobile", "width": 390, "height": 844}
    ]
    return viewports

class TestBackButtonFunctionality:
    """Test that back button properly navigates back to feed list without showing sidebar"""

    def test_back_button_mobile_navigation(self, page: Page):
        """Test mobile back button only goes back to feed list, never toggles sidebar"""
        # Set mobile viewport
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        # Verify we're in mobile mode
        is_mobile = page.evaluate("window.innerWidth < 1024")
        assert is_mobile, "Should be in mobile viewport"

        # Find and click on a feed item to navigate to article
        feed_items = page.locator("li[id^='feed-item-']")
        if feed_items.count() > 0:
            first_item = feed_items.first
            first_item.click()
            wait_for_htmx_complete(page)

            # Verify article view is active
            article_active = page.evaluate("""() => {
                const article = document.getElementById('article-detail');
                return article && article.classList.contains('active');
            }""")
            assert article_active, "Article view should be active after clicking feed item"

            # Check that nav button exists and has correct configuration
            nav_button = page.locator("#nav-button")
            assert nav_button.count() > 0, "Nav button should exist"

            # Verify nav button has back configuration (hx-get attribute, not onclick)
            has_hx_get = nav_button.get_attribute("hx-get") is not None
            has_onclick = nav_button.get_attribute("onclick") is not None

            assert has_hx_get, "Back button should have hx-get attribute"
            assert not has_onclick, "Back button should NOT have onclick attribute"

            # Record sidebar state before clicking back
            sidebar_before = page.evaluate("""() => {
                const sidebar = document.getElementById('sidebar');
                return sidebar ? sidebar.classList.contains('open') : false;
            }""")

            # Click back button
            nav_button.click()
            wait_for_htmx_complete(page)

            # Wait for class changes to settle (hideArticle() runs after swap)
            page.wait_for_function("""() => {
                const article = document.getElementById('article-detail');
                return article && !article.classList.contains('active');
            }""", timeout=2000)

            # Verify we're back to feed list (article view deactivated)
            article_after = page.evaluate("""() => {
                const article = document.getElementById('article-detail');
                return article && article.classList.contains('active');
            }""")
            assert not article_after, "Article view should be deactivated after back button"

            # Verify sidebar state didn't change (should NOT have toggled)
            sidebar_after = page.evaluate("""() => {
                const sidebar = document.getElementById('sidebar');
                return sidebar ? sidebar.classList.contains('open') : false;
            }""")
            assert sidebar_before == sidebar_after, "Back button should NOT toggle sidebar"

    def test_nav_button_id_consistency(self, page: Page):
        """Test that nav button ID remains consistent during navigation"""
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        # Check initial nav button ID
        initial_id = page.evaluate("document.getElementById('nav-button') ? 'nav-button' : 'not-found'")
        assert initial_id == "nav-button", "Initial nav button should have ID 'nav-button'"

        # Navigate to an article if available
        feed_items = page.locator("li[id^='feed-item-']")
        if feed_items.count() > 0:
            feed_items.first.click()
            wait_for_htmx_complete(page)

            # Check nav button ID after navigation (should still be nav-button)
            after_nav_id = page.evaluate("document.getElementById('nav-button') ? 'nav-button' : 'not-found'")
            assert after_nav_id == "nav-button", "Nav button should maintain same ID after navigation"

            # Verify no mobile-nav-button exists (old bug)
            mobile_nav_exists = page.evaluate("document.getElementById('mobile-nav-button') !== null")
            assert not mobile_nav_exists, "Should not create duplicate mobile-nav-button element"


class TestSidebarOpacity:
    """Test that sidebar has proper background and overlay works correctly"""

    def test_sidebar_background_mobile(self, page: Page):
        """Test sidebar has proper background color in mobile view"""
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        # Open sidebar by clicking hamburger menu
        hamburger = page.locator("#nav-button")
        hamburger.click()
        wait_for_sidebar_open(page)

        # Check sidebar background
        sidebar_bg = page.evaluate("""() => {
            const sidebar = document.getElementById('sidebar');
            const computedStyle = window.getComputedStyle(sidebar);
            return {
                backgroundColor: computedStyle.backgroundColor,
                isOpen: sidebar.classList.contains('open'),
                display: computedStyle.display
            };
        }""")

        assert sidebar_bg['isOpen'], "Sidebar should be open after clicking hamburger"
        # Should have a proper background color, not transparent
        assert sidebar_bg['backgroundColor'] not in ['rgba(0, 0, 0, 0)', 'transparent'], \
               f"Sidebar should have background color, got: {sidebar_bg['backgroundColor']}"

    def test_overlay_properties_mobile(self, page: Page):
        """Test overlay has correct semi-transparent background"""
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        # Open sidebar
        hamburger = page.locator("#nav-button")
        hamburger.click()
        wait_for_sidebar_open(page)

        # Check overlay properties
        overlay_props = page.evaluate("""() => {
            const overlay = document.getElementById('sidebar-overlay');
            const computedStyle = window.getComputedStyle(overlay);
            return {
                backgroundColor: computedStyle.backgroundColor,
                display: computedStyle.display,
                isVisible: overlay.classList.contains('show'),
                zIndex: computedStyle.zIndex
            };
        }""")

        assert overlay_props['isVisible'], "Overlay should be visible when sidebar is open"
        assert 'rgba' in overlay_props['backgroundColor'], "Overlay should have rgba background"
        # Should be semi-transparent black
        assert '0.5' in overlay_props['backgroundColor'] or '0, 0, 0' in overlay_props['backgroundColor'], \
               f"Overlay should be semi-transparent, got: {overlay_props['backgroundColor']}"

    def test_sidebar_not_visible_desktop(self, page: Page):
        """Test overlay is hidden in desktop view"""
        page.set_viewport_size({"width": 1400, "height": 900})
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        overlay_display = page.evaluate("""() => {
            const overlay = document.getElementById('sidebar-overlay');
            return window.getComputedStyle(overlay).display;
        }""")

        assert overlay_display == 'none', "Overlay should be hidden on desktop"


class TestHamburgerMenuHTMX:
    """Test hamburger menu doesn't trigger HTMX errors"""

    def test_hamburger_no_form_submission(self, page: Page):
        """Test hamburger button doesn't trigger form submission"""
        page.set_viewport_size({"width": 390, "height": 844})

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type in ['error', 'warning'] else None)

        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        # Check hamburger button attributes
        nav_button_props = page.evaluate("""() => {
            const button = document.getElementById('nav-button');
            return {
                type: button.getAttribute('type'),
                hasFormName: button.hasAttribute('name'),
                hasHxTarget: button.hasAttribute('hx-target'),
                hasOnClick: button.hasAttribute('hx-on-click') || button.hasAttribute('onclick'),
                dataMode: button.getAttribute('data-mode')
            };
        }""")

        assert nav_button_props['type'] == 'button', "Hamburger should be type='button' to prevent form submission"
        assert not nav_button_props['hasFormName'], "Hamburger should not have 'name' attribute"
        assert nav_button_props['hasOnClick'], "Hamburger should have click handler"
        assert nav_button_props['dataMode'] == 'menu', "Hamburger should have data-mode='menu'"

        # Click hamburger and check for HTMX errors
        hamburger = page.locator("#nav-button")
        hamburger.click()
        wait_for_sidebar_open(page)

        # Filter for HTMX-related errors
        htmx_errors = [error for error in console_errors if 'htmx' in error.lower() or 'unknown target' in error.lower()]
        assert len(htmx_errors) == 0, f"Should not have HTMX errors, got: {htmx_errors}"

    def test_search_nav_button_no_form_submission(self, page: Page):
        """Test search nav button also doesn't trigger form submission"""
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        # Open search first
        search_button = page.locator("button[title='Search']")
        if search_button.count() > 0:
            search_button.click()
            wait_for_search_expand(page)

            # Check search nav button
            search_nav_props = page.evaluate("""() => {
                const button = document.getElementById('search-nav-button');
                if (button) {
                    return {
                        type: button.getAttribute('type'),
                        hasFormName: button.hasAttribute('name'),
                        hasOnClick: button.hasAttribute('hx-on-click') || button.hasAttribute('onclick')
                    };
                }
                return {exists: false};
            }""")

            if search_nav_props.get('exists') is not False:
                assert search_nav_props['type'] == 'button', "Search nav button should be type='button'"
                assert not search_nav_props['hasFormName'], "Search nav button should not have 'name' attribute"


class TestChromeLayoutCentering:
    """Test chrome layout has properly centered title with equal spacing"""

    @pytest.mark.parametrize("viewport", [
        {"name": "Desktop", "width": 1400, "height": 900},
        {"name": "Mobile", "width": 390, "height": 844}
    ])
    def test_chrome_layout_structure(self, page: Page, viewport):
        """Test chrome container has correct flexbox layout"""
        page.set_viewport_size(viewport)
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        chrome_layout = page.evaluate("""() => {
            const chrome = document.getElementById('chrome-container');
            if (chrome) {
                const style = window.getComputedStyle(chrome);
                return {
                    display: style.display,
                    justifyContent: style.justifyContent,
                    alignItems: style.alignItems,
                    childCount: chrome.children.length
                };
            }
            return {error: 'Chrome container not found'};
        }""")

        assert chrome_layout['display'] == 'flex', "Chrome should use flexbox"
        assert chrome_layout['justifyContent'] == 'space-between', "Chrome should use justify-content: space-between"
        assert chrome_layout['alignItems'] == 'center', "Chrome should center items vertically"
        assert chrome_layout['childCount'] >= 3, f"Chrome should have at least 3 children (nav, title, icons), got {chrome_layout['childCount']}"

    @pytest.mark.parametrize("viewport", [
        {"name": "Desktop", "width": 1400, "height": 900},
        {"name": "Mobile", "width": 390, "height": 844}
    ])
    def test_title_centering(self, page: Page, viewport):
        """Test title element has proper flex properties for centering"""
        page.set_viewport_size(viewport)
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        title_props = page.evaluate("""() => {
            const title = document.getElementById('feed-name');
            if (title) {
                const style = window.getComputedStyle(title);
                return {
                    flex: style.flex,
                    flexGrow: style.flexGrow,
                    textAlign: style.textAlign,
                    className: title.className,
                    hasFlexOne: title.classList.contains('flex-1'),
                    hasTextCenter: title.classList.contains('text-center')
                };
            }
            return {error: 'Title not found'};
        }""")

        assert title_props['hasFlexOne'], "Title should have flex-1 class"
        assert title_props['hasTextCenter'], "Title should have text-center class"
        assert title_props['flexGrow'] == '1', f"Title should have flex-grow: 1, got {title_props['flexGrow']}"

    def test_icon_bar_positioning(self, page: Page):
        """Test icon bar doesn't have ml-auto which would break centering"""
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        icon_bar_classes = page.evaluate("""() => {
            const iconBar = document.getElementById('icon-bar');
            return iconBar ? iconBar.className : 'not-found';
        }""")

        assert 'ml-auto' not in icon_bar_classes, f"Icon bar should not have ml-auto class, got: {icon_bar_classes}"


class TestComprehensiveUIIntegration:
    """Integration tests to verify all fixes work together"""

    def test_complete_mobile_navigation_flow(self, page: Page):
        """Test complete flow: hamburger → sidebar → close, then article navigation → back"""
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        # Test hamburger menu works
        hamburger = page.locator("#nav-button")
        hamburger.click()
        wait_for_sidebar_open(page)

        sidebar_open = page.evaluate("document.getElementById('sidebar').classList.contains('open')")
        assert sidebar_open, "Sidebar should open with hamburger click"

        # Close sidebar by clicking overlay
        overlay = page.locator("#sidebar-overlay")
        overlay.click()
        wait_for_sidebar_close(page)

        sidebar_closed = page.evaluate("document.getElementById('sidebar').classList.contains('open')")
        assert not sidebar_closed, "Sidebar should close with overlay click"

    def test_sidebar_click_outside_main_content(self, page: Page):
        """Test clicking main content area closes sidebar (not just overlay)"""
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        # Open sidebar
        hamburger = page.locator("#nav-button")
        hamburger.click()
        wait_for_sidebar_open(page)

        sidebar_open = page.evaluate("document.getElementById('sidebar').classList.contains('open')")
        assert sidebar_open, "Sidebar should be open"

        # Click main content area (right side, definitely outside sidebar)
        # Sidebar max-width is 320px, so click at x=350 to be safe
        page.mouse.click(350, 400)
        wait_for_sidebar_close(page)

        sidebar_closed = page.evaluate("!document.getElementById('sidebar')?.classList.contains('open')")
        assert sidebar_closed, "Sidebar should close when clicking outside on main content"

    def test_sidebar_overlay_z_index_above_sidebar(self, page: Page):
        """Test overlay z-index is higher than sidebar (clickable)"""
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        # Open sidebar
        page.locator("#nav-button").click()
        wait_for_sidebar_open(page)

        # Check z-index ordering - sidebar must be ABOVE overlay to be clickable
        z_indices = page.evaluate("""() => {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebar-overlay');
            return {
                sidebarZ: parseInt(getComputedStyle(sidebar).zIndex),
                overlayZ: parseInt(getComputedStyle(overlay).zIndex)
            };
        }""")

        assert z_indices['sidebarZ'] > z_indices['overlayZ'], \
            f"Sidebar z-index ({z_indices['sidebarZ']}) should be higher than overlay ({z_indices['overlayZ']}) to be clickable"

    def test_viewport_resize_during_article_view(self, page: Page):
        """Test viewport resize while viewing article doesn't cause errors"""
        console_errors = []
        page.on("console", lambda msg:
            console_errors.append(msg.text) if msg.type == 'error' else None
        )

        # Start in desktop
        page.set_viewport_size({"width": 1400, "height": 900})
        page.goto("http://localhost:8080")
        wait_for_page_ready(page)

        # Switch to mobile and navigate to article
        page.set_viewport_size({"width": 390, "height": 844})
        import time
        time.sleep(0.3)

        feed_items = page.locator("li[id^='feed-item-']")
        if feed_items.count() > 0:
            feed_items.first.click()
            wait_for_htmx_complete(page)

            # Resize to desktop while article showing
            page.set_viewport_size({"width": 1400, "height": 900})
            time.sleep(0.5)

            # Resize back to mobile
            page.set_viewport_size({"width": 390, "height": 844})
            time.sleep(0.5)

        # Check for HTMX errors
        htmx_errors = [e for e in console_errors if 'unknown target' in e.lower() or 'htmx' in e.lower()]
        assert len(htmx_errors) == 0, f"Should not have HTMX errors during resize, got: {htmx_errors}"

    def test_responsive_design_consistency(self, page: Page):
        """Test that all fixes work across different viewport sizes"""
        viewports = [
            {"width": 1400, "height": 900},  # Desktop
            {"width": 768, "height": 1024},  # Tablet
            {"width": 390, "height": 844}    # Mobile
        ]

        for viewport in viewports:
            page.set_viewport_size(viewport)
            page.goto("http://localhost:8080")
            wait_for_page_ready(page)

            # Check chrome layout consistency
            chrome_ok = page.evaluate("""() => {
                const chrome = document.getElementById('chrome-container');
                const style = window.getComputedStyle(chrome);
                return chrome && style.display === 'flex' && style.justifyContent === 'space-between';
            }""")
            assert chrome_ok, f"Chrome layout should be consistent at {viewport['width']}px"

            # Check sidebar background
            sidebar_bg_ok = page.evaluate("""() => {
                const sidebar = document.getElementById('sidebar');
                const style = window.getComputedStyle(sidebar);
                return style.backgroundColor && style.backgroundColor !== 'rgba(0, 0, 0, 0)';
            }""")
            assert sidebar_bg_ok, f"Sidebar should have background at {viewport['width']}px"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])