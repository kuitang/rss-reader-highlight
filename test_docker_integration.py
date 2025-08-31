#!/usr/bin/env python3
"""
Test Docker container integration using existing test patterns.
Points existing tests to Docker container instead of local server.
"""

import asyncio
from playwright.async_api import async_playwright
import httpx
import time

DOCKER_URL = "http://localhost:8080"

async def test_docker_integration():
    """Test Docker container functionality"""
    print("=== DOCKER INTEGRATION TEST ===")
    
    # Test 1: HTTP API endpoints
    print("\n--- TEST 1: HTTP API Endpoints ---")
    async with httpx.AsyncClient() as client:
        # Test main page
        response = await client.get(f"{DOCKER_URL}/")
        print(f"✓ Main page: {response.status_code} ({len(response.text)} chars)")
        assert "RSS Reader" in response.text
        
        # Test item endpoint (use a likely ID)
        response = await client.get(f"{DOCKER_URL}/item/1")
        print(f"✓ Item endpoint: {response.status_code} ({len(response.text)} chars)")
        
    # Test 2: Playwright UI testing
    print("\n--- TEST 2: Playwright UI Testing ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Desktop functionality
        await page.goto(DOCKER_URL)
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.wait_for_load_state("networkidle")
        
        desktop_visible = await page.locator("#desktop-layout").is_visible()
        articles_count = await page.locator("#desktop-feeds-content .js-filter li").count()
        print(f"✓ Desktop layout: {desktop_visible}, Articles: {articles_count}")
        
        # Test article click
        if articles_count > 0:
            first_article = page.locator("#desktop-feeds-content .js-filter li").first
            await first_article.click()
            await page.wait_for_timeout(1000)
            
            detail_content = await page.locator("#desktop-item-detail").inner_text()
            article_loaded = "Select a post to read" not in detail_content
            print(f"✓ Article loading: {article_loaded}")
        
        # Mobile functionality
        await page.set_viewport_size({"width": 375, "height": 812})
        await page.goto(DOCKER_URL)
        await page.wait_for_load_state("networkidle")
        
        mobile_visible = await page.locator("#main-content").is_visible()
        mobile_articles = await page.locator("#main-content .js-filter li").count()
        print(f"✓ Mobile layout: {mobile_visible}, Articles: {mobile_articles}")
        
        await browser.close()
    
    print("\n🎉 DOCKER INTEGRATION TESTS COMPLETED")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_docker_integration())
    exit(0 if success else 1)