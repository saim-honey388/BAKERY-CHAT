#!/usr/bin/env python3
"""
Test Runner for BAKERY-CHAT

PURPOSE:
    This script provides a convenient way to run different types of tests
    for the BAKERY-CHAT application with various options and configurations.

CREATED:
    January 2025
    Author: AI Assistant
    Version: 1.0

USAGE:
    python tests/run_tests.py [options]
    
    Options:
    --basic          Run basic OrderAgent tests
    --comprehensive  Run comprehensive OrderAgent tests
    --all            Run all available tests
    --coverage       Run tests with coverage reporting
    --verbose        Run with verbose output
    --debug          Run with debug output
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(command, check=True, capture_output=False)
        print(f"\n✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} failed with exit code {e.returncode}")
        return False

def check_environment():
    """Check if the environment is properly set up."""
    print("🔍 Checking environment...")
    
    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Warning: Virtual environment may not be activated")
    
    # Check if pytest is available
    try:
        import pytest
        print("✅ pytest is available")
    except ImportError:
        print("❌ pytest is not available. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "pytest-cov"], check=True)
    
    # Check if backend directory exists
    if not (project_root / "backend").exists():
        print("❌ backend directory not found")
        return False
    
    print("✅ Environment check completed")
    return True

def run_basic_tests(verbose=False, coverage=False):
    """Run basic OrderAgent tests."""
    command = [sys.executable, "-m", "pytest", "tests/test_order_agent_basic.py"]
    
    if verbose:
        command.append("-v")
    if coverage:
        command.extend(["--cov=backend.agents.order_agent", "--cov-report=term-missing"])
    
    return run_command(command, "Basic OrderAgent Tests")

def run_comprehensive_tests(verbose=False, coverage=False):
    """Run comprehensive OrderAgent tests."""
    command = [sys.executable, "-m", "pytest", "tests/test_order_agent_comprehensive.py"]
    
    if verbose:
        command.append("-v")
    if coverage:
        command.extend(["--cov=backend.agents.order_agent", "--cov-report=term-missing"])
    
    return run_command(command, "Comprehensive OrderAgent Tests")

def run_all_tests(verbose=False, coverage=False):
    """Run all available tests."""
    command = [sys.executable, "-m", "pytest", "tests/"]
    
    if verbose:
        command.append("-v")
    if coverage:
        command.extend(["--cov=backend", "--cov-report=term-missing", "--cov-report=html"])
    
    return run_command(command, "All Tests")

def run_coverage_report():
    """Generate a detailed coverage report."""
    command = [
        sys.executable, "-m", "pytest", "tests/",
        "--cov=backend",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-report=xml"
    ]
    
    return run_command(command, "Coverage Report")

def main():
    """Main function to parse arguments and run tests."""
    parser = argparse.ArgumentParser(
        description="Test Runner for BAKERY-CHAT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/run_tests.py --basic
  python tests/run_tests.py --comprehensive --verbose
  python tests/run_tests.py --all --coverage
  python tests/run_tests.py --coverage --debug
        """
    )
    
    parser.add_argument(
        "--basic",
        action="store_true",
        help="Run basic OrderAgent tests"
    )
    
    parser.add_argument(
        "--comprehensive",
        action="store_true",
        help="Run comprehensive OrderAgent tests"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all available tests"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with coverage reporting"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Run with verbose output"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run with debug output"
    )
    
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="Check environment setup only"
    )
    
    args = parser.parse_args()
    
    # Print header
    print("🧪 BAKERY-CHAT Test Runner")
    print("=" * 60)
    print("Purpose: Run comprehensive tests for the bakery chatbot")
    print("Created: January 2025")
    print("=" * 60)
    
    # Check environment if requested
    if args.check_env:
        check_environment()
        return
    
    # Check environment before running tests
    if not check_environment():
        print("❌ Environment check failed. Please fix the issues above.")
        sys.exit(1)
    
    # Determine what tests to run
    tests_to_run = []
    
    if args.basic:
        tests_to_run.append(("basic", run_basic_tests))
    
    if args.comprehensive:
        tests_to_run.append(("comprehensive", run_comprehensive_tests))
    
    if args.all:
        tests_to_run.append(("all", run_all_tests))
    
    # If no specific tests specified, run basic tests
    if not tests_to_run:
        tests_to_run.append(("basic", run_basic_tests))
    
    # Run the tests
    success_count = 0
    total_tests = len(tests_to_run)
    
    for test_name, test_func in tests_to_run:
        success = test_func(
            verbose=args.verbose,
            coverage=args.coverage
        )
        if success:
            success_count += 1
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST RUN SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {total_tests}")
    print(f"Successful: {success_count}")
    print(f"Failed: {total_tests - success_count}")
    print(f"Success rate: {(success_count / total_tests * 100):.1f}%")
    
    if args.coverage:
        print("\n📊 Coverage reports generated:")
        print("  - HTML report: htmlcov/index.html")
        print("  - XML report: coverage.xml")
    
    # Exit with appropriate code
    if success_count == total_tests:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {total_tests - success_count} test suite(s) failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
