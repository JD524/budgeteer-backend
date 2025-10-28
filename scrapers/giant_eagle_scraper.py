import requests
from datetime import datetime, timedelta


class GiantEagleScraper:
    """
    Scrapes Giant Eagle weekly ad deals using their GraphQL endpoint.

    Right now we target one store (storeCode="4096", which corresponds to Stow).
    Later we can make storeCode dynamic (e.g. based on user location).
    """

    def __init__(self, store_code="4096", store_label="stow"):
        self.endpoint = "https://core.shop.gianteagle.com/api/v2"
        self.store_code = store_code         # "4096"
        self.store_label = store_label       # for display like "Giant Eagle (stow)"

        # Base headers: we mimic the browser enough for the API to answer.
        # We include Content-Type because it's a GraphQL-style POST.
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

        # This is the GraphQL query you captured. We'll keep it verbatim.
        # (It can be long, that's fine. It's static.)
        self.query_text = (
            "fragment GetProductTileData on Product {\n"
            "  allergens\n"
            "  brand\n"
            "  categoryNames\n"
            "  categorySeoUrls\n"
            "  comparedPrice\n"
            "  coupons {\n"
            "    conditions {\n"
            "      minBasketValue\n"
            "      minQty\n"
            "      offerType\n"
            "      __typename\n"
            "    }\n"
            "    couponScope\n"
            "    description\n"
            "    disclaimer\n"
            "    expiryDateFormatted\n"
            "    id\n"
            "    imageUrl\n"
            "    products {\n"
            "      sku\n"
            "      __typename\n"
            "    }\n"
            "    rewards {\n"
            "      offerValue\n"
            "      rewardQuantity\n"
            "      __typename\n"
            "    }\n"
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
            "  images {\n"
            "    fileSize\n"
            "    format\n"
            "    height\n"
            "    kind\n"
            "    url\n"
            "    width\n"
            "    __typename\n"
            "  }\n"
            "  indications\n"
            "  ingredients\n"
            "  name\n"
            "  offers {\n"
            "    brand\n"
            "    id\n"
            "    image\n"
            "    offerDetailsType\n"
            "    offerType\n"
            "    rewardInfo\n"
            "    tags\n"
            "    title\n"
            "    __typename\n"
            "  }\n"
            "  price\n"
            "  pricingModel\n"
            "  productLocation {\n"
            "    aisleLocation\n"
            "    __typename\n"
            "  }\n"
            "  restrictions {\n"
            "    restrictionKind\n"
            "    __typename\n"
            "  }\n"
            "  inventoryStatus\n"
            "  isNewLowPrice\n"
            "  isEverydaySavings\n"
            "  isFoodStampItem\n"
            "  isFsaEligible\n"
            "  scopedPromo {\n"
            "    priceLock\n"
            "    qty\n"
            "    __typename\n"
            "  }\n"
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
            "\n"
            "query GetProducts($cursor: String, $count: Int, $filters: ProductFilters, $store: StoreInput!, $sort: ProductSortKey) {\n"
            "  products(\n"
            "    first: $count\n"
            "    after: $cursor\n"
            "    filters: $filters\n"
            "    store: $store\n"
            "    sort: $sort\n"
            "  ) {\n"
            "    edges {\n"
            "      cursor\n"
            "      node {\n"
            "        ...GetProductTileData\n"
            "        __typename\n"
            "      }\n"
            "      __typename\n"
            "    }\n"
            "    pageInfo {\n"
            "      endCursor\n"
            "      hasNextPage\n"
            "      __typename\n"
            "    }\n"
            "    totalCount\n"
            "    queryId\n"
            "    responseId\n"
            "    __typename\n"
            "  }\n"
            "}\n"
        )

    def _fetch_products_page(self, cursor=None, count=34):
        """
        Calls the Giant Eagle GraphQL endpoint for this store.
        We send basically the same POST payload we saw in DevTools.
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
                    "circular": True,           # only sale/weekly-ad items
                    "excludeRestricted": False
                },
                "store": {
                    "storeCode": self.store_code  # <-- "4096"
                },
                "sort": "bestMatch"
            }
        }

        resp = requests.post(
            self.endpoint,
            json=payload,
            headers=self.headers,
            timeout=15
        )

        if resp.status_code != 200:
            print(f"❌ Giant Eagle fetch failed: {resp.status_code}")
            print(resp.text[:300])
            return None

        try:
            return resp.json()
        except Exception as e:
            print(f"❌ Failed to parse JSON: {e}")
            print(resp.text[:300])
            return None

    def _pick_image(self, images):
        """
        Pick a nice image URL from node.images, preferring a 256x256 variant.
        """
        if not images:
            return None

        # Prefer kind containing "256" first
        for img in images:
            kind = (img.get("kind") or "").lower()
            if "256" in kind and img.get("url"):
                return img["url"]

        # Otherwise first valid url
        for img in images:
            if img.get("url"):
                return img["url"]

        return None

    def scrape_deals(self):
        """
        Fetch first page of weekly-ad products and normalize them to our deal shape.
        """
        data = self._fetch_products_page(cursor=None, count=34)
        if not data:
            print("⚠️ No data returned from Giant Eagle API")
            return []

        products_root = (
            data
            .get("data", {})
            .get("products", {})
        )

        edges = products_root.get("edges", [])
        # (We COULD loop more pages if hasNextPage is true using pageInfo.endCursor.)

        deals = []
        now = datetime.utcnow()
        valid_from = now.isoformat()
        valid_until = (now + timedelta(days=7)).isoformat()

        for idx, edge in enumerate(edges):
            node = edge.get("node", {})
            if not node:
                continue

            name = node.get("name")
            if not name:
                continue

            # current price: "5.99" -> "$5.99"
            price_val = node.get("scopedPromoPrice") or node.get("price")
            current_price = f"${price_val}" if price_val else None

            # original price: "7.29" -> "$7.29"
            compared_price_val = node.get("comparedPrice")
            original_price = f"${compared_price_val}" if compared_price_val else None

            if not current_price:
                # If there's truly no numeric price (e.g. "BOGO" only), skip for now
                continue

            # per-unit/size info
            size_info = node.get("displayItemSize")          # "1 lb (avg.)"
            per_unit = node.get("displayPricePerUnit")       # "$5.99/lb"
            extras = []
            if size_info:
                extras.append(size_info)
            if per_unit and per_unit != current_price:
                extras.append(per_unit)
            display_price = current_price
            if extras:
                display_price = f"{current_price} ({', '.join(extras)})"

            # discount math: Save $X
            discount_str = None
            try:
                if price_val and compared_price_val:
                    cur_f = float(price_val)
                    orig_f = float(compared_price_val)
                    diff = orig_f - cur_f
                    if diff > 0:
                        discount_str = f"Save ${diff:.2f}"
            except Exception:
                pass

            # category: last categoryNames entry is usually most specific
            category_names = node.get("categoryNames") or []
            if category_names:
                category_guess = category_names[-1]
            else:
                category_guess = "Grocery"

            # image
            image_url = self._pick_image(node.get("images"))

            # build optional product link from sku (to show user where to buy)
            sku = node.get("sku")
            if sku:
                deal_url = f"https://www.gianteagle.com/{self.store_label}/search/product/{sku}"
            else:
                deal_url = None

            deal = {
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
                "valid_until": valid_until
            }

            deals.append(deal)
            print(f"  ✓ [{idx+1}] {deal['product_name'][:60]}  |  {deal['price']}  |  {deal.get('discount')}")

        print(f"🦅 Giant Eagle ({self.store_label}) total scraped deals: {len(deals)}")
        return deals


if __name__ == "__main__":
    scraper = GiantEagleScraper(store_code="4096", store_label="stow")
    deals = scraper.scrape_deals()
    print(f"\nFound {len(deals)} deals.\n")
    for d in deals[:10]:
        print(f"{d['product_name']}  -> {d['price']}  ({d.get('discount')})")
