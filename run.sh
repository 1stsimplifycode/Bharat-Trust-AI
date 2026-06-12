#!/usr/bin/env bash
# BharatTrust AI - start the app (macOS / Linux)
set -e
cd "$(dirname "$0")/backend"
if [ ! -d ".venv" ]; then echo "Run ./setup.sh first."; exit 1; fi
source .venv/bin/activate
echo "Dashboard: http://localhost:8000   |   API docs: http://localhost:8000/docs"
uvicorn app.main:app --host 0.0.0.0 --port 8000
