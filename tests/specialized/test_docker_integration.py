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
        assert "RSS Reader" in response.text
        
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

if __name__ == "__main__":
    test_docker_integration()