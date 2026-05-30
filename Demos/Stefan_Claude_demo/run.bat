@echo off
REM BiteRec launcher for Windows.
cd /d "%~dp0"
where streamlit >nul 2>nul
if errorlevel 1 (
  echo Installing dependencies...
  pip install -r requirements.txt
)
streamlit run app.py
pause
