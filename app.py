"""
Shopify Manager V4.2 - Performance & Quality Edition
Améliorations vs V4.1:
- Cache produits + collections (évite les appels API répétitifs)
- Retry automatique avec backoff sur rate limit (429)
- SSL vérifié correctement
- Metafields: upsert au lieu de POST (évite les doublons)
- Score SEO avec metafields en cache (score réel dès le listing)
- Pagination frontend lazy-render
- Fix mapping nike-p-6000/air-max
- Meilleure gestion d'erreurs
- Code frontend restructuré et lisible
"""

from flask import Flask, jsonify, request
import json, os, time, re, ssl, certifi
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from datetime import datetime
from threading import Thread, Lock

app = Flask(__name__)

# ─── CONFIG ──────────────────────────────────────────────────────────────
SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'
SITE_NAME = os.environ.get('SITE_NAME', 'KP SHOES')
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'kpshoes.fr')
BENEFITS = ["100% Authentique", "Livraison rapide", "Paiement 3x sans frais"]

# ─── CACHE ───────────────────────────────────────────────────────────────
_cache_lock = Lock()

_products_cache = {'data': [], 'metafields': {}, 'last_update': None}
_collections_cache = {'data': [], 'last_update': None}
CACHE_TTL_PRODUCTS = 300   # 5 min
CACHE_TTL_COLLECTIONS = 600  # 10 min

task_progress = {
    'running': False, 'current': 0, 'total': 0,
    'message': '', 'success_count': 0, 'error_count': 0
}

# ─── SSL CONTEXT (réutilisé) ─────────────────────────────────────────────
try:
    _ssl_ctx = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _ssl_ctx = ssl.create_default_context()


# ═══════════════════════════════════════════════════════════════════════════
#  SHOPIFY API — avec retry & backoff
# ═══════════════════════════════════════════════════════════════════════════
def shopify_request(endpoint, method='GET', data=None, retries=3):
    """Appel Shopify avec retry automatique sur 429/5xx."""
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    body = json.dumps(data).encode('utf-8') if data else None

    for attempt in range(retries):
        try:
            req = Request(url, data=body, headers=headers, method=method)
            with urlopen(req, context=_ssl_ctx, timeout=30) as resp:
                if method == 'DELETE':
                    return True
                return json.loads(resp.read().decode('utf-8'))
        except HTTPError as e:
            status = e.code
            if status == 429:
                # Rate limited — respecter Retry-After ou backoff
                retry_after = float(e.headers.get('Retry-After', 2 * (attempt + 1)))
                print(f"[429] Rate limited, retry in {retry_after}s...")
                time.sleep(retry_after)
                continue
            elif status >= 500:
                wait = 2 * (attempt + 1)
                print(f"[{status}] Server error, retry in {wait}s...")
                time.sleep(wait)
                continue
            else:
                print(f"[API {status}] {e.read().decode('utf-8', errors='replace')[:200]}")
                return None
        except Exception as e:
            print(f"[API Error] {type(e).__name__}: {e}")
            if attempt < retries - 1:
                time.sleep(1)
                continue
            return None
    return None


# ═══════════════════════════════════════════════════════════════════════════
#  DATA FETCHING — avec cache
# ═══════════════════════════════════════════════════════════════════════════
def _cache_is_valid(cache_dict, ttl):
    if not cache_dict['last_update']:
        return False
    age = (datetime.now() - cache_dict['last_update']).total_seconds()
    return age < ttl and cache_dict['data']


def get_all_products(force_refresh=False):
    """Récupère tous les produits avec cache."""
    global _products_cache
    with _cache_lock:
        if not force_refresh and _cache_is_valid(_products_cache, CACHE_TTL_PRODUCTS):
            return _products_cache['data']

    all_products = []
    since_id = 0
    while True:
        result = shopify_request(f'products.json?limit=250&since_id={since_id}')
        if not result or 'products' not in result or not result['products']:
            break
        all_products.extend(result['products'])
        since_id = result['products'][-1]['id']
        if len(result['products']) < 250:
            break
        time.sleep(0.5)

    with _cache_lock:
        _products_cache['data'] = all_products
        _products_cache['last_update'] = datetime.now()

    return all_products


def get_all_collections(force_refresh=False):
    """Récupère toutes les collections avec cache."""
    global _collections_cache
    with _cache_lock:
        if not force_refresh and _cache_is_valid(_collections_cache, CACHE_TTL_COLLECTIONS):
            return _collections_cache['data']

    all_collections = []
    for ctype in ['custom_collections', 'smart_collections']:
        result = shopify_request(f'{ctype}.json?limit=250')
        if result and ctype in result:
            for c in result[ctype]:
                all_collections.append({
                    'id': c['id'], 'handle': c['handle'], 'title': c['title']
                })

    with _cache_lock:
        _collections_cache['data'] = all_collections
        _collections_cache['last_update'] = datetime.now()

    return all_collections


def get_product_metafields(product_id):
    """Récupère les metafields SEO d'un produit."""
    result = shopify_request(f'products/{product_id}/metafields.json')
    meta_title, meta_desc = None, None
    mt_id, md_id = None, None
    if result and 'metafields' in result:
        for mf in result['metafields']:
            if mf.get('namespace') == 'global':
                if mf.get('key') == 'title_tag':
                    meta_title = mf.get('value')
                    mt_id = mf.get('id')
                elif mf.get('key') == 'description_tag':
                    meta_desc = mf.get('value')
                    md_id = mf.get('id')
    return {
        'meta_title': meta_title, 'meta_description': meta_desc,
        'meta_title_id': mt_id, 'meta_description_id': md_id
    }


