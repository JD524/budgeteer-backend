# scrapers/marcs_scraper.py
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests

MARCS_OFFERS_URL = "https://www.marcs.com/Flipp/inmar_offers.json"


class MarcsScraper:
    """
    Scrapes Marc's digital offers from their public Inmar JSON:
    https://www.marcs.com/Flipp/inmar_offers.json

    Returns a list of dicts in the SAME shape your /api/admin/deals/bulk expects.
    """

    def __init__(self, url: str = MARCS_OFFERS_URL):
        self.url = url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.marcs.com/weeklyad",
            }
        )

    # ----------------------------------------------------
    # Fetch + parsing
    # ----------------------------------------------------
    def _fetch_offers(self) -> List[Dict[str, Any]]:
        try:
            resp = self.session.get(self.url, timeout=15)
            resp.raise_for_status()
            data = resp.json() or {}
        except Exception as e:
            logging.error("Marc's: failed to fetch %s: %s", self.url, e)
            return []

        offers_root = data.get("Offers") or {}
        offers = offers_root.get("Offer") or []
        if not isinstance(offers, list):
            offers = [offers]
        return offers

    # ----------------------------------------------------
    # Helpers
    # ----------------------------------------------------
    @staticmethod
    def _pick_valid_from(offer: Dict[str, Any]) -> Optional[str]:
        for key in ("ActiveDate", "ClipStartDate"):
            v = offer.get(key)
            if v:
                return v
        return datetime.utcnow().isoformat()

    @staticmethod
    def _pick_valid_until(offer: Dict[str, Any]) -> Optional[str]:
        for key in ("ExpirationDate", "ClipEndDate"):
            v = offer.get(key)
            if v:
                return v
        return (datetime.utcnow() + timedelta(days=7)).isoformat()

    @staticmethod
    def _is_active_now(offer: Dict[str, Any]) -> bool:
        """Return True if today's date is between start and end dates (inclusive)."""
        today = datetime.utcnow().date()

        start_str = offer.get("ActiveDate") or offer.get("ClipStartDate")
        end_str = offer.get("ExpirationDate") or offer.get("ClipEndDate")

        try:
            if start_str:
                start = datetime.strptime(start_str, "%Y-%m-%d").date()
                if today < start:
                    return False
        except Exception:
            pass

        try:
            if end_str:
                end = datetime.strptime(end_str, "%Y-%m-%d").date()
                if today > end:
                    return False
        except Exception:
            pass

        return True

    # ----------------------------------------------------
    # Main
    # ----------------------------------------------------
    def scrape_deals(self) -> List[Dict[str, Any]]:
        raw_offers = self._fetch_offers()
        if not raw_offers:
            print("🧡 Marc's: fetched 0 offers from inmar_offers.json")
            return []

        active_offers = [o for o in raw_offers if self._is_active_now(o)]
        print(f"🧡 Marc's: {len(active_offers)} of {len(raw_offers)} offers are currently active.")

        deals: List[Dict[str, Any]] = []
        for idx, off in enumerate(active_offers, start=1):
            short_desc = (
                off.get("ShortDescription")
                or off.get("OfferDescription")
                or off.get("ValueText")
                or f"Marc's offer {idx}"
            )
            product_name = short_desc[:200]
            discount_text = off.get("ValueText")
            desc = off.get("OfferDescription")
            cat = off.get("Category")
            img = off.get("ImageURL")
            deal_url = off.get("AvailabilityLink")

            valid_from = self._pick_valid_from(off)
            valid_until = self._pick_valid_until(off)

            deal = {
                "store_name": "Marc's",
                "product_name": product_name,
                "price": None,
                "original_price": None,
                "discount": discount_text,
                "category": cat,
                "description": desc,
                "image_url": img,
                "deal_url": deal_url,
                "valid_from": valid_from,
                "valid_until": valid_until,
            }
            deals.append(deal)
            print(f"🧡 [{idx}] {product_name[:60]} | {discount_text or 'no value'}")

        print(f"🧡 Marc's total scraped deals: {len(deals)} (active only)")
        return deals


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    s = MarcsScraper()
    out = s.scrape_deals()
    print(f"\nFound {len(out)} active Marc's deals.\n")
    for d in out[:10]:
        print(d["product_name"], "->", d.get("discount"))
