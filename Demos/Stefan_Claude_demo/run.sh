#!/usr/bin/env bash
# BiteRec launcher for macOS / Linux.
set -e
cd "$(dirname "$0")"
if ! command -v streamlit >/dev/null 2>&1; then
  echo "Installing dependencies..."
  pip install -r requirements.txt
fi
streamlit run app.py
