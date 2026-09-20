
# 📈 Stockanalysis Scraper

  
A standalone GUI application to effortlessly extract fundamental data, financial ratios, dividends, and historical prices for stocks from StockAnalysis. The project was built on top of https://github.com/ZAIDMOHD777/stockanalysis .

  

No coding, terminal commands, or complicated setups required!

  

## ✨ Features

-  **Graphical Interface**: Clean, modern dark-mode UI built with CustomTkinter.

-  **Interactive Authentication**: Click a button to securely log into StockAnalysis via an automated browser window. The app perfectly captures and manages your session automatically, session info is stored locally in your device.

-  **Custom Date Ranges**: Filter your extracted historical and dividend data to specific date windows effortlessly.

-  **Full Pipeline Automation**: Runs the crawler, ratio extractors, metric analyzers, and Excel pivoting engine silently in the background.

-  **Output**: Beautifully formatted, multi-sheet `portfolio.xlsx` directly matching professional analytics templates.

## 🚀 How to Run Locally (Source)

If you want to run the python script directly from the source code:

  

1.  **Install dependencies:**

```bash

pip install customtkinter playwright pandas openpyxl numpy

playwright install chromium

```

2.  **Run the App:**

```bash

python gui.py

```

  

## 🛠️ How to Compile (Build your own Executable)

You can package this entire application into a single, double-clickable executable (no Python required for your end users).

  

### Windows

Just run the included batch script:

```bash

build.bat

```

Your compiled `.exe` will be generated in the `dist/` folder.

  

### macOS

Run the included bash script:

```bash

chmod  +x  build-mac.sh

./build-mac.sh

```

Your compiled `.app` bundle will be generated in the `dist/` folder.

  

## ☁️ Automated GitHub Releases (CI/CD)

This project is configured with GitHub Actions to automatically compile and release binaries for both Windows and Mac in the cloud.

  

To trigger an automatic build and release:

```bash

git  tag  v1.0.0

git  push  origin  v1.0.0

```

Check the repository's **Releases** page to download your fresh executables!

  

## 📁 Output Structure

When extraction is complete, the app generates an `output/portfolio.xlsx` file containing 4 sheets:

1.  **Ratios**: Stacked vertical fundamental ratios (P/E, NAV, ROA, ROE, NPM, EPS).

2.  **Price Data**: A chronological pivot table of all selected tickers' closing prices.

3.  **Cash Dividend**: A chronological pivot table of historical cash dividend distributions.

4.  **Stock Dividend**: Formatted template for stock dividend tracking.


  ![Screenshot-1](https://github.com/FariazKhan/stockanalysis-scraper-gui/screenshots/1.png)

  ![Screenshot-2](https://github.com/FariazKhan/stockanalysis-scraper-gui/screenshots/2.png)

  ![Screenshot-3](https://github.com/FariazKhan/stockanalysis-scraper-gui/screenshots/3.png)
