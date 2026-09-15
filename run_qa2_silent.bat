@echo off
REM Same as run_qa2.bat, but meant to be launched hidden (no console
REM window) by "Launch QA2 (Silent).vbs" -- no `pause` at the end,
REM since there is no window for anyone to see it in.
setlocal

cd /d "%~dp0"

if exist "python\python.exe" (
    set "QA2_PYTHON=%CD%\python\python.exe"
    set "PLAYWRIGHT_BROWSERS_PATH=%CD%\browsers"
    goto :run
)

if not exist ".venv" (
    py -3 -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat

python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

set "QA2_PYTHON=python"

:run
"%QA2_PYTHON%" -m streamlit run ui\app_v2.py --server.headless false
