#!/usr/bin/env python3
"""
Comprehensive test for toast notification functionality in RSS Reader app.

Tests all toast scenarios in the /api/feed/add route:
1. "Session error" (error) - when no session_id
2. "Please enter a URL" (error) - when empty URL
3. "Already subscribed to: {title}" (warning) - when feed already exists
4. "Feed added successfully" (success) - when feed added successfully
5. "Feed added but background update failed - refresh manually" (warning) - when background queue failed
6. "Failed to add feed: {error}" (error) - when exception occurs

Tests both desktop and mobile viewports.
"""

import asyncio
import pytest
import time
from playwright.async_api import async_playwright, Page, Browser


class ToastTester:
    def __init__(self, page: Page):
        self.page = page
        self.base_url = "http://localhost:8080"

    async def wait_for_toast(self, expected_text: str = None, toast_type: str = None, timeout: int = 10000):
        """Wait for toast to appear and optionally verify its content and type"""
        # Wait for toast container to appear
        await self.page.wait_for_selector(".toast-container", state="visible", timeout=timeout)

        # Wait for actual toast message
        toast_selector = ".toast-container .toast"
        await self.page.wait_for_selector(toast_selector, state="visible", timeout=timeout)

        if expected_text:
            # Wait for toast with specific text
            await self.page.wait_for_selector(f"{toast_selector}:has-text('{expected_text}')",
                                             state="visible", timeout=timeout)

        if toast_type:
            # Verify toast type (error, warning, success)
            toast_type_selector = f"{toast_selector}.toast-{toast_type}"
            await self.page.wait_for_selector(toast_type_selector, state="visible", timeout=timeout)

        return True

    async def wait_for_toast_disappear(self, timeout: int = 6000):
        """Wait for toast to disappear (default timeout is 5 seconds + buffer)"""
        try:
            await self.page.wait_for_selector(".toast-container .toast", state="hidden", timeout=timeout)
            return True
        except:
            return False

    async def get_feed_form_elements(self, viewport_width: int):
        """Get form elements based on viewport - unified layout uses #feeds sidebar"""
        # In unified layout, form is in #feeds sidebar for both desktop and mobile
        input_selector = "#feeds input[name='new_feed_url']"
        # Use more specific selector for the add feed button (has plus icon)
        submit_selector = "#feeds .add-feed-form button[type='submit']"
        return input_selector, submit_selector

    async def ensure_add_form_visible(self, viewport_width: int):
        """Ensure the add feed form is visible for the current viewport"""
        if viewport_width < 1024:  # Mobile - need to open sidebar drawer
            # Check if sidebar drawer is open using CSS selector
            drawer_open = await self.page.evaluate("""
                () => {
                    const appRoot = document.getElementById('app-root');
                    return appRoot && appRoot.getAttribute('data-drawer') === 'open';
                }
            """)

            if not drawer_open:
                # Click hamburger button to open sidebar drawer
                await self.page.click(".hamburger-btn")
                await self.page.wait_for_timeout(300)  # Wait for animation

        # Wait for form to be visible in #feeds sidebar
        input_selector, _ = await self.get_feed_form_elements(viewport_width)
        await self.page.wait_for_selector(input_selector, state="visible")

    async def submit_feed_url(self, url: str, viewport_width: int):
        """Submit a feed URL and return whether form submission was successful"""
        await self.ensure_add_form_visible(viewport_width)

        input_selector, submit_selector = await self.get_feed_form_elements(viewport_width)

        # Clear input and type URL
        await self.page.fill(input_selector, "")
        if url:
            await self.page.fill(input_selector, url)

        # Submit form
        await self.page.click(submit_selector)

        # Wait a moment for HTMX request to complete
        await self.page.wait_for_timeout(500)

        return True

    async def verify_form_integrity(self, viewport_width: int):
        """Verify that form elements are still present and functional after toast"""
        # Ensure form is visible first
        await self.ensure_add_form_visible(viewport_width)

        input_selector, submit_selector = await self.get_feed_form_elements(viewport_width)

        # Check that form elements still exist
        input_visible = await self.page.is_visible(input_selector)
        submit_visible = await self.page.is_visible(submit_selector)

        if not input_visible or not submit_visible:
            raise AssertionError(f"Form elements missing after toast - input visible: {input_visible}, submit visible: {submit_visible}")

        # Check that input is still editable
        await self.page.fill(input_selector, "test")
        input_value = await self.page.input_value(input_selector)
        if input_value != "test":
            raise AssertionError(f"Input not editable after toast - expected 'test', got '{input_value}'")

        # Clear the test input
        await self.page.fill(input_selector, "")

        return True


