@echo off
REM Same as run_qa2.bat, but meant to be launched hidden (no console
REM window) by "Launch QA2 (Silent).vbs" -- no `pause` at the end,
REM since there is no window for anyone to see it in.
setlocal

cd /d "%~dp0"

REM ------------------------------------------------------------------
REM  Si QA2 ya esta corriendo, no se arranca otro.
REM
REM  Cerrar la ventana negra NO detiene el proceso, y la siguiente vez
REM  Streamlit encuentra el puerto ocupado y se va al de al lado. Once
REM  vueltas, once procesos vivos -- y con ellos abiertos Windows no
REM  deja ni borrar la carpeta de QA2. Se abre el navegador al que ya
REM  esta y listo.
REM ------------------------------------------------------------------
for /f "tokens=2 delims==" %%P in ('wmic process where "name='python.exe' and commandline like '%%app_v2%%'" get processid /value 2^>nul ^| find "="') do set QA2_RUNNING=%%P

if defined QA2_RUNNING (
    start "" http://localhost:8501
    exit /b 0
)

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
