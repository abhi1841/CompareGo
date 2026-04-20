"""
Diagnostic: why does "iPhone 16 Pro Max" return ₹70-80k?
Run: python debug_price_audit.py
"""
from dotenv import load_dotenv
load_dotenv()

import os, json, statistics
from serpapi import GoogleSearch

KEY = os.getenv("SERPAPI_KEY","")

params = {
    "engine": "google_shopping",
    "q": "iPhone 16 Pro Max",
    "gl": "in", "hl": "en", "currency": "INR",
    "num": 40,
    "api_key": KEY,
}

print("Fetching raw SerpAPI results for 'iPhone 16 Pro Max'...")
search = GoogleSearch(params)
raw = search.get_dict()
results = raw.get("shopping_results", [])
print(f"Total raw results: {len(results)}\n")

prices = []
print(f"{'#':<3} {'Price(raw)':<14} {'Source':<30} {'Title'[:55]}")
print("-"*110)
for i, r in enumerate(results):
    title  = r.get("title","")[:55]
    source = r.get("source","")[:28]
    price_str = str(r.get("price","") or r.get("extracted_price","") or "")
    condition = r.get("condition","new")
    snippet   = (r.get("snippet","") or "")[:40]

    # parse
    import re
    cleaned = re.sub(r'[\u20b9$\u20ac\xa3Rs.\s]','', price_str).replace(',','').strip()
    m = re.search(r'(\d+(?:\.\d+)?)', cleaned)
    val = int(float(m.group(1))) if m else None
    prices.append(val)

    flag = ""
    if val and val < 80000: flag = " <-- LOW?"
    if any(kw in title.lower() for kw in ['use','refurb','second','open box','old','pre-owned']):
        flag += " [USED/REFURB]"

    print(f"{i+1:<3} {str(val):<14} {source:<30} {title} {flag}")
    if snippet: print(f"    snippet: {snippet}")

valid = [p for p in prices if p]
if valid:
    med = statistics.median(valid)
    mn  = min(valid)
    mx  = max(valid)
    print(f"\nMedian: ₹{med:,.0f} | Min: ₹{mn:,} | Max: ₹{mx:,}")
    print(f"Outliers below 50% of median:")
    for i,p in enumerate(prices):
        if p and p < med*0.5:
            r = results[i]
            print(f"  [{i+1}] ₹{p:,} — {r.get('source','')} — {r.get('title','')[:60]}")
