import requests
import sys

def test_strict_filtering():
    print("Running Strict Category Filtering QA Tests...")
    
    # Test 1: Stationery (Pen) -> Should NOT have Nykaa/Trends
    print("\nTest 1: 'pen' (Stationery)")
    try:
        r = requests.get('http://127.0.0.1:5000/search?query=pen')
        content = r.text
        
        has_amazon = "Amazon" in content
        has_flipkart = "Flipkart" in content
        has_nykaa = "Nykaa" in content
        has_trends = "Trends" in content
        
        print(f"  Amazon: {has_amazon}")
        print(f"  Nykaa: {has_nykaa}")
        print(f"  Trends: {has_trends}")
        
        if has_amazon and not has_nykaa and not has_trends:
             print("✅ PASS: Stationery restricted to general platforms.")
        else:
             print("❌ FAIL: Stationery found on invalid platforms.")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 2: Makeup (Lipstick) -> Should have Nykaa, Should NOT have Trends
    print("\nTest 2: 'lipstick' (Beauty)")
    try:
        r = requests.get('http://127.0.0.1:5000/search?query=lipstick')
        content = r.text
        
        has_nykaa = "Nykaa" in content
        has_trends = "Trends" in content # Trends is fashion only
        
        print(f"  Nykaa: {has_nykaa}")
        print(f"  Trends: {has_trends}")
        
        if has_nykaa and not has_trends:
             print("✅ PASS: Beauty found on Nykaa, excluded from Trends.")
        else:
             print("❌ FAIL: Beauty platform logic incorrect.")
    except Exception as e:
        print(f"❌ Error: {e}")
        
    # Test 3: Fashion (Dress) -> Should have Trends/Ajio/Nykaa
    print("\nTest 3: 'dress' (Fashion)")
    try:
        r = requests.get('http://127.0.0.1:5000/search?query=dress')
        content = r.text
        
        has_trends = "Trends" in content
        has_ajio = "Ajio" in content
        
        print(f"  Trends: {has_trends}")
        print(f"  Ajio: {has_ajio}")
        
        if has_trends or has_ajio:
             print("✅ PASS: Fashion found on specialized platforms.")
        else:
             print("⚠️ WARN: Fashion items might be random, try running again.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_strict_filtering()
