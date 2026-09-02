@echo off
setlocal

REM Build script for DeepWork on Windows.
REM Run this from a Windows machine that has Python 3.13+ installed.

cd /d "%~dp0"

echo Installing or updating PyInstaller...
python -m pip install --upgrade pyinstaller

if errorlevel 1 (
    echo.
    echo Failed to install or update PyInstaller.
    pause
    exit /b 1
)

echo.
echo Removing previous build files...

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "DeepWork.spec" del /f /q "DeepWork.spec"

echo.
echo Building DeepWork.exe...

python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "DeepWork" ^
    "DeepWork.py"

if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    echo.
    echo If Access is denied, close DeepWork.exe and make sure
    echo OneDrive is not locking the build folder.
    pause
    exit /b 1
)

echo.
echo BUILD SUCCESSFUL.
echo Find "DeepWork.exe" inside the "dist" folder.
echo.

pause