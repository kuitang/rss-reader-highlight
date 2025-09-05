"""Shared Playwright fixtures for UI tests with module-level isolation

Each test MODULE (file) gets its own browser instance for isolation when running
files in parallel, but tests within a module share the browser for efficiency.

Server Dependency Management:
- UI tests require a running server (marked with @pytest.mark.needs_server)
- Start server manually: python app.py (or MINIMAL_MODE=true python app.py)
- Server URL standardized through test_server_url fixture
"""

import pytest
import httpx
import os
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def test_server_url():
    """Verify server is running and return URL for UI tests
    
    This fixture enforces server dependency for UI tests.
    
    To run UI tests:
    1. Start server: python app.py (or MINIMAL_MODE=true python app.py)  
    2. Run tests: pytest tests/ui/
    
    Or skip server-dependent tests: pytest -m "not needs_server"
    """
    server_url = os.environ.get('TEST_SERVER_URL', 'http://localhost:8080')
    
    # Verify server is accessible
    try:
        response = httpx.get(server_url, timeout=5)
        if response.status_code != 200:
            pytest.skip(f"Test server not running: returned status {response.status_code}. "
                       f"Start server with: python app.py")
    except httpx.RequestError as e:
        pytest.skip(f"Test server not accessible at {server_url}: {e}. "
                   f"Start server with: python app.py")
    
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