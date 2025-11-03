#!/usr/bin/env python3
"""
Dollar General scraper (stable version, no Playwright)

- tries to read latest ID from dg_publication_id.txt
- else uses env DG_FLIPP_PUBLICATION_ID
- else uses hardcoded known-good ID
- fetches products from Flipp and normalizes
- allows CLI override: --pub 7531003
"""

import os
import time
import logging
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

FLIPP_BASE = "https://dam.flippenterprise.net"

DG_FLIPP_ACCESS_TOKEN = os.getenv(
    "DG_FLIPP_ACCESS_TOKEN",
    "00be606cd7cb8b0cf999e3c7b038a2fe",
)

DG_FALLBACK_PUBLICATION_ID = os.getenv(
    "DG_FLIPP_PUBLICATION_ID",
    "7534096",   # the one you captured that returns ~319 items
)

DG_ID_FILE = Path(__file__).parent / "dg_publication_id.txt"

TIMEOUT = 12
RETRIES = 3
SLEEP = 1.0

API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.dollargeneral.com",
    "Referer": "https://www.dollargeneral.com/deals/weekly-ads",
}


def _get_json(url: str, params: Dict[str, Any]) -> Any:
    last_exc = None
    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=API_HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            time.sleep(SLEEP)
    raise last_exc


def _read_id_file() -> Optional[str]:
    if DG_ID_FILE.exists():
        t = DG_ID_FILE.read_text(encoding="utf-8").strip()
        if t.isdigit():
            return t
    return None


def fetch_publication_products(pub_id: str, token: str) -> List[Dict[str, Any]]:
    url = f"{FLIPP_BASE}/flyerkit/publication/{pub_id}/products"
    params = {
        "display_type": "all",
        "locale": "en",
        "access_token": token,
    }
    try:
        data = _get_json(url, params)
    except requests.HTTPError as e:
        # if they complain about locale (422), drop it
        if e.response is not None and e.response.status_code == 422:
            params.pop("locale", None)
            data = _get_json(url, params)
        else:
            raise

    if isinstance(data, list):
        return data
    return data.get("products") or data.get("items") or []


def normalize_offer(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "offer_id": raw.get("id"),
        "title": raw.get("name"),
        "description": raw.get("description"),
        "image": raw.get("image_url"),
        "brand": raw.get("brand"),
        "sale_story": raw.get("sale_story"),
        "price_text": raw.get("price_text"),
        "pre_price_text": raw.get("pre_price_text"),
        "post_price_text": raw.get("post_price_text"),
        "valid_from": raw.get("valid_from"),
        "valid_to": raw.get("valid_to"),
        "web_url": raw.get("item_web_url"),
        "flyer_id": raw.get("flyer_id"),
        "categories": raw.get("categories") or [],
        "raw": raw,
    }


def scrape_dollar_general(
    zip_code: str = "44224",
    publication_id: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    tok = token or DG_FLIPP_ACCESS_TOKEN

    # priority:
    # 1. CLI / caller override
    if publication_id:
        pub_id = publication_id
    else:
        # 2. last discovered ID from file
        file_id = _read_id_file()
        if file_id:
            pub_id = file_id
        else:
            # 3. env / hardcoded
            pub_id = DG_FALLBACK_PUBLICATION_ID

    products = fetch_publication_products(pub_id, tok)
    offers = [normalize_offer(p) for p in products]

    return {
        "retailer": "dollar_general",
        "zip": zip_code,
        "publication_id": pub_id,
        "weekly_ad": offers,
        "count": len(offers),
    }


def main():
    parser = argparse.ArgumentParser(description="Dollar General scraper (stable)")
    parser.add_argument("--pub", type=str, help="override publication id")
    parser.add_argument("--zip", type=str, default="44224")
    args = parser.parse_args()

    data = scrape_dollar_general(zip_code=args.zip, publication_id=args.pub)
    print(f"DG -> {data['count']} items (pub {data['publication_id']})")
    for item in data["weekly_ad"][:5]:
        print("-", item["title"], "=>", item["sale_story"])


if __name__ == "__main__":
    main()