def get_all_metafields_batch(product_ids):
    """Récupère les metafields SEO pour une liste de produits.
    Utilise le cache pour éviter les appels redondants."""
    global _products_cache
    results = {}
    to_fetch = []

    with _cache_lock:
        for pid in product_ids:
            cached = _products_cache['metafields'].get(pid)
            if cached:
                results[pid] = cached
            else:
                to_fetch.append(pid)

    for pid in to_fetch:
        mf = get_product_metafields(pid)
        results[pid] = mf
        with _cache_lock:
            _products_cache['metafields'][pid] = mf
        time.sleep(0.3)

    return results


# ═══════════════════════════════════════════════════════════════════════════
#  COLLECTION MATCHING
# ═══════════════════════════════════════════════════════════════════════════
# MODÈLES PRÉCIS (priorité 1)
MODEL_MAPPINGS = [
    ('ugg-tasman', ['ugg tasman', 'tasman slipper', 'tasman chestnut', 'tasman black']),
    ('ugg-tazz', ['ugg tazz', 'tazz slipper']),
    ('jordan-4', ['jordan 4', 'aj4', 'air jordan 4']),
    ('jordan-1-low', ['jordan 1 low', 'aj1 low']),
    ('jordan-1-mid', ['jordan 1 mid', 'aj1 mid']),
    ('jordan-1-high', ['jordan 1 high', 'aj1 high', 'jordan 1 retro high']),
    ('nike-dunk-low', ['dunk low']),
    ('nike-dunk-high', ['dunk high']),
    ('air-force-1', ['air force 1', 'af1']),
    ('nike-air-max', ['air max']),          # FIX: était mappé à nike-p-6000
    ('nike-p-6000', ['p-6000', 'p6000']),   # FIX: mapping correct pour P-6000
    ('adidas-samba', ['samba']),
    ('adidas-campus', ['campus']),
    ('adidas-gazelle', ['gazelle']),
    ('adidas-spezial', ['spezial']),
    ('adidas-forum', ['forum']),
    ('new-balance-550', ['new balance 550', 'nb 550']),
    ('new-balance-530', ['new balance 530']),
    ('new-balance-2002r', ['2002r']),
    ('asics-gel-1130', ['gel-1130', 'gel 1130']),
    ('asics-gel-kayano', ['kayano']),
    ('asics-gel-nyc', ['gel-nyc', 'gel nyc']),
    ('yeezy-350', ['yeezy 350']),
    ('yeezy-500', ['yeezy 500']),
    ('yeezy-slide', ['yeezy slide']),
    ('yeezy-foam', ['foam runner']),
    ('birkenstock-boston', ['boston']),
]

# MARQUES (priorité 2) — ordre important: spécifique avant générique
BRAND_MAPPINGS = [
    ('jordan-1', ['jordan', 'air jordan']),
    ('adidas-1', ['adidas']),
    ('asics-1', ['asics']),
    ('ugg', ['ugg']),
    ('nike', ['nike']),
    ('new-balance', ['new balance']),
    ('puma', ['puma']),
    ('birkenstock-1', ['birkenstock']),
    ('yeezy', ['yeezy']),
    ('bape', ['bape']),
]


def find_best_collection(product_title, collections):
    title_lower = product_title.lower()
    available = {c['handle']: c['title'] for c in collections}

    for handle, patterns in MODEL_MAPPINGS:
        if handle in available:
            for pattern in patterns:
                if pattern in title_lower:
                    return {'handle': handle, 'title': available[handle], 'type': 'model'}

    for handle, patterns in BRAND_MAPPINGS:
        if handle in available:
            for pattern in patterns:
                if pattern in title_lower:
                    return {'handle': handle, 'title': available[handle], 'type': 'brand'}
    return None


# ═══════════════════════════════════════════════════════════════════════════
#  SEO ANALYSIS & GENERATION
# ═══════════════════════════════════════════════════════════════════════════
def strip_html(text):
    if not text:
        return ''
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text)).strip()


def extract_sku(product):
    variants = product.get('variants')
    if variants and len(variants) > 0:
        return variants[0].get('sku', '')
    return ''


def extract_brand(product):
    title = product.get('title', '')
    # Ordre: plus spécifique d'abord
    for brand in ['Air Jordan', 'New Balance', 'Birkenstock',
                  'Adidas', 'Nike', 'Jordan', 'Puma', 'Asics',
                  'UGG', 'Yeezy', 'BAPE']:
        if brand.lower() in title.lower():
            return brand
    return product.get('vendor', 'Sneakers')


def extract_colorway(product):
    match = re.search(r'\(([^)]+)\)', product.get('title', ''))
    return match.group(1) if match else ''


def check_seo_status(product, metafields=None):
    status = {
        'meta_title': {'exists': False, 'value': None, 'needs_update': True},
        'meta_description': {'exists': False, 'value': None, 'needs_update': True},
        'description': {'exists': False, 'value': None, 'has_links': False, 'needs_update': True}
    }

    if metafields and metafields.get('meta_title'):
        mt = metafields['meta_title']
        status['meta_title']['exists'] = True
        status['meta_title']['value'] = mt
        if SITE_NAME.lower() in mt.lower():
            status['meta_title']['needs_update'] = False

    if metafields and metafields.get('meta_description'):
        md = metafields['meta_description']
        status['meta_description']['exists'] = True
        status['meta_description']['value'] = md
        if len(md) >= 50 and ('authentique' in md.lower() or SITE_NAME.lower() in md.lower()):
            status['meta_description']['needs_update'] = False

    body = product.get('body_html', '')
    if body and len(body.strip()) > 100:
        status['description']['exists'] = True
        status['description']['value'] = body[:200] + ('...' if len(body) > 200 else '')
        if '<a href=' in body.lower() and SITE_DOMAIN in body.lower():
            status['description']['has_links'] = True
            status['description']['needs_update'] = False

    return status


