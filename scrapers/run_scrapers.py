"""
Script to run all scrapers and upload deals to the API
Can be run manually or via cron job
"""

import requests
import sys
from datetime import datetime
from walmart_scraper import WalmartScraper

# Configuration
API_URL = "https://postgres-production-18e7.up.railway.app"  # Change to your deployed URL


def upload_deals(deals, api_url):
    """Upload deals to the API"""
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
    """Run Walmart scraper"""
    print("🛒 Running Walmart scraper...")
    try:
        scraper = WalmartScraper()
        deals = scraper.scrape_deals()
        print(f"   Found {len(deals)} deals")
        return deals
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []


def run_all_scrapers(api_url):
    """Run all scrapers and upload results"""
    print(f"\n{'=' * 60}")
    print(f"Starting scraper run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}\n")

    all_deals = []

    # Run Walmart scraper
    walmart_deals = run_walmart_scraper()
    all_deals.extend(walmart_deals)

    # TODO: Add more scrapers here
    # target_deals = run_target_scraper()
    # all_deals.extend(target_deals)

    # kroger_deals = run_kroger_scraper()
    # all_deals.extend(kroger_deals)

    print(f"\n{'=' * 60}")
    print(f"Total deals collected: {len(all_deals)}")
    print(f"{'=' * 60}\n")

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
    # Allow API URL to be passed as command line argument
    api_url = sys.argv[1] if len(sys.argv) > 1 else API_URL
    exit_code = run_all_scrapers(api_url)
    sys.exit(exit_code)