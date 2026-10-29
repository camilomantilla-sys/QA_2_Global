@echo off
setlocal

cd /d "%~dp0"

REM ------------------------------------------------------------------
REM  Detiene QA2.
REM
REM  Era un .vbs hasta que la directiva de IT de WPP resulto bloquear
REM  Windows Script Host: "This script is blocked by IT policy". Un
REM  .bat no lo bloquea nadie.
REM
REM  Encuentra QA2 por el PID que la propia app deja escrito en
REM  logs\qa2.pid. Ni por puerto (se mueve al de al lado si el 8501
REM  esta ocupado) ni con wmic (Windows 11 ya no lo trae).
REM ------------------------------------------------------------------

if not exist "logs\qa2.pid" (
    echo QA2 no esta corriendo.
    echo.
    timeout /t 3 >nul
    exit /b 0
)

set /p QA2_PID=<"logs\qa2.pid"

REM Un PID viejo puede haberlo reutilizado Windows para otra cosa.
REM Comprobar que sigue siendo un python antes de matar nada.
REM
REM "python", no "python.exe": el lanzador sin ventana arranca con
REM pythonw.exe, que es el que usa el equipo. Filtrando por python.exe
REM esto contestaba "QA2 no esta corriendo", borraba el PID y dejaba la
REM app viva -- con la carpeta abierta, que Windows entonces no deja ni
REM borrar. O sea: el boton de detener no detenia nada.
tasklist /FI "PID eq %QA2_PID%" /NH 2>nul | find /i "python" >nul
if errorlevel 1 (
    echo QA2 no esta corriendo.
    del "logs\qa2.pid" 2>nul
    echo.
    timeout /t 3 >nul
    exit /b 0
)

taskkill /F /PID %QA2_PID% >nul 2>&1
if errorlevel 1 (
    echo No se pudo detener QA2 ^(PID %QA2_PID%^).
    echo Abre el Administrador de tareas y termina ese proceso.
    echo.
    pause
    exit /b 1
)

del "logs\qa2.pid" 2>nul
echo QA2 se detuvo.
echo.
timeout /t 3 >nul
