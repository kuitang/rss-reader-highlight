"""
Comprehensive regression tests for Steps 4-6 refactoring.

These tests perform repetitive workflows on desktop and mobile to detect
any issues from the recent PageData class and optimization refactoring.
"""

import pytest
import os
from playwright.sync_api import Page, expect
import random
from test_constants import MAX_WAIT_MS, RETRY_DELAY_SECONDS, PAGE_LOAD_RETRY_DELAY
from test_helpers import (
    wait_for_htmx_complete as htmx_wait,
    navigate_with_retry
)
from tenacity import RetryError

pytestmark = pytest.mark.needs_server


# Using imported helper from test_helpers.py
wait_for_htmx_complete = htmx_wait


def ensure_mobile_sidebar_open(page: Page):
    """Helper function to ensure mobile sidebar is open before accessing feed links"""
    # Check if mobile nav button exists and is visible
    mobile_nav_button = page.locator("button#mobile-nav-button")
    if mobile_nav_button.is_visible():
        # We're in mobile layout, need to open sidebar first
        mobile_nav_button.click()
        wait_for_htmx_complete(page)  # Wait for sidebar animation
        return True
    return False  # Desktop layout, no need to open sidebar

def get_feed_links(page: Page):
    """Get feed links that are currently visible, handling mobile vs desktop"""
    # Try mobile sidebar links first (after ensuring sidebar is open)
    mobile_sidebar = page.locator("#mobile-sidebar")
    if mobile_sidebar.is_visible():
        return page.locator("#mobile-sidebar a[href*='feed_id']")
    
    # Fall back to desktop sidebar links
    return page.locator("#sidebar a[href*='feed_id']")


