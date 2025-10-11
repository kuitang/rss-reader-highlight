"""Debug mobile UI issues - Back button, sidebar grey screen, and click behavior

This script tests three critical mobile UI issues:
1. Back button navigation from article to feed list
2. Sidebar grey screen issue (whole screen vs background only)
3. Sidebar click behavior (links work, outside clicks close)

Run with: python debug_mobile_sidebar.py
Requires: Server running on http://localhost:8080
"""

import sys
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import time
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def log_step(message):
    """Log a test step"""
    print(f"{Colors.BLUE}▶{Colors.END} {message}")

def log_success(message):
    """Log a successful check"""
    print(f"  {Colors.GREEN}✓{Colors.END} {message}")

def log_failure(message):
    """Log a failed check"""
    print(f"  {Colors.RED}✗{Colors.END} {message}")

def log_warning(message):
    """Log a warning"""
    print(f"  {Colors.YELLOW}⚠{Colors.END} {message}")

def log_info(message):
    """Log information"""
    print(f"  {Colors.BLUE}ℹ{Colors.END} {message}")

def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete"""
    try:
        page.wait_for_function(
            "() => !document.body.classList.contains('htmx-request')",
            timeout=timeout
        )
    except PlaywrightTimeout:
        log_warning("HTMX completion timeout")

def wait_for_page_ready(page, timeout=5000):
    """Wait for page to be fully loaded"""
    page.wait_for_load_state('domcontentloaded', timeout=timeout)
    page.wait_for_load_state('networkidle', timeout=timeout)

def test_back_button_navigation(page, server_url):
    """Test 1: Back button navigation from article to feed list"""
    print(f"\n{Colors.BOLD}TEST 1: Back Button Navigation{Colors.END}")
    print("=" * 60)

    findings = {
        'passed': [],
        'failed': [],
        'warnings': []
    }

    try:
        # Navigate to homepage
        log_step("Navigating to homepage")
        page.goto(server_url)
        wait_for_page_ready(page)
        log_success(f"Loaded {server_url}")

        # Check for feed items
        log_step("Looking for feed items")
        feed_items = page.locator("li[id^='feed-item-']")
        count = feed_items.count()

        if count == 0:
            log_failure("No feed items found on page")
            findings['failed'].append("No feed items available to test")
            return findings

        log_success(f"Found {count} feed items")

        # Click on first article
        log_step("Clicking on first article")
        first_item = feed_items.first
        first_item.click()
        wait_for_htmx_complete(page)

        # Wait for article detail to be visible
        page.wait_for_selector("#article-detail", state="visible", timeout=5000)

        # Check if we're in article view
        article_visible = page.locator("#article-detail").is_visible()
        if article_visible:
            log_success("Article detail view is visible")
            findings['passed'].append("Article loads correctly")
        else:
            log_failure("Article detail view is not visible")
            findings['failed'].append("Article failed to load")
            return findings

        # Check URL changed
        current_url = page.url
        if "/item/" in current_url:
            log_success(f"URL updated to article view: {current_url}")
            findings['passed'].append("URL updates on article navigation")
        else:
            log_warning(f"URL did not change to article view: {current_url}")
            findings['warnings'].append("URL may not update correctly")

        # Check for back button
        log_step("Looking for back button")
        back_button = page.locator("#nav-button")

        if not back_button.is_visible():
            log_failure("Back button is not visible")
            findings['failed'].append("Back button missing in article view")
            return findings

        log_success("Back button is visible")

        # Check if button has back arrow (SVG)
        back_icon = back_button.locator("svg")
        if back_icon.count() > 0:
            log_success("Back button has arrow icon")
            findings['passed'].append("Back button properly styled")
        else:
            log_warning("Back button missing arrow icon")
            findings['warnings'].append("Back button may not be properly styled")

        # Take screenshot before clicking back
        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        page.screenshot(path=str(screenshots_dir / "1_article_view.png"))
        log_info(f"Screenshot saved: screenshots/1_article_view.png")

        # Click back button
        log_step("Clicking back button")
        back_button.click()
        wait_for_htmx_complete(page)

        # Wait for feed list to be visible
        time.sleep(0.5)  # Brief wait for animation

        # Check if feed list is visible
        feed_list_visible = page.locator("#feed-list").is_visible()

        if feed_list_visible:
            log_success("Feed list is visible after back navigation")
            findings['passed'].append("Back button returns to feed list")
        else:
            log_failure("Feed list is not visible after back navigation")
            findings['failed'].append("Back button does not return to feed list")

        # Check if article is hidden
        article_still_visible = page.locator("#article-detail").is_visible()
        if article_still_visible:
            log_warning("Article detail is still visible after back navigation")
            findings['warnings'].append("Article may not be properly hidden")
        else:
            log_success("Article detail is hidden after back navigation")
            findings['passed'].append("Article properly hidden on back")

        # Check URL changed back
        current_url = page.url
        if "/item/" not in current_url:
            log_success(f"URL returned to list view: {current_url}")
            findings['passed'].append("URL updates on back navigation")
        else:
            log_warning(f"URL still shows article: {current_url}")
            findings['warnings'].append("URL may not update on back navigation")

        # Take screenshot after back
        page.screenshot(path=str(screenshots_dir / "2_after_back.png"))
        log_info(f"Screenshot saved: screenshots/2_after_back.png")

    except Exception as e:
        log_failure(f"Exception during test: {str(e)}")
        findings['failed'].append(f"Test error: {str(e)}")

    return findings

def test_sidebar_grey_screen(page, server_url):
    """Test 2: Sidebar grey screen issue"""
    print(f"\n{Colors.BOLD}TEST 2: Sidebar Grey Screen Issue{Colors.END}")
    print("=" * 60)

    findings = {
        'passed': [],
        'failed': [],
        'warnings': []
    }

    try:
        # Navigate to homepage
        log_step("Navigating to homepage")
        page.goto(server_url)
        wait_for_page_ready(page)

        # Take screenshot of initial state
        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        page.screenshot(path=str(screenshots_dir / "3_before_sidebar.png"))
        log_info(f"Screenshot saved: screenshots/3_before_sidebar.png")

        # Open sidebar
        log_step("Opening sidebar (clicking hamburger menu)")
        nav_button = page.locator("#nav-button")

        if not nav_button.is_visible():
            log_failure("Navigation button not found")
            findings['failed'].append("Cannot find hamburger menu button")
            return findings

        nav_button.click()
        time.sleep(0.5)  # Wait for animation

        # Take screenshot with sidebar open
        page.screenshot(path=str(screenshots_dir / "4_sidebar_open.png"))
        log_info(f"Screenshot saved: screenshots/4_sidebar_open.png")

        # Check sidebar visibility
        log_step("Checking sidebar state")
        sidebar = page.locator("#sidebar")
        sidebar_visible = sidebar.is_visible()

        if sidebar_visible:
            log_success("Sidebar is visible")
            findings['passed'].append("Sidebar opens correctly")
        else:
            log_failure("Sidebar is not visible")
            findings['failed'].append("Sidebar does not open")
            return findings

        # Check sidebar classes
        sidebar_classes = page.evaluate("document.getElementById('sidebar')?.className || ''")
        log_info(f"Sidebar classes: {sidebar_classes}")

        has_open_class = page.evaluate("document.getElementById('sidebar')?.classList.contains('open')")
        if has_open_class:
            log_success("Sidebar has 'open' class")
            findings['passed'].append("Sidebar state correctly set")
        else:
            log_warning("Sidebar missing 'open' class")
            findings['warnings'].append("Sidebar state may be incorrect")

        # Check overlay visibility
        log_step("Checking sidebar overlay")
        overlay = page.locator("#sidebar-overlay")
        overlay_visible = overlay.is_visible()

        if overlay_visible:
            log_success("Sidebar overlay is visible")
            findings['passed'].append("Overlay displays correctly")
        else:
            log_warning("Sidebar overlay is not visible")
            findings['warnings'].append("Overlay may be missing")

        # Check overlay styles
        overlay_styles = page.evaluate("""() => {
            const overlay = document.getElementById('sidebar-overlay');
            if (overlay) {
                const computed = window.getComputedStyle(overlay);
                return {
                    display: computed.display,
                    position: computed.position,
                    zIndex: computed.zIndex,
                    backgroundColor: computed.backgroundColor,
                    opacity: computed.opacity,
                    width: computed.width,
                    height: computed.height
                };
            }
            return null;
        }""")

        if overlay_styles:
            log_info(f"Overlay styles: {overlay_styles}")

            # Check if overlay covers full screen
            if overlay_styles['width'] == '100%' or 'vw' in str(overlay_styles['width']):
                log_warning("Overlay width is 100% (covers full screen)")
                findings['warnings'].append("Overlay may be covering entire screen")
            else:
                log_success(f"Overlay width is limited: {overlay_styles['width']}")
                findings['passed'].append("Overlay does not cover full screen")

            # Check z-index positioning
            z_index = overlay_styles['zIndex']
            log_info(f"Overlay z-index: {z_index}")
        else:
            log_warning("Could not get overlay styles")

        # Check sidebar styles
        sidebar_styles = page.evaluate("""() => {
            const sidebar = document.getElementById('sidebar');
            if (sidebar) {
                const computed = window.getComputedStyle(sidebar);
                return {
                    position: computed.position,
                    left: computed.left,
                    top: computed.top,
                    width: computed.width,
                    height: computed.height,
                    zIndex: computed.zIndex,
                    backgroundColor: computed.backgroundColor
                };
            }
            return null;
        }""")

        if sidebar_styles:
            log_info(f"Sidebar position: {sidebar_styles['position']}")
            log_info(f"Sidebar left: {sidebar_styles['left']}")
            log_info(f"Sidebar width: {sidebar_styles['width']}")
            log_info(f"Sidebar z-index: {sidebar_styles['zIndex']}")

            # Check if sidebar is properly positioned
            if sidebar_styles['left'].startswith('-'):
                log_warning("Sidebar has negative left position (may be off-screen)")
                findings['warnings'].append("Sidebar positioning may be incorrect")
            else:
                log_success("Sidebar is positioned on-screen")
                findings['passed'].append("Sidebar position correct")

        # Check if main content is still accessible
        main_content = page.locator("#content-area")
        main_content_visible = main_content.is_visible()

        if main_content_visible:
            log_info("Main content is still visible")

            # Check if main content is clickable (not covered by overlay)
            main_content_clickable = page.evaluate("""() => {
                const content = document.getElementById('content-area');
                if (content) {
                    const rect = content.getBoundingClientRect();
                    const centerX = rect.left + rect.width / 2;
                    const centerY = rect.top + rect.height / 2;
                    const element = document.elementFromPoint(centerX, centerY);
                    return element && (element.id === 'content-area' || content.contains(element));
                }
                return false;
            }""")

            if main_content_clickable:
                log_warning("Main content appears to be clickable (overlay may not be blocking)")
                findings['warnings'].append("Overlay may not prevent content interaction")
            else:
                log_success("Overlay is blocking main content interaction")
                findings['passed'].append("Overlay correctly blocks content")

    except Exception as e:
        log_failure(f"Exception during test: {str(e)}")
        findings['failed'].append(f"Test error: {str(e)}")

    return findings

def test_sidebar_click_behavior(page, server_url):
    """Test 3: Sidebar click behavior - links work, outside clicks close"""
    print(f"\n{Colors.BOLD}TEST 3: Sidebar Click Behavior{Colors.END}")
    print("=" * 60)

    findings = {
        'passed': [],
        'failed': [],
        'warnings': []
    }

    try:
        # Navigate to homepage
        log_step("Navigating to homepage")
        page.goto(server_url)
        wait_for_page_ready(page)

        # Open sidebar
        log_step("Opening sidebar")
        nav_button = page.locator("#nav-button")
        nav_button.click()
        time.sleep(0.5)

        # Verify sidebar is open
        sidebar_open = page.evaluate("document.getElementById('sidebar')?.classList.contains('open')")
        if not sidebar_open:
            log_failure("Sidebar did not open")
            findings['failed'].append("Cannot test click behavior - sidebar not opening")
            return findings

        log_success("Sidebar is open")

        # Test 3a: Click on a link inside sidebar
        log_step("Test 3a: Clicking on link inside sidebar")
        feed_links = page.locator("#sidebar a[href*='feed_id=']")
        link_count = feed_links.count()

        if link_count == 0:
            log_warning("No feed links found in sidebar")
            findings['warnings'].append("No feed links to test")
        else:
            log_info(f"Found {link_count} feed links in sidebar")

            # Get first link's text and URL
            first_link = feed_links.first
            link_text = first_link.text_content()
            link_href = first_link.get_attribute("href")
            log_info(f"Clicking on link: '{link_text}' ({link_href})")

            # Take screenshot before click
            screenshots_dir = Path("screenshots")
            page.screenshot(path=str(screenshots_dir / "5_before_link_click.png"))
            log_info(f"Screenshot saved: screenshots/5_before_link_click.png")

            # Click the link
            first_link.click()
            wait_for_htmx_complete(page)
            time.sleep(0.5)

            # Take screenshot after click
            page.screenshot(path=str(screenshots_dir / "6_after_link_click.png"))
            log_info(f"Screenshot saved: screenshots/6_after_link_click.png")

            # Check if navigation happened
            current_url = page.url
            if "feed_id=" in current_url:
                log_success(f"Navigation successful: {current_url}")
                findings['passed'].append("Sidebar links navigate correctly")
            else:
                log_failure(f"Navigation may have failed: {current_url}")
                findings['failed'].append("Sidebar links may not work")

            # Check if sidebar closed after clicking link
            sidebar_still_open = page.evaluate("document.getElementById('sidebar')?.classList.contains('open')")
            if sidebar_still_open:
                log_warning("Sidebar is still open after clicking link")
                findings['warnings'].append("Sidebar may not auto-close after link click")
            else:
                log_success("Sidebar closed after clicking link")
                findings['passed'].append("Sidebar auto-closes after link click")

        # Test 3b: Click outside sidebar (on overlay) to close it
        log_step("Test 3b: Clicking outside sidebar (on overlay)")

        # Re-open sidebar if it closed
        if not page.evaluate("document.getElementById('sidebar')?.classList.contains('open')"):
            log_info("Re-opening sidebar")
            page.locator("#nav-button").click()
            time.sleep(0.5)

        # Take screenshot with sidebar open
        page.screenshot(path=str(screenshots_dir / "7_sidebar_open_for_overlay_test.png"))
        log_info(f"Screenshot saved: screenshots/7_sidebar_open_for_overlay_test.png")

        # Click on overlay (outside sidebar)
        log_info("Clicking on overlay to close sidebar")
        overlay = page.locator("#sidebar-overlay")

        if not overlay.is_visible():
            log_warning("Overlay is not visible - cannot test outside click")
            findings['warnings'].append("Overlay not visible for outside click test")
        else:
            overlay.click()
            time.sleep(0.5)

            # Take screenshot after overlay click
            page.screenshot(path=str(screenshots_dir / "8_after_overlay_click.png"))
            log_info(f"Screenshot saved: screenshots/8_after_overlay_click.png")

            # Check if sidebar closed
            sidebar_closed = not page.evaluate("document.getElementById('sidebar')?.classList.contains('open')")
            if sidebar_closed:
                log_success("Sidebar closed after clicking outside")
                findings['passed'].append("Outside clicks close sidebar")
            else:
                log_failure("Sidebar is still open after clicking outside")
                findings['failed'].append("Outside clicks do not close sidebar")

        # Test 3c: Check if sidebar closes immediately when clicking anywhere
        log_step("Test 3c: Testing if sidebar closes immediately on any click")

        # Open sidebar again
        if not page.evaluate("document.getElementById('sidebar')?.classList.contains('open')"):
            log_info("Opening sidebar")
            page.locator("#nav-button").click()
            time.sleep(0.5)

        # Try clicking on main content (should be blocked by overlay)
        log_info("Attempting to click on main content (should be blocked)")
        main_content = page.locator("#content-area")

        try:
            # Get coordinates of main content
            content_box = main_content.bounding_box()
            if content_box:
                # Click in the middle of main content area
                page.mouse.click(content_box['x'] + content_box['width'] / 2,
                               content_box['y'] + content_box['height'] / 2)
                time.sleep(0.5)

                # Check if sidebar closed
                sidebar_closed = not page.evaluate("document.getElementById('sidebar')?.classList.contains('open')")
                if sidebar_closed:
                    log_success("Sidebar closed when clicking on main content area (overlay intercepted)")
                    findings['passed'].append("Overlay correctly intercepts clicks")
                else:
                    log_warning("Sidebar did not close when clicking main content")
                    findings['warnings'].append("Overlay may not intercept all clicks")
        except Exception as e:
            log_info(f"Could not test main content click: {str(e)}")

    except Exception as e:
        log_failure(f"Exception during test: {str(e)}")
        findings['failed'].append(f"Test error: {str(e)}")

    return findings

def print_summary(test_name, findings):
    """Print summary of test findings"""
    total_checks = len(findings['passed']) + len(findings['failed']) + len(findings['warnings'])

    print(f"\n{Colors.BOLD}Summary for {test_name}:{Colors.END}")
    print(f"  Total checks: {total_checks}")
    print(f"  {Colors.GREEN}Passed: {len(findings['passed'])}{Colors.END}")
    print(f"  {Colors.RED}Failed: {len(findings['failed'])}{Colors.END}")
    print(f"  {Colors.YELLOW}Warnings: {len(findings['warnings'])}{Colors.END}")

    if findings['passed']:
        print(f"\n{Colors.GREEN}Passing:{Colors.END}")
        for item in findings['passed']:
            print(f"  ✓ {item}")

    if findings['failed']:
        print(f"\n{Colors.RED}Failing:{Colors.END}")
        for item in findings['failed']:
            print(f"  ✗ {item}")

    if findings['warnings']:
        print(f"\n{Colors.YELLOW}Warnings:{Colors.END}")
        for item in findings['warnings']:
            print(f"  ⚠ {item}")

def main():
    """Main test runner"""
    server_url = "http://localhost:8080"

    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}Mobile UI Debugging Script{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"Server: {server_url}")
    print(f"Viewport: 390x844 (iPhone 12 Pro)")
    print(f"Screenshots will be saved to: ./screenshots/")

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)  # Running in headless mode

        # Create mobile context
        context = browser.new_context(
            viewport={'width': 390, 'height': 844},
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15'
        )

        page = context.new_page()

        try:
            # Check if server is running
            log_step("Checking server availability")
            try:
                page.goto(server_url, timeout=5000)
                wait_for_page_ready(page)
                log_success(f"Server is running at {server_url}")
            except Exception as e:
                log_failure(f"Server is not accessible at {server_url}")
                log_failure(f"Error: {str(e)}")
                print(f"\n{Colors.RED}Please start the server first:{Colors.END}")
                print(f"  python -m app")
                print(f"  OR")
                print(f"  MINIMAL_MODE=true python -m app")
                return

            # Run all tests
            all_findings = {}

            # Test 1: Back button
            findings1 = test_back_button_navigation(page, server_url)
            all_findings['Back Button Navigation'] = findings1
            print_summary('Back Button Navigation', findings1)

            # Test 2: Sidebar grey screen
            findings2 = test_sidebar_grey_screen(page, server_url)
            all_findings['Sidebar Grey Screen'] = findings2
            print_summary('Sidebar Grey Screen', findings2)

            # Test 3: Sidebar click behavior
            findings3 = test_sidebar_click_behavior(page, server_url)
            all_findings['Sidebar Click Behavior'] = findings3
            print_summary('Sidebar Click Behavior', findings3)

            # Final summary
            print(f"\n{Colors.BOLD}{'=' * 60}{Colors.END}")
            print(f"{Colors.BOLD}FINAL SUMMARY{Colors.END}")
            print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")

            total_passed = sum(len(f['passed']) for f in all_findings.values())
            total_failed = sum(len(f['failed']) for f in all_findings.values())
            total_warnings = sum(len(f['warnings']) for f in all_findings.values())

            print(f"\nTotal across all tests:")
            print(f"  {Colors.GREEN}Passed: {total_passed}{Colors.END}")
            print(f"  {Colors.RED}Failed: {total_failed}{Colors.END}")
            print(f"  {Colors.YELLOW}Warnings: {total_warnings}{Colors.END}")

            if total_failed == 0:
                print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed!{Colors.END}")
            else:
                print(f"\n{Colors.RED}{Colors.BOLD}Some tests failed - review findings above{Colors.END}")

            print(f"\n{Colors.BLUE}Screenshots saved to: ./screenshots/{Colors.END}")
            print(f"  1_article_view.png - Article view before back button")
            print(f"  2_after_back.png - After clicking back button")
            print(f"  3_before_sidebar.png - Initial state")
            print(f"  4_sidebar_open.png - Sidebar open (check for grey screen)")
            print(f"  5_before_link_click.png - Before clicking sidebar link")
            print(f"  6_after_link_click.png - After clicking sidebar link")
            print(f"  7_sidebar_open_for_overlay_test.png - Sidebar open for overlay test")
            print(f"  8_after_overlay_click.png - After clicking outside sidebar")

        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    main()
