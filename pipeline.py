"""End-to-end orchestration: crawl, normalize, export. GUI-safe progress callbacks."""
import asyncio
import csv
import logging
from pathlib import Path
from paths import DATA_DIR

from crawler import collect_many, clean_ticker
from excel_exporter import create_excel, read_corporate_actions
from paths import OUTPUT_DIR
from stock_data import save_normalized
from split_history import collect_splits, saved_split_events

LOG=logging.getLogger(__name__)


def parse_tickers(text):
    tickers = [clean_ticker(x) for x in text.replace('\n', ',').split(',') if x.strip()]
    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        raise ValueError('Enter at least one DSE ticker')
    return tickers


def run_pipeline(ticker_text, start_year, end_year, output_file=None, *, refresh=False, progress=None):
    start_year, end_year = int(start_year), int(end_year)
    if start_year < 1990 or end_year > 2100 or end_year < start_year:
        raise ValueError('Choose a valid year range (1990–2100)')
    tickers=parse_tickers(ticker_text)
    callback=progress or (lambda msg: LOG.info(msg))
    callback(f'Collecting data for {len(tickers)} companies...')
    results=asyncio.run(collect_many(tickers,refresh=refresh,progress=callback))
    issues=[]
    usable=0
    for result in results:
        ticker=result['ticker']
        for issue in result['errors']:
            issues.append(f'{ticker}: {issue}')
        if result['requests']:
            info=save_normalized(ticker,result['requests'])
            usable+=1
            if info['industry']=='Unknown Industry':
                issues.append(f'{ticker}: industry could not be verified; grouped as Unknown Industry')
            annual=DATA_DIR/ticker/f'{ticker}_ratios_export.csv'
            with annual.open(encoding='utf-8',newline='') as f:
                available={int(x['year']) for x in csv.DictReader(f) if str(x.get('year','')).isdigit()
                           and any(x.get(field) for field in ('pe','nav','roa','roe','npm','eps'))}
            missing=[y for y in range(start_year,end_year+1) if y not in available]
            if missing:
                recent_missing = [y for y in missing if available and y > max(available)]
                old_missing = [y for y in missing if y not in recent_missing]
                if recent_missing:
                    years=', '.join(map(str,recent_missing[:8])) + ('…' if len(recent_missing)>8 else '')
                    issues.append(f'{ticker}: FY {years} annual ratios not published/available on StockAnalysis; '
                                  f'latest available annual FY {max(available)}. Current/TTM ratios are not annual data.')
                if old_missing:
                    years=', '.join(map(str,old_missing[:8])) + ('…' if len(old_missing)>8 else '')
                    issues.append(f'{ticker}: FY {years} historical annual ratios unavailable (check source plan/history)')
            history=DATA_DIR/ticker/f'{ticker}_history.csv'
            if len(history.read_text(encoding='utf-8').splitlines()) <= 1:
                issues.append(f'{ticker}: no historical price observations returned')
        else:
            # Existing cached normalized data might still exist; user sees an issue.
            issues.append(f'{ticker}: no current dataset; workbook values will be blank')
    if usable == 0:
        raise RuntimeError('No data was retrieved. Check your internet connection, session and site access.')
    callback('Checking StockAnalysis latest splits and verified historical events...')
    try:
        split_results = asyncio.run(collect_splits(tickers,refresh=refresh,progress=callback))
        for result in split_results:
            ticker = result['ticker']
            if result['error']:
                issues.append(f'{ticker}: {result["error"]}')
        # Also consider the verified CSV records when explaining an empty split sheet.
        all_events = [e for e in read_corporate_actions()
                      if e['kind'] == 'split' and e['ticker'] in tickers]
        all_events.extend(saved_split_events(tickers))
        for ticker in tickers:
            dates = {e['date'] for e in all_events if e['ticker'] == ticker}
            if dates and not any(start_year <= d.year <= end_year for d in dates):
                issues.append(f'{ticker}: {len(dates)} verified split event(s) found, '
                              f'but all are outside selected years {start_year}–{end_year}; '
                              'Split cells for these years stay blank')
    except Exception as exc:
        issues.append(f'Split lookup was skipped: {type(exc).__name__}: {exc}')
    callback('Writing seven industry-grouped Excel sheets...')
    destination=Path(output_file) if output_file else OUTPUT_DIR/'portfolio.xlsx'
    saved=create_excel(start_year,end_year,tickers,destination)
    issues_file=saved.with_name(saved.stem+'_warnings.txt')
    issues_file.write_text('\n'.join(issues) if issues else 'No reported crawler errors. Blank cells may still indicate unavailable historical data.\n',encoding='utf-8')
    callback(f'Finished: {saved}')
    return saved, issues