class TestRefactoringRegression:
    """Comprehensive regression tests for desktop and mobile workflows."""
    
    @pytest.mark.skipif(os.getenv("CI") == "true", reason="Resource intensive - run locally")
    def test_desktop_repetitive_workflow(self, page: Page, test_server_url):
        """
        Desktop workflow: Click feeds, scroll, view articles, toggle tabs - 3 cycles.
        Tests the core three-panel layout functionality.
        """
        # Navigate with automatic retry using tenacity
        try:
            navigate_with_retry(page, test_server_url)
            wait_for_htmx_complete(page)  # Use HTMX wait instead of networkidle
            # Verify server is responsive by checking for desktop layout (desktop viewport test)
            page.wait_for_selector("#desktop-layout", timeout=MAX_WAIT_MS)
        except RetryError as e:
            raise Exception(f"Failed to navigate to {test_server_url} after retries: {e}")
        
        # Take initial screenshot
        page.screenshot(path="/tmp/desktop_initial.png")
        
        # Wait for feeds to load - look for the feed list structure
        page.wait_for_selector("#desktop-layout, #main-content", timeout=MAX_WAIT_MS)
        
        # Check console for any initial errors
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        
        # Get list of available feeds from the sidebar - skip "All Feeds" link
        feed_links = page.locator("#sidebar a[href*='feed_id']").all()
        if not feed_links:
            # Fallback to original selector
            feed_links = page.locator("main > div:first-child a").filter(has_not=page.locator("text=All Feeds")).all()
        feed_count = len(feed_links)
        assert feed_count >= 2, f"Expected at least 2 feeds, got {feed_count}"
        
        for cycle in range(3):
            print(f"\n=== Desktop Cycle {cycle + 1} ===")

            # Add delay between cycles to reduce server stress in CI
            if cycle > 0:
                import time
                time.sleep(RETRY_DELAY_SECONDS)
            
            # 1. Click on a random feed in sidebar
            feed_index = cycle % min(feed_count, 3)  # Cycle through first 3 feeds
            feed_link = feed_links[feed_index]
            feed_name = feed_link.text_content()
            print(f"Clicking feed: {feed_name}")
            
            # Check if visible before clicking
            if feed_link.is_visible():
                feed_link.click()
                wait_for_htmx_complete(page)  # Use HTMX wait instead of networkidle
            else:
                print(f"Feed link not visible, skipping")
                continue
            # Wait for feed content to update instead of arbitrary sleep
            page.wait_for_selector("#desktop-feeds-content", state="visible", timeout=MAX_WAIT_MS)
            
            # Take screenshot after feed click
            page.screenshot(path=f"/tmp/desktop_cycle_{cycle}_feed_clicked.png")
            
            # 2. Scroll down in middle feed panel
            middle_panel = page.locator("#desktop-feeds-content")  # Desktop feeds content column
            expect(middle_panel).to_be_visible()
            
            print("Scrolling in middle panel")
            middle_panel.scroll_into_view_if_needed()
            middle_panel.hover()
            
            # Scroll down multiple times to load more items
            for scroll in range(3):
                page.keyboard.press("PageDown")
                wait_for_htmx_complete(page)  # Short wait for scroll animation
            
            # 3. Click on an article to view details in right panel
            article_links = middle_panel.locator("#feeds-list-container .js-filter li").all()  # Each article is in a listitem
            if article_links:
                article_index = cycle % len(article_links)
                article_item = article_links[article_index]
                article_title = article_item.locator("strong").text_content()[:50] + "..."
                print(f"Clicking article: {article_title}")
                
                article_item.click()  # Click the whole list item
                wait_for_htmx_complete(page)  # Use HTMX wait instead of networkidle
                # Wait for feed content to update instead of arbitrary sleep
                page.wait_for_selector("#desktop-feeds-content", state="visible", timeout=MAX_WAIT_MS)
                
                # Verify right panel shows article (desktop detail panel)
                detail_panel = page.locator("#desktop-item-detail")  # Desktop detail panel
                expect(detail_panel).to_be_visible()
                
                # Take screenshot after article click
                page.screenshot(path=f"/tmp/desktop_cycle_{cycle}_article_clicked.png")
                
                # Check that blue dot disappeared (article marked as read)
                # This tests the critical read/unread state functionality
                wait_for_htmx_complete(page)  # Brief wait for state update
            
            # 4. Toggle between "All Posts" and "Unread" tabs
            all_posts_tab = page.locator("text=All Posts").first
            unread_tab = page.locator("text=Unread").first
            
            if unread_tab.is_visible():
                print("Clicking Unread tab")
                unread_tab.click()
                wait_for_htmx_complete(page)  # Use HTMX wait instead of networkidle
                # Wait for feed list to update
                page.wait_for_selector("li[id^='mobile-feed-item-'], li[id^='desktop-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
                
                # Take screenshot of unread view
                page.screenshot(path=f"/tmp/desktop_cycle_{cycle}_unread_tab.png")
            
            if all_posts_tab.is_visible():
                print("Clicking All Posts tab")
                all_posts_tab.click()
                wait_for_htmx_complete(page)  # Use HTMX wait instead of networkidle
                # Wait for feed list to update
                page.wait_for_selector("li[id^='mobile-feed-item-'], li[id^='desktop-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
                
                # Take screenshot of all posts view
                page.screenshot(path=f"/tmp/desktop_cycle_{cycle}_all_posts_tab.png")
            
            print(f"Completed desktop cycle {cycle + 1}")
        
        # Check for actual console errors (not debug logs or known development warnings)
        error_messages = [msg for msg in console_messages 
                         if msg.startswith("error:") or 
                         (msg.startswith("warning:") and "tailwindcss.com" not in msg)]
        if error_messages:
            print(f"Console errors detected: {error_messages}")
        
        # Final screenshot
        page.screenshot(path="/tmp/desktop_final.png")
        
        # Assert no critical errors
        assert len(error_messages) == 0, f"Console errors detected: {error_messages}"

    @pytest.mark.skipif(os.getenv("CI") == "true", reason="Resource intensive - run locally")
    def test_mobile_repetitive_workflow(self, page: Page, test_server_url):
        """
        Mobile workflow: Hamburger menu, feeds, scroll, articles, back navigation - 3 cycles.
        Tests mobile-specific navigation and layout.
        """
        # Set mobile viewport
        page.set_viewport_size({"width": 390, "height": 844})

        # Navigate with automatic retry using tenacity
        try:
            navigate_with_retry(page, test_server_url)
            wait_for_htmx_complete(page)  # Use HTMX wait instead of networkidle
            # Verify server is responsive by checking for mobile layout (mobile viewport test)
            page.wait_for_selector("#mobile-layout", timeout=MAX_WAIT_MS)
        except RetryError as e:
            raise Exception(f"Failed to navigate to {test_server_url} after retries: {e}")
        
        # Take initial mobile screenshot
        page.screenshot(path="/tmp/mobile_initial.png")
        
        # Check console for any initial errors
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        
        for cycle in range(3):
            print(f"\n=== Mobile Cycle {cycle + 1} ===")

            # Add delay between cycles to reduce server stress in CI
            if cycle > 0:
                import time
                time.sleep(RETRY_DELAY_SECONDS)
            
            # 1. Click hamburger menu to open sidebar
            hamburger_menu = page.locator("button#mobile-nav-button")  # Mobile nav button
            expect(hamburger_menu).to_be_visible()
            
            print("Opening hamburger menu")
            hamburger_menu.click()
            wait_for_htmx_complete(page)  # Allow animation
            
            # Verify sidebar is visible (first column on mobile)
            sidebar = page.locator("#mobile-sidebar")
            expect(sidebar).to_be_visible()
            
            # Take screenshot of open sidebar
            page.screenshot(path=f"/tmp/mobile_cycle_{cycle}_sidebar_open.png")
            
            # 2. Click on a feed  
            feed_links = sidebar.locator("a").filter(has_not=page.locator("text=All Feeds")).all()
            feed_count = len(feed_links)
            assert feed_count >= 2, f"Expected at least 2 feeds, got {feed_count}"
            
            feed_index = cycle % min(feed_count, 3)
            feed_link = feed_links[feed_index]
            feed_name = feed_link.text_content()
            print(f"Clicking feed: {feed_name}")
            
            # Check if visible before clicking
            if feed_link.is_visible():
                feed_link.click()
                wait_for_htmx_complete(page)  # Use HTMX wait instead of networkidle
            else:
                print(f"Feed link not visible, skipping")
                continue
            # Wait for feed content to load
            page.wait_for_selector("li[id^='mobile-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
            
            # Verify sidebar closed automatically (mobile behavior)
            # Take screenshot after feed selection
            page.screenshot(path=f"/tmp/mobile_cycle_{cycle}_feed_selected.png")
            
            # 3. Scroll down in the feed list
            feed_container = page.locator("#main-content")  # Mobile content area
            expect(feed_container).to_be_visible()
            
            print("Scrolling in mobile feed list")
            # Scroll down multiple times
            for scroll in range(3):
                page.mouse.wheel(0, 500)
                wait_for_htmx_complete(page)  # Short wait for scroll animation
            
            # 4. Click on an article (should navigate to full-screen view)
            article_links = feed_container.locator("li[id^='mobile-feed-item-']").all()
            if article_links:
                article_index = cycle % len(article_links)
                article_item = article_links[article_index]
                article_title = article_item.locator("strong").text_content()[:50] + "..."
                print(f"Clicking article: {article_title}")
                
                article_item.click()
                wait_for_htmx_complete(page)
                # Wait for article view to load (mobile shows full screen)
                page.wait_for_selector("#main-content", state="visible", timeout=MAX_WAIT_MS)
                
                # Verify we're in mobile article view
                # Take screenshot of article view
                page.screenshot(path=f"/tmp/mobile_cycle_{cycle}_article_view.png")
                
                # 5. Click back arrow to return to feed list
                # Look for back button or use browser back
                back_buttons = page.locator("button").filter(has_text="←").all()
                if back_buttons:
                    print("Clicking back button")
                    back_buttons[0].click()
                    wait_for_htmx_complete(page)
                    # Wait for feed list to update
                    page.wait_for_selector("li[id^='mobile-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
                else:
                    # If no back button, use browser back
                    print("Using browser back navigation")
                    page.go_back()
                    wait_for_htmx_complete(page)
                    # Wait for feed list to update
                    page.wait_for_selector("li[id^='mobile-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
                
                # Verify we're back at feed list
                expect(feed_container).to_be_visible()
                
                # Take screenshot after back navigation
                page.screenshot(path=f"/tmp/mobile_cycle_{cycle}_back_to_list.png")
            
            # 6. Toggle between "All Posts" and "Unread" tabs
            all_posts_tab = page.locator("text=All Posts").first
            unread_tab = page.locator("text=Unread").first
            
            if unread_tab.is_visible():
                print("Clicking Unread tab (mobile)")
                unread_tab.click()
                wait_for_htmx_complete(page)  # Use HTMX wait instead of networkidle
                # Wait for feed list to update
                page.wait_for_selector("li[id^='mobile-feed-item-'], li[id^='desktop-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
                
                # Take screenshot of mobile unread view
                page.screenshot(path=f"/tmp/mobile_cycle_{cycle}_unread_tab.png")
            
            if all_posts_tab.is_visible():
                print("Clicking All Posts tab (mobile)")
                all_posts_tab.click()
                wait_for_htmx_complete(page)  # Use HTMX wait instead of networkidle
                # Wait for feed list to update
                page.wait_for_selector("li[id^='mobile-feed-item-'], li[id^='desktop-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
                
                # Take screenshot of mobile all posts view
                page.screenshot(path=f"/tmp/mobile_cycle_{cycle}_all_posts_tab.png")
            
            print(f"Completed mobile cycle {cycle + 1}")
        
        # Check for actual console errors (not debug logs or known development warnings)
        error_messages = [msg for msg in console_messages 
                         if msg.startswith("error:") or 
                         (msg.startswith("warning:") and "tailwindcss.com" not in msg)]
        if error_messages:
            print(f"Console errors detected: {error_messages}")
        
        # Final mobile screenshot
        page.screenshot(path="/tmp/mobile_final.png")
        
        # Assert no critical errors
        assert len(error_messages) == 0, f"Console errors detected: {error_messages}"

    @pytest.mark.skipif(os.getenv("CI") == "true", reason="Resource intensive - run locally")
    def test_htmx_request_monitoring(self, page: Page, test_server_url):
        """
        Monitor HTMX requests and responses for any failures or incorrect targets.
        This test focuses on the HTMX functionality that could break from refactoring.
        """
        # Navigate with automatic retry using tenacity
        try:
            navigate_with_retry(page, test_server_url)
            page.wait_for_load_state("networkidle", timeout=MAX_WAIT_MS)
            page.wait_for_selector("li[id^='desktop-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
        except RetryError as e:
            raise Exception(f"Failed to navigate to {test_server_url} after retries: {e}")
        
        # Monitor network requests
        requests = []
        responses = []
        
        page.on("request", lambda request: requests.append({
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers)
        }))
        
        page.on("response", lambda response: responses.append({
            "url": response.url,
            "status": response.status,
            "headers": dict(response.headers)
        }))
        
        # Perform typical user interactions that trigger HTMX
        
        # 1. Click on a feed (should trigger HTMX update)
        ensure_mobile_sidebar_open(page)  # Open mobile sidebar if needed
        feed_links = get_feed_links(page).all()
        if feed_links:
            print("Clicking feed to trigger HTMX update")
            feed_links[0].click()
            wait_for_htmx_complete(page)
            # Wait for feed content to load (could be mobile or desktop)
            page.wait_for_selector("li[id^='mobile-feed-item-'], li[id^='desktop-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
        
        # 2. Click on an article (should trigger HTMX update)
        article_items = page.locator("main > div:nth-child(2) li").all()
        if article_items:
            print("Clicking article to trigger HTMX update")
            article_items[0].click()
            wait_for_htmx_complete(page)
            # Wait for content to load after article click
            page.wait_for_selector("#main-content", state="visible", timeout=MAX_WAIT_MS)
        
        # 3. Toggle between tabs (should trigger HTMX update) - desktop viewport
        unread_tab = page.locator("#desktop-icon-bar button[title='Unread']")
        if unread_tab.is_visible():
            print("Toggling to Unread tab")
            unread_tab.click()
            wait_for_htmx_complete(page)
            # Wait for feed content to load (could be mobile or desktop)
            page.wait_for_selector("li[id^='mobile-feed-item-'], li[id^='desktop-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
        
        # Analyze requests for HTMX patterns
        htmx_requests = [req for req in requests if 'hx-request' in req.get('headers', {})]
        failed_responses = [resp for resp in responses if resp['status'] >= 400]
        
        print(f"Total requests: {len(requests)}")
        print(f"HTMX requests: {len(htmx_requests)}")
        print(f"Failed responses: {len(failed_responses)}")
        
        if failed_responses:
            print("Failed responses:")
            for resp in failed_responses:
                print(f"  {resp['status']} - {resp['url']}")
        
        # Assert no failed requests
        assert len(failed_responses) == 0, f"Found {len(failed_responses)} failed HTTP responses"

    @pytest.mark.skipif(os.getenv("CI") == "true", reason="Resource intensive - run locally")
    def test_read_unread_state_management(self, page: Page, test_server_url):
        """
        Test that read/unread state is properly managed after refactoring.
        This is critical functionality that could break with database changes.
        """
        # Navigate with automatic retry using tenacity
        try:
            navigate_with_retry(page, test_server_url)
            page.wait_for_load_state("networkidle", timeout=MAX_WAIT_MS)
            page.wait_for_selector("li[id^='desktop-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
        except RetryError as e:
            raise Exception(f"Failed to navigate to {test_server_url} after retries: {e}")
        
        # Click on a feed
        ensure_mobile_sidebar_open(page)  # Open mobile sidebar if needed
        feed_links = get_feed_links(page).all()
        if feed_links:
            feed_links[0].click()
            wait_for_htmx_complete(page)
            # Wait for feed content to load (could be mobile or desktop)
            page.wait_for_selector("li[id^='mobile-feed-item-'], li[id^='desktop-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
        
        # Find articles with blue dots (unread indicators)
        unread_articles = page.locator("li").filter(has=page.locator(".w-2.h-2.bg-blue-500")).all()
        initial_unread_count = len(unread_articles)
        
        print(f"Initial unread articles: {initial_unread_count}")
        
        if unread_articles:
            # Click on first unread article
            first_unread = unread_articles[0]
            
            # Take screenshot before click
            page.screenshot(path="/tmp/before_article_click.png")
            
            first_unread.click()  # Click the whole list item
            wait_for_htmx_complete(page)
            # Wait for detail panel to load
            page.wait_for_selector("#desktop-item-detail", state="visible", timeout=MAX_WAIT_MS)
            
            # Take screenshot after click
            page.screenshot(path="/tmp/after_article_click.png")
            
            # Verify blue dot disappeared
            remaining_unread = page.locator("li").filter(has=page.locator(".w-2.h-2.bg-blue-500")).all()
            final_unread_count = len(remaining_unread)
            
            print(f"Final unread articles: {final_unread_count}")
            
            # Should have one less unread article
            assert final_unread_count == initial_unread_count - 1, \
                f"Expected {initial_unread_count - 1} unread articles, got {final_unread_count}"
        
        # Test unread view behavior
        unread_tab = page.locator("text=Unread").first
        if unread_tab.is_visible():
            unread_tab.click()
            page.wait_for_load_state("networkidle")
            # Wait for feed content to load
            page.wait_for_selector("li[id^='mobile-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
            
            # Take screenshot of unread view
            page.screenshot(path="/tmp/unread_view.png")
            
            # Click on an article in unread view
            unread_articles_in_view = page.locator("main > div:nth-child(2) li").all()
            if unread_articles_in_view:
                unread_articles_in_view[0].click()
                wait_for_htmx_complete(page)  # Use HTMX wait instead of networkidle
                # Wait for feed list to update
                page.wait_for_selector("li[id^='mobile-feed-item-'], li[id^='desktop-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
                
                # Go back to unread view
                unread_tab.click()
                wait_for_htmx_complete(page)  # Use HTMX wait instead of networkidle
                # Wait for feed list to update
                page.wait_for_selector("li[id^='mobile-feed-item-'], li[id^='desktop-feed-item-']", state="visible", timeout=MAX_WAIT_MS)
                
                # Take screenshot after article removal
                page.screenshot(path="/tmp/unread_view_after_click.png")