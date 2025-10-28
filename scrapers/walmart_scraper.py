import json
import logging
from typing import Any, Dict, List, Optional

import requests


class WalmartScraper:
    """
    Scrapes Walmart homepage 'Flash Deals' (and other ItemCarousel modules)
    using the GraphQL endpoint you captured.

    This tries to look/feel like GiantEagleScraper.scrape_deals():
    - returns a list of normalized deal dicts
    - prints a short summary line per deal
    """

    def __init__(self):
        # --- endpoint + headers/cookies from your captured request ---
        self.url = (
            "https://www.walmart.com/orchestra/home/graphql/HomePageWebRedesignBtf/"
            "97471cea0bb256c5caed77587c60c5c863e4c0c493eae4ce1051d86a6ad6a7de"
        )

        self.headers: Dict[str, str] = {
            "accept": "application/json",
            "accept-language": "en-US",
            "baggage": (
                "trafficType=customer,deviceType=desktop,renderScope=SSR,webRequestSource=Browser,"
                "pageName=homePage,isomorphicSessionId=fM7s68Z4vdqSyhOZ8KGwO,"
                "renderViewId=bfe4ff03-e54d-4e4d-acc0-95bf083e1bb4"
            ),
            "content-type": "application/json",
            "isbtf": "true",
            "origin": "https://www.walmart.com",
            "referer": "https://www.walmart.com/",
            "sec-ch-ua": '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "tenant-id": "elh9ie",
            "traceparent": "00-18728935f0149d5b47bec9df4ed73687-b4f07dc3fd555056-00",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/141.0.0.0 Safari/537.36"
            ),
            "wm-client-traceid": "18728935c926ad5b997ff8376ab277ae",
            "wm_mp": "true",
            "wm_page_url": "https://www.walmart.com/",
            "wm_qos.correlation_id": "WENzoK4ewJE3muBloefHPuS3PXV47s2nfZpz",
            "x-apollo-operation-name": "HomePageWebRedesignBtf",
            "x-enable-server-timing": "1",
            "x-latency-trace": "1",
            "x-o-bu": "WALMART-US",
            "x-o-ccm": "server",
            "x-o-correlation-id": "WENzoK4ewJE3muBloefHPuS3PXV47s2nfZpz",
            "x-o-gql-query": "query HomePageWebRedesignBtf",
            "x-o-mart": "B2C",
            "x-o-platform": "rweb",
            "x-o-platform-version": (
                "usweb-1.230.1-72b46a24d08b3b2f119e9a9c3e542a129a96385f-0241544r"
            ),
            "x-o-segment": "oaoh",
        }

        # NOTE: we include the core cookies you pasted (location, store, etc.).
        # If Walmart starts 403/418'ing again, you'll need to paste the rest of
        # the anti-bot cookies into here (px/akamai/bm_*).
        self.cookies: Dict[str, str] = {
            "vtc": "Rf6n5_hr5KjhaAyHSldq9s",
            "ACID": "8b86e975-5517-4398-b91f-4bd43f7dd6f2",
            "_m": "9",
            "assortmentStoreId": "4285",
            "hasACID": "true",
            "hasLocData": "1",
            "userAppVersion": "usweb-1.230.1-72b46a24d08b3b2f119e9a9c3e542a129a96385f-0241544r",
            "abqme": "true",
            "_intlbu": "false",
            "_shcc": "US",
            "isoLoc": "US_TX_t3",
            "locDataV3": (
                "eyJpc0RlZmF1bHRlZCI6ZmFsc2UsImlzRXhwbGljaXQiOmZhbHNlLCJpbnRlbnQiOiJTSElQUElORyIs"
                "InBpY2t1cCI6W3sibm9kZUlkIjoiNDI4NSIsImRpc3BsYXlOYW1lIjoiQ2xldmVsYW5kIFN1cGVyY2Vu"
                "dGVyIiwiYWRkcmVzcyI6eyJwb3N0YWxDb2RlIjoiNDQxMDkiLCJhZGRyZXNzTGluZTEiOiIzNDAwIFNU"
                "RUVMWUFSRCBEUiIsImNpdHkiOiJDbGV2ZWxhbmQiLCJzdGF0ZSI6Ik9IIiwiY291bnRyeSI6IlVTIn0s"
                "Imdlb1BvaW50Ijp7ImxhdGl0dWRlIjo0MS40NjE1ODEsImxvbmdpdHVkZSI6LTgxLjY5MjcxM30sInNj"
                "aGVkdWxlZEVuYWJsZWQiOnRydWUsInVuU2NoZWR1bGVkRW5hYmxlZCI6dHJ1ZSwic3RvcmVIcnMiOiIw"
                "NjowMC0yMjowMCIsImFsbG93ZWRXSUNBZ2VuY2llcyI6WyJPSCJdLCJzdXBwb3J0ZWRBY2Nlc3NUeXBl"
                "cyI6WyJQSUNLVVBfQ1VSQlNJREUiLCJXSVJFTEVTU19TRVJWSUNFIiwiQUNDX0lOR1JPVU5EIiwiQUND"
                "IiwiUElDS1VQX0JBS0VSWSIsIlBJQ0tVUF9JTlNUT1JFIiwiUElDS1VQX1NQRUNJQUxfRVZFTlQiXSwid"
                "GltZVpvbmUiOiJBbWVyaWNhL05ld19Zb3JrIiwic3RvcmVCcmFuZEZvcm1hdCI6IldhbG1hcnQgU3VwZX"
                "JjZW50ZXIiLCJzZWxlY3Rpb25UeXBlIjoiTFNfU0VMRUNURUQifSx7Im5vZGVJZCI6IjIzNjIifSx7Im5"
                "vZGVJZCI6IjIwNzMifSx7Im5vZGVJZCI6IjUwODIifSx7Im5vZGVJZCI6IjIyNjYifSx7Im5vZGVJZCI6"
                "IjE5MjcifSx7Im5vZGVJZCI6IjIzMTYifSx7Im5vZGVJZCI6IjE4NjMifSx7Im5vZGVJZCI6IjMyNTAif"
                "V0sInNoaXBwaW5nQWRkcmVzcyI6eyJsYXRpdHVkZSI6NDEuNDcyNTkyOSwibG9uZ2l0dWRlIjotODEuNj"
                "UyODIxODk5OTk5OTksInBvc3RhbENvZGUiOiI0NDEyNyIsImNpdHkiOiJDbGV2ZWxhbmQiLCJzdGF0ZSI"
                "6Ik9IIiwiY291bnRyeUNvZGUiOiJVU0EiLCJnaWZ0QWRkcmVzcyI6ZmFsc2UsInRpbWVab25lIjoiQW1l"
                "cmljYS9OZXdfWW9yayIsImFsbG93ZWRXSUNBZ2VuY2llcyI6WyJPSCJdfSwiYXNzb3J0bWVudCI6eyJu"
                "b2RlSWQiOiI0Mjg1IiwiZGlzcGxheU5hbWUiOiJDbGV2ZWxhbmQgU3VwZXJjZW50ZXIiLCJpbnRlbnQi"
                "OiJQSUNLVVAifSwiaW5zdG9yZSI6ZmFsc2UsImRlbGl2ZXJ5Ijp7Im5vZGVJZCI6IjQyODUiLCJkaXNw"
                "bGF5TmFtZSI6IkNsZXZlbGFuZCBTdXBlcmNlbnRlciIsImFkZHJlc3MiOnsicG9zdGFsQ29kZSI6IjQ0"
                "MTA5IiwiYWRkcmVzc0xpbmUxIjoiMzQwMCBTVEVFTFlBUkQgRFIiLCJjaXR5IjoiQ2xldmVsYW5kIiwi"
                "c3RhdGUiOiJPSCIsImNvdW50cnkiOiJVUyJ9LCJnZW9Qb2ludCI6eyJsYXRpdHVkZSI6NDEuNDYxNTgx"
                "LCJsb25naXR1ZGUiOi04MS42OTI3MTN9LCJ0eXBlIjoiREVMSVZFUlkiLCJzY2hlZHVsZWRFbmFibGVk"
                "IjpmYWxzZSwidW5TY2hlZHVsZWRFbmFibGVkIjpmYWxzZSwiYWNjZXNzUG9pbnRzIjpbeyJhY2Nlc3NU"
                "eXBlIjoiREVMSVZFUllfQUREUkVTUyJ9XSwiaXNFeHByZXNzRGVsaXZlcnlPbmx5IjpmYWxzZSwiYWxs"
                "b3dlZFdJQ0FnZW5jaWVzIjpbIk9IIl0sInN1cHBvcnRlZEFjY2Vzc1R5cGVzIjpbIkRFTElWRVJZX0FE"
                "RFJFU1MiLCJBQ0MiXSwidGltZVpvbmUiOiJBbWVyaWNhL05ld19Zb3JrIiwic3RvcmVCcmFuZEZvcm1h"
                "dCI6IldhbG1hcnQgU3VwZXJjZW50ZXIiLCJzZWxlY3Rpb25UeXBlIjoiTFNfU0VMRUNURUQifSwiaXNn"
                "ZW9JbnRsVXNlciI6ZmFsc2UsIm1wRGVsU3RvcmVDb3VudCI6MCwicmVmcmVzaEF0IjoxNzYxNjQxNTc5"
                "Mzc5LCJ2YWxpZGF0ZUtleSI6InByb2Q6djI6OGI4NmU5NzUtNTUxNy00Mzk4LWI5MWYtNGJkNDNmN2Rk"
                "NmYyIn0%3D"
            ),
            "locGuestData": (
                "eyJpbnRlbnQiOiJTSElQUElORyIsImlzRXhwbGljaXQiOmZhbHNlLCJzdG9yZUludGVudCI6IlBJQ0tV"
                "UCIsIm1lcmdlRmxhZyI6ZmFsc2UsImlzRGVmYXVsdGVkIjpmYWxzZSwicGlja3VwIjp7Im5vZGVJZCI6"
                "IjQyODUiLCJ0aW1lc3RhbXAiOjE3NjE0MDc3ODA2MjMsInNlbGVjdGlvblR5cGUiOiJMU19TRUxFQ1RF"
                "RCIsInNlbGVjdGlvblNvdXJjZSI6IklQX1NOSUZGRURfQllfTFMifSwic2hpcHBpbmdBZGRyZXNzIjp7"
                "InRpbWVzdGFtcCI6MTc2MTQwNzc4MDYyMywidHlwZSI6InBhcnRpYWwtbG9jYXRpb24iLCJnaWZ0QWRk"
                "cmVzcyI6ZmFsc2UsInBvc3RhbENvZGUiOiI0NDEyNyIsImRlbGl2ZXJ5U3RvcmVMaXN0IjpbeyJub2Rl"
                "SWQiOiI0Mjg1IiwidHlwZSI6IkRFTElWRVJZIiwidGltZXN0YW1wIjoxNzYxMzk4MzkxMTEyLCJkZWxp"
                "dmVyeVRpZXIiOm51bGwsInNlbGVjdGlvblR5cGUiOiJMU19TRUxFQ1RFRCIsInNlbGVjdGlvblNvdXJj"
                "ZSI6IklQX1NOSUZGRURfQllfTFMifV0sImNpdHkiOiJDbGV2ZWxhbmQiLCJzdGF0ZSI6Ik9IIn0sInBv"
                "c3RhbENvZGUiOnsidGltZXN0YW1wIjoxNzYxNDA3NzgwNjIzLCJiYXNlIjoiNDQxMjcifSwibXAiOltd"
                "LCJtc3AiOnsibm9kZUlkcyI6WyIyMzYyIiwiMjA3MyIsIjUwODIiLCIyMjY2IiwiMTkyNyIsIjIzMTYi"
                "LCIxODYzIiwiMzI1MCJdLCJ0aW1lc3RhbXAiOjE3NjE0MDc3ODA2MjF9LCJtcERlbFN0b3JlQ291bnQi"
                "OjAsInNob3dMb2NhbEV4cGVyaWVuY2UiOmZhbHNlLCJzaG93TE1QRW50cnlQb2ludCI6ZmFsc2UsIm1w"
                "VW5pcXVlU2VsbGVyQ291bnQiOjAsInZhbGlkYXRlS2V5IjoicHJvZDp2Mjo4Yjg2ZTk3NS01NTE3LTQz"
                "OTgtYjkxZi00YmQ0M2Y3ZGQ2ZjIifQ%3D%3D"
            ),
        }

        # Payload: same "variables" object you captured from DevTools,
        # trimmed only to the fields Walmart actually cares about.
        # We include the Flash Deals carousel in lazyModules.
        self.variables: Dict[str, Any] = {
            "tenant": "WM_GLASS",
            "isBTF": True,
            "contentLayoutVersion": "v2",
            "pageType": "GlassHomePageDesktopV1",
            "postProcessingVersion": 2,
            "p13NCallType": "BTF",

            "enableSeoHomePageMetaData": True,
            "enableEventTimerSeconds": True,
            "isPlusBannerRedesign": True,
            "enableAvMode": False,
            "enableClickTrackingURL": False,
            "enableExclusiveWplusLabel": False,
            "enableMultiSaveOnCarousels": False,
            "enableP13nAmendsData": False,
            "enableProductCategory": False,
            "enableProductGridResponseV1": False,
            "enableProductsField": False,
            "enableSubscriptionString": False,
            "enableSwatch": False,

            "p13n": {
                "selectedIntent": "NONE",
                "userClientInfo": {"deviceType": "desktop"},
            },
            "userClientInfo": {"deviceType": "desktop"},
            "userReqInfo": {"isMoreOptionsTileEnabled": True},
            "p13nMetadata": "TFo07QMAAPH/QHsidXNlZE1vZGVscyI6eyJNZXNzYWdlIjpbIjlmNzNmNTgzLWI3NjgtNDZhYy1iMGJiLWNjYTc5MjE3ZDhhZCIsImIzN2RmZDM1LWViYWItNGUxYy1hN2VmLTVjYWYzMjYwZWZmOCIsImQxNDg0OTk0LWY3NjktNDE3OC1hMzFmLTVlY2MyNWU1NTVkMiIsImU3NmQ2MTU4LTQ4NGItNDA3MC1iYmEwLWFmYWE1NzliYjg2NSIsIjVhYzgyOTY4LTgxZGUtNDYyZi05MGQ3LWEzYzVhNmM2MjNkZiIsIjlmZTM5Y2FiLTQ0OTgtNGFmNS04YzRmLWYzYWQwNmM3MTA4YiIsIjNmZDkwNTJhLTljYjQtNGQzMi05OTg0LWE2YWNmNGUzZmRhYyIsIjY3NTA5M2M1LWQ1MTktNDU1Zi1hNWY1LTFlMmI4MjUzZWVOAPAUNzVmY2ViM2EtNWYzYi00ZGYzLTliZDctOWE4ZmEwMmMwYTQnAPAxZmIxMDFlNjQtYmRkNy00MTU5LWIyMGQtN2FhYjZlNDg5YWU1Il0sIkdsYXNzSG9tZXBhZ2VJdGVtTW9kdWxlc6MB8AhDb250aW51ZVlvdXJTaG9wcGluZyIsIiYA8CRDYXJvdXNlbF8wYjlkZTE4Ny01ODE1LTRkMjUtOGQyZi1jYzRkMDQyZTcxYjFfaXRlbXNuAFBBc3NldFsA8HNjY2ZkYWZkNS0zY2M1LTRhOWItYTY4My1lNWVlZWIxZTIzNjAiLCI0ZTc2M2Q1YS1iNjM4LTQ0MjEtOWZlNy00YmFmM2RhNGM2ZjEiLCJjNTA2NDBmMS00N2RlLTQ2MTMtYTA2NC04NWU4NjM0YTQ0MGEiLCI3ZjNkNGIxNC02NjAyFAHxBDgtOTQwZS1mZmI4MjhjNGNiYjNzAlA1Y2MzMpoC8fUzMS00YmNlLWJkMjAtNjBjZmUxODg3Y2M1IiwiNmM4N2MwODYtMWNkOS00MDRmLWE0MmUtNTdlOTBhNmMzNDI0IiwiYzM1MGFlN2MtYWUyNC00ODc5LWI1YjktYjA2NGU3ODRjOTFhIiwiODBlMjRhZmYtY2RmZS00ZDE2LWIzMTMtNjk5MDg5MTc1MDUwIiwiZWRhZDQyMWItYjM4OS00NWY4LThkZmUtNDJmY2QxYzNlNTk3IiwiNDVlMzg3MjgtNzQ0MS00ZGJkLWJiMmMtMDYwZDQ1YWNhNjI0Il19LCJwcmV2aW91c1JlZnJlc2hDb3VudCI6MCwidG90YWxQYWdlcw8AUFNob3duEAJiZW50Wm9uIAIVYxAAUGU0Il19",

            "selectedIntent": "NONE",

            "lazyModules": [
                {
                    "name": "Flash Deals Item Carousel Module - 12.12.24 ",
                    "type": "ItemCarousel",
                    "version": 2,
                    "status": "published",
                }
            ],
        }

    # ---------------- internal helpers ----------------

    def _looks_blocked(self, text: str, status: int) -> bool:
        t = (text or "").lower()
        if status in (403, 418, 429):
            return True
        if "access denied" in t:
            return True
        if "captcha" in t or "distil_r_captcha" in t:
            return True
        if "hang on- you're so close" in t:
            return True
        return False

    def _fetch_modules(self) -> Optional[Dict[str, Any]]:
        """
        Do the POST to Walmart. Return parsed JSON or None on block/error.
        """
        session = requests.Session()
        session.headers.update(self.headers)

        cookiejar = requests.cookies.RequestsCookieJar()
        for k, v in self.cookies.items():
            cookiejar.set(k, v, domain=".walmart.com", path="/")
        session.cookies = cookiejar

        body = {"variables": self.variables}

        resp = session.post(self.url, json=body, timeout=20)

        logging.info("Walmart status: %s", resp.status_code)
        text = resp.text or ""

        if self._looks_blocked(text, resp.status_code):
            logging.error("Walmart blocked/throttled. First 300 chars:\n%r", text[:300])
            return None

        if "application/json" not in (resp.headers.get("content-type", "")).lower():
            logging.error("Unexpected Walmart content-type. Body[0:300]=%r", text[:300])
            return None

        try:
            return resp.json()
        except Exception as e:
            logging.error("JSON parse fail: %s", e)
            logging.error("Body[0:300]=%r", text[:300])
            return None

    def _pull_products_from_layout(self, data_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Walk Walmart's contentLayout.modules and gather every product object.
        """
        out: List[Dict[str, Any]] = []
        layout = (data_json.get("data") or {}).get("contentLayout") or {}
        modules = layout.get("modules") or []

        for mod in modules:
            cfgs = mod.get("configs") or {}
            # Newer shape:
            products_cfg = (cfgs.get("productsConfig") or {}).get("products") or []
            # Fallback shape:
            if not products_cfg and mod.get("products"):
                products_cfg = mod.get("products")

            for p in products_cfg:
                out.append(p)

        return out

    def _normalize_product(self, p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert Walmart product JSON into a compact "deal card".
        Skip items with no sane price.
        """

        name = p.get("name") or p.get("title")
        if not name:
            return None

        price_info = p.get("priceInfo") or {}
        current = price_info.get("currentPrice") or {}
        was = price_info.get("wasPrice") or {}
        savings_amt = price_info.get("savingsAmount") or {}
        savings = price_info.get("savings") or {}

        # current price string
        now_price_val = current.get("price")
        now_price_str = current.get("priceDisplay") or current.get("priceString")
        if not now_price_val and not now_price_str:
            # if we truly can't tell the price, skip
            return None

        # original / was price
        orig_price_str = was.get("priceString")

        # savings text like "SAVE $90.00"
        save_text = savings_amt.get("priceString") or savings.get("priceString")

        # Construct a human-friendly price line:
        # ex: "Now $149.99 (SAVE $90.00)"
        base_price_text = now_price_str or f"${now_price_val}"
        if save_text:
            display_price = f"{base_price_text} ({save_text})"
        else:
            display_price = base_price_text

        # rating / reviews
        rating = p.get("averageRating")
        reviews = p.get("numberOfReviews")

        # badges -> ["Clearance", "Reduced price", ...]
        badges_list: List[str] = []
        badges = (p.get("badges") or {}).get("flags") or []
        for b in badges:
            t = b.get("text")
            if t:
                badges_list.append(t)

        # also sometimes lives under badges.groupsV2[].members[].content[].value
        groupsV2 = (p.get("badges") or {}).get("groupsV2") or []
        for group in groupsV2:
            for mem in group.get("members", []):
                for content in mem.get("content", []):
                    val = content.get("value")
                    if val:
                        badges_list.append(val)

        # de-dupe badges
        badges_list = list(dict.fromkeys(badges_list))

        # thumbnail
        img = (p.get("imageInfo") or {}).get("thumbnailUrl")

        # deep link
        rel_url = (
            p.get("canonicalUrl")
            or p.get("productUrl")
            or p.get("url")
        )
        if rel_url:
            deal_url = "https://www.walmart.com" + rel_url
        else:
            deal_url = None

        return {
            "store_name": "Walmart",
            "product_name": name[:200],
            "price": display_price,
            "original_price": orig_price_str,
            "rating": rating,
            "reviews": reviews,
            "badges": badges_list,
            "image_url": img,
            "deal_url": deal_url,
        }

    def scrape_deals(self) -> List[Dict[str, Any]]:
        """
        High-level: fetch modules, pull products, normalize them.
        Prints short lines for debugging (like GiantEagleScraper).
        """
        data_json = self._fetch_modules()
        if not data_json:
            print("⚠️ No data returned from Walmart API")
            return []

        raw_products = self._pull_products_from_layout(data_json)

        deals: List[Dict[str, Any]] = []
        for idx, p in enumerate(raw_products):
            norm = self._normalize_product(p)
            if not norm:
                continue
            deals.append(norm)

            # pretty console line, like Giant Eagle
            line_left = norm["product_name"][:60]
            line_price = norm["price"]
            badge_preview = ", ".join(norm["badges"][:2]) if norm["badges"] else ""
            if badge_preview:
                print(f"  🛒 [{idx+1}] {line_left} | {line_price} | {badge_preview}")
            else:
                print(f"  🛒 [{idx+1}] {line_left} | {line_price}")

        print(f"🛍️ Walmart total scraped deals: {len(deals)}")
        return deals


# Standalone smoke test, same style as GiantEagleScraper
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = WalmartScraper()
    deals = scraper.scrape_deals()

    print(f"\nFound {len(deals)} Walmart deals.\n")
    for d in deals[:10]:
        print(
            f"{d['product_name']} -> {d['price']} "
            f"(orig {d.get('original_price')})"
        )
        if d["deal_url"]:
            print(f"   {d['deal_url']}")
