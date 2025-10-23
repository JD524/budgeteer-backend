"""
Quick test script to verify your API is working
Run this after starting the Flask server
"""

import requests
import json

# Change this if testing deployed backend
BASE_URL = "http://localhost:5000"


def test_health():
    """Test health endpoint"""
    print("\n🔍 Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        print("✅ Health check passed")
        print(f"   Response: {response.json()}")
    else:
        print(f"❌ Health check failed: {response.status_code}")


def test_stores():
    """Test stores endpoint"""
    print("\n🔍 Testing stores endpoint...")
    response = requests.get(f"{BASE_URL}/api/stores")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['count']} stores")
        for store in data['stores']:
            print(f"   - {store['display_name']}")
    else:
        print(f"❌ Stores request failed: {response.status_code}")


def test_deals():
    """Test deals endpoint"""
    print("\n🔍 Testing deals endpoint...")
    response = requests.get(f"{BASE_URL}/api/deals")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['count']} deals")
        if data['deals']:
            print("\n   Sample deals:")
            for deal in data['deals'][:3]:
                print(f"   - {deal['product_name']}: {deal['price']} at {deal['store_name']}")
    else:
        print(f"❌ Deals request failed: {response.status_code}")


def test_search():
    """Test search endpoint"""
    print("\n🔍 Testing search endpoint (query: 'pizza')...")
    response = requests.get(f"{BASE_URL}/api/deals/search?q=pizza")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['count']} pizza deals")
        for deal in data['deals']:
            print(f"   - {deal['product_name']}: {deal['price']} at {deal['store_name']}")
    else:
        print(f"❌ Search request failed: {response.status_code}")


def test_stats():
    """Test stats endpoint"""
    print("\n🔍 Testing stats endpoint...")
    response = requests.get(f"{BASE_URL}/api/stats")
    if response.status_code == 200:
        data = response.json()
        print("✅ Stats:")
        print(f"   Total deals: {data['total_deals']}")
        print(f"   Active deals: {data['active_deals']}")
        print(f"   Active stores: {data['active_stores']}")
    else:
        print(f"❌ Stats request failed: {response.status_code}")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("🧪 Running API Tests")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    try:
        test_health()
        test_stores()
        test_deals()
        test_search()
        test_stats()

        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API!")
        print("   Make sure the Flask server is running:")
        print("   python app.py")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")


if __name__ == '__main__':
    run_all_tests()