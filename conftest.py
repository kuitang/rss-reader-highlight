"""Pytest configuration and markers for RSS Reader tests"""

import pytest

def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", 
        "need_full_db: Tests that require full database with substantial content, fail in MINIMAL_MODE"
    )