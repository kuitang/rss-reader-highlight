"""Shared Playwright fixtures for UI tests with module-level isolation

Each test MODULE (file) gets its own browser instance for isolation when running
files in parallel, but tests within a module share the browser for efficiency.

Server Dependency Management:
- UI tests require a running server (marked with @pytest.mark.needs_server)
- Start server manually: python app.py (or MINIMAL_MODE=true python app.py)
- Server URL standardized through test_server_url fixture
"""

import pytest
import httpx
from test_helpers import wait_for_server_ready
from tenacity import RetryError
import os
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def test_server_url():
    """Auto-start test server or use existing server for UI tests
    
    This fixture automatically starts a test server in minimal mode,
    or uses an existing server if TEST_SERVER_URL is set.
    
    Environment variables:
    - TEST_SERVER_URL: Use existing server (e.g., http://localhost:8080)
    - TEST_AUTO_SERVER: Set to 'false' to disable auto server startup
    """
    import socket
    import subprocess
    import tempfile
    import time
    import atexit
    
    # Check if user wants to use existing server
    existing_server = os.environ.get('TEST_SERVER_URL')
    if existing_server:
        try:
            response = httpx.get(existing_server, timeout=5)
            if response.status_code == 200:
                return existing_server
        except httpx.RequestError:
            pass
    
    # Check if auto server startup is disabled
    if os.environ.get('TEST_AUTO_SERVER', 'true').lower() == 'false':
        pytest.skip("Test server auto-startup disabled. Set TEST_SERVER_URL or start server manually.")
    
    def get_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    
    # Ensure minimal seed database exists for MINIMAL_MODE
    minimal_seed_path = os.path.join('data', 'minimal_seed.db')
    if not os.path.exists(minimal_seed_path):
        pytest.skip(f"Minimal seed database not found at {minimal_seed_path}. Run: python create_minimal_db.py")
    
    # Start test server with minimal mode
    port = get_free_port()
    server_url = f"http://localhost:{port}"
    
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    # Start server process with MINIMAL_MODE
    # Note: MINIMAL_MODE ignores DATABASE_PATH and uses PID-specific database
    env = os.environ.copy()
    env.update({
        'MINIMAL_MODE': 'true',
        'PORT': str(port)
    })
    
    server_process = subprocess.Popen([
        'python', '-m', 'app'
    ], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd())
    
    # Register cleanup function
    def cleanup_server():
        if server_process:
            # Get PID of the server process to clean up its database
            server_pid = server_process.pid
            
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
                
            # Clean up the PID-specific database created by models.py in MINIMAL_MODE
            pid_specific_db = os.path.join('data', f'minimal.{server_pid}.db')
            try:
                if os.path.exists(pid_specific_db):
                    os.unlink(pid_specific_db)
                # Also clean up any journal files
                journal_file = f"{pid_specific_db}-journal"
                if os.path.exists(journal_file):
                    os.unlink(journal_file)
            except OSError:
                pass
    
    atexit.register(cleanup_server)
    
    # Wait for server to start using tenacity with exponential backoff
    try:
        wait_for_server_ready(server_url)
    except RetryError:
        cleanup_server()
        pytest.skip(f"Failed to start test server on {server_url}")
    
    yield server_url
    
    # Cleanup
    cleanup_server()


@pytest.fixture(scope="module")  # One browser per test file/module
def browser():
    """Create a browser instance per test module for parallel suite execution"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="function")  # Each test gets its own page/context
def page(browser, test_server_url):
    """Create a new page in a new context for test isolation within a module"""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="function")
def mobile_context(browser, test_server_url):
    """Create a mobile browser context (iPhone 12 Pro dimensions)"""
    context = browser.new_context(
        viewport={'width': 390, 'height': 844},
        user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15'
    )
    page = context.new_page()
    yield page
    context.close()