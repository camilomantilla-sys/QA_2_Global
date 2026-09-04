@echo off
REM Same setup as run_qa2.bat, but meant to be launched hidden (no
REM console window) by "Launch QA2 (Silent).vbs" -- no `pause` at the
REM end, since there's no window for anyone to see it in.
setlocal

cd /d "%~dp0"

if not exist ".venv" (
    py -3 -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
)

call .venv\Scripts\activate.bat

python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

python -m streamlit run ui\app_v2.py --server.headless false
