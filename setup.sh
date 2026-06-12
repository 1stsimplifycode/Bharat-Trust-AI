#!/usr/bin/env bash
# BharatTrust AI - one-time setup (macOS / Linux)
set -e
cd "$(dirname "$0")/backend"
echo "[1/4] Creating virtual environment..."
python3 -m venv .venv
echo "[2/4] Activating..."
source .venv/bin/activate
echo "[3/4] Installing dependencies..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt
echo "[4/4] Seeding database..."
python -m app.seed
echo "Setup complete. Run ./run.sh to start."
