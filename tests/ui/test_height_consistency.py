"""Test height consistency between unread and read feed items

This test specifically checks that feed items maintain the same height
when transitioning from unread (strong + blue dot) to read (span + no dot).
"""

import pytest
from playwright.sync_api import sync_playwright, expect
import test_constants as constants
from test_helpers import wait_for_htmx_complete, wait_for_page_ready

pytestmark = pytest.mark.needs_server

class TestFeedItemHeightConsistency:
    """Test that feed items maintain consistent height when clicked"""

    def test_height_consistency_unread_to_read_transition(self, page, test_server_url):
        """Test: Feed item height stays same when transitioning from unread to read

        This test catches the bug where:
        - Unread: <strong> + blue dot = height X
        - Read: <span> + no dot = height Y
        - Bug: X != Y (height changes, causing layout shift)
        - Fix: Font weight normalization + invisible dot space reservation
        """

        # Focus on desktop for height consistency testing since mobile navigates away from list
        for viewport_name, viewport_size in [
            ("desktop", constants.DESKTOP_VIEWPORT_ALT)
        ]:
            print(f"\n🔍 Testing {viewport_name} height consistency")
            page.set_viewport_size(viewport_size)
            page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
            wait_for_page_ready(page)

            # Wait for articles to load
            page.wait_for_selector("li[id^='feed-item-']", timeout=constants.MAX_WAIT_MS)

            # Find multiple unread items to test surgical updates on different items
            unread_items = page.locator("li[data-unread='true']")
            unread_count = unread_items.count()
            assert unread_count >= 3, f"Should have at least 3 unread items in {viewport_name}, got {unread_count}"

            # Test on 2nd and 3rd items to verify surgical updates work beyond first item
            test_item_index = 1 if viewport_name == "desktop" else 2  # 2nd item for desktop, 3rd for mobile
            test_item = unread_items.nth(test_item_index)
            item_id = test_item.get_attribute("id")
            print(f"  🎯 Testing surgical update on item #{test_item_index + 1}: {item_id}")

            # MEASURE BEFORE: Height when unread (strong + blue dot)
            before_metrics = page.evaluate(f"""
                () => {{
                    const item = document.getElementById('{item_id}');
                    if (!item) return null;

                    const rect = item.getBoundingClientRect();
                    const titleElement = item.querySelector('div:first-child strong, div:first-child span');
                    const titleRect = titleElement ? titleElement.getBoundingClientRect() : null;
                    const blueDotElement = item.querySelector('.blue-dot');
                    const hasBlueRot = blueDotElement && getComputedStyle(blueDotElement).opacity !== '0';

                    return {{
                        totalHeight: rect.height,
                        titleHeight: titleRect ? titleRect.height : 0,
                        titleTagName: titleElement ? titleElement.tagName : 'none',
                        hasBlueRot,
                        dataUnread: item.getAttribute('data-unread')
                    }};
                }}
            """)

            assert before_metrics, f"Could not measure {item_id} before click"
            print(f"  📏 BEFORE: {before_metrics['titleTagName']} height={before_metrics['titleHeight']}, total={before_metrics['totalHeight']}, blue_dot={before_metrics['hasBlueRot']}")

            # CLICK the item (triggers unread → read transition)
            test_item.click()
            wait_for_htmx_complete(page, timeout=constants.MAX_WAIT_MS)

            # Wait for HTMX out-of-band update to complete
            # The item should be updated with new styling
            page.wait_for_function(f"""
                () => {{
                    const item = document.getElementById('{item_id}');
                    return item && item.getAttribute('data-unread') === 'false';
                }}
            """, timeout=constants.MAX_WAIT_MS)

            # MEASURE AFTER: Height when read (span + no blue dot)
            after_metrics = page.evaluate(f"""
                () => {{
                    const item = document.getElementById('{item_id}');
                    if (!item) return null;

                    const rect = item.getBoundingClientRect();
                    const titleElement = item.querySelector('div:first-child strong, div:first-child span');
                    const titleRect = titleElement ? titleElement.getBoundingClientRect() : null;
                    const blueDotElement = item.querySelector('.blue-dot');
                    const hasBlueRot = blueDotElement && getComputedStyle(blueDotElement).opacity !== '0';

                    return {{
                        totalHeight: rect.height,
                        titleHeight: titleRect ? titleRect.height : 0,
                        titleTagName: titleElement ? titleElement.tagName : 'none',
                        hasBlueRot,
                        dataUnread: item.getAttribute('data-unread')
                    }};
                }}
            """)

            assert after_metrics, f"Could not measure {item_id} after click"
            print(f"  📏 AFTER:  {after_metrics['titleTagName']} height={after_metrics['titleHeight']}, total={after_metrics['totalHeight']}, blue_dot={after_metrics['hasBlueRot']}")

            # ASSERT: Heights should be identical
            height_tolerance = 1.0  # Allow 1px tolerance for sub-pixel rendering

            title_height_diff = abs(before_metrics['titleHeight'] - after_metrics['titleHeight'])
            total_height_diff = abs(before_metrics['totalHeight'] - after_metrics['totalHeight'])

            assert title_height_diff <= height_tolerance, (
                f"{viewport_name} title height changed by {title_height_diff}px: "
                f"{before_metrics['titleHeight']} → {after_metrics['titleHeight']} "
                f"(before: {before_metrics['titleTagName']}, after: {after_metrics['titleTagName']})"
            )

            assert total_height_diff <= height_tolerance, (
                f"{viewport_name} total height changed by {total_height_diff}px: "
                f"{before_metrics['totalHeight']} → {after_metrics['totalHeight']}"
            )

            # ASSERT: State transition happened correctly
            assert before_metrics['dataUnread'] == 'true', "Item should start as unread"
            assert after_metrics['dataUnread'] == 'false', "Item should be read after click"
            assert before_metrics['hasBlueRot'] == True, "Should have blue dot before"
            assert after_metrics['hasBlueRot'] == False, "Should not have blue dot after"

            print(f"  ✅ {viewport_name} height consistency verified")

            # Navigate back to reset for next viewport
            if viewport_name != "mobile":  # Don't navigate back on last iteration
                page.goto(test_server_url, timeout=constants.MAX_WAIT_MS)
                wait_for_page_ready(page)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])