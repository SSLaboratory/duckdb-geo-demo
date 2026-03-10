# Devcontainer Testing and Validation Guide

This guide helps you verify the devcontainer setup works correctly and provides troubleshooting steps.

---

## Initial Setup

### 1. Rebuild Devcontainer

**VS Code:**
1. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Linux/Windows)
2. Select "Dev Containers: Rebuild Container"
3. Wait for build to complete (~5-10 minutes first time)

**Command Line:**
```bash
# From project root
docker build -t spd-devcontainer .devcontainer/
```

### 2. Open in Devcontainer

**VS Code:**
1. Press `Cmd+Shift+P` / `Ctrl+Shift+P`
2. Select "Dev Containers: Reopen in Container"
3. Wait for container to start and post-create script to run

**VS Code will automatically:**
- Run `mise trust` to trust the `.mise.toml` configuration
- Run `mise install` to install Node 20, Python 3.11, PostgreSQL client
- Install pre-commit hooks
- Install frontend dependencies (`npm ci`)
- Install backend dependencies (`pip install -r requirements.txt`)

---

## Validation Checklist

### Step 1: Verify Tool Versions

Open a terminal in the devcontainer and run:

```bash
# Verify mise is installed
mise --version
# Expected: mise 2024.x.x or later

# Verify Node.js version
node --version
# Expected: v20.15.1

# Verify npm version
npm --version
# Expected: 10.x.x or later

# Verify Python version
python --version
# Expected: Python 3.11.9

# Verify PostgreSQL client
psql --version
# Expected: psql (PostgreSQL) 15.x

# List all mise-managed tools
mise list
# Expected output:
# node    20.15.1  ~/.local/share/mise/installs/node/20.15.1
# postgres 15.8    ~/.local/share/mise/installs/postgres/15.8
# python  3.11.9   ~/.local/share/mise/installs/python/3.11.9
```

**If any version is incorrect:**
```bash
mise install          # Reinstall all tools
mise reshim           # Rebuild shims
mise doctor           # Check for issues
```

### Step 2: Verify Docker-in-Docker

```bash
# Verify Docker is accessible
docker --version
# Expected: Docker version 20.x or later

# Verify docker-compose is accessible
docker-compose --version
# Expected: Docker Compose version v2.x

# Test docker-compose with project services
cd /workspace/infrastructure/docker
docker-compose ps
# Expected: List of services (may be empty if not running)

# Start services (optional)
docker-compose up -d
# Expected: Starts backend, frontend, postgres containers
```

**If Docker socket permission denied:**
```bash
# Check socket mount
ls -l /var/run/docker.sock
# Expected: srwxrwxrwx ... /var/run/docker.sock

# Add user to docker group (if needed)
sudo usermod -aG docker vscode
# Then rebuild container
```

### Step 3: Verify Pre-commit Hooks

```bash
# Check pre-commit installation
pre-commit --version
# Expected: pre-commit 3.x.x

# Verify hooks are installed
pre-commit run --all-files
# Expected: All hooks pass (may auto-fix files)

# Test hook on dummy commit
git config user.name "Test User"
git config user.email "test@example.com"
echo "test" > /tmp/test.txt
git add /tmp/test.txt
git commit -m "test: verify pre-commit hooks"
# Expected: Hooks run automatically
git reset HEAD~1  # Undo test commit
```

### Step 4: Verify Frontend Dependencies

```bash
cd /workspace/apps/frontend

# Verify node_modules installed
ls node_modules/ | head -5
# Expected: List of packages

# Run type checking
npm run check
# Expected: No errors

# Run linting
npm run lint
# Expected: No errors (or auto-fixable warnings)

# Run formatting check
npm run format:check
# Expected: All files formatted correctly

# Run tests (requires Node 20)
npm run test
# Expected: All tests pass
```

**If tests fail with localStorage errors:**
- Verify Node version is 20.x (not 25+)
- Check `node --version` output
- If wrong version, run `mise install node@20.15.1`

### Step 5: Verify Backend Dependencies

