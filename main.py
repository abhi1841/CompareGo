from flask import Flask, render_template, request, jsonify, send_from_directory
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import time
import copy
import hashlib
from scrape import scrapeCompareRaja, scrapeDetailPage, get_suggestions, get_featured_retailers
from predict import predictReview

load_dotenv()

# connect to mongo db
mongo_uri = os.getenv('MONGO_URI') or 'mongodb://localhost:27017/'
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1500, connectTimeoutMS=1500)
db = client['comparego']
productsCollection = db['productreviews']
priceHistoryCollection = db['price_history']
searchAnalyticsCollection = db['search_analytics']
offerBlacklistCollection = db['offer_blacklist']
OFFER_BLACKLIST_MEMORY = set()

SEARCH_CACHE_TTL = 3600  # 1 hour

try:
    priceHistoryCollection.create_index([('pid', 1), ('timestamp', -1)])
    priceHistoryCollection.create_index([('pid', 1), ('retailer', 1), ('timestamp', -1)])
    searchAnalyticsCollection.create_index([('timestamp', -1)])
    offerBlacklistCollection.create_index([('pid', 1), ('retailer', 1), ('link', 1)], unique=True)
    offerBlacklistCollection.create_index([('timestamp', -1)])
    db['search_cache'].create_index([('key', 1)], unique=True)
    db['search_cache'].create_index([('ts', 1)], expireAfterSeconds=86400)
except Exception:
    pass

app = Flask(__name__)

def cached_search(query):
    """
    MongoDB-backed search cache with 1 hour TTL.
    Falls back to live search on miss. Returns a deep copy to prevent mutation.
    """
    cache_key = hashlib.md5(query.lower().strip().encode()).hexdigest()
    now = time.time()

    # Try MongoDB cache first
    try:
        cached = db['search_cache'].find_one({'key': cache_key})
        if cached and (now - cached.get('ts', 0)) < SEARCH_CACHE_TTL:
            print(f"  -> [Cache HIT] '{query}'")
            results = cached.get('results', [])
            error = cached.get('error')
            return copy.deepcopy(results), error
    except Exception:
        pass

    # Live search
    results, error = scrapeCompareRaja(query)

    # Store in MongoDB cache
    try:
        db['search_cache'].update_one(
            {'key': cache_key},
            {'$set': {'key': cache_key, 'query': query, 'results': results,
                      'error': error, 'ts': now}},
            upsert=True
        )
    except Exception:
        pass

    return copy.deepcopy(results or []), error

