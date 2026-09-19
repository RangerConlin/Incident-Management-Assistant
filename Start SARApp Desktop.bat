@echo off
setlocal

set "APP_DIR=%~dp0"
set "LOCAL_PY311=%LocalAppData%\Programs\Python\Python311\python.exe"

if exist "%LOCAL_PY311%" (
    set "PYTHON_EXE=%LOCAL_PY311%"
    set "PYTHON_ARGS="
    goto run_app
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3.11"
        goto run_app
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    set "PYTHON_ARGS="
    goto run_app
)

echo No usable Python was found.
echo Install Python 3.11, then run this launcher again.
pause
exit /b 1

:run_app
cd /d "%APP_DIR%"
"%PYTHON_EXE%" %PYTHON_ARGS% "%APP_DIR%main.py"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo SARApp exited with code %EXIT_CODE%.
    pause
)
exit /b %EXIT_CODE%
