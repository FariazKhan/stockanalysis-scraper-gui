#!/bin/sh
set -e
python3 -m pip install -r requirements.txt pyinstaller
python3 -m playwright install chromium
python3 -m PyInstaller --noconfirm --clean --noconsole --onefile --windowed --name DSE_Scraper --collect-all customtkinter --collect-all playwright --add-data "corporate_actions.csv:." --add-data "investing_split_urls.csv:." --add-data "verified_splits.csv:." gui.py
echo 'Created dist/DSE_Scraper.app (requires Playwright Chromium on destination system)'
