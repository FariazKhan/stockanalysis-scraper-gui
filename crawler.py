"""Playwright crawler for stockanalysis.com API endpoint discovery.

Strategy:
  Phase 1 - Full page loads: captures /api/quotes, /api/symbol/history,
            /api/mc/*, auth endpoints triggered on each page load.
  Phase 2 - In-browser fetch of __data.json: SvelteKit serves financial/ETF/
            market data via SSR (embedded in HTML, not XHR). We manually fetch
            the __data.json endpoints from the authenticated browser context
            to discover them.
"""
import os, sys
import asyncio
import json
import random
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page, Response

def parse_cookies():
    try:
        with open("cookies.json", "r") as f:
            return json.load(f)
    except Exception:
        print("Warning: cookies.json not found. Running without cookies.")
        return []

def get_user_agent():
    return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
BASE_URL = "https://stockanalysis.com"
TICKER = None
VERBOSE = False

def log(msg):
    if VERBOSE:
        print(msg)

def get_full_load_pages(ticker):
    return [
        "/",
        f"/quote/dse/{ticker}/",
        f"/quote/dse/{ticker}/history/",
        f"/quote/dse/{ticker}/financials/",
        f"/quote/dse/{ticker}/financials/balance-sheet/",
        f"/quote/dse/{ticker}/financials/ratios/",
        f"/quote/dse/{ticker}/dividend/",
    ]


def get_data_json_paths(ticker):
    return [
        f"/quote/dse/{ticker}/__data.json?x-sveltekit-trailing-slash=1",
        f"/quote/dse/{ticker}/financials/__data.json?x-sveltekit-trailing-slash=1",
        f"/quote/dse/{ticker}/financials/balance-sheet/__data.json?x-sveltekit-trailing-slash=1",
        f"/quote/dse/{ticker}/financials/cash-flow-statement/__data.json?x-sveltekit-trailing-slash=1",
        f"/quote/dse/{ticker}/financials/ratios/__data.json?x-sveltekit-trailing-slash=1",
        f"/quote/dse/{ticker}/history/__data.json?x-sveltekit-trailing-slash=1",
        f"/quote/dse/{ticker}/dividend/__data.json?x-sveltekit-trailing-slash=1",
    ]


# Only keep domains that belong to stockanalysis.com infrastructure
KEEP_DOMAINS = {
    "stockanalysis.com",
    "api.stockanalysis.com",
    "auth.stockanalysis.com",
}

# Resource types and URL fragments to skip during phase 1
SKIP_RESOURCE_TYPES = {"image", "stylesheet", "font", "media", "websocket", "other"}
SKIP_URL_FRAGMENTS = [
    "google-analytics", "posthog", "doubleclick", "googlesyndication",
    "_next/static", "_next/image", ".png", ".jpg", ".jpeg", ".svg",
    ".woff", ".woff2", ".ttf", ".ico", ".css", "analytics", "gtag",
    "hotjar", "sentry", "ingest.sentry",
]


def is_stockanalysis_domain(url: str) -> bool:
    return any(d in url for d in KEEP_DOMAINS)


def should_skip(url: str, resource_type: str) -> bool:
    if resource_type in SKIP_RESOURCE_TYPES:
        return True
    if any(frag in url for frag in SKIP_URL_FRAGMENTS):
        return True
    return False


