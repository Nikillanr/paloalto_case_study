#!/usr/bin/env bash
set -e

echo "==> Stopping any running server..."
pkill -9 -f "uvicorn app.main" 2>/dev/null || true
sleep 1

echo "==> Cleaning database..."
rm -f data/guardian.db

echo "==> Starting Community Guardian..."
python3 -m uvicorn app.main:app --port 8000