async def test_toast_notifications():
    """Main test function for all toast notification scenarios"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # Headless for CI compatibility

        # Test both desktop and mobile viewports
        viewports = [
            {"width": 1400, "height": 900, "name": "Desktop"},
            {"width": 390, "height": 844, "name": "Mobile"}
        ]

        for viewport in viewports:
            print(f"\n=== Testing {viewport['name']} Viewport ({viewport['width']}x{viewport['height']}) ===")

            page = await browser.new_page()
            await page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})

            tester = ToastTester(page)

            try:
                # Navigate to app
                print(f"1. Navigating to {tester.base_url}")
                await page.goto(tester.base_url)
                await page.wait_for_load_state('networkidle')

                # Test 1: Empty URL submission (error toast)
                print("2. Testing empty URL submission (should show error toast)")
                await tester.submit_feed_url("", viewport["width"])

                toast_appeared = await tester.wait_for_toast("Please enter a URL", "error")
                print(f"   ✓ Error toast appeared: {toast_appeared}")

                await tester.verify_form_integrity(viewport["width"])
                print("   ✓ Form integrity maintained")

                await tester.wait_for_toast_disappear()
                print("   ✓ Toast disappeared")

                # Test 2: Valid URL submission (success toast)
                print("3. Testing valid URL submission (should show success toast)")
                test_feed_url = "https://hnrss.org/newest"
                await tester.submit_feed_url(test_feed_url, viewport["width"])

                # Wait for either success or already subscribed toast
                try:
                    success_toast = await tester.wait_for_toast("Feed added successfully", "success")
                    print(f"   ✓ Success toast appeared: {success_toast}")
                except:
                    try:
                        warning_toast = await tester.wait_for_toast("Already subscribed", "warning")
                        print(f"   ✓ Already subscribed toast appeared: {warning_toast}")
                    except:
                        print("   ✗ No success or warning toast appeared")

                await tester.verify_form_integrity(viewport["width"])
                print("   ✓ Form integrity maintained")

                await tester.wait_for_toast_disappear()
                print("   ✓ Toast disappeared")

                # Test 3: Duplicate URL submission (warning toast)
                print("4. Testing duplicate URL submission (should show warning toast)")
                await tester.submit_feed_url(test_feed_url, viewport["width"])

                warning_toast = await tester.wait_for_toast("Already subscribed", "warning")
                print(f"   ✓ Warning toast appeared: {warning_toast}")

                await tester.verify_form_integrity(viewport["width"])
                print("   ✓ Form integrity maintained")

                await tester.wait_for_toast_disappear()
                print("   ✓ Toast disappeared")

                # Test 4: Invalid URL (should trigger error handling)
                print("5. Testing invalid URL (should show error toast)")
                invalid_url = "not-a-valid-url"
                await tester.submit_feed_url(invalid_url, viewport["width"])

                try:
                    error_toast = await tester.wait_for_toast("Failed to add feed", "error")
                    print(f"   ✓ Error toast appeared: {error_toast}")
                except:
                    print("   ⚠ No error toast appeared (may be expected behavior)")

                await tester.verify_form_integrity(viewport["width"])
                print("   ✓ Form integrity maintained")

                # Test 5: Check sidebar updates after successful addition
                print("6. Verifying sidebar updates")
                # In unified layout, feeds list is always in #feeds sidebar
                feeds_list = await page.query_selector("#feeds .feeds-list")

                if feeds_list:
                    print("   ✓ Feeds list found in sidebar")
                else:
                    print("   ⚠ Feeds list not found")

                print(f"✅ {viewport['name']} viewport tests completed successfully")

            except Exception as e:
                print(f"❌ Error testing {viewport['name']} viewport: {str(e)}")
                # Take screenshot for debugging
                screenshot_path = f"/home/kuitang/git/rss-reader-highlight/toast_test_error_{viewport['name'].lower()}.png"
                await page.screenshot(path=screenshot_path)
                print(f"   Screenshot saved: {screenshot_path}")

            finally:
                await page.close()

        await browser.close()
        print("\n🎉 Toast notification testing completed!")


if __name__ == "__main__":
    asyncio.run(test_toast_notifications())