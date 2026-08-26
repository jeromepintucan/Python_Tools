@echo off
REM Build script for Process Keeper on Windows.
REM Run this from a Windows machine that has Python 3.13+ installed.

python -m pip install --upgrade pip
python -m pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed --name "ProcessKeeper" process-keeper.py

echo.
echo Build complete. Find ProcessKeeper.exe in the "dist" folder.
pause
