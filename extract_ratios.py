import json
import pandas as pd
import os
import sys

def extract_ratios(filename):
    with open(filename, encoding='utf-8') as f:
        raw = json.load(f)

    response = next((x['response_body'] for x in raw if 'financials/ratios/__data.json' in x['url']), None)
    if response is None:
        raise Exception('Ratios JSON not found')

    data = next((n['data'] for n in response.get('nodes', []) if isinstance(n, dict) and isinstance(n.get('data'), list) and len(n.get('data')) > 200), None)

    if data is None:
        print('No usable ratio data node found')
        return {}

    columns = next((x for x in data if isinstance(x, dict) and 'pe' in x and 'roe' in x), None)

    if columns is None:
        print('No ratio table available')
        return {}

    result = {}
    for metric, ref in columns.items():
        if isinstance(ref, int) and ref < len(data) and isinstance(data[ref], list):
            result[metric] = [data[x] if isinstance(x, int) and x < len(data) else x for x in data[ref]]

    return result

if __name__ == '__main__':
    ticker = sys.argv[1]
    raw_file = os.path.join('data', ticker, 'output', 'raw_requests.json')
    result = extract_ratios(raw_file)
    out = os.path.join('data', ticker, f'{ticker}_ratios.csv')
    pd.DataFrame(result).to_csv(out, index=False)
    print('Saved:', out)
