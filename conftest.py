"""
Root conftest.py for RSS Reader test suite with native pytest server management.
Replaces shell-based server management with pytest fixtures and hooks.
"""

import os
import sys
import time
import signal
import subprocess
import httpx
from contextlib import contextmanager
from typing import Optional, Generator

import pytest


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", 
        "need_full_db: Tests that require full database with substantial content, fail in MINIMAL_MODE"
    )
    config.addinivalue_line(
        "markers",
        "needs_server: Tests that require a running server"
    )


def pytest_sessionstart(session):
    """The xdist controller owns the shared HTTP server for all workers.

    Every worker uses port 8080, so independent worker startup/teardown races
    would kill another worker's server while its test is making a request.
    """
    config = session.config
    if not hasattr(config, "workerinput") and getattr(config.option, "numprocesses", 0):
        os.environ['MINIMAL_MODE'] = 'true'
        config._rss_test_server = start_test_server(minimal=True)
        if config._rss_test_server is None:
            pytest.exit("Failed to start the shared xdist test server", returncode=1)


def pytest_sessionfinish(session, exitstatus):
    server = getattr(session.config, "_rss_test_server", None)
    if server is not None:
        stop_test_server(server)


@pytest.fixture(scope="session", autouse=True)
def setup_xdist_server():
    # The controller starts the server before scheduling worker tests and
    # stops it after every worker has finished.
    yield None


@pytest.fixture(scope="session")
def server_manager():
    """
    Session-scoped server manager that adapts to xdist vs single-process execution.
    
    - Single process: Starts and manages server lifecycle
    - xdist worker: Assumes server is managed by worker hooks
    """
    if os.getenv('PYTEST_XDIST_WORKER'):
        # Running under xdist - server managed by worker hooks
        print("🔗 xdist mode: Using worker-managed server")
        yield None
    else:
        # Single process mode - start our own minimal server
        print("🚀 Single process mode: Starting session server...")
        os.environ['MINIMAL_MODE'] = 'true'
        
        server_process = start_test_server(minimal=True)
        if not server_process:
            pytest.fail("Failed to start test server in single process mode")
            
        try:
            yield server_process
        finally:
            print("🧹 Session cleanup: Stopping server...")
            stop_test_server(server_process)


def start_test_server(minimal: bool = True, timeout: int = 20) -> Optional[subprocess.Popen]:
    """Start the test server and wait for it to be ready"""
    env = os.environ.copy()
    env['PRODUCTION'] = 'true'
    if minimal:
        env['MINIMAL_MODE'] = 'true'
    
    try:
        # Start new server
        server_process = subprocess.Popen([
            sys.executable, '-m', 'app'
        ], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait for server to be ready
        for i in range(timeout):
            try:
                response = httpx.get('http://localhost:8080', timeout=1)
                if response.status_code == 200:
                    return server_process
            except httpx.RequestError:
                pass
            time.sleep(1)
        
        # Server failed to start
        stop_test_server(server_process)
        return None
        
    except Exception as e:
        print(f"Error starting test server: {e}")
        return None


def stop_test_server(server_process: subprocess.Popen):
    """Stop the test server gracefully"""
    try:
        # Try graceful shutdown first
        server_process.terminate()
        server_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # Force kill if needed
        server_process.kill()
        server_process.wait()
    except Exception as e:
        print(f"Error stopping server: {e}")


@contextmanager
def minimal_mode():
    """Context manager to ensure MINIMAL_MODE is set for core tests"""
    original = os.environ.get('MINIMAL_MODE')
    os.environ['MINIMAL_MODE'] = 'true'
    try:
        yield
    finally:
        if original is None:
            os.environ.pop('MINIMAL_MODE', None)
        else:
            os.environ['MINIMAL_MODE'] = original


# Auto-use fixture to set MINIMAL_MODE for core tests
@pytest.fixture(autouse=True)
def auto_minimal_mode(request):
    """Automatically set MINIMAL_MODE for core tests"""
    test_file = request.fspath.strpath
    if '/tests/core/' in test_file:
        with minimal_mode():
            yield
    else:
        yield