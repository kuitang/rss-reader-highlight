"""
Regression test for mobile article viewing functionality.
Tests that clicking an article on mobile:
1. Marks the article as read
2. Shows the article detail view
3. Updates the navigation appropriately
"""
import pytest
from playwright.sync_api import Page, expect


def wait_for_htmx_complete(page, timeout=5000):
    """Wait for HTMX requests to complete"""
    page.wait_for_function(
        "() => !document.body.classList.contains('htmx-request')",
        timeout=timeout
    )

class TestMobileArticleViewing:
    """Test critical mobile article viewing functionality"""

    def test_mobile_article_click_shows_content(self, page: Page, test_server_url):
        """
        CRITICAL REGRESSION TEST: Ensure clicking article on mobile shows article content.
        This test verifies the fix for the article-detail ID mismatch issue.
        """
        # Set mobile viewport
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(test_server_url, wait_until="networkidle")

        # Wait for feed list to load
        feed_list = page.locator("#feed-list")
        expect(feed_list).to_be_visible(timeout=10000)

        # Find first unread article (with blue dot)
        unread_articles = page.locator("li[id^='feed-item-'] .bg-blue-600").all()
        assert len(unread_articles) > 0, "No unread articles found"

        # Get the parent article element
        first_article = page.locator("li[id^='feed-item-']").first
        article_id = first_article.get_attribute("id")
        article_title = first_article.locator("strong, span").first.text_content()

        print(f"Clicking article: {article_id} - {article_title}")

        # Enable console logging to see debug messages
        page.on("console", lambda msg: print(f"BROWSER LOG [{msg.type}]: {msg.text}"))

        # Click the article
        first_article.click()

        # Wait for HTMX to complete
        wait_for_htmx_complete(page)

        # Check article detail state before assertion
        article_detail = page.locator("#article-detail")
        has_active_class = page.evaluate("document.getElementById('article-detail')?.classList.contains('active')")
        display_style = page.evaluate("window.getComputedStyle(document.getElementById('article-detail')).display")
        article_exists = page.evaluate("!!document.getElementById('article-detail')")

        print(f"Article detail debug:")
        print(f"  - Element exists: {article_exists}")
        print(f"  - Has 'active' class: {has_active_class}")
        print(f"  - Computed display: {display_style}")

        # CRITICAL: Verify article detail is shown
        expect(article_detail).to_be_visible(timeout=5000)

        # Verify article content is displayed
        article_content = article_detail.locator(".prose")
        expect(article_content).to_be_visible()

        # Verify the title is in the detail view
        detail_title = article_detail.locator("strong").first
        expect(detail_title).to_contain_text(article_title)

        # On mobile, feed list should be hidden
        expect(feed_list).not_to_be_visible()

        # Verify navigation button changed to back arrow
        nav_button = page.locator("#nav-button")
        expect(nav_button).to_be_visible()
        assert nav_button.get_attribute("data-mode") == "back", "Nav button should show back mode"

        # Check nav button attributes before click
        nav_button_mode = nav_button.get_attribute("data-mode")
        nav_button_hx_get = nav_button.get_attribute("hx-get")
        nav_button_hx_target = nav_button.get_attribute("hx-target")
        nav_button_onclick = nav_button.get_attribute("onclick")

        print(f"Nav button before click:")
        print(f"  - data-mode: {nav_button_mode}")
        print(f"  - hx-get: {nav_button_hx_get}")
        print(f"  - hx-target: {nav_button_hx_target}")
        print(f"  - onclick: {nav_button_onclick}")

        nav_button.click()
        wait_for_htmx_complete(page)

        # Give extra time for afterSwap handlers to complete
        page.wait_for_timeout(500)

        # Check feed list state after back navigation
        feed_list_has_article_view = page.evaluate("document.getElementById('feed-list')?.classList.contains('article-view')")
        article_has_active = page.evaluate("document.getElementById('article-detail')?.classList.contains('active')")

        print(f"After back navigation (with extra wait):")
        print(f"  - Feed list has 'article-view' class: {feed_list_has_article_view}")
        print(f"  - Article has 'active' class: {article_has_active}")

        # Feed list should be visible again
        expect(feed_list).to_be_visible()

        # Article should no longer have blue dot (marked as read)
        updated_article = page.locator(f"#{article_id}")
        blue_dot = updated_article.locator(".bg-blue-600")
        expect(blue_dot).not_to_be_visible()

        print("✅ Mobile article viewing test passed!")

    def test_desktop_article_click_shows_sidebar(self, page: Page, test_server_url):
        """
        Test that desktop article clicking works correctly with side-by-side view.
        """
        # Set desktop viewport
        page.set_viewport_size({"width": 1400, "height": 900})
        page.goto(test_server_url, wait_until="networkidle")

        # Wait for feed list to load
        feed_list = page.locator("#feed-list")
        expect(feed_list).to_be_visible(timeout=10000)

        # Article detail should be visible but empty initially
        article_detail = page.locator("#article-detail")
        expect(article_detail).to_be_visible()
        expect(article_detail).to_contain_text("Select a post to read")

        # Click first article
        first_article = page.locator("li[id^='feed-item-']").first
        article_title = first_article.locator("strong, span").first.text_content()
        first_article.click()

        wait_for_htmx_complete(page)

        # Both feed list and article detail should be visible (side by side)
        expect(feed_list).to_be_visible()
        expect(article_detail).to_be_visible()

        # Article content should be shown
        expect(article_detail).not_to_contain_text("Select a post to read")
        detail_title = article_detail.locator("strong").first
        expect(detail_title).to_contain_text(article_title)

        print("✅ Desktop article viewing test passed!")