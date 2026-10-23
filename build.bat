@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --noconsole --onefile --name DSE_Scraper --icon "assets\DSE_Scraper.ico" --add-data "assets\DSE_Scraper.ico;assets" --collect-all customtkinter --collect-all playwright --add-data "corporate_actions.csv;." --add-data "investing_split_urls.csv;." --add-data "verified_splits.csv;." gui.py
if errorlevel 1 (echo Build failed & exit /b 1)
echo Created dist\DSE_Scraper.exe (launch it, then click Install / Repair Requirements to install Chromium)
pause
