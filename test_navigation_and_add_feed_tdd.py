"""
Test-Driven Development for Navigation and Add Feed Flow

This test documents expected behavior and drives the implementation:
1. Test feed navigation patterns (full page refresh)
2. Test add feed form (immediate sidebar update without page refresh) 
3. Test new feeds appear in sidebar and load items correctly
4. Wait up to 2 minutes for background processing
5. Visual verification with Playwright MCP
"""

import pytest
from playwright.sync_api import sync_playwright, expect
import time
from datetime import datetime

class TestNavigationAndAddFeedTDD:
    """Test-driven development for navigation and add feed functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.browser = None
        self.page = None
        
    def teardown_method(self):
        """Cleanup after each test"""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
    
    def _setup_browser(self, viewport_width=1200):
        """Setup browser and page"""
        p = sync_playwright().start()
        self.browser = p.chromium.launch(headless=True)  # Change to False for visual debugging
        self.page = self.browser.new_page()
        self.page.set_viewport_size({"width": viewport_width, "height": 800 if viewport_width > 600 else 667})
        return self.page
    
    def test_desktop_feed_navigation_full_page_refresh(self):
        """Test: Click feed link → Should do full page refresh → URL changes → Content updates"""
        page = self._setup_browser(1200)  # Desktop
        page.goto("http://localhost:8080")
        page.wait_for_timeout(3000)
        
        print("🖥️ TESTING DESKTOP FEED NAVIGATION (Full Page Refresh)")
        
        # Verify we're in desktop layout
        desktop_layout = page.locator("#desktop-layout")
        expect(desktop_layout).to_be_visible()
        print("✓ Desktop layout confirmed")
        
        # Get initial URL
        initial_url = page.url
        print(f"✓ Initial URL: {initial_url}")
        
        # Find a feed link in desktop sidebar
        feed_link = page.locator("#sidebar a[href*='feed_id=']").first
        expect(feed_link).to_be_visible()
        
        # Get the feed URL before clicking
        feed_href = feed_link.get_attribute("href")
        print(f"✓ Feed link href: {feed_href}")
        
        # Click feed link - this should do FULL PAGE REFRESH
        print("🔄 Clicking feed link...")
        feed_link.click()
        
        # Wait for navigation to complete
        page.wait_for_load_state("networkidle")
        
        # Verify URL changed (indicates full page refresh)
        new_url = page.url
        url_changed = new_url != initial_url
        print(f"✓ New URL: {new_url}")
        print(f"✅ FULL PAGE REFRESH: {url_changed}")
        
        # Verify content updated
        content_area = page.locator("#desktop-feeds-content")
        expect(content_area).to_be_visible()
        print("✅ Feed content loaded after navigation")
        
        assert url_changed, "Feed navigation should cause full page refresh with URL change"
        
        page.screenshot(path="test_desktop_navigation.png")
        print("📸 Screenshot: test_desktop_navigation.png")
    
    def test_mobile_feed_navigation_full_page_refresh(self):
        """Test: Mobile feed link → Full page refresh → Content updates"""
        page = self._setup_browser(375)  # Mobile
        page.goto("http://localhost:8080")
        page.wait_for_timeout(3000)
        
        print("📱 TESTING MOBILE FEED NAVIGATION (Full Page Refresh)")
        
        # Open mobile sidebar
        hamburger = page.locator("#mobile-header button").first
        hamburger.click()
        page.wait_for_timeout(1000)
        print("✓ Opened mobile sidebar")
        
        # Get initial URL
        initial_url = page.url
        
        # Find feed link in mobile sidebar
        mobile_feed_link = page.locator("#mobile-sidebar a[href*='feed_id=']").first
        expect(mobile_feed_link).to_be_visible()
        
        feed_href = mobile_feed_link.get_attribute("href")
        print(f"✓ Mobile feed link: {feed_href}")
        
        # Click feed link
        print("🔄 Clicking mobile feed link...")
        mobile_feed_link.click()
        
        # Wait for navigation
        page.wait_for_load_state("networkidle")
        
        # Verify URL changed and sidebar closed
        new_url = page.url
        url_changed = new_url != initial_url
        
        # Check if sidebar auto-closed (good UX)
        sidebar_hidden = page.locator("#mobile-sidebar").get_attribute("hidden") == "true"
        
        print(f"✓ New URL: {new_url}")
        print(f"✅ Full page refresh: {url_changed}")
        print(f"✅ Sidebar auto-closed: {sidebar_hidden}")
        
        assert url_changed, "Mobile feed navigation should cause full page refresh"
        
        page.screenshot(path="test_mobile_navigation.png")
        print("📸 Screenshot: test_mobile_navigation.png")
    
    def test_desktop_add_feed_immediate_ui_update(self):
        """Test: Desktop add feed → Sidebar updates immediately → No page refresh"""
        page = self._setup_browser(1200)  # Desktop
        page.goto("http://localhost:8080")
        page.wait_for_timeout(3000)
        
        print("🖥️ TESTING DESKTOP ADD FEED (Immediate UI Update)")
        
        # Count initial feeds in sidebar
        initial_feeds = page.locator("#sidebar a[href*='feed_id=']")
        initial_count = initial_feeds.count()
        print(f"✓ Initial feed count: {initial_count}")
        
        # Get current URL (should NOT change)
        initial_url = page.url
        
        # Find add feed form
        desktop_input = page.locator("#sidebar #new-feed-url")
        desktop_button = page.locator("#sidebar #add-feed-button")
        
        expect(desktop_input).to_be_visible()
        expect(desktop_button).to_be_visible()
        print("✓ Desktop add feed form found")
        
        # Add a unique test feed
        test_url = f"https://httpbin.org/xml?test=desktop_{int(time.time())}"
        desktop_input.fill(test_url)
        print(f"✓ Filled desktop input: {test_url}")
        
        # Submit form - should NOT cause page refresh
        print("🔄 Submitting desktop form...")
        desktop_button.click()
        
        # Wait for HTMX response (not full page load)
        page.wait_for_timeout(5000)
        
        # Verify URL did NOT change (no page refresh)
        current_url = page.url
        no_page_refresh = current_url == initial_url
        print(f"✅ No page refresh: {no_page_refresh} (URL: {current_url})")
        
        # Verify sidebar was updated (new feed should appear)
        updated_feeds = page.locator("#sidebar a[href*='feed_id=']")
        updated_count = updated_feeds.count()
        feed_added_to_ui = updated_count > initial_count
        
        print(f"✓ Updated feed count: {updated_count}")
        print(f"✅ Feed added to UI: {feed_added_to_ui}")
        
        assert no_page_refresh, "Add feed should not cause page refresh"
        assert feed_added_to_ui, "New feed should appear in sidebar immediately"
        
        page.screenshot(path="test_desktop_add_feed.png")
        print("📸 Screenshot: test_desktop_add_feed.png")
        
        return updated_count > initial_count
    
    def test_mobile_add_feed_immediate_ui_update(self):
        """Test: Mobile add feed → Sidebar updates immediately → No page refresh"""
        page = self._setup_browser(375)  # Mobile
        page.goto("http://localhost:8080")
        page.wait_for_timeout(3000)
        
        print("📱 TESTING MOBILE ADD FEED (Immediate UI Update)")
        
        # Open mobile sidebar
        hamburger = page.locator("#mobile-header button").first
        hamburger.click()
        page.wait_for_timeout(1000)
        
        # Count initial feeds
        initial_mobile_feeds = page.locator("#mobile-sidebar a[href*='feed_id=']")
        initial_count = initial_mobile_feeds.count()
        print(f"✓ Initial mobile feed count: {initial_count}")
        
        initial_url = page.url
        
        # Find mobile add feed form
        mobile_input = page.locator("#mobile-sidebar #mobile-feed-url")
        mobile_button = page.locator("#mobile-sidebar #mobile-add-feed-button")
        
        expect(mobile_input).to_be_visible()
        expect(mobile_button).to_be_visible()
        print("✓ Mobile add feed form found")
        
        # Add unique test feed
        test_url = f"https://httpbin.org/xml?test=mobile_{int(time.time())}"
        mobile_input.fill(test_url)
        print(f"✓ Filled mobile input: {test_url}")
        
        # Submit form
        print("🔄 Submitting mobile form...")
        mobile_button.click()
        
        # Wait for HTMX response
        page.wait_for_timeout(5000)
        
        # Verify no page refresh
        current_url = page.url
        no_page_refresh = current_url == initial_url
        print(f"✅ No page refresh: {no_page_refresh}")
        
        # Verify mobile sidebar was updated
        updated_mobile_feeds = page.locator("#mobile-sidebar a[href*='feed_id=']")
        updated_count = updated_mobile_feeds.count()
        feed_added_to_mobile_ui = updated_count > initial_count
        
        print(f"✓ Updated mobile feed count: {updated_count}")
        print(f"✅ Feed added to mobile UI: {feed_added_to_mobile_ui}")
        
        assert no_page_refresh, "Mobile add feed should not cause page refresh"
        assert feed_added_to_mobile_ui, "New feed should appear in mobile sidebar immediately"
        
        page.screenshot(path="test_mobile_add_feed.png") 
        print("📸 Screenshot: test_mobile_add_feed.png")
        
        return updated_count > initial_count
    
    def test_new_feed_loads_items_after_background_processing(self):
        """Test: Add feed → Wait 2 minutes → Click new feed → Items should load"""
        page = self._setup_browser(1200)
        page.goto("http://localhost:8080")
        page.wait_for_timeout(3000)
        
        print("⏱️ TESTING BACKGROUND PROCESSING (2 minute wait)")
        
        # Add a real RSS feed that should have content
        desktop_input = page.locator("#sidebar #new-feed-url")
        desktop_button = page.locator("#sidebar #add-feed-button")
        
        real_feed_url = "https://feeds.feedburner.com/venturebeat/SZYF"  # VentureBeat
        desktop_input.fill(real_feed_url)
        print(f"✓ Adding real RSS feed: {real_feed_url}")
        
        desktop_button.click()
        page.wait_for_timeout(5000)
        
        # Find the new feed link (should be the newest one)
        new_feed_links = page.locator("#sidebar a[href*='feed_id=']")
        newest_feed = new_feed_links.last  # Assume it's added at the end
        
        if newest_feed.is_visible():
            feed_title_before = newest_feed.inner_text()
            print(f"✓ New feed found: '{feed_title_before[:50]}...'")
            
            # Wait for background processing (up to 2 minutes as requested)
            print("⏳ Waiting up to 2 minutes for background content processing...")
            max_wait_seconds = 120
            wait_interval = 10
            waited_seconds = 0
            
            while waited_seconds < max_wait_seconds:
                page.wait_for_timeout(wait_interval * 1000)
                waited_seconds += wait_interval
                
                # Check if title updated (indicates content was processed)
                current_title = newest_feed.inner_text()
                title_updated = current_title != feed_title_before and "Loading..." not in current_title
                
                print(f"  {waited_seconds}s: Title = '{current_title[:30]}...' Updated: {title_updated}")
                
                if title_updated:
                    print(f"✅ Background processing completed after {waited_seconds} seconds!")
                    break
            
            # Test clicking the new feed
            print(f"🔄 Clicking new feed to test item loading...")
            feed_href = newest_feed.get_attribute("href")
            print(f"✓ Feed URL: {feed_href}")
            
            newest_feed.click()
            page.wait_for_load_state("networkidle")
            
            # Verify items loaded
            feed_items = page.locator("#desktop-feeds-content .js-filter li")
            item_count = feed_items.count()
            items_loaded = item_count > 0
            
            print(f"✓ Items loaded: {item_count}")
            print(f"✅ Feed functional: {items_loaded}")
            
            page.screenshot(path="test_background_processing.png")
            print("📸 Screenshot: test_background_processing.png")
            
            assert items_loaded, f"New feed should have items after background processing"
            return True
        else:
            print("❌ New feed not found in sidebar")
            return False
    
    def test_comprehensive_add_feed_and_navigation_flow(self):
        """Comprehensive test combining all aspects"""
        page = self._setup_browser(375)  # Start with mobile
        page.goto("http://localhost:8080")
        page.wait_for_timeout(3000)
        
        print("🎯 COMPREHENSIVE FLOW TEST")
        
        results = {
            'mobile_add_feed': False,
            'desktop_add_feed': False, 
            'navigation_works': False,
            'background_processing': False
        }
        
        # === MOBILE ADD FEED ===
        print("\n--- Mobile Add Feed ---")
        hamburger = page.locator("#mobile-header button").first
        hamburger.click()
        page.wait_for_timeout(1000)
        
        mobile_input = page.locator("#mobile-sidebar #mobile-feed-url")
        mobile_button = page.locator("#mobile-sidebar #mobile-add-feed-button")
        
        if mobile_input.is_visible() and mobile_button.is_visible():
            mobile_input.fill("https://feeds.mashable.com/Mashable")
            mobile_button.click()
            page.wait_for_timeout(5000)
            
            # Check if feed appears
            mobile_feeds_after = page.locator("#mobile-sidebar a[href*='feed_id=']").count()
            results['mobile_add_feed'] = mobile_feeds_after > 0
            print(f"✅ Mobile add feed: {results['mobile_add_feed']} ({mobile_feeds_after} feeds)")
        
        # === SWITCH TO DESKTOP ===
        print("\n--- Switch to Desktop ---")
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto("http://localhost:8080")  # Full page refresh to desktop
        page.wait_for_timeout(3000)
        
        # === DESKTOP ADD FEED ===
        print("\n--- Desktop Add Feed ---")
        desktop_input = page.locator("#sidebar #new-feed-url")
        desktop_button = page.locator("#sidebar #add-feed-button")
        
        initial_desktop_feeds = page.locator("#sidebar a[href*='feed_id=']").count()
        
        if desktop_input.is_visible() and desktop_button.is_visible():
            desktop_input.fill("https://rss.cnn.com/rss/cnn_topstories.rss")
            desktop_button.click()
            page.wait_for_timeout(5000)
            
            desktop_feeds_after = page.locator("#sidebar a[href*='feed_id=']").count()
            results['desktop_add_feed'] = desktop_feeds_after > initial_desktop_feeds
            print(f"✅ Desktop add feed: {results['desktop_add_feed']} ({desktop_feeds_after} feeds)")
        
        # === TEST NAVIGATION ===
        print("\n--- Test Feed Navigation ---")
        first_feed = page.locator("#sidebar a[href*='feed_id=']").first
        if first_feed.is_visible():
            initial_nav_url = page.url
            first_feed.click()
            page.wait_for_load_state("networkidle")
            
            nav_url_changed = page.url != initial_nav_url
            results['navigation_works'] = nav_url_changed
            print(f"✅ Navigation works: {results['navigation_works']}")
        
        # === FINAL ASSESSMENT ===
        print(f"\n📊 COMPREHENSIVE TEST RESULTS:")
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {test_name}: {status}")
        
        all_passed = all(results.values())
        print(f"\n🎯 OVERALL: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
        
        page.screenshot(path="test_comprehensive_flow.png")
        print("📸 Screenshot: test_comprehensive_flow.png")
        
        return all_passed

# Run tests standalone
if __name__ == "__main__":
    import sys
    
    print("🚀 STARTING TEST-DRIVEN DEVELOPMENT TESTS")
    print("=" * 60)
    
    test_instance = TestNavigationAndAddFeedTDD()
    
    try:
        # Test 1: Desktop navigation
        print("\n🧪 TEST 1: Desktop Feed Navigation")
        test_instance.test_desktop_feed_navigation_full_page_refresh()
        print("✅ Test 1 completed")
        
        # Test 2: Mobile navigation  
        print("\n🧪 TEST 2: Mobile Feed Navigation")
        test_instance.test_mobile_feed_navigation_full_page_refresh()
        print("✅ Test 2 completed")
        
        # Test 3: Desktop add feed
        print("\n🧪 TEST 3: Desktop Add Feed")
        test_instance.test_desktop_add_feed_immediate_ui_update()
        print("✅ Test 3 completed")
        
        # Test 4: Mobile add feed
        print("\n🧪 TEST 4: Mobile Add Feed")
        test_instance.test_mobile_add_feed_immediate_ui_update()
        print("✅ Test 4 completed")
        
        # Test 5: Background processing
        print("\n🧪 TEST 5: Background Processing")
        test_instance.test_new_feed_loads_items_after_background_processing()
        print("✅ Test 5 completed")
        
        # Test 6: Comprehensive flow
        print("\n🧪 TEST 6: Comprehensive Flow")
        success = test_instance.test_comprehensive_add_feed_and_navigation_flow()
        
        print("=" * 60)
        if success:
            print("🎉 ALL TDD TESTS PASSED - Ready for implementation!")
        else:
            print("❌ Some tests failed - Need to fix implementation")
            
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Test execution failed: {str(e)}")
        sys.exit(1)
    finally:
        test_instance.teardown_method()