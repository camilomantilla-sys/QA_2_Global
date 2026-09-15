@echo off
setlocal

cd /d "%~dp0"

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
"%QA2_PYTHON%" -m streamlit run ui\app_v2.py

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