def calculate_seo_score(seo_status):
    score = 0
    if not seo_status['meta_title']['needs_update']:
        score += 30
    elif seo_status['meta_title']['exists']:
        score += 15
    if not seo_status['meta_description']['needs_update']:
        score += 30
    elif seo_status['meta_description']['exists']:
        score += 15
    if not seo_status['description']['needs_update']:
        score += 40
    elif seo_status['description']['exists']:
        score += 20
    return score


def generate_meta_title(product):
    title = product.get('title', '')
    meta = f"{title} | {SITE_NAME}"
    if len(meta) > 60:
        cut = 60 - len(SITE_NAME) - 6
        meta = f"{title[:cut]}... | {SITE_NAME}"
    return meta


def generate_meta_description(product):
    title = product.get('title', '')
    sku = extract_sku(product)
    base = f"Achetez la {title}" + (f" (SKU: {sku})" if sku else "") + f" sur {SITE_NAME}"
    meta = f"{base} ✓ " + " ✓ ".join(BENEFITS) + "."
    if len(meta) > 155:
        meta = f"Achetez la {title} ✓ {BENEFITS[0]} ✓ {BENEFITS[1]} - {SITE_NAME}"[:155]
    return meta


def generate_description(product, collection):
    title = product.get('title', '')
    brand = extract_brand(product)
    sku = extract_sku(product)
    colorway = extract_colorway(product)
    current = strip_html(product.get('body_html', ''))

    lines = []
    if collection:
        link = f'<a href="https://{SITE_DOMAIN}/collections/{collection["handle"]}">{collection["title"]}</a>'
        lines.append(f'<p>Découvrez la <strong>{title}</strong>, une pièce incontournable de notre collection {link}.</p>')
    else:
        lines.append(f'<p>Découvrez la <strong>{title}</strong>, signée {brand}.</p>')

    if current and len(current) > 50:
        lines.append(f'<p>{current[:400]}{"..." if len(current) > 400 else ""}</p>')
    else:
        lines.append(f'<p>Cette {brand} se distingue par son design unique et ses finitions de qualité.</p>')

    tech = []
    if sku:
        tech.append(f'<strong>SKU</strong> : {sku}')
    if colorway:
        tech.append(f'<strong>Colorway</strong> : {colorway}')
    tech.append(f'<strong>Marque</strong> : {brand}')
    lines.append('<p>' + '<br>'.join(tech) + '</p>')

    lines.append(
        f'<p>Chez <strong>{SITE_NAME}</strong>, toutes nos sneakers sont '
        f'<strong>100% authentiques</strong> et vérifiées par nos experts.</p>'
    )
    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  SHOPIFY UPDATE — avec upsert metafields
# ═══════════════════════════════════════════════════════════════════════════
def update_product_seo(product_id, updates, existing_metafields=None):
    """Met à jour le SEO d'un produit. Utilise PUT pour les metafields existants."""
    success = True

    if 'body_html' in updates:
        result = shopify_request(
            f'products/{product_id}.json', 'PUT',
            {'product': {'id': product_id, 'body_html': updates['body_html']}}
        )
        if not result:
            success = False
        time.sleep(0.4)

    # Metafields: PUT si existe déjà, POST sinon
    if 'meta_title' in updates:
        mt_id = (existing_metafields or {}).get('meta_title_id')
        if mt_id:
            shopify_request(
                f'products/{product_id}/metafields/{mt_id}.json', 'PUT',
                {'metafield': {'id': mt_id, 'value': updates['meta_title']}}
            )
        else:
            shopify_request(
                f'products/{product_id}/metafields.json', 'POST',
                {'metafield': {
                    'namespace': 'global', 'key': 'title_tag',
                    'value': updates['meta_title'], 'type': 'single_line_text_field'
                }}
            )
        time.sleep(0.3)

    if 'meta_description' in updates:
        md_id = (existing_metafields or {}).get('meta_description_id')
        if md_id:
            shopify_request(
                f'products/{product_id}/metafields/{md_id}.json', 'PUT',
                {'metafield': {'id': md_id, 'value': updates['meta_description']}}
            )
        else:
            shopify_request(
                f'products/{product_id}/metafields.json', 'POST',
                {'metafield': {
                    'namespace': 'global', 'key': 'description_tag',
                    'value': updates['meta_description'], 'type': 'single_line_text_field'
                }}
            )
        time.sleep(0.3)

    # Invalider le cache metafields pour ce produit
    with _cache_lock:
        _products_cache['metafields'].pop(product_id, None)

    return success


def invalidate_product_cache():
    """Force le rechargement des produits au prochain appel."""
    global _products_cache
    with _cache_lock:
        _products_cache['last_update'] = None


# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES — Pages
# ═══════════════════════════════════════════════════════════════════════════
@app.route('/')
def home():
    return HOME_HTML


@app.route('/seo')
def seo_page():
    return SEO_HTML


# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES — API
# ═══════════════════════════════════════════════════════════════════════════
@app.route('/api/collections')
def api_collections():
    cols = get_all_collections()
    return jsonify({'collections': cols, 'count': len(cols)})


