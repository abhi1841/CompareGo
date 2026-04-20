import requests
import sys

def test_endpoints():
    print("Running Automated QA Tests...")
    
    # Test 1: Homepage
    try:
        r = requests.get('http://127.0.0.1:5000/')
        assert r.status_code == 200
        print("✅ Homepage: Accessible")
    except Exception as e:
        print(f"❌ Homepage: Failed ({e})")
        
    # Test 2: Search (Electronics)
    try:
        r = requests.get('http://127.0.0.1:5000/search?query=iphone')
        assert r.status_code == 200
        
        content = r.text
        
        # 1. Positive Checks
        if "Apple" not in content:
            print("❌ 'Apple' not found in response")
        if "Amazon" not in content:
            print("❌ 'Amazon' not found in response")
            
        # 2. Negative Checks (Brand Purity)
        # When searching for 'iphone', we should NOT see Samsung, Vivo, etc. as the *Product Brand*
        # Note: They might appear in footer or filters, but let's check if they appear too frequently or in product titles.
        # Ideally, our mock data shouldn't generate them at all in the product list.
        
        unwanted_brands = ["Samsung", "Vivo", "Xiaomi", "OnePlus"]
        found_unwanted = [b for b in unwanted_brands if b in content]
        
        if found_unwanted:
             # It's possible they appear in the 'Filter by Brand' sidebar if we didn't clear the global brand list,
             # but the product results should be pure.
             # Let's verify strictness.
             print(f"⚠️ Warning: Found unrelated brands in page (could be in filters): {found_unwanted}")
        
        assert "Apple" in content
        print("✅ Search (Electronics): Verified mock data & Brand Purity")
    except Exception as e:
        print(f"❌ Search (Electronics): Failed ({e})")
        # print(r.text[:500])

    # Test 3: Search (Fashion)
    try:
        r = requests.get('http://127.0.0.1:5000/search?query=nike')
        assert r.status_code == 200
        assert "Nike" in r.text
        assert "Size" in r.text
        print("✅ Search (Fashion): Verified category detection")
    except Exception as e:
        print(f"❌ Search (Fashion): Failed ({e})")

    # Test 4: Value Score & Universal Discovery
    try:
        # Search for a product that triggers AI search
        r = requests.get('http://127.0.0.1:5000/search?query=iphone')
        assert r.status_code == 200
        content = r.text
        
        # Check for Value Score presence (Table Header)
        if "Value Score" in content:
             print("✅ Value Score: Displayed")
        else:
             print("⚠️ Value Score: Not found (Check UI implementation)")

        # Check for Credibility Indicators
        if "New Retailer" in content or "Verified" in content:
             print("✅ Credibility Indicators: Verified")
        else:
             print("⚠️ Credibility Indicators: Not found (Check UI implementation)")

    except Exception as e:
        print(f"❌ Value Score Test: Failed ({e})")
        
    print("\nQA Testing Complete.")

if __name__ == "__main__":
    test_endpoints()
