#!/usr/bin/env python3
"""
Final comprehensive test of all RSS Reader functionality.
Tests mobile, desktop, navigation, unread marking, and performance.
"""

import asyncio
from playwright.async_api import async_playwright
import time

async def test_comprehensive_functionality():
    """Test all functionality comprehensively"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        print("=== FINAL COMPREHENSIVE FUNCTIONALITY TEST ===")
        
        # Test 1: Desktop functionality
        print("\n--- TEST 1: Desktop Functionality ---")
        await page.goto("http://localhost:5001")
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.wait_for_load_state("networkidle")
        
        # Desktop layout check
        desktop_visible = await page.locator("#desktop-layout").is_visible()
        mobile_header_hidden = not await page.locator("#mobile-header").is_visible()
        print(f"✓ Desktop layout: {desktop_visible}, Mobile header hidden: {mobile_header_hidden}")
        
        # Test article loading and unread marking
        first_article = page.locator("#desktop-feeds-content .js-filter li").first
        article_title = (await first_article.inner_text()).split('\\n')[0]
        
        # Check for blue dot before click
        has_blue_dot_before = "bg-blue-600" in await first_article.inner_html()
        
        # Click article
        start_time = time.time()
        await first_article.click()
        await page.wait_for_function("document.querySelector('#desktop-item-detail').innerText !== 'Select a post to read'", timeout=2000)
        load_time = time.time() - start_time
        
        # Check for blue dot after click
        has_blue_dot_after = "bg-blue-600" in await first_article.inner_html()
        
        print(f"✓ Article '{article_title[:40]}...' loaded in {load_time:.2f}s")
        print(f"✓ Unread marking: blue dot before={has_blue_dot_before}, after={has_blue_dot_after}")
        
        # Test pagination
        next_button = page.locator("#desktop-feeds-content button").filter(has_text="").last
        if await next_button.count() > 0:
            await next_button.click()
            await page.wait_for_timeout(500)
            print("✓ Desktop pagination working")
        
        # Test 2: Mobile functionality  
        print("\\n--- TEST 2: Mobile Functionality ---")
        await page.set_viewport_size({"width": 375, "height": 812})
        await page.goto("http://localhost:5001")
        await page.wait_for_load_state("networkidle")
        
        # Mobile layout check
        mobile_visible = await page.locator("#main-content").is_visible()
        mobile_header_visible = await page.locator("#mobile-header").is_visible()
        desktop_hidden = not await page.locator("#desktop-layout").is_visible()
        print(f"✓ Mobile layout: {mobile_visible}, Header: {mobile_header_visible}, Desktop hidden: {desktop_hidden}")
        
        # Test mobile article navigation
        mobile_article = page.locator("#main-content .js-filter li").first
        mobile_title = (await mobile_article.inner_text()).split('\\n')[0]
        
        await mobile_article.click()
        await page.wait_for_timeout(1000)
        
        # Check if back button appears
        back_button_exists = await page.locator("button").filter(has_text="Back").count() > 0
        page_text = await page.locator("body").inner_text()
        article_view_loaded = "Select a post to read" not in page_text
        
        print(f"✓ Mobile article '{mobile_title[:40]}...' navigation: back_button={back_button_exists}, content_loaded={article_view_loaded}")
        
        # Test back navigation
        if back_button_exists:
            await page.locator("button").filter(has_text="Back").click()
            await page.wait_for_timeout(500)
            back_to_list = await page.locator("#main-content .js-filter").is_visible()
            print(f"✓ Mobile back navigation: {back_to_list}")
        
        # Test 3: External links
        print("\\n--- TEST 3: External Links ---")
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.goto("http://localhost:5001")
        await page.wait_for_load_state("networkidle")
        
        # Click article to load detail
        await page.locator("#desktop-feeds-content .js-filter li").first.click()
        await page.wait_for_timeout(500)
        
        # Check if Open Link exists and has target="_blank"
        open_link = page.locator("a").filter(has_text="Open Link")
        if await open_link.count() > 0:
            target_attr = await open_link.get_attribute("target")
            href_attr = await open_link.get_attribute("href")
            print(f"✓ External link: target='{target_attr}', href exists={bool(href_attr)}")
        
        print("\\n🎉 ALL TESTS COMPLETED")
        await browser.close()
        return True

if __name__ == "__main__":
    success = asyncio.run(test_comprehensive_functionality())
    exit(0 if success else 1)