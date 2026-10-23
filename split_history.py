"""Historical splits for DSE stocks, without accessing blocked Investing.com pages.

StockAnalysis statistics exposes the most recent split per company; bundled
verified historical events and user CSVs cover earlier actions. A previous
Investing cache is still readable, but is never refreshed via blocked requests.
Missing records remain blank; no splits are inferred from price fluctuations.
"""
from __future__ import annotations

import asyncio
import csv
import json
import logging
import re
import time
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from html import unescape
from urllib.parse import quote
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from paths import DATA_DIR, ROOT, PACKAGE_DIR, session_path

LOG = logging.getLogger(__name__)
DOMAIN = 'www.investing.com'
CACHE_SECONDS = 24 * 3600
KNOWN_SUFFIXES = {'ltd', 'limited', 'plc', 'inc', 'corp', 'corporation', 'company', 'co'}
MONTHS = r'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?'
SPLIT_ROW = re.compile(
    rf'\b(?P<when>(?:{MONTHS})\s+\d{{1,2}},\s+\d{{4}})\s+'
    r'(?P<numerator>\d+(?:\.\d+)?)\s*:\s*(?P<denominator>\d+(?:\.\d+)?)\b',
    re.IGNORECASE,
)


def _terms(value):
    value = unicodedata.normalize('NFKD', str(value))
    ascii_text = value.encode('ascii', 'ignore').decode('ascii').casefold()
    return [p for p in re.findall(r'[a-z0-9]+', ascii_text) if p not in KNOWN_SUFFIXES]


def valid_split_url(url):
    """Only load Investing.com equity split pages (never arbitrary URL redirects)."""
    try:
        u = urlsplit(str(url).strip())
        return (u.scheme == 'https' and u.hostname is not None
                and (u.hostname == 'investing.com' or u.hostname.endswith('.investing.com'))
                and u.username is None and u.password is None
                and u.port in (None, 443)
                and bool(re.fullmatch(r'/equities/[a-z0-9-]+-historical-data-splits/?', u.path))
                and not u.query and not u.fragment)
    except ValueError:
        return False


def split_url_mapping(path=None):
    path = Path(path) if path else ROOT / 'investing_split_urls.csv'
    if not path.is_file():
        return {}
    output = {}
    with path.open(encoding='utf-8-sig', newline='') as f:
        for index, row in enumerate(csv.DictReader(f), 2):
            ticker = (row.get('ticker') or '').upper().strip()
            url = (row.get('url') or '').strip()
            if not ticker or not url:
                continue
            if not re.fullmatch(r'[A-Z0-9][A-Z0-9.-]{0,24}', ticker) or not valid_split_url(url):
                raise ValueError(f'Invalid ticker or Investing split URL in {path.name}, row {index}')
            output[ticker] = url
    return output


def candidate_urls(ticker, company_name, mapping):
    if ticker in mapping:
        return [mapping[ticker]]
    tokens = _terms(company_name)
    if not tokens or tokens == _terms(ticker):
        return []
    # These are guesses and MUST pass a company-name identity check below.
    stem = '-'.join(tokens)
    guesses = [f'https://{DOMAIN}/equities/{stem}-ltd-historical-data-splits',
               f'https://{DOMAIN}/equities/{stem}-historical-data-splits']
    return list(dict.fromkeys(guesses))


def heading_matches_company(heading, company_name):
    """Reject similarly-named equities rather than import someone else's splits."""
    text = _terms(heading.split('Stock Split History')[0].split('Split History')[0])
    expected = _terms(company_name)
    if len(expected) < 2:
        return bool(expected) and bool(text) and expected[0] == text[0]
    return len(text) >= 2 and text[:2] == expected[:2]


def parse_split_history_text(text):
    """Read text rendered from the *split-history section*, not random ratios."""
    text = re.sub(r'\s+', ' ', str(text))
    anchor = re.search(r'Split\s+date\s+Split\s+ratio', text, flags=re.IGNORECASE)
    if not anchor:
        return []
    # The table is normally small; limit scanning to avoid unrelated site content.
    content = text[anchor.end():anchor.end()+6500]
    output = {}
    for m in SPLIT_ROW.finditer(content):
        try:
            dt = datetime.strptime(re.sub(r'\s+', ' ', m['when']), '%b %d, %Y').date()
        except ValueError:
            try:
                dt = datetime.strptime(re.sub(r'\s+', ' ', m['when']), '%B %d, %Y').date()
            except ValueError:
                continue
        try:
            val = Decimal(m['numerator']) / Decimal(m['denominator'])
        except (InvalidOperation, ZeroDivisionError):
            continue
        if val <= 0 or val > 10000:
            continue
        output[dt.isoformat()] = format(val.normalize(), 'f')
    return [{'date': k, 'ratio': v} for k, v in sorted(output.items())]


