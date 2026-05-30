@echo off
echo 🥗 Starting BiteRec...
cd /d "%~dp0"

python -c "import streamlit" 2>nul || (
    echo 📦 Installing dependencies...
    pip install -r requirements.txt
)

mkdir data 2>nul
mkdir models 2>nul

echo 🚀 Opening http://localhost:8501
streamlit run app.py
pause
