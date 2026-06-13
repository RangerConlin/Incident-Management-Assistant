@echo off
setlocal

set APP_NAME=SARAppServerConsole
set SPEC_FILE=packaging\SARAppServerConsole.spec
set EXE_PATH=dist\%APP_NAME%\%APP_NAME%.exe

echo Building SARApp Server Console...

if not exist "%SPEC_FILE%" (
    echo ERROR: PyInstaller spec file not found: %SPEC_FILE%
    goto :fail
)

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller is not installed in this Python environment.
    echo Install it with: python -m pip install pyinstaller
    goto :fail
)

echo Cleaning old build files...
if exist "build\%APP_NAME%" rmdir /s /q "build\%APP_NAME%"
if exist "dist\%APP_NAME%" rmdir /s /q "dist\%APP_NAME%"

echo Running PyInstaller...
pyinstaller --noconfirm --clean "%SPEC_FILE%"
if errorlevel 1 goto :fail

if not exist "%EXE_PATH%" (
    echo ERROR: Build finished but expected executable was not found:
    echo %EXE_PATH%
    goto :fail
)

echo Build complete:
echo %EXE_PATH%
echo.
echo Run "%EXE_PATH%" to launch the Server Console.
goto :done

:fail
echo.
echo SARApp Server Console build failed.
if /i "%SARAPP_NO_PAUSE%"=="1" exit /b 1
pause
exit /b 1

:done
if /i "%SARAPP_NO_PAUSE%"=="1" exit /b 0
pause
exit /b 0
