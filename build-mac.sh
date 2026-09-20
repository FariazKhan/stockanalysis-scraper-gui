#!/bin/bash
echo "===================================================="
echo "  Building DSE Share Price Scraper (macOS)"
echo "===================================================="
echo ""

echo "1. Installing required build tools..."
pip3 install pyinstaller customtkinter playwright pandas openpyxl numpy

echo ""
echo "2. Ensuring Playwright browsers are installed..."
playwright install chromium

echo ""
echo "3. Compiling the application..."
# --noconsole hides the terminal window
# --onefile creates a single executable
# --windowed creates a macOS .app bundle
pyinstaller --noconsole --onefile --windowed --name "DSE_Scraper" gui.py

echo ""
echo "===================================================="
echo "BUILD COMPLETE!"
echo "You can find your compiled app in the 'dist' folder:"
echo "dist/DSE_Scraper.app (and dist/DSE_Scraper UNIX executable)"
echo "===================================================="
