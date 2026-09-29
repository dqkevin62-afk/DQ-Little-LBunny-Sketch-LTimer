@echo off
rem Development helper: start the desktop pet (topmost, bottom-right) + local proxy
rem without opening a browser window. Double-click to run.
python "%~dp0run-pet.py" %*
if errorlevel 1 pause
