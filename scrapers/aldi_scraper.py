# scrapers/aldi_scraper.py
import asyncio
import json
import os
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Set, Any, Optional

import requests

ALDI_API = "https://api.aldi.us/v2/products"
ALDI_WEB = "https://www.aldi.us"

SERVICE_POINT = os.environ.get("ALDI_SERVICE_POINT", "463-091")  # store (e.g., 463-091)
SERVICE_TYPE  = os.environ.get("ALDI_SERVICE_TYPE",  "pickup")   # "pickup" or "delivery"

# Pages that, in practice, emit large /v2/products?skus=... requests
ENTRY_PAGES = [
    f"{ALDI_WEB}/",
    f"{ALDI_WEB}/featured/new-trending",
    f"{ALDI_WEB}/featured/aldi-finds",
    f"{ALDI_WEB}/search?q=weekly",
    f"{ALDI_WEB}/search?q=seasonal",
    f"{ALDI_WEB}/search?q=limited",
]

# Categories that are most likely “deals” (loose heuristic)
DEAL_CATEGORY_TOKENS = {
    "ALDI Finds", "Featured", "Seasonal", "Holiday", "Home & Decor", "Food"
}


def _chunk(lst: List[str], n: int) -> List[List[str]]:
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def _normalize_aldi_product(p: Dict[str, Any]) -> Dict[str, Any]:
    name = p.get("name")
    brand = p.get("brandName")
    sku = p.get("sku")
    price = (p.get("price") or {}).get("amountRelevantDisplay")
    size = p.get("sellingSize")
    cats = [c.get("name") for c in (p.get("categories") or []) if c.get("name")]
    slug = p.get("urlSlugText")
    url = f"{ALDI_WEB}/{slug}" if slug else None
    snap = (p.get("countryExtensions") or {}).get("usSnapEligible")

    display_price = price
    if size and price:
        # keep it compact and familiar to your DB
        display_price = f"{price}"

    return {
        "store_name": "Aldi",
        "product_name": (name or "")[:200],
        "price": display_price,
        "original_price": None,
        "discount": None,
        "category": cats[-1] if cats else None,
        "description": f"{brand or ''}".strip() or None,
        "image_url": None,          # (Aldi doesn't expose img on this endpoint reliably)
        "deal_url": url,
        "valid_from": None,
        "valid_until": None,
        # not persisted but can be handy while debugging:
        "_cats": cats,
        "_sku": sku,
        "_snap": snap,
    }


def _looks_like_deal(product: Dict[str, Any]) -> bool:
    cats = set(product.get("_cats") or [])
    # Tag a product as a "deal" if any category token appears
    return any(tok in cats for tok in DEAL_CATEGORY_TOKENS)


async def _collect_skus_via_playwright(headless: bool = True, max_entries_per_page: int = 12) -> List[str]:
    """
    Open a real browser, visit a handful of pages, and capture any
    /v2/products?skus=... requests to harvest SKUs.
    """
    from playwright.async_api import async_playwright

    seen: Set[str] = set()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        def on_request(req):
            try:
                url = req.url
                if "/v2/products" in url:
                    parsed = urlparse(url)
                    qs = parse_qs(parsed.query)
                    skus_param = qs.get("skus", [])
                    if skus_param:
                        for sku in ",".join(skus_param).split(","):
                            sku = sku.strip()
                            if sku:
                                seen.add(sku)
            except Exception:
                pass

        page.on("request", on_request)

        for url in ENTRY_PAGES:
            try:
                await page.goto(url, wait_until="load", timeout=60000)
                # Let XHRs fire for a bit
                await page.wait_for_timeout(2500)
            except Exception:
                # keep going; some pages 404 softly or time out occasionally
                continue

        await context.close()
        await browser.close()

    return list(seen)


def _hydrate_products_from_api(skus: List[str]) -> List[Dict[str, Any]]:
    """
    Call /v2/products in chunks to retrieve product JSON.
    """
    out: List[Dict[str, Any]] = []
    headers = {
        "accept": "application/json",
        "origin": ALDI_WEB,
        "referer": f"{ALDI_WEB}/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/142.0.0.0 Safari/537.36"
        ),
    }

    for group in _chunk(skus, 30):
        params = {
            "servicePoint": SERVICE_POINT,
            "serviceType": SERVICE_TYPE,
            "skus": ",".join(group),
            "limit": "12",  # mirrors real traffic; not required for correctness
        }
        resp = requests.get(ALDI_API, params=params, headers=headers, timeout=20)
        if resp.status_code != 200:
            continue
        try:
            data = resp.json()
        except Exception:
            continue
        out.extend(data.get("data", []))

    return out


class AldiScraper:
    """
    Playwright-bootstrapped Aldi scraper:
      1) Uses a real browser to capture live SKUs Aldi is currently promoting.
      2) Hydrates those SKUs via /v2/products.
      3) Returns DB-ready 'deals' filtered by likely-deal categories.

    TIP for Railway: make sure browsers are installed at boot.
    """

    def __init__(self, headless: Optional[bool] = None):
        # default to headless in production unless ALDI_HEADFUL=1
        if headless is None:
            headless = os.environ.get("ALDI_HEADFUL") not in ("1", "true", "True")
        self.headless = headless

    def scrape_deals(self) -> List[Dict[str, Any]]:
        # 1) collect SKUs with Playwright
        try:
            skus = asyncio.run(_collect_skus_via_playwright(headless=self.headless))
        except Exception as e:
            print(f"❌ Aldi Playwright bootstrap failed: {e}")
            skus = []

        if not skus:
            print("⚠️ Aldi: no SKUs captured; returning empty list")
            return []

        # 2) hydrate SKUs via API
        products = _hydrate_products_from_api(skus)
        if not products:
            print("⚠️ Aldi: no products hydrated from API")
            return []

        # 3) normalize + filter for 'deals'
        normalized = [_normalize_aldi_product(p) for p in products]
        deals = [n for n in normalized if _looks_like_deal(n)]

        # cleanup temp keys
        for d in deals:
            d.pop("_cats", None)
            d.pop("_sku", None)
            d.pop("_snap", None)

        # pretty log
        for i, d in enumerate(deals[:25], start=1):
            print(f"  🥬 [{i}] {d['product_name'][:60]} | {d['price']} | {d.get('category')}")

        print(f"🥬 Aldi total scraped deals: {len(deals)}")
        return deals


if __name__ == "__main__":
    # local smoke test
    scraper = AldiScraper(headless=False)
    ds = scraper.scrape_deals()
    print(f"\nFound {len(ds)} Aldi deals.\n")
    for x in ds[:10]:
        print(f"{x['product_name']} -> {x['price']}")
        if x.get('deal_url'):
            print(f"   {x['deal_url']}")
