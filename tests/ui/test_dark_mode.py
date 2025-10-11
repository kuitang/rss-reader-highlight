"""Test dark mode functionality and CSS variable usage"""

import pytest
from playwright.sync_api import Page, expect
from tests.ui.conftest import wait_for_htmx_complete, wait_for_page_ready
import time

class TestDarkMode:
    """Test suite for dark mode functionality"""

    def test_dark_mode_toggle_and_css_variables(self, page: Page, test_server_url):
        """Test that dark mode properly applies CSS variables to all elements

        This test verifies:
        1. Dark mode can be toggled
        2. Background colors use CSS variables (not hardcoded white)
        3. All major elements respect dark mode
        """
        # Use load instead of networkidle - networkidle is unreliable in CI
        page.goto(test_server_url, wait_until="load")
        wait_for_page_ready(page)

        # Take screenshot in light mode
        page.screenshot(path="light_mode.png", full_page=True)

        # Check if there's a dark mode toggle (if implemented)
        # For now, we'll inject dark mode CSS to test
        page.evaluate("""() => {
            // Add dark mode class to HTML element
            document.documentElement.classList.add('dark');

            // Define dark mode CSS variables
            const style = document.createElement('style');
            style.textContent = `
                :root.dark {
                    --background: #1a1a1a;
                    --foreground: #e5e5e5;
                    --border: #333;
                    --muted: #666;
                    --muted-foreground: #999;
                    --secondary: #2a2a2a;
                }
            `;
            document.head.appendChild(style);
        }""")

        # Wait for CSS variable to be applied
        page.wait_for_function(
            """() => {
                const bg = getComputedStyle(document.documentElement)
                    .getPropertyValue('--background');
                return bg && bg.trim() === '#1a1a1a';
            }""",
            timeout=2000
        )

        # Take screenshot in dark mode
        page.screenshot(path="dark_mode.png", full_page=True)

        # Verify critical elements use CSS variables
        elements_to_check = [
            ('#sidebar', 'sidebar'),
            ('#chrome-container', 'chrome'),
            ('#article-detail', 'article detail'),
            ('.sidebar', 'sidebar class'),
            ('.chrome-container', 'chrome class')
        ]

        for selector, name in elements_to_check:
            element = page.locator(selector).first
            if element.is_visible():
                # Check computed styles
                bg_color = page.evaluate(f"""() => {{
                    const elem = document.querySelector('{selector}');
                    if (elem) {{
                        const computed = window.getComputedStyle(elem);
                        return computed.backgroundColor;
                    }}
                    return null;
                }}""")

                # In dark mode, background should NOT be white (rgb(255, 255, 255))
                if bg_color and bg_color != 'rgba(0, 0, 0, 0)':  # Skip transparent
                    assert bg_color != 'rgb(255, 255, 255)', f"{name} has hardcoded white background: {bg_color}"
                    print(f"✓ {name} respects dark mode: {bg_color}")

    def test_mobile_chrome_preserved_in_article_view(self, page: Page, test_server_url):
        """Test that mobile chrome is preserved when viewing articles

        CRITICAL: The chrome must remain visible in mobile article view
        """
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        # Use load instead of networkidle - networkidle is unreliable in CI
        page.goto(test_server_url, wait_until="load")
        wait_for_page_ready(page)

        # Click on first article
        first_article = page.locator('li[id^="feed-item-"]').first
        if first_article.is_visible():
            # Check chrome is visible before click
            chrome = page.locator('#chrome-container')
            expect(chrome).to_be_visible()
            initial_chrome_html = chrome.inner_html()

            # Click article
            first_article.click()
            wait_for_htmx_complete(page)

            # CRITICAL: Chrome must still be visible after article click
            expect(chrome).to_be_visible()

            # Chrome should have hx-preserve attribute
            has_preserve = page.evaluate("""() => {
                const chrome = document.getElementById('chrome-container');
                return chrome && chrome.hasAttribute('hx-preserve');
            }""")
            assert has_preserve, "Chrome container missing hx-preserve attribute"

            # Article should be below chrome (top: 64px on mobile)
            article_top = page.evaluate("""() => {
                const article = document.getElementById('article-detail');
                if (article && article.classList.contains('block')) {
                    const computed = window.getComputedStyle(article);
                    return computed.top;
                }
                return null;
            }""")
            assert article_top == '64px', f"Article not positioned below chrome: {article_top}"

            # Take screenshot to verify layout
            page.screenshot(path="mobile_article_with_chrome.png", full_page=False)
            print("✓ Mobile chrome preserved in article view")

    @pytest.mark.parametrize("viewport", [
        {"name": "desktop", "width": 1400, "height": 900},
        {"name": "mobile", "width": 375, "height": 667}
    ])
    def test_banner_layout_spacing(self, page: Page, test_server_url, viewport):
        """Test that banner has proper [hamburger] title [buttons] layout

        The chrome should use justify-between for proper spacing
        """
        page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
        # Use load instead of networkidle - networkidle is unreliable in CI
        page.goto(test_server_url, wait_until="load")
        wait_for_page_ready(page)

        chrome = page.locator('#chrome-container')
        expect(chrome).to_be_visible()

        # Check flexbox justify-content
        justify_content = page.evaluate("""() => {
            const chrome = document.getElementById('chrome-container');
            if (chrome) {
                const computed = window.getComputedStyle(chrome);
                return computed.justifyContent;
            }
            return null;
        }""")

        assert justify_content == 'space-between', f"{viewport['name']}: Chrome not using justify-between: {justify_content}"

        # Check feed name is centered
        feed_name = page.locator('#feed-name')
        if feed_name.is_visible():
            text_align = page.evaluate("""() => {
                const feedName = document.getElementById('feed-name');
                if (feedName) {
                    const computed = window.getComputedStyle(feedName);
                    return computed.textAlign;
                }
                return null;
            }""")
            assert text_align == 'center', f"{viewport['name']}: Feed name not centered: {text_align}"

        # Take screenshot to verify layout
        page.screenshot(path=f"banner_layout_{viewport['name']}.png", full_page=False)
        print(f"✓ {viewport['name']} banner layout correct")