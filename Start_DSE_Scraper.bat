@echo off
setlocal
cd /d "%~dp0"
title Starting DSE Stock Scraper
where py >nul 2>nul
if not errorlevel 1 (
  set "PY=py"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python is not installed or cannot be found.
    echo Please install Python 3.10 or newer from https://www.python.org/downloads/
    echo Then double-click this file again.
    pause
    exit /b 1
  )
  set "PY=python"
)
%PY% -c "import customtkinter, playwright, openpyxl" >nul 2>nul
if errorlevel 1 (
  echo Installing GUI Python dependencies for the first launch...
  %PY% -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 (
    echo Could not install Python dependencies. Check your internet connection.
    pause
    exit /b 1
  )
)
%PY% "%~dp0gui.py"
if errorlevel 1 (
  echo The app was unable to start. Please read the message above.
  pause
)
