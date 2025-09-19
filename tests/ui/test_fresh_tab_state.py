"""Test that full state is preserved in URLs for fresh tab navigation"""

import pytest
from playwright.sync_api import Page, expect, Browser
import test_constants as constants
from test_helpers import (
    wait_for_htmx_complete,
    wait_for_page_ready,
)


class TestFreshTabStatePreservation:
    """Test that URLs preserve complete state for copying and fresh tab access"""

    def test_mobile_fresh_tab_with_full_state(self, browser: Browser, test_server_url):
        """Test: Mobile URL with feed_id, page, scroll, unread state works in fresh tab"""

        # Create first context and page for initial navigation
        context1 = browser.new_context(viewport=constants.MOBILE_VIEWPORT)
        page1 = context1.new_page()

        # Navigate to All Posts view
        page1.goto(f"{test_server_url}/?unread=0", wait_until="networkidle", timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page1)

        # Check if we have items and can scroll
        has_items = page1.evaluate("""() => {
            const summary = document.getElementById('summary');
            const feedItems = document.querySelectorAll("li[data-testid='feed-item']");
            if (summary && feedItems.length > 0) {
                // Set a scroll position
                summary.scrollTop = 200;
                return {
                    hasItems: true,
                    scrollSet: summary.scrollTop,
                    itemCount: feedItems.length
                };
            }
            return {hasItems: false, scrollSet: 0, itemCount: 0};
        }""")

        if not has_items['hasItems']:
            # Skip test if no items available in minimal mode
            context1.close()
            pytest.skip("No feed items available in test environment")

        # Navigate to an item (this should capture scroll position)
        first_item = page1.locator("li[data-testid='feed-item']").first
        first_item.click()
        wait_for_htmx_complete(page1)

        # Wait for item URL
        page1.wait_for_url("**/item/**", timeout=constants.MAX_WAIT_MS)

        # Go back using browser back button (simpler than finding the UI back button)
        page1.go_back()
        wait_for_htmx_complete(page1)

        # Get the current URL (should have all state params except _scroll which is cleaned up)
        current_url = page1.url

        # Verify we have the expected parameters in URL
        assert "unread=0" in current_url, "URL should preserve unread state"

        # Test fresh tab with scroll parameter
        # Create a completely new context (simulating fresh tab)
        context2 = browser.new_context(viewport=constants.MOBILE_VIEWPORT)
        page2 = context2.new_page()

        # Manually construct a URL with all state params including scroll
        state_url = f"{test_server_url}/?unread=0&page=1&_scroll=150"

        # Navigate to the URL with full state
        page2.goto(state_url, wait_until="networkidle", timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page2)

        # Wait a bit more for scroll restoration to complete
        page2.wait_for_timeout(500)

        # Check that state was restored
        restored_state = page2.evaluate("""() => {
            const summary = document.getElementById('summary');
            const urlParams = new URLSearchParams(window.location.search);
            const firstFeedItem = document.querySelector("li[data-testid='feed-item']");

            return {
                scrollTop: summary ? summary.scrollTop : 0,
                hasUnreadParam: urlParams.has('unread'),
                unreadValue: urlParams.get('unread'),
                hasScrollParam: urlParams.has('_scroll'),  // Should be cleaned up after applying
                hasItems: !!firstFeedItem,
                url: window.location.href
            };
        }""")

        # Verify state restoration
        assert restored_state['hasUnreadParam'], "URL should have unread parameter"
        assert restored_state['unreadValue'] == '0', "Unread should be set to 0 (All Posts)"
        assert not restored_state['hasScrollParam'], "_scroll param should be cleaned up after applying"
        assert restored_state['hasItems'], "Feed items should be visible"

        # Verify scroll restoration worked (should be close to 150px that we passed)
        assert restored_state['scrollTop'] > 100, f"Scroll should be restored close to 150px (got {restored_state['scrollTop']}px)"
        print(f"✅ Scroll restoration worked: {restored_state['scrollTop']}px")

        # Clean up contexts
        context1.close()
        context2.close()

    def test_desktop_fresh_tab_with_full_state(self, browser: Browser, test_server_url):
        """Test: Desktop URL with feed_id, page, unread state works in fresh tab"""

        # Create first context and page for initial navigation
        context1 = browser.new_context(viewport=constants.DESKTOP_VIEWPORT)
        page1 = context1.new_page()

        # Navigate to unread view
        page1.goto(f"{test_server_url}/?unread=1", wait_until="networkidle", timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page1)

        # Get current URL
        current_url = page1.url
        assert "unread=1" in current_url, "URL should have unread=1"

        # Navigate to page 2 if available (or just verify page 1)
        # For this test, we'll just verify the current state can be restored

        # Create a completely new context (simulating fresh tab)
        context2 = browser.new_context(viewport=constants.DESKTOP_VIEWPORT)
        page2 = context2.new_page()

        # Navigate to URL with full state
        state_url = f"{test_server_url}/?unread=1&feed_id=2&page=1"
        page2.goto(state_url, wait_until="networkidle", timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page2)

        # Check that state was restored
        restored_state = page2.evaluate("""() => {
            const urlParams = new URLSearchParams(window.location.search);
            const feedsList = document.querySelector('#feeds-list-container');
            const iconBar = document.querySelector('#icon-bar');

            // Check if unread button is active
            const unreadBtn = iconBar ? iconBar.querySelector('button[title*="unread"], button[uk-tooltip*="unread"]') : null;
            const unreadBtnClasses = unreadBtn ? unreadBtn.className : '';

            return {
                hasUnreadParam: urlParams.has('unread'),
                unreadValue: urlParams.get('unread'),
                hasFeedParam: urlParams.has('feed_id'),
                feedValue: urlParams.get('feed_id'),
                hasPageParam: urlParams.has('page'),
                pageValue: urlParams.get('page'),
                hasFeedsList: !!feedsList,
                unreadButtonActive: unreadBtnClasses.includes('text-blue-600') || unreadBtnClasses.includes('active'),
                url: window.location.href
            };
        }""")

        # Verify state restoration
        assert restored_state['hasUnreadParam'], "URL should have unread parameter"
        assert restored_state['unreadValue'] == '1', "Unread should be set to 1"
        assert restored_state['hasFeedParam'], "URL should have feed_id parameter"
        assert restored_state['feedValue'] == '2', "Feed ID should be 2"
        assert restored_state['hasFeedsList'], "Feeds list should be visible"

        # Clean up contexts
        context1.close()
        context2.close()

    def test_copy_url_preserves_all_state(self, page: Page, test_server_url):
        """Test: Copying URL from browser preserves all navigation state"""

        # Set mobile viewport
        page.set_viewport_size(constants.MOBILE_VIEWPORT)

        # Navigate to All Posts view (no specific feed_id to avoid issues)
        page.goto(f"{test_server_url}/?unread=0", wait_until="networkidle", timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page)

        # Check if we have items first
        has_items = page.evaluate("""() => {
            const summary = document.getElementById('summary');
            const feedItems = document.querySelectorAll("li[data-testid='feed-item']");
            if (summary && feedItems.length > 0) {
                // Set a scroll position
                summary.scrollTop = 300;
                return true;
            }
            return false;
        }""")

        if not has_items:
            pytest.skip("No feed items available in test environment")

        # Click first available item
        first_item = page.locator("li[data-testid='feed-item']").first
        first_item.click()
        wait_for_htmx_complete(page)

        # Get item URL
        page.wait_for_url("**/item/**", timeout=constants.MAX_WAIT_MS)
        item_url = page.url

        # Verify item URL has unread state parameter
        assert "unread" in item_url, "Item URL should have unread state"

        # Navigate back using browser back button
        page.go_back()
        wait_for_htmx_complete(page)

        # Wait a bit for scroll restoration and DOM updates
        page.wait_for_timeout(500)

        # Get the feed list URL and debug info
        feed_list_url = page.url

        # Get debug information about the current state
        debug_info = page.evaluate("""() => {
            const summary = document.getElementById('summary');
            const urlParams = new URLSearchParams(window.location.search);
            const currentUrl = window.location.pathname + window.location.search;

            // Check sessionStorage for scroll position
            const storedKeys = [];
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                if (key && key.startsWith('scrollPos_')) {
                    storedKeys.push({key: key, value: sessionStorage.getItem(key)});
                }
            }

            // Try multiple times to get scroll position (sometimes needs a moment to apply)
            let scrollPos = summary ? summary.scrollTop : 0;

            return {
                url: window.location.href,
                hasScrollParam: urlParams.has('_scroll'),
                scrollParam: urlParams.get('_scroll'),
                scrollTop: scrollPos,
                scrollHeight: summary ? summary.scrollHeight : 0,
                clientHeight: summary ? summary.clientHeight : 0,
                summaryExists: !!summary,
                sessionStorageKeys: storedKeys,
                currentUrlKey: 'scrollPos_' + currentUrl
            };
        }""")

        print(f"🔍 Debug after back: URL={debug_info['url']}")
        print(f"🔍 Scroll param: {debug_info['scrollParam']}, ScrollTop: {debug_info['scrollTop']}")
        print(f"🔍 Summary exists: {debug_info['summaryExists']}, Height: {debug_info['scrollHeight']}/{debug_info['clientHeight']}")

        # Verify URL has expected parameters
        assert "unread=0" in feed_list_url, "Feed list URL should have unread state"

        # If scroll isn't restored immediately, wait a bit more for JS to execute
        if debug_info['scrollTop'] == 0:
            page.wait_for_timeout(500)
            scroll_pos = page.evaluate("() => document.getElementById('summary')?.scrollTop || 0")
        else:
            scroll_pos = debug_info['scrollTop']

        # Verify scroll restoration worked
        # With the CSS fix, scroll should now be properly restored
        assert scroll_pos > 250, f"Scroll position should be approximately restored to 300px (got {scroll_pos})"
        print(f"✅ Scroll position restored: {scroll_pos}px")