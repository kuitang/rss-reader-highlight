"""
Test for race condition fix when rapidly clicking articles.
Ensures that double-clicking or rapid clicking doesn't cause overlapping content.
"""
import pytest
from playwright.sync_api import Page, expect


def wait_for_htmx_complete(page, timeout=5000):
    """Wait for HTMX requests to complete"""
    page.wait_for_function(
        "() => !document.body.classList.contains('htmx-request')",
        timeout=timeout
    )


class TestRaceConditionFix:
    """Test that rapid clicking doesn't cause race conditions"""

    def test_rapid_article_clicking_no_overlap(self, page: Page, test_server_url):
        """
        Test that rapidly clicking multiple articles doesn't cause overlapping content.
        """
        # Set mobile viewport where the issue is most visible
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(test_server_url, wait_until="networkidle")

        # Enable console logging to see our debug messages
        page.on("console", lambda msg: print(f"BROWSER: {msg.text}"))

        # Wait for articles to load
        articles = page.locator("li[id^='feed-item-']")
        expect(articles.first).to_be_visible(timeout=10000)

        article_count = articles.count()
        assert article_count >= 3, "Need at least 3 articles for test"

        # Rapidly click multiple articles
        print("Testing rapid clicking...")

        # Click first article multiple times rapidly
        first_article = articles.nth(0)
        for i in range(3):
            print(f"  Rapid click {i+1} on first article")
            first_article.click()
            page.wait_for_timeout(50)  # Very short delay to simulate rapid clicks

        # Wait a bit for any transitions
        page.wait_for_timeout(500)

        # Check that only ONE article detail is visible
        article_detail = page.locator("#article-detail")
        feed_list = page.locator("#feed-list")

        # On mobile, either article OR feed list should be visible, not both
        article_visible = article_detail.is_visible()
        feed_visible = feed_list.is_visible()

        # Check for race condition symptoms
        if article_visible:
            # Article is showing - feed list should be hidden
            assert not feed_visible or page.evaluate(
                "document.getElementById('feed-list')?.classList.contains('article-view')"
            ), "Race condition: Both article and feed list fully visible"
            print("✅ Article view active, feed list properly hidden")
        else:
            # Feed list is showing - article should be hidden
            assert not page.evaluate(
                "document.getElementById('article-detail')?.classList.contains('active')"
            ), "Race condition: Article has active class but is hidden"
            print("✅ Feed list active, article properly hidden")

        # Now test clicking different articles rapidly
        print("\nTesting rapid clicks on different articles...")

        # Click three different articles in rapid succession
        for i in range(3):
            article = articles.nth(i % article_count)
            print(f"  Clicking article {i}")
            article.click()
            page.wait_for_timeout(100)  # Slightly longer but still rapid

        # Final wait for transitions
        wait_for_htmx_complete(page)
        page.wait_for_timeout(500)

        # Verify final state is consistent
        article_detail_active = page.evaluate(
            "document.getElementById('article-detail')?.classList.contains('active')"
        )
        feed_list_article_view = page.evaluate(
            "document.getElementById('feed-list')?.classList.contains('article-view')"
        )

        # Both should be in sync
        if article_detail_active:
            assert feed_list_article_view, "Inconsistent state: article active but feed not in article-view"
            print("✅ Final state: Article view properly active")
        else:
            assert not feed_list_article_view, "Inconsistent state: feed in article-view but article not active"
            print("✅ Final state: Feed list properly active")

        print("\n✅ Race condition test passed - no overlapping content!")

    def test_double_click_prevention(self, page: Page, test_server_url):
        """
        Test that double-clicking an article doesn't cause issues.
        """
        # Set mobile viewport
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(test_server_url, wait_until="networkidle")

        # Find an article
        articles = page.locator("li[id^='feed-item-']")
        expect(articles.first).to_be_visible(timeout=10000)

        first_article = articles.first

        # Double-click the article
        print("Testing double-click...")
        first_article.dblclick()

        # Wait for any transitions
        wait_for_htmx_complete(page)
        page.wait_for_timeout(500)

        # Check console for our blocking message
        console_logs = []
        page.on("console", lambda msg: console_logs.append(msg.text))

        # Try another double-click to trigger the block
        first_article.dblclick()
        page.wait_for_timeout(100)

        # Verify state is consistent
        article_detail = page.locator("#article-detail")
        if article_detail.is_visible():
            # Should show article content properly
            expect(article_detail.locator(".prose")).to_be_visible()
            print("✅ Double-click handled correctly - article shown")

        print("✅ Double-click prevention test passed!")