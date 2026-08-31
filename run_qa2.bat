@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv" (
    echo Setting up QA2 for the first time, this can take a minute...
    py -3 -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Checking required packages...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo.
echo Starting QA2. Your browser will open automatically.
echo Keep this window open while you work - closing it stops QA2.
echo.

streamlit run ui\app_v2.py

pause
