@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto failed
echo Setup complete. Double-click Start Dictate.cmd to launch.
pause
exit /b 0
:failed
echo Setup failed. Install Python 3.11 or newer and check your internet connection.
pause
exit /b 1
