@echo off
REM Windows batch script to run NovelCraft tests

echo ================================================================================
echo NovelCraft Test Suite
echo ================================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.11+
    exit /b 1
)

REM Install test dependencies if needed
echo Checking test dependencies...
python -m pip install -q -r tests\requirements.txt
if errorlevel 1 (
    echo Error: Failed to install test dependencies
    exit /b 1
)

echo.
echo Running tests...
echo --------------------------------------------------------------------------------

REM Run pytest with coverage
python -m pytest tests\ -v --tb=short --cov=backend --cov-report=term-missing --cov-report=html:tests\htmlcov --junit-xml=tests\junit.xml

if errorlevel 1 (
    echo.
    echo --------------------------------------------------------------------------------
    echo Some tests failed. Please check the output above.
    exit /b 1
) else (
    echo.
    echo --------------------------------------------------------------------------------
    echo All tests passed!
    echo.
    echo Coverage report: tests\htmlcov\index.html
    echo JUnit XML report: tests\junit.xml
    echo.
    echo ================================================================================
)
