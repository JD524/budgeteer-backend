import json
import logging
import requests
from typing import List, Dict, Any

WALMART_GRAPHQL_URL = "https://www.walmart.com/orchestra/home/graphql/HomePageWebRedesignBtf/97471cea0bb256c5caed77587c60c5c863e4c0c493eae4ce1051d86a6ad6a7de"

WALMART_HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US",
    "content-type": "application/json",
    "origin": "https://www.walmart.com",
    "referer": "https://www.walmart.com/",
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
    "x-o-bu": "WALMART-US",
    "x-o-platform": "rweb",
    "x-o-platform-version": "usweb-1.230.1-72b46a24d08b3b2f119e9a9c3e542a129a96385f-0241544r",
    "x-o-mart": "B2C",
    "x-o-ccm": "server",
    "x-o-platform": "rweb",
    "x-o-mart": "B2C",
    # these aren't strictly required, but make us look closer to your captured request
    "wm_page_url": "https://www.walmart.com/",
    "x-o-bu": "WALMART-US",
}

WALMART_COOKIES = {
    "vtc": "Rf6n5_hr5KjhaAyHSldq9s",
    "ACID": "8b86e975-5517-4398-b91f-4bd43f7dd6f2",
    "hasACID": "true",
    "_m": "9",
    "assortmentStoreId": "4285",
    # paste your full blobs here (no truncation!)
    "locDataV3": "FULL_LOC_DATA_V3_VALUE",
    "locGuestData": "FULL_LOC_GUEST_DATA_VALUE",
}

WALMART_BODY = {
    "variables": {
        "tenant": "WM_GLASS",
        "isBTF": True,
        "contentLayoutVersion": "v2",
        "pageType": "GlassHomePageDesktopV1",
        "postProcessingVersion": 2,
        "p13NCallType": "BTF",

        # personalization block
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

        # feature flags we saw you send
        "enableSeoHomePageMetaData": True,
        "enableEventTimerSeconds": True,
        "isPlusBannerRedesign": True,
        "isBTF": True,

        # we’ll leave p13nMetadata empty for now
        "p13nMetadata": "",

        # IMPORTANT:
        # we ask Walmart to hydrate this module specifically.
        # If Walmart refuses because the module name doesn’t match what
        # they expect for you, we'll see that in the error body we log.
        "lazyModules": [
            {
                "name": "Flash Deals Item Carousel Module - 12.12.24 ",
                "type": "ItemCarousel",
                "version": 2,
                "status": "published",
            }
        ],
    }
}


def _looks_like_waiting_room(resp_text: str, status: int) -> bool:
    """
    If we land in anti-bot, sometimes we still get 200 but with
    a tiny JSON blob like:
    {
      "data": {
        "type": "standard",
        "title": "Hang on- you're so close..."
      }
    }
    Other times we get HTML (captcha, queue, etc).

    We'll just pattern match here.
    """
    if "Hang on- you're so close" in resp_text:
        return True
    if "WaitingRoom.png" in resp_text:
        return True
    if "distil_r_captcha" in resp_text.lower():
        return True
    if status == 429:
        return True
    return False


def _extract_deals(resp_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    deals = []

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

            thumb = (
                p.get("imageInfo", {})
                .get("thumbnailUrl")
            )

            rel_url = p.get("canonicalUrl")
            full_url = (
                "https://www.walmart.com" + rel_url
                if rel_url else None
            )

            deals.append({
                "title": name,
                "price": price_val,
                "price_str": price_str,
                "image": thumb,
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
        # IMPORTANT CHANGE: use json= instead of data=json.dumps(...)
        resp = session.post(
            WALMART_GRAPHQL_URL,
            json={"variables": WALMART_BODY["variables"]},
        )

        status = resp.status_code
        text = resp.text or ""

        # log status always, so we can see if it's 200/403/etc
        logging.error("Walmart status: %s", status)

        # detect waiting room / captcha before attempting JSON parse
        if _looks_like_waiting_room(text, status):
            logging.error("Blocked by Walmart / waiting room / captcha")
            logging.error("First 500 chars of body: %r", text[:500])
            return []

        # try JSON
        try:
            data_json = resp.json()
        except Exception:
            # dump body so we can inspect what Walmart actually sent
            logging.error("Non-JSON Walmart body (first 500 chars): %r", text[:500])
            raise  # re-raise so outer except logs stacktrace

        # happy path
        return _extract_deals(data_json)

    except Exception as e:
        logging.exception("Walmart request failed: %s", e)
        return []


if __name__ == "__main__":
    # quick local smoke test
    logging.basicConfig(level=logging.INFO)
    results = fetch_deals()
    print(json.dumps(results[:10], indent=2))
