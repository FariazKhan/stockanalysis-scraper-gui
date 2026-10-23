import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys


def extract_history(ticker):

    raw_file = Path(
        f"data/{ticker}/output/raw_requests.json"
    )

    if not raw_file.exists():
        raise FileNotFoundError(
            f"Missing: {raw_file}"
        )


    with open(raw_file, encoding="utf-8") as f:
        requests = json.load(f)


    history_response = None


    for r in requests:
        url = r.get("url", "")

        if "history?type=chart" in url:
            history_response = r["response_body"]
            break


    if history_response is None:
        print("No history data found")
        return None


    prices = history_response.get("data")


    if not prices:
        print("Empty history data")
        return None


    rows = []


    for item in prices:

        timestamp = item[0]
        close = item[1]

        date = datetime.fromtimestamp(
            timestamp / 1000
        ).strftime("%Y-%m-%d")


        rows.append(
            {
                "date": date,
                "close": close
            }
        )


    df = pd.DataFrame(rows)


    # filter duplicate dates
    df = df.drop_duplicates(
        subset=["date"]
    )


    df = df.sort_values(
        "date"
    )


    output = Path(
        f"data/{ticker}/{ticker}_history.csv"
    )


    df.to_csv(
        output,
        index=False
    )


    print(
        f"Saved {output}"
    )


    print(df.head())
    print(df.tail())


    return df



if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(
            "Usage: python extract_history.py TICKER"
        )
        sys.exit()


    ticker = sys.argv[1]

    extract_history(ticker)