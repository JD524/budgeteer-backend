import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import requests


WALMART_ENDPOINT = "https://www.walmart.com/orchestra/home/graphql/HomePageWebRedesignBtf/97471cea0bb256c5caed77587c60c5c863e4c0c493eae4ce1051d86a6ad6a7de"

# Minimal headers that look like a normal browser call.
BASE_HEADERS = {
    "content-type": "application/json",
    "accept": "application/json",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0.0.0 Safari/537.36"
    ),
    "x-apollo-operation-name": "HomePageWebRedesignBtf",
    "tenant-id": "elh9ie",
    "x-o-bu": "WALMART-US",
    "x-o-platform": "rweb",
    # Version you captured. This can drift, but tends not to hard-break parsing.
    "x-o-platform-version": "usweb-1.230.1-72b46a24d08b3b2f119e9a9c3e542a129a96385f-0241544r",
    "wm_page_url": "https://www.walmart.com/",
}

# Body payload we saw in DevTools.
# NOTE: some values (like p13nMetadata) are huge, user/session flavored, and can change.
# The good news: Walmart usually does NOT require that exact giant blob,
# as long as we send the core structural fields (tenant, pageType, etc.).
#
# We'll keep a slimmed version that should still return modules + products.
BASE_PAYLOAD = {
    "variables": {
        "tenant": "WM_GLASS",
        "isBTF": True,
        "pageType": "GlassHomePageDesktopV1",
        "contentLayoutVersion": "v2",
        "selectedIntent": "NONE",
        "p13NCallType": "BTF",
        "userClientInfo": {"deviceType": "desktop"},
        "p13n": {
            "userClientInfo": {"deviceType": "desktop"},
            "selectedIntent": "NONE",
            "deviceType": "desktop",
            "userReqInfo": {"isMoreOptionsTileEnabled": True},
        },
        # Walmart lazily loads modules by name/type/version.
        # We'll request the same lazyModules list shape you saw.
        # We don't actually need every module definition here to get content,
        # but including them increases likelihood we get the same shelves.
        "lazyModules": [
            # We'll include just the hero carousel bottom, because that's the one
            # you pasted that clearly contains real product carousels.
            {
                "name": "05/05 PrismHeroCarouselBottom",
                "type": "PrismHeroCarousel",
                "subType": "PRISM",
                "version": 1,
            },
            # You can add more modules here if you want more shelves.
        ],
        # feature toggles
        "enableSeoHomePageMetaData": True,
        "enableEventTimerSeconds": True,
        "enableClickTrackingURL": False,
        "enableExclusiveWplusLabel": False,
        "enableMultiSaveOnCarousels": False,
        "enableSubscriptionString": False,
        "enableSwatch": False,
        "enableAvMode": False,
        "enableProductsField": False,
        "enableProductGridResponseV1": False,
        "enableProductCategory": False,
        "enableP13nAmendsData": False,
        "isPlusBannerRedesign": True,
        "postProcessingVersion": 2,
        "p13nMetadata": "",  # left blank intentionally
        "p13nMetadataV2": "",
    }
}


