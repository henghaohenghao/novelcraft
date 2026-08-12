#!/bin/bash
# Unix/Linux/Mac script to run NovelCraft tests

echo "================================================================================"
echo "NovelCraft Test Suite"
echo "================================================================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Please install Python 3.11+"
    exit 1
fi

# Install test dependencies if needed
echo "Checking test dependencies..."
python3 -m pip install -q -r tests/requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install test dependencies"
    exit 1
fi

echo ""
echo "Running tests..."
echo "--------------------------------------------------------------------------------"

# Run pytest with coverage
python3 -m pytest tests/ -v --tb=short --cov=backend --cov-report=term-missing --cov-report=html:tests/htmlcov --junit-xml=tests/junit.xml

if [ $? -ne 0 ]; then
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "❌ Some tests failed. Please check the output above."
    exit 1
else
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "✅ All tests passed!"
    echo ""
    echo "📊 Coverage report: tests/htmlcov/index.html"
    echo "📄 JUnit XML report: tests/junit.xml"
    echo ""
    echo "================================================================================"
fi
