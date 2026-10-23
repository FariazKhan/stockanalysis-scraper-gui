"""Bounded, authenticated collection of public StockAnalysis DSE data.

No full network interception: only known, company-specific JSON endpoints are kept.
SvelteKit node[0] contains session information and is deliberately discarded.
"""
import asyncio
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright
from paths import DATA_DIR, session_path

LOG = logging.getLogger(__name__)
BASE = 'https://stockanalysis.com'
SEMAPHORE = 2  # be polite; higher concurrency can trigger rate limits
CACHE_HOURS = 12


def clean_ticker(ticker):
    ticker = str(ticker).strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9.-]{0,24}', ticker):
        raise ValueError(f'Invalid ticker: {ticker!r}')
    return ticker


def json_url(ticker, suffix=''):
    return f'{BASE}/quote/dse/{quote(ticker)}/{suffix}__data.json?x-sveltekit-trailing-slash=1'


def filtered_data(body):
    """Keep company and financial nodes but never persist the auth/session node."""
    if not isinstance(body, dict) or not isinstance(body.get('nodes'), list):
        return None
    nodes = body['nodes']
    if len(nodes) < 3:
        return None
    return {'nodes': [None, nodes[1], nodes[2]]}


async def _request_json(request, url, retries=2):
    for attempt in range(retries + 1):
        try:
            response = await request.get(url, timeout=25000)
            if response.status in (429, 500, 502, 503, 504):
                if attempt < retries:
                    await asyncio.sleep(min(2 ** attempt + 0.5, 5))
                    continue
            if response.status != 200:
                return None, f'HTTP {response.status} for {url.split("?")[0]}'
            return await response.json(), None
        except Exception as exc:
            if attempt == retries:
                return None, f'{type(exc).__name__}: {exc}'
            await asyncio.sleep(min(2 ** attempt + 0.5, 5))
    return None, 'No response'


async def _one(context, ticker, *, refresh=False, progress=None):
    ticker = clean_ticker(ticker)
    dest = DATA_DIR / ticker / 'output' / 'raw_requests.json'
    if not refresh and dest.exists() and time.time() - dest.stat().st_mtime < CACHE_HOURS * 3600:
        try:
            saved = json.loads(dest.read_text(encoding='utf-8'))
            # Sanitize legacy caches, which may contain an embedded auth token in node[0].
            sanitized = False
            for record in saved:
                body = record.get('response_body', {})
                if isinstance(body, dict) and isinstance(body.get('nodes'), list):
                    clean = filtered_data(body)
                    if clean is not None and clean != body:
                        record['response_body'] = clean
                        sanitized = True
            if sanitized:
                tmp = dest.with_suffix('.tmp')
                tmp.write_text(json.dumps(saved,ensure_ascii=False),encoding='utf-8')
                tmp.replace(dest)
            if saved and any('/financials/ratios/' in x.get('url', '') for x in saved):
                if progress: progress(f'{ticker}: using recent cached data')
                return {'ticker': ticker, 'requests': saved, 'errors': [], 'cached': True}
        except (OSError, ValueError):
            pass

    endpoints = {
        'profile': json_url(ticker),
        'ratios': json_url(ticker, 'financials/ratios/'),
        'income': json_url(ticker, 'financials/'),
        'balance': json_url(ticker, 'financials/balance-sheet/'),
        'dividend': json_url(ticker, 'dividend/'),
        'history': f'{BASE}/api/symbol/a/DSE-{quote(ticker)}/history?type=chart',
    }
    # Request context shares logged-in browser cookies. Fetch company-specific endpoints only.
    # Limit request concurrency independently of company concurrency.
    gate = asyncio.Semaphore(3)
    async def gated(url):
        async with gate:
            return await _request_json(context.request, url)
    results = await asyncio.gather(*[gated(url) for url in endpoints.values()])
    collected, errors = [], []
    for (label, url), (body, err) in zip(endpoints.items(), results):
        if err:
            errors.append(f'{label}: {err}')
            continue
        if label != 'history':
            body = filtered_data(body)
            if body is None:
                errors.append(f'{label}: unexpected or inaccessible JSON data')
                continue
        elif not isinstance(body, dict) or not isinstance(body.get('data'), list):
            errors.append('history: invalid chart response')
            continue
        collected.append({'url': url, 'status': 200, 'response_body': body, 'captured_at': time.time()})

    if collected:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix('.tmp')
        tmp.write_text(json.dumps(collected, ensure_ascii=False), encoding='utf-8')
        tmp.replace(dest)
    if progress: progress(f'{ticker}: fetched {len(collected)}/6 endpoints' + (f'; {len(errors)} issues' if errors else ''))
    return {'ticker': ticker, 'requests': collected, 'errors': errors, 'cached': False}


async def collect_many(tickers, *, refresh=False, progress=None):
    tickers = list(dict.fromkeys(clean_ticker(t) for t in tickers))
    results = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        state = session_path()
        context_kwargs = {'ignore_https_errors': False}
        if state.exists():
            context_kwargs['storage_state'] = str(state)
        context = await browser.new_context(**context_kwargs)
        semaphore = asyncio.Semaphore(SEMAPHORE)

        async def work(ticker):
            async with semaphore:
                try:
                    return await _one(context, ticker, refresh=refresh, progress=progress)
                except Exception as exc:
                    LOG.exception('Ticker failure: %s', ticker)
                    return {'ticker': ticker, 'requests': [], 'errors': [f'{type(exc).__name__}: {exc}']}

        try:
            results = await asyncio.gather(*(work(t) for t in tickers))
        finally:
            await context.close()
            await browser.close()
    return results


def run_crawler(ticker, output_dir=None):
    """Legacy compatible single ticker entry point. Results are sanitized."""
    result = asyncio.run(collect_many([ticker], refresh=True))[0]
    if result['errors']:
        LOG.warning('%s: %s', ticker, '; '.join(result['errors']))
    return result['requests']


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python crawler.py TICKER')
    print(f"Fetched {len(run_crawler(sys.argv[1]))} data endpoints")
