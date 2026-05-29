#!/bin/bash
# LeadHarvest — One-command installer (Mac/Linux)
set -e

echo ""
echo "  ⬡ LeadHarvest — Installer"
echo "  ─────────────────────────────"

# Check Python version
PYTHON=$(python3 --version 2>&1 | awk '{print $2}')
MAJOR=$(echo "$PYTHON" | cut -d. -f1)
MINOR=$(echo "$PYTHON" | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]; }; then
  echo "  ✗ Python 3.10+ required. Found: $PYTHON"
  exit 1
fi
echo "  ✓ Python $PYTHON"

# Create virtual environment
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "  ✓ Virtual environment created"
fi

source .venv/bin/activate

# Install dependencies
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "  ✓ Python packages installed"

# Install Playwright Chromium
playwright install chromium --with-deps
echo "  ✓ Playwright Chromium installed"

# Create directories
mkdir -p exports logs
echo "  ✓ Directories created"

# Copy .env if missing
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  ✓ .env created from .env.example"
fi

echo ""
echo "  ✅ Installation complete!"
echo ""
echo "  To start LeadHarvest:"
echo "    source .venv/bin/activate"
echo "    cd backend && uvicorn main:app --reload"
echo "  Then open: http://127.0.0.1:8000"
echo ""
