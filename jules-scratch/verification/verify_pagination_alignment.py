from playwright.sync_api import sync_playwright, expect, Page

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Set a desktop viewport
        page.set_viewport_size({"width": 1280, "height": 720})
        page.goto("http://localhost:8080")

        # Wait for the pagination container to be visible
        pagination_container = page.locator("#desktop-feeds-content .p-4.border-t")
        expect(pagination_container).to_be_visible()

        # Take a screenshot of the pagination container
        pagination_container.screenshot(path="jules-scratch/verification/pagination_alignment.png")

        browser.close()

if __name__ == "__main__":
    main()
