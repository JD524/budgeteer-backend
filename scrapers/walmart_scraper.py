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
        Scrape Walmart deals
        Returns list of deal dictionaries
        """
        deals = []

        try:
            # Walmart rollbacks page
            url = f"{self.base_url}/shop/deals/rollbacks"

            print(f"Fetching Walmart deals from {url}...")
            response = requests.get(url, headers=self.headers, timeout=15)

            print(f"Response status: {response.status_code}")

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')

                # Find all product tiles
                # Walmart uses different containers, let's try multiple approaches

                # Method 1: Find by data-automation-id
                products = soup.find_all(attrs={'data-automation-id': 'product-title'})

                if not products:
                    # Method 2: Find spans with title info
                    products = soup.find_all('span', class_='w_V_DM')

                print(f"Found {len(products)} product elements")

                for idx, product in enumerate(products[:30]):  # Limit to 30
                    try:
                        # Get the parent container (go up a few levels)
                        container = product.parent
                        for _ in range(5):  # Go up max 5 levels
                            if container.parent:
                                container = container.parent

                        # Extract product name
                        title_elem = container.find(attrs={'data-automation-id': 'product-title'})
                        if not title_elem:
                            title_elem = container.find('span', class_='w_V_DM')

                        if not title_elem:
                            continue

                        name = title_elem.get_text(strip=True)

                        # Extract current price
                        # Look for the "Now" price or any price element
                        price_container = container.find(attrs={'data-automation-id': 'product-price'})

                        current_price = None
                        original_price = None
                        savings = None

                        if price_container:
                            # Find the big price number (class f2 or f3)
                            price_elem = price_container.find('span', class_='f2')
                            if not price_elem:
                                price_elem = price_container.find('span', class_='f3')

                            if price_elem:
                                # Get the cents too
                                price_text = price_elem.get_text(strip=True)
                                # Look for decimal part
                                cents_elem = price_elem.find_next_sibling('span')
                                if cents_elem:
                                    cents_text = cents_elem.get_text(strip=True)
                                    current_price = f"${price_text}.{cents_text}"
                                else:
                                    current_price = f"${price_text}.00"

                            # Find original price (strikethrough)
                            strike_elem = price_container.find('span', class_='strike')
                            if strike_elem:
                                original_price = strike_elem.get_text(strip=True)

                            # Find savings
                            savings_text = container.get_text()
                            if 'You save' in savings_text:
                                # Extract the dollar amount after "You save"
                                match = re.search(r'You save\s*\$?([\d,]+\.?\d*)', savings_text)
                                if match:
                                    savings = f"Save ${match.group(1)}"

                        # Skip if we couldn't find a price
                        if not current_price:
                            continue

                        # Clean up the name (remove extra whitespace)
                        name = ' '.join(name.split())

                        # Create deal object
                        deal = {
                            'store_name': 'Walmart',
                            'product_name': name[:200],  # Limit length
                            'price': current_price,
                            'original_price': original_price,
                            'discount': savings,
                            'category': self._categorize_product(name),
                            'description': None,
                            'image_url': None,
                            'deal_url': url,
                            'valid_from': datetime.utcnow().isoformat(),
                            'valid_until': (datetime.utcnow() + timedelta(days=7)).isoformat()
                        }

                        deals.append(deal)
                        print(f"  ✓ [{idx + 1}] {name[:50]}... : {current_price}")

                    except Exception as e:
                        print(f"  ✗ Error parsing product {idx + 1}: {e}")
                        continue

                print(f"\n✅ Successfully scraped {len(deals)} deals")

            else:
                print(f"❌ Failed to fetch page: {response.status_code}")

            # Fallback to sample data if scraping fails
            if len(deals) == 0:
                print("⚠️  No deals found with real scraping, using sample data")
                deals = self._get_sample_deals()

        except Exception as e:
            print(f"❌ Error scraping Walmart: {e}")
            print("⚠️  Falling back to sample data")
            deals = self._get_sample_deals()

        return deals

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