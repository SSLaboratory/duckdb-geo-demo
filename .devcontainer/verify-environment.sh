#!/bin/bash
# Environment verification script for SPD devcontainer

set -e

echo "🔍 SPD Devcontainer Environment Verification"
echo "=============================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is NOT installed"
        return 1
    fi
}

check_version() {
    local tool=$1
    local expected=$2
    local actual=$($tool --version 2>&1 | head -1)

    if echo "$actual" | grep -q "$expected"; then
        echo -e "${GREEN}✓${NC} $tool version matches: $actual"
        return 0
    else
        echo -e "${YELLOW}⚠${NC}  $tool version mismatch: $actual (expected: $expected)"
        return 1
    fi
}

echo "📦 Checking core tools..."
check_command mise
check_command node
check_command npm
check_command python
check_command psql
check_command docker
check_command vim
check_command git
check_command make

echo ""
echo "🔢 Checking versions..."
check_version node "v20"
check_version python "3.11"
check_version psql "15"

echo ""
echo "📁 Checking project structure..."
if [ -f "/workspace/.mise.toml" ]; then
    echo -e "${GREEN}✓${NC} .mise.toml exists"
else
    echo -e "${RED}✗${NC} .mise.toml NOT found"
fi

if [ -f "/workspace/.vimrc" ]; then
    echo -e "${GREEN}✓${NC} .vimrc exists"
else
    echo -e "${RED}✗${NC} .vimrc NOT found"
fi

if [ -d "/workspace/apps/frontend/node_modules" ]; then
    echo -e "${GREEN}✓${NC} Frontend dependencies installed"
else
    echo -e "${RED}✗${NC} Frontend dependencies NOT installed"
fi

if [ -d "/workspace/apps/backend/.venv" ]; then
    echo -e "${GREEN}✓${NC} Backend virtual environment exists"
else
    echo -e "${RED}✗${NC} Backend virtual environment NOT found"
fi

echo ""
echo "🔧 Checking pre-commit..."
if command -v pre-commit &> /dev/null; then
    echo -e "${GREEN}✓${NC} pre-commit is installed"
    if [ -f "/workspace/.git/hooks/pre-commit" ]; then
        echo -e "${GREEN}✓${NC} pre-commit hooks are installed"
    else
        echo -e "${YELLOW}⚠${NC}  pre-commit hooks NOT installed (run: pre-commit install)"
    fi
else
    echo -e "${RED}✗${NC} pre-commit is NOT installed"
fi

echo ""
echo "🐳 Checking Docker..."
if docker ps &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker daemon is accessible"
else
    echo -e "${RED}✗${NC} Docker daemon is NOT accessible"
fi

echo ""
echo "✅ Verification complete!"
