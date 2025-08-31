#!/usr/bin/env python3
"""Script to run all tests for RSS Reader"""

import os
import subprocess
import sys

def run_command(cmd, description):
    """Run command and handle results"""
    print(f"\n{'='*50}")
    print(f"🧪 {description}")
    print(f"{'='*50}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {description} PASSED")
            if result.stdout:
                print("\nOutput:")
                print(result.stdout)
        else:
            print(f"❌ {description} FAILED")
            if result.stderr:
                print("\nError output:")
                print(result.stderr)
            if result.stdout:
                print("\nStandard output:")
                print(result.stdout)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Failed to run {description}: {str(e)}")
        return False

def main():
    """Run optimized test suite"""
    print("RSS Reader - Optimized Test Suite")
    print("=" * 50)
    print("72% reduction: 4,315 → 1,186 lines")
    print("Focus: Complex workflows that broke during development")
    print("=" * 50)
    
    # Change to project directory
    os.chdir('/home/kuitang/git/scratches/rss-reader-highlight')
    
    # Activate virtual environment in commands
    venv_prefix = "source venv/bin/activate && "
    
    tests = [
        (f"{venv_prefix}python -m pytest test_optimized_integration.py -v", "HTTP Integration Tests (Black-box)"),
        (f"{venv_prefix}python -m pytest test_essential_mocks.py -v", "Essential Mock Tests (Dangerous scenarios)"),
        (f"{venv_prefix}python -c 'from models import init_db; init_db(); print(\"Database: OK\")'", "Database Setup"),
        (f"{venv_prefix}python -c 'import app; print(\"App import: OK\")'", "App Import"),
    ]
    
    # Create test directories
    os.makedirs("tests", exist_ok=True)
    
    passed = 0
    total = len(tests)
    
    for cmd, description in tests:
        if run_command(cmd, description):
            passed += 1
    
    # Summary
    print(f"\n{'='*50}")
    print(f"📊 TEST SUMMARY")
    print(f"{'='*50}")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())