def _safe_get(d: Dict[str, Any], path: List[str], default=None):
    """Little helper to walk nested dicts safely."""
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _parse_product(p: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts the normalized deal info from one Walmart product dict."""
    name = p.get("name")
    brand = p.get("brand")
    canonical_url = p.get("canonicalUrl")
    full_url = f"https://www.walmart.com{canonical_url}" if canonical_url else None

    # current price
    current_price_val = _safe_get(p, ["priceInfo", "currentPrice", "price"])
    current_price_str = _safe_get(p, ["priceInfo", "currentPrice", "priceString"])

    # "was" price – Walmart sometimes sticks this in "wasPrice" or implies a deal via strikethrough
    was_price_val = _safe_get(p, ["priceInfo", "wasPrice", "price"])
    strikethrough = _safe_get(
        p, ["priceInfo", "priceDisplayCodes", "strikethrough"], False
    )

    availability = p.get("availabilityStatus")
    in_stock = availability == "IN_STOCK"

    event_flags = _safe_get(p, ["eventAttributes"], {}) or {}
    special_buy = event_flags.get("specialBuy", False)
    price_flip = event_flags.get("priceFlip", False)

    thumb = _safe_get(p, ["imageInfo", "thumbnailUrl"])

    return {
        "store": "Walmart",
        "title": name,
        "brand": brand,
        "image": thumb,
        "url": full_url,
        "price": current_price_val,
        "price_str": current_price_str,
        "was_price": was_price_val,
        "strikethrough": strikethrough,
        "in_stock": in_stock,
        "specialBuy": special_buy,
        "priceFlip": price_flip,
        "raw_usItemId": p.get("usItemId"),
    }


def _extract_products_from_modules(modules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Walk the modules array, find any module.configs.productsConfig.products,
    and parse each product.
    """
    results: List[Dict[str, Any]] = []

    for mod in modules:
        configs = mod.get("configs") or {}
        products_cfg = configs.get("productsConfig") or {}

        # productsConfig.products is the big list we saw in your paste
        products = products_cfg.get("products") or []

        # Some modules (like the PrismHeroCarousel) embed ONE "asset" with configs.items.products
        # pattern: configs.heroCarouselContainersV2[].asset.configs.productsConfig.products
        if not products:
            hero_containers = configs.get("heroCarouselContainersV2") or []
            for container in hero_containers:
                asset = container.get("asset") or {}
                asset_configs = asset.get("configs") or {}
                nested_products_cfg = asset_configs.get("productsConfig") or {}
                maybe_products = nested_products_cfg.get("products") or []
                if maybe_products:
                    products.extend(maybe_products)

        for p in products:
            try:
                parsed = _parse_product(p)
                # sanity: must have title + price
                if parsed["title"] and parsed["price"] is not None:
                    results.append(parsed)
            except Exception as ex:
                logging.exception("Failed to parse Walmart product", exc_info=ex)

    return results


def fetch_deals(
    session: Optional[requests.Session] = None,
    extra_cookies: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Scrape Walmart homepage carousels (BTF) for deal-like products.
    Mirrors the shape of Giant Eagle's fetch_deals(): returns a list of dicts.

    session: optional requests.Session you manage (for reuse / testing)
    extra_cookies: optional {cookie_name: value} to force location/store.
    """
    sess = session or requests.Session()

    # clone headers so caller can tweak if needed
    headers = dict(BASE_HEADERS)

    # We'll send JSON body.
    payload = json.dumps(BASE_PAYLOAD)

    # optional location cookies (e.g. assortmentStoreId) if caller wants to pin store
    cookies = extra_cookies or {}

    resp = sess.post(
        WALMART_ENDPOINT,
        headers=headers,
        data=payload,
        cookies=cookies,
        timeout=20,
    )

    if resp.status_code != 200:
        logging.error("Walmart request failed: %s %s", resp.status_code, resp.text[:500])
        return []

    try:
        data = resp.json()
    except Exception as ex:
        logging.exception("Walmart response was not JSON", exc_info=ex)
        return []

    # Walk data -> contentLayout -> modules
    modules = _safe_get(data, ["data", "contentLayout", "modules"], default=[])
    if not modules:
        # Fallback: sometimes Walmart nests response in ["data"]["0"]["contentLayout"]
        if isinstance(_safe_get(data, ["data"]), list):
            # If data["data"] is a list of results
            for block in data["data"]:
                if "contentLayout" in block and "modules" in block["contentLayout"]:
                    modules = block["contentLayout"]["modules"]
                    break

    if not modules:
        logging.warning("No modules found in Walmart response.")
        return []

    deals = _extract_products_from_modules(modules)

    # Optional: sort / dedupe
    # let's dedupe by url+price
    seen: set[Tuple[str, float]] = set()
    unique_deals: List[Dict[str, Any]] = []
    for d in deals:
        key = (d.get("url"), d.get("price"))
        if key not in seen:
            seen.add(key)
            unique_deals.append(d)

    return unique_deals


if __name__ == "__main__":
    # quick local smoke test
    logging.basicConfig(level=logging.INFO)
    results = fetch_deals()
    print(json.dumps(results[:10], indent=2))