@app.route('/')
def index():
    featured_retailers = get_featured_retailers(limit=6)
    trending_queries = []
    try:
        pipeline = [
            {'$group': {'_id': '$query', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': 6}
        ]
        trending_queries = [{'query': x['_id'], 'count': x['count']} for x in db['search_analytics'].aggregate(pipeline)]
    except Exception:
        trending_queries = []
    return render_template('index.html', featured_retailers=featured_retailers, trending_queries=trending_queries)


@app.route('/api/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('q', '')
    suggestions = get_suggestions(query)
    return jsonify(suggestions)

@app.route('/api/flag-offer', methods=['POST'])
def flag_offer():
    data = request.get_json(silent=True) or {}
    pid = data.get('pid')
    retailer = data.get('retailer')
    link = data.get('link')
    reason = data.get('reason') or 'incorrect_match'

    if not pid or not retailer or not link:
        return jsonify({'status': 'error', 'message': 'missing_fields'}), 400

    doc = {
        'pid': pid,
        'retailer': retailer,
        'link': link,
        'reason': reason,
        'timestamp': time.time(),
        'ip': request.remote_addr
    }

    try:
        offerBlacklistCollection.update_one(
            {'pid': pid, 'retailer': retailer, 'link': link},
            {'$setOnInsert': doc},
            upsert=True
        )
        return jsonify({'status': 'ok'})
    except Exception:
        OFFER_BLACKLIST_MEMORY.add((pid, retailer, link))
        return jsonify({'status': 'ok'})

def _log_price_history_from_results(results):
    if not results:
        return
    now = time.time()

    for product in results[:12]:
        pid = product.get('pid')
        if not pid:
            continue

        offers = product.get('offers') or []
        offers = [o for o in offers if o.get('raw_price') is not None and o.get('platform')]
        offers.sort(key=lambda o: o.get('raw_price'))
        for offer in offers[:4]:
            retailer = offer.get('platform')
            price = offer.get('raw_price')

            last = None
            try:
                last = priceHistoryCollection.find_one(
                    {'pid': pid, 'retailer': retailer},
                    sort=[('timestamp', -1)],
                    projection={'price': 1, 'timestamp': 1}
                )
            except Exception:
                last = None

            if last:
                last_ts = last.get('timestamp') or 0
                last_price = last.get('price')
                if (now - last_ts) < 6 * 60 * 60 and last_price == price:
                    continue

            try:
                priceHistoryCollection.insert_one({
                    'pid': pid,
                    'retailer': retailer,
                    'price': price,
                    'timestamp': now
                })
            except Exception:
                pass

def _get_price_trend(pid, days=30, points=15):
    if not pid:
        return {'series': [], 'label': 'No trend'}

    cutoff = time.time() - days * 86400
    try:
        docs = list(
            priceHistoryCollection.find(
                {'pid': pid, 'timestamp': {'$gte': cutoff}},
                projection={'price': 1, 'timestamp': 1, '_id': 0}
            ).sort('timestamp', -1).limit(points * 6)
        )
    except Exception:
        return {'series': [], 'label': 'No trend'}

    docs.reverse()
    prices = [d.get('price') for d in docs if isinstance(d.get('price'), (int, float))]
    if len(prices) < 2:
        return {'series': [], 'label': 'No trend'}

    if len(prices) > points:
        step = max(1, len(prices) // points)
        prices = prices[::step]
        prices = prices[:points]

    first = prices[0]
    last = prices[-1]
    if first <= 0:
        label = 'No trend'
    else:
        pct = ((last - first) / first) * 100.0
        if abs(pct) < 1.0:
            label = 'Stable'
        elif pct > 0:
            label = f"Up {pct:.1f}%"
        else:
            label = f"Down {abs(pct):.1f}%"

    return {'series': prices, 'label': label}

def _apply_offer_blacklist(results):
    if not results:
        return

    pids = [p.get('pid') for p in results if p.get('pid')]
    if not pids:
        return

    blocked = {}
    try:
        docs = list(
            offerBlacklistCollection.find(
                {'pid': {'$in': pids}},
                projection={'pid': 1, 'retailer': 1, 'link': 1, '_id': 0}
            )
        )
        for d in docs:
            pid = d.get('pid')
            if not pid:
                continue
            blocked.setdefault(pid, set()).add((d.get('retailer'), d.get('link')))
    except Exception:
        pass

    for pid, retailer, link in OFFER_BLACKLIST_MEMORY:
        if pid in pids:
            blocked.setdefault(pid, set()).add((retailer, link))

    for product in results:
        pid = product.get('pid')
        if not pid or pid not in blocked:
            continue

        offers = product.get('offers') or []
        filtered = [o for o in offers if (o.get('platform'), o.get('link')) not in blocked[pid]]
        product['offers'] = filtered
        product['store_count'] = len(filtered)

        prices = [o.get('raw_price') for o in filtered if o.get('raw_price') is not None]
        if prices:
            lowest = min(prices)
            product['raw_lowest_price'] = lowest
            product['lowest_price'] = f"{int(lowest):,}"

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    if query:
        try:
            searchAnalyticsCollection.insert_one({
                'query': query,
                'timestamp': time.time(),
                'ip': request.remote_addr
            })
        except Exception:
            pass
    results, error = cached_search(query)

    _log_price_history_from_results(results)
    for product in results or []:
        product['trend'] = _get_price_trend(product.get('pid'))
    _apply_offer_blacklist(results)
    
    # Extract data for filters
    brands = sorted(list(set(p['brand'] for p in results))) if results else []
    
    # Extract dynamic filters from specs
    dynamic_filters = {}
    if results:
        for product in results:
            for key, value in product.get('specs', {}).items():
                if key not in dynamic_filters:
                    dynamic_filters[key] = set()
                dynamic_filters[key].add(value)
    
    # Convert sets to sorted lists for template
    for key in dynamic_filters:
        dynamic_filters[key] = sorted(list(dynamic_filters[key]))

    min_price = 0
    max_price = 100000
    if results:
        prices = [p['raw_lowest_price'] for p in results if p.get('raw_lowest_price') is not None]
        if prices:
            min_price = min(prices)
            max_price = max(prices) or 100000
        
    return render_template('search.html', 
                           results=results, 
                           error=error, 
                           query=query,
                           brands=brands,
                           dynamic_filters=dynamic_filters,
                           min_price=min_price,
                           max_price=max_price)

# /details/id


@app.route('/details/<id>')
def details(id):
    url = 'https://www.compareraja.in/' + id + '.html'
    print(url)
    results, error = scrapeDetailPage(url)
    if not results:
        results = {'title': '', 'image': '', 'points': [], 'prices': []}
    results['id'] = id
    # get product reviews , and overall rating
    productDetail = productsCollection.find_one({'id': id})
    if productDetail:
        productDetail['reviews'].reverse()
    else:
        productDetail = {
            'reviews': [],
            'overallRating': 0,
            'reviewsCount': 0
        }
    return render_template('details.html', results=results, productDetail=productDetail, error=error)


# review structure
# {
    # id: '123', # product id
    # reviews: [
    # {
    # comment: 'good product',
    # rating: 4,
    # }
    # ],
    # overallRating: 4.5
    # reviewsCount: 1
# }


@app.route('/api/review', methods=['POST'])
def addReview():
    data = request.get_json()
    id = data['id']
    review = data['review']
    # check if product exists
    product = productsCollection.find_one({'id': id})
    if product:
        # update the product
        updated_rating = (product['overallRating'] + review['rating']) / 2
        productsCollection.update_one({'id': id}, {'$push': {
                                      'reviews': review},
            '$set': {
            'overallRating': updated_rating},
            '$inc': {
            'reviewsCount': 1}
        },
        )
    else:
        # create the product
        productsCollection.insert_one({
            'id': id,
            'reviews': [review],
            'overallRating': review['rating'],
            'reviewsCount': 1
        })
    return jsonify({'message': 'success'})


@app.route('/api/predict', methods=['POST'])
def predict():
    data = request.get_json()
    stars = predictReview(data['comment'])
    return jsonify({'stars': stars})

# ---------------------logos---------------------


@app.route('/logo/fpk')
def fkp():
    return send_from_directory('static', 'fpk.png')


@app.route('/logo/amzn')
def amzn():
    return send_from_directory('static', 'amzn.png')


@app.route('/logo/tclck')
def tclck():
    return send_from_directory('static', 'tclck.png')

# wildcard route for other than these


@app.route('/logo/<path:path>')
def send_logo(path):
    return send_from_directory('static', "shopping.png")


@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """Dev endpoint: clears the search result cache (useful after updating SERPAPI_KEY)."""
    try:
        result = db['search_cache'].delete_many({})
        return jsonify({'status': 'ok', 'deleted': result.deleted_count})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
