@echo off
setlocal

cd /d "%~dp0"

REM ------------------------------------------------------------------
REM  La version CON ventana, para ver que pasa mientras arranca.
REM  Para el dia a dia se usa QA2.bat, que no deja ninguna.
REM ------------------------------------------------------------------

REM ------------------------------------------------------------------
REM  Dos formas de arrancar, y la carpeta dice cual.
REM
REM  Si existe python\python.exe, este es el paquete que se le entrega
REM  al equipo: trae su propio Python y sus librerias ya instaladas.
REM  No hace falta que nadie instale nada, no se toca PyPI y no se
REM  pide ningun permiso.
REM
REM  Si no existe, es una copia del repositorio en la maquina de quien
REM  desarrolla: se usa el Python del sistema y su .venv, como siempre.
REM ------------------------------------------------------------------

REM ------------------------------------------------------------------
REM  Si QA2 ya esta corriendo, no se arranca otro.
REM
REM  Cerrar la ventana negra NO detiene el proceso, y la siguiente vez
REM  Streamlit encuentra el puerto ocupado y se va al de al lado. Once
REM  vueltas, once procesos vivos -- y con ellos abiertos Windows no
REM  deja ni borrar la carpeta de QA2.
REM
REM  Se reconoce por el PID que la app deja en logs\qa2.pid. No por
REM  puerto (se mueve) ni con wmic (Windows 11 ya no lo trae). Un PID
REM  viejo puede estar reutilizado, asi que se comprueba que siga
REM  siendo un python.
REM ------------------------------------------------------------------
if exist "logs\qa2.pid" (
    set /p QA2_PID=<"logs\qa2.pid"
    call :ya_corriendo
)
goto :arrancar

:ya_corriendo
REM "python" y no "python.exe": QA2.bat arranca con pythonw.exe.
tasklist /FI "PID eq %QA2_PID%" /NH 2>nul | find /i "python" >nul
if errorlevel 1 exit /b 0
echo QA2 ya esta abierto. Abriendo tu navegador.
echo.
echo Para detenerlo del todo, usa "Stop QA2.bat".
echo.
start "" http://localhost:8501
timeout /t 4 >nul
exit

:arrancar

if exist "python\python.exe" (
    set "QA2_PYTHON=%CD%\python\python.exe"
    set "PLAYWRIGHT_BROWSERS_PATH=%CD%\browsers"
    echo Starting QA2. Your browser will open automatically.
    echo Keep this window open while you work - closing it stops QA2.
    echo.
    goto :run
)

echo No bundled Python here, so this is a development copy.
echo.

if not exist ".venv" (
    echo Setting up QA2 for the first time, this can take a minute...
    py -3 -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
    if errorlevel 1 goto :nopython
)

call .venv\Scripts\activate.bat

echo Checking required packages...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

set "QA2_PYTHON=python"

echo.
echo Starting QA2. Your browser will open automatically.
echo Keep this window open while you work - closing it stops QA2.
echo.

:run
REM Streamlit ya no abre el navegador (headless, ver
REM .streamlit\config.toml), asi que se abre aqui unos segundos
REM despues -- lo que tarda el servidor en levantar.
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 6; Start-Process 'http://localhost:8501'"

"%QA2_PYTHON%" scripts\start_qa2.py 8501

pause
exit /b

:nopython
echo.
echo ---------------------------------------------------------------
echo  Python was not found on this machine.
echo.
echo  You are running a development copy of QA2, which needs Python
echo  installed. The package handed to the team does not: it carries
echo  its own, and starts with a double-click.
echo.
echo  If you were given a .zip, make sure you EXTRACTED it before
echo  running this file. Opening QA2 from inside the .zip does not
echo  work - right-click the .zip and choose "Extract All" first.
echo ---------------------------------------------------------------
echo.
pause
exit /b 1
