import requests
from bs4 import BeautifulSoup
import time
import random

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

def test_amazon(query):
    print(f"Testing Amazon for '{query}'...")
    try:
        url = f"https://www.amazon.in/s?k={query}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"Amazon Status: {r.status_code}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            titles = soup.select('h2 a span')
            if titles:
                print(f"Amazon Success! Found {len(titles)} items. First: {titles[0].text.strip()}")
                return True
            else:
                print("Amazon: 200 OK but no titles found (might be captcha page)")
        return False
    except Exception as e:
        print(f"Amazon Error: {e}")
        return False

def test_flipkart(query):
    print(f"Testing Flipkart for '{query}'...")
    try:
        url = f"https://www.flipkart.com/search?q={query}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"Flipkart Status: {r.status_code}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Flipkart classes change often, checking generic structure
            titles = soup.select('div._4rR01T') or soup.select('a.s1Q9rs') or soup.select('div.KzDlHZ')
            if titles:
                print(f"Flipkart Success! Found {len(titles)} items. First: {titles[0].text.strip()}")
                return True
            else:
                print("Flipkart: 200 OK but no common title classes found")
                # Debug: print partial html
                # print(r.text[:500])
        return False
    except Exception as e:
        print(f"Flipkart Error: {e}")
        return False

def test_ajio(query):
    print(f"Testing Ajio for '{query}'...")
    try:
        url = f"https://www.ajio.com/search/?text={query}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"Ajio Status: {r.status_code}")
        # Ajio is client-side rendered mostly, might fail with pure requests
        if r.status_code == 200:
            if "products" in r.text:
                print("Ajio: 200 OK, found 'products' keyword (likely JSON in script)")
                return True
            else:
                print("Ajio: 200 OK but content unclear")
        return False
    except Exception as e:
        print(f"Ajio Error: {e}")
        return False

if __name__ == "__main__":
    query = "iphone 13"
    test_amazon(query)
    time.sleep(1)
    test_flipkart(query)
    time.sleep(1)
    test_ajio(query)
