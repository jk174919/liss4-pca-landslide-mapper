@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Install Python 3.10 or newer first.
  pause
  exit /b 1
)
echo Starting LISS-4 PCA and landslide candidate mapping in your browser...
py -3 -m streamlit run streamlit_app.py
pause

