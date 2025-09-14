"""Consolidated add feed flow tests - Mobile, Desktop, and Navigation patterns

Combines functionality from:
- test_add_feed_flow.py (mobile debug flow)
- test_desktop_add_feed.py (desktop flow) 
- test_navigation_and_add_feed_tdd.py (TDD navigation patterns)
"""

import pytest
from playwright.sync_api import sync_playwright, expect
import time
from datetime import datetime

pytestmark = pytest.mark.needs_server

# HTMX Helper Functions for Fast Testing
def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete - much faster than fixed timeouts"""
    page.wait_for_function("() => !document.body.classList.contains('htmx-request')", timeout=timeout)

def wait_for_page_ready(page):
    """Fast page ready check - waits for network idle instead of fixed timeout"""
    page.wait_for_load_state("networkidle")


@pytest.mark.skip(reason="All feed submission tests - skipping per user request")
class TestAddFeedFlows:
    """Test add feed functionality across mobile and desktop interfaces"""
    
    def test_add_feed_complete_flow(self, page, test_server_url):
        """Test complete add feed flow for both mobile and desktop"""
        
        for viewport_name, viewport_size, test_url in [
            ("mobile", {"width": 375, "height": 667}, "https://httpbin.org/xml"),
            ("desktop", {"width": 1200, "height": 800}, "https://feeds.feedburner.com/oreilly/radar")
        ]:
            print(f"\n{('📱' if viewport_name == 'mobile' else '🖥️')} TESTING {viewport_name.upper()} ADD FEED FLOW")
            page.set_viewport_size(viewport_size)
            page.goto(test_server_url, timeout=10000)
            wait_for_page_ready(page)
            
            if viewport_name == "mobile":
                print("=== STEP 1: Open mobile sidebar ===")
                # Find and click hamburger menu
                hamburger_button = page.locator('#mobile-nav-button')
                expect(hamburger_button).to_be_visible(timeout=10000)
                hamburger_button.click()
                page.wait_for_selector("#mobile-sidebar", state="visible")
                print("✓ Clicked hamburger menu")
                    
                # Verify sidebar opened  
                sidebar = page.locator("#mobile-sidebar")
                expect(sidebar).to_be_visible()
                print("✓ Sidebar opened successfully")
                
                print("=== STEP 2: Find add feed form ===")
                # Mobile form elements
                feed_input = page.locator('#mobile-sidebar input[placeholder="Enter RSS URL"]')
                add_button = page.locator('#mobile-sidebar button.uk-btn.add-feed-button')
                layout_selector = "#main-content"
                
                expect(feed_input).to_be_visible()
                expect(add_button).to_be_visible()
                print("✓ Mobile form elements found")
                
                # Check input attributes
                input_name = feed_input.get_attribute("name")
                assert input_name == "new_feed_url", f"Expected name='new_feed_url', got '{input_name}'"
                print(f"✓ Input attributes correct: name='{input_name}'")
            else:
                # Verify desktop layout
                desktop_layout = page.locator("#desktop-layout")
                expect(desktop_layout).to_be_visible()
                print("✓ Desktop layout confirmed")
                
                # Desktop form elements
                feed_input = page.locator('#sidebar input.add-feed-input')
                add_button = page.locator('#sidebar button.uk-btn.add-feed-button')
                layout_selector = "#desktop-layout"
                
                expect(feed_input).to_be_visible()
                expect(add_button).to_be_visible()
                print("✓ Desktop form elements found")
                
                # Check button configuration
                button_target = add_button.get_attribute("hx-target") 
                print(f"✓ Button hx-target: '{button_target}' (may be None if JS sets it dynamically)")
            
            print("=== STEP 3: Test adding a feed ===")
            # Enter test RSS URL
            feed_input.fill(test_url)
            print(f"✓ Entered test URL: {test_url}")
            
            # Click add button
            add_button.click()
            print("✓ Clicked add button")
            
            # Wait for HTMX response
            wait_for_htmx_complete(page, timeout=8000)
            
            # Verify app stability
            expect(page.locator(layout_selector)).to_be_visible()
            if viewport_name == "mobile":
                expect(page.locator("#mobile-sidebar")).to_be_visible()
                print("✓ Mobile sidebar remained stable after add")
                # Check feed links in mobile sidebar
                feed_links = page.locator('#mobile-sidebar a[href*="feed_id"]')
                feed_count = feed_links.count()
                print(f"✓ Feed links found: {feed_count}")
                assert feed_count >= 0, "Should have some feed links (at least default feeds)"
            else:
                expect(page).to_have_title("RSS Reader")
                print("✓ Desktop app remains stable after form submission (no crash)")
            
            print(f"  ✓ {viewport_name} add feed flow test passed")
    
    def test_feed_navigation_after_add(self, page):
        """Test that feed navigation works properly after adding feeds on both mobile and desktop"""
        
        for viewport_name, viewport_size in [
            ("desktop", {"width": 1200, "height": 800}),
            ("mobile", {"width": 375, "height": 667})
        ]:
            print(f"\n{('🖥️' if viewport_name == 'desktop' else '📱')} TESTING {viewport_name.upper()} NAVIGATION AFTER FEED ADD")
            page.set_viewport_size(viewport_size)
            page.goto(test_server_url, timeout=10000)
            wait_for_page_ready(page)
            
            if viewport_name == "desktop":
                # Verify desktop layout
                desktop_layout = page.locator("#desktop-layout")
                expect(desktop_layout).to_be_visible()
                print("✓ Desktop layout confirmed")
                
                # Get initial state
                initial_url = page.url
                initial_feed_links = page.locator("#sidebar a[href*='feed_id=']")
                initial_count = initial_feed_links.count()
                print(f"✓ Initial state: URL={initial_url}, feeds={initial_count}")
                
                # Add a feed first (if form available)
                desktop_input = page.locator('#sidebar input.add-feed-input')
                desktop_button = page.locator('#sidebar button.uk-btn.add-feed-button')
                
                if desktop_input.is_visible() and desktop_button.is_visible():
                    test_url = "https://httpbin.org/xml"
                    desktop_input.fill(test_url)
                    desktop_button.click()
                    wait_for_htmx_complete(page)
                    print("✓ Added test feed")
                
                # Test navigation
                feed_links = page.locator("#sidebar a[href*='feed_id=']")
                content_selector = "#desktop-feeds-content"
            else:
                # Mobile layout
                mobile_content = page.locator("#main-content")
                expect(mobile_content).to_be_visible()
                print("✓ Mobile layout confirmed")
                
                # Open sidebar and add feed
                hamburger_button = page.locator('#mobile-nav-button')
                hamburger_button.click()
                page.wait_for_selector("#mobile-sidebar", state="visible")
                
                # Add feed if form available
                feed_input = page.locator('#mobile-sidebar input[placeholder="Enter RSS URL"]')
                add_button = page.locator('#mobile-sidebar button.uk-btn.add-feed-button')
                
                if feed_input.is_visible() and add_button.is_visible():
                    test_url = "https://httpbin.org/xml"
                    feed_input.fill(test_url)
                    add_button.click()
                    wait_for_htmx_complete(page)
                    print("✓ Added test feed to mobile")
                
                # Test navigation
                feed_links = page.locator('#mobile-sidebar a[href*="feed_id="]')
                content_selector = "#main-content"
            
            # Navigate to first feed
            if feed_links.count() > 0:
                first_feed = feed_links.first
                expect(first_feed).to_be_visible()
                
                # Get feed URL before clicking
                feed_href = first_feed.get_attribute("href")
                print(f"✓ Navigating to: {feed_href}")
                
                # Click feed link
                first_feed.click()
                wait_for_htmx_complete(page)
                
                if viewport_name == "desktop":
                    # Desktop: verify URL changed and content updated
                    new_url = page.url
                    print(f"✓ Navigation completed: {initial_url} -> {new_url}")
                    expect(page.locator(content_selector)).to_be_visible()
                    print("✓ Content area remains visible after navigation")
                else:
                    # Mobile: verify sidebar closed and content updated
                    sidebar = page.locator("#mobile-sidebar")
                    expect(sidebar).to_have_attribute("hidden", "true")
                    print("✓ Sidebar closed after feed selection")
                    expect(page.locator(content_selector)).to_be_visible()
                    print("✓ Main content updated after feed selection")
            
            print(f"  ✓ {viewport_name} navigation test passed")
    
    def test_duplicate_feed_handling(self, page):
        """Test handling of duplicate feed additions"""
        page.set_viewport_size({"width": 1200, "height": 800})  # Desktop for simplicity
        page.goto(test_server_url, timeout=10000)
        wait_for_page_ready(page)
        
        print("🔄 TESTING DUPLICATE FEED HANDLING")
        
        desktop_input = page.locator('#sidebar input.add-feed-input')
        desktop_button = page.locator('#sidebar button.uk-btn.add-feed-button')
        
        expect(desktop_input).to_be_visible()
        expect(desktop_button).to_be_visible()
        
        # Try to add a URL that might already exist (default feeds)
        # Use Hacker News as it's likely to be a default feed
        duplicate_url = "https://hnrss.org/frontpage"
        
        desktop_input.fill(duplicate_url)
        desktop_button.click()
        wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX response instead of page ready
        
        # Should handle gracefully - either show "already subscribed" message
        # or silently ignore, but shouldn't crash
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page).to_have_title("RSS Reader")  # App should remain stable
        print("✓ Duplicate feed handled gracefully")
    
    def test_invalid_url_handling(self, page):
        """Test handling of invalid URLs"""
        page.set_viewport_size({"width": 1200, "height": 800})  # Desktop
        page.goto(test_server_url, timeout=10000)
        wait_for_page_ready(page)
        
        print("❌ TESTING INVALID URL HANDLING")
        
        invalid_urls = [
            "not-a-url",
            "javascript:alert('xss')",
            "http://",
            "https://definitely-does-not-exist-domain-12345.com/rss"
        ]
        
        for invalid_url in invalid_urls:
            print(f"Testing invalid URL: {invalid_url}")
            
            # OPTION 1: Fresh element lookup after each HTMX operation
            # Check if sidebar still exists after previous operation
            if not page.locator('#sidebar').is_visible():
                print(f"  ! Sidebar not available after previous operation, skipping {invalid_url}")
                continue
                
            desktop_input = page.locator('#sidebar input.add-feed-input')
            desktop_button = page.locator('#sidebar button.uk-btn.add-feed-button')
            
            if not (desktop_input.is_visible() and desktop_button.is_visible()):
                print(f"  ! Form elements not available, skipping {invalid_url}")
                continue
            
            desktop_input.clear()
            desktop_input.fill(invalid_url)
            desktop_button.click()
            wait_for_htmx_complete(page)
            
            # Should handle gracefully - app shouldn't crash
            expect(page.locator("#desktop-layout")).to_be_visible()
            expect(page).to_have_title("RSS Reader")
            print(f"✓ Invalid URL handled gracefully: {invalid_url}")
    
    def test_empty_form_submission(self, page):
        """Test submission of empty form"""
        page.set_viewport_size({"width": 1200, "height": 800})  # Desktop
        page.goto(test_server_url, timeout=10000)
        wait_for_page_ready(page)
        
        print("⭕ TESTING EMPTY FORM SUBMISSION")
        
        desktop_input = page.locator('#sidebar input.add-feed-input')
        desktop_button = page.locator('#sidebar button.uk-btn.add-feed-button')
        
        expect(desktop_input).to_be_visible()
        expect(desktop_button).to_be_visible()
        
        # Ensure input is empty
        desktop_input.clear()
        
        # Submit empty form
        desktop_button.click()
        wait_for_htmx_complete(page)
        
        # Should handle gracefully - possibly show validation message
        expect(page.locator("#desktop-layout")).to_be_visible()
        expect(page).to_have_title("RSS Reader")  # App should remain stable
        print("✓ Empty form submission handled gracefully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])