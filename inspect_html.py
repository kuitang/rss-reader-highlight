#!/usr/bin/env python3
"""
Script to inspect HTML structure of the RSS reader application
"""
import os
import sys
import time
import socket
import subprocess
from playwright.sync_api import sync_playwright

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def start_test_server():
    """Start the server in MINIMAL_MODE"""
    port = get_free_port()
    server_url = f"http://localhost:{port}"
    
    # Start server process with MINIMAL_MODE
    env = os.environ.copy()
    env.update({
        'MINIMAL_MODE': 'true',
        'PORT': str(port)
    })
    
    server_process = subprocess.Popen([
        'python', 'app.py'
    ], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd())
    
    # Wait for server to start
    for _ in range(30):  # 30 seconds timeout
        try:
            import httpx
            response = httpx.get(server_url, timeout=2)
            if response.status_code == 200:
                break
        except httpx.RequestError:
            time.sleep(1)
    else:
        server_process.terminate()
        raise Exception(f"Failed to start test server on {server_url}")
    
    return server_process, server_url

def inspect_html_structure():
    """Launch browser and inspect HTML structure"""
    server_process = None
    
    try:
        # Start server
        print("Starting test server...")
        server_process, server_url = start_test_server()
        print(f"Server running at {server_url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # Make it visible
            
            # Test both desktop and mobile layouts
            viewports = [
                {"name": "desktop", "width": 1200, "height": 800},
                {"name": "mobile", "width": 375, "height": 667}
            ]
            
            for viewport in viewports:
                print(f"\n=== INSPECTING {viewport['name'].upper()} LAYOUT ===")
                
                context = browser.new_context(
                    viewport={'width': viewport['width'], 'height': viewport['height']}
                )
                page = context.new_page()
                
                # Navigate to the application
                page.goto(server_url)
                page.wait_for_load_state("networkidle")
                
                # Take screenshot
                screenshot_path = f"/home/kuitang/git/rss-reader-highlight/{viewport['name']}_layout.png"
                page.screenshot(path=screenshot_path)
                print(f"Screenshot saved: {screenshot_path}")
                
                # Get HTML structure
                html_content = page.content()
                html_path = f"/home/kuitang/git/rss-reader-highlight/{viewport['name']}_structure.html"
                with open(html_path, 'w') as f:
                    f.write(html_content)
                print(f"HTML structure saved: {html_path}")
                
                # Extract key selectors
                print(f"\n{viewport['name'].upper()} Key Elements:")
                
                # Layout containers
                desktop_layout = page.locator("#desktop-layout")
                mobile_layout = page.locator("#mobile-layout")
                
                if desktop_layout.is_visible():
                    print("✓ #desktop-layout is visible")
                    
                    # Desktop sidebar elements
                    sidebar = page.locator("#sidebar")
                    if sidebar.is_visible():
                        print("✓ #sidebar is visible")
                        
                        # Feed links in sidebar
                        feed_links = page.locator("#sidebar a[href*='feed_id']")
                        print(f"  Feed links in sidebar: {feed_links.count()}")
                        
                        # Add feed form elements
                        url_input = page.locator('#sidebar input[name="new_feed_url"]')
                        add_button = page.locator('#sidebar button.add-feed-button')
                        print(f"  URL input found: {url_input.is_visible()}")
                        print(f"  Add button found: {add_button.is_visible()}")
                    
                    # Middle content panel
                    feeds_content = page.locator("#desktop-feeds-content")
                    if feeds_content.is_visible():
                        print("✓ #desktop-feeds-content is visible")
                        
                        # Tab navigation
                        tabs = page.locator('.uk-tab-alt')
                        if tabs.count() > 0:
                            print(f"  Tab containers found: {tabs.count()}")
                            all_posts = page.locator('#desktop-feeds-content a:has-text("All Posts")')
                            unread = page.locator('#desktop-feeds-content a:has-text("Unread")')
                            print(f"  'All Posts' tab found: {all_posts.count() > 0}")
                            print(f"  'Unread' tab found: {unread.count() > 0}")
                        
                        # Article items
                        desktop_articles = page.locator("li[id^='desktop-feed-item-']")
                        print(f"  Desktop articles found: {desktop_articles.count()}")
                    
                    # Detail panel
                    item_detail = page.locator("#desktop-item-detail")
                    if item_detail.is_visible():
                        print("✓ #desktop-item-detail is visible")
                
                if mobile_layout.is_visible():
                    print("✓ #mobile-layout is visible")
                    
                    # Mobile nav button
                    mobile_nav = page.locator('#mobile-nav-button')
                    if mobile_nav.is_visible():
                        print("✓ #mobile-nav-button is visible")
                    
                    # Mobile sidebar
                    mobile_sidebar = page.locator('#mobile-sidebar')
                    print(f"  Mobile sidebar exists: {mobile_sidebar.count() > 0}")
                    
                    # Mobile main content
                    main_content = page.locator("#main-content")
                    if main_content.is_visible():
                        print("✓ #main-content is visible")
                        
                        # Mobile articles
                        mobile_articles = page.locator("li[id^='mobile-feed-item-']")
                        print(f"  Mobile articles found: {mobile_articles.count()}")
                    
                    # Mobile persistent header
                    mobile_header = page.locator('#mobile-persistent-header')
                    if mobile_header.count() > 0:
                        print("✓ #mobile-persistent-header exists")
                        if mobile_header.is_visible():
                            print("  (visible)")
                        else:
                            print("  (hidden)")
                
                # Check for blue indicators (unread items)
                blue_dots = page.locator(".bg-blue-600")
                print(f"  Blue indicator dots found: {blue_dots.count()}")
                
                context.close()
                time.sleep(2)  # Brief pause between viewports
            
            browser.close()
            print("\n=== INSPECTION COMPLETE ===")
            print("Check the generated screenshots and HTML files for structure details")
            
    finally:
        if server_process:
            server_process.terminate()
            server_process.wait()

if __name__ == "__main__":
    inspect_html_structure()