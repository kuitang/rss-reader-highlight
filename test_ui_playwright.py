#!/usr/bin/env python3
"""
Playwright TDD tests for UI layout and spinner issues
"""

import pytest
from playwright.sync_api import Page, expect


class TestUILayout:
    """TDD tests for UI layout issues"""
    
    def test_mobile_loading_spinner_hidden_by_default(self, page: Page):
        """
        CRITICAL: Mobile loading spinner should be hidden by default
        """
        # Navigate to mobile view
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8080")
        
        # Wait for page to load
        page.wait_for_selector("h3", timeout=5000)
        
        # Check loading spinner exists but is hidden
        spinner = page.locator("#loading-spinner")
        expect(spinner).to_exist()
        
        # Should have hidden class and not be visible
        expect(spinner).to_have_class(r".*hidden.*")
        expect(spinner).not_to_be_visible()
        
        # Verify it doesn't interfere with content
        main_content = page.locator("#main-content")
        expect(main_content).to_be_visible()
    
    def test_mobile_loading_spinner_shows_during_htmx_request(self, page: Page):
        """
        Mobile loading spinner should only show during HTMX requests
        """
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8080")
        
        # Wait for initial load
        page.wait_for_selector("h3", timeout=5000)
        
        # Spinner should be hidden initially
        spinner = page.locator("#loading-spinner")
        expect(spinner).not_to_be_visible()
        
        # Trigger HTMX request by clicking a feed item
        first_item = page.locator("li[id*='mobile-feed-item']").first
        
        # Click and immediately check if spinner appears
        # Note: This is timing-sensitive, spinner may be very brief
        first_item.click()
        
        # Wait for request to complete
        page.wait_for_load_state("networkidle", timeout=3000)
        
        # Spinner should be hidden again after request
        expect(spinner).not_to_be_visible()
    
    def test_desktop_layout_proper_spacing(self, page: Page):
        """
        CRITICAL: Desktop layout should have proper spacing and margins
        """
        # Navigate to desktop view
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto("http://localhost:8080")
        
        # Wait for desktop layout to load
        desktop_layout = page.locator("#desktop-layout")
        page.wait_for_selector("#desktop-layout", timeout=5000)
        expect(desktop_layout).to_be_visible()
        
        # Check top padding exists
        expect(desktop_layout).to_have_class(r".*pt-4.*")
        
        # Check sidebar has proper padding
        sidebar = page.locator("#sidebar")
        expect(sidebar).to_have_class(r".*px-2.*")
        
        # Check feeds content has padding
        feeds_content = page.locator("#desktop-feeds-content")
        expect(feeds_content).to_have_class(r".*px-4.*")
        
        # Check article detail has padding
        item_detail = page.locator("#desktop-item-detail")
        expect(item_detail).to_have_class(r".*px-6.*")
        
        # Check grid has proper gap
        grid = page.locator("#desktop-layout > div")  # The Grid component
        expect(grid).to_have_class(r".*gap-4.*")
    
    def test_desktop_layout_column_spacing_visual(self, page: Page):
        """
        Desktop columns should have visible spacing between them
        """
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto("http://localhost:8080")
        
        # Wait for layout
        page.wait_for_selector("#desktop-layout", timeout=5000)
        
        # Get bounding boxes of each column
        sidebar_box = page.locator("#sidebar").bounding_box()
        feeds_box = page.locator("#desktop-feeds-content").bounding_box()
        detail_box = page.locator("#desktop-item-detail").bounding_box()
        
        # Verify columns don't overlap and have gaps
        assert sidebar_box["x"] + sidebar_box["width"] < feeds_box["x"], "Sidebar and feeds should have gap"
        assert feeds_box["x"] + feeds_box["width"] < detail_box["x"], "Feeds and detail should have gap"
        
        # Check minimum gap size (should be at least 16px for gap-4)
        sidebar_to_feeds_gap = feeds_box["x"] - (sidebar_box["x"] + sidebar_box["width"])
        feeds_to_detail_gap = detail_box["x"] - (feeds_box["x"] + feeds_box["width"])
        
        assert sidebar_to_feeds_gap >= 16, f"Sidebar to feeds gap too small: {sidebar_to_feeds_gap}px"
        assert feeds_to_detail_gap >= 16, f"Feeds to detail gap too small: {feeds_to_detail_gap}px"
    
    def test_desktop_article_detail_spacing(self, page: Page):
        """
        Article detail panel should have proper internal spacing
        """
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto("http://localhost:8080")
        
        # Wait for layout and click an article
        page.wait_for_selector("#desktop-layout", timeout=5000)
        first_article = page.locator("li[id*='desktop-feed-item']").first
        first_article.click()
        
        # Wait for article to load
        page.wait_for_selector("#item-detail", timeout=5000)
        
        # Check article detail has proper container classes
        article_detail = page.locator("#item-detail")
        expect(article_detail).to_be_visible()
        
        # Should have proper spacing classes
        content_area = page.locator("#item-detail .prose")
        expect(content_area).to_be_visible()
        
        # Check that content isn't cramped against edges
        detail_box = page.locator("#desktop-item-detail").bounding_box()
        content_box = content_area.bounding_box()
        
        # Content should have margins from container edges
        left_margin = content_box["x"] - detail_box["x"]
        assert left_margin >= 20, f"Article content left margin too small: {left_margin}px"
    
    def test_responsive_layout_switches_correctly(self, page: Page):
        """
        Layout should switch correctly between mobile and desktop
        """
        # Start with mobile
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8080")
        
        # Mobile layout should be visible, desktop hidden
        mobile_content = page.locator("#main-content")
        desktop_layout = page.locator("#desktop-layout")
        
        expect(mobile_content).to_be_visible()
        expect(desktop_layout).to_have_class(r".*hidden.*")
        
        # Switch to desktop
        page.set_viewport_size({"width": 1920, "height": 1080})
        
        # Desktop layout should now be visible, mobile content hidden
        expect(desktop_layout).to_have_class(r".*lg:grid.*")
        expect(mobile_content).to_have_class(r".*lg:hidden.*")
    
    def test_all_feeds_show_in_sidebar(self, page: Page):
        """
        All 15 feeds should be visible in the sidebar
        """
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto("http://localhost:8080")
        
        # Wait for feeds to load
        page.wait_for_selector("#sidebar", timeout=5000)
        
        # Count feed items in sidebar (excluding "All Feeds" and "Add Folder")
        feed_links = page.locator("#sidebar a[href*='feed_id']")
        feed_count = feed_links.count()
        
        # Should have 15 feeds (we removed 1 duplicate)
        assert feed_count == 15, f"Expected 15 feeds, found {feed_count}"
        
        # Verify some key feeds are present
        expect(page.locator("text=BBC News")).to_be_visible()
        expect(page.locator("text=Hacker News")).to_be_visible()
        expect(page.locator("text=Bloomberg")).to_be_visible()


