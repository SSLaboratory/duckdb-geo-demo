#!/bin/bash
# Install mise tools for the vscode user
# This script is designed to run after the container is built

set -e

echo "🔧 Installing mise tools for user: $(whoami)"
echo "Home directory: $HOME"
echo "Working directory: $(pwd)"

# Ensure mise cache directory exists
echo "📁 Creating mise cache directory..."
mkdir -p "$HOME/.cache/mise"
chmod 755 "$HOME/.cache/mise"

# Trust the mise configuration
echo "🔐 Trusting mise configuration..."
if [ -f "/workspace/.mise.toml" ]; then
    mise trust /workspace/.mise.toml
    echo "✓ Trusted /workspace/.mise.toml"
else
    echo "⚠️  Warning: /workspace/.mise.toml not found"
fi

# Install mise tools
echo "📦 Installing mise tools (Node 20, Python 3.11, PostgreSQL 15)..."
cd /workspace
mise install

# Verify installations
echo ""
echo "✅ Mise tool installation complete!"
echo ""
echo "Installed versions:"
mise list

echo ""
echo "Tool versions:"
node --version 2>/dev/null && echo "✓ Node: $(node --version)" || echo "⚠️  Node not found in PATH"
npm --version 2>/dev/null && echo "✓ npm: $(npm --version)" || echo "⚠️  npm not found in PATH"
python --version 2>/dev/null && echo "✓ Python: $(python --version)" || echo "⚠️  Python not found in PATH"
psql --version 2>/dev/null && echo "✓ PostgreSQL client: $(psql --version | head -1)" || echo "⚠️  psql not found in PATH"

echo ""
echo "💡 If tools are not in PATH, run: eval \"\$(mise activate bash)\""
echo "   Or add to ~/.bashrc: eval \"\$(mise activate bash)\""