def _read_cache(ticker):
    path = DATA_DIR / ticker / f'{ticker}_investing_splits.csv'
    if not path.is_file():
        return []
    with path.open(encoding='utf-8-sig', newline='') as f:
        return [x for x in csv.DictReader(f)
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', x.get('date', ''))
                and re.fullmatch(r'\d+(?:\.\d+)?', x.get('ratio', ''))
                and valid_split_url(x.get('source_url', ''))]


def _write_cache(ticker, events):
    path = DATA_DIR / ticker / f'{ticker}_investing_splits.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=('date', 'ratio', 'source_url'))
        writer.writeheader()
        writer.writerows(events)
    tmp.replace(path)


class _VisibleText(HTMLParser):
    """Collect readable HTML; don't mistake embedded JS for table contents."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('script', 'style', 'template'):
            self.hidden += 1
        if tag.lower() in ('td', 'th', 'tr', 'p', 'h1', 'h2', 'h3', 'section'):
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag.lower() in ('script', 'style', 'template'):
            self.hidden = max(0, self.hidden - 1)
        if tag.lower() in ('td', 'th', 'tr', 'p', 'h1', 'h2', 'h3', 'section'):
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data)


def parse_stockanalysis_stats(html):
    """Parse only the last split, never claim a full historical record.

    Returns {'date': ISO date, 'ratio': decimal text}, or None. An empty
    split section is a normal result for companies without a listed split.
    """
    parser = _VisibleText()
    parser.feed(str(html))
    text = re.sub(r'\s+', ' ', unescape(' '.join(parser.parts)))
    section = re.search(r'\bStock Splits\b(.*?)(?:\bScores\b|\bData Source\b|$)', text, re.I)
    if not section:
        return None
    piece = section.group(1)[:1500]
    dt_match = re.search(r'\bLast Split Date\s+([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})\b', piece, re.I)
    ratio_match = re.search(r'\bSplit Ratio\s+(\d+(?:\.\d+)?)\b', piece, re.I)
    if not dt_match or not ratio_match:
        return None
    dt = None
    for fmt in ('%b %d, %Y', '%B %d, %Y'):
        try:
            dt = datetime.strptime(re.sub(r'\s+', ' ', dt_match.group(1)), fmt).date()
            break
        except ValueError:
            continue
    if dt is None:
        return None
    try:
        ratio = Decimal(ratio_match.group(1))
    except InvalidOperation:
        return None
    if not Decimal('0.000001') <= ratio <= Decimal('10000'):
        return None
    return {'date': dt.isoformat(), 'ratio': format(ratio.normalize(), 'f')}


def _stockanalysis_cache_path(ticker):
    return DATA_DIR / ticker / f'{ticker}_stockanalysis_latest_split.csv'


def _read_stockanalysis_cache(ticker):
    path = _stockanalysis_cache_path(ticker)
    if not path.is_file():
        return []
    with path.open(encoding='utf-8-sig', newline='') as f:
        return [r for r in csv.DictReader(f)
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', r.get('date',''))
                and re.fullmatch(r'\d+(?:\.\d+)?', r.get('ratio',''))
                and r.get('source_url') == f'https://stockanalysis.com/quote/dse/{ticker}/statistics/']


def _write_stockanalysis_cache(ticker, item):
    path = _stockanalysis_cache_path(ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['date','ratio','source_url'])
        writer.writeheader()
        if item:
            writer.writerow({**item,'source_url': f'https://stockanalysis.com/quote/dse/{ticker}/statistics/'})
    tmp.replace(path)


async def _fetch_stockanalysis_last_split(context, ticker, *, refresh=False):
    """Read last recorded split from the primary source, without a blocked service."""
    path = _stockanalysis_cache_path(ticker)
    if not refresh and path.exists() and time.time() - path.stat().st_mtime < CACHE_SECONDS:
        return {'ticker':ticker, 'cached':True, 'error':''}
    url = f'https://stockanalysis.com/quote/dse/{quote(ticker)}/statistics/'
    try:
        response = await context.request.get(url, timeout=22000)
        if response.status != 200:
            return {'ticker':ticker, 'cached':False,
                    'error':f'StockAnalysis statistics unavailable (HTTP {response.status}); verified historical fallback retained'}
        if response.url.split('?',1)[0].rstrip('/') != url.rstrip('/'):
            return {'ticker':ticker, 'cached':False, 'error':'StockAnalysis statistics redirected; no split data imported'}
        data = parse_stockanalysis_stats(await response.text())
        # Keep a newer known split if a stale source temporarily returns an older date.
        old = _read_stockanalysis_cache(ticker)
        if old and (not data or old[0]['date'] > data['date']):
            return {'ticker':ticker, 'cached':True, 'error':''}
        if data is not None:
            _write_stockanalysis_cache(ticker, data)
        return {'ticker':ticker, 'cached':False, 'error':''}
    except Exception as exc:
        return {'ticker':ticker, 'cached':False,
                'error':f'StockAnalysis split statistics: {type(exc).__name__}: {str(exc)[:180]}'}


async def collect_splits(tickers, *, refresh=False, progress=None):
    """Collect available latest splits from StockAnalysis, merging verified history.

    Investing.com may deny automated access (403). We never retry with
    alternative IPs/regions or stealth-browser tricks to bypass that denial.
    """
    from playwright.async_api import async_playwright

    results = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            state = session_path()
            context = await browser.new_context(**({'storage_state':str(state)} if state.is_file() else {}))
            gate = asyncio.Semaphore(2)
            async def collect(ticker):
                async with gate:
                    result = await _fetch_stockanalysis_last_split(context,ticker,refresh=refresh)
                    result['count'] = len(saved_split_events([ticker]))
                    if progress:
                        msg = f'{ticker}: {result["count"]} confirmed split event(s) from available records'
                        if result['cached']:
                            msg += ' (latest check cached)'
                        progress(msg)
                    return result
            try:
                results = await asyncio.gather(*(collect(t) for t in tickers))
            finally:
                await context.close()
                await browser.close()
    except Exception as exc:
        LOG.warning('StockAnalysis split statistics source unavailable: %s', exc)
        results = [{'ticker':ticker, 'count':len(saved_split_events([ticker])),
                    'error':f'Split latest-date check unavailable: {type(exc).__name__}: {exc}',
                    'cached':False} for ticker in tickers]
    return results


def saved_split_events(tickers):
    """Merge verified multi-year history, old verified Investing cache, and latest split.

    Exactly one event per (ticker, date); never multiply duplicate sources.
    """
    available = set(tickers)
    result = {}
    source = PACKAGE_DIR / 'verified_splits.csv'
    if source.is_file():
        with source.open(encoding='utf-8-sig', newline='') as f:
            for item in csv.DictReader(f):
                ticker = (item.get('ticker') or '').strip().upper()
                if ticker not in available or not valid_split_url(item.get('source_url', '')):
                    continue
                try:
                    dt = datetime.strptime(item['date'], '%Y-%m-%d').date()
                    ratio = float(Decimal(item['ratio']))
                except (ValueError, KeyError, InvalidOperation):
                    continue
                if 0 < ratio <= 10000:
                    result[(ticker, dt)] = {'ticker':ticker, 'kind':'split', 'date':dt,
                                            'ratio':ratio, 'offer_price':None,
                                            'source_url': item['source_url']}
    for ticker in tickers:
        for item in _read_cache(ticker) + _read_stockanalysis_cache(ticker):
            try:
                dt = datetime.strptime(item['date'], '%Y-%m-%d').date()
                ratio = float(Decimal(item['ratio']))
            except (ValueError, InvalidOperation):
                continue
            if 0 < ratio <= 10000:
                result[(ticker, dt)] = {'ticker':ticker, 'kind':'split', 'date':dt,
                                         'ratio':ratio, 'offer_price':None,
                                         'source_url': item['source_url']}
    return list(result.values())