```bash
cd /workspace/apps/backend

# Verify virtual environment exists
ls .venv/
# Expected: bin/ lib/ include/ directories

# Activate virtual environment
source .venv/bin/activate

# Verify Python packages installed
pip list | grep fastapi
# Expected: fastapi 0.104.x or similar

# Run type checking (MyPy disabled due to known issues)
# mypy app/  # Currently disabled, see CLAUDE.md

# Run linting
ruff check app/
# Expected: No errors

# Run formatting check
ruff format --check app/
# Expected: All files formatted correctly

# Run tests
pytest --cov=app --cov-report=term-missing
# Expected: Tests pass with 80%+ coverage

# Deactivate virtual environment
deactivate
```

### Step 6: Verify Vim Configuration

```bash
# Open vim
vim

# Inside vim, verify basic settings
:set number?
# Expected: number

:set tabstop?
# Expected: tabstop=2

:set expandtab?
# Expected: expandtab

# Test custom commands (requires files to exist)
# :FormatFrontend
# :FormatBackend
# :LintFrontend
# :LintBackend

# Exit vim
:q
```

**Test external formatting commands:**
```bash
# Frontend formatting
cd /workspace/apps/frontend
npm run format
# Expected: Files formatted

# Backend formatting
cd /workspace/apps/backend
ruff format app/
# Expected: Files formatted

# Frontend linting
cd /workspace/apps/frontend
npm run lint:fix
# Expected: Issues auto-fixed

# Backend linting
cd /workspace/apps/backend
ruff check --fix app/
# Expected: Issues auto-fixed
```

### Step 7: Verify Mise Task Shortcuts

```bash
# Return to workspace root
cd /workspace

# List available tasks
mise tasks
# Expected: List of tasks (dev, test, lint, format, etc.)

# Test format task (formats both frontend and backend)
mise format
# Expected: Runs prettier and ruff format

# Test lint task (lints both frontend and backend)
mise lint
# Expected: Runs eslint and ruff check

# Test type checking
mise check
# Expected: Runs tsc for frontend

# Test full test suite (takes several minutes)
# mise test
# Expected: Runs pytest and vitest
```

---

## Common Issues and Troubleshooting

### Issue: "mise: command not found"

**Cause:** Mise not installed or not in PATH

**Fix:**
```bash
# Reinstall mise
curl https://mise.run | sh

# Add to PATH (already in Dockerfile, but verify)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify installation
mise --version
```

### Issue: "Node version is not 20.x"

**Cause:** Mise not activated or wrong Node installed

**Fix:**
```bash
# Check mise status
mise doctor

# Reinstall Node 20
mise install node@20.15.1

# Verify shims
mise reshim

# Check version
node --version
```

### Issue: "Permission denied: /var/run/docker.sock"

**Cause:** Docker socket not accessible from devcontainer

**Fix:**
```bash
# Verify socket is mounted
ls -l /var/run/docker.sock

# Check devcontainer.json has runArgs
cat /workspace/.devcontainer/devcontainer.json | grep docker.sock
# Expected: "-v", "/var/run/docker.sock:/var/run/docker.sock"

# Rebuild devcontainer if missing
```

### Issue: "Tests fail with localStorage.getItem is not a function"

**Cause:** Node version mismatch (likely Node 25+ instead of Node 20)

**Fix:**
```bash
# Verify Node version
node --version
# Must be v20.x.x

# If wrong version
mise install node@20.15.1
mise use node@20.15.1

# Clear node_modules and reinstall
cd /workspace/apps/frontend
rm -rf node_modules package-lock.json
npm install

# Retry tests
npm run test
```

### Issue: "Pre-commit hooks not running"

**Cause:** Hooks not installed or git config issue

**Fix:**
```bash
# Reinstall hooks
cd /workspace
pre-commit install

# Verify installation
pre-commit run --all-files

# Check git hooks directory
ls -la /workspace/.git/hooks/
# Expected: pre-commit symlink or script
```

### Issue: "Virtual environment not found (backend)"

**Cause:** Post-create script failed or didn't run

