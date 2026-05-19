#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from template. Edit it to add ANTHROPIC_API_KEY before running."
fi

echo
echo "Setup complete. To run:"
echo "  source .venv/bin/activate"
echo "  python3 -m src.cli run --limit-per-sub 10"
