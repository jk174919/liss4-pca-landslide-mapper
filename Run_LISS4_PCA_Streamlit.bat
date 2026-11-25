@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install dependencies. Install Python 3.10 or newer first.
  pause
  exit /b 1
)
py -3 -m streamlit run streamlit_app.py
pause

