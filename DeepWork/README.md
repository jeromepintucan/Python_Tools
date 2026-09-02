# Process Keeper — Build Instructions

Your `process-keeper.py` code is unchanged. These files just wrap it with
PyInstaller so it becomes a standalone double-clickable app. Activate,
Deactivate, and the running timer all still work exactly as written.

## Important: build on the OS you're targeting

PyInstaller does not cross-compile. To get a `.exe` you must run the build
on Windows; to get a `.app` you must run it on a Mac; a Linux binary must be
built on Linux. Pick the script below that matches the machine you're on.

## Files included

- `process-keeper.py` — your original script, untouched
- `build_windows.bat` — builds `ProcessKeeper.exe` on Windows
- `build_macos.sh` — builds `ProcessKeeper.app` on macOS
- `build_linux.sh` — builds a `ProcessKeeper` binary on Linux

## Windows

1. Install Python 3.13+ from python.org (check "Add python.exe to PATH"
   during install).
2. Put `process-keeper.py` and `build_windows.bat` in the same folder.
3. Double-click `build_windows.bat` (or run it from a terminal).
4. When it finishes, find `ProcessKeeper.exe` inside the new `dist` folder.
   That single file is your app — copy it anywhere and run it directly,
   no Python install needed on the machine that runs it.

## macOS

1. Install Python 3.13+ (python.org installer, or `brew install python`).
2. Put `process-keeper.py` and `build_macos.sh` in the same folder.
3. In Terminal, in that folder, run:
   ```
   chmod +x build_macos.sh
   ./build_macos.sh
   ```
4. Find `ProcessKeeper.app` inside the new `dist` folder. Double-click to run.
   (First launch may need a right-click > Open, since it isn't notarized.)

## Linux

1. Make sure Tk is installed, e.g. `sudo apt install python3-tk`.
2. Put `process-keeper.py` and `build_linux.sh` in the same folder.
3. Run:
   ```
   chmod +x build_linux.sh
   ./build_linux.sh
   ```
4. Find the `ProcessKeeper` executable inside the new `dist` folder.

## New: optional "keep chat status active" checkbox

Sleep prevention (`SetThreadExecutionState`) and Teams/chat idle detection
are two separate things — sleep prevention stops the OS from sleeping, but
Teams marks you Away based on actual keyboard/mouse input, which the base
app never simulated.

There is now an unchecked-by-default checkbox: "Also keep chat status
(e.g. Teams) active." When you check it and Activate, the app additionally
nudges the mouse by 1 pixel and immediately back, roughly once a minute,
purely to reset that idle timer. It only runs while protection is active,
and turning the checkbox off (or deactivating) stops it immediately.

- Windows: built in, no extra install needed.
- macOS: requires `cliclick` (`brew install cliclick`) for this specific
  feature; sleep prevention itself needs nothing extra.
- Linux: requires `xdotool` (`sudo apt install xdotool`) for this feature.

## What `--onefile --windowed` does

- `--onefile`: bundles everything into a single executable file.
- `--windowed`: no console/terminal window pops up alongside the GUI
  (on Windows this is the same as `--noconsole`).

## Notes

- I test-built the Linux version here to confirm the script packages
  cleanly with no code changes — it built successfully.
- On Windows, some antivirus tools flag PyInstaller-built exe files as
  suspicious purely because of how PyInstaller packages Python apps (a
  well-known false positive). If that happens, it's not something wrong
  with your code.
- If you'd like a custom icon, add `--icon=youricon.ico` (Windows) or
  `--icon=youricon.icns` (macOS) to the pyinstaller command in the
  relevant build script.
