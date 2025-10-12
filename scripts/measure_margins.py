#!/usr/bin/env python3
"""Compare margins and spacing between localhost and production"""

from playwright.sync_api import sync_playwright
import json

def measure_site(url, name):
    """Measure all margins and spacing on a site"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        measurements = {}

        # Test both desktop and mobile viewports
        for viewport_name, viewport in [
            ("desktop", {"width": 1400, "height": 900}),
            ("mobile", {"width": 390, "height": 844})
        ]:
            page = browser.new_page(viewport=viewport)
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for content to load - try multiple selectors
            try:
                page.wait_for_selector("#main-layout", state="visible", timeout=10000)
            except:
                try:
                    page.wait_for_selector("#content-area", state="visible", timeout=10000)
                except:
                    page.wait_for_selector("body", state="visible", timeout=10000)

            # Measure all spacing and get class names
            spacing = page.evaluate("""() => {
                const measurements = {};

                // Chrome container
                const chrome = document.getElementById('chrome-container');
                if (chrome) {
                    const chromeStyles = window.getComputedStyle(chrome);
                    measurements.chrome = {
                        className: chrome.className,
                        paddingTop: chromeStyles.paddingTop,
                        paddingBottom: chromeStyles.paddingBottom,
                        paddingLeft: chromeStyles.paddingLeft,
                        paddingRight: chromeStyles.paddingRight,
                        height: chromeStyles.height,
                        borderBottom: chromeStyles.borderBottomWidth
                    };
                }

                // Sidebar
                const sidebar = document.getElementById('sidebar');
                if (sidebar) {
                    const sidebarStyles = window.getComputedStyle(sidebar);
                    measurements.sidebar = {
                        className: sidebar.className,
                        paddingTop: sidebarStyles.paddingTop,
                        paddingBottom: sidebarStyles.paddingBottom,
                        paddingLeft: sidebarStyles.paddingLeft,
                        paddingRight: sidebarStyles.paddingRight,
                        width: sidebarStyles.width
                    };
                }

                // Content area
                const contentArea = document.getElementById('content-area');
                if (contentArea) {
                    const contentStyles = window.getComputedStyle(contentArea);
                    measurements.contentArea = {
                        className: contentArea.className,
                        paddingTop: contentStyles.paddingTop,
                        paddingBottom: contentStyles.paddingBottom,
                        paddingLeft: contentStyles.paddingLeft,
                        paddingRight: contentStyles.paddingRight,
                        gap: contentStyles.gap
                    };
                }

                // Feed list
                const feedList = document.getElementById('feed-list');
                if (feedList) {
                    const feedListStyles = window.getComputedStyle(feedList);
                    measurements.feedList = {
                        className: feedList.className,
                        paddingTop: feedListStyles.paddingTop,
                        paddingBottom: feedListStyles.paddingBottom,
                        paddingLeft: feedListStyles.paddingLeft,
                        paddingRight: feedListStyles.paddingRight
                    };
                }

                // Article detail
                const articleDetail = document.getElementById('article-detail');
                if (articleDetail) {
                    const articleStyles = window.getComputedStyle(articleDetail);
                    measurements.articleDetail = {
                        className: articleDetail.className,
                        paddingTop: articleStyles.paddingTop,
                        paddingBottom: articleStyles.paddingBottom,
                        paddingLeft: articleStyles.paddingLeft,
                        paddingRight: articleStyles.paddingRight
                    };
                }

                // Main layout
                const mainLayout = document.getElementById('main-layout');
                if (mainLayout) {
                    const mainStyles = window.getComputedStyle(mainLayout);
                    measurements.mainLayout = {
                        className: mainLayout.className,
                        gap: mainStyles.gap,
                        gridTemplateColumns: mainStyles.gridTemplateColumns,
                        gridTemplateRows: mainStyles.gridTemplateRows
                    };
                }

                return measurements;
            }""")

            measurements[viewport_name] = spacing
            page.close()

        browser.close()
        return measurements

def compare_measurements(localhost, production):
    """Compare measurements and show differences"""
    print("\n" + "="*80)
    print("MARGIN & SPACING COMPARISON")
    print("="*80)

    for viewport in ["desktop", "mobile"]:
        print(f"\n{'─'*80}")
        print(f"📱 {viewport.upper()} VIEWPORT")
        print(f"{'─'*80}")

        local = localhost.get(viewport, {})
        prod = production.get(viewport, {})

        for element in local.keys():
            print(f"\n🔍 {element.upper()}")
            print(f"{'─'*40}")

            local_elem = local.get(element, {})
            prod_elem = prod.get(element, {})

            # Compare each property
            all_props = set(local_elem.keys()) | set(prod_elem.keys())

            for prop in sorted(all_props):
                local_val = local_elem.get(prop, "N/A")
                prod_val = prod_elem.get(prop, "N/A")

                if local_val != prod_val:
                    print(f"  ❌ {prop:20s} | Local: {local_val:15s} | Prod: {prod_val:15s}")
                else:
                    print(f"  ✅ {prop:20s} | {local_val}")

    print("\n" + "="*80)
    print("SUMMARY OF DIFFERENCES")
    print("="*80)

    differences = []
    for viewport in ["desktop", "mobile"]:
        local = localhost.get(viewport, {})
        prod = production.get(viewport, {})

        for element in local.keys():
            local_elem = local.get(element, {})
            prod_elem = prod.get(element, {})

            for prop in local_elem.keys():
                local_val = local_elem.get(prop, "N/A")
                prod_val = prod_elem.get(prop, "N/A")

                if local_val != prod_val:
                    differences.append({
                        "viewport": viewport,
                        "element": element,
                        "property": prop,
                        "localhost": local_val,
                        "production": prod_val
                    })

    if differences:
        print("\n🔴 DIFFERENCES FOUND:")
        for diff in differences:
            print(f"  • [{diff['viewport']}] {diff['element']}.{diff['property']}")
            print(f"    Local: {diff['localhost']} → Prod: {diff['production']}")
    else:
        print("\n✅ No differences found!")

    return differences

if __name__ == "__main__":
    print("Measuring localhost...")
    localhost = measure_site("http://localhost:8080", "localhost")

    print("Measuring production...")
    production = measure_site("https://rss-reader-highlight.fly.dev", "production")

    # Save measurements
    with open("measurements.json", "w") as f:
        json.dump({
            "localhost": localhost,
            "production": production
        }, f, indent=2)

    print("\n💾 Measurements saved to measurements.json")

    # Compare
    differences = compare_measurements(localhost, production)

    print(f"\n📊 Total differences: {len(differences)}")
