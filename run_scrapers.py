"""
Script to run all scrapers and upload deals to the API.
Works both:
- locally (to http://127.0.0.1:5000)
- and against Railway (https://web-production-b311.up.railway.app)
"""

import sys
import requests
from datetime import datetime

from scrapers.walmart_scraper import WalmartScraper
from scrapers.giant_eagle_scraper import GiantEagleScraper
from scrapers.aldi_scraper import AldiScraper
from scrapers.dollar_general_scraper import scrape_dollar_general
from scrapers.marcs_scraper import MarcsScraper   # 👈 NEW

# default: your Railway app
DEFAULT_API_URL = "https://web-production-b311.up.railway.app"


# ---------------------------------------------------------------------
# UPLOAD
# ---------------------------------------------------------------------
def upload_deals(deals, api_url: str):
    """
    Try to upload to the given api_url.
    If Railway says "Application not found" (404), fall back to local Flask.
    """
    payload = deals
    urls_to_try = [api_url]

    # if user is running locally with no arg, and Railway is down,
    # we can still make it succeed locally:
    if not api_url.startswith("http://127.0.0.1"):
        urls_to_try.append("http://127.0.0.1:5000")

    last_err = None
    for url in urls_to_try:
        try:
            resp = requests.post(f"{url}/api/admin/deals/bulk", json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                print(f"↩️  API responded with 200 at {url}")
                print(f"📦 API body: {data}")
                return True
            else:
                print(f"❌ Upload failed to {url}: {resp.status_code}")
                print(resp.text)
                last_err = resp.text
        except Exception as e:
            print(f"❌ Error uploading to {url}: {e}")
            last_err = str(e)

    print("❌ Failed to upload deals to all targets")
    if last_err:
        print(f"Last error: {last_err}")
    return False


# ---------------------------------------------------------------------
# NORMALIZATION (make data DB-safe)
# ---------------------------------------------------------------------
def _normalize_deals(
    deals,
    *,
    default_store: str | None = None,
    fallback_name_prefix: str = "Deal",
):
    """
    Make sure every deal has:
      - store_name
      - product_name
    because your Flask model requires them.
    """
    normalized = []
    for idx, d in enumerate(deals):
        if not isinstance(d, dict):
            continue

        store_name = d.get("store_name") or d.get("store") or default_store
        product_name = d.get("product_name")

        # DG case: only description
        if not product_name:
            desc = (
                d.get("description")
                or d.get("title")
                or d.get("name")
                or ""
            )
            if desc:
                product_name = desc
            else:
                product_name = f"{fallback_name_prefix} #{idx+1}"

        # clamp to DB column
        if product_name and len(product_name) > 500:
            product_name = product_name[:500]

        d["store_name"] = store_name or "Unknown Store"
        d["product_name"] = product_name

        normalized.append(d)

    return normalized


# ---------------------------------------------------------------------
# INDIVIDUAL SCRAPERS
# ---------------------------------------------------------------------
def run_walmart_scraper():
    print("🛒 Running Walmart scraper...")
    try:
        scraper = WalmartScraper()
        deals = scraper.scrape_deals()
        print(f"   Walmart found {len(deals)} deals")
        return _normalize_deals(
            deals,
            default_store="Walmart",
            fallback_name_prefix="Walmart item",
        )
    except Exception as e:
        print(f"   ❌ Walmart error: {e}")
        return []


def run_giant_eagle_scraper():
    print("🦅 Running Giant Eagle scraper (storeCode=4096)...")
    try:
        scraper = GiantEagleScraper(store_code="4096", store_label="stow")
        raw_deals = scraper.scrape_deals()

        # force nicer store name
        for d in raw_deals:
            d["store_name"] = "Giant Eagle"

        print(f"   Giant Eagle found {len(raw_deals)} deals")
        return _normalize_deals(
            raw_deals,
            default_store="Giant Eagle",
            fallback_name_prefix="Giant Eagle item",
        )
    except Exception as e:
        print(f"   ❌ Giant Eagle error: {e}")
        return []


def run_aldi_scraper():
    print("🥬 Running Aldi scraper...")
    try:
        scraper = AldiScraper()
        deals = scraper.scrape_deals()
        print(f"   Aldi found {len(deals)} deals")
        return _normalize_deals(
            deals,
            default_store="ALDI",
            fallback_name_prefix="Aldi item",
        )
    except Exception as e:
        print(f"   ❌ Aldi error: {e}")
        return []


def run_dollar_general_scraper():
    """
    Your DG scraper sometimes returns:
      - a LIST of items (good), OR
      - a DICT like {"retailer":..., "weekly_ad": [...], "count": ...}
    Our old code assumed LIST → `deals[:50]` blew up on dict.
    """
    print("💛 Running Dollar General scraper...")
    try:
        raw = scrape_dollar_general("44224")
        print(f"   Dollar General scraped {len(raw) if hasattr(raw, '__len__') else 'unknown'} raw items")

        # --- detect shape ---
        if isinstance(raw, dict):
            # try the shapes we've seen in your logs
            if "weekly_ad" in raw and isinstance(raw["weekly_ad"], list):
                deals = raw["weekly_ad"]
            elif "items" in raw and isinstance(raw["items"], list):
                deals = raw["items"]
            else:
                # nothing useful, just bail out gracefully
                print("   Dollar General: dict shape had no 'weekly_ad' or 'items' → skipping.")
                return []
        elif isinstance(raw, list):
            deals = raw
        else:
            print("   Dollar General: unknown return type → skipping.")
            return []

        # cap to 50 for API
        deals = deals[:50]
        print(f"   Dollar General capped to {len(deals)} deals for upload.")

        # normalize: force store + name
        deals = _normalize_deals(
            deals,
            default_store="Dollar General",
            fallback_name_prefix="Dollar General deal",
        )
        return deals

    except Exception as e:
        print(f"   ❌ Dollar General error: {e}")
        return []


def run_marcs_scraper():
    """
    NEW: Marc's digital offers (Inmar JSON).
    """
    print("🧡 Running Marc's scraper...")
    try:
        scraper = MarcsScraper()
        raw_deals = scraper.scrape_deals()
        print(f"   Marc's found {len(raw_deals)} active offers")

        # cap to avoid uploading 600+ items if they dump a huge file
        raw_deals = raw_deals[:50]

        return _normalize_deals(
            raw_deals,
            default_store="Marc's",
            fallback_name_prefix="Marc's offer",
        )
    except Exception as e:
        print(f"   ❌ Marc's error: {e}")
        return []


# ---------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------
def run_all_scrapers(api_url: str):
    print("\n" + "=" * 60)
    print(f"Starting scraper run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")

    all_deals = []

    # Walmart
    all_deals.extend(run_walmart_scraper())

    # Giant Eagle
    all_deals.extend(run_giant_eagle_scraper())

    # Aldi
    all_deals.extend(run_aldi_scraper())

    # Dollar General
    all_deals.extend(run_dollar_general_scraper())

    # Marc's (NEW)
    all_deals.extend(run_marcs_scraper())

    print("\n" + "=" * 60)
    print(f"Total deals collected: {len(all_deals)}")
    print("=" * 60 + "\n")

    if not all_deals:
        print("⚠️  No deals found")
        return 1

    print("📤 Uploading deals to API...")
    ok = upload_deals(all_deals, api_url)
    if ok:
        print("\n✅ Scraper run completed successfully!")
        return 0
    else:
        print("\n❌ Failed to upload deals")
        return 1


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # allow: python run_scrapers.py http://127.0.0.1:5000
    api_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_API_URL
    raise SystemExit(run_all_scrapers(api_url))