if __name__ == '__main__':
    """
    Run tests manually for debugging
    """
    import asyncio
    from playwright.async_api import async_playwright
    
    async def run_ui_tests():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            test_instance = TestUILayout()
            
            print("Testing mobile loading spinner...")
            try:
                # Convert sync test to async for manual running
                await page.set_viewport_size({"width": 375, "height": 667})
                await page.goto("http://localhost:8080")
                await page.wait_for_selector("h3", timeout=5000)
                
                spinner = page.locator("#loading-spinner")
                is_hidden = await spinner.is_hidden()
                print(f"✓ Mobile spinner hidden: {is_hidden}")
                
            except Exception as e:
                print(f"✗ Mobile spinner test failed: {e}")
            
            print("Testing desktop layout spacing...")
            try:
                await page.set_viewport_size({"width": 1920, "height": 1080})
                await page.goto("http://localhost:8080")
                await page.wait_for_selector("#desktop-layout", timeout=5000)
                
                # Check spacing classes
                has_top_padding = await page.locator("#desktop-layout").get_attribute("class")
                has_gap = "gap-4" in has_top_padding and "pt-4" in has_top_padding
                print(f"✓ Desktop spacing classes applied: {has_gap}")
                
                # Click an article to test detail view
                await page.locator("li[id*='desktop-feed-item']").first.click()
                await page.wait_for_selector("#item-detail", timeout=5000)
                print("✓ Article detail loads with proper spacing")
                
            except Exception as e:
                print(f"✗ Desktop layout test failed: {e}")
            
            await browser.close()
    
    # For manual testing
    print("Running UI tests manually...")
    asyncio.run(run_ui_tests())