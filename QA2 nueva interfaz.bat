@echo off
setlocal
cd /d "%~dp0"

REM ------------------------------------------------------------------
REM  Vista previa de la interfaz nueva (ui\web). Convive con la de
REM  Streamlit: esta usa el puerto 8502 y la otra el 8501.
REM  Cerrar esta ventana la detiene.
REM ------------------------------------------------------------------

if exist "python\python.exe" (
    "%CD%\python\python.exe" -m ui.web
    goto :fin
)
if exist ".venv\Scripts\python.exe" (
    "%CD%\.venv\Scripts\python.exe" -m ui.web
    goto :fin
)
python -m ui.web

:fin
pause
