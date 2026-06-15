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


# Nombre max de tentatives quand Shopify limite (429 REST / THROTTLED GraphQL)
SHOPIFY_MAX_RETRIES = 5


def shopify_request(endpoint, method='GET', data=None):
    """Requete REST Shopify avec SSL active + retry automatique sur rate-limit (429).
    Respecte l'en-tete Retry-After de Shopify. Evite les 'photos manquantes' quand
    l'API limite apres un long run."""
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    body = json.dumps(data).encode('utf-8') if data else None

    for attempt in range(SHOPIFY_MAX_RETRIES):
        try:
            req = Request(url, data=body, headers=headers, method=method)
            with urlopen(req, timeout=30) as r:
                if method == 'DELETE':
                    return True
                return json.loads(r.read().decode('utf-8'))
        except HTTPError as e:
            # 429 = rate limit, 5xx = erreur serveur transitoire -> on retente
            if e.code in (429, 500, 502, 503, 504) and attempt < SHOPIFY_MAX_RETRIES - 1:
                try:
                    wait = float(e.headers.get('Retry-After', '')) if e.headers else 0
                except (TypeError, ValueError):
                    wait = 0
                if wait <= 0:
                    wait = 1.5 * (attempt + 1)  # backoff progressif
                log.warning(f"[Shopify] HTTP {e.code} on {method} {endpoint} -> retry {attempt+1}/{SHOPIFY_MAX_RETRIES} dans {wait:.1f}s")
                time.sleep(wait)
                continue
            body_text = ''
            try:
                body_text = e.read().decode('utf-8')[:200]
            except Exception:
                pass
            log.error(f"[Shopify] HTTP {e.code} on {method} {endpoint}: {body_text}")
            return None
        except URLError as e:
            if attempt < SHOPIFY_MAX_RETRIES - 1:
                log.warning(f"[Shopify] URL error on {endpoint} ({e.reason}) -> retry {attempt+1}")
                time.sleep(1.5 * (attempt + 1))
                continue
            log.error(f"[Shopify] URL error on {endpoint}: {e.reason}")
            return None
        except Exception as e:
            log.error(f"[Shopify] Error on {endpoint}: {e}")
            return None
    return None


def shopify_graphql(query, variables=None):
    """Requete GraphQL Shopify + retry sur throttling.
    Shopify GraphQL renvoie un HTTP 200 avec une erreur 'THROTTLED' (limite basee
    sur le cout) -> sans retry, les renommages/alt echouaient silencieusement."""
    url = f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json"
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    body = json.dumps(payload).encode('utf-8')

    for attempt in range(SHOPIFY_MAX_RETRIES):
        try:
            req = Request(url, data=body, headers=headers, method='POST')
            with urlopen(req, timeout=30) as r:
                result = json.loads(r.read().decode('utf-8'))
            # Detecter le throttling cout-base (HTTP 200 mais errors THROTTLED)
            errs = result.get('errors') if isinstance(result, dict) else None
            throttled = False
            if errs:
                for err in errs:
                    code = (err.get('extensions', {}) or {}).get('code', '')
                    if code == 'THROTTLED' or 'throttl' in (err.get('message', '') or '').lower():
                        throttled = True
                        break
            if throttled and attempt < SHOPIFY_MAX_RETRIES - 1:
                wait = 2.0 * (attempt + 1)
                log.warning(f"[Shopify GraphQL] THROTTLED -> retry {attempt+1}/{SHOPIFY_MAX_RETRIES} dans {wait:.1f}s")
                time.sleep(wait)
                continue
            return result
        except HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < SHOPIFY_MAX_RETRIES - 1:
                try:
                    wait = float(e.headers.get('Retry-After', '')) if e.headers else 0
                except (TypeError, ValueError):
                    wait = 0
                if wait <= 0:
                    wait = 2.0 * (attempt + 1)
                log.warning(f"[Shopify GraphQL] HTTP {e.code} -> retry {attempt+1}/{SHOPIFY_MAX_RETRIES} dans {wait:.1f}s")
                time.sleep(wait)
                continue
            log.error(f"[Shopify GraphQL] HTTP {e.code}")
            return None
        except Exception as e:
            if attempt < SHOPIFY_MAX_RETRIES - 1:
                log.warning(f"[Shopify GraphQL] {e} -> retry {attempt+1}")
                time.sleep(2.0 * (attempt + 1))
                continue
            log.error(f"[Shopify GraphQL] {e}")
            return None
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
