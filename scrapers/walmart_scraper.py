import json
import logging
import requests
from typing import List, Dict, Any

WALMART_GRAPHQL_URL = "https://www.walmart.com/orchestra/home/graphql/HomePageWebRedesignBtf/97471cea0bb256c5caed77587c60c5c863e4c0c493eae4ce1051d86a6ad6a7de"

# These headers are copied from real browser traffic you captured.
WALMART_HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US",
    "content-type": "application/json",
    "sec-ch-ua": '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0.0.0 Safari/537.36"
    ),
    # Walmart expects these hint headers:
    "x-o-bu": "WALMART-US",
    "x-o-platform": "rweb",
    "x-o-platform-version": "usweb-1.230.1-72b46a24d08b3b2f119e9a9c3e542a129a96385f-0241544r",
    "x-o-mart": "B2C",
}

# Super important cookies. These are from YOUR browser session.
# For now we're hardcoding. Later we can make them env vars.
WALMART_COOKIES = {
    # session identity
    "vtc": "Rf6n5_hr5KjhaAyHSldq9s",
    "ACID": "8b86e975-5517-4398-b91f-4bd43f7dd6f2",
    "hasACID": "true",
    "_m": "9",

    # store / geo targeting
    "assortmentStoreId": "4285",

    # these blobs tell walmart what store/zip you're "in"
    # NOTE: paste EXACT values you saw in DevTools for locDataV3 and locGuestData.
    # I've truncated them here to show structure.
    "locDataV3": "eyJpc0RlZmF1bHRlZCI6ZmFsc2UsImlzRXhwbGljaXQiOmZhbHNlLCJpbnRlbnQiOiJTSElQUElORyIsInBpY2t1cCI6W3sibm9kZUlkIjoiNDI4NSIsImRpc3BsYXlOYW1lIjoiQ2xldmVsYW5kIFN1cGVyY2VudGVyIiwiYWRkcmVzcyI6eyJwb3N0YWxDb2RlIjoiNDQxMDkiLCJhZGRyZXNzTGluZTEiOiIzNDAwIFNURUVMWUFSRCBEUiIsImNpdHkiOiJDbGV2ZWxhbmQiLCJzdGF0ZSI6Ik9IIiwiY291bnRyeSI6IlVTIn0sImdlb1BvaW50Ijp7ImxhdGl0dWRlIjo0MS40NjE1ODEsImxvbmdpdHVkZSI6LTgxLjY5MjcxM30sInNjaGVkdWxlZEVuYWJsZWQiOnRydWUsInVuU2NoZWR1bGVkRW5hYmxlZCI6dHJ1ZSwic3RvcmVIcnMiOiIwNjowMC0yMjowMCIsImFsbG93ZWRXSUNBZ2VuY2llcyI6WyJPSCJdLCJzdXBwb3J0ZWRBY2Nlc3NUeXBlcyI6WyJQSUNLVVBfQ1VSQlNJREUiLCJXSVJFTEVTU19TRVJWSUNFIiwiQUNDX0lOR1JPVU5EIiwiQUNDIiwiUElDS1VQX0JBS0VSWSIsIlBJQ0tVUF9JTlNUT1JFIiwiUElDS1VQX1NQRUNJQUxfRVZFTlQiXSwidGltZVpvbmUiOiJBbWVyaWNhL05ld19Zb3JrIiwic3RvcmVCcmFuZEZvcm1hdCI6IldhbG1hcnQgU3VwZXJjZW50ZXIiLCJzZWxlY3Rpb25UeXBlIjoiTFNfU0VMRUNURUQifSx7Im5vZGVJZCI6IjIzNjIifV0=",  # <-- keep full string
    "locGuestData": "eyJpbnRlbnQiOiJTSElQUElORyIsImlzRXhwbGljaXQiOmZhbHNlLCJzdG9yZUludGVudCI6IlBJQ0tVUCIsIm1lcmdlRmxhZyI6ZmFsc2UsImlzRGVmYXVsdGVkIjpmYWxzZSwicGlja3VwIjp7Im5vZGVJZCI6IjQyODUiLCJ0aW1lc3RhbXAiOjE3NjE0MDc3ODA2MjMsInNlbGVjdGlvblR5cGUiOiJMU19TRUxFQ1RFRCIsInNlbGVjdGlvblNvdXJjZSI6IklQX1NOSUZGRURfQllfTFMifX0=",  # <-- keep full string
}

