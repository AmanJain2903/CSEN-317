#!/bin/bash
# Verification script to check project setup

set -e

echo "==================================="
echo "Distributed Chat System - Setup Verification"
echo "==================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall status
ALL_GOOD=true

# Check Python version
echo "1. Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓${NC} Python 3 found: $PYTHON_VERSION"
else
    echo -e "${RED}✗${NC} Python 3 not found"
    ALL_GOOD=false
fi
echo ""

# Check Python dependencies
echo "2. Checking Python package requirements..."
if command -v python3 &> /dev/null; then
    for pkg in websockets PyYAML pytest; do
        if python3 -c "import ${pkg/PyYAML/yaml}" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} $pkg installed"
        else
            echo -e "${YELLOW}!${NC} $pkg not installed (run: pip install -r requirements.txt)"
            ALL_GOOD=false
        fi
    done
else
    echo -e "${YELLOW}!${NC} Cannot check packages (Python not found)"
fi
echo ""

# Check directory structure
echo "3. Checking directory structure..."
for dir in src configs tests deploy data; do
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} Directory '$dir' exists"
    else
        echo -e "${RED}✗${NC} Directory '$dir' missing"
        ALL_GOOD=false
    fi
done
echo ""

# Check source files
echo "4. Checking source files..."
SOURCE_FILES=(
    "src/__init__.py"
    "src/common.py"
    "src/transport.py"
    "src/membership.py"
    "src/failure.py"
    "src/election.py"
    "src/ordering.py"
    "src/storage.py"
    "src/node.py"
    "src/client_tui.py"
)

for file in "${SOURCE_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file missing"
        ALL_GOOD=false
    fi
done
echo ""

# Check config files
echo "5. Checking configuration files..."
CONFIG_FILES=(
    "configs/node1.yml"
    "configs/node2.yml"
    "configs/node3.yml"
    "configs/node1_local.yml"
    "configs/node2_local.yml"
    "configs/node3_local.yml"
)

for file in "${CONFIG_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${YELLOW}!${NC} $file missing"
    fi
done
echo ""

# Check test files
echo "6. Checking test files..."
TEST_FILES=(
    "tests/__init__.py"
    "tests/test_ordering.py"
    "tests/test_election.py"
    "tests/test_failure.py"
    "tests/test_integration_local.py"
)

for file in "${TEST_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file missing"
        ALL_GOOD=false
    fi
done
echo ""

# Check deployment files
echo "7. Checking deployment files..."
DEPLOY_FILES=(
    "deploy/Dockerfile"
    "deploy/docker-compose.yml"
    "deploy/k8s/deployment.yaml"
    "deploy/k8s/service.yaml"
)

for file in "${DEPLOY_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${YELLOW}!${NC} $file missing"
    fi
done
echo ""

# Check documentation
echo "8. Checking documentation..."
DOC_FILES=(
    "README.md"
    "QUICKSTART.md"
    "ARCHITECTURE.md"
    "DEMO.md"
)

for file in "${DOC_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${YELLOW}!${NC} $file missing"
    fi
done
echo ""

# Check Docker
echo "9. Checking Docker installation..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
    echo -e "${GREEN}✓${NC} Docker found: $DOCKER_VERSION"
    
    if command -v docker compose &> /dev/null; then
        echo -e "${GREEN}✓${NC} Docker Compose available"
    else
        echo -e "${YELLOW}!${NC} Docker Compose not found (optional)"
    fi
else
    echo -e "${YELLOW}!${NC} Docker not found (optional, but recommended)"
fi
echo ""

# Check data directory permissions
echo "10. Checking data directory..."
mkdir -p data/logs
if [ -w data/logs ]; then
    echo -e "${GREEN}✓${NC} data/logs is writable"
else
    echo -e "${RED}✗${NC} data/logs is not writable"
    ALL_GOOD=false
fi
echo ""

# Summary
echo "==================================="
if $ALL_GOOD; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Install dependencies: pip install -r requirements.txt"
    echo "  2. Run local: bash run_local.sh"
    echo "  3. Or Docker: cd deploy && docker compose up"
    echo "  4. Run tests: pytest tests/ -v"
    echo ""
    echo "See QUICKSTART.md for detailed instructions."
else
    echo -e "${RED}✗ Some checks failed${NC}"
    echo ""
    echo "Please fix the issues above before running the system."
    echo "See README.md for setup instructions."
fi
echo "==================================="

