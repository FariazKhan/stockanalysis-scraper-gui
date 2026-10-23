import os
import pandas as pd
import numpy as np
import subprocess
import sys

DATA_DIR = "data"
OUTPUT_DIR = "output"


os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_command(command):

    print("\nRunning:")
    print(command)

    result = subprocess.run(
        command,
        shell=True
    )

    if result.returncode != 0:
        print("FAILED:", command)

def safe_read(path):

    try:
        df = pd.read_csv(path)

        if df.empty:
            return None

        return df

    except:
        return None



def cagr(start, end, years):

    try:
        if start <= 0 or end <= 0:
            return None

        return (end/start)**(1/years)-1

    except:
        return None


def process_ticker(ticker):

    folder = os.path.join(DATA_DIR, ticker)

    row = {
        "ticker": ticker
    }


    # -----------------
    # RATIOS
    # -----------------

    ratio_file = os.path.join(
        folder,
        f"{ticker}_ratios.csv"
    )

    ratios = safe_read(ratio_file)


    if ratios is not None and len(ratios) > 0:

        latest = ratios.iloc[0]

        for col in [
            "marketcap",
            "pe",
            "peForward",
            "pb",
            "ps",
            "evrevenue",
            "evebitda",
            "pfcf",
            "dividendyield",
            "roe",
            "roa",
            "roic",
            "roce",
            "debtequity",
            "debtebitda",
            "currentratio",
            "quickRatio"
        ]:

            row[col] = latest.get(col, np.nan)


        row["ratio_available"] = True


    else:

        row["ratio_available"] = False



    # -----------------
    # FINANCIALS
    # -----------------

    fin_file = os.path.join(
        folder,
        f"{ticker}_financials.csv"
    )


    fin = safe_read(fin_file)


    if fin is not None and len(fin) > 0:


        latest = fin.iloc[0]


        row["revenue"] = latest.get(
            "revenue",
            np.nan
        )

        row["gross_profit"] = latest.get(
            "gp",
            np.nan
        )

        row["operating_income"] = latest.get(
            "opinc",
            np.nan
        )

        row["net_income"] = latest.get(
            "netinccmn",
            np.nan
        )

        row["eps"] = latest.get(
            "epsdil",
            np.nan
        )


        try:

            row["gross_margin"] = (
                row["gross_profit"] /
                row["revenue"]
            )

            row["operating_margin"] = (
                row["operating_income"] /
                row["revenue"]
            )

            row["net_margin"] = (
                row["net_income"] /
                row["revenue"]
            )

        except:

            pass



        # Growth

        if len(fin) >= 5:

            old = fin.iloc[-1]
            new = fin.iloc[0]


            row["revenue_cagr"] = cagr(
                old["revenue"],
                new["revenue"],
                4
            )

            row["net_income_cagr"] = cagr(
                old["netinccmn"],
                new["netinccmn"],
                4
            )

            row["eps_cagr"] = cagr(
                old["epsdil"],
                new["epsdil"],
                4
            )


        row["financial_available"] = True


    else:

        row["financial_available"] = False



    # -----------------
    # PRICE HISTORY
    # -----------------

    history_file = os.path.join(
        folder,
        f"{ticker}_history.csv"
    )


    history = safe_read(history_file)


    if history is not None and len(history) > 0:


        history["date"] = pd.to_datetime(
            history["date"]
        )

        history = history.sort_values(
            "date"
        )


        prices = history["close"]


        latest_price = prices.iloc[-1]


        row["current_price"] = latest_price


        # 52 week data

        one_year = history[
            history["date"] >= (
                history["date"].max()
                -
                pd.Timedelta(days=365)
            )
        ]


        if len(one_year):

            row["52w_high"] = one_year["close"].max()
            row["52w_low"] = one_year["close"].min()


        else:

            row["52w_high"] = np.nan
            row["52w_low"] = np.nan



        # Returns

        def get_return(days):

            cutoff = (
                history["date"].max()
                -
                pd.Timedelta(days=days)
            )


            old_data = history[
                history["date"] <= cutoff
            ]


            if len(old_data):

                old_price = old_data.iloc[-1]["close"]

                return (
                    latest_price /
                    old_price
                    -
                    1
                )

            return np.nan



        row["1m_return"] = get_return(30)
        row["3m_return"] = get_return(90)
        row["6m_return"] = get_return(180)
        row["1y_return"] = get_return(365)



        # Daily volatility

        returns = prices.pct_change()


        row["volatility"] = (
            returns.std()
            *
            np.sqrt(252)
        )


        row["history_available"] = True



    else:

        row["history_available"] = False



    return row


import crawler
import extract_ratios
import extract_financials
import extract_history
import extract_dividend
import asyncio

def build_portfolio():
    tickers = [x.strip() for x in open("tickers.txt") if x.strip()]
    results = []
    
    for i, ticker in enumerate(tickers, 1):
        print(f"\n{'#'*60}\n{i}/{len(tickers)} Processing {ticker}\n{'#'*60}")
        
        # Run crawler
        out_dir = os.path.join("data", ticker, "output")
        os.makedirs(out_dir, exist_ok=True)
        asyncio.run(crawler.run_crawler(ticker, out_dir))
        
        # Run extractors
        raw_file = os.path.join(out_dir, "raw_requests.json")
        
        # Ratios
        if os.path.exists(raw_file):
            r_res = extract_ratios.extract_ratios(raw_file)
            pd.DataFrame(r_res).to_csv(os.path.join("data", ticker, f"{ticker}_ratios.csv"), index=False)
            
            # Financials
            f_res = extract_financials.extract_financials(raw_file)
            pd.DataFrame(f_res).to_csv(os.path.join("data", ticker, f"{ticker}_financials.csv"), index=False)
            
            # History
            h_res = extract_history.extract_history(raw_file)
            pd.DataFrame(h_res).to_csv(os.path.join("data", ticker, f"{ticker}_history.csv"), index=False)
            
            # Dividends
            d_res = extract_dividend.extract_dividend(raw_file)
            d_out = os.path.join("data", ticker, f"{ticker}_dividend.csv")
            if d_res:
                pd.DataFrame(d_res).to_csv(d_out, index=False)
            else:
                pd.DataFrame(columns=['dt', 'amt', 'dec', 'record', 'pay']).to_csv(d_out, index=False)
                
        results.append(process_ticker(ticker))
        
    df = pd.DataFrame(results)
    df.to_csv(f"{OUTPUT_DIR}/portfolio_master.csv", index=False)
    
    df.filter(regex="pe|pb|ps|ev|marketcap|dividend").to_csv(f"{OUTPUT_DIR}/valuation.csv", index=False)
    df.filter(regex="roe|roa|roic|roce|margin|debt|ratio").to_csv(f"{OUTPUT_DIR}/profitability.csv", index=False)
    df.filter(regex="cagr").to_csv(f"{OUTPUT_DIR}/growth.csv", index=False)
    
    print("All outputs created.")

if __name__ == "__main__":
    build_portfolio()