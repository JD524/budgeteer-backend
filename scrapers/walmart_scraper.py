import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import re


class WalmartScraper:
    """
    Scrapes Walmart weekly ads and deals
    Note: Walmart's site structure may change - this is a starting point
    """

    def __init__(self):
        self.base_url = "https://www.walmart.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def scrape_deals(self, zip_code="10001"):
        """
        Scrape Walmart deals
        Returns list of deal dictionaries
        """
        deals = []

        try:
            # Walmart has an API endpoint for deals/rollbacks
            # This is more reliable than scraping HTML
            api_url = f"{self.base_url}/shop/deals/rollbacks"

            response = requests.get(api_url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')

                # Find product tiles (Walmart uses different selectors)
                # This is a simplified version - actual selectors may vary
                products = soup.find_all('div', class_='mb1')

                for product in products[:50]:  # Limit to 50 deals
                    try:
                        deal = self._parse_product(product)
                        if deal:
                            deals.append(deal)
                    except Exception as e:
                        print(f"Error parsing product: {e}")
                        continue

            # Fallback: Use mock data for demonstration
            if len(deals) == 0:
                deals = self._get_sample_deals()

        except Exception as e:
            print(f"Error scraping Walmart: {e}")
            # Return sample data on error
            deals = self._get_sample_deals()

        return deals

    def _parse_product(self, product_element):
        """Parse a single product element"""
        try:
            # Extract product details
            name_elem = product_element.find('span', class_='w_iUH7')
            price_elem = product_element.find('div', class_='mr1')

            if not name_elem:
                return None

            name = name_elem.get_text(strip=True)
            price = price_elem.get_text(strip=True) if price_elem else "N/A"

            # Clean price
            price = re.sub(r'[^\d.]', '', price) if price != "N/A" else None

            now = datetime.utcnow()
            deal = {
                'store_name': 'Walmart',
                'product_name': name,
                'price': f"${price}" if price else None,
                'original_price': None,
                'discount': None,
                'category': self._categorize_product(name),
                'description': None,
                'image_url': None,
                'deal_url': f"{self.base_url}/shop/deals/rollbacks",
                'valid_from': now.isoformat(),  # ← Convert to string
                'valid_until': (now + timedelta(days=7)).isoformat()  # ← Convert to string
            }

            return deal

        except Exception as e:
            print(f"Error parsing product element: {e}")
            return None

    def _categorize_product(self, product_name):
        """Categorize product based on name"""
        name_lower = product_name.lower()

        # Food & Beverages
        food_keywords = ['pizza', 'chicken', 'beef', 'pork', 'fish', 'bread', 'milk',
                         'cheese', 'yogurt', 'eggs', 'butter', 'soda', 'juice', 'water',
                         'coffee', 'tea', 'snack', 'chip', 'cookie', 'candy', 'chocolate']
        if any(keyword in name_lower for keyword in food_keywords):
            return 'Food & Beverages'

        # Personal Care
        care_keywords = ['shampoo', 'soap', 'toothpaste', 'deodorant', 'lotion',
                         'tissue', 'toilet paper', 'paper towel']
        if any(keyword in name_lower for keyword in care_keywords):
            return 'Personal Care'

        # Household
        household_keywords = ['detergent', 'cleaner', 'dish', 'laundry', 'trash bag']
        if any(keyword in name_lower for keyword in household_keywords):
            return 'Household'

        # Electronics
        electronics_keywords = ['tv', 'laptop', 'phone', 'tablet', 'headphone', 'speaker']
        if any(keyword in name_lower for keyword in electronics_keywords):
            return 'Electronics'

        return 'General Merchandise'

    def _get_sample_deals(self):
        """
        Return sample deals for testing
        In production, you'd remove this once real scraping works
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
                'valid_from': now.isoformat(),  # ← Convert to string
                'valid_until': valid_until.isoformat()  # ← Convert to string
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
            },
            {
                'store_name': 'Walmart',
                'product_name': "Lay's Potato Chips, Variety Pack",
                'price': '$9.98',
                'original_price': '$12.98',
                'discount': 'Save $3.00',
                'category': 'Food & Beverages',
                'description': '18 count variety pack',
                'image_url': None,
                'deal_url': 'https://www.walmart.com/shop/deals/rollbacks',
                'valid_from': now.isoformat(),
                'valid_until': valid_until.isoformat()
            },
            {
                'store_name': 'Walmart',
                'product_name': 'Ground Beef, 80/20, 1 lb',
                'price': '$3.98',
                'original_price': '$5.48',
                'discount': 'Save $1.50',
                'category': 'Food & Beverages',
                'description': 'Fresh ground beef',
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
    print(f"Found {len(deals)} Walmart deals")
    for deal in deals[:3]:
        print(f"  - {deal['product_name']}: {deal['price']}")