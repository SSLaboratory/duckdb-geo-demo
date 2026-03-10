# SPD Devcontainer Setup

## Quick Start

### 1. Build and Start Container

```bash
devpod up . --recreate
```

Or in VS Code:
- Press `Cmd/Ctrl+Shift+P`
- Select "Dev Containers: Rebuild Container"

### 2. Install Development Tools (One-Time Setup)

After the container starts, run this command **once**:

```bash
bash .devcontainer/install-mise-tools.sh
```

This will:
- ✅ Install Node 20.15.1
- ✅ Install Python 3.11.9
- ✅ Install PostgreSQL 15.8 client
- ✅ Set up mise configuration

### 3. Activate mise (Every New Shell)

The tools are installed but need to be activated in your shell PATH:

```bash
eval "$(mise activate bash)"
```

**OR** it's already added to `~/.bashrc`, so just start a new shell:

```bash
bash
```

### 4. Install Project Dependencies

```bash
# Install pre-commit hooks
pre-commit install

# Install frontend dependencies
cd /workspace/apps/frontend
npm ci

# Install backend dependencies
cd /workspace/apps/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Verify Setup

Run the verification script:

```bash
bash .devcontainer/verify-environment.sh
```

Expected output:
```
✓ mise is installed
✓ node is installed
✓ npm is installed
✓ python is installed
✓ psql is installed
✓ Node version matches: v20.15.1
✓ Python version matches: 3.11.9
✓ PostgreSQL version matches: 15.x
```

## Troubleshooting

### Issue: Permission denied when running `npm test` or other commands

**Cause:** Mounted volumes (especially `node_modules`) may have incorrect ownership.

**Immediate Fix (in current container):**

If you have sudo access:
```bash
sudo bash .devcontainer/fix-permissions.sh
```

If sudo doesn't work, you'll need to rebuild the container with the updated configuration:
```bash
# Exit container
exit

# Rebuild with new permission fixes
devpod up . --recreate
```

The new container will automatically fix permissions on startup via `postStartCommand`.

**Verify ownership:**
```bash
ls -la /workspace/apps/frontend/node_modules | head -5
# Should show: drwxr-xr-x vscode vscode
```

### Issue: `node: command not found` after running install script

**Solution:** Activate mise in your current shell:
```bash
eval "$(mise activate bash)"
```

Or start a new shell (mise is activated automatically in new shells):
```bash
bash
```

### Issue: `mise: command not found`

**Solution:** Mise should be installed in the container. Verify:
```bash
/home/vscode/.local/bin/mise --version
```

If mise is missing, rebuild the container.

### Issue: Permission denied when running install script

**Solution:** The script should run as the `vscode` user. Check:
```bash
whoami  # Should output: vscode
```

If running as root, switch to vscode user:
```bash
su - vscode
cd /workspace
bash .devcontainer/install-mise-tools.sh
```

## Scripts

### install-mise-tools.sh
Installs all mise-managed tools (Node, Python, PostgreSQL). Run once after container build.

### post-create.sh
Legacy script - now just calls `install-mise-tools.sh`. Can be run manually if needed.

### verify-environment.sh
Checks all tools are installed with correct versions.

## What's Included

The devcontainer provides:

- ✅ Node 20.15.1 (via mise)
- ✅ Python 3.11.9 (via mise)
- ✅ PostgreSQL 15.8 client (via mise)
- ✅ Docker-in-Docker (run `docker-compose` from inside container)
- ✅ Vim with custom configuration (`.vimrc`)
- ✅ VS Code extensions (Prettier, ESLint, Ruff, Python)
- ✅ Pre-commit hooks support
- ✅ Persistent caches (npm, pip, mise)

## Development Workflow

```bash
# Start all services (postgres, backend, frontend)
mise dev

# Or manually
cd /workspace/infrastructure/docker
docker-compose up

# Run tests
mise test

# Format code
mise format

# Lint code
mise lint
```

## Manual Tool Installation (Alternative)

If the script doesn't work, install tools manually:

```bash
# Trust mise config
cd /workspace
mise trust

# Install tools
mise install

# Verify
mise list
```

## Notes

- **First run takes 2-3 minutes** to download and install tools
- **Subsequent runs are fast** (<10 seconds) due to volume caching
- **Mise activation is automatic** in new shells (added to `~/.bashrc`)
- **Tools are user-specific** - installed for `vscode` user only

## Getting Help

See the full testing guide: `.devcontainer/TESTING.md`