async def random_delay(min_s: float = 0.3, max_s: float = 1.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def scroll_page(page: Page):
    """Scroll down the page to trigger lazy-load content."""
    await page.evaluate("""
        async () => {
            await new Promise((resolve) => {
                let totalHeight = 0;
                const distance = 400;
                const timer = setInterval(() => {
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if (totalHeight >= Math.min(document.body.scrollHeight, 2000)) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 80);
            });
        }
    """)
    await asyncio.sleep(0.3)


def truncate_preview(body) -> object:
    """Truncate large response bodies to keep manageable previews."""
    if isinstance(body, dict):
        preview = {}
        for k, v in body.items():
            if isinstance(v, list) and len(v) > 5:
                preview[k] = v[:5] + [f"... ({len(v)} total items)"]
            elif isinstance(v, dict) and len(str(v)) > 600:
                preview[k] = dict(list(v.items())[:5])
            else:
                preview[k] = v
        return preview
    elif isinstance(body, list):
        return body[:5] + ([f"... ({len(body)} total items)"] if len(body) > 5 else [])
    return body


async def phase1_full_loads(page: Page, captured: list):
    """Phase 1: Full page loads to capture real-time API calls."""
    log("\n=== Phase 1: Full page loads ===")

    async def on_response(response: Response):
        req = response.request
        url = response.url
        resource_type = req.resource_type

        if should_skip(url, resource_type):
            return
        if resource_type not in ("xhr", "fetch"):
            return
        if not is_stockanalysis_domain(url):
            return

        body = None
        try:
            body = await response.json()
            preview = truncate_preview(body)
        except Exception:
            preview = None

        try:
            post_data = req.post_data
        except Exception:
            post_data = None

        entry = {
            "url": url,
            "method": req.method,
            "resource_type": resource_type,
            "post_data": post_data,
            "status": response.status,
            "response_preview": preview,
            "response_body": body,
            "captured_at": time.time(),
            "phase": "P1"
        }
        captured.append(entry)
        log(f"  [P1] {req.method} {url[:90]}")

    page.on("response", on_response)

    for path in FULL_LOAD_PAGES:
        url = BASE_URL + path
        log(f"\n[Page] {path}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            await scroll_page(page)
            await random_delay(0.5, 1.0)
        except Exception as e:
            log(f"  Error: {e}")
        await random_delay(0.8, 1.5)


async def phase2_data_json(page: Page, captured: list):
    """Phase 2: Fetch __data.json endpoints from within authenticated browser context."""
    log("\n\n=== Phase 2: Fetching __data.json endpoints ===")

    for data_path in DATA_JSON_PATHS:
        full_url = BASE_URL + data_path
        log(f"  [P2] GET {full_url[:90]}")

        try:
            result = await page.evaluate(f"""
                async () => {{
                    const r = await fetch('{full_url}', {{
                        credentials: 'include',
                        headers: {{ 'Accept': 'application/json' }}
                    }});
                    const status = r.status;
                    let body = null;
                    try {{ body = await r.json(); }} catch(e) {{}}
                    return {{ status, body }};
                }}
            """)

            if result and result.get("body"):
                preview = truncate_preview(result["body"])
                entry = {
                    
                    "url": full_url,
                    "method": "GET",
                    "resource_type": "fetch",
                    "post_data": None,
                    "status": result.get("status"),
                    "response_preview": preview,
                    "response_body": result.get("body"),
                    "captured_at": time.time(),
                    "phase": "P2"
                }
                captured.append(entry)
                log(f"    → status={result.get('status')}")
            else:
                status = result.get("status") if result else "?"
                log(f"    → status={status} (no JSON body)")

        except Exception as e:
            log(f"    → Error: {e}")

        await random_delay(0.3, 0.6)


async def phase3_extra_api(page: Page, captured: list):
    """Phase 3: Directly fetch known API endpoint patterns."""
    log("\n\n=== Phase 3: Direct API endpoint probing ===")

    # Known API endpoint patterns to probe
    api_endpoints = [
        # Quotes
        "/api/quotes/s/aapl",
        "/api/quotes/s/tsla",
        "/api/quotes/s/msft",
        "/api/quotes/e/spy",
        "/api/quotes/e/qqq",
        f"/api/quotes/a/DSE-{TICKER}",
        # Symbol history
        f"/api/symbol/a/DSE-{TICKER}/history?type=chart",
        f"/api/symbol/a/DSE-{TICKER}/dividend?chart=yield&range=5Y",
        "/api/symbol/s/aapl/history?type=annual",
        "/api/symbol/s/aapl/history?type=quarterly",
        "/api/symbol/e/spy/history?type=chart",
        # Market clock
        "/api/mc/pre?c=1",
        "/api/mc/post?c=1",
        "/api/mc/1d?c=1",
        # Screener
        "/api/screener/s?m=marketCap&s=desc&ln=en&c=no,marketCap,lastClose,change1W&p=1&i=stocks",
        "/api/screener/etf?m=totalAssets&s=desc&ln=en&c=no,totalAssets,lastClose,volume&p=1",
    ]

    for api_path in api_endpoints:
        full_url = BASE_URL + api_path
        log(f"  [P3] GET {full_url[:90]}")

        try:
            result = await page.evaluate(f"""
                async () => {{
                    const r = await fetch('{full_url}', {{
                        credentials: 'include',
                        headers: {{
                            'Accept': 'application/json',
                            'Referer': 'https://stockanalysis.com/'
                        }}
                    }});
                    const status = r.status;
                    let body = null;
                    try {{ body = await r.json(); }} catch(e) {{}}
                    return {{ status, body }};
                }}
            """)

            if result:
                status = result.get("status", "?")
                body = result.get("body")
                if body:
                    preview = truncate_preview(body)
                    entry = {
                        "url": full_url,
                        "method": "GET",
                        "resource_type": "fetch",
                        "post_data": None,
                        "status": status,
                        "response_preview": preview,
                        "response_body": body,
                        "captured_at": time.time(),
                        "phase": "P3"
                    }
                    captured.append(entry)
                    log(f"    → status={status} ✓")
                else:
                    log(f"    → status={status} (no JSON)")
        except Exception as e:
            log(f"    → Error: {e}")

        await random_delay(0.2, 0.5)


async def run_crawler(ticker, output_dir="output"):
    """Main crawler entry point."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    captured = []
    global TICKER
    TICKER = ticker
    global FULL_LOAD_PAGES, DATA_JSON_PATHS
    FULL_LOAD_PAGES = get_full_load_pages(ticker)
    DATA_JSON_PATHS = get_data_json_paths(ticker)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=get_user_agent(),
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
        )

        cookies = parse_cookies()
        await context.add_cookies(cookies)
        log(f"Injected {len(cookies)} cookies")

        page = await context.new_page()

        # Phase 1: full page loads (network interception)
        await phase1_full_loads(page, captured)

        # Phase 2: fetch __data.json from authenticated browser
        await phase2_data_json(page, captured)

        # Phase 3: probe known API patterns
        await phase3_extra_api(page, captured)

        await browser.close()

    # Save raw results
    raw_path = Path(output_dir) / "raw_requests.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(captured, f, indent=2, default=str)
    log(f"\nSaved {len(captured)} requests to {raw_path}")

    return captured

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(
            "Usage: python crawler.py TICKER"
        )
        sys.exit()


    ticker = sys.argv[1].upper()


    output_dir = os.path.join(
        "data",
        ticker,
        "output"
    )


    # create folder
    os.makedirs(
        output_dir,
        exist_ok=True
    )


    # remove old crawl
    old_file = os.path.join(
        output_dir,
        "raw_requests.json"
    )

    if os.path.exists(old_file):
        os.remove(old_file)


    results = asyncio.run(
        run_crawler(
            ticker,
            output_dir
        )
    )


    print(
        f"Completed crawl for {ticker}"
    )