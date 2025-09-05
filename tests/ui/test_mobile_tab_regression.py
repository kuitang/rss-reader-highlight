"""Test mobile tab style updates regression"""

import pytest
import re
from playwright.sync_api import Page, expect

# HTMX Helper Functions for Fast Testing
def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete - much faster than fixed timeouts"""
    page.wait_for_function("() => !document.body.classList.contains('htmx-request')", timeout=timeout)

def wait_for_page_ready(page):
    """Fast page ready check - waits for network idle instead of fixed timeout"""
    page.wait_for_load_state("networkidle")


def test_mobile_tab_active_style_updates(page: Page, test_server_url):
    """Test that mobile tab styles update correctly when switching between All Posts and Unread"""
    page.goto(test_server_url)
    page.set_viewport_size({"width": 390, "height": 844})
    
    # Wait for page load
    wait_for_page_ready(page)
    
    # Find the tab buttons in mobile persistent header
    all_posts_tab = page.locator('#mobile-persistent-header a[role="button"]:has-text("All Posts")').first
    unread_tab = page.locator('#mobile-persistent-header a[role="button"]:has-text("Unread")').first
    
    # Verify tabs exist
    expect(all_posts_tab).to_be_visible()
    expect(unread_tab).to_be_visible()
    
    # Test 1: Default state - Unread should be active
    unread_parent = unread_tab.locator('..')
    expect(unread_parent).to_have_class(re.compile(r'uk-active'))
    print("✅ Initial state: Unread tab has uk-active class")
    
    # Test 2: Click All Posts - should become active
    all_posts_tab.click()
    wait_for_htmx_complete(page)
    
    all_posts_parent = all_posts_tab.locator('..')
    expect(all_posts_parent).to_have_class(re.compile(r'uk-active'))
    print("✅ After clicking All Posts: All Posts tab has uk-active class")
    
    # Verify Unread tab is no longer active
    unread_parent = unread_tab.locator('..')
    expect(unread_parent).not_to_have_class(re.compile(r'uk-active'))
    print("✅ After clicking All Posts: Unread tab lost uk-active class")
    
    # Test 3: Click Unread - should become active again
    unread_tab.click()
    wait_for_htmx_complete(page)
    
    unread_parent = unread_tab.locator('..')
    expect(unread_parent).to_have_class(re.compile(r'uk-active'))
    print("✅ After clicking Unread: Unread tab has uk-active class")
    
    # Verify All Posts tab is no longer active
    all_posts_parent = all_posts_tab.locator('..')
    expect(all_posts_parent).not_to_have_class(re.compile(r'uk-active'))
    print("✅ After clicking Unread: All Posts tab lost uk-active class")


if __name__ == "__main__":
    import re
    # Can run this file directly for debugging
    pass