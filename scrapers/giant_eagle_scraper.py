import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timedelta


class GiantEagleScraper:
    """
    Scrapes Giant Eagle weekly-ad / promo items via their GraphQL endpoint.
    Default storeCode=4096 (Stow). Keep store_label for nice display / deep links.
    """

    def __init__(self, store_code="4096", store_label="stow"):
        self.endpoint = "https://core.shop.gianteagle.com/api/v2"
        self.store_code = store_code
        self.store_label = store_label

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://www.gianteagle.com",
            "Referer": "https://www.gianteagle.com/",
        }

        # === Your captured query (kept verbatim) ===
        self.query_text = (
            "fragment GetProductTileData on Product {\n"
            "  allergens\n"
            "  brand\n"
            "  categoryNames\n"
            "  categorySeoUrls\n"
            "  comparedPrice\n"
            "  coupons {\n"
            "    conditions { minBasketValue minQty offerType __typename }\n"
            "    couponScope\n"
            "    description\n"
            "    disclaimer\n"
            "    expiryDateFormatted\n"
            "    id\n"
            "    imageUrl\n"
            "    products { sku __typename }\n"
            "    rewards { offerValue rewardQuantity __typename }\n"
            "    summary\n"
            "    __typename\n"
            "  }\n"
            "  description\n"
            "  directions\n"
            "  displayItemSize\n"
            "  displayPricePerUnit\n"
            "  eventId\n"
            "  fulfillmentMethods\n"
            "  healthClaims\n"
            "  id\n"
            "  images { fileSize format height kind url width __typename }\n"
            "  indications\n"
            "  ingredients\n"
            "  name\n"
            "  offers { brand id image offerDetailsType offerType rewardInfo tags title __typename }\n"
            "  price\n"
            "  pricingModel\n"
            "  productLocation { aisleLocation __typename }\n"
            "  restrictions { restrictionKind __typename }\n"
            "  inventoryStatus\n"
            "  isNewLowPrice\n"
            "  isEverydaySavings\n"
            "  isFoodStampItem\n"
            "  isFsaEligible\n"
            "  scopedPromo { priceLock qty __typename }\n"
            "  scopedPromoDisplayPricePerUnit\n"
            "  scopedPromoPrice\n"
            "  scopedPromoUnitPrice\n"
            "  sizeOfFirstAdd\n"
            "  sizes\n"
            "  sku\n"
            "  unitPrice\n"
            "  unitQty\n"
            "  units\n"
            "  vendor\n"
            "  warnings\n"
            "  previouslyPurchased\n"
            "  lastPurchaseDate\n"
            "  __typename\n"
            "}\n"
            "query GetProducts($cursor: String, $count: Int, $filters: ProductFilters, $store: StoreInput!, $sort: ProductSortKey) {\n"
            "  products(first: $count, after: $cursor, filters: $filters, store: $store, sort: $sort) {\n"
            "    edges {\n"
            "      cursor\n"
            "      node { ...GetProductTileData __typename }\n"
            "      __typename\n"
            "    }\n"
            "    pageInfo { endCursor hasNextPage __typename }\n"
            "    totalCount\n"
            "    queryId\n"
            "    responseId\n"
            "    __typename\n"
            "  }\n"
            "}\n"
        )

        # Retryy/timeout session
        self.session = requests.Session()
        retry = Retry(
            total=4, connect=3, read=3, status=3,
            status_forcelist=(502, 503, 504),
            allowed_methods=("POST",),
            backoff_factor=0.8,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _post(self, payload, timeout=(10, 45)):
        resp = self.session.post(self.endpoint, json=payload, headers=self.headers, timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"GE non-200 {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
        except ValueError:
            raise RuntimeError(f"GE invalid JSON: {resp.text[:300]}")
        if "errors" in data and data["errors"]:
            # surface GraphQL errors for fast diagnosis
            raise RuntimeError(f"GE GraphQL errors: {data['errors']}")
        return data

    def _fetch_products_page(self, cursor=None, count=32):
        """
        Same shape you captured originally: GetProducts + filters (circular: true) and store.storeCode.
        """
        payload = {
            "operationName": "GetProducts",
            "query": self.query_text,
            "variables": {
                "cursor": cursor,
                "count": count,
                "filters": {
                    "query": "",
                    "brandIds": [],
                    "healthClaimIds": [],
                    "benefitPrograms": [],
                    "savings": [],
                    "circular": True,          # weekly ad / promos
                    "excludeRestricted": False
                },
                "store": { "storeCode": self.store_code },  # NOTE: storeCode (NOT "code")
                "sort": "bestMatch"
            }
        }
        return self._post(payload)

    @staticmethod
    def _pick_image(images):
        if not images:
            return None
        for img in images:
            kind = (img.get("kind") or "").lower()
            if "256" in kind and img.get("url"):
                return img["url"]
        for img in images:
            if img.get("url"):
                return img["url"]
        return None

    def scrape_deals(self):
        """
        Pull first page; you can loop pagination if needed via pageInfo.hasNextPage/endCursor.
        """
        try:
            data = self._fetch_products_page(cursor=None, count=36)
        except Exception as e:
            print(f"⚠️ Giant Eagle request failed: {e}")
            return []

        products_root = (data.get("data", {}) or {}).get("products", {})  # :contentReference[oaicite:5]{index=5}
        edges = products_root.get("edges", []) or []
        if not edges:
            print("⚠️ No products returned from Giant Eagle API")
            return []

        now = datetime.utcnow()
        valid_from = now.isoformat()
        valid_until = (now + timedelta(days=7)).isoformat()

        deals = []
        for idx, edge in enumerate(edges):
            node = edge.get("node") or {}
            name = node.get("name")
            if not name:
                continue

            price_val = node.get("scopedPromoPrice") or node.get("price")
            current_price = f"${price_val}" if price_val else None

            compared_price_val = node.get("comparedPrice")
            original_price = f"${compared_price_val}" if compared_price_val else None
            if not current_price:
                continue

            size_info = node.get("displayItemSize")
            per_unit = node.get("displayPricePerUnit")
            extras = [x for x in (size_info, per_unit) if x]
            display_price = current_price if not extras else f"{current_price} ({', '.join(extras)})"

            discount_str = None
            try:
                if price_val and compared_price_val:
                    diff = float(compared_price_val) - float(price_val)
                    if diff > 0:
                        discount_str = f"Save ${diff:.2f}"
            except Exception:
                pass

            cats = node.get("categoryNames") or []
            category_guess = cats[-1] if cats else "Grocery"

            image_url = self._pick_image(node.get("images"))
            sku = node.get("sku")
            deal_url = f"https://www.gianteagle.com/{self.store_label}/search/product/{sku}" if sku else None

            deals.append({
                "store_name": f"Giant Eagle ({self.store_label})",
                "product_name": name[:200],
                "price": display_price,
                "original_price": original_price,
                "discount": discount_str,
                "category": category_guess,
                "description": node.get("description"),
                "image_url": image_url,
                "deal_url": deal_url,
                "valid_from": valid_from,
                "valid_until": valid_until,
            })

            line_left = name[:60]
            print(f"  ✓ [{idx+1}] {line_left}  |  {display_price}  |  {discount_str or ''}".rstrip())

        print(f"🦅 Giant Eagle ({self.store_label}) total scraped deals: {len(deals)}")
        return deals


if __name__ == "__main__":
    scraper = GiantEagleScraper(store_code="4096", store_label="stow")
    out = scraper.scrape_deals()
    print(f"\nFound {len(out)} deals.\n")
    for d in out[:10]:
        print(f"{d['product_name']} -> {d['price']} ({d.get('discount')})")
