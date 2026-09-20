import pandas as pd
import numpy as np
import os

OUTPUT_DIR = "output"
DATA_DIR = "data"

def create_excel(start_date=None, end_date=None):
    master_csv = os.path.join(OUTPUT_DIR, "portfolio_master.csv")
    if not os.path.exists(master_csv):
        print(f"Error: {master_csv} not found.")
        return

    portfolio_df = pd.read_csv(master_csv)
    tickers = portfolio_df["ticker"].dropna().unique()

    excel_path = os.path.join(OUTPUT_DIR, "portfolio.xlsx")

    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        
        # ---------------------------------------------------------
        # SHEET 1: Ratios
        # ---------------------------------------------------------
        ratios_rows = []
        
        for i, ticker in enumerate(tickers, 1):
            # Ticker Title Row
            ratios_rows.append([f"{i}. {ticker}", "", "", "", "", "", ""])
            # Header Row
            ratios_rows.append(["Year", "P/E", "NAV", "ROA", "ROE", "NPM", "EPS"])
            
            # Load ratios and financials
            ratio_file = os.path.join(DATA_DIR, ticker, f"{ticker}_ratios.csv")
            fin_file = os.path.join(DATA_DIR, ticker, f"{ticker}_financials.csv")
            
            if os.path.exists(ratio_file) and os.path.getsize(ratio_file) > 10:
                try:
                    r_df = pd.read_csv(ratio_file)
                except Exception:
                    r_df = pd.DataFrame()
            else:
                r_df = pd.DataFrame()
                
            if os.path.exists(fin_file) and os.path.getsize(fin_file) > 10:
                try:
                    f_df = pd.read_csv(fin_file)
                except Exception:
                    f_df = pd.DataFrame()
            else:
                f_df = pd.DataFrame()
                
            if not r_df.empty and not f_df.empty and 'fiscalYear' in r_df.columns and 'fiscalYear' in f_df.columns:
                merged = pd.merge(r_df, f_df, on="fiscalYear", how="left")
            elif not r_df.empty:
                merged = r_df
            elif not f_df.empty:
                merged = f_df
            else:
                merged = pd.DataFrame()
            
            # Sort by year ascending
            if not merged.empty and 'fiscalYear' in merged.columns:
                if start_date:
                    merged = merged[merged["fiscalYear"] >= start_date.year]
                if end_date:
                    merged = merged[merged["fiscalYear"] <= end_date.year]
                    
                merged = merged.sort_values("fiscalYear").dropna(subset=["fiscalYear"])
                
                for _, row in merged.iterrows():
                        year = row.get("fiscalYear")
                        pe = row.get("pe", np.nan)
                        pb = row.get("pb", np.nan)
                        last_close = row.get("lastCloseRatios", np.nan)
                        
                        nav = np.nan
                        if pd.notna(pb) and pd.notna(last_close) and pb != 0:
                            nav = last_close / pb
                            
                        roa = row.get("roa", np.nan)
                        roe = row.get("roe", np.nan)
                        
                        eps = row.get("epsdil", np.nan)
                        revenue = row.get("revenue", np.nan)
                        netinccmn = row.get("netinccmn", np.nan)
                        
                        npm = np.nan
                        if pd.notna(revenue) and pd.notna(netinccmn) and revenue != 0:
                            npm = netinccmn / revenue
                            
                        ratios_rows.append([year, pe, nav, roa, roe, npm, eps])
            
            # Spacer row
            ratios_rows.append(["", "", "", "", "", "", ""])
            
        ratios_sheet_df = pd.DataFrame(ratios_rows)
        ratios_sheet_df.to_excel(writer, sheet_name="Ratios", index=False, header=False)


        # ---------------------------------------------------------
        # SHEET 2: Price Data
        # ---------------------------------------------------------
        history_frames = []
        for ticker in tickers:
            hist_file = os.path.join(DATA_DIR, ticker, f"{ticker}_history.csv")
            if os.path.exists(hist_file) and os.path.getsize(hist_file) > 10:
                try:
                    hdf = pd.read_csv(hist_file)
                    if 'date' in hdf.columns and 'close' in hdf.columns:
                        hdf['ticker'] = ticker
                        hdf['date'] = pd.to_datetime(hdf['date'])
                        history_frames.append(hdf)
                except Exception:
                    pass
        
        if history_frames:
            all_history = pd.concat(history_frames, ignore_index=True)
            
            if start_date:
                all_history = all_history[all_history['date'] >= start_date]
            if end_date:
                all_history = all_history[all_history['date'] <= end_date]
                
            # Extract Year and Month Name
            all_history['Year'] = all_history['date'].dt.year
            all_history['Month'] = all_history['date'].dt.strftime('%B')
            all_history['MonthNum'] = all_history['date'].dt.month
            
            # For each month, we want the LAST closing price of that month.
            all_history = all_history.sort_values('date')
            monthly = all_history.groupby(['ticker', 'Year', 'MonthNum', 'Month'], as_index=False).last()
            
            # Pivot table: rows = (Year, MonthNum, Month), cols = ticker, values = close
            pivot = monthly.pivot_table(index=['Year', 'MonthNum', 'Month'], columns='ticker', values='close')
            
            # Sort index chronologically
            pivot = pivot.sort_index(level=['Year', 'MonthNum'])
            
            # Prepare output rows for Price Data
            price_rows = []
            
            # Row 0: Top Header (Sectors - we don't have them, so blank)
            top_header = ["", ""] + [""] * len(pivot.columns)
            price_rows.append(top_header)
            
            # Row 1: Columns (Years, Months, Tickers)
            col_header = ["Years", "Months"] + list(pivot.columns)
            price_rows.append(col_header)
            
            # Data rows
            current_year = None
            for idx, row in pivot.iterrows():
                year, month_num, month_name = idx
                
                # Only show year if it's the first time we've seen it
                display_year = year if year != current_year else np.nan
                current_year = year
                
                data_row = [display_year, month_name] + [row.get(t, np.nan) for t in pivot.columns]
                price_rows.append(data_row)
                
            price_sheet_df = pd.DataFrame(price_rows)
            price_sheet_df.to_excel(writer, sheet_name="Price Data", index=False, header=False)
        
        else:
            print("No history data found for Price Data sheet.")

        # ---------------------------------------------------------
        # SHEET 3: Cash Dividend
        # ---------------------------------------------------------
        div_frames = []
        for ticker in tickers:
            div_file = os.path.join(DATA_DIR, ticker, f"{ticker}_dividend.csv")
            if os.path.exists(div_file) and os.path.getsize(div_file) > 10:
                try:
                    ddf = pd.read_csv(div_file)
                    if 'dt' in ddf.columns and 'amt' in ddf.columns and not ddf.empty:
                        ddf['ticker'] = ticker
                        ddf['date'] = pd.to_datetime(ddf['dt'])
                        ddf['amt'] = ddf['amt'].astype(str).str.replace(' BDT', '', regex=False).astype(float)
                        div_frames.append(ddf)
                except Exception:
                    pass
        
        if div_frames:
            all_divs = pd.concat(div_frames, ignore_index=True)
            
            if start_date:
                all_divs = all_divs[all_divs['date'] >= start_date]
            if end_date:
                all_divs = all_divs[all_divs['date'] <= end_date]
                
            all_divs['Year'] = all_divs['date'].dt.year
            all_divs['Month'] = all_divs['date'].dt.strftime('%B')
            all_divs['MonthNum'] = all_divs['date'].dt.month
            
            # Pivot table: rows = (Year, MonthNum, Month), cols = ticker, values = amt
            if not all_divs.empty:
                monthly_div = all_divs.groupby(['ticker', 'Year', 'MonthNum', 'Month'], as_index=False).last()
                pivot_div = monthly_div.pivot_table(index=['Year', 'MonthNum', 'Month'], columns='ticker', values='amt')
                pivot_div = pivot_div.sort_index(level=['Year', 'MonthNum'])
                
                div_rows = []
                # Headers
                top_header_div = ["", ""] + [""] * len(pivot_div.columns)
                div_rows.append(top_header_div)
                col_header_div = ["Years", "Months"] + list(pivot_div.columns)
                div_rows.append(col_header_div)
                
                current_year_div = None
                for idx, row in pivot_div.iterrows():
                    year, month_num, month_name = idx
                    display_year = year if year != current_year_div else np.nan
                    current_year_div = year
                    data_row = [display_year, month_name] + [row.get(t, np.nan) for t in pivot_div.columns]
                    div_rows.append(data_row)
                    
                cash_div_sheet_df = pd.DataFrame(div_rows)
                cash_div_sheet_df.to_excel(writer, sheet_name="Cash Dividend", index=False, header=False)
                
                # Sheet 4: Stock Dividend (same format, empty data as we don't have it)
                stock_div_rows = [top_header_div, col_header_div]
                stock_div_sheet_df = pd.DataFrame(stock_div_rows)
                stock_div_sheet_df.to_excel(writer, sheet_name="Stock Dividend", index=False, header=False)
            else:
                print("No dividend data within the 2021-2026 range.")
        else:
            print("No dividend data found.")

    print(f"Successfully generated {excel_path} matching sample.xlsx structure")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", help="Start date in DD-MM-YYYY format")
    parser.add_argument("--end-date", help="End date in DD-MM-YYYY format")
    args = parser.parse_args()
    
    start_dt = pd.to_datetime(args.start_date, format="%d-%m-%Y") if args.start_date else None
    end_dt = pd.to_datetime(args.end_date, format="%d-%m-%Y") if args.end_date else None
    
    create_excel(start_dt, end_dt)
