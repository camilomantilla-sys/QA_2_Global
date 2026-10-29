@echo off
setlocal

cd /d "%~dp0"

REM ------------------------------------------------------------------
REM  Este es el archivo que abre el equipo. Doble clic y ya.
REM
REM  No deja ventana: arranca con pythonw.exe, que corre sin consola, y
REM  esta ventanita se cierra sola en cuanto lo lanza. El navegador lo
REM  abre QA2 cuando el servidor responde de verdad.
REM
REM  Si algo falla, QA2 lo dice en un cuadro de dialogo y lo escribe en
REM  logs\qa2_startup.log. Eso es lo que le faltaba al lanzador .vbs
REM  que habia antes -- y que ademas la directiva de IT bloquea.
REM
REM  Para ver que pasa mientras arranca, usa run_qa2.bat: ese si deja
REM  ventana con todo lo que Streamlit imprime.
REM ------------------------------------------------------------------

REM El navegador del paquete. QA2 tambien lo deduce solo al
REM arrancar, asi que esto es solo por si alguien lanza algo a mano
REM desde aqui.
if exist "browsers" set "PLAYWRIGHT_BROWSERS_PATH=%CD%\browsers"

if exist "python\pythonw.exe" (
    start "" "%CD%\python\pythonw.exe" "%CD%\scripts\start_qa2.py" 8501
    exit /b 0
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" "%CD%\.venv\Scripts\pythonw.exe" "%CD%\scripts\start_qa2.py" 8501
    exit /b 0
)

REM Sin pythonw no se puede arrancar sin ventana. Mejor arrancar con
REM ella que no arrancar.
echo QA2 va a abrirse en una ventana: no encuentro pythonw.exe.
echo.
call "%~dp0run_qa2.bat"
