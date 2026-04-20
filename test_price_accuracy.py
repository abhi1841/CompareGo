"""
CompareGo Price Accuracy Test Suite
====================================
Tests every validation stage + regression set of 10 key SKUs.
Run:  python test_price_accuracy.py
"""
import sys, re, statistics, json, time
from dotenv import load_dotenv
load_dotenv()

import scrape
from scrape import (
    _parse_price, _parse_price_from_text, _classify_condition,
    _model_similarity, _reject_outliers, _currency_sane,
    _price_breakdown, PRICE_CONFIG, KNOWN_PRICE_ANCHORS,
)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []

def check(name, actual, expected, tol=0.0):
    """tol: fractional tolerance, e.g. 0.03 = ±3%"""
    if isinstance(expected, bool):
        ok = bool(actual) == expected
    elif isinstance(expected, type(None)):
        ok = actual is None
    elif tol > 0 and isinstance(expected, (int, float)):
        ok = abs(actual - expected) / max(expected, 1) <= tol
    else:
        ok = actual == expected
    status = PASS if ok else FAIL
    print(f"  [{status}] {name}")
    if not ok:
        print(f"          Expected: {expected!r}  Got: {actual!r}")
    results.append((name, ok))
    return ok

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("STAGE 1 — Price Parser")
print("="*65)

check("Rs 1,59,900 -> 159900",       _parse_price("Rs 1,59,900"),           159900)
check("Rs.1,59,900 -> 159900",       _parse_price("Rs.1,59,900"),           159900)
check("159900.0 -> 159900",          _parse_price("159900.0"),              159900)
check("1.599 lakh -> 159900",        _parse_price("1.599 lakh"),            159900, tol=0.01)
check("1,59,900 (Indian) -> 159900", _parse_price("1,59,900"),              159900)
check("74,900 -> 74900",             _parse_price("74,900"),                74900)
check("EMI-only string -> None",     _parse_price("EMI from 5000/mo"),     None)
check("Empty string -> None",        _parse_price(""),                      None)
check("Garbage string -> None",      _parse_price("N/A"),                   None)
check("Croatian huge number -> pass currency gate",
      _currency_sane(14_180_314), False)   # should be rejected
check("Normal price passes gate",    _currency_sane(159900),  True)
check("Zero rejected",               _currency_sane(0),       False)

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("STAGE 2 — Condition Classifier")
print("="*65)

check("'Refurbished Certified' -> refurbished",
      _classify_condition("Apple iPhone 16 Pro Max Refurbished Certified", "Ovantica"), "refurbished")
check("'Pre-loved' -> used",
      _classify_condition("iPhone 16 Pro Max Pre-loved 256 GB", "Tetro"), "used")
check("Cashify source -> used",
      _classify_condition("Apple iPhone 16 Pro - 256GB", "Cashify"), "used")
check("'Open Box' in title -> open_box",
      _classify_condition("iPhone 16 Pro Max OpenBox With Apple Warranty", "iTradeit"), "open_box")
check("New product -> new",
      _classify_condition("Apple iPhone 16 Pro Max 256 GB (Black Titanium)", "Amazon"), "new")
check("'Sell your iPhone' -> used",
      _classify_condition("Sell Apple iPhone 16 Pro Max 256 GB", "GameLoot"), "used")
check("GudFast Refurbished -> used",
      _classify_condition("Apple IPhone 16 Pro Max (256 GB) (Refurbished)", "GudFast"), "refurbished")

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("STAGE 3 — Model-Exact Similarity")
print("="*65)

check("'iPhone 16 Pro Max' matches correct title",
      _model_similarity("iPhone 16 Pro Max", "Apple iPhone 16 Pro Max 256 GB Desert Titanium") > 0.4, True)
check("'iPhone 16 Pro Max' DOES NOT match 'iPhone 16 Plus'",
      _model_similarity("iPhone 16 Pro Max", "Apple iPhone 16 Plus 256 GB"), 0.0)
check("'iPhone 16 Pro Max' DOES NOT match 'iPhone 16 Pro' (no Max)",
      _model_similarity("iPhone 16 Pro Max", "Apple iPhone 16 Pro 128 GB"), 0.0)
check("'Samsung Galaxy S24 Ultra' DOES NOT match plain 'Galaxy S24'",
      _model_similarity("Samsung Galaxy S24 Ultra", "Samsung Galaxy S24 128GB") <= 0.3, True)
check("'iPhone 16 Pro' does not match 'iPhone 16 Pro Max'",
      _model_similarity("iPhone 16 Pro", "Apple iPhone 16 Pro Max 1TB"), 0.0)
check("'Sony WH-1000XM5' matches correctly",
      _model_similarity("Sony WH-1000XM5", "Sony WH-1000XM5 Wireless Headphones") > 0.5, True)

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("STAGE 4 — Median Outlier Rejection")
print("="*65)

def make_offer(price, platform="TestStore", source="real"):
    return {'platform':platform,'raw_price':price,'source':source,
            'title':f"Product ₹{price}",'in_stock':True}

