"""Shared Playwright fixtures for UI tests with module-level isolation

Each test MODULE (file) gets its own browser instance for isolation when running
files in parallel, but tests within a module share the browser for efficiency.
"""

import pytest
import httpx
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def server_manager():
    """Dummy fixture for compatibility - tests should start server manually or use MINIMAL_MODE"""
    # This is a placeholder since tests are expected to have server running
    # Start server with: MINIMAL_MODE=true python app.py
    return None


@pytest.fixture(scope="session")
def test_server_url(server_manager):
    """Ensure test server is running and return URL for UI tests"""
    server_url = "http://localhost:8080"
    
    # Verify server is accessible
    try:
        response = httpx.get(server_url, timeout=5)
        if response.status_code != 200:
            pytest.fail(f"Test server returned status {response.status_code}")
    except httpx.RequestError as e:
        pytest.fail(f"Test server not accessible at {server_url}: {e}")
    
    return server_url


@pytest.fixture(scope="module")  # One browser per test file/module
def browser():
    """Create a browser instance per test module for parallel suite execution"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="function")  # Each test gets its own page/context
def page(browser, test_server_url):
    """Create a new page in a new context for test isolation within a module"""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="function")
def mobile_context(browser, test_server_url):
    """Create a mobile browser context (iPhone 12 Pro dimensions)"""
    context = browser.new_context(
        viewport={'width': 390, 'height': 844},
        user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15'
    )
    page = context.new_page()
    yield page
    context.close()