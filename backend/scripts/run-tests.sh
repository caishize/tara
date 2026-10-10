#!/bin/bash
# Run tests for Secretary backend

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Secretary Backend Test Runner ===${NC}\n"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Warning: Virtual environment not found${NC}"
    echo "Run: python -m venv venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment if not already activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${BLUE}Activating virtual environment...${NC}"
    source .venv/bin/activate
fi

# Parse command line arguments
TEST_TYPE=${1:-"all"}
COVERAGE=${2:-"no"}

case $TEST_TYPE in
    "unit")
        echo -e "${GREEN}Running unit tests only...${NC}"
        if [ "$COVERAGE" = "cov" ]; then
            pytest -m unit --cov=src --cov-report=html --cov-report=term-missing
        else
            pytest -m unit -v
        fi
        ;;
    "integration")
        echo -e "${GREEN}Running integration tests only...${NC}"
        if [ "$COVERAGE" = "cov" ]; then
            pytest -m integration --cov=src --cov-report=html --cov-report=term-missing
        else
            pytest -m integration -v
        fi
        ;;
    "all")
        echo -e "${GREEN}Running all tests...${NC}"
        if [ "$COVERAGE" = "cov" ]; then
            pytest --cov=src --cov-report=html --cov-report=term-missing
            echo -e "\n${BLUE}Coverage report generated: htmlcov/index.html${NC}"
        else
            pytest -v
        fi
        ;;
    "quick")
        echo -e "${GREEN}Running quick test (unit tests without coverage)...${NC}"
        pytest -m unit -v --tb=short
        ;;
    *)
        echo -e "${YELLOW}Usage: $0 [all|unit|integration|quick] [cov]${NC}"
        echo ""
        echo "Examples:"
        echo "  $0              # Run all tests"
        echo "  $0 unit         # Run unit tests only"
        echo "  $0 all cov      # Run all tests with coverage"
        echo "  $0 quick        # Quick unit tests"
        exit 1
        ;;
esac

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓ All tests passed!${NC}"
else
    echo -e "\n${YELLOW}✗ Some tests failed${NC}"
    exit 1
fi
