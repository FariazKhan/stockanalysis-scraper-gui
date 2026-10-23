# DSE Stock Scraper — improved seven-sheet Excel exporter

A GUI for comma-separated Dhaka Stock Exchange trading codes and an inclusive **start/end year**. Uses StockAnalysis DSE financials, market history, cash dividends and the latest split statistic, plus locally verified historical split records. Outputs one `.xlsx` with **exactly seven sheets**, following `sample.xlsx`.

## For non-technical Windows users: launch and setup (NEW)

You do **not** need to type Python or Playwright commands to configure the app.

**If you have a built `DSE_Scraper.exe`:** Double-click the EXE, click **Install / Repair Requirements**, and wait for the setup terminal to report success. The EXE already has Python libraries packaged inside it. This setup downloads the **exact Chromium version required by the packaged Playwright**; it does **not** need a separately installed Python or pip. Keep the app open until setup finishes. On subsequent launches you normally won't need to repeat setup.

**If you are running the source ZIP:** Install Python 3.10+ from [python.org](https://www.python.org/downloads/) if it isn't on the computer. On Windows, double-click **`Start_DSE_Scraper.bat`** in the extracted project directory. It installs missing GUI imports and starts the app. Then click **Install / Repair Requirements** in the GUI. A Windows Command Prompt will open, install/update `requirements.txt`, and run `playwright install chromium` automatically. No typing is needed. If source dependencies are upgraded, close and reopen the GUI afterward.

The setup terminal displays download progress and any install errors. The GUI displays the final status; if something fails, **leave the terminal open to read the error**. The browser download requires internet and may be blocked by a firewall/proxy. **This does not download Python itself** for source users. It also cannot replace an organization's software-installation policies.

**The new Activity log** is at the bottom of the main GUI: it grows with the window, has a vertical scrollbar, and shows timestamped progress, errors, warnings, and saved file paths. Use **Copy all** to share a log, or **Clear** to reset the panel. Scrolling up to review earlier lines won't be interrupted by new messages. To keep the app responsive, the panel retains the most recent 2,000 log lines.

Manual fallback (if desired):

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python gui.py
```

Requires Python 3.10+ and a desktop environment to run *from source*. A packaged Windows EXE does not require a separate Python installation.

Authentication is optional for public StockAnalysis data. If your own StockAnalysis account permits additional history, click **Log in to StockAnalysis**, complete the login in the open Chromium window, and click OK in the GUI. The saved browser session is kept **outside the project** in your OS user config directory. Keep it private. You must have legitimate access to any paid features; this app does not bypass paywalls.

Enter `BRACBANK, CITYBANK, BXPHARMA`, select the years, select the `.xlsx` destination and click **Start extraction**. The GUI continues responding during the run. The project caches company-specific network results for 12 hours; tick **Refresh** to bypass the cache. Polite parallel requests (two tickers concurrently) and retry/backoff improve throughput.

The output directory defaults to `output/portfolio.xlsx` when run from Python. If bundled as a desktop executable, generated working files default to `~/Documents/DSEStockScraper/`. The chosen output path takes precedence.

## Worksheet rules

1. **Stock Selection**: vertical company blocks; header `Year | P/E | NAV | ROA | ROE | NPM | EPS`. The selected years are always present, oldest first. NAV uses reported **Book Value Per Share** (`bvps`, BDT/share) from the balance sheet; if absent it tries equity/shares. ROA and ROE are fractions displayed as percent; NPM = net income attributable to common shareholders / revenue. P/E and diluted EPS are taken from annual fiscal year data. TTM is excluded.
2. **Price Data**: last available daily *closing price* of each calendar month, BDT. It is **not** an average, OHLC, adjusted close, or a guaranteed historical unadjusted market price.
3. **Cash Dividend**: BDT/share in the month of the **ex-dividend date**, summed if multiple distributions fall in one month. StockAnalysis dividend values may be split-adjusted.
4. **Stock Dividend**: verified stock/bonus percentages imported from `corporate_actions.csv`. No cash-to-stock conversion.
5. **Right Share Ratio**: verified rights shares per existing share from `corporate_actions.csv`. Example: `1R:2` = `0.5`.
6. **Right Share Offer Price**: verified rights subscription price BDT/share, sourced from that same file.
7. **Split**: split factor `new shares / old shares` from the StockAnalysis latest-split statistic, bundled verified historical events, previous imported split caches, or `corporate_actions.csv`. Example: 1.1:1 = `1.10`; 2-for-1 = `2`. Only the months in your requested year range are populated.

**Sheets 2–7 use exactly the same company column order**: grouped alphabetically by StockAnalysis industry, then company name. First header row shows industries, second row company names. Every month in the selected inclusive year range appears, including months without observations. Year appears only on the first row of that year.

### Stock-split data without Investing.com HTTP 403 (Sheet 7)

**Normal extraction no longer requests Investing.com.** It may block automated page requests with HTTP 403; the app respects that decision instead of retrying with alternative identities, IP addresses or browser fingerprints. Its historical data is still useful as a **manual verification reference**, but it is not the active crawler.

Instead, for every ticker the application fetches `https://stockanalysis.com/quote/dse/<TICKER>/statistics/`, which often includes **Last Split Date** and **Split Ratio**. That page only lists the **latest** split, not every historical split. Results are cached for up to 24 hours in `data/<TICKER>/<TICKER>_stockanalysis_latest_split.csv`. Unavailable or unparseable pages do not overwrite previously saved split records. If a ticker has no known events in the requested years, the cells remain blank.

Older records can be supplied by editable `corporate_actions.csv`, bundled `verified_splits.csv`, or a pre-existing verified historical split cache imported by the previous version. Records for the same ticker and exact event date are deduplicated. User-supplied CSV events have highest priority.

The bundled `verified_splits.csv` contains the following **separate** companies' histories, verified against the public Investing.com split tables:

- **BSRMLTD — Bangladesh Steel Re-Rolling Mills Limited:** March 6, 2016 (`1.10`), September 10, 2017 (`1.10`), October 22, 2018 (`1.10`). [Source](https://www.investing.com/equities/bangladesh-steel-re-rolling-mills-historical-data-splits)
- **BSRMSTEEL — BSRM Steels Limited:** May 6, 2010 (`1.15`); April 13, 2011 (`1.20`); December 4, 2011 (`10.00`); March 13, 2013 (`1.05`); October 9, 2017 (`1.10`); October 22, 2018 (`1.10`). [Source](https://www.investing.com/equities/bsrm-steels-ltd-historical-data-splits)

**These are distinct DSE tickers.** Splits and bonus issues are not conflated automatically with Sheet 4. An absent event in the requested year range is not treated as a verified `1.0` split factor. The included `investing_split_urls.csv` remains for historical/reference purposes; editing it no longer triggers requests to Investing.com. For additional earlier splits of other tickers, the app still needs verified entries in `corporate_actions.csv`.

### Corporate actions: how to populate sheets 4–7

StockAnalysis's dividend page reports **cash amounts**, not a dependable, numeric DSE bonus share/rights/split history. Amarstock rights announcements can contain rights ratios and offer prices, but its news articles are not a reliable structured corporate-action feed, and Investing.com URLs cannot reliably be generated by substituting tickers or company names. **Stock dividends and rights issues still require user-confirmed rows in the CSV**; Sheet 7 instead uses StockAnalysis latest-split data and the locally verified historical records described above.

Edit `corporate_actions.csv` in the project directory (or `Documents/DSEStockScraper/` for a packaged EXE). Example rows (illustrative only — **do not treat as real events**):

```csv
ticker,event_type,date,ratio,offer_price,source_url,notes
EXAMPLE,stock_dividend,2025-04-20,10%,,https://example.org/filing,10 percent bonus shares
EXAMPLE,rights,2025-05-15,1R:2,20,https://example.org/filing,one rights share for two held
EXAMPLE,split,2025-06-01,2:1,,https://example.org/filing,two shares for one
```

- `date` is the action's *effective/ex-entitlement date*, not the press release date. Use `YYYY-MM-DD`.
- `ratio`: bonus-share percentage (`10%` or `10`, meaning ten percent); rights `1R:2`, `1:2`, or decimal `0.5`; split `2:1` or decimal `2`.
- `offer_price`: required only when a rights offer price is known. If blank, the rights ratio is still included and the offer-price cell remains blank.
- If there are multiple events of the same type in a month, stock dividends and rights ratios are added, split multipliers multiplied; the **last rights offer price** is used.
- Only rows matching your requested tickers and dates are applied. Source URL is for your audit records. Do not enter assumptions. Verified user CSV records override a scraped record for the same ticker, date and event type; duplicates are never multiplied.
- **Blank is intentionally different from zero or one.** Empty event cells mean "not verified / not in source"; the exporter does not invent zero dividends or a `1` split factor for every month.

## Reliability / limitations

- DSE data availability is determined by your StockAnalysis subscription and its current pages; older FY data may be blocked or missing. This program does not circumvent those restrictions. A selected year with no accessible data remains blank. **BSRMSTEEL currently shows annual financials through FY 2025**, not FY 2026. The current/TTM column cannot substitute for a completed FY 2026 annual figure.
- If a company is not found or the company profile is unavailable, it is labeled with its ticker and grouped under **Unknown Industry** instead of incorrectly assigned an industry.
- Network errors and access restrictions are reported in `<workbook>_warnings.txt` beside the workbook. A completed workbook is not a guarantee that every company/field is available.
- The exporter reads sanitized JSON: any StockAnalysis SvelteKit session node is discarded instead of writing tokens to disk. Do not redistribute your session files. **The original uploaded ZIP included browser cookies; none are packaged in this update.** Consider signing out and revoking that old session if the archive was shared elsewhere.
- Website response formats can change. A cached normalized dataset is stored under `data/<TICKER>/` to help diagnosis.

## CLI / offline export

After a GUI run, you can regenerate Excel without downloading:

```bash
python excel_exporter.py --tickers BRACBANK,CITYBANK --start-year 2021 --end-year 2025 --output output/portfolio.xlsx
```

The GUI uses `pipeline.py` → `crawler.py` → `stock_data.py` → `excel_exporter.py`. Original `portfolio_builder.py`, `portfolio_analyzer.py`, and standalone extract scripts are retained as **legacy reference tools**, not used by the new pipeline.

## Testing

```bash
python -m unittest discover -s tests -v
```

The tests verify period selection, financial calculations, industry ordering, monthly pivots, corporate-action import and seven-sheet workbook structure without contacting external services.

## Packaging

Use `build.bat` (Windows) or `build-mac.sh` (macOS) to bundle the GUI. These scripts include `verified_splits.csv`, a legacy `investing_split_urls.csv` reference, and the blank user `corporate_actions.csv`. The packaged app copies the editable mapping and actions CSV to `~/Documents/DSEStockScraper` on first run without overwriting existing files. The `verified_splits.csv` reference is read from packaged resources.

A Playwright Chromium browser installation is still required on target machines. The packaged app points Playwright at a persistent browser cache, not PyInstaller's temporary `_MEI` directory. **The GUI's Install / Repair Requirements button now performs that download for Windows EXEs using Playwright's bundled Node/CLI**, without needing `python`, `pip` or an administrator terminal on the target PC (ordinary user directory write access is still required). The first-time source installer uses the current Python interpreter instead. `Start_DSE_Scraper.bat` additionally bootstraps missing *GUI packages* for source users.

**Rebuild the Windows EXE** using `build.bat` if you distribute a packaged binary. The previously compiled EXE does not contain the button or the scrollable log. Build/test on Windows for Windows, and macOS for macOS; cross-compilation is not provided. The auto-terminal setup button currently targets Windows; macOS/Linux users can use the manual commands above.

The Activity log shows operation messages and warnings. The external installer terminal shows installation output; it is not automatically duplicated line-by-line into the GUI log.


## DSE Stock Scraper application icon (Windows)

The project includes a custom app icon:

- `assets/DSE_Scraper.ico` — multi-resolution Windows executable/window icon
- `assets/DSE_Scraper.png` — large PNG for branding and shortcuts
- `assets/DSE_Scraper.svg` — editable vector source

**No icon setup is required:** `build.bat` already specifies
`--icon "assets\DSE_Scraper.ico"`, and bundles the `.ico` using
`--add-data "assets\DSE_Scraper.ico;assets"` so the CustomTkinter window
also displays it. The GUI applies the icon via `iconbitmap` on Windows.

To build or rebuild the application, double-click `build.bat` on **Windows**
and wait for `dist\DSE_Scraper.exe` to appear. This requires Python and
Internet access for the build-machine dependencies. The resulting EXE is
bundled but Playwright Chromium still needs to be installed on the user PC
from the app's **Install / Repair Requirements** button.

To update an existing EXE, you **must rebuild** it. Copying an `.ico` alongside
an already-built EXE does not replace the icon embedded in it. Windows
Explorer can cache the old icon; if so, refresh Explorer or change the
EXE filename when checking the result.

For a manual PyInstaller build, add:

```bat
--icon "assets\DSE_Scraper.ico" --add-data "assets\DSE_Scraper.ico;assets"
```

The icon is visual branding only and does not change scraping behavior.
