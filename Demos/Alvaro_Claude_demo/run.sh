#!/usr/bin/env bash
# BiteRec launcher — macOS / Linux
set -e
cd "$(dirname "$0")"

echo "🥗 Starting BiteRec..."

if ! python3 -c "import streamlit" 2>/dev/null; then
  echo "📦 Installing dependencies..."
  pip install -r requirements.txt
fi

mkdir -p data models

echo "🚀 Opening http://localhost:8501"
streamlit run app.py
