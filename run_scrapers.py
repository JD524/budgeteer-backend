"""
Script to run all scrapers and upload deals to the API.
Can be run manually or via scheduler.
"""

import sys
import requests
from datetime import datetime

from scrapers.walmart_scraper import WalmartScraper
from scrapers.giant_eagle_scraper import GiantEagleScraper
from scrapers.aldi_scraper import AldiScraper

# Default API URL (can still be overridden by CLI arg or env via scheduled_scraper)
API_URL = "https://web-production-b311.up.railway.app"


def upload_deals(deals, api_url):
    """Upload deals to the API in bulk."""
    try:
        response = requests.post(
            f"{api_url}/api/admin/deals/bulk",
            json=deals,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Successfully uploaded {result.get('deals_processed', 0)} deals")
            return True
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(response.text)
            return False

    except Exception as e:
        print(f"❌ Error uploading deals: {e}")
        return False


def run_walmart_scraper():
    """Run Walmart scraper."""
    print("🛒 Running Walmart scraper...")
    try:
        scraper = WalmartScraper()
        deals = scraper.scrape_deals()
        print(f"   Walmart found {len(deals)} deals")
        return deals
    except Exception as e:
        print(f"   ❌ Walmart error: {e}")
        return []


def run_giant_eagle_scraper():
    """Run Giant Eagle scraper (currently hardcoded to Stow / storeCode=4096)."""
    print("🦅 Running Giant Eagle scraper (storeCode=4096)...")
    try:
        scraper = GiantEagleScraper(store_code="4096", store_label="stow")

        # IMPORTANT: optionally simplify store_name for now so the app shows just "Giant Eagle".
        # We'll do that here after we scrape so we don't have to change the scraper file itself.
        raw_deals = scraper.scrape_deals()

        for d in raw_deals:
            # Overwrite "Giant Eagle (stow)" → "Giant Eagle"
            if d.get("store_name"):
                d["store_name"] = "Giant Eagle"

        print(f"   Giant Eagle found {len(raw_deals)} deals")
        return raw_deals
    except Exception as e:
        print(f"   ❌ Giant Eagle error: {e}")
        return []

def run_aldi_scraper():
    """Run Aldi scraper (Playwright-bootstrapped)."""
    print("🥬 Running Aldi scraper...")
    try:
        # headless in production; toggle with env ALDI_HEADFUL=1 for local debugging
        scraper = AldiScraper()
        deals = scraper.scrape_deals()
        print(f"   Aldi found {len(deals)} deals")
        return deals
    except Exception as e:
        print(f"   ❌ Aldi error: {e}")
        return []


def run_all_scrapers(api_url):
    """Run all scrapers and upload results."""
    print("\n" + "=" * 60)
    print(f"Starting scraper run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")

    all_deals = []

    # Walmart
    walmart_deals = run_walmart_scraper()
    all_deals.extend(walmart_deals)

    # Giant Eagle
    giant_eagle_deals = run_giant_eagle_scraper()
    all_deals.extend(giant_eagle_deals)

    # Aldi
    aldi_deals = run_aldi_scraper()
    all_deals.extend(aldi_deals)

    print("\n" + "=" * 60)
    print(f"Total deals collected: {len(all_deals)}")
    print("=" * 60 + "\n")

    if all_deals:
        print("📤 Uploading deals to API...")
        success = upload_deals(all_deals, api_url)

        if success:
            print("\n✅ Scraper run completed successfully!")
            return 0
        else:
            print("\n❌ Failed to upload deals")
            return 1
    else:
        print("\n⚠️  No deals found")
        return 1


if __name__ == '__main__':
    # Allow API URL to be passed as command line argument:
    #   python scrapers/run_scrapers.py https://your-api-here
    api_url = sys.argv[1] if len(sys.argv) > 1 else API_URL
    exit_code = run_all_scrapers(api_url)
    sys.exit(exit_code)
