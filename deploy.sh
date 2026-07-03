#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "Deploying Golden Plate Recorder Locally"
echo "========================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f "requirements.txt" ]]; then
  if [[ -f "goldenplatewebsite/requirements.txt" ]]; then
    echo "Found project folder next to script. Navigating into goldenplatewebsite..."
    cd goldenplatewebsite
  else
    echo "ERROR: Cannot find requirements.txt or the goldenplatewebsite folder."
    echo "Run this script from the project folder, or place it directly next to the project folder."
    exit 1
  fi
fi

find_python() {
  local cmd
  for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
      if "$cmd" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
      then
        printf '%s\n' "$cmd"
        return 0
      fi
    fi
  done
  return 1
}

load_node_tools() {
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    return 0
  fi

  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck source=/dev/null
    source "$NVM_DIR/nvm.sh"
    nvm use --silent default >/dev/null 2>&1 \
      || nvm use --silent node >/dev/null 2>&1 \
      || nvm use --silent --lts >/dev/null 2>&1 \
      || true
  fi

  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    return 0
  fi

  local node_bin
  for node_bin in "$HOME"/.nvm/versions/node/*/bin; do
    if [[ -x "$node_bin/node" && -x "$node_bin/npm" ]]; then
      export PATH="$node_bin:$PATH"
      return 0
    fi
  done

  return 1
}

echo
echo "[1/7] Checking for Python 3.11+..."
PYTHON_CMD="$(find_python || true)"
if [[ -z "$PYTHON_CMD" ]]; then
  echo "ERROR: Python 3.11+ is required."
  echo "Install it with Homebrew:"
  echo "  brew install python@3.13"
  echo "or download it from https://www.python.org/downloads/macos/"
  exit 1
fi
"$PYTHON_CMD" --version

echo
echo "[2/7] Checking for Node.js and npm..."
if ! load_node_tools; then
  echo "ERROR: Node.js and npm are required."
  echo "Install Node.js from https://nodejs.org/ or with nvm:"
  echo "  nvm install --lts"
  exit 1
fi
node --version
npm --version

echo
echo "[3/7] Setting up Python virtual environment..."
VENV_DIR="${VENV_DIR:-venv}"
if [[ -x "$VENV_DIR/bin/python" ]]; then
  if ! "$VENV_DIR/bin/python" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
    echo "Existing virtual environment does not use Python 3.11+. Recreating it..."
    rm -rf "$VENV_DIR"
  fi
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_CMD" -m venv "$VENV_DIR"
else
  echo "Virtual environment already exists."
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  echo "Installing Python dependencies..."
  python -m pip install --upgrade pip
  python -m pip install --prefer-binary -r requirements.txt
else
  echo "Skipping Python dependency install because SKIP_INSTALL=1."
fi

echo
echo "[4/7] Setting up frontend dependencies..."
if [[ ! -d "frontend" ]]; then
  echo "ERROR: Cannot find frontend folder."
  exit 1
fi

if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  npm --prefix frontend install --legacy-peer-deps
else
  echo "Skipping frontend dependency install because SKIP_INSTALL=1."
fi

echo
echo "[5/7] Building frontend..."
npm --prefix frontend run build

echo
echo "[6/7] Verifying frontend build output..."
if [[ ! -f "src/static/index.html" ]]; then
  echo "ERROR: Frontend build output was not generated in src/static."
  exit 1
fi
echo "Frontend build emitted successfully into src/static."

echo
echo "[7/7] Starting the application..."
APP_PORT="${PORT:-59237}"
echo "The application will be running at http://127.0.0.1:${APP_PORT}"
echo "Press Ctrl+C to stop the server."
echo
PORT="$APP_PORT" python src/main.py
