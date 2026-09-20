@echo off
echo ====================================================
echo   Building DSE Share Price Scraper Executable
echo ====================================================
echo.

echo 1. Installing required build tools...
pip install pyinstaller customtkinter playwright pandas openpyxl numpy

echo.
echo 2. Ensuring Playwright browsers are installed...
playwright install chromium

echo.
echo 3. Compiling the application into a single executable...
:: The --noconsole flag hides the background command prompt
:: The --onefile flag bundles everything into a single .exe
:: Playwright requires some extra hooks/data to bundle correctly
pyinstaller --noconsole --onefile --name "DSE_Scraper" gui.py

echo.
echo ====================================================
echo BUILD COMPLETE!
echo You can find your compiled app in the "dist" folder:
echo dist\DSE_Scraper.exe
echo ====================================================
pause
