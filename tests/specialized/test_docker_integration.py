#!/usr/bin/env python3
"""
Test Docker container integration using existing test patterns.
This test verifies the application works correctly when run in a Docker container.
"""

import pytest
from playwright.sync_api import sync_playwright
import httpx
import time
import subprocess
import os
import socket

def get_free_port():
    """Find an available port on the system"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

# HTMX Helper Functions for Fast Testing  
def wait_for_htmx_complete(page, timeout=5000):
    """Wait for all HTMX requests to complete - much faster than fixed timeouts"""
    page.wait_for_function("() => !document.body.classList.contains('htmx-request')", timeout=timeout)

@pytest.fixture(scope="module")
def docker_container():
    """Start a Docker container for testing"""
    # Get a random free port
    host_port = get_free_port()
    docker_url = f"http://localhost:{host_port}"
    print(f"Using random port {host_port} for Docker container")
    
    # Build the Docker image
    print("Building Docker image...")
    build_result = subprocess.run(
        ['docker', 'build', '-t', 'rss-reader-test', '.'],
        capture_output=True,
        text=True
    )
    assert build_result.returncode == 0, f"Docker build failed: {build_result.stderr}"
    
    # Start the container
    print("Starting Docker container...")
    container_result = subprocess.run(
        ['docker', 'run', '-d', '--rm', '-p', f'{host_port}:8080', '--name', 'rss-reader-test-container', 'rss-reader-test'],
        capture_output=True,
        text=True
    )
    assert container_result.returncode == 0, f"Docker run failed: {container_result.stderr}"
    container_id = container_result.stdout.strip()
    
    # Wait for container to be ready
    print("Waiting for container to be ready...")
    for i in range(30):
        try:
            response = httpx.get(docker_url, timeout=1)
            if response.status_code == 200:
                print("Container is ready!")
                break
        except httpx.RequestError:
            pass
        time.sleep(1)
    else:
        # Clean up if startup failed
        subprocess.run(['docker', 'stop', 'rss-reader-test-container'], capture_output=True)
        pytest.fail("Docker container failed to start within 30 seconds")
    
    yield {"container_id": container_id, "url": docker_url}
    
    # Cleanup
    print("Stopping Docker container...")
    subprocess.run(['docker', 'stop', 'rss-reader-test-container'], capture_output=True)

def test_docker_integration(docker_container):
    """Test Docker container functionality"""
    print("=== DOCKER INTEGRATION TEST ===")
    
    docker_url = docker_container["url"]
    print(f"Testing container at {docker_url}")
    
    # Test 1: HTTP API endpoints
    print("\n--- TEST 1: HTTP API Endpoints ---")
    with httpx.Client() as client:
        # Test main page
        response = client.get(f"{docker_url}/")
        print(f"✓ Main page: {response.status_code} ({len(response.text)} chars)")
        # Check for actual content - feed names or "All Feeds" title
        assert "All Feeds" in response.text or "Bloomberg" in response.text, \
            f"Expected feed content in page, got: {response.text[:500]}"
        
        # Test item endpoint (use a likely ID)
        response = client.get(f"{docker_url}/item/1")
        print(f"✓ Item endpoint: {response.status_code} ({len(response.text)} chars)")
        
    # Test 2: Playwright UI testing (sync API)
    print("\n--- TEST 2: Playwright UI Testing ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Desktop functionality
        page.goto(docker_url)
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.wait_for_load_state("networkidle")
        
        desktop_visible = page.locator("#desktop-layout").is_visible()
        articles_count = page.locator("#desktop-feeds-content .js-filter li").count()
        print(f"✓ Desktop layout: {desktop_visible}, Articles: {articles_count}")
        
        # Test article click
        if articles_count > 0:
            first_article = page.locator("#desktop-feeds-content .js-filter li").first
            first_article.click()
            wait_for_htmx_complete(page)  # OPTIMIZED: Wait for HTMX response instead of 1 second
            
            detail_content = page.locator("#desktop-item-detail").inner_text()
            article_loaded = "Select a post to read" not in detail_content
            print(f"✓ Article loading: {article_loaded}")
        
        # Mobile functionality
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(docker_url)
        page.wait_for_load_state("networkidle")
        
        mobile_visible = page.locator("#main-content").is_visible()
        mobile_articles = page.locator("#main-content .js-filter li").count()
        print(f"✓ Mobile layout: {mobile_visible}, Articles: {mobile_articles}")
        
        browser.close()
    
    print("\n🎉 DOCKER INTEGRATION TESTS COMPLETED")

def test_docker_static_files(docker_container):
    """Test that static files (JS/CSS) are included in Docker image and accessible

    REGRESSION TEST: This prevents the bug where Dockerfile didn't copy static/
    directory, causing all JavaScript to return 404 in production/preview.
    """
    print("=== DOCKER STATIC FILES TEST ===")

    docker_url = docker_container["url"]
    print(f"Testing static files at {docker_url}")

    with httpx.Client() as client:
        # Test 1: JavaScript files exist and are accessible
        print("\n--- TEST 1: JavaScript Files ---")
        js_files = [
            '/static/js/main.js',
            '/static/js/htmx-config.js'
        ]

        for js_file in js_files:
            response = client.get(f"{docker_url}{js_file}")
            assert response.status_code == 200, \
                f"❌ {js_file} returned {response.status_code} (expected 200). " \
                f"Dockerfile may be missing 'COPY static/ ./static/'"

            content_length = len(response.text)
            assert content_length > 100, \
                f"❌ {js_file} is too small ({content_length} bytes). File may be empty or corrupted."

            print(f"✓ {js_file}: {response.status_code} ({content_length} bytes)")

        # Test 2: Critical JavaScript functions are defined
        print("\n--- TEST 2: Critical JavaScript Functions ---")
        main_js = client.get(f"{docker_url}/static/js/main.js").text
        htmx_config = client.get(f"{docker_url}/static/js/htmx-config.js").text

        # Check for critical mobile functions
        critical_functions = [
            ('window.showArticle', main_js, 'main.js'),
            ('window.hideArticle', main_js, 'main.js'),
            ('window.toggleSidebar', main_js, 'main.js'),
            ('htmx.on', htmx_config, 'htmx-config.js'),
        ]

        for func_name, content, file_name in critical_functions:
            assert func_name in content, \
                f"❌ {func_name} not found in {file_name}. File may be corrupted or wrong version."
            print(f"✓ {func_name} found in {file_name}")

        # Test 3: CSS files exist
        print("\n--- TEST 3: CSS Files ---")
        response = client.get(f"{docker_url}/static/css/main.css")
        assert response.status_code == 200, \
            f"❌ main.css returned {response.status_code}. Dockerfile may be missing static/ directory."

        css_length = len(response.text)
        assert css_length > 100, \
            f"❌ main.css is too small ({css_length} bytes)"

        print(f"✓ /static/css/main.css: {response.status_code} ({css_length} bytes)")

    # Test 4: Mobile functionality works with JavaScript loaded
    print("\n--- TEST 4: Mobile Article Click (with JS) ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 390, 'height': 844},
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)'
        )
        page = context.new_page()

        page.goto(docker_url, wait_until="load", timeout=10000)
        page.wait_for_load_state('networkidle', timeout=10000)

        # Check that showArticle is defined
        show_article_defined = page.evaluate("typeof window.showArticle === 'function'")
        assert show_article_defined, \
            "❌ window.showArticle is not defined! JavaScript files not loaded."
        print("✓ window.showArticle is defined")

        # Find and click first feed item
        feed_items = page.locator("li[id^='feed-item-']")
        count = feed_items.count()

        if count > 0:
            # Get initial state
            article_hidden_before = page.evaluate(
                "document.getElementById('article-detail')?.classList.contains('hidden')"
            )

            # Click article
            feed_items.first.click()
            page.wait_for_timeout(2000)  # Wait for HTMX + showArticle

            # Check that article is now visible
            article_classes = page.evaluate("document.getElementById('article-detail')?.className")
            article_display = page.evaluate(
                "window.getComputedStyle(document.getElementById('article-detail')).display"
            )

            assert 'block' in article_classes or article_display == 'block', \
                f"❌ Article not visible after click! classList={article_classes}, display={article_display}. " \
                f"JavaScript may not be working correctly."

            print(f"✓ Mobile article click works (hidden before: {article_hidden_before}, visible after: True)")

        browser.close()

    print("\n🎉 DOCKER STATIC FILES TESTS COMPLETED")

if __name__ == "__main__":
    test_docker_integration()