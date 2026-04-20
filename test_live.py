from dotenv import load_dotenv
load_dotenv()
from scrape import scrapeCompareRaja

queries = ['iPhone 15 Pro', 'Nike Air Max', 'Sony WH-1000XM5']
for q in queries:
    r, e = scrapeCompareRaja(q)
    if r:
        p = r[0]
        print(q, '-> Lowest:', p['lowest_price'], '| Stores:', p['store_count'], '| Error:', e)
        for o in p['offers'][:2]:
            print('   ', o['platform'], ':', o['price'])
    print()
