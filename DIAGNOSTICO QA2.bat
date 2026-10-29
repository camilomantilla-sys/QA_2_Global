@echo off
setlocal

cd /d "%~dp0"

REM ------------------------------------------------------------------
REM  Para cuando QA2 "no abre" y no hay nada que mirar.
REM
REM  Doble clic, y deja en logs\diagnostico.txt todo lo que hace falta
REM  para saber por que. Un archivo que mandar, en vez de una
REM  conversacion de diez mensajes preguntando que sale en pantalla.
REM
REM  No arregla nada y no toca nada: solo mira.
REM ------------------------------------------------------------------

if not exist "logs" mkdir "logs"
set "OUT=logs\diagnostico.txt"

echo QA2 - diagnostico> "%OUT%"
echo Fecha: %DATE% %TIME%>> "%OUT%"
echo Carpeta: %CD%>> "%OUT%"
echo.>> "%OUT%"

echo -- version --------------------------------------------------->> "%OUT%"
if exist "VERSION" (type "VERSION" >> "%OUT%") else (echo NO hay archivo VERSION>> "%OUT%")
echo.>> "%OUT%"

echo -- que hay en la carpeta -------------------------------------->> "%OUT%"
if exist "python\pythonw.exe" (echo python\pythonw.exe   SI>> "%OUT%") else (echo python\pythonw.exe   NO>> "%OUT%")
if exist "python\python.exe"  (echo python\python.exe    SI>> "%OUT%") else (echo python\python.exe    NO>> "%OUT%")
if exist "browsers"           (echo browsers\            SI>> "%OUT%") else (echo browsers\            NO>> "%OUT%")
if exist "ui\app_v2.py"       (echo ui\app_v2.py         SI>> "%OUT%") else (echo ui\app_v2.py         NO>> "%OUT%")
if exist "scripts\start_qa2.py" (echo scripts\start_qa2.py SI>> "%OUT%") else (echo scripts\start_qa2.py NO>> "%OUT%")
echo.>> "%OUT%"

echo -- procesos de QA2 -------------------------------------------->> "%OUT%"
tasklist /FI "IMAGENAME eq pythonw.exe" /NH >> "%OUT%" 2>&1
tasklist /FI "IMAGENAME eq python.exe" /NH >> "%OUT%" 2>&1
echo.>> "%OUT%"

echo -- el PID que anoto esta carpeta ------------------------------>> "%OUT%"
if exist "logs\qa2.pid" (type "logs\qa2.pid" >> "%OUT%") else (echo no hay logs\qa2.pid>> "%OUT%")
echo.>> "%OUT%"
echo.>> "%OUT%"

echo -- el puerto 8501 --------------------------------------------->> "%OUT%"
netstat -ano ^| findstr ":8501" >> "%OUT%" 2>&1
echo.>> "%OUT%"

echo -- ultimo arranque -------------------------------------------->> "%OUT%"
if exist "logs\qa2_startup.log" (
    type "logs\qa2_startup.log" >> "%OUT%"
) else (
    echo NO hay logs\qa2_startup.log.>> "%OUT%"
    echo Quiere decir que QA2 nunca llego a arrancar: el .bat no pudo>> "%OUT%"
    echo lanzar python. Casi siempre es el .zip bloqueado por Windows:>> "%OUT%"
    echo clic derecho en el .zip ^> Propiedades ^> Desbloquear, y volver>> "%OUT%"
    echo a extraer.>> "%OUT%"
)
echo.>> "%OUT%"

echo.
echo   Listo. El diagnostico quedo en:
echo   %CD%\%OUT%
echo.
echo   Mandale ESE archivo a quien te compartio QA2.
echo.
start "" notepad "%OUT%"
timeout /t 4 >nul
