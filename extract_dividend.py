import json
import pandas as pd
import os
import sys

def extract_dividend(filename):
    with open(filename, encoding='utf-8') as f:
        raw = json.load(f)

    response = next((x['response_body'] for x in raw if 'dividend/__data.json' in x['url']), None)
    if response is None:
        print('Dividend JSON not found')
        return []

    d = next((n['data'] for n in response.get('nodes', []) if isinstance(n, dict) and isinstance(n.get('data'), list) and isinstance(n['data'][0], dict) and 'history' in n['data'][0]), None)

    if d is None:
        print('No usable dividend data node found')
        return []

    root = d[0]
    history_idx = root.get('history')
    
    if history_idx is None or history_idx >= len(d) or not isinstance(d[history_idx], list):
        print('No dividend history found')
        return []

    history_list = d[history_idx]
    
    results = []
    for idx in history_list:
        if isinstance(d[idx], dict):
            obj = d[idx]
            resolved_obj = {}
            for k, v in obj.items():
                if isinstance(v, int) and v < len(d):
                    resolved_obj[k] = d[v]
                else:
                    resolved_obj[k] = v
            results.append(resolved_obj)
            
    return results

if __name__ == '__main__':
    ticker = sys.argv[1]
    raw_file = os.path.join('data', ticker, 'output', 'raw_requests.json')
    if os.path.exists(raw_file):
        result = extract_dividend(raw_file)
        out = os.path.join('data', ticker, f'{ticker}_dividend.csv')
        if result:
            pd.DataFrame(result).to_csv(out, index=False)
            print('Saved:', out)
        else:
            pd.DataFrame(columns=['dt', 'amt', 'dec', 'record', 'pay']).to_csv(out, index=False)
            print('Saved empty:', out)
    else:
        print(f'Raw requests file not found: {raw_file}')
