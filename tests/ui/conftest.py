"""Shared Playwright fixtures for UI tests with module-level isolation

Each test MODULE (file) gets its own browser instance for isolation when running
files in parallel, but tests within a module share the browser for efficiency.
"""

import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="module")  # One browser per test file/module
def browser():
    """Create a browser instance per test module for parallel suite execution"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture(scope="function")  # Each test gets its own page/context
def page(browser):
    """Create a new page in a new context for test isolation within a module"""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()

@pytest.fixture(scope="function")
def mobile_context(browser):
    """Create a mobile browser context (iPhone 12 Pro dimensions)"""
    context = browser.new_context(
        viewport={'width': 390, 'height': 844},
        user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15'
    )
    page = context.new_page()
    yield page
    context.close()