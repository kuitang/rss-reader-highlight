#!/usr/bin/env python3
"""
Playwright test to replicate desktop article loading issue.
TDD approach: Test first, then fix.

Problem: Desktop articles either don't load or only work on second click.
Expected: First click should instantly load article in right panel.
"""

import asyncio
from playwright.async_api import async_playwright
import time

async def test_desktop_article_loading():
    """
    Test desktop article loading behavior:
    1. Click once -> Should load content immediately
    2. If fails, test second click behavior
    """
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Enable request/response logging
        page.on("request", lambda req: print(f"REQUEST: {req.method} {req.url}"))
        page.on("response", lambda resp: print(f"RESPONSE: {resp.status} {resp.url} ({resp.request.timing['responseEnd'] - resp.request.timing['requestStart']:.2f}ms)"))
        
        print("=== DESKTOP ARTICLE LOADING TEST ===")
        
        # Navigate to desktop view
        await page.goto("http://localhost:5001")
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        # Wait for initial load
        await page.wait_for_load_state("networkidle")
        print("✓ Initial page loaded")
        
        # Verify we're in desktop mode (3-column layout)
        desktop_layout = await page.locator("#desktop-layout").is_visible()
        detail_panel = await page.locator("#desktop-item-detail").is_visible()
        
        print(f"DEBUG: desktop_layout visible = {desktop_layout}")
        print(f"DEBUG: detail_panel visible = {detail_panel}")
        
        if not desktop_layout or not detail_panel:
            print("❌ FAIL: Desktop layout not detected")
            await browser.close()
            return False
            
        print("✓ Desktop layout confirmed")
        
        # Find first article
        first_article = page.locator("#desktop-layout .js-filter li").first
        article_text = await first_article.inner_text()
        article_title = article_text.split('\n')[0]
        print(f"✓ Found first article: {article_title}")
        
        # Check initial detail panel state (use desktop-specific selector)
        initial_detail = await page.locator("#desktop-item-detail").inner_text()
        print(f"✓ Initial detail panel: {initial_detail.strip()}")
        
        # TEST 1: First click
        print("\n--- TEST 1: First Click ---")
        start_time = time.time()
        
        await first_article.click()
        
        # Wait a reasonable amount for content (2 seconds)
        try:
            await page.wait_for_function(
                "document.querySelector('#desktop-item-detail').innerText !== 'Select a post to read'",
                timeout=2000
            )
            first_click_time = time.time() - start_time
            detail_after_first = await page.locator("#desktop-item-detail").inner_text()
            print(f"✓ FIRST CLICK SUCCESS: Content loaded in {first_click_time:.2f}s")
            print(f"  Content preview: {detail_after_first[:100]}...")
            await browser.close()
            return True
            
        except Exception as e:
            first_click_time = time.time() - start_time
            detail_after_first = await page.locator("#desktop-item-detail").inner_text()
            print(f"❌ FIRST CLICK FAIL: No content after {first_click_time:.2f}s")
            print(f"  Detail panel still shows: {detail_after_first.strip()}")
        
        # TEST 2: Second click
        print("\n--- TEST 2: Second Click ---")
        start_time = time.time()
        
        await first_article.click()
        
        # Wait for content after second click
        try:
            await page.wait_for_function(
                "document.querySelector('#desktop-item-detail').innerText !== 'Select a post to read'",
                timeout=2000
            )
            second_click_time = time.time() - start_time
            detail_after_second = await page.locator("#desktop-item-detail").inner_text()
            print(f"✓ SECOND CLICK SUCCESS: Content loaded in {second_click_time:.2f}s")
            print(f"  Content preview: {detail_after_second[:100]}...")
            print("\n❌ CONCLUSION: Desktop requires double-click - this is the bug!")
            
        except Exception as e:
            second_click_time = time.time() - start_time
            print(f"❌ SECOND CLICK ALSO FAIL: No content after {second_click_time:.2f}s")
            print("❌ CONCLUSION: Desktop article loading completely broken!")
        
        await browser.close()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_desktop_article_loading())
    exit(0 if success else 1)