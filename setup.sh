#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# First-time setup script for the Morning Fitness Dashboard
# Run this once: bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo ""
echo "═══════════════════════════════════════════════"
echo "  Morning Fitness Dashboard — First-Time Setup"
echo "═══════════════════════════════════════════════"
echo ""

# 1. Create virtual environment
if [ ! -d "venv" ]; then
  echo "→ Creating Python virtual environment..."
  python3 -m venv venv
else
  echo "✓ Virtual environment already exists"
fi

# 2. Install dependencies
echo "→ Installing dependencies..."
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# 3. Create .env if it doesn't exist
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "✓ Created .env file from template"
  echo ""
  echo "  ┌──────────────────────────────────────────────────────┐"
  echo "  │  IMPORTANT: Open .env in a text editor and fill in  │"
  echo "  │  your API credentials before running the dashboard.  │"
  echo "  └──────────────────────────────────────────────────────┘"
  echo ""
  echo "  Credentials you need:"
  echo "  • Whoop Client ID + Secret  →  developer.whoop.com"
  echo "  • Strava Client ID + Secret →  strava.com/settings/api"
  echo "  • Anthropic API Key         →  console.anthropic.com"
  echo "  • Flask Secret Key (run: python3 -c \"import secrets; print(secrets.token_hex(32))\")"
  echo ""
else
  echo "✓ .env file already exists"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit .env with your API credentials"
echo "  2. Run:  bash run.sh"
echo "  3. Open: http://localhost:5000"
echo "═══════════════════════════════════════════════"
echo ""
