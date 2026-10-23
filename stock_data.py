"""Normalize company profile and historical data from sanitized SvelteKit payloads."""
import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from paths import DATA_DIR


def load_requests(ticker):
    p = DATA_DIR / ticker / 'output' / 'raw_requests.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []


def find_node(requests, section):
    """Return flattened data payload of a known company endpoint."""
    marker = f'/{section}/__data.json'
    for item in requests:
        url = item.get('url', '')
        if section == 'profile':
            if '/quote/dse/' not in url or '/__data.json' not in url or '/financials/' in url or '/dividend/' in url:
                continue
            # Main profile: /SYMBOL/__data.json (not nested)
            if not re.search(r'/quote/dse/[^/]+/__data.json', url):
                continue
        elif marker not in url:
            continue
        b = item.get('response_body')
        if isinstance(b, dict) and isinstance(b.get('nodes'), list):
            if len(b['nodes']) > 2 and isinstance(b['nodes'][2], dict):
                return b['nodes'][2].get('data')
    return None


def ref(data, index):
    """Resolve one devalue reference; -1 and other negative sentinels are missing."""
    if isinstance(index, int) and not isinstance(index, bool):
        return data[index] if 0 <= index < len(data) else None
    return index


def string_ref(data, index):
    result = ref(data, index)
    return str(result).strip() if result is not None else None


def company_metadata(requests, ticker):
    name, industry = ticker, 'Unknown Industry'
    for entry in requests:
        url = entry.get('url', '')
        if not re.search(r'/quote/dse/[^/]+/__data.json', url):
            continue
        b = entry.get('response_body', {})
        nodes = b.get('nodes', []) if isinstance(b, dict) else []
        if len(nodes) > 1 and isinstance(nodes[1], dict):
            d = nodes[1].get('data')
            if isinstance(d, list) and d and isinstance(d[0], dict):
                info = ref(d, d[0].get('info', -1))
                if isinstance(info, dict):
                    name = string_ref(d, info.get('name')) or name
        if len(nodes) > 2 and isinstance(nodes[2], dict):
            d = nodes[2].get('data')
            if isinstance(d, list) and d and isinstance(d[0], dict):
                entries = ref(d, d[0].get('infoTable', -1))
                if isinstance(entries, list):
                    for entry_ref in entries:
                        obj = ref(d, entry_ref)
                        if isinstance(obj, dict):
                            title = string_ref(d, obj.get('t'))
                            value = string_ref(d, obj.get('v'))
                            if title and value and title.casefold() == 'industry':
                                industry = value
        break
    return {'ticker': ticker, 'name': name, 'industry': industry}


def financial_table(requests, section):
    """Read arrays from fiscal-year financial tables; excludes TTM by datekey."""
    d = find_node(requests, section)
    if not isinstance(d, list) or not d:
        return {}
    table = None
    # Income overview uses a nested table while ratios and balance use financialData.
    if isinstance(d[0], dict):
        fd = ref(d, d[0].get('financialData', -1))
        if isinstance(fd, dict) and 'fiscalYear' in fd:
            table = fd
    if table is None:
        for obj in d:
            if isinstance(obj, dict) and 'rows' in obj and 'data' in obj:
                candidate = ref(d, obj['data'])
                if isinstance(candidate, dict) and 'fiscalYear' in candidate:
                    table = candidate
                    break
    if not isinstance(table, dict):
        return {}
    lists = {}
    for metric, pointer in table.items():
        sequence = ref(d, pointer)
        if isinstance(sequence, list):
            lists[metric] = [ref(d, item) for item in sequence]
    if 'fiscalYear' not in lists:
        return {}
    periods = {}
    for pos, raw_year in enumerate(lists['fiscalYear']):
        try:
            year = int(raw_year)
        except (ValueError, TypeError):
            continue
        # First TTM may share fiscal year with previous year, don't overwrite.
        datekey = lists.get('datekey', [])
        if pos < len(datekey) and str(datekey[pos]).upper() == 'TTM':
            continue
        if year in periods:
            continue
        periods[year] = {field: seq[pos] if pos < len(seq) else None for field, seq in lists.items()}
    return periods


def ratio_data(requests):
    ratios = financial_table(requests, 'financials/ratios')
    income = financial_table(requests, 'financials')
    balance = financial_table(requests, 'financials/balance-sheet')
    results = {}
    for year in sorted(set(ratios) | set(income) | set(balance)):
        r, f, b = ratios.get(year, {}), income.get(year, {}), balance.get(year, {})
        # StockAnalysis's Book Value Per Share (bvps) is already expressed in BDT/share.
        nav = b.get('bvps')
        # Use common equity and shares as a fallback (both source values in same unit).
        if number(nav) is None:
            eq = number(b.get('equitycommon')) or number(b.get('equity'))
            shares = number(b.get('sharesout')) or number(b.get('sharesbasic'))
            if eq is not None and shares not in (None, 0):
                nav = eq / shares
            else:
                nav = None
        profit = number(f.get('netinccmn'))
        revenue = number(f.get('revenue'))
        npm = profit / revenue if profit is not None and revenue not in (None, 0) else None
        results[year] = {'pe': number(r.get('pe')), 'nav': number(nav),
                         'roa': number(r.get('roa')), 'roe': number(r.get('roe')),
                         'npm': npm, 'eps': number(f.get('epsdil'))}
    return results


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, str):
            value = value.replace(',', '').replace('BDT', '').strip()
            if not value or value.lower() in ('n/a', 'na', '-', 'none'):
                return None
            if value.endswith('%'):
                value = float(value[:-1]) / 100
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def history_data(requests):
    for item in requests:
        if '/history?type=chart' not in item.get('url', ''):
            continue
        payload = item.get('response_body', {}).get('data', [])
        if not isinstance(payload, list):
            continue
        result = []
        for pair in payload:
            if not isinstance(pair, list) or len(pair) < 2:
                continue
            price = number(pair[1])
            if price is None:
                continue
            try:
                date = datetime.fromtimestamp(float(pair[0])/1000, timezone.utc).date()
                result.append({'date': date.isoformat(), 'close': price})
            except (OverflowError, TypeError, ValueError):
                pass
        return sorted({r['date']: r for r in result}.values(), key=lambda r: r['date'])
    return []


def dividend_data(requests):
    d = find_node(requests, 'dividend')
    if not isinstance(d, list) or not d or not isinstance(d[0], dict):
        return []
    entries = ref(d, d[0].get('history', -1))
    if not isinstance(entries, list):
        return []
    result = []
    for ptr in entries:
        obj = ref(d, ptr)
        if not isinstance(obj, dict):
            continue
        data = {k:ref(d,v) for k,v in obj.items()}
        dt = data.get('dt') or data.get('date')
        cash = number(data.get('amt'))
        if dt and cash is not None:
            result.append({'date': str(dt)[:10], 'cash': cash})
    return result


def write_csv(filename, rows, columns):
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open('w', encoding='utf-8', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def save_normalized(ticker, requests):
    target = DATA_DIR / ticker
    meta=company_metadata(requests,ticker)
    target.mkdir(parents=True, exist_ok=True)
    (target / 'company.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    ratios=ratio_data(requests)
    write_csv(target/f'{ticker}_ratios_export.csv', [{'year':y,**v} for y,v in ratios.items()], ['year','pe','nav','roa','roe','npm','eps'])
    write_csv(target/f'{ticker}_history.csv', history_data(requests), ['date','close'])
    write_csv(target/f'{ticker}_dividend.csv', dividend_data(requests), ['date','cash'])
    return meta
