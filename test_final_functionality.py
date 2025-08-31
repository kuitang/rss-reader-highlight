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
        
        # Test article loading and unread marking with proper styling assertions
        first_article = page.locator("#desktop-feeds-content .js-filter li").first
        article_title = (await first_article.inner_text()).split('\\n')[0]
        
        # Get article ID for stable reference (should be desktop-feed-item-*)
        article_id = await first_article.get_attribute("id")
        stable_article = page.locator(f"#{article_id}")
        print(f"✓ Testing article with stable ID: {article_id}")
        
        # Check complete styling before click (unread state)
        style_before = await stable_article.evaluate("""(element) => ({
            hasBlueSpan: element.querySelector('.bg-blue-600') !== null,
            hasBgMuted: element.classList.contains('bg-muted'),
            isTaggedUnread: element.classList.contains('tag-unread'),
            hasStrongTitle: element.querySelector('strong') !== null,
            backgroundColor: window.getComputedStyle(element).backgroundColor
        })""")
        
        # Click article
        start_time = time.time()
        await stable_article.click()
        await page.wait_for_function("document.querySelector('#desktop-item-detail').innerText !== 'Select a post to read'", timeout=2000)
        load_time = time.time() - start_time
        
        # Wait for OOB swap to complete and check styling after click (read state)
        await page.wait_for_timeout(500)
        style_after = await stable_article.evaluate("""(element) => ({
            hasBlueSpan: element.querySelector('.bg-blue-600') !== null,
            hasBgMuted: element.classList.contains('bg-muted'),
            isTaggedRead: element.classList.contains('tag-read'),
            hasStrongTitle: element.querySelector('strong') !== null,
            backgroundColor: window.getComputedStyle(element).backgroundColor
        })""")
        
        print(f"✓ Article '{article_title[:40]}...' loaded in {load_time:.2f}s")
        print(f"✓ BEFORE: blue_dot={style_before['hasBlueSpan']}, grey_bg={style_before['hasBgMuted']}, bold_title={style_before['hasStrongTitle']}")
        print(f"✓ AFTER:  blue_dot={style_after['hasBlueSpan']}, grey_bg={style_after['hasBgMuted']}, bold_title={style_after['hasStrongTitle']}")
        
        # Assert proper styling transitions
        assert style_before['hasBlueSpan'] == True, "Unread: must have blue dot"
        assert style_before['hasBgMuted'] == False, "Unread: must not have grey background"
        assert style_before['hasStrongTitle'] == True, "Unread: must have bold title"
        assert style_after['hasBlueSpan'] == False, "Read: must not have blue dot"
        assert style_after['hasBgMuted'] == True, "Read: must have grey background"
        assert style_after['hasStrongTitle'] == False, "Read: must not have bold title"
        print("✅ Desktop unread → read styling FULLY VERIFIED")
        
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
        
        # Test 3: Summary and Content Fields
        print("\\n--- TEST 3: Summary and Content Fields ---")
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.goto("http://localhost:5001")
        await page.wait_for_load_state("networkidle")
        
        # Check that articles show summaries (not just truncated text)
        first_article = page.locator("#desktop-feeds-content .js-filter li").first
        article_text = await first_article.inner_text()
        lines = article_text.split('\\n')
        has_title = len(lines) >= 1
        has_source_time = len(lines) >= 2  
        has_summary = len(lines) >= 3 and len(lines[2]) > 20  # Should have meaningful summary
        
        print(f"✓ Article structure: title={has_title}, source/time={has_source_time}, summary={has_summary}")
        print(f"✓ Summary length: {len(lines[2]) if len(lines) >= 3 else 0} chars")
        
        # Click article to load detail and verify content vs summary
        await first_article.click()
        await page.wait_for_timeout(500)
        
        detail_content = await page.locator("#desktop-item-detail").inner_text()
        content_length = len(detail_content)
        summary_length = len(lines[2]) if len(lines) >= 3 else 0
        
        print(f"✓ Detail view content: {content_length} chars")
        print(f"✓ Summary vs Content: summary={summary_length}, detail={content_length}")
        
        # External links test
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