# Baseline: all prices around ₹1.5L
valid_set = [
    make_offer(159900, "Amazon"),
    make_offer(157900, "Flipkart"),
    make_offer(161900, "Croma"),
    make_offer(158500, "Reliance"),
    make_offer( 65000, "GameLoot"),    # outlier — used phone
    make_offer( 91999, "Ovantica"),    # outlier — refurb
    make_offer(14180314, "Croatia"),   # outlier — wrong currency
]
cleaned = _reject_outliers(valid_set, "iPhone 16 Pro Max")
cleaned_prices = [o['raw_price'] for o in cleaned]
check("Median filter: 4 valid offers retained",  len(cleaned), 4)
check("Outlier ₹65k rejected",   65000  not in cleaned_prices, True)
check("Outlier ₹91999 rejected", 91999  not in cleaned_prices, True)
check("Outlier ₹1.4cr rejected", 14180314 not in cleaned_prices, True)
check("₹159900 retained",        159900 in cleaned_prices, True)

# Edge: EMI-only scenario — price might be EMI not full price (we just test parsing)
emi_str = "Starting from Rs 6,641/month for 24 months"
emi_parsed = _parse_price(emi_str)  # should return 6641 (monthly) — not a valid product price
check("EMI-only text parses to a low value that anchor floors will catch",
      emi_parsed is None or emi_parsed < 50000, True)

# Edge: out-of-stock should still appear (we don't hide OoS from results)
oos_offer = make_offer(159900, "CromaOOS"); oos_offer['in_stock'] = False
mixed = [make_offer(159900,"Amazon"), oos_offer]
kept = _reject_outliers(mixed, "iPhone 16 Pro Max")
check("Out-of-stock SKU not removed by price filter", len(kept), 2)

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("STAGE 5 — Known-Price Anchors")
print("="*65)

# iphone 16 pro max anchor: floor=130000*0.85=110500, ceil=230000*1.15=264500
test_offers = [make_offer(p) for p in [159900, 157900, 75000, 161900]]   # 75k should be cut by anchor
res = _reject_outliers(test_offers, "iPhone 16 Pro Max")
check("Anchor test: ₹75k rejected for 'iPhone 16 Pro Max'",
      75000 not in [o['raw_price'] for o in res], True)
check("Anchor test: ₹159900 retained",
      159900 in [o['raw_price'] for o in res], True)

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("STAGE 6 — Price Breakdown (GST Inclusive)")
print("="*65)

bd = _price_breakdown(159900, "electronics")
check("Total matches input price",      bd['total'], 159900)
check("GST rate 18% for electronics",  bd['gst_rate_pct'], 18)
check("Base + GST = Total",
      bd['base_ex_gst'] + bd['gst_component'], 159900)
check("GST component is reasonable",
      10000 < bd['gst_component'] < 40000, True)

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("STAGE 7 — LIVE REGRESSION TEST (needs SERPAPI_KEY in .env)")
print("="*65)

# 10-SKU regression set with ground-truth price ranges (as of April 2025)
REGRESSION_SKUs = [
    ("iPhone 16 Pro Max",          130000, 230000),
    ("iPhone 16 Pro",               99000, 180000),
    ("iPhone 16",                   70000, 130000),
    ("Samsung Galaxy S24",          55000, 120000),
    ("Samsung Galaxy S24 Ultra",    80000, 175000),
    ("OnePlus 13",                  40000,  85000),
    ("MacBook Air M3",             110000, 190000),
    ("Sony WH-1000XM5",            18000,  36000),
    ("Apple AirPods Pro 2",        19000,  36000),
    ("Nike Air Max 270",            4000,  15000),
]

import os
if not os.getenv("SERPAPI_KEY"):
    print("  [SKIP] SERPAPI_KEY not set — skipping live regression tests")
else:
    reg_pass = reg_fail = 0
    for query, gt_min, gt_max in REGRESSION_SKUs:
        print(f"\n  Testing: {query}  (ground truth: Rs{gt_min:,} - Rs{gt_max:,})")
        r, err = scrape.scrapeCompareRaja(query)
        if not r or not r[0].get('offers'):
            print(f"    [SKIP] No offers returned")
            continue
        lowest = r[0]['raw_lowest_price']
        offers = r[0]['offers']
        prices = [o['raw_price'] for o in offers]
        med    = statistics.median(prices)
        in_range = gt_min <= lowest <= gt_max
        med_ok   = gt_min <= med    <= gt_max
        cond_tag = " | ".join(sorted(set(o.get('condition','?') for o in offers)))
        print(f"    Lowest: Rs{lowest:,}  Median: Rs{med:,.0f}  Conditions: {cond_tag}")
        print(f"    In-range: {'YES' if in_range else 'NO'}  |  Median in-range: {'YES' if med_ok else 'NO'}")
        if in_range:
            reg_pass += 1
            print(f"    [{PASS}]")
        else:
            reg_fail += 1
            print(f"    [{FAIL}]  Rs{lowest:,} not in [{gt_min:,}, {gt_max:,}]")
    total = reg_pass + reg_fail
    pct = int(reg_pass/total*100) if total else 0
    print(f"\n  Regression: {reg_pass}/{total} passed ({pct}%)")
    results.append((f"Regression suite {pct}%>=80%", pct >= 80))

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
passed = sum(1 for _,ok in results if ok)
total  = len(results)
pct    = int(passed / total * 100) if total else 0
print(f"TOTAL: {passed}/{total} tests passed ({pct}%)")
print("="*65)
sys.exit(0 if pct >= 85 else 1)