# This payload is the same structure Walmart expects on HomePageWebRedesignBtf
# (trimmed to only what's actually required to get carousels/modules back).
WALMART_BODY = {
    "variables": {
        "tenant": "WM_GLASS",
        "isBTF": True,
        "contentLayoutVersion": "v2",
        "pageType": "GlassHomePageDesktopV1",
        "postProcessingVersion": 2,
        "p13NCallType": "BTF",
        "p13n": {
            "selectedIntent": "NONE",
            "userClientInfo": {
                "deviceType": "desktop"
            }
        },
        "userClientInfo": {
            "deviceType": "desktop"
        },
        "userReqInfo": {
            "isMoreOptionsTileEnabled": True
        },
        "enableSeoHomePageMetaData": True,
        "enableEventTimerSeconds": True,
        "isPlusBannerRedesign": True,
        "isBTF": True,
        "p13nMetadata": "",  # we can leave this blank for now
        "lazyModules": [
            # we only REALLY care about Flash Deals etc.
            {
                "name": "Flash Deals Item Carousel Module - 12.12.24 ",
                "type": "ItemCarousel",
                "version": 2,
                "status": "published"
            }
        ],
    }
}

def _looks_like_waiting_room(resp_json: Any) -> bool:
    """
    Walmart's anti-bot 'waiting room' returns a totally different shape,
    usually { data: { type: 'standard', title: 'Hang on...' } }
    If we see that, we bail gracefully.
    """
    if not isinstance(resp_json, dict):
        return False
    # what you showed in logs actually looked like:
    # { "data": { "type": "standard", "title": "Hang on- you're so close..." } }
    inner = resp_json.get("data")
    if isinstance(inner, dict):
        if inner.get("type") == "standard" and "Hang on" in inner.get("title", ""):
            return True
    return False


def _extract_deals(resp_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Walk the modules -> find carousels -> pull out products in the same shape we use everywhere else.
    We'll return a list of dicts:
    {
       "title": str,
       "price": float | None,
       "price_str": str | None,
       "image": str | None,
       "url": str | None,
       "store": "Walmart"
    }
    """
    deals: List[Dict[str, Any]] = []

    layout = (
        resp_json
        .get("data", {})
        .get("contentLayout", {})
    )

    modules = layout.get("modules", [])
    for module in modules:
        configs = module.get("configs", {})
        products_cfg = (
            configs
            .get("productsConfig", {})
            .get("products", [])
        )

        for p in products_cfg:
            name = p.get("name")
            priceInfo = p.get("priceInfo", {})
            currentPrice = priceInfo.get("currentPrice", {})
            price_val = currentPrice.get("price")
            price_str = currentPrice.get("priceString")
            image = (
                p.get("imageInfo", {})
                .get("thumbnailUrl")
            )
            # canonicalUrl is relative like "/ip/..."; prepend walmart.com so frontend can click
            rel_url = p.get("canonicalUrl")
            if rel_url:
                full_url = "https://www.walmart.com" + rel_url
            else:
                full_url = None

            deals.append({
                "title": name,
                "price": price_val,
                "price_str": price_str,
                "image": image,
                "url": full_url,
                "store": "Walmart",
            })

    return deals


def fetch_deals(extra_cookies: Dict[str, str] = None) -> List[Dict[str, Any]]:
    session = requests.Session()

    # headers
    session.headers.update(WALMART_HEADERS)

    # cookies
    jar = requests.cookies.RequestsCookieJar()
    for k, v in WALMART_COOKIES.items():
        jar.set(k, v, domain=".walmart.com", path="/")
    if extra_cookies:
        for k, v in extra_cookies.items():
            jar.set(k, v, domain=".walmart.com", path="/")
    session.cookies = jar

    try:
        resp = session.post(
            WALMART_GRAPHQL_URL,
            data=json.dumps({
                "variables": WALMART_BODY["variables"]
            }),
        )

        if resp.status_code == 429:
            logging.error("Walmart 429 / waiting room")
            return []

        data_json = resp.json()

        if _looks_like_waiting_room(data_json):
            logging.error("Walmart anti-bot waiting room triggered")
            return []

        return _extract_deals(data_json)

    except Exception as e:
        logging.exception("Walmart request failed: %s", e)
        return []

if __name__ == "__main__":
    # quick local smoke test
    logging.basicConfig(level=logging.INFO)
    results = fetch_deals()
    print(json.dumps(results[:10], indent=2))
