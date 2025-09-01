"""Debug HTMX form submission issues"""

from playwright.sync_api import sync_playwright

def debug_htmx_form():
    """Debug why HTMX form submission isn't working"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Enable console logging to catch HTMX errors
        page.on("console", lambda msg: print(f"CONSOLE: {msg.type} - {msg.text}"))
        
        # Set desktop viewport
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto("http://localhost:8080")
        page.wait_for_timeout(5000)
        
        print("🔍 DEBUGGING HTMX FORM SUBMISSION")
        
        # Test desktop form first (simpler)
        print("=== DESKTOP FORM TEST ===")
        
        desktop_input = page.locator('#sidebar input[id="new-feed-url"]')
        desktop_button = page.locator('#sidebar button[hx-post="/api/feed/add"]')
        
        print(f"Input found: {desktop_input.is_visible()}")
        print(f"Button found: {desktop_button.is_visible()}")
        
        if desktop_input.is_visible() and desktop_button.is_visible():
            # Check HTMX attributes
            include_attr = desktop_button.get_attribute("hx-include")
            target_attr = desktop_button.get_attribute("hx-target")
            post_attr = desktop_button.get_attribute("hx-post")
            
            print(f"hx-include: '{include_attr}'")
            print(f"hx-target: '{target_attr}'")
            print(f"hx-post: '{post_attr}'")
            
            # Check if target element exists
            target_element = page.locator(target_attr) if target_attr else None
            target_exists = target_element.is_visible() if target_element else False
            print(f"Target element exists: {target_exists}")
            
            # Test form submission
            desktop_input.fill("https://example.com/rss")
            print("✓ Filled input with test URL")
            
            # Check input value was set
            input_value = desktop_input.input_value()
            print(f"Input value: '{input_value}'")
            
            # Click button and monitor network
            print("Clicking button...")
            
            # Monitor network requests
            requests = []
            page.on("request", lambda req: requests.append(f"{req.method} {req.url}"))
            page.on("response", lambda resp: print(f"RESPONSE: {resp.status} {resp.url}"))
            
            desktop_button.click()
            page.wait_for_timeout(3000)
            
            print("Network requests made:")
            for req in requests:
                print(f"  {req}")
            
            if not any("/api/feed/add" in req for req in requests):
                print("❌ No POST request to /api/feed/add made")
                print("HTMX form submission is broken")
            else:
                print("✓ POST request to /api/feed/add was made")
        
        print("Browser staying open for inspection...")
        input("Press Enter to close browser...")
        browser.close()

if __name__ == "__main__":
    debug_htmx_form()