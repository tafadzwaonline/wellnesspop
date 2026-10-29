@echo off
rem Double-click to run WellnessPop on this computer and open it in your browser.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setting up WellnessPop for the first time...
  python -m venv .venv || (echo Python 3.12 is required: https://www.python.org/downloads/ & pause & exit /b 1)
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
)
".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501 --server.headless false
