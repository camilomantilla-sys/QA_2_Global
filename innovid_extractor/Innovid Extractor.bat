@echo off
setlocal
cd /d "%~dp0"
title Innovid Extractor

REM ------------------------------------------------------------------
REM  Doble clic y ya. Busca un Python que tenga Playwright, en este
REM  orden:
REM    1. el propio del extractor (.venv de esta carpeta)
REM    2. el de QA2, si esta carpeta vive dentro de QA2 (solo se usa
REM       para correr; el extractor no usa codigo de QA2)
REM    3. si no hay ninguno, crea el propio la primera vez
REM ------------------------------------------------------------------

if exist "..\browsers" set "PLAYWRIGHT_BROWSERS_PATH=%~dp0..\browsers"

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "..\python\python.exe" set "PY=..\python\python.exe"
if not defined PY if exist "..\.venv\Scripts\python.exe" set "PY=..\.venv\Scripts\python.exe"
if defined PY goto :run

echo Primera vez: preparando el extractor. Tarda unos minutos y solo pasa una vez.
echo.
py -3 -m venv .venv 2>nul
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if not exist ".venv\Scripts\python.exe" goto :nopython
set "PY=.venv\Scripts\python.exe"
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
"%PY%" -m playwright install chromium
if errorlevel 1 goto :failed

:run
"%PY%" extractor.py %*
echo.
pause
exit /b 0

:nopython
echo No encontre Python en este equipo. Instala Python 3 o pon esta carpeta dentro de QA2.
pause
exit /b 1

:failed
echo La instalacion no termino. Revisa el mensaje de arriba.
pause
exit /b 1
