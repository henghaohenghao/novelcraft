#!/usr/bin/env python3
"""
Test runner script for NovelCraft
Runs all tests and generates a comprehensive report
"""
import sys
import subprocess
import os
from pathlib import Path


def main():
    """Run all tests and generate report"""
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    print("=" * 80)
    print("NovelCraft Test Suite")
    print("=" * 80)
    print()

    # Check if pytest is installed
    try:
        import pytest
    except ImportError:
        print("❌ pytest not found. Installing test dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "tests/requirements.txt"])
        print()

    # Run tests with coverage
    print("Running tests...")
    print("-" * 80)

    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--cov=backend",
        "--cov-report=term-missing",
        "--cov-report=html:tests/htmlcov",
        "--junit-xml=tests/junit.xml"
    ]

    result = subprocess.run(cmd)

    print()
    print("-" * 80)

    if result.returncode == 0:
        print("✅ All tests passed!")
        print()
        print("📊 Coverage report generated at: tests/htmlcov/index.html")
        print("📄 JUnit XML report generated at: tests/junit.xml")
    else:
        print("❌ Some tests failed. Please check the output above.")
        sys.exit(1)

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
