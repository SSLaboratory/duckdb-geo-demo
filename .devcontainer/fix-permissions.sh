#!/bin/bash
# Fix permissions for mounted volumes in devcontainer
# Run this if you encounter permission errors

set -e

echo "🔧 Fixing permissions for vscode user..."

# Check if running as root (needed for chown)
if [ "$(id -u)" -eq 0 ]; then
    echo "Running as root - fixing permissions..."

    # Fix workspace permissions
    echo "Fixing /workspace permissions..."
    chown -R vscode:vscode /workspace

    # Fix cache directory permissions
    echo "Fixing cache directory permissions..."
    chown -R vscode:vscode /home/vscode/.cache

    echo "✅ Permissions fixed!"
    echo ""
    echo "Now switch to vscode user:"
    echo "  su - vscode"
    echo "  cd /workspace"
else
    echo "Not running as root - attempting with sudo..."

    # Try with sudo
    sudo chown -R vscode:vscode /workspace
    sudo chown -R vscode:vscode /home/vscode/.cache

    echo "✅ Permissions fixed!"
fi

echo ""
echo "Current user: $(whoami)"
echo "Workspace ownership:"
ls -la /workspace | head -5
echo ""
echo "You should now be able to run npm commands without permission errors."
