"""Helper functions for UI tests with tenacity-based retries and conditional waits"""

import httpx
from playwright.sync_api import Page
from tenacity import (
    retry,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError
)
import logging

from test_constants import (
    MAX_WAIT_MS,
    MINIMAL_WAIT_MS,
    SERVER_STARTUP_TIMEOUT_SECONDS,
    SERVER_STARTUP_RETRY_DELAY,
    RETRY_DELAY_SECONDS,
    PAGE_LOAD_RETRY_DELAY
)

logger = logging.getLogger(__name__)


def wait_for_htmx_complete(page: Page, timeout: int = MAX_WAIT_MS):
    """Wait for all HTMX requests to complete"""
    page.wait_for_function(
        "() => !document.body.classList.contains('htmx-request')",
        timeout=timeout
    )


def wait_for_htmx_settle(page: Page, timeout: int = MAX_WAIT_MS):
    """Wait for HTMX to fully settle (no requests and no settling class)"""
    page.wait_for_function(
        "() => !document.body.classList.contains('htmx-request') && !document.body.classList.contains('htmx-settling')",
        timeout=timeout
    )


def wait_for_page_ready(page: Page):
    """Wait for page to be fully loaded"""
    page.wait_for_load_state('domcontentloaded')
    page.wait_for_load_state('networkidle')


@retry(
    stop=stop_after_delay(SERVER_STARTUP_TIMEOUT_SECONDS),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.RequestError),
    before_sleep=before_sleep_log(logger, logging.DEBUG)
)
def wait_for_server_ready(url: str, timeout: float = 2.0) -> httpx.Response:
    """
    Wait for server to be ready using tenacity with exponential backoff.

    Args:
        url: Server URL to check
        timeout: Timeout for each request attempt

    Returns:
        httpx.Response when server is ready

    Raises:
        RetryError: If server doesn't become ready within timeout
    """
    response = httpx.get(url, timeout=timeout)
    if response.status_code != 200:
        raise httpx.RequestError(f"Server returned {response.status_code}")
    return response


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(TimeoutError),
    before_sleep=before_sleep_log(logger, logging.DEBUG)
)
def navigate_with_retry(page: Page, url: str, timeout: int = MAX_WAIT_MS):
    """
    Navigate to a URL with automatic retry using tenacity.

    Args:
        page: Playwright page object
        url: URL to navigate to
        timeout: Navigation timeout

    Raises:
        RetryError: If navigation fails after all retries
    """
    try:
        page.goto(url, timeout=timeout)
    except Exception as e:
        # Convert Playwright timeout to standard TimeoutError for tenacity
        if "Timeout" in str(e):
            raise TimeoutError(f"Navigation timeout: {e}")
        raise


def wait_for_css_transition(page: Page, selector: str, property: str = None, timeout: int = MAX_WAIT_MS):
    """
    Wait for CSS transition to complete on an element.

    Args:
        page: Playwright page object
        selector: Element selector
        property: Specific CSS property to check (optional)
        timeout: Maximum wait time
    """
    if property:
        # Wait for specific property transition to complete
        page.wait_for_function(
            f"""(selector, prop) => {{
                const el = document.querySelector(selector);
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const transition = style.transition || style.webkitTransition || '';
                return !transition.includes(prop) ||
                       transition === 'none' ||
                       transition === 'all 0s ease 0s';
            }}""",
            arg=[selector, property],
            timeout=timeout
        )
    else:
        # Wait for all transitions to complete
        page.wait_for_function(
            f"""(selector) => {{
                const el = document.querySelector(selector);
                if (!el) return false;
                return new Promise(resolve => {{
                    const handleEnd = () => {{
                        el.removeEventListener('transitionend', handleEnd);
                        resolve(true);
                    }};

                    const style = window.getComputedStyle(el);
                    const transition = style.transition || style.webkitTransition || '';

                    if (transition === 'none' || transition === 'all 0s ease 0s' || !transition) {{
                        resolve(true);
                    }} else {{
                        el.addEventListener('transitionend', handleEnd);
                        // Fallback timeout in case transitionend doesn't fire
                        setTimeout(() => resolve(true), {MINIMAL_WAIT_MS});
                    }}
                }});
            }}""",
            arg=selector,
            timeout=timeout
        )


def wait_for_viewport_transition(page: Page, timeout: int = MAX_WAIT_MS):
    """
    Wait for responsive layout transition after viewport change.

    Args:
        page: Playwright page object
        timeout: Maximum wait time
    """
    # Wait for any media query transitions to complete
    page.wait_for_function(
        """() => {
            // Check if any elements are transitioning
            const elements = document.querySelectorAll('*');
            for (const el of elements) {
                const style = window.getComputedStyle(el);
                const transition = style.transition || style.webkitTransition || '';
                if (transition && transition !== 'none' && transition !== 'all 0s ease 0s') {
                    return false;
                }
            }
            return true;
        }""",
        timeout=timeout
    )

    # Also ensure layout elements are in expected state
    page.wait_for_function(
        """() => {
            const desktop = document.querySelector('#desktop-layout');
            const mobile = document.querySelector('#mobile-layout');

            // At least one layout should be visible
            const desktopVisible = desktop && window.getComputedStyle(desktop).display !== 'none';
            const mobileVisible = mobile && window.getComputedStyle(mobile).display !== 'none';

            return desktopVisible || mobileVisible;
        }""",
        timeout=timeout
    )


def wait_for_element_transition(page: Page, selector: str, timeout: int = MAX_WAIT_MS):
    """
    Wait for an element to finish any transitions or animations.

    Args:
        page: Playwright page object
        selector: Element selector
        timeout: Maximum wait time
    """
    page.wait_for_function(
        f"""(selector) => {{
            const el = document.querySelector(selector);
            if (!el) return true; // Element doesn't exist, no transition

            const style = window.getComputedStyle(el);
            const transition = style.transition || style.webkitTransition || '';
            const animation = style.animation || style.webkitAnimation || '';

            return (transition === 'none' || transition === 'all 0s ease 0s' || !transition) &&
                   (animation === 'none' || animation === '' || !animation);
        }}""",
        arg=selector,
        timeout=timeout
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1, max=5),
    before_sleep=before_sleep_log(logger, logging.DEBUG)
)
def click_with_retry(page: Page, selector: str, timeout: int = MAX_WAIT_MS):
    """
    Click an element with automatic retry using tenacity.

    Args:
        page: Playwright page object
        selector: Element selector to click
        timeout: Timeout for element to be clickable

    Raises:
        RetryError: If click fails after all retries
    """
    element = page.locator(selector)
    element.wait_for(state="visible", timeout=timeout)
    element.click()
    wait_for_htmx_complete(page, timeout=timeout)