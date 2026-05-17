#!/usr/bin/env bash
# Run the Morning Fitness Dashboard
# Usage: bash run.sh

set -e

if [ ! -d "venv" ]; then
  echo "Virtual environment not found. Run 'bash setup.sh' first."
  exit 1
fi

if [ ! -f ".env" ]; then
  echo ".env file not found. Run 'bash setup.sh' first."
  exit 1
fi

echo ""
echo "  Starting Morning Fitness Dashboard..."
echo "  → http://localhost:5000"
echo "  → Press Ctrl+C to stop"
echo ""

./venv/bin/python app.py
