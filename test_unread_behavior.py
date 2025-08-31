#!/usr/bin/env python3
"""
Comprehensive test for unread behavior and navigation issues.
Tests both mobile and desktop functionality.
"""

import asyncio
from playwright.async_api import async_playwright
import time

async def test_unread_behavior():
    """Test unread marking behavior and navigation"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Enable request/response logging
        page.on("request", lambda req: print(f"REQUEST: {req.method} {req.url}"))
        page.on("response", lambda resp: print(f"RESPONSE: {resp.status} {resp.url}"))
        
        print("=== COMPREHENSIVE UNREAD BEHAVIOR TEST ===")
        
        # Test 1: Desktop unread marking
        print("\n--- TEST 1: Desktop Unread Marking ---")
        await page.goto("http://localhost:5001")
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.wait_for_load_state("networkidle")
        
        # Find first unread article (should have blue dot)
        first_article = page.locator("#desktop-feeds-content .js-filter li").first
        article_html_before = await first_article.inner_html()
        has_blue_dot_before = "bg-blue-600" in article_html_before
        print(f"✓ First article has blue dot before click: {has_blue_dot_before}")
        
        # Click article
        await first_article.click()
        await page.wait_for_timeout(1000)  # Wait for update
        
        # Check if blue dot is removed
        article_html_after = await first_article.inner_html()
        has_blue_dot_after = "bg-blue-600" in article_html_after
        print(f"❌ First article still has blue dot after click: {has_blue_dot_after}")
        
        if has_blue_dot_after == has_blue_dot_before:
            print("❌ DESKTOP UNREAD MARKING FAILED: Style not updated")
        else:
            print("✓ DESKTOP UNREAD MARKING WORKING: Style updated")
        
        # Test 2: Desktop pagination
        print("\n--- TEST 2: Desktop Pagination ---")
        next_button = page.locator("#desktop-feeds-content").get_by_role("button").filter(has_text="")
        if await next_button.count() > 0:
            await next_button.last.click()
            await page.wait_for_timeout(1000)
            page_info = await page.locator("#desktop-feeds-content").get_by_text("Page").inner_text()
            print(f"✓ Pagination result: {page_info}")
        else:
            print("❌ PAGINATION BUTTONS NOT FOUND")
        
        # Test 3: Mobile unread marking
        print("\n--- TEST 3: Mobile Unread Marking ---")
        await page.set_viewport_size({"width": 375, "height": 812})
        await page.goto("http://localhost:5001")
        await page.wait_for_load_state("networkidle")
        
        # Find first unread article on mobile
        mobile_article = page.locator("#main-content .js-filter li").first
        mobile_html_before = await mobile_article.inner_html()
        mobile_has_dot_before = "bg-blue-600" in mobile_html_before
        print(f"✓ Mobile first article has blue dot before click: {mobile_has_dot_before}")
        
        # Click article (should show full screen)
        await mobile_article.click()
        await page.wait_for_timeout(1000)
        
        # Check if we're now in article view
        back_button_exists = await page.locator("button").filter(has_text="Back").count() > 0
        print(f"✓ Mobile article view loaded (back button exists): {back_button_exists}")
        
        # Go back and check if style updated
        if back_button_exists:
            await page.locator("button").filter(has_text="Back").click()
            await page.wait_for_timeout(1000)
            
            # Check same article for style change
            mobile_html_after = await mobile_article.inner_html()
            mobile_has_dot_after = "bg-blue-600" in mobile_html_after
            print(f"❌ Mobile article still has blue dot after reading: {mobile_has_dot_after}")
            
            if mobile_has_dot_after == mobile_has_dot_before:
                print("❌ MOBILE UNREAD MARKING FAILED: Style not updated")
            else:
                print("✓ MOBILE UNREAD MARKING WORKING: Style updated")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_unread_behavior())