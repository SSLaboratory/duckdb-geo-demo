#!/bin/bash
# Post-create script for SPD devcontainer
# Runs after container is created to set up development environment

set -e

echo "🚀 Setting up SPD development environment..."

# Install mise tools using dedicated script
bash /workspace/.devcontainer/install-mise-tools.sh

# Verify tool versions
echo "✅ Verifying installed tools..."
echo "Node: $(node --version)"
echo "NPM: $(npm --version)"
echo "Python: $(python --version)"
echo "PostgreSQL client: $(psql --version)"
echo "Mise: $(mise --version)"

# Install pre-commit hooks
echo "🔧 Installing pre-commit hooks..."
if command -v pre-commit &> /dev/null; then
    pre-commit install || echo "⚠️  Pre-commit install failed (will retry later)"
else
    pip install pre-commit
    pre-commit install
fi

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd /workspace/apps/frontend
npm ci

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd /workspace/apps/backend

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    python -m venv .venv
fi

# Activate virtual environment and install dependencies
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Deactivate virtual environment
deactivate

# Return to workspace root
cd /workspace

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "📚 Quick Start Commands:"
echo "  mise dev                    # Start all services (frontend + backend + postgres)"
echo "  mise dev:frontend           # Start frontend only"
echo "  mise dev:backend            # Start backend only"
echo "  mise test                   # Run all tests"
echo "  mise lint                   # Lint all code"
echo "  mise format                 # Format all code"
echo ""
echo "📖 See .mise.toml for all available tasks"
echo ""
