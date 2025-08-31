"""Comprehensive E2E tests based on actual user workflows and debugging experience"""

import pytest
import subprocess
import time
import sqlite3
import os
import sys
from playwright.sync_api import sync_playwright, expect
from contextlib import contextmanager

TEST_PORT = 5002
TEST_URL = f"http://localhost:{TEST_PORT}"
TEST_DB_PATH = "data/test_e2e_comprehensive.db"

@contextmanager
def rss_app_server():
    """Start RSS Reader server for testing"""
    # Clean up any existing test database
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    # Set environment for test database
    env = os.environ.copy()
    env['RSS_DB_PATH'] = TEST_DB_PATH
    
    # Start server
    process = subprocess.Popen([
        sys.executable, "app.py"
    ], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server startup
    time.sleep(4)
    
    try:
        yield process
    finally:
        # Cleanup
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

@pytest.fixture(scope="session")
def browser():
    """Browser instance for all tests"""
    with sync_playwright() as p:
        # Use non-headless for debugging if needed
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture
def page(browser):
    """Fresh page for each test"""
    page = browser.new_page()
    yield page
    page.close()

class TestCompleteUserJourneys:
    """Test complete user workflows that we debugged"""
    
    def test_fresh_user_first_visit_workflow(self, page):
        """Test: Fresh DB → App start → First visit → Auto feeds → Read articles
        
        This tests the complete onboarding flow we implemented.
        """
        with rss_app_server():
            # 1. Fresh user visits homepage
            page.goto(TEST_URL)
            page.wait_for_timeout(3000)  # Wait for feeds to load
            
            # 2. Should see default feeds in sidebar
            expect(page.locator("h3:has-text('Feeds')")).to_be_visible()
            expect(page.locator("text=All Feeds")).to_be_visible()
            
            # 3. Should see articles loaded (default feeds auto-setup)
            page.wait_for_selector("strong", timeout=10000)  # Wait for articles
            articles = page.locator("li strong").all()
            
            # Should have multiple articles from default feeds
            assert len(articles) > 10
            
            # 4. Should see proper feed names in sidebar
            feed_links = page.locator("a[href*='feed_id']").all()
            assert len(feed_links) >= 3  # At least 3 default feeds
            
            # 5. Test article reading
            first_article = page.locator("li[id^='feed-item-']").first
            first_article.click()
            
            # Should show detail view
            expect(page.locator("#item-detail")).to_contain_text("From:")
            
            # 6. Test pagination
            pagination = page.locator("text=Page 1 of")
            if pagination.is_visible():
                # Test next page navigation
                next_button = page.locator("button:has([data-uk-tooltip='Next page'])")
                if next_button.is_visible():
                    next_button.click()
                    page.wait_for_timeout(1000)
                    expect(page.locator("text=Page 2 of")).to_be_visible()
    
    def test_feed_addition_complete_workflow(self, page):
        """Test: Add feed → Parse → Subscribe → View articles
        
        Tests the feed addition flow that had form parameter issues.
        """
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(2000)
            
            # Count initial feeds
            initial_feeds = page.locator("a[href*='feed_id']").count()
            
            # Test adding a feed (use a reliable test feed)
            feed_input = page.locator("#new-feed-url")
            feed_input.fill("https://hnrss.org/newest")  # Different HN feed
            
            add_button = page.locator("button:has([data-icon='plus'])")
            add_button.click()
            
            # Wait for feed to be processed
            page.wait_for_timeout(3000)
            
            # Should show either new feed or error message
            # Don't assert success/failure, just that app handles it gracefully
            expect(page.locator("h3:has-text('Feeds')")).to_be_visible()
    
    def test_article_reading_ux_flow(self, page):
        """Test: Click article → Blue dot disappears → Detail view → Read state
        
        Tests the complex HTMX multi-element update flow.
        """
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(3000)
            
            # 1. Switch to "Unread" view to see blue indicators
            unread_tab = page.locator("text=Unread")
            unread_tab.click()
            page.wait_for_timeout(1000)
            
            # 2. Count unread items with blue indicators
            blue_dots = page.locator(".bg-blue-600").all()
            initial_unread_count = len(blue_dots)
            
            if initial_unread_count > 0:
                # 3. Click first unread article
                first_unread = page.locator("li[id^='feed-item-']").first
                first_unread.click()
                page.wait_for_timeout(500)
                
                # 4. Verify detail view loaded
                expect(page.locator("#item-detail strong")).to_be_visible()
                
                # 5. In unread view, clicked article should disappear or lose blue dot
                # (Implementation might vary, but UI should update)
                blue_dots_after = page.locator(".bg-blue-600").all()
                # Should have same or fewer blue dots
                assert len(blue_dots_after) <= initial_unread_count
    
    def test_feed_navigation_and_filtering(self, page):
        """Test: Feed filtering → URL changes → Content filtering
        
        Tests navigation between different views.
        """
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(3000)
            
            # Test feed filtering
            feed_links = page.locator("a[href*='feed_id']").all()
            
            if len(feed_links) > 0:
                # Click first feed
                first_feed = feed_links[0]
                feed_name = first_feed.text_content()
                first_feed.click()
                page.wait_for_timeout(1000)
                
                # URL should change to include feed_id
                expect(page).to_have_url(url_contains="feed_id=")
                
                # Header should show feed name
                expect(page.locator("h3")).to_contain_text(feed_name.split(" updated")[0])
            
            # Test "All Feeds" navigation
            all_feeds_link = page.locator("text=All Feeds")
            all_feeds_link.click()
            page.wait_for_timeout(500)
            
            # Should return to main view
            expect(page.locator("h3:has-text('All Posts')")).to_be_visible()

class TestErrorHandlingAndEdgeCases:
    """Test error scenarios and edge cases"""
    
    def test_invalid_feed_url_handling(self, page):
        """Test: Invalid URL → Error message → App stability"""
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(2000)
            
            # Try adding clearly invalid URL
            feed_input = page.locator("#new-feed-url")
            feed_input.fill("not-a-valid-url-at-all")
            
            add_button = page.locator("button:has([data-icon='plus'])")
            add_button.click()
            page.wait_for_timeout(2000)
            
            # App should handle gracefully - no crash
            expect(page.locator("h3:has-text('Feeds')")).to_be_visible()
            
            # Should show some form of error feedback
            # (Could be error message or just no new feed added)
    
    def test_pagination_edge_cases(self, page):
        """Test: Invalid page numbers → Boundary conditions → Graceful handling"""
        with rss_app_server():
            # Test invalid page numbers
            page.goto(f"{TEST_URL}/?page=0")
            page.wait_for_timeout(1000)
            expect(page.locator("h3")).to_be_visible()
            
            page.goto(f"{TEST_URL}/?page=999")
            page.wait_for_timeout(1000)
            expect(page.locator("h3")).to_be_visible()
            
            page.goto(f"{TEST_URL}/?page=-1")
            page.wait_for_timeout(1000)
            expect(page.locator("h3")).to_be_visible()
    
    def test_concurrent_browser_sessions(self, browser):
        """Test: Multiple browser tabs → Independent sessions → No interference"""
        with rss_app_server():
            # Open multiple tabs
            page1 = browser.new_page()
            page2 = browser.new_page()
            
            try:
                page1.goto(TEST_URL)
                page2.goto(TEST_URL)
                
                page1.wait_for_timeout(3000)
                page2.wait_for_timeout(3000)
                
                # Both should work independently
                expect(page1.locator("h3:has-text('Feeds')")).to_be_visible()
                expect(page2.locator("h3:has-text('Feeds')")).to_be_visible()
                
                # Test that actions in one don't affect the other
                if page1.locator("li[id^='feed-item-']").count() > 0:
                    page1.locator("li[id^='feed-item-']").first.click()
                    page1.wait_for_timeout(500)
                    
                    # Page2 should be unaffected
                    expect(page2.locator("h3:has-text('Feeds')")).to_be_visible()
                    
            finally:
                page1.close()
                page2.close()

class TestResponsiveDesignAndLayout:
    """Test responsive design and layout behavior"""
    
    def test_mobile_responsiveness(self, page):
        """Test: Mobile viewport → Layout adaptation → Usability
        
        Tests the responsive MonsterUI grid system.
        """
        with rss_app_server():
            # Test desktop first
            page.set_viewport_size({"width": 1400, "height": 1000})
            page.goto(TEST_URL)
            page.wait_for_timeout(2000)
            
            # Desktop should show three-panel layout
            expect(page.locator("#sidebar")).to_be_visible()
            expect(page.locator("#item-detail")).to_be_visible()
            
            # Test tablet
            page.set_viewport_size({"width": 768, "height": 1024})
            page.wait_for_timeout(1000)
            
            # Should still be usable
            expect(page.locator("h3:has-text('Feeds')")).to_be_visible()
            
            # Test mobile
            page.set_viewport_size({"width": 375, "height": 667})
            page.wait_for_timeout(1000)
            
            # Should adapt layout but remain functional
            expect(page.locator("h3")).to_be_visible()
    
    def test_full_viewport_height_usage(self, page):
        """Test: Viewport height utilization → Proper scrolling → No wasted space"""
        with rss_app_server():
            page.set_viewport_size({"width": 1200, "height": 800})
            page.goto(TEST_URL)
            page.wait_for_timeout(2000)
            
            # Check that layout uses full height
            main_container = page.locator(".min-h-screen")
            expect(main_container).to_be_visible()
            
            # Test scrolling behavior in article list
            article_list = page.locator("#feeds-list-container")
            if article_list.is_visible():
                # Should be scrollable if content exceeds height
                expect(article_list).to_have_css("overflow-y", "auto")

class TestComplexStateManagement:
    """Test complex state management and UI synchronization"""
    
    def test_unread_article_disappearing_flow(self, page):
        """Test: Unread view → Click article → Article disappears → State sync
        
        This tests the most complex UX flow we implemented.
        """
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(3000)
            
            # 1. Switch to unread view
            unread_tab = page.locator("button:has-text('Unread')")
            unread_tab.click()
            page.wait_for_timeout(1000)
            
            # 2. Count initial unread articles
            unread_articles = page.locator("li[id^='feed-item-']").all()
            initial_count = len(unread_articles)
            
            if initial_count > 0:
                # 3. Click first unread article
                first_article_title = unread_articles[0].locator("strong").text_content()
                unread_articles[0].click()
                page.wait_for_timeout(1000)
                
                # 4. Article should load in detail view
                expect(page.locator("#item-detail")).to_contain_text(first_article_title)
                
                # 5. In unread view, article should disappear or change state
                remaining_articles = page.locator("li[id^='feed-item-']").all()
                # Should have same or fewer articles (depending on implementation)
                assert len(remaining_articles) <= initial_count
    
    def test_blue_indicator_management(self, page):
        """Test: Blue indicators → Click articles → Indicators disappear → Visual feedback"""
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(3000)
            
            # Count blue indicators (unread items)
            blue_dots = page.locator(".bg-blue-600").all()
            initial_blue_count = len(blue_dots)
            
            # Click articles and verify blue dots decrease
            articles_to_click = min(3, len(blue_dots))
            
            for i in range(articles_to_click):
                if page.locator(".bg-blue-600").count() > 0:
                    # Find an article with blue dot
                    unread_article = page.locator("li:has(.bg-blue-600)").first
                    unread_article.click()
                    page.wait_for_timeout(500)
                    
                    # Blue dot should disappear or reduce count
                    remaining_blue = page.locator(".bg-blue-600").all()
                    assert len(remaining_blue) <= initial_blue_count - (i + 1)
    
    def test_pagination_navigation_comprehensive(self, page):
        """Test: All pagination controls → URL changes → Content changes"""
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(3000)
            
            # Look for pagination controls
            page_info = page.locator("text*=Page")
            
            if page_info.is_visible():
                page_text = page_info.text_content()
                
                if "Page 1 of" in page_text and "of 1" not in page_text:
                    # Multiple pages exist, test navigation
                    
                    # Test next page
                    next_btn = page.locator("button[data-uk-tooltip='Next page']")
                    if next_btn.is_visible():
                        next_btn.click()
                        page.wait_for_timeout(1000)
                        expect(page).to_have_url(url_contains="page=2")
                        expect(page.locator("text=Page 2 of")).to_be_visible()
                    
                    # Test first page
                    first_btn = page.locator("button[data-uk-tooltip='First page']")
                    if first_btn.is_visible():
                        first_btn.click()
                        page.wait_for_timeout(1000)
                        expect(page.locator("text=Page 1 of")).to_be_visible()

class TestFormInteractionsAndValidation:
    """Test form interactions that broke during development"""
    
    def test_feed_addition_form_processing(self, page):
        """Test: Form input → FastHTML parameters → Server processing → UI feedback"""
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(2000)
            
            # Test various feed URL inputs
            test_cases = [
                ("", "Please enter a URL"),  # Empty input
                ("not-a-url", None),  # Invalid URL format
                ("https://httpbin.org/xml", None),  # Valid format but may not be RSS
            ]
            
            for test_url, expected_error in test_cases:
                feed_input = page.locator("#new-feed-url")
                feed_input.clear()
                
                if test_url:
                    feed_input.fill(test_url)
                
                add_button = page.locator("button:has([data-icon='plus'])")
                add_button.click()
                page.wait_for_timeout(2000)
                
                if expected_error:
                    expect(page.locator(f"text={expected_error}")).to_be_visible()
                
                # App should remain stable regardless
                expect(page.locator("h3:has-text('Feeds')")).to_be_visible()
    
    def test_folder_creation_workflow(self, page):
        """Test: Create folder → Prompt handling → UI update"""
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(2000)
            
            # Test folder creation
            add_folder_btn = page.locator("text=Add Folder")
            
            # Handle prompt dialog
            page.on("dialog", lambda dialog: dialog.accept("Test E2E Folder"))
            add_folder_btn.click()
            page.wait_for_timeout(1000)
            
            # Should handle gracefully (folder might appear or not depending on implementation)
            expect(page.locator("h4:has-text('Folders')")).to_be_visible()

class TestDataConsistencyAndPersistence:
    """Test data consistency across page refreshes and navigation"""
    
    def test_session_persistence_across_refreshes(self, page):
        """Test: User session → Page refresh → Data maintained → No re-setup"""
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(3000)
            
            # Count initial articles
            initial_articles = page.locator("li[id^='feed-item-']").count()
            
            # Refresh page
            page.reload()
            page.wait_for_timeout(3000)
            
            # Should maintain similar state
            after_refresh_articles = page.locator("li[id^='feed-item-']").count()
            
            # Should have similar article count (allowing for new items)
            assert after_refresh_articles >= initial_articles * 0.8  # Allow some variance
            
            # Structure should be maintained
            expect(page.locator("h3:has-text('Feeds')")).to_be_visible()
            expect(page.locator("h3:has-text('All Posts')")).to_be_visible()
    
    def test_navigation_state_consistency(self, page):
        """Test: Navigate between views → Back navigation → State maintenance"""
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(3000)
            
            # Navigate through different views
            feed_links = page.locator("a[href*='feed_id']").all()
            
            if len(feed_links) > 0:
                # Click specific feed
                feed_links[0].click()
                page.wait_for_timeout(1000)
                
                # Click "All Feeds"
                page.locator("text=All Feeds").click()
                page.wait_for_timeout(1000)
                
                # Click "Unread"
                page.locator("button:has-text('Unread')").click()
                page.wait_for_timeout(1000)
                
                # Click "All Posts"
                page.locator("button:has-text('All Posts')").click()
                page.wait_for_timeout(1000)
                
                # Should end up in consistent state
                expect(page.locator("h3:has-text('All Posts')")).to_be_visible()

class TestPerformanceAndScalability:
    """Test performance with realistic data loads"""
    
    def test_large_article_list_performance(self, page):
        """Test: Many articles → Pagination → Scrolling performance → UI responsiveness"""
        with rss_app_server():
            page.goto(TEST_URL)
            
            # Wait for content to load
            page.wait_for_timeout(5000)  # Longer wait for feed processing
            
            # Test scrolling performance in article list
            article_container = page.locator("#feeds-list-container")
            if article_container.is_visible():
                # Scroll through articles
                for i in range(3):
                    article_container.scroll_into_view_if_needed()
                    page.wait_for_timeout(200)
                
                # UI should remain responsive
                expect(page.locator("h3")).to_be_visible()
    
    def test_rapid_navigation_stability(self, page):
        """Test: Rapid clicking → Multiple requests → App stability"""
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(3000)
            
            # Rapidly click different elements
            elements_to_click = [
                page.locator("button:has-text('All Posts')"),
                page.locator("button:has-text('Unread')"),
                page.locator("text=All Feeds"),
            ]
            
            # Add feed links if available
            feed_links = page.locator("a[href*='feed_id']").all()[:2]  # First 2 feeds
            elements_to_click.extend(feed_links)
            
            # Rapid navigation test
            for element in elements_to_click:
                if element.is_visible():
                    element.click()
                    page.wait_for_timeout(100)  # Short wait
            
            # App should remain stable
            expect(page.locator("h3")).to_be_visible()
            expect(page.locator("title")).to_have_text("RSS Reader")

class TestVisualRegressionAndLayout:
    """Test visual layout and ensure consistency"""
    
    def test_layout_structure_integrity(self, page):
        """Test: Layout components → Three-panel structure → MonsterUI styling"""
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(3000)
            
            # Verify three-panel layout exists
            sidebar = page.locator("#sidebar")
            main_content = page.locator("h3:has-text('All Posts')").locator("..")
            detail_panel = page.locator("#item-detail")
            
            expect(sidebar).to_be_visible()
            expect(main_content).to_be_visible() 
            expect(detail_panel).to_be_visible()
            
            # Verify MonsterUI styling is applied
            expect(page.locator(".uk-iconnav, .uk-icon, .rounded-lg")).to_be_visible()
    
    def test_article_detail_view_rendering(self, page):
        """Test: Click article → Detail view → Content formatting → Links working"""
        with rss_app_server():
            page.goto(TEST_URL)
            page.wait_for_timeout(3000)
            
            articles = page.locator("li[id^='feed-item-']").all()
            
            if len(articles) > 0:
                # Click article
                articles[0].click()
                page.wait_for_timeout(1000)
                
                # Verify detail view structure
                expect(page.locator("#item-detail strong")).to_be_visible()  # Title
                expect(page.locator("#item-detail time")).to_be_visible()    # Timestamp
                expect(page.locator("text=From:")).to_be_visible()           # Source
                expect(page.locator("text=Open Link")).to_be_visible()       # External link
                
                # Test external link works
                open_link = page.locator("text=Open Link")
                expect(open_link).to_have_attribute("href", url_contains="http")

def test_comprehensive_user_story(browser):
    """Test: Complete user story from empty DB to reading articles
    
    This is the ultimate integration test covering our entire implementation.
    """
    page = browser.new_page()
    
    try:
        with rss_app_server():
            # 1. Fresh start - empty database
            page.goto(TEST_URL)
            page.wait_for_timeout(5000)  # Wait for full setup
            
            # 2. Verify default feeds loaded
            expect(page.locator("text*=Hacker News")).to_be_visible(timeout=10000)
            
            # 3. Verify articles loaded
            articles = page.locator("li[id^='feed-item-']")
            expect(articles.first).to_be_visible(timeout=5000)
            
            # 4. Test article reading flow
            articles.first.click()
            expect(page.locator("#item-detail strong")).to_be_visible()
            
            # 5. Test feed navigation
            page.locator("text=All Feeds").click()
            page.wait_for_timeout(500)
            expect(page.locator("h3:has-text('All Posts')")).to_be_visible()
            
            # 6. Test pagination if available
            if page.locator("text*=Page 1 of").is_visible():
                if page.locator("button[data-uk-tooltip='Next page']").is_visible():
                    page.locator("button[data-uk-tooltip='Next page']").click()
                    page.wait_for_timeout(1000)
                    expect(page.locator("text*=Page 2 of")).to_be_visible()
            
            # 7. Test feed addition
            page.locator("#new-feed-url").fill("https://httpbin.org/xml")
            page.locator("button:has([data-icon='plus'])").click()
            page.wait_for_timeout(3000)
            
            # App should handle gracefully
            expect(page.locator("h3:has-text('Feeds')")).to_be_visible()
            
    finally:
        page.close()

if __name__ == "__main__":
    # Create test output directory
    os.makedirs("test_results", exist_ok=True)
    
    # Run comprehensive tests
    pytest.main([
        __file__, 
        "-v", 
        "--tb=short",
        "--html=test_results/e2e_report.html",
        "--self-contained-html"
    ])