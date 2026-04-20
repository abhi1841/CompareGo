from scrape import calculate_similarity, get_retailer_reliability, _extract_model

def test_similarity():
    print("Testing Similarity Logic...")
    
    # Exact match
    s1 = "iPhone 15 Pro"
    s2 = "iPhone 15 Pro"
    score = calculate_similarity(s1, s2)
    print(f"'{s1}' vs '{s2}': {score} (Expected 1.0)")
    assert score == 1.0

    # Case insensitive
    s1 = "iPhone 15 Pro"
    s2 = "iphone 15 pro"
    score = calculate_similarity(s1, s2)
    print(f"'{s1}' vs '{s2}': {score} (Expected 1.0)")
    assert score == 1.0
    
    # Minor difference
    s1 = "iPhone 15 Pro"
    s2 = "iPhone 15 Pro 128GB"
    score = calculate_similarity(s1, s2)
    print(f"'{s1}' vs '{s2}': {score:.2f} (Expected high, e.g. > 0.6)")
    assert score > 0.6
    
    # Completely different
    s1 = "iPhone 15 Pro"
    s2 = "Samsung Galaxy S24"
    score = calculate_similarity(s1, s2)
    print(f"'{s1}' vs '{s2}': {score:.2f} (Expected low, e.g. < 0.3)")
    assert score < 0.3
    
    # User case: "Pen" vs "Eyeliner Pen" (Should be distinct if strictly checked, but similarity might be tricky)
    s1 = "Pen"
    s2 = "Eyeliner Pen"
    score = calculate_similarity(s1, s2)
    print(f"'{s1}' vs '{s2}': {score:.2f}")
    
    print("Similarity Tests Passed!\n")

def test_reliability():
    print("Testing Reliability Logic...")
    
    assert get_retailer_reliability("Amazon") == 98
    assert get_retailer_reliability("amazon.in") == 98
    assert get_retailer_reliability("Unknown Shop") == 70
    assert get_retailer_reliability("Myntra") == 94
    
    print("Reliability Tests Passed!\n")

def test_model_extraction():
    print("Testing Model Extraction Logic...")

    cases = [
        ("Samsung Galaxy S24 Ultra SM-S921B/DS 256GB", "SM-S921B/DS"),
        ("SAMSUNG S24 ULTRA sm-s921b/ds", "SM-S921B/DS"),
        ("Sony WH-1000XM5 Wireless Headphones", "WH-1000XM5"),
        ("iPhone 15 Pro A2848", "A2848"),
    ]

    for title, expected in cases:
        got = _extract_model(title)
        print(f"  {title!r} -> {got!r} (Expected {expected!r})")
        assert got == expected

    print("Model Extraction Tests Passed!\n")

if __name__ == "__main__":
    test_similarity()
    test_reliability()
    test_model_extraction()
