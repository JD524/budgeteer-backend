import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import re


class WalmartScraper:
    """
    Scrapes Walmart weekly ads and deals
    """

    def __init__(self):
        self.base_url = "https://www.walmart.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    def scrape_deals(self, zip_code="10001"):
        """
        Scrape Walmart deals from multiple deal pages (rollbacks, flash picks, clearance).
        Returns a list of deal dicts.
        """
        all_deals = []

        # Pages to scrape
        deal_pages = [
            f"{self.base_url}/shop/deals/rollbacks",
            f"{self.base_url}/shop/deals/flash-picks",
            f"{self.base_url}/shop/deals/clearance",
        ]

        for url in deal_pages:
            try:
                print(f"\nFetching Walmart deals from {url}...")
                response = requests.get(url, headers=self.headers, timeout=15)
                print(f"Response status: {response.status_code}")

                if response.status_code != 200:
                    print(f"❌ Failed to fetch page: {response.status_code}")
                    continue

                soup = BeautifulSoup(response.content, 'html.parser')

                # Try multiple strategies to grab product cards
                # Strategy 1: find all product title elements directly
                product_title_nodes = soup.find_all(attrs={'data-automation-id': 'product-title'})
                # Strategy 2: fallback class you saw
                if not product_title_nodes:
                    product_title_nodes = soup.find_all('span', class_='w_V_DM')

                print(f"Found {len(product_title_nodes)} product elements")

                # We'll walk each title node, then climb upward to find a "card" container
                for idx, title_node in enumerate(product_title_nodes):
                    try:
                        # Heuristic: climb up a few levels to get the full product card container
                        container = title_node
                        for _ in range(5):
                            if container and container.parent:
                                container = container.parent

                        # ---------- NAME ----------
                        name = None
                        title_elem = container.find(attrs={'data-automation-id': 'product-title'})
                        if title_elem:
                            name = title_elem.get_text(strip=True)
                        else:
                            fallback_title = container.find('span', class_='w_V_DM')
                            if fallback_title:
                                name = fallback_title.get_text(strip=True)

                        if not name:
                            # if we can't even get a name, skip this card
                            continue

                        # normalize whitespace
                        name = " ".join(name.split())

                        # ---------- PRICE BLOCK ----------
                        # Walmart shuffles class names, so we do defensive extraction.

                        current_price = None
                        original_price = None
                        savings = None

                        # Look for something that looks like a price container
                        price_container = None

                        # first try with data-automation-id they sometimes use
                        price_container = container.find(attrs={'data-automation-id': 'product-price'})
                        if not price_container:
                            # fallback: look for any element with a $ in it
                            # but still within reasonable depth of container
                            # (keeps us from scanning entire soup)
                            possible_prices = container.find_all(string=re.compile(r"\$\s*\d"))
                            if possible_prices:
                                # grab the first parent tag of a "$12" style string
                                price_container = possible_prices[0].parent

                        # Now parse current / original / savings from price_container
                        if price_container:
                            # Walmart often splits dollars and cents into siblings.
                            # We'll try to reconstruct like $12.34

                            # Find something that looks like the main dollars value
                            # (you were checking class_='f2'/'f3'; keep that, but also add fallback)
                            dollars_node = (
                                    price_container.find('span', class_='f2')
                                    or price_container.find('span', class_='f3')
                            )
                            cents_node = None

                            if dollars_node:
                                # cents sometimes is literally the next sibling <span> with 2 digits
                                nxt = dollars_node.find_next_sibling('span')
                                if nxt and re.match(r"^\d{2}$", nxt.get_text(strip=True)):
                                    cents_node = nxt

                                dollars_text = dollars_node.get_text(strip=True)
                                if cents_node:
                                    cents_text = cents_node.get_text(strip=True)
                                    current_price = f"${dollars_text}.{cents_text}"
                                else:
                                    # if it already has decimals, keep it
                                    if re.search(r"\d+\.\d{2}", dollars_text):
                                        # already looks like 12.34
                                        if dollars_text.startswith("$"):
                                            current_price = dollars_text
                                        else:
                                            current_price = f"${dollars_text}"
                                    else:
                                        # assume whole dollars
                                        if dollars_text.startswith("$"):
                                            current_price = f"{dollars_text}.00"
                                        else:
                                            current_price = f"${dollars_text}.00"

                            # original / strikethrough (rollback price before discount)
                            strike_elem = price_container.find('span', class_='strike')
                            if strike_elem:
                                original_price = strike_elem.get_text(strip=True)

                            # savings text ("You save $5.00")
                            # we'll just scan container text
                            container_text = container.get_text(" ", strip=True)
                            m = re.search(r"You save\s*\$?([\d,]+\.?\d*)", container_text, re.IGNORECASE)
                            if m:
                                savings = f"Save ${m.group(1)}"

                        # If we STILL didn't get a price, skip this card
                        if not current_price:
                            continue

                        # ---------- CATEGORY ----------
                        category_guess = self._categorize_product(name)

                        # ---------- IMAGE ----------
                        # We try common patterns for imgs/thumbnails within the container
                        image_url = None
                        img_tag = container.find('img')
                        if img_tag and img_tag.get('src'):
                            image_url = img_tag['src']
                        elif img_tag and img_tag.get('data-src'):
                            image_url = img_tag['data-src']

                        # ---------- BUILD DEAL OBJECT ----------
                        deal = {
                            'store_name': 'Walmart',
                            'product_name': name[:200],
                            'price': current_price,
                            'original_price': original_price,
                            'discount': savings,
                            'category': category_guess,
                            'description': None,
                            'image_url': image_url,
                            'deal_url': url,
                            'valid_from': datetime.utcnow().isoformat(),
                            'valid_until': (datetime.utcnow() + timedelta(days=7)).isoformat()
                        }

                        all_deals.append(deal)
                        print(f"  ✓ [{idx + 1}] {name[:50]}... : {current_price}")

                    except Exception as e:
                        print(f"  ✗ Error parsing product {idx + 1} on {url}: {e}")
                        # keep going, just this item failed
                        continue

                print(f"✅ {len(all_deals)} total deals collected so far")

            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")
                # continue with the next URL
                continue

        # Fallback if we got absolutely nothing
        if len(all_deals) == 0:
            print("⚠️  No deals found across all pages, using sample data")
            all_deals = self._get_sample_deals()

        return all_deals

    def _categorize_product(self, product_name):
        """Categorize product based on name"""
        name_lower = product_name.lower()

        # Food & Beverages
        food_keywords = ['pizza', 'chicken', 'beef', 'pork', 'fish', 'bread', 'milk',
                         'cheese', 'yogurt', 'eggs', 'butter', 'soda', 'juice', 'water',
                         'coffee', 'tea', 'snack', 'chip', 'cookie', 'candy', 'chocolate',
                         'cereal', 'pasta', 'rice', 'meat', 'frozen', 'fruit', 'vegetable']
        if any(keyword in name_lower for keyword in food_keywords):
            return 'Food & Beverages'

        # Personal Care
        care_keywords = ['shampoo', 'soap', 'toothpaste', 'deodorant', 'lotion',
                         'tissue', 'toilet paper', 'paper towel', 'shave', 'razor']
        if any(keyword in name_lower for keyword in care_keywords):
            return 'Personal Care'

        # Household
        household_keywords = ['detergent', 'cleaner', 'dish', 'laundry', 'trash bag',
                              'vacuum', 'mop', 'broom', 'sponge']
        if any(keyword in name_lower for keyword in household_keywords):
            return 'Household'

        # Electronics
        electronics_keywords = ['tv', 'laptop', 'phone', 'tablet', 'headphone', 'speaker',
                                'camera', 'computer', 'monitor', 'keyboard', 'mouse']
        if any(keyword in name_lower for keyword in electronics_keywords):
            return 'Electronics'

        # Home & Furniture
        home_keywords = ['bed', 'mattress', 'pillow', 'blanket', 'sheet', 'towel',
                         'furniture', 'chair', 'table', 'lamp', 'decor']
        if any(keyword in name_lower for keyword in home_keywords):
            return 'Home & Furniture'

        return 'General Merchandise'

    def _get_sample_deals(self):
        """
        Return sample deals as fallback
        """
        now = datetime.utcnow()
        valid_until = now + timedelta(days=7)

        return [
            {
                'store_name': 'Walmart',
                'product_name': 'Great Value Pizza, Pepperoni, 12"',
                'price': '$2.98',
                'original_price': '$4.98',
                'discount': 'Save $2.00',
                'category': 'Food & Beverages',
                'description': 'Frozen pepperoni pizza',
                'image_url': None,
                'deal_url': 'https://www.walmart.com/shop/deals/rollbacks',
                'valid_from': now.isoformat(),
                'valid_until': valid_until.isoformat()
            },
            {
                'store_name': 'Walmart',
                'product_name': 'Tyson Chicken Nuggets, 2 lb',
                'price': '$5.98',
                'original_price': '$7.98',
                'discount': 'Save $2.00',
                'category': 'Food & Beverages',
                'description': 'Frozen chicken nuggets',
                'image_url': None,
                'deal_url': 'https://www.walmart.com/shop/deals/rollbacks',
                'valid_from': now.isoformat(),
                'valid_until': valid_until.isoformat()
            },
            {
                'store_name': 'Walmart',
                'product_name': 'Coca-Cola, 12 pack cans',
                'price': '$4.48',
                'original_price': '$6.48',
                'discount': 'Save $2.00',
                'category': 'Food & Beverages',
                'description': '12 oz cans',
                'image_url': None,
                'deal_url': 'https://www.walmart.com/shop/deals/rollbacks',
                'valid_from': now.isoformat(),
                'valid_until': valid_until.isoformat()
            }
        ]


# Test function
if __name__ == '__main__':
    scraper = WalmartScraper()
    deals = scraper.scrape_deals()
    print(f"\n{'=' * 60}")
    print(f"FINAL RESULTS: Found {len(deals)} Walmart deals")
    print(f"{'=' * 60}")
    for i, deal in enumerate(deals[:10], 1):
        print(f"{i}. {deal['product_name'][:60]}")
        print(f"   Price: {deal['price']} (was: {deal.get('original_price', 'N/A')})")
        print(f"   Category: {deal['category']}")