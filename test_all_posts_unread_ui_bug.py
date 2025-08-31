"""Playwright test for All Posts vs Unread view bug - UI verification"""

import pytest
from playwright.sync_api import sync_playwright, expect

TEST_URL = "http://localhost:5001"

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()

class TestAllPostsVsUnreadUIBehavior:
    """UI regression test for All Posts vs Unread view behavior"""
    
    def test_all_posts_should_keep_read_articles_visible(self, page):
        """CRITICAL: All Posts view should show read articles, Unread view should hide them
        
        Bug: All Posts view was hiding read articles like Unread view.
        Requires: Server running on localhost:5001
        """
        page.goto(TEST_URL)
        page.wait_for_timeout(5000)  # Wait for articles to load
        
        # 1. Start in All Posts view
        all_posts_tab = page.locator("button:has-text('All Posts')")
        all_posts_tab.click()
        page.wait_for_timeout(1000)
        
        # 2. Count initial articles
        initial_articles = page.locator("li[id^='feed-item-']")
        initial_count = initial_articles.count()
        
        if initial_count == 0:
            pytest.skip("No articles available to test")
        
        # 3. Find an article with blue dot (unread)
        articles_with_blue = page.locator("li:has(.bg-blue-600)")
        unread_count = articles_with_blue.count()
        
        if unread_count == 0:
            pytest.skip("No unread articles (blue dots) to test")
        
        # 4. Click first unread article
        first_unread = articles_with_blue.first
        article_title = first_unread.locator("strong").text_content()
        first_unread.click()
        page.wait_for_timeout(1000)  # Wait for HTMX response
        
        # 5. CRITICAL: Article should STILL be visible in All Posts view
        clicked_article = page.locator(f"strong:has-text('{article_title}')")
        expect(clicked_article).to_be_visible(), f"Article '{article_title}' should remain visible in All Posts view"
        
        # 6. Blue dot should be gone (article marked as read)
        article_container = page.locator(f"li:has(strong:has-text('{article_title}'))")
        blue_dot_in_article = article_container.locator(".bg-blue-600")
        expect(blue_dot_in_article).not_to_be_visible(), "Blue dot should disappear after clicking"
        
        # 7. Detail view should show the article
        expect(page.locator("#item-detail")).to_contain_text(article_title)
        
        # 8. Switch to Unread view
        unread_tab = page.locator("button:has-text('Unread')")
        unread_tab.click()
        page.wait_for_timeout(1000)
        
        # 9. CRITICAL: Read article should NOT appear in Unread view
        read_article_in_unread = page.locator(f"strong:has-text('{article_title}')")
        expect(read_article_in_unread).not_to_be_visible(), f"Read article '{article_title}' should not appear in Unread view"
        
        # 10. Switch back to All Posts
        all_posts_tab.click() 
        page.wait_for_timeout(1000)
        
        # 11. CRITICAL: Read article should reappear in All Posts view
        read_article_in_all = page.locator(f"strong:has-text('{article_title}')")
        expect(read_article_in_all).to_be_visible(), f"Read article '{article_title}' should reappear in All Posts view"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])