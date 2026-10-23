import json
import pandas as pd
import os
import sys

def resolve(d, x):
    return d[x] if isinstance(x, int) and x < len(d) else x

def extract_financials(filename):
    with open(filename, encoding='utf-8') as f:
        raw = json.load(f)

    response = next((x['response_body'] for x in raw if 'financials/__data.json' in x['url']), None)
    if response is None:
        raise Exception('Financials JSON not found')

    d = next((n['data'] for n in response.get('nodes', []) if isinstance(n, dict) and isinstance(n.get('data'), list) and len(n.get('data')) > 200), None)

    if d is None:
        print('No usable financial data node found')
        return {}

    section = next((x for x in d if isinstance(x, dict) and 'data' in x and 'rows' in x), None)

    if section is None:
        print('No financial table available')
        return {}

    table = d[section['data']]
    result = {}

    if isinstance(table, dict):
        for metric, ref in table.items():
            if isinstance(ref, int) and ref < len(d) and isinstance(d[ref], list):
                result[metric] = [resolve(d, x) for x in d[ref]]

    return result

if __name__ == '__main__':
    ticker = sys.argv[1]
    raw_file = os.path.join('data', ticker, 'output', 'raw_requests.json')
    result = extract_financials(raw_file)
    out = os.path.join('data', ticker, f'{ticker}_financials.csv')
    pd.DataFrame(result).to_csv(out, index=False)
    print('Saved:', out)