**Fix:**
```bash
# Manually create virtual environment
cd /workspace/apps/backend
python -m venv .venv

# Activate and install dependencies
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Verify installation
pip list
```

### Issue: "Vim commands not working (:FormatFrontend, etc.)"

**Cause:** Vim not loading .vimrc

**Fix:**
```bash
# Verify .vimrc exists
cat /workspace/.vimrc | head -20

# Check if vim loads it
vim -u /workspace/.vimrc

# If not loading automatically, source it manually in vim
# :source /workspace/.vimrc

# Or add to ~/.vimrc
echo "source /workspace/.vimrc" >> ~/.vimrc
```

---

## Manual Testing Workflows

### Workflow 1: Edit Frontend File

```bash
# Open a React component
cd /workspace/apps/frontend
vim src/App.tsx

# Make changes
# Press 'i' to enter insert mode
# Make some edits
# Press 'Esc' to exit insert mode

# Format the file (inside vim)
:FormatFrontend

# Save and exit
:wq

# Verify formatting applied
git diff src/App.tsx
```

### Workflow 2: Edit Backend File

```bash
# Open a Python service
cd /workspace/apps/backend
vim app/services/page_service.py

# Make changes
# Press 'i' to enter insert mode
# Add a new function or edit existing code
# Press 'Esc' to exit insert mode

# Format the file (inside vim)
:FormatPython

# Lint the file (inside vim)
:LintPython

# Save and exit
:wq

# Verify changes
git diff app/services/page_service.py
```

### Workflow 3: Full Development Cycle

```bash
# 1. Start services
cd /workspace
mise dev
# (Or manually: cd infrastructure/docker && docker-compose up)

# 2. Make code changes (use vim)
vim apps/frontend/src/components/SomeComponent.tsx

# 3. Format and lint before commit
mise format
mise lint

# 4. Run tests
mise test

# 5. Commit changes (pre-commit hooks run automatically)
git add .
git commit -m "feat(frontend): add new component"

# 6. Push to GitHub
git push origin feature/branch-name
```

---

## Performance Benchmarks

**Expected performance (first run vs subsequent runs):**

| Task | First Run | Subsequent Runs |
|------|-----------|-----------------|
| Container build | 5-10 min | 30-60 sec (cached) |
| mise install | 2-3 min | 5-10 sec (cached) |
| npm ci (frontend) | 1-2 min | 10-20 sec (cached) |
| pip install (backend) | 1-2 min | 10-20 sec (cached) |
| pre-commit --all-files | 30-60 sec | 5-10 sec |
| npm run test (frontend) | 20-40 sec | 10-20 sec |
| pytest (backend) | 10-20 sec | 5-10 sec |

**Total setup time:**
- First run: ~15-20 minutes
- Subsequent runs: ~2-3 minutes

---

## Environment Verification Script

Save this as `/workspace/.devcontainer/verify-environment.sh` and run to check all requirements:

```bash
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
```

Make it executable:
```bash
chmod +x /workspace/.devcontainer/verify-environment.sh
```

Run it:
```bash
/workspace/.devcontainer/verify-environment.sh
```

---

## Next Steps

Once all validation checks pass:

1. **Test with Claude Code:**
   ```bash
   # Launch Claude Code in the devcontainer
   # (User will do this manually)
   ```

2. **Run full test suite:**
   ```bash
   mise test
   ```

3. **Start development:**
   ```bash
   mise dev
   ```

4. **Make a test commit:**
   ```bash
   # Create a small change
   # Verify pre-commit hooks run
   # Verify all checks pass
   ```

5. **Push to GitHub and verify CI:**
   ```bash
   git push origin branch-name
   # Watch GitHub Actions run
   ```

---

## Reference

- **Mise Documentation:** https://mise.jdx.dev/
- **Devcontainer Specification:** https://containers.dev/
- **SPD Project Documentation:** `/workspace/CLAUDE.md`
- **Pre-commit Framework:** https://pre-commit.com/
- **Docker-in-Docker:** https://github.com/devcontainers/features/tree/main/src/docker-in-docker

---

**Last Updated:** 2025-12-30
**Maintained By:** SPD Development Team
