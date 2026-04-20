from duckduckgo_search import DDGS
import json

def test_ddg(query):
    print(f"Searching for: {query}")
    try:
        results = list(DDGS().text(query, max_results=5))
        print(f"Found {len(results)} results")
        for r in results:
            print(f"Title: {r.get('title')}")
            print(f"Link: {r.get('href')}")
            print(f"Snippet: {r.get('body')}")
            print("-" * 50)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Testing Amazon:")
    test_ddg("iphone 13 price site:amazon.in")
    print("\nTesting Flipkart:")
    test_ddg("iphone 13 price site:flipkart.com")
