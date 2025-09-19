"""Test surgical updates work for multiple items, not just the first one

This test verifies that the CSS-driven surgical updates work for any feed item,
not just the first one clicked.
"""

import pytest
from playwright.sync_api import sync_playwright, expect
import test_constants as constants
from test_helpers import wait_for_htmx_complete, wait_for_page_ready

pytestmark = pytest.mark.needs_server

class TestSurgicalUpdatesMultipleItems:
    """Test that surgical updates work for any item, not just first"""

    def test_surgical_updates_on_multiple_items(self, page, test_server_url):
        """Test: Click 2nd, 3rd, 4th items → Each gets surgical update correctly

        This test verifies that surgical updates (changing data-unread attribute
        and letting CSS handle styling) work for any item, not just the first one.

        Potential issues to catch:
        - Script target element reuse conflicts
        - Race conditions between multiple surgical updates
        - HTMX caching of script responses
        """

        # Desktop only (mobile navigates away from list)
        page.set_viewport_size(constants.DESKTOP_VIEWPORT_ALT)
        page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
        wait_for_page_ready(page)

        # Wait for articles to load
        page.wait_for_selector("li[id^='feed-item-']", timeout=constants.MAX_WAIT_MS)

        # Find unread items
        unread_items = page.locator("li[data-unread='true']")
        unread_count = unread_items.count()
        assert unread_count >= 5, f"Should have at least 5 unread items, got {unread_count}"

        print(f"🧪 Testing surgical updates on items 2, 3, 4 (indices 1, 2, 3)")

        # Test items 2, 3, 4 (indices 1, 2, 3) to verify surgical updates work beyond first
        test_indices = [1, 2, 3]

        for test_index in test_indices:
            print(f"\n  🎯 Testing item #{test_index + 1}")

            # Fresh locator since previous clicks might have changed state
            current_unread_items = page.locator("li[data-unread='true']")
            current_count = current_unread_items.count()

            if test_index >= current_count:
                print(f"    ⚠️ Skipping - only {current_count} unread items remaining")
                continue

            test_item = current_unread_items.nth(test_index)
            item_id = test_item.get_attribute("id")

            # BEFORE: Check initial state
            before_state = page.evaluate(f"""
                () => {{
                    const item = document.getElementById('{item_id}');
                    if (!item) return null;

                    const blueDotElement = item.querySelector('.blue-dot');
                    return {{
                        itemId: '{item_id}',
                        dataUnread: item.getAttribute('data-unread'),
                        blueDotOpacity: blueDotElement ? getComputedStyle(blueDotElement).opacity : null,
                        titleWeight: getComputedStyle(item.querySelector('.feed-title')).fontWeight
                    }};
                }}
            """)

            print(f"    📏 BEFORE: data-unread={before_state['dataUnread']}, blue_opacity={before_state['blueDotOpacity']}, title_weight={before_state['titleWeight']}")

            # CLICK the item
            test_item.click()
            wait_for_htmx_complete(page, timeout=constants.MAX_WAIT_MS)

            # Give surgical update time to execute
            page.wait_for_timeout(500)

            # AFTER: Check if surgical update worked
            after_state = page.evaluate(f"""
                () => {{
                    const item = document.getElementById('{item_id}');
                    if (!item) return null;

                    const blueDotElement = item.querySelector('.blue-dot');
                    return {{
                        itemId: '{item_id}',
                        dataUnread: item.getAttribute('data-unread'),
                        blueDotOpacity: blueDotElement ? getComputedStyle(blueDotElement).opacity : null,
                        titleWeight: getComputedStyle(item.querySelector('.feed-title')).fontWeight,
                        surgicalUpdateWorked: item.getAttribute('data-unread') === 'false'
                    }};
                }}
            """)

            print(f"    📏 AFTER:  data-unread={after_state['dataUnread']}, blue_opacity={after_state['blueDotOpacity']}, title_weight={after_state['titleWeight']}, surgical_worked={after_state['surgicalUpdateWorked']}")

            # ASSERT: Surgical update should have worked
            if after_state['surgicalUpdateWorked']:
                print(f"    ✅ Item #{test_index + 1} ({item_id}) - surgical update worked")

                # Verify CSS changes applied correctly
                assert after_state['blueDotOpacity'] == '0', f"Blue dot should be hidden (opacity 0), got {after_state['blueDotOpacity']}"
                assert after_state['titleWeight'] == '400', f"Title should be normal weight (400), got {after_state['titleWeight']}"
            else:
                print(f"    ❌ Item #{test_index + 1} ({item_id}) - surgical update FAILED")
                print(f"       data-unread remained: {after_state['dataUnread']}")

                # This is the bug we're trying to catch!
                assert False, f"Surgical update failed for item #{test_index + 1} ({item_id})"

            # Navigate back to list view for next test
            page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
            wait_for_page_ready(page)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])