@app.route('/api/products')
def api_products():
    """Liste tous les produits avec score SEO.
    Le score est basé sur body_html uniquement (rapide).
    Pour le score complet avec metafields, utiliser /api/product/<id>/seo-status.
    """
    force = request.args.get('refresh', '').lower() == 'true'
    products = get_all_products(force_refresh=force)
    collections = get_all_collections()

    result = []
    stats = {'total': 0, 'seo_complete': 0, 'seo_partial': 0, 'seo_missing': 0}

    for p in products:
        collection = find_best_collection(p.get('title', ''), collections)
        body = p.get('body_html', '') or ''
        stripped = strip_html(body)
        has_desc = len(stripped) > 100
        has_links = '<a href=' in body.lower() and SITE_DOMAIN in body.lower()
        # Score partiel (sans metafields pour la vitesse)
        score = (30 if has_desc else 0) + (40 if has_links else 0)

        stats['total'] += 1
        if score >= 70:
            stats['seo_complete'] += 1
        elif score >= 30:
            stats['seo_partial'] += 1
        else:
            stats['seo_missing'] += 1

        result.append({
            'id': p['id'],
            'title': p['title'],
            'handle': p['handle'],
            'image': (p.get('image') or {}).get('src'),
            'sku': extract_sku(p),
            'collection': collection,
            'seo_score': score,
            'has_description': has_desc,
            'has_links': has_links
        })

    stats['percentage_complete'] = (
        round(stats['seo_complete'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0
    )
    return jsonify({'products': result, 'stats': stats})


@app.route('/api/product/<int:product_id>/seo-status')
def api_product_seo_status(product_id):
    result = shopify_request(f'products/{product_id}.json')
    if not result:
        return jsonify({'error': 'Not found'}), 404

    product = result['product']
    metafields = get_product_metafields(product_id)
    collections = get_all_collections()
    collection = find_best_collection(product.get('title', ''), collections)
    seo_status = check_seo_status(product, metafields)

    return jsonify({
        'product': {
            'id': product['id'],
            'title': product['title'],
            'sku': extract_sku(product)
        },
        'collection': collection,
        'seo_status': seo_status,
        'score': calculate_seo_score(seo_status),
        'generated': {
            'meta_title': generate_meta_title(product),
            'meta_description': generate_meta_description(product),
            'description': generate_description(product, collection)
        }
    })


@app.route('/api/seo/apply', methods=['POST'])
def api_apply_seo():
    data = request.json
    product_id = data.get('product_id')
    fields = data.get('fields', [])
    if not product_id or not fields:
        return jsonify({'error': 'Missing params'}), 400

    result = shopify_request(f'products/{product_id}.json')
    if not result:
        return jsonify({'error': 'Not found'}), 404

    product = result['product']
    collection = find_best_collection(product.get('title', ''), get_all_collections())
    metafields = get_product_metafields(product_id)

    updates = {}
    if 'meta_title' in fields:
        updates['meta_title'] = generate_meta_title(product)
    if 'meta_description' in fields:
        updates['meta_description'] = generate_meta_description(product)
    if 'description' in fields:
        updates['body_html'] = generate_description(product, collection)

    ok = update_product_seo(product_id, updates, existing_metafields=metafields)
    if ok:
        invalidate_product_cache()

    return jsonify({'success': ok, 'applied_fields': list(updates.keys())})


@app.route('/api/seo/batch', methods=['POST'])
def api_batch_seo():
    global task_progress
    data = request.json
    product_ids = data.get('product_ids', [])
    fields = data.get('fields', ['description'])

    if not product_ids:
        return jsonify({'error': 'No products'}), 400
    if task_progress.get('running'):
        return jsonify({'error': 'Batch already running'}), 409

    def process():
        global task_progress
        task_progress = {
            'running': True, 'current': 0, 'total': len(product_ids),
            'message': 'Démarrage...', 'success_count': 0, 'error_count': 0
        }
        collections = get_all_collections()

        for i, pid in enumerate(product_ids):
            task_progress['current'] = i + 1
            result = shopify_request(f'products/{pid}.json')

            if result and 'product' in result:
                product = result['product']
                title = product.get('title', '')[:30]
                task_progress['message'] = f'#{i+1}/{len(product_ids)} {title}...'

                collection = find_best_collection(product.get('title', ''), collections)
                metafields = get_product_metafields(pid) if ('meta_title' in fields or 'meta_description' in fields) else None

                updates = {}
                if 'meta_title' in fields:
                    updates['meta_title'] = generate_meta_title(product)
                if 'meta_description' in fields:
                    updates['meta_description'] = generate_meta_description(product)
                if 'description' in fields:
                    updates['body_html'] = generate_description(product, collection)

                if updates and update_product_seo(pid, updates, existing_metafields=metafields):
                    task_progress['success_count'] += 1
                else:
                    task_progress['error_count'] += 1
            else:
                task_progress['error_count'] += 1

            time.sleep(1.0)

        task_progress['running'] = False
        task_progress['message'] = (
            f'Terminé! {task_progress["success_count"]} OK, '
            f'{task_progress["error_count"]} erreurs'
        )
        invalidate_product_cache()

    Thread(target=process, daemon=True).start()
    return jsonify({'status': 'started', 'total': len(product_ids)})


@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)


@app.route('/api/cache/clear', methods=['POST'])
def api_clear_cache():
    """Vide tous les caches pour forcer un refresh complet."""
    global _products_cache, _collections_cache
    with _cache_lock:
        _products_cache = {'data': [], 'metafields': {}, 'last_update': None}
        _collections_cache = {'data': [], 'last_update': None}
    return jsonify({'success': True, 'message': 'Cache vidé'})


# ═══════════════════════════════════════════════════════════════════════════
#  HTML TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════

HOME_HTML = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Shopify Manager V4.2</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:linear-gradient(135deg,#0a0a0f,#1a1a2e);min-height:100vh;
  display:flex;align-items:center;justify-content:center;color:#fff}
.c{text-align:center;padding:40px}
.logo{font-size:70px;margin-bottom:20px}
h1{font-size:48px;background:linear-gradient(135deg,#00ff88,#00cc6a);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}
.v{background:#8b5cf6;padding:6px 16px;border-radius:20px;font-size:14px;
  margin:15px 0 30px;display:inline-block}
.f{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:40px}
.f span{background:rgba(255,255,255,0.1);padding:8px 16px;border-radius:20px;font-size:12px}
.btn{display:inline-block;padding:18px 50px;
  background:linear-gradient(135deg,#00ff88,#00cc6a);color:#000;
  text-decoration:none;border-radius:12px;font-size:18px;font-weight:bold;
  transition:transform .2s,box-shadow .2s}
.btn:hover{transform:translateY(-2px);box-shadow:0 8px 25px rgba(0,255,136,0.3)}
</style>
</head>
<body>
<div class="c">
  <div class="logo">🤖</div>
  <h1>Shopify Manager</h1>
  <div class="v">V4.2 — Performance</div>
  <div class="f">
    <span>⚡ Cache intelligent</span>
    <span>🔄 Retry auto (429)</span>
    <span>✅ Upsert metafields</span>
    <span>🔒 SSL vérifié</span>
  </div>
  <a href="/seo" class="btn">🚀 Gestion SEO</a>
</div>
</body>
</html>'''


SEO_HTML = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SEO Manager V4.2</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:#0a0a0f;min-height:100vh;color:#fff}

/* Header */
.hd{padding:15px 30px;background:#111;border-bottom:1px solid #222;
  display:flex;justify-content:space-between;align-items:center}
.logo{font-size:18px;font-weight:bold}
.logo span{color:#00ff88}
.back{color:#888;text-decoration:none;transition:color .2s}
.back:hover{color:#fff}

/* Stats */
.stats{display:flex;gap:15px;padding:20px 30px;
  background:linear-gradient(90deg,rgba(0,255,136,0.08),rgba(139,92,246,0.08));
  flex-wrap:wrap}
.stat{background:rgba(0,0,0,0.3);padding:12px 20px;border-radius:8px;text-align:center}
.sv{font-size:24px;font-weight:bold}
.sv.g{color:#00ff88}.sv.o{color:#ffa502}.sv.r{color:#ff4757}
.sl{font-size:10px;color:#666;margin-top:4px}

/* Controls */
.ctrl{padding:20px 30px;display:flex;gap:15px;flex-wrap:wrap;
  align-items:flex-end;border-bottom:1px solid #222}
.cg{display:flex;flex-direction:column;gap:5px}
.cg label{font-size:10px;color:#666;text-transform:uppercase;letter-spacing:.5px}
.cg input,.cg select{padding:10px 14px;background:#1a1a2e;border:1px solid #333;
  border-radius:6px;color:#fff;font-size:13px;outline:none;transition:border-color .2s}
.cg input:focus,.cg select:focus{border-color:#00ff88}
.fs{display:flex;gap:10px;align-items:center;background:#1a1a2e;
  padding:10px 15px;border-radius:8px;border:1px solid #333}
.fs label{font-size:12px;display:flex;align-items:center;gap:5px;cursor:pointer}
.fs input[type="checkbox"]{width:16px;height:16px;accent-color:#00ff88}

/* Buttons */
.btn{padding:10px 20px;border:none;border-radius:6px;font-size:13px;
  font-weight:600;cursor:pointer;transition:opacity .2s}
.btn:hover{opacity:0.85}
.bp{background:#00ff88;color:#000}
.bd{background:#ff6b6b;color:#fff}
.bs{background:#333;color:#fff}

/* Product list */
.prods{padding:20px 30px;display:flex;flex-direction:column;gap:10px}
.prod{background:#1a1a2e;border:1px solid #2a2a3a;border-radius:10px;
  padding:15px;display:grid;
  grid-template-columns:30px 60px 1fr 150px 80px 100px;
  gap:15px;align-items:center;transition:border-color .2s}
.prod:hover{border-color:#444}

/* Checkbox */
.pck{width:22px;height:22px;border:2px solid #444;border-radius:5px;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  transition:all .15s}
.pck.chk{background:#00ff88;border-color:#00ff88}
.pck.chk::after{content:'✓';color:#000;font-weight:bold}

/* Image */
.pim{width:60px;height:60px;border-radius:8px;object-fit:cover;background:#333}

/* Info */
.pin h3{font-size:13px;margin-bottom:4px}
.psku{font-size:11px;color:#666;font-family:monospace}
.pcol{font-size:11px;margin-top:4px}
.pcol.f{color:#00ff88}.pcol.b{color:#8b5cf6}.pcol.n{color:#ff4757}

/* Status */
.pst{font-size:11px}
.si{display:flex;align-items:center;gap:5px;margin-bottom:3px}
.sok{color:#00ff88}.sms{color:#ff4757}

/* Score */
.psc{text-align:center}
.scb{display:inline-block;padding:6px 10px;border-radius:15px;
  font-weight:bold;font-size:12px}
.scb.h{background:rgba(0,255,136,0.2);color:#00ff88}
.scb.m{background:rgba(255,165,2,0.2);color:#ffa502}
.scb.l{background:rgba(255,71,87,0.2);color:#ff4757}

/* Actions */
.pac{display:flex;gap:5px}
.ab{padding:6px 10px;font-size:11px;border:none;border-radius:4px;
  cursor:pointer;transition:opacity .2s}
.ab:hover{opacity:0.8}
.ab.v{background:#333;color:#fff}
.ab.a{background:#00ff88;color:#000}

/* Modal */
.mod{position:fixed;top:0;left:0;right:0;bottom:0;
  background:rgba(0,0,0,0.9);display:none;align-items:center;
  justify-content:center;z-index:1000;padding:20px}
.mod.sh{display:flex}
.mc{background:#1a1a2e;border-radius:12px;max-width:900px;width:100%;
  max-height:90vh;overflow-y:auto}
.mh{padding:20px;border-bottom:1px solid #333;display:flex;justify-content:space-between}
.mh h2{font-size:18px}
.mx{background:none;border:none;color:#888;font-size:24px;cursor:pointer}
.mx:hover{color:#fff}
.mb{padding:20px}
.ss{margin-bottom:20px}
.ss h4{font-size:13px;color:#888;margin-bottom:10px;display:flex;align-items:center;gap:10px}
.ss .bg{font-size:10px;padding:2px 8px;border-radius:10px}
.ss .bg.ok{background:#00ff88;color:#000}
.ss .bg.ms{background:#ff4757;color:#fff}
.sc{background:#0a0a0f;padding:12px;border-radius:6px;font-size:12px;color:#888;
  margin-bottom:8px;border-left:3px solid #444;word-break:break-word}
.sg{background:#0a0a0f;padding:12px;border-radius:6px;font-size:12px;color:#00ff88;
  border-left:3px solid #00ff88;word-break:break-word}
.sg pre{white-space:pre-wrap;font-family:inherit}
.mfs{margin-top:20px;padding:15px;background:#0a0a0f;border-radius:8px}
.mfs h4{margin-bottom:10px;font-size:13px}
.mfs label{display:flex;align-items:center;gap:8px;margin-bottom:8px;
  font-size:13px;cursor:pointer}
.ma{padding:20px;border-top:1px solid #333;display:flex;gap:10px;justify-content:flex-end}

/* Progress bar */
.pb{position:fixed;top:0;left:0;right:0;background:#1a1a2e;padding:20px 30px;
  z-index:2000;border-bottom:2px solid #00ff88;display:none}
.pb.sh{display:block}
.ph{display:flex;justify-content:space-between;margin-bottom:10px}
.pt{height:8px;background:#333;border-radius:4px;overflow:hidden}
.pf{height:100%;background:linear-gradient(90deg,#00ff88,#8b5cf6);
  transition:width 0.3s}
.px{margin-top:8px;font-size:13px;color:#888}

/* Toast */
.tst{position:fixed;bottom:20px;right:20px;padding:12px 20px;
  border-radius:8px;z-index:3000;animation:fadeIn .2s}
.tst.s{background:#00ff88;color:#000}
.tst.e{background:#ff4757;color:#fff}

/* Loading */
.ld{text-align:center;padding:60px;color:#666}
.sp{width:40px;height:40px;border:3px solid #333;border-top-color:#00ff88;
  border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 15px}

/* Cache indicator */
.cache-info{font-size:10px;color:#555;padding:5px 30px;text-align:right}

@keyframes spin{to{transform:rotate(360deg)}}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
</style>
</head>
<body>

<div class="pb" id="pb">
  <div class="ph"><strong>Génération SEO...</strong><span id="pc">0/0</span></div>
  <div class="pt"><div class="pf" id="pf"></div></div>
  <div class="px" id="px">Init...</div>
</div>

<header class="hd">
  <a href="/" class="back">← Accueil</a>
  <div class="logo">🤖 SEO <span>Manager</span> <small style="color:#8b5cf6;font-size:11px">v4.2</small></div>
  <div></div>
</header>

<div class="stats">
  <div class="stat"><div class="sv g" id="s1">-</div><div class="sl">Complet</div></div>
  <div class="stat"><div class="sv o" id="s2">-</div><div class="sl">Partiel</div></div>
  <div class="stat"><div class="sv r" id="s3">-</div><div class="sl">Manquant</div></div>
  <div class="stat"><div class="sv" id="s4">-</div><div class="sl">Total</div></div>
  <div class="stat"><div class="sv g" id="s5">-%</div><div class="sl">Optimisé</div></div>
</div>

<div class="ctrl">
  <div class="cg"><label>Rechercher</label>
    <input type="text" id="src" placeholder="Nom, SKU..."></div>
  <div class="cg"><label>Filtrer</label>
    <select id="flt">
      <option value="all">Tous</option>
      <option value="missing">❌ Sans liens</option>
      <option value="partial">⚠️ Partiel</option>
      <option value="complete">✅ Complet</option>
    </select>
  </div>
  <div class="fs">
    <span style="font-size:11px;color:#888">Champs:</span>
    <label><input type="checkbox" id="ft"> Title</label>
    <label><input type="checkbox" id="fd"> Desc</label>
    <label><input type="checkbox" id="fb" checked> Body</label>
  </div>
  <button class="btn bs" onclick="load(true)" title="Forcer refresh depuis Shopify">🔄</button>
  <button class="btn bp" onclick="applySel()">⚡ Sélection</button>
  <button class="btn bd" onclick="applyAll()">🚀 TOUT</button>
  <div style="margin-left:auto;font-size:12px;color:#888">
    <strong id="sc">0</strong> sélect.
  </div>
</div>

<div class="cache-info" id="cache-info"></div>
<div class="prods" id="prods"><div class="ld"><div class="sp"></div>Chargement...</div></div>

<!-- Modal détails -->
<div class="mod" id="mod">
  <div class="mc">
    <div class="mh">
      <h2 id="mt">Détails</h2>
      <button class="mx" onclick="closeMod()">×</button>
    </div>
    <div class="mb" id="mmb"></div>
    <div class="ma">
      <button class="btn bs" onclick="closeMod()">Fermer</button>
      <button class="btn bp" onclick="applyMod()">✅ Appliquer</button>
    </div>
  </div>
</div>

<script>
let P = [], sel = new Set(), curId = null, loadTime = 0;

async function load(forceRefresh) {
  const prodsEl = document.getElementById('prods');
  prodsEl.innerHTML = '<div class="ld"><div class="sp"></div>Chargement...</div>';
  const t0 = performance.now();
  try {
    const url = '/api/products' + (forceRefresh ? '?refresh=true' : '');
    const r = await fetch(url);
    const d = await r.json();
    P = d.products;
    loadTime = Math.round(performance.now() - t0);

    document.getElementById('s1').textContent = d.stats.seo_complete;
    document.getElementById('s2').textContent = d.stats.seo_partial;
    document.getElementById('s3').textContent = d.stats.seo_missing;
    document.getElementById('s4').textContent = d.stats.total;
    document.getElementById('s5').textContent = d.stats.percentage_complete + '%';
    document.getElementById('cache-info').textContent =
      d.stats.total + ' produits chargés en ' + loadTime + 'ms';
    filter();
  } catch (e) {
    prodsEl.innerHTML = '<div class="ld">❌ Erreur de chargement</div>';
  }
}

function filter() {
  const s = document.getElementById('src').value.toLowerCase();
  const f = document.getElementById('flt').value;
  const L = P.filter(p => {
    if (s && !p.title.toLowerCase().includes(s) && !(p.sku || '').toLowerCase().includes(s))
      return false;
    if (f === 'missing') return !p.has_links;
    if (f === 'complete') return p.has_links;
    if (f === 'partial') return p.has_description && !p.has_links;
    return true;
  });
  render(L);
}

function render(L) {
  const el = document.getElementById('prods');
  if (!L.length) { el.innerHTML = '<div class="ld">Aucun produit trouvé</div>'; return; }

  // Render par batch de 30 pour ne pas bloquer le thread principal
  const BATCH = 30;
  const total = L.length;
  let html = '';

  for (let i = 0; i < Math.min(BATCH, total); i++) {
    html += renderCard(L[i]);
  }
  el.innerHTML = html;

  // Lazy render le reste
  if (total > BATCH) {
    let loaded = BATCH;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && loaded < total) {
        const end = Math.min(loaded + BATCH, total);
        let chunk = '';
        for (let i = loaded; i < end; i++) {
          chunk += renderCard(L[i]);
        }
        sentinel.insertAdjacentHTML('beforebegin', chunk);
        loaded = end;
        if (loaded >= total) observer.disconnect();
      }
    }, { rootMargin: '200px' });

    const sentinel = document.createElement('div');
    sentinel.id = 'sentinel';
    sentinel.style.height = '1px';
    el.appendChild(sentinel);
    observer.observe(sentinel);
  }
}

function renderCard(p) {
  const ck = sel.has(p.id) ? 'chk' : '';
  const sc = p.seo_score >= 70 ? 'h' : p.seo_score >= 30 ? 'm' : 'l';
  let cc = 'n', ct = '⚠️ Aucune';
  if (p.collection) {
    cc = p.collection.type === 'model' ? 'f' : 'b';
    ct = (p.collection.type === 'model' ? '✅ ' : '📁 ') + p.collection.title;
  }
  return '<div class="prod">' +
    '<div class="pck ' + ck + '" onclick="tog(' + p.id + ')"></div>' +
    '<img class="pim" src="' + (p.image || '') + '" loading="lazy" onerror="this.style.background=\'#333\';this.onerror=null">' +
    '<div class="pin"><h3>' + esc(p.title.substring(0, 50)) + (p.title.length > 50 ? '...' : '') + '</h3>' +
    '<div class="psku">' + (p.sku || 'N/A') + '</div>' +
    '<div class="pcol ' + cc + '">' + ct + '</div></div>' +
    '<div class="pst">' +
    '<div class="si ' + (p.has_description ? 'sok' : 'sms') + '">' + (p.has_description ? '✅' : '❌') + ' Desc</div>' +
    '<div class="si ' + (p.has_links ? 'sok' : 'sms') + '">' + (p.has_links ? '✅' : '❌') + ' Liens</div></div>' +
    '<div class="psc"><span class="scb ' + sc + '">' + p.seo_score + '%</span></div>' +
    '<div class="pac">' +
    '<button class="ab v" onclick="view(' + p.id + ')">👁️</button>' +
    '<button class="ab a" onclick="applyOne(' + p.id + ')">⚡</button></div></div>';
}

function tog(id) {
  sel.has(id) ? sel.delete(id) : sel.add(id);
  document.getElementById('sc').textContent = sel.size;
  // Update just the checkbox visually instead of re-rendering all
  const cards = document.querySelectorAll('.prod');
  cards.forEach(card => {
    const ckEl = card.querySelector('.pck');
    if (ckEl && ckEl.getAttribute('onclick')?.includes(id)) {
      ckEl.classList.toggle('chk');
    }
  });
}

function esc(t) {
  return (t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function view(id) {
  curId = id;
  document.getElementById('mmb').innerHTML = '<div class="ld"><div class="sp"></div></div>';
  document.getElementById('mod').classList.add('sh');
  try {
    const r = await fetch('/api/product/' + id + '/seo-status');
    const d = await r.json();
    const s = d.seo_status, g = d.generated;

    let h = '<p><b>Produit:</b> ' + esc(d.product.title) + '</p>';
    if (d.collection)
      h += '<p><b>Collection:</b> ' + esc(d.collection.title) + ' (' + d.collection.type + ')</p>';
    h += '<p><b>Score:</b> ' + d.score + '%</p>';
    h += '<hr style="border-color:#333;margin:15px 0">';

    // Meta Title
    h += '<div class="ss"><h4>Meta Title <span class="bg ' +
      (s.meta_title.needs_update ? 'ms' : 'ok') + '">' +
      (s.meta_title.needs_update ? 'À modifier' : 'OK') + '</span></h4>' +
      '<div class="sc">' + (s.meta_title.value ? esc(s.meta_title.value) : 'Aucun') + '</div>' +
      '<div class="sg">' + esc(g.meta_title) + '</div></div>';

    // Meta Desc
    h += '<div class="ss"><h4>Meta Desc <span class="bg ' +
      (s.meta_description.needs_update ? 'ms' : 'ok') + '">' +
      (s.meta_description.needs_update ? 'À modifier' : 'OK') + '</span></h4>' +
      '<div class="sc">' + (s.meta_description.value ? esc(s.meta_description.value) : 'Aucune') + '</div>' +
      '<div class="sg">' + esc(g.meta_description) + '</div></div>';

    // Description
    h += '<div class="ss"><h4>Description <span class="bg ' +
      (s.description.needs_update ? 'ms' : 'ok') + '">' +
      (s.description.needs_update ? 'À modifier' : 'OK') + '</span>' +
      (s.description.has_links ? ' 🔗' : '') + '</h4>' +
      '<div class="sc">' + (s.description.value ? esc(s.description.value) : 'Aucune') + '</div>' +
      '<div class="sg"><pre>' + esc(g.description) + '</pre></div></div>';

    // Checkboxes
    h += '<div class="mfs"><h4>Appliquer:</h4>' +
      '<label><input type="checkbox" id="mft" ' + (s.meta_title.needs_update ? 'checked' : '') + '> Meta Title</label>' +
      '<label><input type="checkbox" id="mfd" ' + (s.meta_description.needs_update ? 'checked' : '') + '> Meta Desc</label>' +
      '<label><input type="checkbox" id="mfb" ' + (s.description.needs_update ? 'checked' : '') + '> Description</label></div>';

    document.getElementById('mmb').innerHTML = h;
    document.getElementById('mt').textContent = d.product.title;
  } catch (e) {
    document.getElementById('mmb').innerHTML = '<div class="ld">❌ Erreur de chargement</div>';
  }
}

function closeMod() {
  document.getElementById('mod').classList.remove('sh');
  curId = null;
}

async function applyMod() {
  if (!curId) return;
  const f = [];
  if (document.getElementById('mft').checked) f.push('meta_title');
  if (document.getElementById('mfd').checked) f.push('meta_description');
  if (document.getElementById('mfb').checked) f.push('description');
  if (!f.length) { toast('Sélectionnez un champ', 'e'); return; }
  closeMod();
  toast('Application en cours...', 's');
  try {
    const r = await fetch('/api/seo/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: curId, fields: f })
    });
    const d = await r.json();
    if (d.success) { toast('✅ Appliqué!', 's'); load(); }
    else toast('❌ Erreur', 'e');
  } catch (e) { toast('❌ Erreur réseau', 'e'); }
}

function getF() {
  const f = [];
  if (document.getElementById('ft').checked) f.push('meta_title');
  if (document.getElementById('fd').checked) f.push('meta_description');
  if (document.getElementById('fb').checked) f.push('description');
  return f;
}

async function applyOne(id) {
  const f = getF();
  if (!f.length) { toast('Cochez un champ', 'e'); return; }
  toast('Application...', 's');
  try {
    const r = await fetch('/api/seo/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: id, fields: f })
    });
    const d = await r.json();
    if (d.success) { toast('✅ OK!', 's'); load(); }
    else toast('❌ Erreur', 'e');
  } catch (e) { toast('❌ Erreur', 'e'); }
}

async function applySel() {
  if (!sel.size) { toast('Sélectionnez des produits', 'e'); return; }
  const f = getF();
  if (!f.length) { toast('Cochez un champ', 'e'); return; }
  batch(Array.from(sel), f);
}

async function applyAll() {
  const f = getF();
  if (!f.length) { toast('Cochez un champ', 'e'); return; }
  if (!confirm('Modifier ' + f.join(', ') + ' pour ' + P.length + ' produits ?')) return;
  batch(P.map(p => p.id), f);
}

async function batch(ids, f) {
  showPB();
  try {
    const r = await fetch('/api/seo/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_ids: ids, fields: f })
    });
    const d = await r.json();
    if (d.error) { toast('❌ ' + d.error, 'e'); hidePB(); return; }
    mon();
  } catch (e) { toast('❌ Erreur', 'e'); hidePB(); }
}

function mon() {
  const iv = setInterval(async () => {
    try {
      const r = await fetch('/api/progress');
      const p = await r.json();
      const pct = p.total > 0 ? (p.current / p.total * 100) : 0;
      document.getElementById('pf').style.width = pct + '%';
      document.getElementById('pc').textContent = p.current + '/' + p.total;
      document.getElementById('px').textContent = p.message;
      if (!p.running) {
        clearInterval(iv);
        hidePB();
        toast(p.message, 's');
        sel.clear();
        document.getElementById('sc').textContent = '0';
        load(true);
      }
    } catch (e) { /* silently retry */ }
  }, 800);
}

function showPB() { document.getElementById('pb').classList.add('sh'); }
function hidePB() { document.getElementById('pb').classList.remove('sh'); }

function toast(m, t) {
  document.querySelectorAll('.tst').forEach(el => el.remove());
  const e = document.createElement('div');
  e.className = 'tst ' + t;
  e.textContent = m;
  document.body.appendChild(e);
  setTimeout(() => e.remove(), 4000);
}

// Debounce search
let searchTimer;
document.getElementById('src').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(filter, 150);
});
document.getElementById('flt').addEventListener('change', filter);

// Fermer modal avec Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeMod();
});

// Initial load
load();
</script>
</body>
</html>'''


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print(f"[V4.2] Shop: {SHOP}")
    print(f"[V4.2] Cache TTL: products={CACHE_TTL_PRODUCTS}s, collections={CACHE_TTL_COLLECTIONS}s")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
