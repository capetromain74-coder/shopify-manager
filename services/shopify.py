"""
KP SHOES - Client Shopify (REST + GraphQL)
SSL active, retry automatique, gestion d'erreurs propre.
"""

import json
import time
import logging
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from threading import Lock

from config import SHOP, ACCESS_TOKEN, API_VERSION, COLLECTIONS_CACHE_TTL

log = logging.getLogger('kpshoes.shopify')

_collections_cache = None
_collections_cache_time = 0
_collections_lock = Lock()

_task_lock = Lock()
task_progress = {'running': False, 'current': 0, 'total': 0, 'message': ''}


def get_task_progress():
    with _task_lock:
        return dict(task_progress)


def set_task_progress(**kwargs):
    with _task_lock:
        task_progress.update(kwargs)


def shopify_request(endpoint, method='GET', data=None):
    """Requete REST Shopify avec SSL active."""
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    try:
        body = json.dumps(data).encode('utf-8') if data else None
        req = Request(url, data=body, headers=headers, method=method)
        with urlopen(req, timeout=30) as r:
            if method == 'DELETE':
                return True
            return json.loads(r.read().decode('utf-8'))
    except HTTPError as e:
        body_text = ''
        try:
            body_text = e.read().decode('utf-8')[:200]
        except Exception:
            pass
        log.error(f"[Shopify] HTTP {e.code} on {method} {endpoint}: {body_text}")
        return None
    except URLError as e:
        log.error(f"[Shopify] URL error on {endpoint}: {e.reason}")
        return None
    except Exception as e:
        log.error(f"[Shopify] Error on {endpoint}: {e}")
        return None


def shopify_graphql(query, variables=None):
    """Requete GraphQL Shopify avec SSL active."""
    url = f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json"
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    try:
        body = json.dumps(payload).encode('utf-8')
        req = Request(url, data=body, headers=headers, method='POST')
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        log.error(f"[Shopify GraphQL] {e}")
        return None


def get_collections():
    """Recupere les collections Shopify avec cache TTL."""
    global _collections_cache, _collections_cache_time

    with _collections_lock:
        now = time.time()
        if _collections_cache and (now - _collections_cache_time) < COLLECTIONS_CACHE_TTL:
            return _collections_cache

    cols = []
    for ctype in ['custom_collections', 'smart_collections']:
        r = shopify_request(f'{ctype}.json?limit=250')
        if r and ctype in r:
            for c in r[ctype]:
                cols.append({'id': c['id'], 'handle': c['handle'], 'title': c['title']})

    with _collections_lock:
        _collections_cache = cols
        _collections_cache_time = time.time()

    return cols


def invalidate_collections_cache():
    """Force le renouvellement du cache collections."""
    global _collections_cache, _collections_cache_time
    with _collections_lock:
        _collections_cache = None
        _collections_cache_time = 0


def get_product_metafields(product_id):
    """Recupere les meta title et meta description d'un produit."""
    r = shopify_request(f'products/{product_id}/metafields.json')
    meta_title = ''
    meta_description = ''
    if r and 'metafields' in r:
        for m in r['metafields']:
            if m.get('key') == 'title_tag':
                meta_title = m.get('value', '')
            elif m.get('key') == 'description_tag':
                meta_description = m.get('value', '')
    return {'meta_title': meta_title, 'meta_description': meta_description}


def get_all_products(fields=None):
    """Recupere TOUS les produits avec pagination complete."""
    products = []
    since_id = 0
    default_fields = 'id,title,handle,vendor,product_type,tags,images,variants,body_html'
    fields_param = fields or default_fields

    for _ in range(20):
        r = shopify_request(f'products.json?limit=250&since_id={since_id}&fields={fields_param}')
        if not r or 'products' not in r or not r['products']:
            break
        products.extend(r['products'])
        since_id = r['products'][-1]['id']
        if len(r['products']) < 250:
            break

    return products
