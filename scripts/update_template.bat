@echo off
setlocal enabledelayedexpansion
title Actualizar QA2

REM ------------------------------------------------------------------
REM  Va DENTRO del zip de actualizacion, en la raiz.
REM
REM  Existe porque "abre el zip y arrastra el contenido" no es lo que
REM  hace la gente: le dan a Extraer todo, que crea una carpeta con el
REM  nombre del zip, y la actualizacion se queda ahi sin aplicarse. Sin
REM  ningun error -- la carpeta existe, los archivos estan, y QA2 sigue
REM  con la version vieja.
REM
REM  Con esto se extrae donde sea y se hace doble clic.
REM ------------------------------------------------------------------

cd /d "%~dp0"

echo.
echo   ACTUALIZAR QA2
echo   ==============
echo.

REM Si QA2 esta corriendo, sus archivos estan en uso y la copia falla a
REM la mitad -- que es peor que no empezar.
tasklist /fi "imagename eq python.exe" 2>nul | find /i "python.exe" >nul
if not errorlevel 1 (
    echo   QA2 parece estar abierto.
    echo.
    echo   Cierra la ventana negra de QA2 ^(o usa "Stop QA2.vbs"^) y
    echo   vuelve a ejecutar este archivo. Con QA2 abierto, Windows no
    echo   deja reemplazar sus archivos.
    echo.
    pause
    exit /b 1
)

REM Encontrar la carpeta de QA2. Primero la que se arrastro encima,
REM despues las de al lado, y si no, se pregunta.
set "TARGET=%~1"

if not defined TARGET (
    for /d %%D in ("..\QA2-*-windows" "..\QA2-*" "..\QA_2_Global") do (
        if exist "%%~fD\ui\app_v2.py" if not defined TARGET set "TARGET=%%~fD"
    )
)

if not defined TARGET (
    echo   No encontre la carpeta de QA2 aqui al lado.
    echo.
    echo   Arrastra tu carpeta de QA2 ^(la que tiene run_qa2.bat dentro^)
    echo   encima de este archivo, o escribe su ruta completa:
    echo.
    set /p TARGET="   Carpeta de QA2: "
)

set "TARGET=%TARGET:"=%"

if not exist "%TARGET%\ui\app_v2.py" (
    echo.
    echo   Esa carpeta no parece ser QA2: no tiene ui\app_v2.py dentro.
    echo   Busca la que contiene run_qa2.bat.
    echo.
    pause
    exit /b 1
)

echo   QA2 encontrado en:
echo     %TARGET%
echo.
echo   Se van a reemplazar los archivos de codigo. NO se tocan:
echo     - python\        ^(el interprete^)
echo     - browsers\      ^(el navegador^)
echo     - config\        ^(tu sesion de Innovid^)
echo     - logs\
echo.
set /p CONFIRM="   Continuar? (S/N): "
if /i not "%CONFIRM%"=="S" (
    echo   Cancelado, no se toco nada.
    pause
    exit /b 0
)

echo.
echo   Copiando...

REM /E subcarpetas, /Y sin preguntar, /Q sin listar cada archivo.
REM Se excluye este .bat, que no es parte de QA2.
robocopy "%~dp0." "%TARGET%" /E /NFL /NDL /NJH /NJS /NP /XF "%~nx0" >nul
set RC=%errorlevel%

REM robocopy: 0-7 es exito, 8 o mas es fallo. No es como los demas.
if %RC% GEQ 8 (
    echo.
    echo   Algo fallo al copiar ^(codigo %RC%^).
    echo   Revisa que QA2 este cerrado y vuelve a intentar.
    echo.
    pause
    exit /b 1
)

for /f "usebackq delims=" %%V in ("%TARGET%\VERSION") do set "NEWVER=%%V"

echo.
echo   Listo. QA2 quedo en la version %NEWVER%.
echo.
echo   Abrelo con run_qa2.bat. En la barra lateral, "What's new in
echo   QA2" dice que cambio.
echo.
echo   Esta carpeta ya se puede borrar.
echo.
pause
