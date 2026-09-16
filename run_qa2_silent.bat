@echo off
REM Same as run_qa2.bat, but meant to be launched hidden (no console
REM window) by "Launch QA2 (Silent).vbs" -- no `pause` at the end,
REM since there is no window for anyone to see it in.
setlocal

cd /d "%~dp0"

del "%TEMP%\qa2_launch_error.txt" 2>nul

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

REM Una copia de desarrollo: hace falta Python del sistema. Si no
REM esta, se deja escrito por que -- no hay ventana donde verlo, y el
REM .vbs lee este archivo para poder decirlo.
if not exist ".venv" (
    py -3 -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
    if errorlevel 1 (
        echo NO_PYTHON > "%TEMP%\qa2_launch_error.txt"
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

set "QA2_PYTHON=python"

:run
REM Puerto fijo y sin abrir el navegador aqui: lo abre el .vbs cuando
REM confirma que el servidor responde. Asi hay un sitio donde saber si
REM arranco o no, que es justo lo que faltaba.
"%QA2_PYTHON%" -m streamlit run ui\app_v2.py --server.headless true --server.port 8501
echo STREAMLIT_EXITED %errorlevel% > "%TEMP%\qa2_launch_error.txt"
