@echo off
rem ==============================================================================
rem QuantOS Studio — Desktop Launcher
rem Launches QuantOS in dedicated standalone application window mode.
rem ==============================================================================
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    set "PYTHON_EXE=.venv\Scripts\pythonw.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

start "" "%PYTHON_EXE%" quantos_studio.py %*
exit /b 0
