"""
KP SHOES - Plateforme de Gestion Shopify V8
Avec import photos GOAT via curl_cffi
"""

from flask import Flask, jsonify, request
import json, os, time, re, ssl, logging
from urllib.request import Request, urlopen
from urllib.parse import quote
from threading import Thread

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'
SITE_NAME = os.environ.get('SITE_NAME', 'KP SHOES')
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'kpshoes.fr')

task_progress = {'running': False, 'current': 0, 'total': 0, 'message': ''}
_collections_cache = None


def title_to_filename(title):
    """Convertit un titre produit en nom de fichier safe: 'Air Jordan 4 Rétro (2025)' -> 'Air_Jordan_4_Retro_2025'"""
    import unicodedata
    # Enlever les accents : è→e, é→e, à→a, etc.
    fn = unicodedata.normalize('NFD', title)
    fn = ''.join(c for c in fn if unicodedata.category(c) != 'Mn')
    fn = fn.replace(' ', '_')
    fn = re.sub(r'[^\w\-]', '_', fn)
    fn = re.sub(r'_+', '_', fn)
    return fn.strip('_')


def shopify_request(endpoint, method='GET', data=None):
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    headers = {'X-Shopify-Access-Token': ACCESS_TOKEN, 'Content-Type': 'application/json'}
    try:
        req = Request(url, data=json.dumps(data).encode('utf-8') if data else None, headers=headers, method=method)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urlopen(req, context=ctx, timeout=30) as r:
            return True if method == 'DELETE' else json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f"[Shopify Err] {e}")
        return None


def get_collections():
    global _collections_cache
    if _collections_cache: return _collections_cache
    cols = []
    for t in ['custom_collections', 'smart_collections']:
        r = shopify_request(f'{t}.json?limit=250')
        if r and t in r:
            for c in r[t]:
                cols.append({'id': c['id'], 'handle': c['handle'], 'title': c['title']})
    _collections_cache = cols
    return cols


def get_product_metafields(product_id):
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


# ══════════════════════════════════════════════════════════════
# GOAT IMAGES - Intégration directe (Algolia search + web-api)
# ══════════════════════════════════════════════════════════════

GOAT_ALGOLIA_URL = 'https://2fwotdvm2o-dsn.algolia.net/1/indexes/*/queries'
GOAT_ALGOLIA_APP_ID = '2FWOTDVM2O'
GOAT_ALGOLIA_API_KEY = 'ac96de6fef0e02bb95d433d8d5c7038a'
GOAT_PRODUCT_API = 'https://www.goat.com/web-api/v1/product_templates'

_goat_session = None
_goat_session_time = 0
_goat_impersonate_idx = 0
_GOAT_PROFILES = ["chrome", "chrome110", "chrome116", "safari", "safari_ios"]

def _get_goat_session(force_new=False, rotate_profile=False):
    """Crée/réutilise une session curl_cffi. Renouvelle toutes les 60s ou si force_new."""
    global _goat_session, _goat_session_time, _goat_impersonate_idx
    import time
    now = time.time()
    if _goat_session is not None and not force_new and not rotate_profile and (now - _goat_session_time) < 60:
        return _goat_session
    try:
        from curl_cffi.requests import Session
        if _goat_session:
            try: _goat_session.close()
            except: pass
        if rotate_profile:
            _goat_impersonate_idx = (_goat_impersonate_idx + 1) % len(_GOAT_PROFILES)
        profile = _GOAT_PROFILES[_goat_impersonate_idx]
        _goat_session = Session(impersonate=profile)
        _goat_session_time = now
        log.info(f"[GOAT] New curl_cffi session created (profile={profile})")
    except ImportError:
        log.warning("[GOAT] curl_cffi not available, using subprocess curl")
        _goat_session = None
    return _goat_session

def _goat_get(url):
    """GET avec retry : tente plusieurs profils TLS si Cloudflare bloque."""
    import time
    for attempt in range(4):
        sess = _get_goat_session(force_new=(attempt > 0), rotate_profile=(attempt > 1))
        if sess:
            try:
                if attempt > 0:
                    time.sleep(1 + attempt)  # Délai croissant entre retries
                r = sess.get(url, timeout=20, headers={
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
                    'Referer': 'https://www.goat.com/',
                })
                if r.status_code == 200:
                    # Vérifier que c'est du vrai JSON, pas un Cloudflare block
                    text = r.text or ''
                    if text.strip().startswith('{') or text.strip().startswith('['):
                        log.info(f"[GOAT] GET OK on attempt {attempt+1}: {url[:60]}...")
                        return text
                    elif '1020' in text[:200]:
                        log.warning(f"[GOAT] GET attempt {attempt+1}: Cloudflare 1020 in body")
                        continue
                    return text
                log.warning(f"[GOAT] GET attempt {attempt+1} {url[:60]}... -> {r.status_code}")
                if r.status_code in (403, 503) or '1020' in (r.text or '')[:200]:
                    continue  # Retry with rotated profile
                return r.text if r.text else None
            except Exception as e:
                log.warning(f"[GOAT] curl_cffi GET attempt {attempt+1} failed: {e}")
                continue
    # Fallback subprocess
    import subprocess
    try:
        result = subprocess.run(
            ["curl", "-s", "-m", "20", url,
             "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"],
            capture_output=True, text=True, timeout=25)
        if result.returncode == 0 and result.stdout: return result.stdout
    except Exception as e:
        log.warning(f"[GOAT] subprocess curl failed: {e}")
    return None

def _goat_post(url, json_data):
    sess = _get_goat_session()
    if sess:
        try:
            r = sess.post(url, json=json_data, timeout=20)
            if r.status_code == 200: return r.text
            log.warning(f"[GOAT] POST {url[:60]}... -> {r.status_code}")
        except Exception as e:
            log.warning(f"[GOAT] curl_cffi POST failed: {e}")
    import subprocess
    try:
        body = json.dumps(json_data)
        result = subprocess.run(
            ["curl", "-s", "-m", "20", url, "-X", "POST",
             "-H", "Content-Type: application/json",
             "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
             "-d", body],
            capture_output=True, text=True, timeout=25)
        if result.returncode == 0 and result.stdout: return result.stdout
    except Exception as e:
        log.warning(f"[GOAT] subprocess curl POST failed: {e}")
    return None

def goat_search(sku):
    """Recherche un produit GOAT via Algolia. Retourne slug + image principale."""
    url = f"{GOAT_ALGOLIA_URL}?x-algolia-application-id={GOAT_ALGOLIA_APP_ID}&x-algolia-api-key={GOAT_ALGOLIA_API_KEY}"
    payload = {"requests": [{"indexName": "product_variants_v2", "params": f"distinct=true&maxValuesPerFacet=1&page=0&query={sku}"}]}
    raw = _goat_post(url, payload)
    if not raw: return None
    try: data = json.loads(raw)
    except: return None
    hits = data.get('results', [{}])[0].get('hits', [])
    if not hits: return None
    sku_clean = sku.replace('-', ' ').replace('  ', ' ').upper()
    best = None
    for h in hits:
        h_sku = (h.get('sku', '') or '').upper()
        if h_sku == sku_clean or h_sku == sku.upper():
            best = h; break
    if not best: best = hits[0]
    return {
        'name': best.get('name', ''),
        'sku': best.get('sku', sku),
        'slug': best.get('slug', ''),
        'brand': best.get('brand_name', ''),
        'main_picture_url': best.get('original_picture_url', '') or best.get('main_picture_url', ''),
    }

def goat_get_product_images(slug):
    """Récupère TOUTES les images d'un produit via web-api. Gère les produits à 1 seule image."""
    raw = _goat_get(f"{GOAT_PRODUCT_API}/{slug}")
    if not raw: return []
    try: data = json.loads(raw)
    except:
        log.warning(f"[GOAT] API response not JSON for {slug} (likely Cloudflare 1020)")
        return []
    
    # 1. Collecter les images galerie (multi-angles: _01, _02, etc.) — qualité classique telle quelle
    gallery_images = []
    gallery_fields = [
        'productTemplateExternalPictures',
        'externalPictures',
        'galleryPictures',
        'pictures',
        'additionalPictures',
        'productImages',
    ]
    for field in gallery_fields:
        pics = data.get(field, [])
        if not isinstance(pics, list): continue
        for pic in pics:
            if isinstance(pic, dict):
                # IMPORTANT: mainPictureUrl = qualité classique (medium), les autres champs = original (trop gros)
                url = pic.get('mainPictureUrl', '')
            elif isinstance(pic, str):
                url = pic
            else:
                continue
            if url and url not in gallery_images:
                gallery_images.append(url)
    
    # 2. Si la galerie a des images → utiliser UNIQUEMENT la galerie (pas la _00)
    if gallery_images:
        log.info(f"[GOAT] Found {len(gallery_images)} gallery images for {slug} (skipping main _00)")
        return gallery_images
    
    # 3. Sinon fallback sur l'image principale seule (sera redimensionnée à l'apply)
    # Préférer mainPictureUrl (750px, classique) plutôt que pictureUrl (1000px, optimale)
    main_url = data.get('mainPictureUrl', '') or data.get('pictureUrl', '') or data.get('originalPictureUrl', '')
    if main_url:
        log.info(f"[GOAT] Single image product for {slug}, will need resize. URL: {main_url[:80]}...")
        return [main_url]
    
    log.info(f"[GOAT] No images found for {slug}")
    return []


def _discover_goat_image_angles(base_url):
    """Découvre les images d'angles supplémentaires en testant les URLs numérotées sur le CDN GOAT.
    Pattern: https://image.goat.com/.../1118288_00.png.png -> _01, _02, _03, etc.
    """
    extra_images = []
    
    # Détecter le pattern /{digits}_00.ext dans l'URL
    match = re.search(r'(/\d+_)(\d{2})(\.png\.png|\.jpg\.jpg|\.png|\.jpg|\.jpeg|\.webp)(\?.*)?$', base_url)
    if not match:
        log.info(f"[GOAT] No angle pattern in URL: ...{base_url[-60:]}")
        return extra_images
    
    prefix = base_url[:match.start() + len(match.group(1))]  # Tout jusqu'à "1118288_"
    current_angle = int(match.group(2))  # 00
    ext = match.group(3)  # .png.png
    query = match.group(4) or ''
    
    log.info(f"[GOAT] Angle pattern found: current=_{current_angle:02d}, testing others...")
    
    # Tester les angles 00 à 08 (GOAT a rarement plus de 8 vues)
    consecutive_misses = 0
    for i in range(0, 9):
        if i == current_angle:
            consecutive_misses = 0
            continue
        
        test_url = f"{prefix}{i:02d}{ext}{query}"
        
        if _goat_url_exists(test_url):
            extra_images.append(test_url)
            consecutive_misses = 0
            log.info(f"[GOAT] ✓ Found angle _{i:02d}")
        else:
            consecutive_misses += 1
            if consecutive_misses >= 2 and i > current_angle:
                break  # 2 ratés d'affilée après l'angle courant = on arrête
    
    log.info(f"[GOAT] Discovered {len(extra_images)} additional angles")
    return extra_images


def _goat_url_exists(url):
    """Vérifie si une URL d'image GOAT existe via GET request (HEAD souvent bloqué par CDN)."""
    import subprocess
    # Méthode 1: GET request avec range header (télécharge seulement 1 byte)
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-m", "8",
             "-r", "0-0", url,
             "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
             "-H", "Accept: image/webp,image/apng,image/*,*/*;q=0.8",
             "-H", "Referer: https://www.goat.com/"],
            capture_output=True, text=True, timeout=12)
        if result.returncode == 0:
            code = result.stdout.strip()
            log.debug(f"[GOAT] URL check {url[-40:]}: HTTP {code}")
            return code in ('200', '206')  # 206 = Partial Content (range request OK)
    except Exception as e:
        log.debug(f"[GOAT] curl range failed: {e}")
    
    # Méthode 2: GET simple avec curl_cffi session
    sess = _get_goat_session()
    if sess:
        try:
            r = sess.get(url, timeout=8, headers={
                'Range': 'bytes=0-0',
                'Referer': 'https://www.goat.com/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
            })
            log.debug(f"[GOAT] Session check {url[-40:]}: HTTP {r.status_code}")
            return r.status_code in (200, 206)
        except Exception as e:
            log.debug(f"[GOAT] Session check failed: {e}")
    
    return False


def get_goat_images(sku):
    """Récupère les images GOAT pour un SKU. Gère les SKU multiples (ex: 0951301/0951303).
    Stratégie: Algolia pour trouver le produit + découverte d'angles sur le CDN.
    """
    try:
        sku = re.sub(r':\d+$', '', sku.strip())
        skus = [s.strip() for s in sku.replace('/', ' ').replace('|', ' ').split() if s.strip()]
        if not skus: skus = [sku]
        
        if len(skus) == 1:
            product = goat_search(skus[0])
            if not product or not product.get('slug'): return None
            
            # 1. Essayer l'API produit (peut être bloquée par Cloudflare)
            images = goat_get_product_images(product['slug'])
            
            # 2. Si l'API échoue/retourne peu, utiliser l'image Algolia + découverte d'angles
            if len(images) <= 1:
                main_url = images[0] if images else product.get('main_picture_url', '')
                if main_url:
                    if not images:
                        images = [main_url]
                    # Découvrir les angles supplémentaires sur le CDN
                    extra = _discover_goat_image_angles(main_url)
                    for url in extra:
                        if url not in images:
                            images.append(url)
                    log.info(f"[GOAT] Total after angle discovery: {len(images)} images")
            
            if not images: return None
            return {'name': product.get('name', ''), 'sku': product.get('sku', sku), 'images': images, 'multi': False}
        
        results = []
        for s in skus:
            try:
                product = goat_search(s)
                if product and product.get('slug'):
                    images = goat_get_product_images(product['slug'])
                    # Même logique de fallback + angle discovery
                    if len(images) <= 1:
                        main_url = images[0] if images else product.get('main_picture_url', '')
                        if main_url:
                            if not images:
                                images = [main_url]
                            extra = _discover_goat_image_angles(main_url)
                            for url in extra:
                                if url not in images:
                                    images.append(url)
                    results.append({'name': product.get('name', ''), 'sku': s, 'images': images})
                else:
                    results.append({'name': '', 'sku': s, 'images': []})
            except Exception as e:
                log.error(f"[GOAT] Error for SKU {s}: {e}")
                results.append({'name': '', 'sku': s, 'images': []})
        return {'multi': True, 'results': results}
    except Exception as e:
        log.error(f"[GOAT] Error: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# Collections & SEO
# ══════════════════════════════════════════════════════════════

MODEL_COLLECTIONS = {
    'jordan-4': ['jordan 4'], 'jordan-1-high': ['jordan 1 high'], 'jordan-1-low': ['jordan 1 low'],
    'jordan-1-mid': ['jordan 1 mid'], 'nike-dunk': ['dunk'], 'air-force-1': ['air force 1'],
    'nike-p-6000': ['air max'], 'nike-vomero': ['vomero'], 'nike-sacail': ['sacai'],
    'adidas-samba': ['samba'], 'adidas-campus': ['campus'], 'adidas-gazelle': ['gazelle'],
    'adidas-spezial': ['spezial'], 'adidas-forum': ['forum'], 'yeezy-slide': ['yeezy slide'],
    'yeezy-351': ['yeezy 350', '350 v2'], 'yeezy-350': ['yeezy 700', '700'],
    'new-balance-550': ['550'], 'new-balance-530': ['530'], 'new-balance-2002r': ['2002r'],
    'new-balance-9060': ['9060'], 'asics-gel-1130': ['gel-1130', 'gel 1130'],
    'asics-gel-kayano': ['kayano'], 'asics-gel-nyc': ['gel-nyc', 'gel nyc'],
    'ugg-tasman': ['tasman'], 'ugg-tazz': ['tazz'], 'ugg-ultra-mini': ['ultra mini'],
    'travis-scott': ['travis scott'], 'off-white': ['off-white'], 'supreme': ['supreme'],
    'tous-nos-vetements': ['essentials', 'hoodie', 'sweatpant', 'sweatshort', 'tee ', 't-shirt'],
}

BRAND_COLLECTIONS = {
    'jordan-1': ['jordan'], 'nike-1': ['nike', 'nocta', 'blazer'], 'adidas-1': ['adidas'],
    'yeezy-1': ['yeezy', 'foam runner'], 'new-balance-1': ['new balance'], 'asics-1': ['asics'],
    'ugg-1': ['ugg'], 'puma-1': ['puma'], 'crocs': ['crocs'], 'birkenstock-1': ['birkenstock'],
    'converse': ['converse'], 'salomon': ['salomon'], 'timberland': ['timberland'],
}

EXCLUDED = ['tout-nos-modeles', 'best-seller', 'moins-de-150', 'livraison-48h', 'pour-enfants', 'sport', 'autre-marques']


def find_collection(title, collections):
    if not title or not collections: return None
    t = title.lower()
    available = [c['handle'] for c in collections if c['handle'] not in EXCLUDED]
    for handle, keywords in MODEL_COLLECTIONS.items():
        if handle in available:
            for kw in keywords:
                if kw in t:
                    col = next((c for c in collections if c['handle'] == handle), None)
                    if col: return {'handle': col['handle'], 'title': col['title'], 'url': f"https://{SITE_DOMAIN}/collections/{col['handle']}", 'type': 'model'}
    for handle, keywords in BRAND_COLLECTIONS.items():
        if handle in available:
            for kw in keywords:
                if kw in t:
                    col = next((c for c in collections if c['handle'] == handle), None)
                    if col: return {'handle': col['handle'], 'title': col['title'], 'url': f"https://{SITE_DOMAIN}/collections/{col['handle']}", 'type': 'brand'}
    return None


def extract_brand(title):
    t = title.lower()
    if 'fear of god' in t or 'essentials' in t: return 'Fear of God'
    if 'jordan' in t: return 'Jordan'
    if 'yeezy' in t: return 'Yeezy'
    if 'travis scott' in t: return 'Nike x Travis Scott'
    if 'off-white' in t.replace(' ', '-'): return 'Nike x Off-White'
    if 'dior' in t: return 'Dior'
    if 'mschf' in t: return 'MSCHF'
    brands = [
        ('Nike', ['nike', 'dunk', 'air force', 'air max', 'nocta', 'blazer', 'vomero', 'p-6000']),
        ('Adidas', ['adidas', 'samba', 'campus', 'gazelle', 'spezial', 'forum', 'sl 72', 'adilette']),
        ('New Balance', ['new balance']),
        ('Asics', ['asics', 'gel-']),
        ('UGG', ['ugg', 'tasman', 'tazz']),
        ('Puma', ['puma']),
        ('Crocs', ['crocs']),
        ('Birkenstock', ['birkenstock']),
        ('Salomon', ['salomon']),
        ('Timberland', ['timberland']),
        ('Converse', ['converse', 'chuck taylor']),
        ('Vans', ['vans', 'old skool', 'sk8-hi']),
        ('Reebok', ['reebok']),
        ('On Running', ['on cloud', 'cloudmonster', 'cloudnova']),
    ]
    for brand, kws in brands:
        for kw in kws:
            if kw in t: return brand
    return 'Sneakers'


def analyze_seo(product, meta_title, meta_description):
    body_html = product.get('body_html', '') or ''
    results = {'score': 0, 'max_score': 100, 'checks': []}
    
    check1 = {'name': 'Meta Title', 'points': 0, 'max': 20, 'status': 'error', 'message': 'Absent'}
    if meta_title:
        if SITE_NAME in meta_title and len(meta_title) <= 60:
            check1 = {'name': 'Meta Title', 'points': 20, 'max': 20, 'status': 'success', 'message': 'OK (' + str(len(meta_title)) + ' car.)'}
        elif len(meta_title) > 60:
            check1 = {'name': 'Meta Title', 'points': 8, 'max': 20, 'status': 'warning', 'message': 'Trop long'}
        else:
            check1 = {'name': 'Meta Title', 'points': 12, 'max': 20, 'status': 'warning', 'message': 'Manque KP SHOES'}
    results['checks'].append(check1)
    results['score'] += check1['points']
    
    check2 = {'name': 'Meta Description', 'points': 0, 'max': 20, 'status': 'error', 'message': 'Absente'}
    if meta_description:
        has_auth = '100%' in meta_description or 'authentique' in meta_description.lower()
        good_len = 100 <= len(meta_description) <= 155
        if has_auth and good_len:
            check2 = {'name': 'Meta Description', 'points': 20, 'max': 20, 'status': 'success', 'message': 'OK'}
        elif good_len:
            check2 = {'name': 'Meta Description', 'points': 12, 'max': 20, 'status': 'warning', 'message': 'Manque authenticite'}
        else:
            check2 = {'name': 'Meta Description', 'points': 8, 'max': 20, 'status': 'warning', 'message': 'Longueur incorrecte'}
    results['checks'].append(check2)
    results['score'] += check2['points']
    
    check3 = {'name': 'Description + Lien', 'points': 0, 'max': 30, 'status': 'error', 'message': 'Manquante'}
    has_desc = len(body_html) > 100
    has_link = 'kpshoes.fr/collections/' in body_html.lower()
    if has_desc and has_link:
        check3 = {'name': 'Description + Lien', 'points': 30, 'max': 30, 'status': 'success', 'message': 'Complete avec lien'}
    elif has_desc:
        check3 = {'name': 'Description + Lien', 'points': 12, 'max': 30, 'status': 'warning', 'message': 'Sans lien'}
    results['checks'].append(check3)
    results['score'] += check3['points']
    
    check4 = {'name': 'SKU', 'points': 0, 'max': 10, 'status': 'error', 'message': 'Manquant'}
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    if sku:
        check4 = {'name': 'SKU', 'points': 10, 'max': 10, 'status': 'success', 'message': sku}
    results['checks'].append(check4)
    results['score'] += check4['points']
    
    # Check Images : alt text + filename
    images = product.get('images', [])
    title = product.get('title', '')
    title_for_filename = title_to_filename(title)
    check5 = {'name': 'Images SEO', 'points': 0, 'max': 20, 'status': 'error', 'message': 'Aucune image'}
    if images:
        all_alt_ok = True
        all_filename_ok = True
        bad_alt = 0
        bad_filename = 0
        for img in images:
            alt = img.get('alt', '') or ''
            src = img.get('src', '') or ''
            filename = src.split('/')[-1].split('?')[0] if src else ''
            if alt != title:
                all_alt_ok = False
                bad_alt += 1
            if title_for_filename not in filename:
                all_filename_ok = False
                bad_filename += 1
        
        if all_alt_ok and all_filename_ok:
            check5 = {'name': 'Images SEO', 'points': 20, 'max': 20, 'status': 'success', 'message': f'{len(images)} images OK'}
        elif all_alt_ok:
            check5 = {'name': 'Images SEO', 'points': 10, 'max': 20, 'status': 'warning', 'message': f'Alt OK, {bad_filename} noms a corriger'}
        elif all_filename_ok:
            check5 = {'name': 'Images SEO', 'points': 10, 'max': 20, 'status': 'warning', 'message': f'Noms OK, {bad_alt} alt a corriger'}
        else:
            check5 = {'name': 'Images SEO', 'points': 0, 'max': 20, 'status': 'error', 'message': f'{bad_alt} alt + {bad_filename} noms a corriger'}
    results['checks'].append(check5)
    results['score'] += check5['points']
    
    if results['score'] >= 85: results['status'] = 'excellent'
    elif results['score'] >= 70: results['status'] = 'good'
    elif results['score'] >= 50: results['status'] = 'warning'
    else: results['status'] = 'poor'
    
    return results


MODEL_DESCRIPTIONS = {
    'jordan 4': "Conçue par Tinker Hatfield en 1989, la Air Jordan 4 allie mesh respirant, œillets en TPU et amorti Air visible au talon. Portée par MJ pour son premier titre de meilleur marqueur NBA, elle reste l'une des silhouettes les plus convoitées.",
    'jordan 3': "Première collaboration entre Michael Jordan et Tinker Hatfield en 1988, la Air Jordan 3 a introduit l'elephant print iconique et le logo Jumpman. Son amorti Air visible au talon et sa tige en cuir en font un classique intemporel.",
    'jordan 2': "Sortie en 1986, la Air Jordan 2 se distingue par son design épuré inspiré de la mode italienne, sans logo Swoosh. Son upper en cuir premium lui confère une allure luxueuse unique dans la lignée Jordan.",
    'jordan 5': "Dessinée par Tinker Hatfield en 1990, la Air Jordan 5 s'inspire des avions de chasse P-51 Mustang avec sa semelle translucide, ses empiècements en mesh et ses dents de requin sur la midsole. Un design agressif devenu culte.",
    'jordan 6': "Portée par MJ lors de son premier titre NBA en 1991 contre les Lakers, la Air Jordan 6 se reconnaît à son spoiler arrière, ses trous de ventilation et son système de laçage innovant. Une sneaker chargée d'histoire.",
    'jordan 7': "Chaussure des JO de Barcelone 1992 et du Dream Team, la Air Jordan 7 arbore un design coloré inspiré par l'art afro-pop. Première Jordan sans Nike Air visible, elle mise tout sur le style et la performance.",
    'jordan 11': "Chef-d'œuvre de Tinker Hatfield sorti en 1995, la Air Jordan 11 révolutionne le design sneaker avec son upper en cuir verni et sa semelle en fibre de carbone translucide. MJ la portait lors de son retour triomphal en NBA.",
    'jordan 12': "Inspirée du drapeau japonais et des chaussures habillées, la Air Jordan 12 accompagna MJ lors de la saison 72-10 en 1996-97 et du fameux Flu Game. Son cuir premium et ses coutures distinctives en font un modèle élégant.",
    'jordan 13': "Inspirée de la panthère noire, la Air Jordan 13 dispose d'un œil de chat holographique, d'une patte de panthère en semelle et de la technologie Zoom Air. La dernière Jordan portée par MJ en saison régulière.",
    'jordan 1 high': "Créée par Peter Moore en 1985, la Air Jordan 1 High est la sneaker qui a tout commencé. Bannie par la NBA pour infraction au code couleur, elle a généré 5 000 dollars d'amende par match, propulsant Nike et MJ dans la légende.",
    'jordan 1 low': "Version basse de la légendaire Air Jordan 1, la Low conserve le design iconique de 1985 avec un col plus bas pour un confort quotidien. Même cuir premium, même semelle Air, avec un profil plus discret et polyvalent.",
    'jordan 1 mid': "La Air Jordan 1 Mid offre le parfait équilibre entre la High et la Low avec un col intermédiaire. Sortie dans des centaines de coloris, elle reste l'entrée idéale dans l'univers Jordan.",
    'dunk low': "Créée en 1985 pour le programme basketball Be True To Your School, la Nike Dunk Low est l'une des silhouettes les plus populaires au monde. Sa tige en cuir, sa semelle cupsole et ses déclinaisons infinies en font un pilier du streetwear.",
    'dunk high': "La Nike Dunk High conserve le design original de 1985 avec sa tige montante et son col rembourré. Du basketball universitaire au skateboarding, elle a traversé les époques sans perdre son attrait.",
    'dunk': "Créée en 1985 pour le basketball universitaire, la Nike Dunk est devenue une icône grâce à son design épuré, ses matériaux premium et ses innombrables collaborations.",
    'air force 1': "Première sneaker à intégrer la technologie Air en 1982, la Nike Air Force 1 dessinée par Bruce Kilgore est le modèle le plus vendu de Nike. Son cuir premium, sa semelle Air et sa silhouette épaisse en font un classique absolu.",
    'air max 1': "Conçue par Tinker Hatfield en 1987 après une visite au Centre Pompidou, la Air Max 1 a révélé pour la première fois la bulle Air au monde. Son design et son window visible ont changé l'industrie du sneaker.",
    'air max 90': "Baptisée Air Max III en 1990, la Air Max 90 de Tinker Hatfield se distingue par ses couches superposées de mesh et daim, et son unité Air visible imposante. Un pilier de la culture urbaine.",
    'air max 95': "Conçue par Sergio Lozano en 1995, la Air Max 95 s'inspire de l'anatomie humaine : la semelle est la colonne vertébrale, les couches les muscles, le mesh la peau. Première Nike avec Air avant-pied et talon.",
    'air max 97': "Dessinée par Christian Tresser en 1997, la Air Max 97 s'inspire des trains Shinkansen japonais. Première sneaker avec une unité Air pleine longueur, ses lignes fluides et réfléchissantes sont devenues iconiques.",
    'air max plus': "Née en 1998, la Air Max Plus TN de Sean McDowell s'inspire des couchers de soleil de Floride. Ses lignes ondulées et son système Tuned Air en ont fait un phénomène mondial, particulièrement culte en France.",
    'air max dn': "La Nike Air Max Dn représente la nouvelle génération Air avec son système Dynamic Air composé de quatre unités Air Tube réactives. Design futuriste et amorti révolutionnaire.",
    'air max': "La gamme Air Max de Nike révolutionne le confort depuis 1987 avec sa bulle d'air visible, alliant innovation technologique et design audacieux, génération après génération.",
    'vomero': "La Nike Vomero 5, modèle running de 2000, fait son retour en streetwear. Ses superpositions cuir/mesh, sa technologie Zoom Air et son look chunky rétro-technique séduisent les amateurs de dad shoes.",
    'p-6000': "La Nike P-6000, inspirée des Pegasus du début des années 2000, combine cuir, mesh et détails réfléchissants dans une silhouette chunky. Sa technologie Air Zoom au talon assure un confort optimal.",
    'blazer': "Née sur les terrains de basket en 1973, la Nike Blazer est la première basketball Nike. Son upper en cuir, son Swoosh oversize et sa semelle vulcanisée en font une icône du style décontracté.",
    'samba': "Née en 1950 pour le football sur terrain gelé, l'Adidas Samba est l'une des chaussures les plus vendues de l'histoire. Son upper en cuir, sa semelle en gomme et son toe cap en T sont reconnaissables entre mille.",
    'campus': "Apparue dans les années 80, l'Adidas Campus se distingue par son upper en daim premium et ses trois bandes contrastées. Adoptée par le hip-hop new-yorkais puis le skate, elle incarne le style universitaire.",
    'gazelle': "Créée en 1966 comme chaussure d'entraînement polyvalente, l'Adidas Gazelle a conquis les terrains de foot, les scènes musicales et les rues. Son daim et son profil épuré en font un classique intemporel.",
    'spezial': "L'Adidas Spezial, née dans les années 70 pour le handball, incarne l'esprit terrace culture britannique. Son daim, sa semelle en gomme translucide et sa silhouette basse symbolisent le style casual européen.",
    'forum': "Sortie en 1984, l'Adidas Forum était la basketball la plus chère de l'époque. Son strap à boucle, son upper en cuir et sa silhouette imposante en ont fait un favori du hip-hop et du streetwear.",
    'sl 72': "Créée pour les JO de Munich en 1972, l'Adidas SL 72 était la compétition la plus légère de son époque. Son design running vintage en nylon et daim incarne le style sportif rétro.",
    'adilette': "Née en 1972, l'Adidas Adilette est la claquette la plus iconique de l'histoire. Conçue pour les vestiaires sportifs, son bandeau à trois bandes en a fait un accessoire de mode incontournable.",
    'yeezy slide': "La Yeezy Slide, conçue par Kanye West, est une sandale monobloc en mousse EVA injectée. Son design minimaliste, son confort exceptionnel et sa rareté en ont fait l'un des slides les plus désirées.",
    'yeezy 350': "La Yeezy Boost 350 V2, fruit de la collaboration Kanye West x Adidas, a révolutionné le marché sneaker en 2016. Son upper Primeknit, son boost pleine longueur et sa bande SPLY-350 sont reconnaissables.",
    'yeezy 700': "La Yeezy 700 Wave Runner, sortie en 2017, a relancé la tendance chunky. Ses couches de daim, mesh et cuir avec un amorti Boost encapsulé en font une pièce aussi confortable que visuellement audacieuse.",
    'foam runner': "La Yeezy Foam Runner est en mousse EVA et algues récoltées, dans une forme futuriste moulée d'une seule pièce. Son design organique perforé est devenu un phénomène culturel.",
    'new balance 550': "Ressortie des archives en 2020, la New Balance 550 de 1989 est une basketball au cuir premium et logo N en relief. Propulsée par la collaboration Aimé Leon Dore, elle incarne le revival vintage.",
    'new balance 530': "La New Balance 530, modèle running des années 90, séduit par son design chunky avec technologie ABZORB et tige en mesh/synthétique. Son esthétique Y2K et son confort en font une silhouette très demandée.",
    'new balance 2002r': "La New Balance 2002R combine les technologies N-ERGY et ABZORB SBS pour un confort premium. Son upper en daim et mesh avec silhouette arrondie est devenue un favori du streetwear contemporain.",
    'new balance 9060': "Sortie en 2022, la New Balance 9060 fusionne des éléments de la 990, 860 et 2002R. Ses lignes exagérées, ses superpositions daim/mesh et son amorti FuelCell en font un modèle d'avant-garde.",
    'new balance 1906': "La New Balance 1906R revisite un runner des années 2000 avec les technologies N-ERGY et ABZORB DTS. Son design rétro-futuriste en mesh et empiècements synthétiques plaît aux amateurs de silhouettes techniques.",
    'new balance 990': "Sortie en 1982, la New Balance 990 fut la première running à 100 dollars. Fabriquée aux USA, elle est devenue un symbole de qualité premium portée aussi bien par Steve Jobs que par des présidents américains.",
    'gel-1130': "Sortie en 2008, l'Asics Gel-1130 a resurgi en streetwear grâce à sa silhouette technique Y2K. Sa technologie Gel au talon, son upper en mesh/synthétique et son look rétro-technique sont irrésistibles.",
    'gel-kayano 14': "L'Asics Gel-Kayano 14, sortie en 2008, impressionne par son design ultra-technique avec gel visible et technologie IGS. Le modèle le plus prisé des amateurs de gorpcore et de silhouettes techniques.",
    'gel-kayano': "Lancée en 1993 par Toshikazu Kayano, l'Asics Gel-Kayano est la référence des running stabilisantes. Sa technologie Gel et son design technique en font une icône du running devenue pièce streetwear.",
    'gel-nyc': "Sortie en 2023, l'Asics Gel-NYC fusionne le Gel-Nimbus 3 et le MC Plus V. Son design hybride avec gel apparent, daim et mesh en fait l'une des sorties les plus remarquées de la marque japonaise.",
    'tasman': "La UGG Tasman combine la peau de mouton iconique avec un design slip-on inspiré du mocassin. Sa doublure en laine mérinos de 17mm, sa semelle Treadlite et ses coutures tressées offrent un confort exceptionnel.",
    'tazz': "La UGG Tazz revisite le classique Tasman avec une semelle plateforme en EVA qui ajoute 3cm de hauteur. Même confort en peau de mouton, même facilité d'enfilage, avec un twist contemporain.",
    'ultra mini': "La UGG Ultra Mini est la version compacte du classique boot UGG. Sa tige ultra-courte, sa doublure en peau de mouton recyclée et sa semelle Treadlite légère sont parfaites pour un style décontracté.",
    'crocs': "Inventées en 2002 avec le matériau breveté Croslite, les Crocs offrent une légèreté et un confort uniques. Des blocs opératoires aux podiums de mode, elles sont un phénomène mondial grâce aux Jibbitz personnalisables.",
    'birkenstock': "Fabriquées en Allemagne depuis 1774, les Birkenstock sont célèbres pour leur semelle anatomique en liège et latex naturel. Un confort orthopédique devenu symbole de style normcore.",
    'salomon': "Marque française d'Annecy depuis 1947, les Salomon ont conquis le streetwear avec la XT-6 et l'ACS Pro. Technologie Contagrip, design technique et résistance aux éléments.",
    'converse': "Les Converse Chuck Taylor, créées en 1917, sont les sneakers les plus vendues de tous les temps. Toile de coton, semelle vulcanisée et patch étoile All-Star : un symbole universel de la culture jeune.",
    'vans': "Nées en 1966 à Anaheim, les Vans sont indissociables de la culture skate. Leur semelle waffle, leur construction robuste et leur style décontracté incarnent l'esprit créatif de la côte ouest.",
    'timberland': "Les Timberland 6-Inch, surnommées Timbs, sont un symbole du hip-hop et de la culture urbaine depuis les années 90. Cuir nubuck imperméable, semelle anti-fatigue et durabilité légendaire.",
    'travis scott': "Les collaborations Travis Scott x Nike, lancées en 2019, se distinguent par leur Swoosh inversé, leurs coloris terreux et leurs détails cachés. Des pièces de collection qui prennent de la valeur.",
    'off-white': "Les collaborations Off-White x Nike de Virgil Abloh ont redéfini le concept de sneaker en 2017 avec The Ten. Esthétique déconstructiviste, zip-ties et inscriptions entre guillemets : un mouvement.",
    'bermuda': "L'Adidas Bermuda, modèle terrace des années 70, se distingue par son daim premium, sa semelle en gomme et son profil épuré. Symbole de la culture casual britannique et du style décontracté européen.",
    'superstar': "L'Adidas Superstar, née en 1969 sur les terrains de basketball, est devenue un pilier du hip-hop grâce à Run-DMC. Son shell toe en caoutchouc et ses trois bandes latérales en font l'une des sneakers les plus reconnaissables au monde.",
    'stan smith': "L'Adidas Stan Smith, lancée en 1971, est la sneaker minimaliste par excellence. Son cuir blanc épuré, son logo vert et sa silhouette intemporelle en ont fait le modèle le plus vendu d'Adidas et un symbole du style clean.",
    'nocta glide': "La Nike NOCTA Glide, fruit de la collaboration entre Nike et Drake (NOCTA), marie une base en mesh technique avec des overlays en texture carbone. Un design futuriste qui reflète l'esthétique premium de la ligne NOCTA.",
    'nocta': "La ligne NOCTA, collaboration entre Nike et Drake, propose des pièces premium alliant performance sportive et style urbain nocturne. Un design distinctif qui repousse les limites du streetwear.",
    'ae 1': "L'Adidas AE 1, signature shoe d'Anthony Edwards, est la chaussure de basketball de nouvelle génération. Son design audacieux et sa technologie Lightstrike Pro offrent performance et style sur et en dehors du terrain.",
    'yeezy 500': "La Yeezy 500, avec son design inspiré des dad shoes et sa semelle épaisse adiPRENE+, offre un look chunky rétro avec des empiècements en daim, mesh et cuir de vache. Un modèle phare de la gamme Yeezy.",
    'sb dunk low': "La Nike SB Dunk Low adapte le classique de 1985 aux besoins du skateboarding avec un col rembourré Zoom Air et une languette épaisse. Ses collaborations légendaires en ont fait un graal des collectionneurs.",
    'sb dunk high': "La Nike SB Dunk High combine l'ADN basketball de 1985 avec les exigences du skate : col rembourré, semelle Zoom Air et grip optimisé. Un modèle culte de la culture skateboard.",
    'bad bunny': "Les collaborations Bad Bunny x Adidas allient l'univers créatif du superstar portoricain avec le savoir-faire sportif d'Adidas. Des pièces audacieuses aux détails uniques qui reflètent l'esthétique avant-gardiste de l'artiste.",
    'pharrell': "Les collaborations Pharrell Williams x Adidas repoussent les limites du design avec des silhouettes innovantes et des coloris audacieux. L'expression de la vision créative sans frontières du producteur et entrepreneur.",
    # ── NIKE (modèles additionnels) ──
    'shox': "La Nike Shox, lancée en 2000, a révolutionné l'amorti avec ses colonnes mécaniques en mousse au talon. Son design futuriste et son système de ressort visible en ont fait un symbole du Y2K et de l'innovation Nike.",
    'kobe 4': "La Nike Kobe 4 Protro, signature shoe de Kobe Bryant sortie en 2009, a inauguré l'ère des chaussures de basketball basses. Son upper léger et son profil bas ont changé le jeu pour toujours.",
    'kobe 5': "La Nike Kobe 5, sortie en 2009, poursuit la révolution low-top de Kobe Bryant avec une tige en Flywire ultra-légère et un amorti Zoom Air. Un modèle technique au design agressif inspiré par la Mamba Mentality.",
    'kobe 6': "La Nike Kobe 6 Protro de 2010 pousse encore plus loin le concept low-top avec un profil ultra-bas et un upper en mesh 3D. Portée par Kobe lors de sa cinquième bague NBA, c'est une pièce chargée de légende.",
    'kobe 8': "La Nike Kobe 8 System, sortie en 2012, est la première Kobe signature en Engineered Mesh, offrant un upper ultra-léger et respirant. Un modèle qui incarne la quête d'innovation permanente de la Black Mamba.",
    'kobe': "Les Nike Kobe, ligne signature de Kobe Bryant, ont révolutionné la chaussure de basketball avec leur profil bas et leur légèreté. Chaque modèle incarne la Mamba Mentality : performance, précision et excellence.",
    'ld waffle': "La Nike LD Waffle, née de la collaboration avec Sacai, superpose deux sneakers en une avec sa double semelle, double languette et double Swoosh. Un design déconstructiviste devenu culte du streetwear.",
    'vaporwaffle': "La Nike VaporWaffle Sacai fusionne la Pegasus VaporFly et la LD 1000 dans un design hybride à double épaisseur signature de Sacai. Légèreté, transparence et superposition définissent cette collaboration iconique.",
    'killshot': "La Nike Killshot, modèle court de tennis vintage des années 80, est devenue un classique du style casual grâce à sa silhouette épurée en cuir et daim avec semelle en gomme.",
    'mac attack': "La Nike Mac Attack, chaussure de tennis de John McEnroe des années 80, fait son comeback avec son design rétro court en cuir et son Swoosh bold distinctif. Un classique du tennis devenu pièce streetwear.",
    'field general': "La Nike Field General, modèle d'entraînement football américain, a été réinventée par les collaborations Union LA avec des matériaux premium et un style vintage universitaire.",
    'cortez': "La Nike Cortez, première chaussure de running Nike créée par Bill Bowerman en 1972, est un symbole de la culture californienne et du style décontracté américain depuis plus de 50 ans.",
    'kd 4': "La Nike KD 4, signature shoe de Kevin Durant, combine Zoom Air au talon et semelle Phylon pour un amorti réactif. Son upper en Hyperfuse et son strap au médio-pied offrent maintien et légèreté.",
    'kd': "Les Nike KD, ligne signature de Kevin Durant, allient technologie de pointe et design épuré. Chaque modèle reflète le jeu fluide et polyvalent du Slim Reaper.",
    'air foamposite': "La Nike Air Foamposite One, sortie en 1997, est la première sneaker avec un upper moulé d'une seule pièce. Son design futuriste en mousse Foamposite et son look unique en font un graal des collectionneurs.",
    'air penny': "La Nike Air Penny, ligne signature d'Anfernee Penny Hardaway, se distingue par son design élégant et ses lignes fluides. Le logo 1 Cent et la technologie Air Zoom en font une icône du basketball des années 90.",
    'mind 001': "La Nike Mind 001, slide premium de nouvelle génération, propose un design minimaliste et futuriste avec un confort optimal. Une sandale qui redéfinit le segment du footwear décontracté.",
    'calm slide': "La Nike Calm Slide offre un confort enveloppant avec sa mousse texturée et son profil épuré. Un design minimaliste pensé pour la récupération et la détente après le sport.",
    'air zoom courtposite': "La Nike Air Zoom Courtposite fusionne la technologie Foamposite avec le design tennis pour une silhouette unique. Portée par les collaborations Supreme, elle est devenue un objet de collection rare.",
    'sb darwin': "La Nike SB Darwin Low, modèle skateboard au profil épuré, combine cuir premium et semelle vulcanisée pour un style décontracté. Ses collaborations Supreme en ont fait une pièce très recherchée.",
    'total 90': "La Nike Total 90, chaussure de football iconique du début des années 2000, revient en version lifestyle. Son design technique agressif et ses empiècements en TPU sont devenus cultes dans la culture street.",
    'air dt max': "La Nike Air DT Max '96, chaussure d'entraînement de Deion Sanders, se distingue par son strap imposant et son design audacieux des années 90. Un modèle cross-training devenu pièce de collection.",
    'nikecraft': "Les Nike NikeCraft, collaboration avec l'artiste Tom Sachs, proposent des chaussures utilitaires au design brut et fonctionnel. La General Purpose Shoe incarne une philosophie de simplicité et d'usure assumée.",
    'astro grabber': "La Nike Astro Grabber, modèle vintage de football américain, a été réinventée par la collaboration Bode avec des matériaux artisanaux et un esprit rétro-bohème unique.",
    'air humara': "La Nike Air Humara, modèle trail des années 2000, fait son retour avec son design outdoor technique. Sa semelle crantée et son upper en mesh/cuir séduisent les amateurs de gorpcore.",
    # ── ADIDAS (modèles additionnels) ──
    'bw army': "L'Adidas BW Army (Bundeswehr Army), issue de l'armée allemande, est un modèle militaire réapproprié par le streetwear. Son cuir épuré, sa semelle en gomme et son profil bas en font un classique discret et élégant.",
    # ── NEW BALANCE (modèles additionnels) ──
    'new balance 991': "La New Balance 991, fabriquée en Angleterre (Made in UK), combine technologies ABZORB et Encap pour un confort premium. Son upper en daim et mesh avec des finitions artisanales en fait un modèle haut de gamme.",
    'new balance 993': "La New Balance 993, dernière de la lignée 99X Made in USA, est devenue un symbole de l'élite discrète. Son amorti ABZORB DTS et son cuir premium en font la sneaker de ceux qui savent.",
    'new balance 574': "La New Balance 574, sortie en 1988, est le modèle le plus populaire de New Balance. Son design running rétro en daim et mesh avec technologie Encap offre un confort quotidien intemporel.",
    'new balance 860': "La New Balance 860, modèle running stabilisant, combine technologies ABZORB et Trufuse pour un maintien optimal. Son design technique et ses lignes dynamiques séduisent les amateurs de silhouettes sportives.",
    'new balance 1000': "La New Balance 1000, runner technique des années 2000, fait son retour grâce aux collaborations comme Aimé Leon Dore. Son design chunky rétro et ses technologies d'amorti en font un modèle prisé.",
    'new balance 992': "La New Balance 992, Made in USA et portée par Steve Jobs, est un pilier de la gamme premium NB. Son amorti ABZORB SBS et son upper en daim/mesh gris en font le symbole du confort discret et raffiné.",
    'new balance 740': "La New Balance 740, modèle running rétro-technique, revient sur le devant de la scène avec un design Y2K et des technologies d'amorti modernes. Une silhouette qui séduit la nouvelle génération.",
    'new balance 204': "La New Balance 204L est un modèle technique qui allie innovation et esthétique contemporaine. Son design distinctif et ses matériaux premium en font une pièce remarquée du catalogue New Balance.",
    'abzorb 2000': "La New Balance Abzorb 2000 tire son nom de la technologie d'amorti ABZORB signature de la marque. Son design technique des années 2000 et son profil chunky en font un modèle streetwear recherché.",
    # ── ASICS (modèles additionnels) ──
    'gel-cumulus': "L'Asics Gel-Cumulus, modèle running neutre depuis 1997, offre un amorti Gel confortable et un upper respirant. Sa silhouette technique retro séduit aussi bien les coureurs que les amateurs de streetwear.",
    'gel-lyte iii': "L'Asics Gel-Lyte III, conçue par Shigeyuki Mitsui en 1990, a introduit la languette fendue split-tongue devenue iconique. Son amorti Gel et son design coloré en font un classique du running rétro.",
    'gel-lyte': "L'Asics Gel-Lyte, lancée en 1987, a été la première chaussure à intégrer la technologie d'amorti Gel. Son design running vintage et ses lignes épurées en font un pilier du streetwear japonais.",
    'gt-2160': "L'Asics GT-2160, modèle running stabilisant sorti en 2009, impressionne par son design ultra-technique. Sa technologie Gel et son upper structuré en font un favori du style gorpcore et technique.",
    'gel-nimbus': "L'Asics Gel-Nimbus, référence de l'amorti neutre depuis 1999, offre un confort maximal grâce à ses unités Gel avant-pied et talon. Son design technique et moderne en fait un modèle polyvalent.",
    'gel-quantum': "L'Asics Gel-Quantum 360 enveloppe le pied dans une semelle Gel à 360 degrés pour un amorti intégral. Son design futuriste et son confort maximal en font un modèle unique dans la gamme Asics.",
    # ── UGG (modèles additionnels) ──
    'classic mini': "La UGG Classic Mini, version courte du classique boot UGG, offre la même doublure en peau de mouton et la même semelle Treadlite dans un format compact et polyvalent, parfait pour toutes les saisons.",
    'disquette': "La UGG Disquette, slipper plateforme au design audacieux, combine la peau de mouton UGG avec une semelle surélevée en sucre canne. Un modèle statement qui a conquis les réseaux sociaux.",
    'goldenstar': "La UGG Goldenstar Clog revisite le sabot classique avec la peau de mouton signature UGG et une semelle plateforme. Un modèle confort-first devenu incontournable du style casual.",
    'lowmel': "La UGG Lowmel est une mule plateforme moderne qui combine la doublure en peau de mouton UGG avec un design contemporain. Un modèle facile à enfiler pour un confort instantané.",
    # ── PUMA ──
    'speedcat': "La Puma Speedcat, inspirée des chaussures de pilotes de Formule 1, se distingue par son profil ultra-bas et sa semelle fine. Son design racing minimaliste en fait un modèle tendance du moment.",
    'puma suede': "La Puma Suede, née en 1968 sur les podiums olympiques de Mexico, est un classique du streetwear et du hip-hop. Son upper en daim, sa forme basse et ses coloris variés traversent les décennies.",
    'lamelo': "Les Puma LaMelo Ball, signature shoe du prodige NBA, combinent design avant-gardiste et technologies de performance. L'expression du style flamboyant et du jeu spectaculaire de Melo.",
    # ── AUTRES ──
    'fear of god': "Fear of God, marque fondée par Jerry Lorenzo en 2013, fusionne luxe et streetwear dans des pièces essentielles. La ligne Essentials propose des basiques premium au design minimaliste et intemporel.",
    'dior b23': "La Dior B23, sneaker haute couture de la maison Dior, arbore le motif Oblique signature sur une toile technique. Un modèle de luxe qui incarne la fusion entre mode et culture sneaker.",
    'mschf': "MSCHF, collectif artistique new-yorkais, crée des sneakers provocatrices qui remettent en question les codes du marché. La Big Red Boot, devenue virale, illustre leur approche disruptive du design.",
    'adifom': "L'Adidas adiFOM réinvente des silhouettes classiques avec un matériau mousse monobloc futuriste. Un design minimaliste et organique qui transforme les icônes Adidas en pièces d'art contemporain.",

}

DEFAULT_DESC = "Un modèle premium qui allie qualité de fabrication et design soigné, pensé pour ceux qui recherchent style et confort au quotidien."


def get_model_description(title):
    t = title.lower()
    # Vérifier les clés les plus longues (spécifiques) d'abord
    sorted_keys = sorted(MODEL_DESCRIPTIONS.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in t:
            return MODEL_DESCRIPTIONS[key]
    
    # Matching avancé pour les Jordan (titres Shopify: "Air Jordan X Retro High/Low/Mid OG ...")
    if 'jordan 1' in t:
        if 'high' in t: return MODEL_DESCRIPTIONS.get('jordan 1 high', DEFAULT_DESC)
        if 'low' in t: return MODEL_DESCRIPTIONS.get('jordan 1 low', DEFAULT_DESC)
        if 'mid' in t: return MODEL_DESCRIPTIONS.get('jordan 1 mid', DEFAULT_DESC)
    if 'jordan 4' in t: return MODEL_DESCRIPTIONS.get('jordan 4', DEFAULT_DESC)
    if 'jordan 3' in t: return MODEL_DESCRIPTIONS.get('jordan 3', DEFAULT_DESC)
    if 'jordan 2' in t and 'jordan 2002' not in t: return MODEL_DESCRIPTIONS.get('jordan 2', DEFAULT_DESC)
    if 'jordan 5' in t: return MODEL_DESCRIPTIONS.get('jordan 5', DEFAULT_DESC)
    if 'jordan 6' in t: return MODEL_DESCRIPTIONS.get('jordan 6', DEFAULT_DESC)
    if 'jordan 7' in t: return MODEL_DESCRIPTIONS.get('jordan 7', DEFAULT_DESC)
    if 'jordan 11' in t: return MODEL_DESCRIPTIONS.get('jordan 11', DEFAULT_DESC)
    if 'jordan 12' in t: return MODEL_DESCRIPTIONS.get('jordan 12', DEFAULT_DESC)
    if 'jordan 13' in t: return MODEL_DESCRIPTIONS.get('jordan 13', DEFAULT_DESC)
    
    # Matching par mots-clés larges
    broad = {
        'dunk': 'dunk', 'air force': 'air force 1', 'air max': 'air max',
        'samba': 'samba', 'campus': 'campus', 'gazelle': 'gazelle',
        'forum': 'forum', 'superstar': 'superstar', 'stan smith': 'stan smith',
        'yeezy': 'yeezy 350', 'jordan': 'jordan 1 high',
        'gel 1130': 'gel-1130', 'gel kayano': 'gel-kayano', 'gel nyc': 'gel-nyc',
        'gel lyte': 'gel-lyte', 'gel nimbus': 'gel-nimbus', 'gel quantum': 'gel-quantum',
        'gel cumulus': 'gel-cumulus',
    }
    for kw, key in broad.items():
        if kw in t and key in MODEL_DESCRIPTIONS:
            return MODEL_DESCRIPTIONS[key]
    
    return DEFAULT_DESC



def generate_meta_title(product):
    title = product.get('title', '')
    meta_title = title + ' | ' + SITE_NAME
    if len(meta_title) > 60:
        meta_title = title[:47] + '... | ' + SITE_NAME
    return meta_title


def generate_meta_description(product):
    title = product.get('title', '')
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    brand = extract_brand(title)
    colorway = extract_colorway(title)
    
    # ── VÊTEMENTS ──
    if is_clothing(title):
        clothing_type = get_clothing_type(title)
        color = extract_clothing_color(title)
        if color:
            desc = f"{title} sur {SITE_NAME}. {clothing_type.capitalize()} streetwear premium, coloris {color}. 100% authentique, livraison rapide en France."
        else:
            desc = f"{title} sur {SITE_NAME}. {clothing_type.capitalize()} streetwear premium, 100% authentique. Livraison rapide en France."
        if len(desc) > 155:
            desc = desc[:152].rsplit(' ', 1)[0] + '...'
        return desc
    
    # ── SNEAKERS ──
    collabs = ['Travis Scott', 'Off-White', 'Fragment', 'Union LA', 'Undefeated', 'A Ma Maniere',
               'Sacai', 'CLOT', 'Stussy', 'Patta', 'Supreme', 'BAPE', 'Kith', 'Bad Bunny',
               'Pharrell', 'Drake', 'NOCTA', 'The Simpsons', 'Mercedes AMG', 'Jacquemus', 'Nigo']
    is_collab = any(c.lower() in title.lower() for c in collabs)
    
    if is_collab:
        desc = f"{title} sur {SITE_NAME}. Édition limitée 100% authentique, vérifiée par nos experts. Livraison rapide en France."
    elif colorway and sku:
        desc = f"{title} ({sku}) sur {SITE_NAME}. Coloris {colorway}, 100% authentique. Livraison rapide et paiement sécurisé."
    elif colorway:
        desc = f"Achetez la {title} sur {SITE_NAME}. Coloris {colorway}, authenticité garantie par nos experts. Livraison rapide."
    elif sku:
        desc = f"Achetez la {title} ({sku}) sur {SITE_NAME}. 100% authentique, vérifiée par nos experts. Livraison rapide."
    else:
        desc = f"Achetez la {title} sur {SITE_NAME}. Authenticité garantie, vérifiée par nos experts. Livraison rapide et paiement sécurisé."
    
    if len(desc) > 155:
        desc = desc[:152].rsplit(' ', 1)[0] + '...'
    return desc


def extract_colorway(title):
    """Extrait le coloris/version spécifique du titre produit"""
    t = title
    # Enlever la marque
    brands = ['Nike', 'Adidas', 'New Balance', 'Asics', 'Puma', 'Reebok', 'UGG', 'Crocs', 'Salomon', 'Birkenstock', 'Vans', 'Converse']
    for b in brands:
        if t.startswith(b + ' '):
            t = t[len(b)+1:]
            break
    
    # Enlever le modèle pour garder le coloris
    models = [
        # Jordan (du plus spécifique au moins spécifique)
        'Air Jordan 4 Retro OG SP', 'Air Jordan 4 Retro SE', 'Air Jordan 4 Retro Premium', 'Air Jordan 4 Retro',
        'Air Jordan 1 Retro High OG SP', 'Air Jordan 1 Retro High OG', 'Air Jordan 1 Retro High',
        'Air Jordan 1 Retro Low OG SP', 'Air Jordan 1 Retro Low OG', 'Air Jordan 1 Low SE', 'Air Jordan 1 Low',
        'Air Jordan 1 Mid SE', 'Air Jordan 1 Mid', 'Air Jordan 1 High',
        'Air Jordan 2 Retro', 'Air Jordan 3 Retro', 'Air Jordan 5 Retro', 'Air Jordan 6 Retro',
        'Air Jordan 7 Retro', 'Air Jordan 8 Retro', 'Air Jordan 9 Retro',
        'Air Jordan 11 Retro Low', 'Air Jordan 11 Retro', 'Air Jordan 12 Retro', 'Air Jordan 13 Retro',
        # Nike
        'Dunk Low Retro SP', 'Dunk Low Retro', 'Dunk Low SE', 'Dunk Low', 'Dunk High Retro', 'Dunk High',
        'Air Force 1 Low Retro', 'Air Force 1 Low', 'Air Force 1 High', 'Air Force 1 Mid', 'Air Force 1',
        'Air Max 1', 'Air Max 90', 'Air Max 95', 'Air Max 97', 'Air Max Plus', 'Air Max TN',
        'Vomero 5', 'Vomero', 'P-6000', 'Blazer Mid', 'Blazer Low', 'Blazer',
        # Adidas
        'Samba OG', 'Samba Decon', 'Samba', 'Campus 00s', 'Campus', 'Gazelle Bold', 'Gazelle Indoor', 'Gazelle',
        'Handball Spezial', 'Spezial', 'Forum Low', 'Forum Mid', 'Forum 84 Low', 'Forum',
        'SL 72 OG', 'SL 72', 'Adilette 22', 'Adilette',
        # Yeezy
        'Yeezy Slide', 'Yeezy Boost 350 V2', 'Yeezy 350 V2', 'Yeezy 350', 'Yeezy 700 V3', 'Yeezy 700',
        'Yeezy Foam Runner', 'Yeezy 500',
        # New Balance
        '550', '530', '2002R', '9060', '1906R', '990v6', '990v5', '990v4', '990v3', '990',
        '993', '2002', '327', '574', '480',
        # Asics
        'Gel-1130', 'Gel-Kayano 14', 'Gel-Kayano', 'Gel-NYC', 'Gel-Nimbus 9', 'GT-2160',
        # UGG
        'Tasman Slipper', 'Tasman', 'Tazz Slipper', 'Tazz Platform', 'Tazz',
        'Ultra Mini Platform', 'Ultra Mini', 'Classic Mini II Boot', 'Classic Mini II', 'Classic Mini',
        'Classic Short II Boot', 'Classic Short II', 'Classic Short',
        'Disquette Slipper', 'Disquette', 'Goldenstar Clog', 'Goldenstar',
        'Lowmel', 'Scuffette II',
        # Autres
        'SB Dunk Low', 'SB Dunk High',  # Nike SB
        'NOCTA Glide', 'NOCTA Hot Step',  # NOCTA
        'AE 1', 'AE1',  # Adidas AE
        'Bermuda', 'Superstar', 'Stan Smith',  # Adidas
        'adiFOM Superstar',  # Adidas
        'Yeezy 500', 'Yeezy Boost 380',  # Yeezy
        'Adiracer GT', 'Adistar Jellyfish',  # Adidas collab
        'Adizero SL 72',  # Adidas
        'Classic Clog', 'Classic Slide',  # Crocs
        'Old Skool', 'Sk8-Hi', 'Era', 'Authentic',  # Vans
        'Chuck Taylor', 'Chuck 70',  # Converse
        'XT-6', 'XT-4', 'ACS Pro',  # Salomon
    ]
    
    colorway = t
    for m in models:
        if t.startswith(m + ' '):
            colorway = t[len(m)+1:]
            break
        elif t.startswith(m):
            colorway = t[len(m):]
            break
    
    colorway = colorway.strip(' -')
    return colorway if colorway and colorway != t else ''


def generate_color_description_ai(title, colorway, brand, model_desc):
    """Utilise l'API Claude pour générer une description spécifique au coloris"""
    if not colorway:
        return '', 'color'
    
    try:
        prompt = f"""Tu es un expert sneakers qui rédige des descriptions produits pour un site e-commerce français (KP SHOES).

Produit : {title}
Coloris/version : {colorway}
Marque : {brand}

Écris UNE SEULE phrase (2-3 lignes max) décrivant spécifiquement ce coloris/cette version. 
- Décris les couleurs réelles de la paire (pas juste traduire le nom)
- Si c'est une collaboration, mentionne-la
- Si c'est un coloris iconique (Chicago, Bred, Panda, etc.), mentionne son histoire
- Sois précis et naturel, pas générique
- Ne commence PAS par "Le coloris" ou "Cette version"
- Réponds UNIQUEMENT avec la phrase, rien d'autre."""

        api_url = "https://api.anthropic.com/v1/messages"
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': os.environ.get('ANTHROPIC_API_KEY', ''),
            'anthropic-version': '2023-06-01'
        }
        data = {
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 150,
            'messages': [{'role': 'user', 'content': prompt}]
        }
        
        if not headers['x-api-key']:
            return generate_color_sentence_fallback(title, colorway)
        
        req = Request(api_url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urlopen(req, context=ctx, timeout=15) as r:
            result = json.loads(r.read().decode('utf-8'))
            if result.get('content') and result['content'][0].get('text'):
                sentence = result['content'][0]['text'].strip()
                # Déterminer le type via le fallback logic
                _, cw_type = generate_color_sentence_fallback(title, colorway)
                return sentence, cw_type
    except Exception as e:
        log.error(f"[AI Color] Error: {e}")
    
    return generate_color_sentence_fallback(title, colorway)


def generate_color_sentence_fallback(title, colorway):
    """Fallback sans IA pour la description coloris"""
    if not colorway:
        return '', 'color'
    
    collabs = ['Travis Scott', 'Off-White', 'Fragment', 'Union LA', 'Undefeated', 'A Ma Maniere', 
               'A Ma Maniére', 'J Balvin', 'PSG', 'Eminem', 'Fear of God', 'Sacai', 'CLOT', 'Stussy',
               'Patta', 'Concepts', 'atmos', 'Supreme', 'BAPE', 'Kith', 'JJJJound', 'Nocta',
               'Billie Eilish', 'Bad Bunny', 'Pharrell', 'Drake', 'UNDFTD', 'Cactus Jack',
               'Union', 'Ambush', 'Comme des Garcons', 'CDG', 'Social Status', 'SoleFly',
               'The Simpsons', 'Nigo', 'Mercedes AMG', 'Dodgers', 'Yankees', 'Georgia Bulldogs',
               'Manchester United', 'Gratitude', 'What The', 'Aleali May', 'Melody Ehsani',
               'Maison Chateau Rouge', 'Jacquemus']
    
    for collab in collabs:
        if collab.lower() in colorway.lower() or collab.lower() in title.lower():
            sentence = f'Fruit de la collaboration exclusive avec {collab}, cette édition se distingue par un design unique et des détails soignés qui en font une pièce très convoitée.'
            return sentence, 'collab'
    
    # Coloris iconiques avec descriptions spécifiques
    iconic = {
        'chicago': "Habillée du légendaire coloris Chicago — rouge, blanc et noir — cette paire rend hommage à la ville qui a vu naître la dynastie Jordan et la culture sneaker.",
        'bred': "Le coloris Bred (Black/Red), indissociable de Michael Jordan et de la marque Jordan, reste l'un des duos de couleurs les plus emblématiques de l'histoire des sneakers.",
        'royal': "Le coloris Royal Blue, associé à la Air Jordan depuis 1985, offre un contraste saisissant entre le bleu royal et le noir qui en fait un classique intemporel.",
        'panda': "Le coloris Panda, combinaison épurée de noir et blanc, est devenu un phénomène viral et l'un des coloris les plus demandés de ces dernières années.",
        'shadow': "Le coloris Shadow, mélange subtil de noir et gris, apporte une élégance discrète et polyvalente qui se marie avec toutes les tenues.",
        'mocha': "Le coloris Mocha associe des tons marron chocolat au noir et au blanc, créant une palette chaleureuse inspirée des teintes café très prisée des collectionneurs.",
        'university blue': "Le coloris University Blue s'inspire du bleu de l'université de Caroline du Nord (UNC), alma mater de Michael Jordan, créant un lien direct avec les racines de la marque.",
        'cool grey': "Le coloris Cool Grey, popularisé par la Air Jordan 11 en 2001, offre une palette de gris sophistiquée et passe-partout devenue un classique de la gamme.",
        'infrared': "Le coloris Infrared, associé aux Air Max 90 depuis 1990, est reconnaissable à son rouge-rose éclatant qui a défini l'identité visuelle de ce modèle iconique.",
        'triple white': "Cette version Triple White propose un look monochrome immaculé et épuré, parfait pour un style minimaliste et élégant au quotidien.",
        'triple black': "Cette version Triple Black offre un look monochrome total en noir, alliant discrétion et sophistication pour un style urbain affirmé.",
        'lost and found': "L'édition Lost and Found reproduit l'effet d'une paire vintage retrouvée dans un entrepôt, avec un cuir craquelé vieilli et une boîte jaunie par le temps.",
        'reimagined': "L'édition Reimagined revisite un coloris classique avec des finitions vintage et un cuir premium vieilli pour un look authentique dès la sortie de boîte.",
        'washed': "Cette édition Washed présente un traitement délavé sur les matériaux, donnant un aspect vintage porté qui séduit les amateurs de style rétro.",
        'reverse mocha': "Le Reverse Mocha inverse les panneaux du coloris Mocha original, plaçant le daim marron sur la base et le blanc en overlay pour un résultat distinctif.",
        'military black': "Le coloris Military Black associe des tons noirs, gris et blancs dans une palette sobre et polyvalente d'inspiration militaire.",
        'oxidized green': "Le coloris Oxidized Green s'inspire de la patine du cuivre oxydé, offrant des tons verts émeraude vieillis pour un rendu unique.",
        'cement': "Le coloris Cement rend hommage à l'elephant print iconique de la Jordan 3, avec ses motifs gris éclaboussés devenus signature de la marque.",
    }
    
    cl = colorway.lower()
    for key, desc in iconic.items():
        if key in cl:
            return desc, 'color'
    
    # Détecter si c'est un vrai nom de couleur
    color_keywords = [
        'black', 'white', 'red', 'blue', 'green', 'grey', 'gray', 'pink', 'purple',
        'orange', 'yellow', 'brown', 'beige', 'cream', 'navy', 'olive', 'gold', 'silver',
        'sail', 'bone', 'sand', 'smoke', 'royal', 'bred', 'panda', 'shadow', 'mocha',
        'cement', 'infrared', 'scarlet', 'burgundy', 'core black', 'cloud white',
        'phantom', 'mushroom', 'tan', 'cobalt', 'teal', 'coral', 'mint', 'lavender',
        'rust', 'sesame', 'slate', 'charcoal', 'chalk', 'dark', 'light', 'pure',
        'noir', 'blanc', 'rouge', 'bleu', 'vert', 'rose', 'gris',
        'indigo', 'khaki', 'ivory', 'onyx', 'ochre', 'lime', 'crimson', 'magnet',
        'stone', 'forest', 'dust', 'metallic', 'chrome', 'platinum', 'copper',
        'midnight', 'graphite', 'glow', 'alabaster', 'fossil', 'sea salt', 'rain cloud',
        'desert', 'azure', 'peach', 'plum', 'amber', 'mauve', 'cardinal', 'aqua',
    ]
    
    has_color = any(kw in cl for kw in color_keywords)
    
    if has_color:
        sentence = f'Proposée dans le coloris "{colorway}", cette paire affirme son identité avec une combinaison de teintes et de matières qui lui est propre.'
        return sentence, 'color'
    
    # Pas de couleur détectée et pas de collab → édition spéciale
    sentence = f'Cette édition "{colorway}" se démarque par son identité visuelle unique et ses finitions soignées.'
    return sentence, 'edition'


def is_clothing(title):
    """Détecte si le produit est un vêtement (pas une sneaker)"""
    clothing_kw = ['hoodie', 'sweatpant', 'sweatshort', 'tee ', 't-shirt', 'crewneck', 'jacket',
                   'pant ', 'pants', 'short ', 'shorts']
    t = title.lower()
    return any(kw in t for kw in clothing_kw)


def get_clothing_type(title):
    """Retourne le type de vêtement en français"""
    t = title.lower()
    if 'hoodie' in t: return 'hoodie'
    if 'sweatpant' in t: return 'jogging'
    if 'sweatshort' in t: return 'short'
    if 'crewneck' in t or 's/s tee' in t or 'ss tee' in t or 't-shirt' in t or 'tee ' in t: return 't-shirt'
    if 'jacket' in t: return 'veste'
    if 'pant' in t: return 'pantalon'
    if 'short' in t: return 'short'
    return 'pièce'


def extract_clothing_color(title):
    """Extrait la couleur d'un vêtement depuis le titre"""
    t = title
    # Supprimer les patterns connus pour garder la couleur à la fin
    for remove in ['Fear Of God Fear of God Essentials ', 'Fear Of God ', '(FW24)', '(SS25)', '(FW23)']:
        t = t.replace(remove, '')
    # Le dernier mot/groupe est généralement la couleur
    parts = t.strip().split()
    # Trouver où commence la couleur (après le type de vêtement)
    clothing_words = ['Classic', 'Fleece', 'Essential', 'Jersey', 'Crewneck', 'Core', 'Collection',
                      'Heavy', 'S/S', 'SS', 'NBA', 'Relaxed', 'Hoodie', 'Sweatpant', 'Sweatshort',
                      'Sweatshorts', 'Tee', 'T-Shirt']
    color_start = 0
    for i, p in enumerate(parts):
        if p in clothing_words:
            color_start = i + 1
    color = ' '.join(parts[color_start:]) if color_start < len(parts) else ''
    return color.strip()


def generate_body_html(product, collections):
    title = product.get('title', '')
    brand = extract_brand(title)
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    collection = find_collection(title, collections)
    
    # ── VÊTEMENTS ──
    if is_clothing(title):
        clothing_type = get_clothing_type(title)
        color = extract_clothing_color(title)
        
        lines = []
        # Paragraphe 1: Introduction
        if collection:
            lines.append(f'<p>Découvrez le <strong>{title}</strong> disponible sur {SITE_NAME}. Retrouvez cette pièce et bien d\'autres dans notre collection <a href="{collection["url"]}">{collection["title"]}</a>.</p>')
        else:
            lines.append(f'<p>Découvrez le <strong>{title}</strong> disponible sur {SITE_NAME}.</p>')
        
        # Paragraphe 2: Description de la marque/ligne
        if 'essentials' in title.lower():
            lines.append(f'<p>La ligne Essentials de Fear of God, créée par Jerry Lorenzo, propose des basiques streetwear premium au design minimaliste et intemporel. Chaque pièce se distingue par sa coupe oversize signature, ses matériaux de haute qualité et le logo Essentials discret qui est devenu un symbole du luxe décontracté.</p>')
        else:
            lines.append(f'<p>{get_model_description(title)}</p>')
        
        # Paragraphe 3: Description spécifique à la pièce
        type_descs = {
            'hoodie': f'Ce hoodie en molleton épais offre un confort enveloppant avec sa capuche doublée, sa poche kangourou et ses finitions côtelées aux poignets et à la taille. Une pièce essentielle de toute garde-robe streetwear.',
            'jogging': f'Ce jogging en molleton premium allie confort et style avec sa coupe décontractée, sa taille élastiquée à cordon et ses finitions côtelées aux chevilles. Parfait pour un look streetwear complet.',
            'short': f'Ce short en molleton combine confort et style décontracté avec sa coupe ample, sa taille élastiquée et ses finitions soignées. Idéal pour un look casual urbain.',
            't-shirt': f'Ce t-shirt en jersey de coton premium offre une coupe ample et décontractée avec des coutures renforcées et une finition douce au toucher. Un basique streetwear élevé au rang de pièce premium.',
            'veste': f'Cette veste allie fonctionnalité et esthétique streetwear avec ses matériaux premium et sa coupe contemporaine.',
        }
        desc = type_descs.get(clothing_type, f'Cette pièce incarne l\'esthétique minimaliste et premium de la collection, avec des matériaux de haute qualité et une coupe contemporaine.')
        lines.append(f'<p>{desc}</p>')
        
        # Paragraphe 4: Caractéristiques
        tech_items = []
        if sku:
            tech_items.append(f'<li><strong>Référence :</strong> {sku}</li>')
        tech_items.append(f'<li><strong>Marque :</strong> Fear of God Essentials</li>')
        tech_items.append(f'<li><strong>Type :</strong> {clothing_type.capitalize()}</li>')
        if color:
            tech_items.append(f'<li><strong>Coloris :</strong> {color}</li>')
        lines.append('<ul style="list-style:none;padding-left:0;">' + ''.join(tech_items) + '</ul>')
        
        # Paragraphe 5: Garanties
        lines.append(f'<p>Chez <strong>{SITE_NAME}</strong>, nous garantissons l\'authenticité de chaque article. Tous nos produits sont vérifiés par nos experts avant expédition. Livraison rapide et paiement sécurisé.</p>')
        
        return ''.join(lines)
    
    # ── SNEAKERS (logique existante) ──
    model_desc = get_model_description(title)
    colorway = extract_colorway(title)
    
    # Obtenir la phrase + le type (color, collab, edition)
    if colorway:
        color_sentence, cw_type = generate_color_description_ai(title, colorway, brand, model_desc)
    else:
        color_sentence, cw_type = '', 'color'
    
    lines = []
    
    # Paragraphe 1: Introduction avec lien collection
    if collection:
        lines.append(f'<p>Découvrez la <strong>{title}</strong> disponible sur {SITE_NAME}. Retrouvez ce modèle et bien d\'autres dans notre collection <a href="{collection["url"]}">{collection["title"]}</a>.</p>')
    else:
        lines.append(f'<p>Découvrez la <strong>{title}</strong> disponible sur {SITE_NAME}.</p>')
    
    # Paragraphe 2: Description du modèle
    lines.append(f'<p>{model_desc}</p>')
    
    # Paragraphe 3: Description spécifique au coloris/collab
    if color_sentence:
        lines.append(f'<p>{color_sentence}</p>')
    
    # Paragraphe 4: Caractéristiques techniques
    tech_items = []
    if sku:
        tech_items.append(f'<li><strong>Référence :</strong> {sku}</li>')
    tech_items.append(f'<li><strong>Marque :</strong> {brand}</li>')
    if colorway:
        if cw_type == 'collab':
            tech_items.append(f'<li><strong>Édition :</strong> {colorway}</li>')
        else:
            tech_items.append(f'<li><strong>Coloris :</strong> {colorway}</li>')
    lines.append('<ul style="list-style:none;padding-left:0;">' + ''.join(tech_items) + '</ul>')
    
    # Paragraphe 5: Garanties KP SHOES
    lines.append(f'<p>Chez <strong>{SITE_NAME}</strong>, nous garantissons l\'authenticité de chaque paire. Toutes nos sneakers sont vérifiées par nos experts avant expédition. Livraison rapide et paiement sécurisé.</p>')
    
    return ''.join(lines)


def update_seo_field(pid, field, value):
    if field == 'body_html':
        shopify_request(f'products/{pid}.json', 'PUT', {'product': {'id': pid, 'body_html': value}})
    elif field == 'meta_title':
        shopify_request(f'products/{pid}/metafields.json', 'POST', {'metafield': {'namespace': 'global', 'key': 'title_tag', 'value': value, 'type': 'single_line_text_field'}})
    elif field == 'meta_description':
        shopify_request(f'products/{pid}/metafields.json', 'POST', {'metafield': {'namespace': 'global', 'key': 'description_tag', 'value': value, 'type': 'single_line_text_field'}})
    return True


# ══════════════════════════════════════════════════════════════
# COLLECTIONS SEO
# ══════════════════════════════════════════════════════════════

COLLECTION_SEO = {
    'jordan-4': {
        'meta_title': 'Air Jordan 4 - Sneakers Jordan pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre Air Jordan 4 sur KP SHOES. Tous les coloris disponibles : Military Black, Bred, Cement. 100% authentique, livraison rapide en France.",
        'description': "<p>Conçue par Tinker Hatfield en 1989, la <strong>Air Jordan 4</strong> est l'une des silhouettes les plus emblématiques de l'histoire des sneakers. Imaginée pour répondre aux besoins de Michael Jordan sur le terrain, elle a introduit le mesh sur une chaussure de basketball, les œillets en TPU et un amorti Air visible au talon — des innovations qui ont redéfini le design sneaker.</p><p>C'est avec la AJ4 aux pieds que MJ a inscrit son nom dans la légende avec « The Shot », le tir décisif contre Craig Ehlo lors des Playoffs 1989. La silhouette a aussi conquis la rue grâce au réalisateur Spike Lee, qui l'a portée dans plusieurs de ses films et a créé une série de publicités iconiques avec Nike sous le personnage de Mars Blackmon.</p><p>Depuis, la Jordan 4 a été déclinée dans des coloris devenus cultes : <strong>Bred</strong>, <strong>White Cement</strong>, <strong>Military Black</strong>, <strong>Fire Red</strong> ou encore la collaboration avec <strong>Travis Scott</strong>. Chaque nouvelle release continue de provoquer un engouement massif auprès des collectionneurs et amateurs de streetwear.</p><p>Chez <strong>KP SHOES</strong>, retrouvez toutes les Air Jordan 4 disponibles, 100% authentiques et vérifiées par nos experts. Livraison rapide en France et paiement sécurisé.</p>",
    },
    'jordan-1-high': {
        'meta_title': 'Air Jordan 1 High - Sneakers Jordan pour Homme et Femme | KP SHOES',
        'meta_description': "Découvrez toutes les Air Jordan 1 High sur KP SHOES. Chicago, Bred, Mocha, University Blue... 100% authentiques, livraison rapide en France.",
        'description': "<p>Créée par Peter Moore en 1985, la <strong>Air Jordan 1 High</strong> est la sneaker qui a tout commencé. Premier modèle signature de Michael Jordan chez Nike, elle a été immédiatement bannie par la NBA pour infraction au code couleur — une amende de 5 000 dollars par match que Nike a payée avec plaisir, transformant la controverse en opération marketing légendaire.</p><p>Avec son upper en cuir premium, son col montant et sa technologie Air dans la semelle, la Jordan 1 High a posé les fondations d'un empire. Les coloris originaux — <strong>Chicago</strong>, <strong>Bred</strong>, <strong>Royal Blue</strong>, <strong>Shadow</strong> — sont devenus des grails qui continuent de faire vibrer les collectionneurs à chaque réédition.</p><p>Au fil des décennies, la silhouette a été sublimée par des collaborations d'exception : <strong>Off-White</strong> et Virgil Abloh, <strong>Travis Scott</strong> avec le Swoosh inversé, <strong>Union LA</strong>, <strong>Dior</strong> ou encore l'édition <strong>Lost and Found</strong> qui reproduit l'effet d'une paire retrouvée dans un entrepôt. Chaque release crée l'événement.</p><p>Retrouvez toutes les Air Jordan 1 High sur <strong>KP SHOES</strong>, 100% authentiques et vérifiées par nos experts.</p>",
    },
    'jordan-1-low': {
        'meta_title': 'Air Jordan 1 Low - Sneakers Jordan pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Air Jordan 1 Low sur KP SHOES. Panda, Mocha, University Blue, Travis Scott... Authenticité garantie, livraison rapide en France.",
        'description': "<p>Version basse de la légendaire Air Jordan 1, la <strong>Air Jordan 1 Low</strong> conserve l'ADN iconique du modèle de 1985 avec un col plus bas pour un confort quotidien optimal. Même cuir premium, même semelle Air, même style — dans un profil plus discret et polyvalent qui se porte avec tout.</p><p>Déclinée dans une multitude de coloris, la AJ1 Low est devenue l'une des silhouettes les plus populaires du moment. Du classique <strong>Panda</strong> noir et blanc aux éditions <strong>Travis Scott Reverse Mocha</strong>, en passant par les <strong>University Blue</strong> et les <strong>Starfish</strong>, il existe une Jordan 1 Low pour chaque style.</p><p>Chez <strong>KP SHOES</strong>, découvrez tous les coloris Air Jordan 1 Low disponibles. Chaque paire est 100% authentique et vérifiée par nos experts avant expédition.</p>",
    },
    'jordan-1-mid': {
        'meta_title': 'Air Jordan 1 Mid - Sneakers Jordan pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre Air Jordan 1 Mid sur KP SHOES. Des centaines de coloris disponibles, 100% authentiques. Livraison rapide en France.",
        'description': "<p>La <strong>Air Jordan 1 Mid</strong> offre le parfait équilibre entre la High et la Low avec un col intermédiaire qui allie style et confort. Sortie dans des centaines de coloris depuis 1985, elle est l'entrée idéale dans l'univers Jordan grâce à son rapport qualité-prix imbattable.</p><p>Du <strong>UNC</strong> au <strong>Banned</strong> en passant par des éditions saisonnières toujours plus créatives, la AJ1 Mid est la toile idéale pour toutes les inspirations. Sa polyvalence en fait un modèle adopté aussi bien par les collectionneurs que par ceux qui découvrent l'univers sneakers.</p><p>Retrouvez toutes les Air Jordan 1 Mid disponibles sur <strong>KP SHOES</strong>. 100% authentiques, livrées dans leur boîte d'origine.</p>",
    },
    'nike-dunk': {
        'meta_title': 'Nike Dunk Low & High - Sneakers Nike pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez vos Nike Dunk Low et High sur KP SHOES. Panda, Travis Scott, Off-White... Tous les coloris, 100% authentiques. Livraison rapide.",
        'description': "<p>Créée en 1985 pour le programme basketball universitaire <em>Be True To Your School</em>, la <strong>Nike Dunk</strong> est devenue l'une des silhouettes les plus populaires au monde. Du parquet au skatepark, puis du skatepark au trottoir, elle a traversé quatre décennies sans jamais perdre de son attrait.</p><p>La <strong>Dunk Low</strong> est la star incontestée : le coloris <strong>Panda</strong> (Black White) a été la sneaker la plus vendue en 2022 et 2023. Les collaborations légendaires — <strong>Travis Scott</strong>, <strong>Off-White</strong>, <strong>Supreme</strong>, <strong>Ben &amp; Jerry's</strong> — ont propulsé la Dunk au rang de grail ultime. La <strong>Dunk High</strong> conserve quant à elle le charme du modèle original avec sa tige montante.</p><p>Découvrez toutes les Nike Dunk disponibles sur <strong>KP SHOES</strong>. Authenticité garantie, livraison rapide en France.</p>",
    },
    'air-force-1': {
        'meta_title': 'Nike Air Force 1 - Sneakers Nike pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Nike Air Force 1 sur KP SHOES. White, Black, collaborations... Le modèle Nike le plus vendu, 100% authentique. Livraison rapide.",
        'description': "<p>Première sneaker de l'histoire à intégrer la technologie Air en 1982, la <strong>Nike Air Force 1</strong> dessinée par Bruce Kilgore est tout simplement le modèle le plus vendu de Nike — et l'une des chaussures les plus vendues de tous les temps. Son cuir premium, sa semelle Air et sa silhouette épaisse en ont fait un classique absolu de la culture urbaine.</p><p>De la version <strong>Triple White</strong> immaculée à la <strong>Triple Black</strong>, en passant par les collaborations avec <strong>Off-White</strong>, <strong>Supreme</strong> ou <strong>Louis Vuitton</strong>, l'AF1 se réinvente sans cesse tout en restant fidèle à son ADN. Adoptée par le hip-hop depuis les années 80, elle est aujourd'hui un symbole universel du style streetwear.</p><p>Retrouvez toutes les Nike Air Force 1 sur <strong>KP SHOES</strong>, 100% authentiques et vérifiées par nos experts.</p>",
    },
    'nike-p-6000': {
        'meta_title': 'Nike Air Max - Sneakers Nike pour Homme et Femme | KP SHOES',
        'meta_description': "Découvrez toutes les Nike Air Max sur KP SHOES. Air Max 1, 90, 95, 97, Plus TN, Dn... 100% authentiques, livraison rapide en France.",
        'description': "<p>Depuis 1987 et la révolution de la bulle Air visible imaginée par Tinker Hatfield, la gamme <strong>Nike Air Max</strong> n'a cessé de repousser les limites de l'innovation et du design. De la <strong>Air Max 1</strong> qui a tout lancé à la <strong>Air Max Dn</strong> de nouvelle génération, chaque modèle a marqué son époque.</p><p>La <strong>Air Max 90</strong> est un pilier de la culture urbaine, la <strong>Air Max 95</strong> inspirée de l'anatomie humaine a bouleversé les codes du design, la <strong>Air Max 97</strong> avec ses lignes de Shinkansen a introduit le full-length Air, et la <strong>Air Max Plus TN</strong> est devenue un phénomène mondial particulièrement culte en France.</p><p>Découvrez toute la collection Nike Air Max sur <strong>KP SHOES</strong>. Tous les modèles, tous les coloris, 100% authentiques.</p>",
    },
    'nike-vomero': {
        'meta_title': 'Nike Vomero 5 - Sneakers Nike pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez la Nike Zoom Vomero 5 sur KP SHOES. Tous les coloris disponibles. 100% authentique, livraison rapide en France.",
        'description': "<p>La <strong>Nike Zoom Vomero 5</strong>, modèle running technique sorti en 2000, fait son grand retour sur la scène streetwear. Ses superpositions en cuir et mesh, sa technologie Zoom Air et son look chunky rétro-technique en font un favori des amateurs de silhouettes Y2K.</p><p>Retrouvez toutes les Nike Vomero 5 disponibles sur <strong>KP SHOES</strong>. 100% authentiques, vérifiées par nos experts.</p>",
    },
    'nike-sacail': {
        'meta_title': 'Nike x Sacai - Sneakers en Édition Limitée | KP SHOES',
        'meta_description': "Toutes les Nike x Sacai sur KP SHOES. LD Waffle, VaporWaffle, Cortez... Éditions limitées 100% authentiques. Livraison rapide en France.",
        'description': "<p>La collaboration entre <strong>Nike et Sacai</strong>, label japonais fondé par Chitose Abe, a redéfini le concept de sneaker hybride. En superposant deux modèles en un — double semelle, double languette, double Swoosh — Sacai a créé un langage visuel unique qui a conquis le monde entier.</p><p>La <strong>LD Waffle</strong>, la <strong>VaporWaffle</strong> et la <strong>Cortez 4.0</strong> sont devenues des pièces maîtresses du streetwear contemporain. Chaque release est un événement qui mêle héritage running et innovation déconstructiviste.</p><p>Retrouvez toutes les Nike x Sacai sur <strong>KP SHOES</strong>, 100% authentiques et vérifiées par nos experts.</p>",
    },
    'adidas-samba': {
        'meta_title': 'Adidas Samba - Sneakers Adidas pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre Adidas Samba sur KP SHOES. OG, Bold, Decon... Tous les coloris disponibles. 100% authentique, livraison rapide en France.",
        'description': "<p>Née en 1950 pour permettre aux footballeurs de s'entraîner sur terrain gelé, l'<strong>Adidas Samba</strong> est devenue l'une des chaussures les plus vendues de l'histoire. Son upper en cuir, sa semelle en gomme, son toe cap en T et ses trois bandes latérales sont reconnaissables entre mille.</p><p>Portée par les terraces britanniques dans les années 80, adoptée par le monde de la mode et du streetwear dans les années 2020, la Samba connaît un revival spectaculaire. Les versions <strong>OG</strong>, <strong>Bold</strong> (plateforme) et <strong>Decon</strong> se déclinent dans des dizaines de coloris, du classique <strong>Core Black</strong> aux éditions les plus créatives.</p><p>Retrouvez toutes les Adidas Samba sur <strong>KP SHOES</strong>. 100% authentiques, livraison rapide en France.</p>",
    },
    'adidas-campus': {
        'meta_title': 'Adidas Campus 00s - Sneakers Adidas pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Adidas Campus 00s sur KP SHOES. Core Black, Grey, Forest Glade... En daim premium, 100% authentiques. Livraison rapide.",
        'description': "<p>Apparue dans les années 80, l'<strong>Adidas Campus</strong> se distingue par son upper en daim premium et ses trois bandes contrastées. Adoptée par la scène hip-hop new-yorkaise puis par le skateboarding, elle incarne l'esprit universitaire américain.</p><p>La version <strong>Campus 00s</strong> revisite le classique avec une semelle jaunie pour un effet vintage et une coupe modernisée. Disponible dans des coloris comme le <strong>Core Black</strong>, <strong>Grey White</strong> ou <strong>Forest Glade</strong>, c'est la silhouette rétro parfaite pour un look casual raffiné.</p><p>Retrouvez toutes les Adidas Campus sur <strong>KP SHOES</strong>. Authenticité garantie.</p>",
    },
    'adidas-gazelle': {
        'meta_title': 'Adidas Gazelle - Sneakers Adidas pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre Adidas Gazelle sur KP SHOES. Bold, Indoor, OG... Tous les coloris en daim, 100% authentiques. Livraison rapide en France.",
        'description': "<p>Créée en 1966, l'<strong>Adidas Gazelle</strong> est un classique intemporel qui traverse les décennies. Son upper en daim, sa semelle en caoutchouc et son profil épuré en ont fait un modèle adopté par les terrains de foot, les scènes musicales et les rues du monde entier.</p><p>Avec les versions <strong>Bold</strong> (plateforme), <strong>Indoor</strong> et les déclinaisons saisonnières, la Gazelle se réinvente tout en restant fidèle à son ADN minimaliste. Un must-have de toute garde-robe streetwear.</p><p>Découvrez toutes les Adidas Gazelle sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'adidas-spezial': {
        'meta_title': 'Adidas Spezial - Sneakers Adidas pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Adidas Spezial sur KP SHOES. Handball Spezial, terrace style... 100% authentiques, livraison rapide en France.",
        'description': "<p>L'<strong>Adidas Spezial</strong>, née dans les années 70 pour le handball, incarne l'esprit terrace culture britannique. Son daim premium, sa semelle en gomme translucide et sa silhouette basse en font un symbole du style casual européen.</p><p>Portée par les supporters de football anglais et adoptée par la scène streetwear mondiale, la Spezial est la sneaker du connaisseur. Son design épuré et ses matériaux nobles en font une pièce qui se bonifie avec le temps.</p><p>Retrouvez toutes les Adidas Spezial sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'adidas-forum': {
        'meta_title': 'Adidas Forum - Sneakers Adidas pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre Adidas Forum sur KP SHOES. Forum Low, Mid, 84... Tous les coloris, 100% authentiques. Livraison rapide en France.",
        'description': "<p>Sortie en 1984, l'<strong>Adidas Forum</strong> était la chaussure de basketball la plus chère de l'époque. Son strap à boucle distinctif, son upper en cuir et sa silhouette imposante en ont fait un favori du hip-hop dès les années 80.</p><p>Déclinée en versions <strong>Low</strong>, <strong>Mid</strong> et <strong>84</strong>, la Forum revient en force avec des collaborations remarquées et des coloris contemporains. Le strap signature reste son signe distinctif.</p><p>Retrouvez toutes les Adidas Forum sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'yeezy-slide': {
        'meta_title': 'Yeezy Slide - Slides Yeezy pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez vos Yeezy Slide sur KP SHOES. Onyx, Bone, Pure... Tous les coloris disponibles, 100% authentiques. Livraison rapide en France.",
        'description': "<p>La <strong>Yeezy Slide</strong>, conçue par Kanye West, est une sandale monobloc en mousse EVA injectée devenue l'un des slides les plus désirées du marché. Son design minimaliste, son confort exceptionnel et sa rareté en ont fait un phénomène culturel.</p><p>Disponible dans les coloris <strong>Onyx</strong>, <strong>Bone</strong>, <strong>Pure</strong> et bien d'autres, la Yeezy Slide est la pièce indispensable de l'été et du style décontracté toute l'année.</p><p>Retrouvez toutes les Yeezy Slide sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'yeezy-351': {
        'meta_title': 'Yeezy Boost 350 V2 - Sneakers Yeezy pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre Yeezy 350 V2 sur KP SHOES. Zebra, Beluga, Bred... Tous les coloris, 100% authentiques. Livraison rapide en France.",
        'description': "<p>La <strong>Yeezy Boost 350 V2</strong>, fruit de la collaboration entre Kanye West et Adidas, a révolutionné le marché sneaker en 2016. Son upper Primeknit, son boost pleine longueur et sa bande latérale SPLY-350 sont immédiatement reconnaissables.</p><p>Des coloris iconiques comme <strong>Zebra</strong>, <strong>Beluga</strong>, <strong>Bred</strong> et <strong>Cream White</strong> ont défini une ère de la culture sneakers. Chaque drop continue de créer l'événement.</p><p>Retrouvez toutes les Yeezy 350 V2 sur <strong>KP SHOES</strong>, 100% authentiques et vérifiées.</p>",
    },
    'yeezy-350': {
        'meta_title': 'Yeezy 700 - Sneakers Yeezy pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Yeezy 700 sur KP SHOES. Wave Runner, V2, V3... Tous les coloris, 100% authentiques. Livraison rapide en France.",
        'description': "<p>La <strong>Yeezy 700</strong>, sortie en 2017, a relancé la tendance chunky sneaker. Ses multiples couches de daim, mesh et cuir combinées à un amorti Boost encapsulé en font une pièce aussi confortable que visuellement audacieuse.</p><p>Du <strong>Wave Runner</strong> original aux versions <strong>V2</strong> et <strong>V3</strong>, la Yeezy 700 décline un design futuriste dans des coloris recherchés.</p><p>Retrouvez toutes les Yeezy 700 sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'new-balance-550': {
        'meta_title': 'New Balance 550 - Sneakers NB pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre New Balance 550 sur KP SHOES. White Green, ALD, Sea Salt... 100% authentiques, livraison rapide en France.",
        'description': "<p>Ressortie des archives en 2020, la <strong>New Balance 550</strong> de 1989 est une chaussure de basketball au cuir premium et logo N en relief. Propulsée par la collaboration avec <strong>Aimé Leon Dore</strong>, elle incarne le revival du design vintage des années 80.</p><p>Son esthétique rétro épurée et ses déclinaisons infinies en font l'un des modèles les plus populaires du moment. De la <strong>White Green</strong> à la <strong>Sea Salt</strong>, chaque coloris raconte une histoire différente.</p><p>Retrouvez toutes les New Balance 550 sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'new-balance-530': {
        'meta_title': 'New Balance 530 - Sneakers NB pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les New Balance 530 sur KP SHOES. White Silver, tous les coloris disponibles. 100% authentiques, livraison rapide en France.",
        'description': "<p>La <strong>New Balance 530</strong>, modèle running des années 90, séduit par son design chunky avec sa technologie ABZORB et sa tige en mesh/synthétique. Son esthétique Y2K et son confort quotidien en font une silhouette très demandée.</p><p>Retrouvez toutes les New Balance 530 sur <strong>KP SHOES</strong>, 100% authentiques et vérifiées par nos experts.</p>",
    },
    'new-balance-2002r': {
        'meta_title': 'New Balance 2002R - Sneakers NB pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre New Balance 2002R sur KP SHOES. Protection Pack, Rain Cloud... 100% authentiques, livraison rapide en France.",
        'description': "<p>La <strong>New Balance 2002R</strong> combine les technologies N-ERGY et ABZORB SBS pour un confort premium. Son upper en daim et mesh avec sa silhouette arrondie est devenue un favori du streetwear contemporain.</p><p>Du <strong>Protection Pack</strong> aux éditions saisonnières, la 2002R séduit par son équilibre entre technique et style. Retrouvez toutes les New Balance 2002R sur <strong>KP SHOES</strong>.</p>",
    },
    'new-balance-9060': {
        'meta_title': 'New Balance 9060 - Sneakers NB pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les New Balance 9060 sur KP SHOES. Sea Salt, Rain Cloud... Design futuriste, 100% authentiques. Livraison rapide en France.",
        'description': "<p>Sortie en 2022, la <strong>New Balance 9060</strong> fusionne des éléments de la 990, 860 et 2002R pour créer une silhouette futuriste. Ses lignes exagérées, ses superpositions de daim/mesh et son amorti FuelCell en font un modèle d'avant-garde plébiscité par la nouvelle génération.</p><p>Retrouvez toutes les New Balance 9060 sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'asics-gel-1130': {
        'meta_title': 'Asics Gel-1130 - Sneakers Asics pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre Asics Gel-1130 sur KP SHOES. White Clay Canyon, Black Silver... 100% authentiques, livraison rapide en France.",
        'description': "<p>Sortie en 2008, l'<strong>Asics Gel-1130</strong> a resurgi sur la scène streetwear grâce à sa silhouette technique Y2K. Sa technologie Gel au talon, son upper en mesh/synthétique et son look rétro-technique sont devenus irrésistibles.</p><p>Retrouvez toutes les Asics Gel-1130 sur <strong>KP SHOES</strong>, 100% authentiques et vérifiées.</p>",
    },
    'asics-gel-kayano': {
        'meta_title': 'Asics Gel-Kayano 14 - Sneakers Asics pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Asics Gel-Kayano sur KP SHOES. Kayano 14, tous les coloris. 100% authentiques, livraison rapide en France.",
        'description': "<p>Lancée en 1993 par Toshikazu Kayano, l'<strong>Asics Gel-Kayano</strong> est la référence des chaussures de running stabilisantes. La version <strong>Kayano 14</strong>, sortie en 2008, impressionne par son design ultra-technique avec gel visible et technologie IGS — le modèle le plus prisé des amateurs de gorpcore.</p><p>Retrouvez toutes les Asics Gel-Kayano sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'asics-gel-nyc': {
        'meta_title': 'Asics Gel-NYC - Sneakers Asics pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre Asics Gel-NYC sur KP SHOES. Graphite Grey, Cream... Design hybride unique, 100% authentiques. Livraison rapide.",
        'description': "<p>Sortie en 2023, l'<strong>Asics Gel-NYC</strong> fusionne le Gel-Nimbus 3 et le MC Plus V pour une silhouette inédite. Son design hybride avec gel apparent, daim et mesh en fait l'une des sorties les plus remarquées de la marque japonaise.</p><p>Retrouvez toutes les Asics Gel-NYC sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'ugg-tasman': {
        'meta_title': 'UGG Tasman - Chaussures UGG pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre UGG Tasman sur KP SHOES. Chestnut, Black, Sand... Peau de mouton authentique, livraison rapide en France.",
        'description': "<p>La <strong>UGG Tasman</strong> combine l'iconique peau de mouton UGG avec un design slip-on inspiré du mocassin. Sa doublure en laine mérinos de 17mm, sa semelle Treadlite et ses coutures tressées offrent un confort exceptionnel en toute saison.</p><p>Disponible en <strong>Chestnut</strong>, <strong>Black</strong>, <strong>Sand</strong> et d'autres coloris, la Tasman est devenue un incontournable du style casual. Retrouvez toutes les UGG Tasman sur <strong>KP SHOES</strong>.</p>",
    },
    'ugg-tazz': {
        'meta_title': 'UGG Tazz - Chaussures UGG pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les UGG Tazz sur KP SHOES. Sand, Chestnut, Black... Semelle plateforme, peau de mouton. 100% authentiques, livraison rapide.",
        'description': "<p>La <strong>UGG Tazz</strong> revisite le classique Tasman avec une semelle plateforme en EVA qui ajoute 3cm de hauteur. Même confort en peau de mouton, même facilité d'enfilage, avec un twist contemporain qui a conquis les réseaux sociaux.</p><p>Retrouvez toutes les UGG Tazz sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'ugg-ultra-mini': {
        'meta_title': 'UGG Ultra Mini - Boots UGG pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre UGG Ultra Mini sur KP SHOES. Chestnut, Black, Mustard Seed... Peau de mouton recyclée, livraison rapide en France.",
        'description': "<p>La <strong>UGG Ultra Mini</strong> est la version compacte du classique boot UGG. Sa tige ultra-courte, sa doublure en peau de mouton recyclée et sa semelle Treadlite en font la boot parfaite pour un style décontracté toute l'année.</p><p>Retrouvez toutes les UGG Ultra Mini sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'travis-scott': {
        'meta_title': 'Travis Scott x Nike - Sneakers Cactus Jack en Édition Limitée | KP SHOES',
        'meta_description': "Toutes les Travis Scott x Nike sur KP SHOES. Jordan 1, Dunk, Air Max... Swoosh inversé, éditions limitées 100% authentiques.",
        'description': "<p>Les collaborations <strong>Travis Scott x Nike</strong>, lancées en 2019, ont révolutionné le marché sneaker. Le <strong>Swoosh inversé</strong> est devenu la signature de Cactus Jack, tandis que les coloris terreux inspirés de Houston et les détails cachés (poches secrètes, languettes multiples) font de chaque paire une pièce de collection.</p><p>De la <strong>Air Jordan 1 High Mocha</strong> à la <strong>SB Dunk Low</strong>, en passant par les <strong>Air Jordan 4</strong> et les <strong>Air Max 1</strong>, chaque release Travis Scott génère un engouement sans précédent et une prise de valeur immédiate.</p><p>Retrouvez toutes les Travis Scott x Nike sur <strong>KP SHOES</strong>, 100% authentiques et vérifiées.</p>",
    },
    'off-white': {
        'meta_title': 'Off-White x Nike - Sneakers Virgil Abloh en Édition Limitée | KP SHOES',
        'meta_description': "Toutes les Off-White x Nike sur KP SHOES. The Ten, Jordan, Dunk... Éditions limitées de Virgil Abloh, 100% authentiques.",
        'description': "<p>Les collaborations <strong>Off-White x Nike</strong> imaginées par <strong>Virgil Abloh</strong> ont redéfini le concept de sneaker en 2017 avec la collection <em>The Ten</em>. L'esthétique déconstructiviste — zip-ties oranges, inscriptions entre guillemets, Swoosh décalé — a créé un mouvement qui a influencé toute l'industrie.</p><p>De la <strong>Air Jordan 1 Chicago</strong> à la <strong>Dunk Low</strong>, en passant par les <strong>Air Force 1</strong> et <strong>Air Max 90</strong>, chaque modèle Off-White est devenu un grail dont la valeur ne cesse de monter, en hommage à la vision créative de Virgil Abloh.</p><p>Retrouvez toutes les Off-White x Nike sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'supreme': {
        'meta_title': 'Supreme x Nike - Sneakers Supreme en Édition Limitée | KP SHOES',
        'meta_description': "Toutes les Supreme x Nike sur KP SHOES. Dunk, Air Force 1, Air Max... Éditions limitées 100% authentiques. Livraison rapide.",
        'description': "<p>Depuis les années 2000, les collaborations <strong>Supreme x Nike</strong> sont devenues des événements majeurs de la culture streetwear. La marque new-yorkaise fondée par James Jebbia apporte son esthétique audacieuse aux silhouettes iconiques de Nike.</p><p>Des <strong>SB Dunk Low</strong> aux <strong>Air Force 1</strong> en passant par les <strong>Air Max</strong>, chaque collaboration Supreme est une pièce de collection recherchée. Retrouvez-les sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'tous-nos-vetements': {
        'meta_title': 'Streetwear - Hoodies, T-shirts et Joggers Premium | KP SHOES',
        'meta_description': "Découvrez notre collection streetwear sur KP SHOES. Fear of God Essentials, hoodies, t-shirts, joggers. 100% authentiques, livraison rapide.",
        'description': "<p>Découvrez notre sélection de <strong>vêtements streetwear premium</strong> sur KP SHOES. Des pièces essentielles signées <strong>Fear of God Essentials</strong> : hoodies en molleton épais, joggings à coupe oversize, t-shirts en jersey de coton premium et shorts décontractés.</p><p>Créée par <strong>Jerry Lorenzo</strong>, la ligne Essentials incarne le luxe minimaliste avec des basiques élevés au rang de pièces mode. Chaque vêtement se distingue par sa coupe oversize signature, ses matériaux de haute qualité et le logo Essentials discret.</p><p>Tous nos articles sont <strong>100% authentiques</strong> et vérifiés par nos experts avant expédition.</p>",
    },
    # Collections de marques
    'jordan-1': {
        'meta_title': 'Air Jordan - Sneakers Jordan pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les sneakers Jordan sur KP SHOES. Air Jordan 1, 3, 4, 5, 11... Tous les modèles et coloris, 100% authentiques. Livraison rapide.",
        'description': "<p><strong>Jordan Brand</strong>, né de la collaboration entre Michael Jordan et Nike en 1984, est devenu bien plus qu'une marque de sneakers — c'est un symbole culturel. De la <strong>Air Jordan 1</strong> bannie par la NBA en 1985 aux collaborations modernes avec Travis Scott et Off-White, chaque modèle raconte un chapitre de l'histoire du sport et du streetwear.</p><p>Retrouvez tous les modèles Jordan sur <strong>KP SHOES</strong> : Air Jordan 1 High, Mid, Low, Air Jordan 3, 4, 5, 6, 11, 12, 13... Tous 100% authentiques.</p>",
    },
    'nike-1': {
        'meta_title': 'Nike - Sneakers Nike pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les sneakers Nike sur KP SHOES. Dunk, Air Force 1, Air Max, Vomero... Tous les modèles, 100% authentiques. Livraison rapide.",
        'description': "<p><strong>Nike</strong>, fondée en 1964 par Phil Knight et Bill Bowerman, est le leader mondial de l'équipement sportif. De la <strong>Air Force 1</strong> à la <strong>Dunk</strong>, de la <strong>Air Max</strong> aux collaborations avec les plus grands artistes et designers, Nike définit la culture sneakers depuis plus de 50 ans.</p><p>Retrouvez toutes les sneakers Nike sur <strong>KP SHOES</strong>, 100% authentiques et vérifiées par nos experts.</p>",
    },
    'adidas-1': {
        'meta_title': 'Adidas - Sneakers Adidas pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les sneakers Adidas sur KP SHOES. Samba, Campus, Gazelle, Forum, Spezial... 100% authentiques, livraison rapide en France.",
        'description': "<p><strong>Adidas</strong>, fondée en 1949 par Adi Dassler à Herzogenaurach en Allemagne, est un pilier de la culture sportive et streetwear mondiale. Des trois bandes iconiques à l'héritage terrace culture, Adidas allie tradition et innovation depuis plus de 75 ans.</p><p>Retrouvez les <strong>Samba</strong>, <strong>Campus</strong>, <strong>Gazelle</strong>, <strong>Spezial</strong>, <strong>Forum</strong> et toutes les sneakers Adidas sur <strong>KP SHOES</strong>. 100% authentiques.</p>",
    },
    'yeezy-1': {
        'meta_title': 'Yeezy - Sneakers Yeezy pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Yeezy sur KP SHOES. 350 V2, 700, Slide, Foam Runner... Kanye West x Adidas, 100% authentiques. Livraison rapide.",
        'description': "<p>La gamme <strong>Yeezy</strong>, née de la collaboration entre Kanye West et Adidas, a bouleversé l'industrie sneakers dès 2015. Du <strong>Boost 350 V2</strong> à la <strong>Foam Runner</strong>, en passant par la <strong>700 Wave Runner</strong> et la <strong>Slide</strong>, chaque modèle a redéfini les codes du design et du marché.</p><p>Retrouvez toutes les Yeezy sur <strong>KP SHOES</strong>, 100% authentiques et vérifiées.</p>",
    },
    'new-balance-1': {
        'meta_title': 'New Balance - Sneakers NB pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les New Balance sur KP SHOES. 550, 530, 2002R, 9060, 990... Tous les modèles, 100% authentiques. Livraison rapide en France.",
        'description': "<p><strong>New Balance</strong>, fondée en 1906 à Boston, se distingue par son approche premium et son savoir-faire artisanal. Des modèles <strong>Made in USA</strong> et <strong>Made in UK</strong> aux collaborations avec Aimé Leon Dore et JJJJound, New Balance incarne le confort et l'élégance discrète.</p><p>Retrouvez les <strong>550</strong>, <strong>530</strong>, <strong>2002R</strong>, <strong>9060</strong>, <strong>990</strong> et toutes les New Balance sur <strong>KP SHOES</strong>.</p>",
    },
    'asics-1': {
        'meta_title': 'Asics - Sneakers Asics pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Asics sur KP SHOES. Gel-1130, Gel-Kayano, Gel-NYC, GT-2160... 100% authentiques, livraison rapide en France.",
        'description': "<p><strong>Asics</strong> (Anima Sana In Corpore Sano), marque japonaise fondée en 1949, est synonyme de performance et d'innovation technique. Sa technologie <strong>Gel</strong> brevetée a révolutionné l'amorti dans le running.</p><p>Retrouvez les <strong>Gel-1130</strong>, <strong>Gel-Kayano 14</strong>, <strong>Gel-NYC</strong>, <strong>GT-2160</strong> et toutes les Asics sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'ugg-1': {
        'meta_title': 'UGG - Boots et Slides UGG pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les UGG sur KP SHOES. Tasman, Tazz, Ultra Mini, Classic Mini... Peau de mouton authentique, livraison rapide en France.",
        'description': "<p><strong>UGG</strong>, marque californienne fondée en 1978, est devenue synonyme de confort premium grâce à sa doublure en peau de mouton signature. De la <strong>Classic Mini</strong> à la <strong>Tasman</strong>, de la <strong>Tazz</strong> à la <strong>Ultra Mini</strong>, chaque modèle offre un confort inégalé.</p><p>Retrouvez toutes les UGG sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'puma-1': {
        'meta_title': 'Puma - Sneakers Puma pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Puma sur KP SHOES. Speedcat, Suede, LaMelo Ball... 100% authentiques, livraison rapide en France.",
        'description': "<p><strong>Puma</strong>, fondée en 1948 par Rudolf Dassler (frère d'Adi Dassler), est une marque sportive au riche héritage. De la <strong>Suede</strong> adoptée par le hip-hop aux <strong>Speedcat</strong> inspirées de la Formule 1, Puma allie sport et style depuis plus de 75 ans.</p><p>Retrouvez toutes les Puma sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'crocs': {
        'meta_title': 'Crocs - Classic Clog et Slides pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Crocs sur KP SHOES. Classic Clog, Slides, collaborations... Confort Croslite, 100% authentiques. Livraison rapide.",
        'description': "<p>Inventées en 2002, les <strong>Crocs</strong> sont devenues un phénomène mondial grâce à leur matériau breveté Croslite ultra-léger et confortable. Personnalisables avec les <strong>Jibbitz</strong>, elles sont passées des blocs opératoires aux podiums de mode.</p><p>Retrouvez toutes les Crocs sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'birkenstock-1': {
        'meta_title': 'Birkenstock - Sandales Birkenstock pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Birkenstock sur KP SHOES. Arizona, Boston... Semelle en liège anatomique, 100% authentiques. Livraison rapide.",
        'description': "<p>Fabriquées en Allemagne depuis 1774, les <strong>Birkenstock</strong> sont célèbres pour leur semelle anatomique en liège et latex naturel qui s'adapte à la forme du pied. Un confort orthopédique devenu symbole de style normcore.</p><p>Retrouvez toutes les Birkenstock sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'salomon': {
        'meta_title': 'Salomon - Sneakers Trail Salomon pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Salomon sur KP SHOES. XT-6, ACS Pro, trail outdoor... Technologie Contagrip, 100% authentiques. Livraison rapide.",
        'description': "<p>Marque française d'Annecy depuis 1947, <strong>Salomon</strong> a conquis le streetwear avec ses modèles trail comme la <strong>XT-6</strong> et l'<strong>ACS Pro</strong>. Technologie Contagrip, design technique et résistance aux éléments font de Salomon la marque outdoor préférée du mouvement gorpcore.</p><p>Retrouvez toutes les Salomon sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'converse': {
        'meta_title': 'Converse - Chuck Taylor et Chuck 70 pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Converse sur KP SHOES. Chuck Taylor, Chuck 70... Les sneakers les plus iconiques, 100% authentiques. Livraison rapide.",
        'description': "<p>Les <strong>Converse Chuck Taylor</strong>, créées en 1917, sont les sneakers les plus vendues de tous les temps. Toile de coton, semelle vulcanisée et patch étoile All-Star : un symbole universel de la culture jeune qui traverse les générations.</p><p>Retrouvez toutes les Converse sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'timberland': {
        'meta_title': 'Timberland - Boots Timberland pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Timberland sur KP SHOES. 6-Inch Premium Boot, Wheat, Black... Cuir nubuck imperméable, 100% authentiques. Livraison rapide.",
        'description': "<p>Les <strong>Timberland 6-Inch Premium</strong>, surnommées Timbs, sont un symbole du hip-hop et de la culture urbaine depuis les années 90. Cuir nubuck imperméable, semelle anti-fatigue et durabilité légendaire en font un classique toutes saisons.</p><p>Retrouvez toutes les Timberland sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'tout-nos-modeles': {
        'meta_title': 'Toutes nos Sneakers - Sneakers pour Homme et Femme | KP SHOES',
        'meta_description': "Parcourez l'ensemble de nos sneakers sur KP SHOES. Nike, Jordan, Adidas, New Balance, Yeezy, Asics... 100% authentiques, livraison rapide.",
        'description': "<p>Découvrez l'intégralité de notre catalogue sur <strong>KP SHOES</strong>. Plus de 2 500 modèles de sneakers authentiques des plus grandes marques : <strong>Nike</strong>, <strong>Jordan</strong>, <strong>Adidas</strong>, <strong>New Balance</strong>, <strong>Yeezy</strong>, <strong>Asics</strong>, <strong>UGG</strong> et bien d'autres.</p><p>Chaque paire est <strong>100% authentique</strong>, vérifiée par nos experts et livrée dans sa boîte d'origine. Livraison rapide en France et paiement sécurisé.</p>",
    },
    'best-seller': {
        'meta_title': 'Meilleures Ventes - Sneakers les Plus Populaires | KP SHOES',
        'meta_description': "Nos best-sellers : les sneakers les plus populaires du moment sur KP SHOES. Testées et approuvées, 100% authentiques. Livraison rapide.",
        'description': "<p>Découvrez les <strong>sneakers les plus vendues</strong> du moment sur KP SHOES. Notre sélection best-sellers regroupe les modèles les plus demandés : <strong>Nike Dunk Low</strong>, <strong>Air Jordan 1</strong>, <strong>Adidas Samba</strong>, <strong>New Balance 550</strong> et bien d'autres.</p><p>Tous nos produits sont <strong>100% authentiques</strong> et vérifiés par nos experts avant expédition.</p>",
    },
    'moins-de-150': {
        'meta_title': 'Sneakers à Moins de 150€ - Bons Plans Sneakers | KP SHOES',
        'meta_description': "Des sneakers tendance à moins de 150€ sur KP SHOES. Nike, Adidas, New Balance... Petit prix, grande qualité. 100% authentiques.",
        'description': "<p>Découvrez notre sélection de <strong>sneakers à moins de 150€</strong> sur KP SHOES. Des modèles tendance des plus grandes marques à prix accessible, sans compromis sur l'authenticité.</p><p><strong>Nike</strong>, <strong>Adidas</strong>, <strong>New Balance</strong>, <strong>Asics</strong>... Trouvez votre paire idéale sans vous ruiner. Toutes 100% authentiques et vérifiées.</p>",
    },
    'livraison-48h': {
        'meta_title': 'Livraison 48h - Sneakers Livrées en Express | KP SHOES',
        'meta_description': "Recevez vos sneakers en 48h avec KP SHOES. Sélection de modèles disponibles en livraison express. 100% authentiques.",
        'description': "<p>Besoin de vos sneakers rapidement ? Découvrez notre sélection <strong>livraison en 48h</strong>. Ces modèles sont en stock dans notre entrepôt et expédiés immédiatement pour une réception ultra-rapide.</p><p>Même garantie d'<strong>authenticité</strong>, même qualité de service, en deux fois moins de temps.</p>",
    },
    'pour-enfants': {
        'meta_title': 'Sneakers Enfant - Nike, Jordan, Adidas pour Kids | KP SHOES',
        'meta_description': "Sneakers pour enfants sur KP SHOES. Nike, Jordan, Adidas, New Balance... Confort, style et durabilité. 100% authentiques, livraison rapide.",
        'description': "<p>Découvrez notre sélection de <strong>sneakers pour enfants</strong> sur KP SHOES. Les plus grandes marques — <strong>Nike</strong>, <strong>Jordan</strong>, <strong>Adidas</strong>, <strong>New Balance</strong> — dans des tailles kids et junior.</p><p>Confort, style et durabilité pour accompagner chaque aventure. Toutes <strong>100% authentiques</strong> et livrées dans leur boîte d'origine.</p>",
    },
    'sport': {
        'meta_title': 'Sneakers Sport - Performance et Running | KP SHOES',
        'meta_description': "Sneakers sport et running sur KP SHOES. Nike, Asics, New Balance... Performance et style réunis. 100% authentiques, livraison rapide.",
        'description': "<p>Découvrez notre sélection de <strong>sneakers sport et performance</strong> sur KP SHOES. Des modèles pensés pour l'entraînement, la course et le quotidien actif, signés <strong>Nike</strong>, <strong>Asics</strong>, <strong>New Balance</strong> et <strong>Adidas</strong>.</p><p>Performance, confort et style réunis. Toutes <strong>100% authentiques</strong>.</p>",
    },
    'autre-marques': {
        'meta_title': 'Autres Marques - Dior, Puma, Crocs et Plus | KP SHOES',
        'meta_description': "Découvrez nos autres marques sur KP SHOES. Dior, Puma, Crocs, Birkenstock, Salomon... 100% authentiques, livraison rapide en France.",
        'description': "<p>Au-delà des incontournables, <strong>KP SHOES</strong> propose une sélection de marques premium : <strong>Dior</strong>, <strong>Puma</strong>, <strong>Crocs</strong>, <strong>Birkenstock</strong>, <strong>Salomon</strong>, <strong>Converse</strong>, <strong>Vans</strong> et plus encore.</p><p>Tous nos produits sont <strong>100% authentiques</strong> et vérifiés par nos experts.</p>",
    },
    'stock-x-sneakers': {
        'meta_title': 'Stock X Sneakers - Baskets en Édition Limitée | KP SHOES',
        'meta_description': "Découvrez le lien entre le Stock et les Sneakers \"Stock x Sneakers\" qui impacte le prix et la hype sur ces modèles de baskets en éditions limitées.",
        'description': "<p>Le marché de la revente de sneakers, souvent désigné par l'expression <strong>Stock X Sneakers</strong>, connaît une croissance exponentielle depuis plusieurs années. La demande pour les sneakers en édition limitée ne cesse d'augmenter, notamment pour les modèles des marques les plus populaires comme <strong>Nike</strong>, <strong>Jordan</strong>, <strong>Adidas</strong>, <strong>New Balance</strong> ou <strong>UGG</strong>. Cette forte demande crée une pression sur les stocks disponibles, rendant certaines paires particulièrement rares et convoitées.</p><p>L'équation est simple : des stocks limités face à une demande massive font grimper les prix et la hype autour de ces modèles. Prenons l'exemple des <strong>Adidas Samba</strong> ou des <strong>Nike Dunk Low</strong> : initialement vendues autour d'une centaine d'euros, certaines éditions valent désormais le double, voire le triple, en raison de leur popularité qui a rapidement épuisé les stocks. Ce phénomène touche toutes les grandes marques : le stock Jordan, le stock Nike, le stock Adidas, le stock UGG — tous sont impactés par ces tendances.</p><p>Face à cette rareté, les plateformes de revente de sneakers comme <strong>StockX</strong>, <strong>GOAT</strong> et <strong>Flight Club</strong> sont devenues des acteurs incontournables du marché. StockX, fondée en 2016 par Josh Luber et Dan Gilbert, s'est imposée grâce à son système de vérification d'authenticité et son modèle inspiré de la bourse. GOAT, créée en 2015 par Eddy Lu et Daishin Sugano, a développé le système « ship-to-verify » pour garantir l'authenticité de chaque paire. Ces marketplaces sont devenues des alliés précieux pour les passionnés à la recherche de modèles introuvables.</p><p>Chez <strong>KP SHOES</strong>, nous proposons une alternative fiable à ces grandes plateformes. Notre sélection de sneakers en édition limitée est <strong>100% authentique</strong>, vérifiée par nos experts, et livrée rapidement en France. Que vous cherchiez des <strong>Air Jordan 4</strong>, des <strong>Nike Dunk</strong>, des <strong>Yeezy</strong> ou des <strong>New Balance 550</strong>, retrouvez les modèles les plus recherchés du marché à des prix compétitifs, sans les frais et délais des plateformes internationales.</p>",
    },
    'ugg-lowmel': {
        'meta_title': 'UGG Lowmel - Chaussures UGG pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre UGG Lowmel sur KP SHOES. Chestnut, Black, Sand... Design hybride mule-clog en peau de mouton. 100% authentiques, livraison rapide.",
        'description': "<p>La <strong>UGG Lowmel</strong> est un hybride entre la mule et le clog qui fusionne le confort signature UGG avec un design contemporain. Sa tige basse en daim premium, sa doublure en peau de mouton et sa semelle plateforme en EVA offrent un confort exceptionnel dans un profil tendance facile à enfiler.</p><p>Disponible en <strong>Chestnut</strong>, <strong>Black</strong> et d'autres coloris, la Lowmel est devenue un incontournable du style décontracté. Retrouvez toutes les UGG Lowmel sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'ugg-classic-mini': {
        'meta_title': 'UGG Classic Mini - Boots UGG pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les UGG Classic Mini sur KP SHOES. Chestnut, Black... La boot iconique en peau de mouton. 100% authentiques, livraison rapide en France.",
        'description': "<p>La <strong>UGG Classic Mini</strong> est la version raccourcie de l'iconique Classic Boot, avec une tige qui arrive à la cheville. Sa doublure en peau de mouton de 17mm, son upper en daim Twinface et sa semelle Treadlite légère en font la boot parfaite pour un confort quotidien.</p><p>Silhouette la plus polyvalente de la gamme UGG, la Classic Mini se porte aussi bien avec un jean qu'avec un jogging. Disponible en <strong>Chestnut</strong>, <strong>Black</strong>, <strong>Grey</strong> et d'autres coloris. Retrouvez-la sur <strong>KP SHOES</strong>, 100% authentique.</p>",
    },
    'nouveautes': {
        'meta_title': 'Nouveautés - Dernières Sneakers Disponibles | KP SHOES',
        'meta_description': "Découvrez les dernières sorties sneakers sur KP SHOES. Nouveautés Nike, Jordan, Adidas, New Balance... 100% authentiques, livraison rapide.",
        'description': "<p>Restez à la pointe des tendances avec les <strong>dernières sorties sneakers</strong> disponibles sur KP SHOES. Chaque semaine, de nouveaux modèles <strong>Nike</strong>, <strong>Jordan</strong>, <strong>Adidas</strong>, <strong>New Balance</strong>, <strong>Asics</strong> et d'autres marques viennent enrichir notre catalogue.</p><p>Des releases les plus attendues aux drops surprise, retrouvez les nouveautés sneakers avant tout le monde. Toutes nos paires sont <strong>100% authentiques</strong> et livrées rapidement en France.</p>",
    },
    'pata': {
        'meta_title': 'Patta - Sneakers Patta en Édition Limitée | KP SHOES',
        'meta_description': "Toutes les Patta sur KP SHOES. Patta x Nike Air Max 1, collaborations... Éditions limitées 100% authentiques. Livraison rapide en France.",
        'description': "<p>Fondé en 2004 à Amsterdam par Edson Sabajo et Guillaume Schmidt, <strong>Patta</strong> est un label streetwear devenu une référence mondiale grâce à ses collaborations exceptionnelles avec Nike. Le shop néerlandais, dont le nom signifie « chaussure » en surinamais, est né d'une passion commune pour les sneakers rares, et plus particulièrement pour la gamme Air Max.</p><p>La collaboration <strong>Patta x Nike Air Max 1</strong> est devenue légendaire. Du « 5th Anniversary Pack » de 2009 avec l'iconique coloris Chlorophyll au « Wave Pack » de 2021 qui a révolutionné le mudguard de la AM1, chaque release Patta crée l'événement. Les coloris <strong>Monarch</strong>, <strong>Noise Aqua</strong>, <strong>Rush Maroon</strong> et <strong>Black</strong> sont devenus des grails instantanés.</p><p>Retrouvez toutes les sneakers Patta sur <strong>KP SHOES</strong>, 100% authentiques et vérifiées.</p>",
    },
    'nike-sb': {
        'meta_title': 'Nike SB - Sneakers Nike Skateboarding pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Nike SB sur KP SHOES. SB Dunk Low, SB Dunk High... Sneakers de skate en édition limitée, 100% authentiques. Livraison rapide.",
        'description': "<p>Créée en 2002, la division <strong>Nike SB</strong> (Skateboarding) a révolutionné le monde du skate et de la sneaker. En adaptant la Dunk de 1985 aux exigences du skateboard — semelle Zoom Air, languette rembourrée, renforts latéraux — Nike a donné naissance à certains des modèles les plus convoités de l'histoire.</p><p>Les collaborations Nike SB sont devenues légendaires : la <strong>SB Dunk Low Paris</strong> (200 paires), la <strong>Pigeon</strong> de Jeff Staple qui a provoqué des émeutes à New York, les éditions <strong>Supreme</strong>, <strong>Travis Scott</strong>, <strong>Ben &amp; Jerry's Chunky Dunky</strong>... Chaque drop SB est un événement pour les collectionneurs du monde entier.</p><p>Retrouvez toutes les Nike SB sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'new-balance-740': {
        'meta_title': 'New Balance 740 - Sneakers NB 740 pour Homme et Femme | KP SHOES',
        'meta_description': "Achetez votre New Balance 740 sur KP SHOES. Tous les coloris disponibles. Design trail rétro, 100% authentiques. Livraison rapide en France.",
        'description': "<p>La <strong>New Balance 740</strong> est un modèle trail des années 2000 qui revient en force sur la scène streetwear. Sa silhouette robuste, ses superpositions en mesh et synthétique, et son amorti ABZORB en font une pièce technique au look outdoor recherché.</p><p>Adoptée par le mouvement gorpcore, la 740 séduit par son esthétique brute et ses coloris terreux. Retrouvez toutes les New Balance 740 sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'dior': {
        'meta_title': 'Dior - Sneakers Dior B23 et Plus | KP SHOES',
        'meta_description': "Sneakers Dior sur KP SHOES. B23 High, B23 Low... Luxe et streetwear réunis. 100% authentiques, livraison rapide en France.",
        'description': "<p>Les sneakers <strong>Dior</strong> incarnent la fusion entre haute couture et culture sneakers. La <strong>B23</strong>, dessinée par Kim Jones, est devenue un symbole du luxe streetwear avec son upper en toile oblique Dior transparente et sa silhouette high-top inspirée du basketball.</p><p>Disponible en versions <strong>High</strong> et <strong>Low</strong>, dans les coloris <strong>Oblique</strong> noir et blanc, la B23 est une pièce de collection qui mêle savoir-faire artisanal et design contemporain. Retrouvez les sneakers Dior sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
    'bape': {
        'meta_title': 'Bape - Sneakers Bape Sta pour Homme et Femme | KP SHOES',
        'meta_description': "Toutes les Bape sur KP SHOES. Bape Sta, camo... Streetwear japonais iconique. 100% authentiques, livraison rapide en France.",
        'description': "<p>Fondé en 1993 à Tokyo par Nigo, <strong>A Bathing Ape (Bape)</strong> est un pilier du streetwear japonais. La <strong>Bape Sta</strong>, inspirée de la silhouette des sneakers de basketball américaines, se distingue par son imprimé camouflage signature et son étoile filante sur le côté.</p><p>Adoptée par le hip-hop américain dans les années 2000 grâce à Pharrell Williams et Kanye West, la Bape Sta est devenue un symbole du streetwear premium. Retrouvez toutes les Bape sur <strong>KP SHOES</strong>, 100% authentiques.</p>",
    },
}


def get_collection_seo(handle):
    """Retourne le SEO optimisé pour une collection"""
    return COLLECTION_SEO.get(handle, None)


def update_collection_seo(collection_id, handle):
    """Applique le SEO optimisé à une collection Shopify"""
    seo = get_collection_seo(handle)
    if not seo:
        return False
    
    # Déterminer le type (custom ou smart)
    for ctype in ['custom_collections', 'smart_collections']:
        singular = ctype.rstrip('s')
        r = shopify_request(f'{ctype}/{collection_id}.json')
        if r and singular in r:
            update_data = {singular: {
                'id': collection_id,
                'body_html': '<div style="display:none">' + seo['description'] + '</div>',
            }}
            shopify_request(f'{ctype}/{collection_id}.json', 'PUT', update_data)
            time.sleep(0.3)
            
            # Meta title & description via metafields
            shopify_request(f'collections/{collection_id}/metafields.json', 'POST',
                {'metafield': {'namespace': 'global', 'key': 'title_tag', 'value': seo['meta_title'], 'type': 'single_line_text_field'}})
            time.sleep(0.3)
            shopify_request(f'collections/{collection_id}/metafields.json', 'POST',
                {'metafield': {'namespace': 'global', 'key': 'description_tag', 'value': seo['meta_description'], 'type': 'single_line_text_field'}})
            return True
    return False

HOME_HTML = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KP SHOES - Gestion</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#0a0a0f;color:#fff;min-height:100vh}
.hd{background:#111;padding:15px 20px;border-bottom:1px solid #222;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:20px;font-weight:bold;color:#00ff88}
.stats{display:flex;gap:15px;padding:15px 20px;background:#0d0d14;flex-wrap:wrap}
.st{background:#1a1a2e;padding:12px 20px;border-radius:8px;text-align:center}
.st .v{font-size:24px;font-weight:bold;color:#00ff88}
.st .l{font-size:10px;color:#666;margin-top:3px}
.main{max-width:1400px;margin:0 auto;padding:20px}
.toolbar{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
.search{flex:1;min-width:200px;padding:10px 15px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#fff}
.filter{padding:10px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#fff}
.btn{padding:10px 20px;border:none;border-radius:8px;font-weight:600;cursor:pointer;font-size:12px}
.btn-s{background:#333;color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:15px}
.card{background:#111;border:1px solid #222;border-radius:10px;overflow:hidden;cursor:pointer;transition:all 0.2s}
.card:hover{border-color:#00ff88}
.card img{width:100%;height:180px;object-fit:cover;background:#1a1a2e}
.card-body{padding:12px}
.card-title{font-size:12px;font-weight:600;margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card-sku{font-size:10px;color:#666;margin-bottom:8px}
.card-meta{display:flex;justify-content:space-between;align-items:center}
.card-price{font-size:14px;font-weight:bold;color:#00ff88}
.badge{padding:3px 8px;border-radius:10px;font-size:9px;font-weight:600}
.badge.excellent{background:#00ff8833;color:#00ff88}
.badge.good{background:#00cc6a33;color:#00cc6a}
.badge.warning{background:#ffa50033;color:#ffa500}
.badge.poor{background:#ff475733;color:#ff4757}
.loading{text-align:center;padding:60px;color:#666}
.spinner{width:35px;height:35px;border:3px solid #222;border-top-color:#00ff88;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 15px}
@keyframes spin{to{transform:rotate(360deg)}}
.msg{padding:12px 20px;background:#00ff8815;color:#00ff88;border-radius:8px;margin-bottom:15px;display:none;font-size:13px}
.msg.on{display:block}
.modal-bg{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.85);z-index:9999;overflow-y:auto}
.modal-box{max-width:650px;margin:40px auto;background:#1a1a2e;border-radius:12px;padding:30px;color:#fff}
.modal-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
.modal-close{background:none;border:none;color:#fff;font-size:24px;cursor:pointer}
.opt-group{margin-bottom:20px}
.opt-label{font-size:13px;font-weight:600;color:#888;margin-bottom:10px}
.opt-radio,.opt-check{display:flex;align-items:center;gap:8px;cursor:pointer;font-size:14px;padding:8px 12px;background:#111;border-radius:6px;margin-bottom:6px}
.opt-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-left:10px}
.opt-sub{display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px;padding:8px;background:#0d0d14;border-radius:6px}
.prog-bar{background:#333;border-radius:6px;overflow:hidden;height:8px}
.prog-fill{width:0%;height:100%;background:linear-gradient(90deg,#00ff88,#00cc6a);transition:width .3s}
.issue-row{display:flex;align-items:center;gap:10px;padding:10px;background:#111;border-radius:6px;margin-bottom:6px}
.issue-bar{background:#333;border-radius:4px;height:6px;margin-top:4px}
</style>
</head>
<body>
<header class="hd">
<div class="logo">KP SHOES</div>
<div style="display:flex;gap:10px;align-items:center">
<a href="/blog-generator" style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:8px 16px;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600">&#10024; Blog</a>
<span style="color:#666;font-size:12px">V8</span>
</div>
</header>
<div class="stats">
<div class="st"><div class="v" id="totalP">-</div><div class="l">PRODUITS</div></div>
<div class="st"><div class="v" id="totalV">-</div><div class="l">VARIANTES</div></div>
<div class="st"><div class="v" id="seoAvg">-</div><div class="l">SEO MOY.</div></div>
<div class="st" style="cursor:pointer" onclick="window.location='/collections'"><div class="v" id="totalC">-</div><div class="l">COLLECTIONS &#8594;</div></div>
</div>
<main class="main">
<div class="msg" id="msg"></div>
<div class="toolbar">
<input type="text" class="search" id="q" placeholder="Rechercher un produit...">
<select class="filter" id="f"><option value="">Tous</option><option value="excellent">Excellent</option><option value="good">Bon</option><option value="warning">Moyen</option><option value="poor">Faible</option></select>
<button class="btn btn-s" onclick="reload()">&#8635; Actualiser</button>
<button class="btn btn-s" onclick="selectAll()">Tout cocher</button>
<button class="btn" style="background:#00ff88;color:#000" onclick="openCorrector()">&#128295; Corriger<span id="selBadge"></span></button>
<button class="btn" style="background:#3b82f6;color:#fff" onclick="openAnalyzer()">&#128270; Analyser</button>
</div>
<div id="selectCount" style="display:none;align-items:center;gap:10px;padding:8px 15px;background:#00ff8822;border-radius:8px;margin-bottom:15px;font-size:13px;color:#00ff88"></div>

<!-- ══════ MODAL CORRIGER ══════ -->
<div class="modal-bg" id="correctorModal">
<div class="modal-box">
<div class="modal-head">
<h2 style="margin:0;font-size:20px">&#128295; Corriger le site</h2>
<button class="modal-close" onclick="closeCorrector()">&times;</button>
</div>

<div class="opt-group">
<div class="opt-label">PORT&Eacute;E</div>
<label class="opt-radio"><input type="radio" name="corScope" value="all" checked> Tous les produits (<span id="corTotal">0</span>)</label>
<label class="opt-radio"><input type="radio" name="corScope" value="selection"> S&eacute;lection uniquement (<span id="corSel">0</span> coch&eacute;s)</label>
</div>

<div class="opt-group">
<div class="opt-label">QUE CORRIGER ?</div>
<label class="opt-check" style="margin-bottom:8px"><input type="checkbox" id="corAll" onchange="toggleCorAll()" style="accent-color:#00ff88;width:18px;height:18px"> <strong>Tout s&eacute;lectionner</strong></label>
<div class="opt-grid">
<label class="opt-sub"><input type="checkbox" class="corF" value="body_html" style="accent-color:#00ff88"> &#128221; Description</label>
<label class="opt-sub"><input type="checkbox" class="corF" value="meta_title" style="accent-color:#00ff88"> &#127991;&#65039; Meta Title</label>
<label class="opt-sub"><input type="checkbox" class="corF" value="meta_description" style="accent-color:#00ff88"> &#128203; Meta Description</label>
<label class="opt-sub"><input type="checkbox" class="corF" value="images_alt" style="accent-color:#00ff88"> &#128444;&#65039; Alt Photos</label>
<label class="opt-sub"><input type="checkbox" class="corF" value="images_filename" style="accent-color:#00ff88"> &#128193; Nom Photos</label>
</div>
</div>

<div id="corStatus" style="display:none;margin:15px 0;padding:12px;border-radius:8px;font-size:13px"></div>
<div id="corProg" style="display:none;margin:15px 0">
<div class="prog-bar"><div class="prog-fill" id="corBar"></div></div>
<div id="corTxt" style="text-align:center;font-size:12px;color:#aaa;margin-top:6px"></div>
</div>
<div style="display:flex;gap:10px">
<button id="corBtn" onclick="startCorrection()" style="flex:1;padding:14px;background:#00ff88;color:#000;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px">&#128640; Lancer la correction</button>
<button onclick="closeCorrector()" style="padding:14px 20px;background:#333;color:#fff;border:none;border-radius:8px;cursor:pointer">Fermer</button>
</div>
</div>
</div>

<!-- ══════ MODAL ANALYSER ══════ -->
<div class="modal-bg" id="analyzerModal">
<div class="modal-box" style="max-width:600px">
<div class="modal-head">
<h2 style="margin:0;font-size:20px">&#128270; Analyse SEO du site</h2>
<button class="modal-close" onclick="closeAnalyzer()">&times;</button>
</div>
<div id="azContent"></div>
<div style="display:flex;gap:10px;margin-top:15px">
<button onclick="closeAnalyzer()" style="padding:12px 20px;background:#333;color:#fff;border:none;border-radius:8px;cursor:pointer;width:100%">Fermer</button>
</div>
</div>
</div>

<div class="grid" id="grid"><div class="loading"><div class="spinner"></div>Chargement...</div></div>
</main>
<script>
var P=[],C=[],sinceId=0,loading=false,totalV=0,selectedPids=[];

function saveCache(){
    try{
        var lite=[];
        for(var i=0;i<P.length;i++){
            var p=P[i];
            lite.push({id:p.id,title:p.title,handle:p.handle,vendor:p.vendor,product_type:p.product_type,
                images:p.images?[{src:(p.images[0]||{}).src||"",alt:(p.images[0]||{}).alt||""}]:[],
                variants:p.variants?[{sku:(p.variants[0]||{}).sku||"",price:(p.variants[0]||{}).price||""}]:[],
                _lk:p._lk,_ds:p._ds,_img:p._img,_sc:p._sc,_seo:p._seo,tags:p.tags||""});
        }
        sessionStorage.setItem("kp_cache",JSON.stringify({P:lite,C:C,totalV:totalV,ts:Date.now()}));
    }catch(e){try{sessionStorage.removeItem("kp_cache")}catch(e2){}}
}
function loadCache(){
    try{
        var d=JSON.parse(sessionStorage.getItem("kp_cache")||"null");
        if(d&&d.P&&d.P.length>500&&(Date.now()-d.ts)<300000){
            P=d.P;C=d.C;totalV=d.totalV;sinceId=P[P.length-1].id;
            updateStats();filter();
            document.getElementById("msg").className="msg";
            return true;
        }
    }catch(e){}
    return false;
}

function load(){
    if(loading)return;loading=true;
    document.getElementById("msg").textContent="Chargement... "+P.length+" produits";
    document.getElementById("msg").className="msg on";
    fetch("/api/products?since_id="+sinceId+"&limit=250").then(function(r){return r.json()}).then(function(d){
        if(d.collections)C=d.collections;
        if(d.products&&d.products.length>0){
            for(var i=0;i<d.products.length;i++){
                var p=d.products[i];
                var b=(p.body_html||"").toLowerCase();
                p._lk=b.indexOf("kpshoes.fr/collections/")>=0;
                p._ds=(p.body_html||"").length>100;
                var imgOk=true;
                var titleFn=(p.title||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/ /g,"_").replace(/[^\\w\\-]/g,"_").replace(/_+/g,"_").replace(/^_|_$/g,"");
                if(p.images&&p.images.length>0){
                    for(var j=0;j<p.images.length;j++){
                        var alt=p.images[j].alt||"";
                        var src=p.images[j].src||"";
                        var fn=src.split("/").pop().split("?")[0];
                        if(alt!==p.title||fn.indexOf(titleFn)<0){imgOk=false;break}
                    }
                }else{imgOk=false}
                p._img=imgOk;
                var hasSku=!!((p.variants||[])[0]||{}).sku;
                var metaEst=(p._ds&&p._lk)?35:(p._ds?15:0);
                p._sc=metaEst+(p._ds?15:0)+(p._lk?15:0)+(p._img?20:0)+(hasSku?10:0);
                p._sc=Math.min(p._sc,100);
                if(p._sc>=85)p._seo="excellent";else if(p._sc>=70)p._seo="good";else if(p._sc>=50)p._seo="warning";else p._seo="poor";
                totalV+=(p.variants||[]).length;P.push(p);
            }
            sinceId=d.products[d.products.length-1].id;updateStats();filter();loading=false;
            if(d.products.length>=250)setTimeout(load,100);else{document.getElementById("msg").className="msg";saveCache()}
        }else{document.getElementById("msg").className="msg";loading=false;filter();saveCache()}
    }).catch(function(e){document.getElementById("msg").textContent="Erreur: "+e.message;loading=false});
}

function updateStats(){
    document.getElementById("totalP").textContent=P.length;
    document.getElementById("totalV").textContent=totalV;
    document.getElementById("totalC").textContent=C.length;
    var avg=0;for(var i=0;i<P.length;i++)avg+=P[i]._sc;
    avg=P.length?Math.round(avg/P.length):0;
    document.getElementById("seoAvg").textContent=avg+"%";
}

function filter(){
    var q=document.getElementById("q").value.toLowerCase();
    var f=document.getElementById("f").value;
    var L=[];for(var i=0;i<P.length;i++){var p=P[i];if(q&&p.title.toLowerCase().indexOf(q)<0)continue;if(f&&p._seo!==f)continue;L.push(p)}
    render(L);
}

function render(L){
    var el=document.getElementById("grid");
    if(!L.length&&!loading){el.innerHTML="<div class='loading'>Aucun produit</div>";return}
    var html="";var max=Math.min(L.length,100);
    for(var i=0;i<max;i++){
        var p=L[i];var img=(p.image&&p.image.src)?p.image.src.replace(/'/g,"%27"):((p.images&&p.images[0]&&p.images[0].src)?p.images[0].src.replace(/'/g,"%27"):"");        var sku=(p.variants&&p.variants[0])?p.variants[0].sku||"":"";
        var price=(p.variants&&p.variants[0])?p.variants[0].price:"0";
        var chk=selectedPids.indexOf(p.id)>=0?" checked":"";
        html+="<div class='card' style='position:relative' data-id='"+p.id+"'>";
        html+="<input type='checkbox'"+chk+" onclick='event.stopPropagation();toggleSel("+p.id+")' style='position:absolute;top:8px;left:8px;width:20px;height:20px;z-index:2;cursor:pointer;accent-color:#00ff88'>";
        html+="<img src='"+img+"' onclick='go("+p.id+")'><div class='card-body' onclick='go("+p.id+")'>";
        html+="<div class='card-title'>"+esc(p.title)+"</div><div class='card-sku'>"+sku+"</div>";
        html+="<div class='card-meta'><span class='card-price'>"+price+" EUR</span><span class='badge "+p._seo+"'>"+p._sc+"%</span></div>";
        html+="</div></div>";
    }
    el.innerHTML=html;updateSelCount();
}

function toggleSel(pid){var i=selectedPids.indexOf(pid);if(i>=0)selectedPids.splice(i,1);else selectedPids.push(pid);updateSelCount()}
function selectAll(){selectedPids=[];for(var i=0;i<P.length;i++)selectedPids.push(P[i].id);filter()}
function deselectAll(){selectedPids=[];filter()}
function updateSelCount(){
    var el=document.getElementById("selectCount");
    var badge=document.getElementById("selBadge");
    if(selectedPids.length>0){
        el.style.display="flex";
        el.innerHTML="<span>"+selectedPids.length+" produit"+(selectedPids.length>1?"s":"")+" coch&eacute;"+(selectedPids.length>1?"s":"")+"</span><button onclick='deselectAll()' style='background:none;border:none;color:#ff4757;cursor:pointer;font-size:12px;text-decoration:underline;margin-left:10px'>D&eacute;s&eacute;lectionner</button>";
        badge.textContent=" ("+selectedPids.length+")";
    }else{el.style.display="none";badge.textContent=""}
}
function esc(s){return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function go(id){window.location.href="/product/"+id}
function reload(){P=[];C=[];sinceId=0;totalV=0;try{sessionStorage.removeItem("kp_cache")}catch(e){}document.getElementById("grid").innerHTML="<div class='loading'><div class='spinner'></div>Chargement...</div>";load()}
document.getElementById("q").oninput=filter;
document.getElementById("f").onchange=filter;

/* ══════ CORRECTOR ══════ */
function toggleCorAll(){var c=document.getElementById("corAll").checked;var f=document.querySelectorAll(".corF");for(var i=0;i<f.length;i++)f[i].checked=c}
function openCorrector(){
    document.getElementById("correctorModal").style.display="block";
    document.getElementById("corSel").textContent=selectedPids.length;
    document.getElementById("corTotal").textContent=P.length;
    document.getElementById("corStatus").style.display="none";
    document.getElementById("corProg").style.display="none";
    var btn=document.getElementById("corBtn");btn.disabled=false;btn.textContent="\\uD83D\\uDE80 Lancer la correction";
    if(selectedPids.length>0)document.querySelector('input[name="corScope"][value="selection"]').checked=true;
    else document.querySelector('input[name="corScope"][value="all"]').checked=true;
}
function closeCorrector(){document.getElementById("correctorModal").style.display="none"}

function startCorrection(){
    var scope=document.querySelector('input[name="corScope"]:checked').value;
    var fields=[];var checks=document.querySelectorAll(".corF:checked");
    for(var i=0;i<checks.length;i++)fields.push(checks[i].value);
    if(!fields.length){alert("Coche au moins un element.");return}
    var pids=(scope==="selection")?selectedPids.slice():P.map(function(p){return p.id});
    if(!pids.length){alert("Aucun produit.");return}

    var seoFields=fields.filter(function(f){return f!=="images_alt"&&f!=="images_filename"});
    var doImg=fields.indexOf("images_alt")>=0||fields.indexOf("images_filename")>=0;

    var btn=document.getElementById("corBtn");
    var status=document.getElementById("corStatus");
    var bar=document.getElementById("corBar");
    var txt=document.getElementById("corTxt");
    btn.disabled=true;btn.textContent="Correction en cours...";
    status.style.display="block";status.style.background="#333";status.style.color="#aaa";
    document.getElementById("corProg").style.display="block";bar.style.width="0%";

    var done=0,errs=0;
    function next(){
        if(done>=pids.length){
            bar.style.width="100%";txt.textContent=done+"/"+pids.length;
            status.style.background="#00ff8822";status.style.color="#00ff88";
            status.textContent="\\u2705 "+done+" produits corrig\\u00e9s"+(errs?" ("+errs+" erreurs)":"");
            btn.textContent="\\u2705 Termin\\u00e9!";return;
        }
        bar.style.width=Math.round(done/pids.length*100)+"%";
        txt.textContent=(done+1)+"/"+pids.length;
        status.textContent="\\u23F3 Produit "+(done+1)+"/"+pids.length+"...";
        var promises=[];
        if(seoFields.length>0)promises.push(fetch("/api/seo/update",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:pids[done],fields:seoFields})}).then(function(r){return r.json()}));
        if(doImg)promises.push(fetch("/api/images/fix",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:pids[done]})}).then(function(r){return r.json()}));
        Promise.all(promises).then(function(){done++;setTimeout(next,50)}).catch(function(){errs++;done++;setTimeout(next,50)});
    }
    next();
}

/* ══════ ANALYZER ══════ */
var azProblems=[];
var azIssues={};
function openAnalyzer(){
    document.getElementById("analyzerModal").style.display="block";
    runAnalysis();
}
function closeAnalyzer(){document.getElementById("analyzerModal").style.display="none"}

function runAnalysis(){
    var el=document.getElementById("azContent");
    el.innerHTML="<div style='text-align:center;padding:30px'><div class='spinner'></div><p style='color:#888;margin-top:10px'>Analyse de "+P.length+" produits...</p></div>";
    setTimeout(function(){
        azIssues={noDesc:[],noLink:[],badAlt:[],badFn:[],noSku:[]};
        for(var i=0;i<P.length;i++){
            var p=P[i];
            if(!p._ds)azIssues.noDesc.push(p);
            else if(!p._lk)azIssues.noLink.push(p);
            if(!p._img&&p.images&&p.images.length>0){
                var titleFn=(p.title||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/ /g,"_").replace(/[^\\w\\-]/g,"_").replace(/_+/g,"_").replace(/^_|_$/g,"");
                var bAlt=false,bFn=false;
                for(var j=0;j<p.images.length;j++){
                    if((p.images[j].alt||"")!==p.title)bAlt=true;
                    var fn=(p.images[j].src||"").split("/").pop().split("?")[0];
                    if(fn.indexOf(titleFn)<0)bFn=true;
                }
                if(bAlt)azIssues.badAlt.push(p);
                if(bFn)azIssues.badFn.push(p);
            }
            if(!((p.variants||[])[0]||{}).sku)azIssues.noSku.push(p);
        }
        var total=P.length,perfect=0;
        for(var i=0;i<P.length;i++){if(P[i]._sc>=85)perfect++}

        var totalTasks=azIssues.noDesc.length+azIssues.noLink.length+azIssues.badAlt.length+azIssues.badFn.length;

        var h="<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:20px'>";
        h+="<div style='background:#111;padding:15px;border-radius:8px;text-align:center'><div style='font-size:28px;font-weight:bold;color:#00ff88'>"+total+"</div><div style='font-size:11px;color:#888'>Total produits</div></div>";
        h+="<div style='background:#111;padding:15px;border-radius:8px;text-align:center'><div style='font-size:28px;font-weight:bold;color:#00ff88'>"+perfect+"</div><div style='font-size:11px;color:#888'>SEO parfait (85%+)</div></div>";
        h+="<div style='background:#111;padding:15px;border-radius:8px;text-align:center'><div style='font-size:28px;font-weight:bold;color:"+(totalTasks>0?"#ff4757":"#00ff88")+"'>"+totalTasks+"</div><div style='font-size:11px;color:#888'>Tâches à faire</div></div>";
        h+="</div>";

        var cats=[
            {k:"noDesc",icon:"📝",name:"Descriptions manquantes",desc:"Bio produit absente ou trop courte",col:"#ff4757",auto:true},
            {k:"noLink",icon:"🔗",name:"Liens collection manquants",desc:"Description sans lien vers la collection",col:"#ff9500",auto:true},
            {k:"badAlt",icon:"🖼",name:"Alt images incorrect",desc:"Texte alternatif des photos ne correspond pas au titre",col:"#ff4757",auto:true},
            {k:"badFn",icon:"📁",name:"Noms fichiers images",desc:"Nom de fichier photo non optimise pour le SEO",col:"#ff4757",auto:true},
            {k:"noSku",icon:"🏷",name:"SKU manquants",desc:"Pas de reference produit (ajout manuel requis)",col:"#666",auto:false}
        ];

        for(var c=0;c<cats.length;c++){
            var cat=cats[c];var count=azIssues[cat.k].length;
            var statusCol=count===0?"#00ff88":cat.col;
            var statusTxt=count===0?"\u2705 OK":count+" produit"+(count>1?"s":"");
            h+="<div style='display:flex;align-items:center;gap:12px;padding:14px;background:#111;border-radius:8px;margin-bottom:8px;border-left:3px solid "+statusCol+"'>";
            h+="<span style='font-size:22px'>"+cat.icon+"</span>";
            h+="<div style='flex:1'><div style='font-size:14px;font-weight:600'>"+cat.name+"</div>";
            h+="<div style='font-size:11px;color:#666;margin-top:2px'>"+cat.desc+"</div></div>";
            h+="<div style='text-align:right'><div style='font-size:18px;font-weight:bold;color:"+statusCol+"'>"+statusTxt+"</div>";
            if(count>0&&!cat.auto)h+="<div style='font-size:10px;color:#555'>Manuel</div>";
            h+="</div></div>";
        }

        if(totalTasks===0){
            h+="<div style='text-align:center;padding:25px;color:#00ff88;font-size:15px;margin-top:10px'>\u2705 Tout est parfait ! Aucune correction nécessaire.</div>";
        }

        // Bouton corriger
        h+="<div id='azActions' style='margin-top:20px;display:flex;gap:10px;align-items:center'>";
        if(totalTasks>0){
            h+="<button class='btn btn-p' onclick='runAutoFix()' style='flex:1;padding:14px;font-size:15px;background:linear-gradient(135deg,#00ff88,#00cc6a);color:#000;font-weight:700;border:none;border-radius:8px;cursor:pointer'>&#128640; Corriger "+totalTasks+" t&acirc;ches automatiquement</button>";
        }
        h+="</div>";
        h+="<div id='azProgress' style='display:none;margin-top:15px'>";
        h+="<div style='display:flex;justify-content:space-between;margin-bottom:8px'><span id='azProgressTxt' style='font-size:12px;color:#888'>Préparation...</span><span id='azProgressPct' style='font-size:12px;color:#00ff88'>0%</span></div>";
        h+="<div style='background:#222;border-radius:6px;height:8px;overflow:hidden'><div id='azBar' style='background:#00ff88;height:100%;width:0%;border-radius:6px;transition:width 0.3s'></div></div>";
        h+="<div id='azLog' style='margin-top:12px;max-height:200px;overflow-y:auto;font-size:11px;color:#666'></div>";
        h+="</div>";

        el.innerHTML=h;
    },200);
}

function runAutoFix(){
    // Construire la liste de tâches
    var tasks=[];
    // 1. Descriptions (body_html) - inclut noDesc + noLink
    var descPids=[];
    for(var i=0;i<azIssues.noDesc.length;i++){var id=azIssues.noDesc[i].id;if(descPids.indexOf(id)<0){descPids.push(id);tasks.push({pid:id,type:"seo",fields:["body_html"],label:"Bio"})}}
    for(var i=0;i<azIssues.noLink.length;i++){var id=azIssues.noLink[i].id;if(descPids.indexOf(id)<0){descPids.push(id);tasks.push({pid:id,type:"seo",fields:["body_html"],label:"Bio"})}}
    // 2. Images (alt + filename)
    var imgPids=[];
    for(var i=0;i<azIssues.badAlt.length;i++){var id=azIssues.badAlt[i].id;if(imgPids.indexOf(id)<0)imgPids.push(id)}
    for(var i=0;i<azIssues.badFn.length;i++){var id=azIssues.badFn[i].id;if(imgPids.indexOf(id)<0)imgPids.push(id)}
    for(var i=0;i<imgPids.length;i++){tasks.push({pid:imgPids[i],type:"images",label:"Images"})}

    if(tasks.length===0)return;

    var prog=document.getElementById("azProgress");
    var bar=document.getElementById("azBar");
    var txt=document.getElementById("azProgressTxt");
    var pct=document.getElementById("azProgressPct");
    var log=document.getElementById("azLog");
    var btn=document.querySelector("#azActions button");
    prog.style.display="block";
    if(btn){btn.disabled=true;btn.style.opacity="0.5";btn.textContent="\u23F3 Correction en cours...";}

    var done=0,ok=0,errs=0;
    function next(){
        if(done>=tasks.length){
            bar.style.width="100%";pct.textContent="100%";
            txt.innerHTML="<span style='color:#00ff88;font-weight:600'>\u2705 Terminé ! "+ok+" corrections réussies"+(errs>0?", "+errs+" erreurs":"")+"</span>";
            if(btn){btn.textContent="\u2705 Terminé !";btn.style.background="#00ff88";}
            log.innerHTML+="<div style='color:#00ff88;margin-top:8px;font-weight:600'>Rechargement dans 3s...</div>";
            setTimeout(function(){try{sessionStorage.removeItem("kp_cache")}catch(e){}location.reload();},3000);
            return;
        }
        var t=tasks[done];
        var p=Math.round(done/tasks.length*100);
        bar.style.width=p+"%";pct.textContent=p+"%";
        txt.textContent="\u23F3 "+t.label+" — produit "+(done+1)+"/"+tasks.length;

        var promise;
        if(t.type==="seo"){
            promise=fetch("/api/seo/update",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:t.pid,fields:t.fields})});
        }else{
            promise=fetch("/api/images/fix",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:t.pid})});
        }
        promise.then(function(r){return r.json()}).then(function(d){
            if(d.success||d.fixed>=0){ok++;log.innerHTML+="<div>\u2705 #"+t.pid+" "+t.label+" OK</div>"}
            else{errs++;log.innerHTML+="<div style='color:#ff4757'>\u274C #"+t.pid+" "+t.label+": "+(d.error||"erreur")+"</div>"}
            done++;log.scrollTop=log.scrollHeight;setTimeout(next,100);
        }).catch(function(e){
            errs++;log.innerHTML+="<div style='color:#ff4757'>\u274C #"+t.pid+" "+t.label+": "+e.message+"</div>";
            done++;log.scrollTop=log.scrollHeight;setTimeout(next,100);
        });
    }
    next();
}

if(!loadCache())load();
</script>
</body>
</html>'''


COLLECTIONS_HTML = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Collections - KP SHOES</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#0a0a0f;color:#fff;min-height:100vh}
.hd{background:#111;padding:15px 20px;border-bottom:1px solid #222;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:20px;font-weight:bold;color:#00ff88;text-decoration:none}
.stats{display:flex;gap:15px;padding:15px 20px;background:#0d0d14;flex-wrap:wrap}
.st{background:#1a1a2e;padding:12px 20px;border-radius:8px;text-align:center}
.st .v{font-size:24px;font-weight:bold;color:#00ff88}
.st .l{font-size:10px;color:#666;margin-top:3px}
.main{max-width:1200px;margin:0 auto;padding:20px}
.toolbar{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
.search{flex:1;min-width:200px;padding:10px 15px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#fff}
.btn{padding:10px 20px;border:none;border-radius:8px;font-weight:600;cursor:pointer;font-size:12px}
.msg{padding:12px 20px;border-radius:8px;margin-bottom:15px;font-size:13px;display:none}
.msg.on{display:block}
.msg.ok{background:#00ff8815;color:#00ff88}
.msg.err{background:#ff475715;color:#ff4757}
table{width:100%;border-collapse:collapse;margin-top:10px}
th{text-align:left;padding:12px 15px;background:#1a1a2e;color:#888;font-size:11px;text-transform:uppercase;border-bottom:1px solid #333}
td{padding:12px 15px;border-bottom:1px solid #1a1a2e;font-size:13px;vertical-align:top}
tr:hover{background:#111}
.handle{color:#666;font-size:11px;font-family:monospace}
.seo-yes{color:#00ff88;font-weight:600}
.seo-no{color:#ff4757;font-weight:600}
.badge-seo{display:inline-block;padding:3px 8px;border-radius:10px;font-size:10px;font-weight:600}
.badge-seo.ok{background:#00ff8833;color:#00ff88}
.badge-seo.miss{background:#ff475733;color:#ff4757}
.btn-apply{padding:6px 14px;background:#00ff88;color:#000;border:none;border-radius:6px;font-weight:600;cursor:pointer;font-size:11px}
.btn-apply:disabled{opacity:0.4;cursor:not-allowed}
.btn-apply:hover:not(:disabled){background:#00cc6a}
.preview{max-width:400px;font-size:11px;color:#aaa;line-height:1.4;max-height:60px;overflow:hidden;text-overflow:ellipsis}
.spinner-sm{display:inline-block;width:14px;height:14px;border:2px solid #333;border-top-color:#00ff88;border-radius:50%;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.detail-modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.85);z-index:9999;overflow-y:auto}
.detail-box{max-width:750px;margin:40px auto;background:#1a1a2e;border-radius:12px;padding:30px;color:#fff}
.detail-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
.detail-close{background:none;border:none;color:#fff;font-size:24px;cursor:pointer}
.detail-section{margin-bottom:20px}
.detail-section h3{font-size:13px;color:#888;text-transform:uppercase;margin-bottom:8px}
.detail-section .val{background:#111;padding:12px;border-radius:8px;font-size:13px;line-height:1.6;color:#ccc;word-break:break-word}
.detail-section .val strong{color:#fff}
.prog-bar{background:#333;border-radius:6px;overflow:hidden;height:8px;margin:15px 0}
.prog-fill{width:0%;height:100%;background:linear-gradient(90deg,#00ff88,#00cc6a);transition:width .3s}
</style>
</head>
<body>
<header class="hd">
<a href="/" class="logo">&larr; KP SHOES</a>
<div style="display:flex;gap:10px;align-items:center">
<span style="color:#aaa;font-size:13px">Gestion des Collections</span>
</div>
</header>
<div class="stats">
<div class="st"><div class="v" id="totalCol">-</div><div class="l">COLLECTIONS</div></div>
<div class="st"><div class="v" id="seoOk">-</div><div class="l">SEO PR&Ecirc;T</div></div>
<div class="st"><div class="v" id="seoMiss">-</div><div class="l">SANS SEO</div></div>
</div>
<main class="main">
<div class="msg" id="msg"></div>
<div class="toolbar">
<input type="text" class="search" id="q" placeholder="Rechercher une collection..." oninput="filterCols()">
<button class="btn" style="background:#00ff88;color:#000" onclick="applyAll()">&#128640; Appliquer tout le SEO</button>
</div>
<div id="batchProg" style="display:none;margin-bottom:15px">
<div class="prog-bar"><div class="prog-fill" id="batchBar"></div></div>
<div id="batchTxt" style="text-align:center;font-size:12px;color:#aaa;margin-top:6px"></div>
</div>
<table>
<thead><tr><th>Collection</th><th>Handle</th><th>SEO</th><th>Aper&ccedil;u Meta Title</th><th>Action</th></tr></thead>
<tbody id="tbody"><tr><td colspan="5" style="text-align:center;padding:40px;color:#666">Chargement...</td></tr></tbody>
</table>
</main>

<!-- Modal détail -->
<div class="detail-modal" id="detailModal">
<div class="detail-box">
<div class="detail-head">
<h2 style="margin:0;font-size:18px" id="detailTitle">Collection</h2>
<button class="detail-close" onclick="closeDetail()">&times;</button>
</div>
<div id="detailContent"></div>
<div style="display:flex;gap:10px;margin-top:20px">
<button id="detailApplyBtn" class="btn" style="flex:1;padding:12px;background:#00ff88;color:#000;font-size:14px" onclick="applyFromDetail()">&#128640; Appliquer le SEO</button>
<a id="detailLink" href="#" target="_blank" class="btn" style="padding:12px 20px;background:#333;color:#fff;text-decoration:none;text-align:center">Voir sur le site &#8599;</a>
</div>
</div>
</div>

<script>
var cols=[];

function loadCols(){
    fetch("/api/collections").then(function(r){return r.json()}).then(function(d){
        cols=d.collections||[];
        updateStats();
        filterCols();
    });
}

function updateStats(){
    var ok=0,miss=0;
    for(var i=0;i<cols.length;i++){
        if(cols[i].has_seo)ok++;else miss++;
    }
    document.getElementById("totalCol").textContent=cols.length;
    document.getElementById("seoOk").textContent=ok;
    document.getElementById("seoMiss").textContent=miss;
}

function filterCols(){
    var q=document.getElementById("q").value.toLowerCase();
    var tb=document.getElementById("tbody");
    var html="";
    for(var i=0;i<cols.length;i++){
        var c=cols[i];
        if(q && c.title.toLowerCase().indexOf(q)<0 && c.handle.toLowerCase().indexOf(q)<0) continue;
        var seoClass=c.has_seo?"ok":"miss";
        var seoText=c.has_seo?"Pr\\u00eat":"Manquant";
        var preview=c.has_seo?(c.seo.meta_title||"").substring(0,50)+"...":"\\u2014";
        html+="<tr onclick=\\"showDetail("+i+")\\" style=\\"cursor:pointer\\">";
        html+="<td><strong>"+c.title+"</strong></td>";
        html+="<td><span class=\\"handle\\">"+c.handle+"</span></td>";
        html+="<td><span class=\\"badge-seo "+seoClass+"\\">"+seoText+"</span></td>";
        html+="<td><span class=\\"preview\\">"+preview+"</span></td>";
        html+="<td><button class=\\"btn-apply\\" onclick=\\"event.stopPropagation();applySeo("+c.id+",this)\\" "+(c.has_seo?"":"")+">Appliquer</button></td>";
        html+="</tr>";
    }
    if(!html)html="<tr><td colspan=\\"5\\" style=\\"text-align:center;padding:40px;color:#666\\">Aucune collection</td></tr>";
    tb.innerHTML=html;
}

function showDetail(idx){
    var c=cols[idx];
    document.getElementById("detailTitle").textContent=c.title;
    document.getElementById("detailLink").href="https://kpshoes.fr/collections/"+c.handle;
    var html="";
    if(c.has_seo){
        html+="<div class=\\"detail-section\\"><h3>Meta Title</h3><div class=\\"val\\">"+c.seo.meta_title+"</div></div>";
        html+="<div class=\\"detail-section\\"><h3>Meta Description</h3><div class=\\"val\\">"+c.seo.meta_description+"</div></div>";
        html+="<div class=\\"detail-section\\"><h3>Description (Body HTML)</h3><div class=\\"val\\">"+c.seo.description+"</div></div>";
        document.getElementById("detailApplyBtn").style.display="block";
        document.getElementById("detailApplyBtn").setAttribute("data-id",c.id);
    }else{
        html="<div style=\\"text-align:center;padding:30px;color:#666\\"><p>Aucun SEO d\\u00e9fini pour cette collection.</p><p style=\\"font-size:12px;margin-top:10px\\">Handle: "+c.handle+"</p></div>";
        document.getElementById("detailApplyBtn").style.display="none";
    }
    document.getElementById("detailContent").innerHTML=html;
    document.getElementById("detailModal").style.display="block";
}

function closeDetail(){document.getElementById("detailModal").style.display="none"}

function applySeo(cid,btn){
    var old=btn.innerHTML;
    btn.innerHTML="<span class=\\"spinner-sm\\"></span>";
    btn.disabled=true;
    fetch("/api/collections/"+cid+"/seo",{method:"POST",headers:{"Content-Type":"application/json"}}).then(function(r){return r.json()}).then(function(d){
        if(d.success){
            btn.innerHTML="\\u2713 OK";btn.style.background="#00cc6a";
            showMsg("Collection mise \\u00e0 jour !","ok");
        }else{
            btn.innerHTML="Erreur";btn.style.background="#ff4757";btn.style.color="#fff";
            showMsg("Erreur: "+(d.error||"inconnue"),"err");
        }
        setTimeout(function(){btn.innerHTML=old;btn.disabled=false;btn.style.background="#00ff88";btn.style.color="#000"},2000);
    }).catch(function(e){btn.innerHTML=old;btn.disabled=false;showMsg("Erreur: "+e.message,"err")});
}

function applyFromDetail(){
    var cid=document.getElementById("detailApplyBtn").getAttribute("data-id");
    var btn=document.getElementById("detailApplyBtn");
    btn.innerHTML="<span class=\\"spinner-sm\\"></span> Application...";
    btn.disabled=true;
    fetch("/api/collections/"+cid+"/seo",{method:"POST",headers:{"Content-Type":"application/json"}}).then(function(r){return r.json()}).then(function(d){
        if(d.success){
            btn.innerHTML="\\u2713 SEO appliqu\\u00e9 !";btn.style.background="#00cc6a";
            showMsg("Collection mise \\u00e0 jour !","ok");
        }else{
            btn.innerHTML="Erreur";btn.style.background="#ff4757";
            showMsg("Erreur: "+(d.error||"inconnue"),"err");
        }
        setTimeout(function(){btn.innerHTML="\\ud83d\\ude80 Appliquer le SEO";btn.disabled=false;btn.style.background="#00ff88"},2000);
    });
}

function applyAll(){
    var ready=[];
    for(var i=0;i<cols.length;i++){if(cols[i].has_seo)ready.push(cols[i])}
    if(!ready.length){showMsg("Aucune collection avec SEO d\\u00e9fini","err");return}
    if(!confirm("Appliquer le SEO \\u00e0 "+ready.length+" collections ?"))return;
    document.getElementById("batchProg").style.display="block";
    var done=0;
    function next(){
        if(done>=ready.length){
            document.getElementById("batchBar").style.width="100%";
            document.getElementById("batchTxt").textContent="Termin\\u00e9 ! "+done+"/"+ready.length+" collections mises \\u00e0 jour";
            showMsg(done+" collections mises \\u00e0 jour avec succ\\u00e8s !","ok");
            return;
        }
        var c=ready[done];
        document.getElementById("batchTxt").textContent=c.title+" ("+(done+1)+"/"+ready.length+")";
        document.getElementById("batchBar").style.width=Math.round((done+1)/ready.length*100)+"%";
        fetch("/api/collections/"+c.id+"/seo",{method:"POST",headers:{"Content-Type":"application/json"}}).then(function(r){return r.json()}).then(function(){
            done++;setTimeout(next,500);
        }).catch(function(){done++;setTimeout(next,500)});
    }
    next();
}

function showMsg(txt,type){
    var el=document.getElementById("msg");
    el.textContent=txt;el.className="msg on "+(type||"ok");
    setTimeout(function(){el.className="msg"},4000);
}

loadCols();
</script>
</body>
</html>'''



PRODUCT_HTML = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Produit - KP SHOES</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#0a0a0f;color:#fff;min-height:100vh}
.hd{background:#111;padding:12px 20px;border-bottom:1px solid #222;display:flex;align-items:center;gap:20px}
.hd a{color:#888;text-decoration:none}.hd a:hover{color:#fff}
.hd-title{font-size:16px;font-weight:bold;color:#00ff88}
.main{max-width:1200px;margin:0 auto;padding:20px}
.top{display:grid;grid-template-columns:350px 1fr;gap:25px;margin-bottom:25px}
.gallery{background:#111;border-radius:10px;overflow:hidden}
.main-img{width:100%;height:350px;object-fit:contain;background:#1a1a2e}
.thumbs{display:flex;gap:8px;padding:10px;overflow-x:auto}
.thumb{width:50px;height:50px;object-fit:cover;border-radius:5px;cursor:pointer;border:2px solid transparent}
.thumb:hover,.thumb.active{border-color:#00ff88}
.info{display:flex;flex-direction:column;gap:12px}
.title{font-size:18px;font-weight:bold}
.sku{color:#666;font-size:12px}
.price{font-size:24px;font-weight:bold;color:#00ff88}
.seo-box{display:flex;align-items:center;gap:15px;background:#111;padding:12px;border-radius:8px}
.score{width:60px;height:60px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:bold}
.score.excellent{background:#00ff8833;color:#00ff88;border:3px solid #00ff88}
.score.good{background:#00cc6a33;color:#00cc6a;border:3px solid #00cc6a}
.score.warning{background:#ffa50033;color:#ffa500;border:3px solid #ffa500}
.score.poor{background:#ff475733;color:#ff4757;border:3px solid #ff4757}
.btns{display:flex;gap:8px;flex-wrap:wrap}
.btn{padding:10px 16px;border:none;border-radius:6px;font-weight:600;cursor:pointer;font-size:12px;text-decoration:none}
.btn-p{background:#00ff88;color:#000}.btn-s{background:#333;color:#fff}.btn-o{background:#ff9500;color:#000}.btn-g{background:#3b82f6;color:#fff}
.section{background:#111;border-radius:10px;padding:15px;margin-bottom:15px}
.section-title{font-size:13px;font-weight:bold;margin-bottom:10px;color:#00ff88;display:flex;justify-content:space-between;align-items:center}
.checks{display:flex;flex-direction:column;gap:6px}
.check{display:flex;align-items:center;gap:10px;padding:8px 10px;background:#1a1a2e;border-radius:6px;cursor:pointer;border:2px solid transparent}
.check:hover{border-color:#333}.check.selected{border-color:#00ff88;background:#00ff8815}
.check-icon{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px}
.check-icon.success{background:#00ff8833;color:#00ff88}
.check-icon.warning{background:#ffa50033;color:#ffa500}
.check-icon.error{background:#ff475733;color:#ff4757}
.check-info{flex:1}.check-name{font-weight:600;font-size:11px}.check-msg{font-size:9px;color:#888}
.check-pts{font-weight:bold;font-size:10px}
.meta-box{background:#1a1a2e;border-radius:6px;padding:10px;margin-bottom:8px}
.meta-label{font-size:9px;color:#666;margin-bottom:3px}
.meta-value{font-size:11px;word-break:break-all}
table{width:100%;border-collapse:collapse}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #222;font-size:11px}
th{background:#1a1a2e;font-size:9px;color:#888}
.loading{text-align:center;padding:40px;color:#666}
.spinner{width:30px;height:30px;border:3px solid #222;border-top-color:#00ff88;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 10px}
@keyframes spin{to{transform:rotate(360deg)}}
.toast{position:fixed;bottom:20px;right:20px;padding:10px 18px;border-radius:6px;font-size:12px;z-index:100}
.toast.success{background:#00ff88;color:#000}.toast.error{background:#ff4757}
.goat-preview{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);z-index:200;overflow-y:auto;padding:20px}
.goat-preview.show{display:block}
.goat-content{max-width:800px;margin:0 auto;background:#111;border-radius:10px;padding:20px}
.goat-close{position:absolute;top:20px;right:20px;background:#333;border:none;color:#fff;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:20px}
.goat-images{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:20px 0}
.goat-images img{width:100%;height:150px;object-fit:contain;background:#1a1a2e;border-radius:8px;border:2px solid transparent}
.goat-images img.selected{border-color:#00ff88}
@media(max-width:800px){.top{grid-template-columns:1fr}}
</style>
</head>
<body>
<header class="hd">
<a href="/">← Retour</a>
<div class="hd-title">Detail Produit</div>
</header>
<main class="main" id="main"><div class="loading"><div class="spinner"></div>Chargement...</div></main>

<!-- Modal GOAT Preview -->
<div class="goat-preview" id="goatPreview">
<button class="goat-close" onclick="closeGoat()">×</button>
<div class="goat-content">
<h2 style="margin-bottom:10px">Photos GOAT</h2>
<p id="goatStatus" style="color:#888;font-size:12px;margin-bottom:15px">Recherche en cours...</p>
<div class="goat-images" id="goatImages"></div>
<div style="display:flex;gap:10px;margin-top:15px">
<button class="btn btn-p" onclick="applyGoatImages()">Remplacer les photos</button>
<button class="btn btn-s" onclick="closeGoat()">Annuler</button>
</div>
</div>
</div>

<script>
var pid=PRODUCT_ID_PLACEHOLDER;
var P=null;
var SEO=null;
var SHOP_URL="SHOP_PLACEHOLDER";
var selectedFields=[];
var goatImages=[];

function load(){
    fetch("/api/product/"+pid).then(function(r){return r.json();}).then(function(d){
        if(d.error){document.getElementById("main").innerHTML="<div class='loading'>Produit non trouve</div>";return;}
        P=d.product;SEO=d.seo;render();
    }).catch(function(e){document.getElementById("main").innerHTML="<div class='loading'>Erreur: "+e.message+"</div>";});
}

function render(){
    var p=P;var seo=SEO;
    var mainImg=(p.images&&p.images[0])?p.images[0].src:"";
    var sku=(p.variants&&p.variants[0])?p.variants[0].sku||"N/A":"N/A";
    var price=(p.variants&&p.variants[0])?p.variants[0].price:"0";
    
    var h="<div class='top'><div class='gallery'><img class='main-img' id='mainImg' src='"+mainImg+"'>";
    if(p.images&&p.images.length>1){h+="<div class='thumbs'>";for(var i=0;i<p.images.length;i++){h+="<img class='thumb"+(i===0?" active":"")+"' src='"+p.images[i].src+"' onclick='chImg(this)'>";}h+="</div>";}
    h+="</div><div class='info'>";
    h+="<div class='title'>"+esc(p.title)+"</div>";
    h+="<div class='sku'>SKU: "+sku+" | ID: "+p.id+"</div>";
    h+="<div class='price'>"+price+" EUR</div>";
    h+="<div class='seo-box'><div class='score "+seo.status+"'>"+seo.score+"</div><div><div style='font-weight:bold'>Score SEO</div><div style='font-size:11px;color:#888'>"+getLabel(seo.status)+"</div></div></div>";
    h+="<div class='btns'>";
    h+="<button class='btn btn-p' onclick='regenSelected()'>Modifier Selection</button>";
    h+="<button class='btn btn-s' onclick='regenAll()'>Tout Regenerer</button>";
    h+="<button class='btn btn-g' onclick='openGoat()'>📷 Photos GOAT</button>";
    h+="<a href='https://"+SHOP_URL+"/admin/products/"+p.id+"' target='_blank' class='btn btn-s'>Shopify</a>";
    h+="</div></div></div>";
    
    h+="<div class='section'><div class='section-title'>Analyse SEO <span style='font-size:10px;color:#888;font-weight:normal'>Cliquez pour selectionner</span></div><div class='checks'>";
    var fields=["meta_title","meta_description","body_html","","images_seo"];
    for(var i=0;i<seo.checks.length;i++){
        var c=seo.checks[i];
        var icon=c.status==="success"?"✓":c.status==="warning"?"!":"✗";
        var fld=fields[i]||"";
        h+="<div class='check' data-field='"+fld+"' onclick='toggleField(this)'>";
        h+="<div class='check-icon "+c.status+"'>"+icon+"</div>";
        h+="<div class='check-info'><div class='check-name'>"+c.name+"</div><div class='check-msg'>"+c.message+"</div></div>";
        h+="<div class='check-pts'>"+c.points+"/"+c.max+"</div></div>";
    }
    h+="</div></div>";
    
    h+="<div class='section'><div class='section-title'>Donnees SEO</div>";
    h+="<div class='meta-box'><div class='meta-label'>META TITLE</div><div class='meta-value'>"+(seo.meta_title||"Non defini")+"</div></div>";
    h+="<div class='meta-box'><div class='meta-label'>META DESCRIPTION</div><div class='meta-value'>"+(seo.meta_description||"Non definie")+"</div></div>";
    h+="<div class='meta-box'><div class='meta-label'>DESCRIPTION</div><div class='meta-value' style='max-height:80px;overflow-y:auto'>"+(p.body_html||"Non definie")+"</div></div>";
    h+="</div>";
    
    h+="<div class='section'><div class='section-title'>Images ("+p.images.length+") <button class='btn btn-o' onclick='fixImages()' style='float:right;font-size:11px;padding:5px 12px'>🖼️ Fix Images</button></div>";
    h+="<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px'>";
    var titleFn=(p.title||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/ /g,"_").replace(/[^\w\-]/g,"_").replace(/_+/g,"_").replace(/^_|_$/g,"");
    for(var i=0;i<p.images.length;i++){
        var img=p.images[i];
        var src=img.src||"";
        var alt=img.alt||"";
        var fn=src.split("/").pop().split("?")[0];
        var altOk=(alt===p.title);
        var fnOk=(fn.indexOf(titleFn)>=0);
        var borderColor=(altOk&&fnOk)?"#00ff88":(altOk||fnOk)?"#ff9500":"#ff4757";
        h+="<div style='border:2px solid "+borderColor+";border-radius:8px;overflow:hidden;background:#1a1a2e'>";
        h+="<img src='"+src+"' style='width:100%;height:100px;object-fit:contain'>";
        h+="<div style='padding:6px;font-size:10px'>";
        h+="<div style='color:"+(altOk?"#00ff88":"#ff4757")+"'>Alt: "+(altOk?"✓":"✗ "+esc(alt||"vide").substring(0,25))+"</div>";
        h+="<div style='color:"+(fnOk?"#00ff88":"#ff4757")+";overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>Nom: "+(fnOk?"✓":"✗ "+fn.substring(0,20))+"</div>";
        h+="</div></div>";
    }
    h+="</div>";
    h+="<div id='imgFixResult' style='margin-top:10px'></div>";
    h+="</div>";
    
    h+="<div class='section'><div class='section-title'>Variantes ("+p.variants.length+")</div>";
    h+="<table><thead><tr><th>Taille</th><th>SKU</th><th>Prix</th><th>Stock</th></tr></thead><tbody>";
    for(var i=0;i<p.variants.length;i++){
        var v=p.variants[i];
        h+="<tr><td><strong>"+v.title+"</strong></td><td>"+(v.sku||"-")+"</td><td>"+v.price+" EUR</td><td>"+v.inventory_quantity+"</td></tr>";
    }
    h+="</tbody></table></div>";
    
    document.getElementById("main").innerHTML=h;
}

function getLabel(s){if(s==="excellent")return"Excellent";if(s==="good")return"Bon";if(s==="warning")return"A ameliorer";return"Faible";}
function chImg(el){document.getElementById("mainImg").src=el.src;var all=document.querySelectorAll(".thumb");for(var i=0;i<all.length;i++)all[i].classList.remove("active");el.classList.add("active");}
function esc(s){return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

function toggleField(el){
    var field=el.getAttribute("data-field");
    if(!field)return;
    var idx=selectedFields.indexOf(field);
    if(idx>=0){selectedFields.splice(idx,1);el.classList.remove("selected");}
    else{selectedFields.push(field);el.classList.add("selected");}
}

function regenSelected(){
    if(selectedFields.length===0){toast("Selectionnez des elements","error");return;}
    toast("Mise a jour...","success");
    fetch("/api/seo/update",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:pid,fields:selectedFields})})
        .then(function(r){return r.json();}).then(function(d){
            if(d.success){toast("Mis a jour!","success");setTimeout(function(){location.reload();},1500);}
            else{toast("Erreur","error");}
        }).catch(function(){toast("Erreur","error");});
}

function regenAll(){
    toast("Regeneration...","success");
    fetch("/api/seo/apply",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:pid})})
        .then(function(r){return r.json();}).then(function(d){
            if(d.success){toast("SEO mis a jour!","success");setTimeout(function(){location.reload();},1500);}
            else{toast("Erreur","error");}
        }).catch(function(){toast("Erreur","error");});
}

// ===== GOAT Functions =====
function openGoat(){
    var sku=(P.variants&&P.variants[0])?P.variants[0].sku:"";
    if(!sku){toast("Pas de SKU","error");return;}
    
    document.getElementById("goatPreview").classList.add("show");
    document.getElementById("goatStatus").innerHTML="🔍 Recherche pour <strong>"+sku+"</strong>...<br><small style='color:#888'>(peut prendre 30-60s si le serveur est en veille)</small>";
    document.getElementById("goatImages").innerHTML="<div class='spinner'></div>";
    goatImages=[];
    
    fetch("/api/goat/images?sku="+encodeURIComponent(sku))
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.error){
                document.getElementById("goatStatus").innerHTML="<span style='color:#ff4757'>❌ "+d.error+"</span>";
                document.getElementById("goatImages").innerHTML="";
                return;
            }
            
            // Multi-SKU : afficher les onglets
            if(d.multi){
                var results=d.results;
                var tabsHtml="<div style='display:flex;gap:8px;margin-bottom:15px;flex-wrap:wrap'>";
                var firstWithImages=-1;
                for(var t=0;t<results.length;t++){
                    var count=results[t].images?results[t].images.length:0;
                    var label=results[t].sku+(results[t].name?" - "+results[t].name.substring(0,30):"")+" ("+count+" photos)";
                    var disabled=count===0;
                    tabsHtml+="<button class='goat-tab"+(firstWithImages===-1&&!disabled?" active":"")+"' onclick='switchGoatTab("+t+")' "+(disabled?"disabled style='opacity:0.4;cursor:not-allowed;padding:8px 16px;background:#222;border:1px solid #333;border-radius:6px;color:#666;font-size:12px'":"style='padding:8px 16px;background:#1a1a2e;border:1px solid #333;border-radius:6px;color:#fff;font-size:12px;cursor:pointer'")+">"+label+"</button>";
                    if(firstWithImages===-1&&!disabled)firstWithImages=t;
                }
                tabsHtml+="</div>";
                
                // Stocker les résultats multi
                window._goatMultiResults=results;
                
                document.getElementById("goatStatus").innerHTML="📦 <strong>SKU multiple détecté</strong> — Choisissez les photos à utiliser :"+tabsHtml;
                
                if(firstWithImages>=0){
                    switchGoatTab(firstWithImages);
                }else{
                    document.getElementById("goatImages").innerHTML="<p style='color:#666;text-align:center'>Aucune image trouvée pour ces SKU</p>";
                }
                return;
            }
            
            // Single SKU
            goatImages=d.images||[];
            document.getElementById("goatStatus").innerHTML="✅ <strong>"+d.name+"</strong> - "+goatImages.length+" photos trouvées<br><small style='color:#888'>Cliquez sur une image pour la désélectionner</small>";
            var html="";
            for(var i=0;i<goatImages.length;i++){
                html+="<img src='"+goatImages[i]+"' class='selected' onclick='toggleGoatImg(this,"+i+")'>";
            }
            document.getElementById("goatImages").innerHTML=html;
        })
        .catch(function(e){
            document.getElementById("goatStatus").innerHTML="<span style='color:#ff4757'>❌ Erreur: "+e.message+"</span>";
            document.getElementById("goatImages").innerHTML="";
        });
}

function switchGoatTab(idx){
    var results=window._goatMultiResults;
    if(!results||!results[idx])return;
    
    // Update active tab
    var tabs=document.querySelectorAll(".goat-tab");
    for(var i=0;i<tabs.length;i++){
        tabs[i].style.borderColor=i===idx?"#00ff88":"#333";
        tabs[i].style.background=i===idx?"#00ff8822":"#1a1a2e";
    }
    
    goatImages=results[idx].images||[];
    var html="";
    for(var i=0;i<goatImages.length;i++){
        html+="<img src='"+goatImages[i]+"' class='selected' onclick='toggleGoatImg(this,"+i+")'>";
    }
    document.getElementById("goatImages").innerHTML=html;
}

function closeGoat(){
    document.getElementById("goatPreview").classList.remove("show");
}

function toggleGoatImg(el,idx){
    el.classList.toggle("selected");
}

function applyGoatImages(){
    var selected=[];
    var imgs=document.querySelectorAll("#goatImages img.selected");
    for(var i=0;i<imgs.length;i++){
        selected.push(imgs[i].src);
    }
    if(selected.length===0){toast("Selectionnez au moins une image","error");return;}
    
    // Désactiver le bouton et montrer le loader
    var btn=document.querySelector(".goat-content .btn-p");
    btn.disabled=true;
    btn.innerHTML="<span class='spinner' style='width:16px;height:16px;display:inline-block;vertical-align:middle;margin-right:8px'></span>Remplacement en cours...";
    document.getElementById("goatStatus").textContent="⏳ Suppression des anciennes photos et ajout des nouvelles ("+selected.length+" photos)...";
    
    fetch("/api/goat/apply",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({product_id:pid,images:selected})
    })
    .then(function(r){return r.json();})
    .then(function(d){
        if(d.success){
            document.getElementById("goatStatus").innerHTML="<span style='color:#00ff88;font-size:16px'>✅ "+d.added+" photos remplacées avec succès!</span>";
            btn.innerHTML="✅ Terminé!";
            btn.style.background="#00ff88";
            toast("Photos remplacees! Rechargement...","success");
            setTimeout(function(){location.reload();},2000);
        }else{
            document.getElementById("goatStatus").innerHTML="<span style='color:#ff4757'>❌ Erreur: "+d.error+"</span>";
            btn.disabled=false;
            btn.innerHTML="Remplacer les photos";
            toast("Erreur: "+d.error,"error");
        }
    })
    .catch(function(e){
        document.getElementById("goatStatus").innerHTML="<span style='color:#ff4757'>❌ Erreur: "+e.message+"</span>";
        btn.disabled=false;
        btn.innerHTML="Remplacer les photos";
        toast("Erreur: "+e.message,"error");
    });
}

function toast(m,t){var e=document.createElement("div");e.className="toast "+t;e.textContent=m;document.body.appendChild(e);setTimeout(function(){e.remove();},3000);}

function fixImages(){
    var el=document.getElementById("imgFixResult");
    el.innerHTML="<div style='padding:10px;background:#333;border-radius:8px;font-size:13px;color:#aaa'><span class='spinner' style='width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:8px'></span>Correction des images...</div>";
    fetch("/api/images/fix",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:pid})})
    .then(function(r){return r.json();})
    .then(function(d){
        if(d.success){
            var msg="&#9989; "+d.fixed+" images corrig&eacute;es sur "+d.total;
            if(d.rename_errors){
                msg+="<br><span style='color:#ff9500'>&#9888;&#65039; Erreur renommage: "+JSON.stringify(d.rename_errors)+"</span>";
                if(d.attempted_filenames)msg+="<br><small style='color:#888'>Noms tent&eacute;s: "+d.attempted_filenames.join(", ")+"</small>";
            }
            el.innerHTML="<div style='padding:10px;background:#00ff8822;border-radius:8px;font-size:13px;color:#00ff88'>"+msg+"</div>";
            if(!d.rename_errors)setTimeout(function(){location.reload();},1500);
        }else{
            el.innerHTML="<div style='padding:10px;background:#ff475722;border-radius:8px;font-size:13px;color:#ff4757'>&#10060; Erreur: "+(d.error||"Inconnue")+"</div>";
        }
    }).catch(function(e){
        el.innerHTML="<div style='padding:10px;background:#ff475722;border-radius:8px;font-size:13px;color:#ff4757'>&#10060; "+e.message+"</div>";
    });
}

load();
</script>
</body>
</html>'''


BLOG_GENERATOR_HTML = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Générateur Blog SEO - KP SHOES</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#0a0a0f;color:#fff;min-height:100vh}
.hd{background:#111;padding:12px 20px;border-bottom:1px solid #222;display:flex;align-items:center;gap:20px}
.hd a{color:#888;text-decoration:none}.hd a:hover{color:#fff}
.hd-title{font-size:16px;font-weight:bold;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.main{max-width:1000px;margin:0 auto;padding:20px}
.intro{background:linear-gradient(135deg,#667eea22,#764ba222);border:1px solid #667eea44;border-radius:12px;padding:20px;margin-bottom:25px}
.intro h1{font-size:24px;margin-bottom:10px;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.intro p{color:#888;font-size:13px;line-height:1.6}
.section{background:#111;border-radius:12px;padding:20px;margin-bottom:20px;border:1px solid #222}
.section-title{font-size:14px;font-weight:bold;margin-bottom:15px;color:#fff;display:flex;align-items:center;gap:10px}
.section-title span{font-size:18px}
.topics{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
.topic{background:#1a1a2e;border:2px solid #333;border-radius:8px;padding:15px;cursor:pointer;transition:all 0.2s}
.topic:hover{border-color:#667eea}
.topic.selected{border-color:#667eea;background:#667eea22}
.topic-icon{font-size:24px;margin-bottom:8px}
.topic-name{font-weight:600;font-size:13px;margin-bottom:4px}
.topic-desc{font-size:10px;color:#888}
.form-group{margin-bottom:15px}
.form-group label{display:block;font-size:11px;color:#888;margin-bottom:5px}
.form-group input,.form-group select,.form-group textarea{width:100%;padding:10px 12px;background:#1a1a2e;border:1px solid #333;border-radius:6px;color:#fff;font-size:13px}
.form-group textarea{min-height:100px;resize:vertical}
.btn{padding:12px 24px;border:none;border-radius:8px;font-weight:600;cursor:pointer;font-size:13px;transition:all 0.2s}
.btn-primary{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 5px 20px #667eea44}
.btn-primary:disabled{opacity:0.5;cursor:not-allowed;transform:none}
.btn-secondary{background:#333;color:#fff}
.preview{background:#1a1a2e;border-radius:8px;padding:20px;margin-top:20px;display:none}
.preview.show{display:block}
.preview-title{font-size:18px;font-weight:bold;margin-bottom:10px}
.preview-meta{font-size:11px;color:#888;margin-bottom:15px}
.preview-content{font-size:13px;line-height:1.8;color:#ccc}
.preview-content h2{font-size:16px;color:#fff;margin:20px 0 10px}
.preview-content h3{font-size:14px;color:#fff;margin:15px 0 8px}
.preview-content p{margin-bottom:12px}
.preview-content a{color:#667eea}
.preview-content img{max-width:100%;border-radius:8px;margin:15px 0}
.preview-content ul{margin:10px 0 10px 20px}
.preview-content li{margin-bottom:5px}
.loading{display:none;align-items:center;gap:10px;padding:20px;background:#1a1a2e;border-radius:8px;margin-top:20px}
.loading.show{display:flex}
.spinner{width:24px;height:24px;border:3px solid #333;border-top-color:#667eea;border-radius:50%;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.success{background:#00ff8822;border:1px solid #00ff88;color:#00ff88;padding:15px;border-radius:8px;margin-top:20px;display:none}
.success.show{display:block}
.toast{position:fixed;bottom:20px;right:20px;padding:12px 20px;border-radius:8px;font-size:13px;z-index:1000}
.toast.success{background:#00ff88;color:#000}
.toast.error{background:#ff4757;color:#fff}
.articles-list{margin-top:20px}
.article-item{background:#1a1a2e;border-radius:8px;padding:15px;margin-bottom:10px;display:flex;gap:15px;align-items:center}
.article-item img{width:80px;height:80px;object-fit:cover;border-radius:6px}
.article-info{flex:1}
.article-title{font-weight:600;font-size:14px;margin-bottom:5px}
.article-date{font-size:11px;color:#888}
.keywords-input{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.keyword-tag{background:#667eea33;color:#667eea;padding:4px 10px;border-radius:15px;font-size:11px;display:flex;align-items:center;gap:5px}
.keyword-tag button{background:none;border:none;color:#667eea;cursor:pointer;font-size:14px}
</style>
</head>
<body>
<header class="hd">
<a href="/">← Retour</a>
<div class="hd-title">✨ Générateur Blog SEO</div>
</header>

<main class="main">
<div class="intro">
<h1>Générateur d'Articles SEO</h1>
<p>Créez des articles de blog optimisés pour le référencement, basés sur les tendances actuelles des sneakers. Les articles incluent automatiquement des liens vers vos produits et collections, des images GOAT, et sont structurés pour maximiser votre visibilité Google.</p>
</div>

<!-- Type d'article -->
<div class="section">
<div class="section-title"><span>📝</span> Type d'article</div>
<div class="topics" id="topics">
<div class="topic" data-type="release" onclick="selectTopic(this)">
<div class="topic-icon">📅</div>
<div class="topic-name">Calendrier Sorties</div>
<div class="topic-desc">Prochaines releases Nike, Jordan, Adidas...</div>
</div>
<div class="topic" data-type="guide_taille" onclick="selectTopic(this)">
<div class="topic-icon">📏</div>
<div class="topic-name">Guide de Tailles</div>
<div class="topic-desc">Comment taille la Jordan 4, Dunk Low...</div>
</div>
<div class="topic" data-type="tendance" onclick="selectTopic(this)">
<div class="topic-icon">🔥</div>
<div class="topic-name">Tendances 2026</div>
<div class="topic-desc">Les sneakers les plus hype du moment</div>
</div>
<div class="topic" data-type="comparatif" onclick="selectTopic(this)">
<div class="topic-icon">⚖️</div>
<div class="topic-name">Comparatif</div>
<div class="topic-desc">Jordan 4 vs Dunk Low, quelle choisir ?</div>
</div>
<div class="topic" data-type="histoire" onclick="selectTopic(this)">
<div class="topic-icon">📚</div>
<div class="topic-name">Histoire & Culture</div>
<div class="topic-desc">L'histoire de la Air Jordan 1, Nike Dunk...</div>
</div>
<div class="topic" data-type="entretien" onclick="selectTopic(this)">
<div class="topic-icon">🧹</div>
<div class="topic-name">Entretien</div>
<div class="topic-desc">Nettoyer ses sneakers, déjaunir semelles...</div>
</div>
<div class="topic" data-type="style" onclick="selectTopic(this)">
<div class="topic-icon">👔</div>
<div class="topic-name">Style & Outfit</div>
<div class="topic-desc">Comment porter ses sneakers au quotidien</div>
</div>
<div class="topic" data-type="custom" onclick="selectTopic(this)">
<div class="topic-icon">✏️</div>
<div class="topic-name">Article Libre</div>
<div class="topic-desc">Écrivez sur le sujet de votre choix</div>
</div>
</div>
</div>

<!-- Configuration -->
<div class="section">
<div class="section-title"><span>⚙️</span> Configuration</div>
<div class="form-group">
<label>Modèle/Sujet principal</label>
<input type="text" id="subject" placeholder="Ex: Air Jordan 4, Nike Dunk Low Panda, Yeezy 350...">
</div>
<div class="form-group">
<label>Mots-clés SEO (séparés par des virgules)</label>
<input type="text" id="keywords" placeholder="Ex: acheter jordan 4, jordan 4 pas cher, taille jordan 4">
</div>
<div class="form-group">
<label>Ton de l'article</label>
<select id="tone">
<option value="expert">Expert & Informatif</option>
<option value="casual">Casual & Accessible</option>
<option value="hype">Hype & Enthousiaste</option>
</select>
</div>
<div class="form-group">
<label>Longueur</label>
<select id="length">
<option value="medium">Moyen (~1500 mots)</option>
<option value="long">Long (~2500 mots)</option>
<option value="short">Court (~800 mots)</option>
</select>
</div>
</div>

<!-- Actions -->
<div style="display:flex;gap:10px;flex-wrap:wrap">
<button class="btn btn-primary" id="generateBtn" onclick="generateArticle()">✨ Générer l'article</button>
<button class="btn btn-secondary" onclick="loadExistingArticles()">📄 Voir articles existants</button>
</div>

<!-- Loading -->
<div class="loading" id="loading">
<div class="spinner"></div>
<div>
<div style="font-weight:600">Génération en cours...</div>
<div style="font-size:11px;color:#888" id="loadingStatus">Recherche des tendances actuelles...</div>
</div>
</div>

<!-- Preview -->
<div class="preview" id="preview">
<div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:15px">
<div>
<div class="preview-title" id="previewTitle">Titre de l'article</div>
<div class="preview-meta" id="previewMeta">Par KP SHOES • Février 2026</div>
</div>
<div style="display:flex;gap:8px">
<button class="btn btn-secondary" onclick="regenerate()">🔄 Régénérer</button>
<button class="btn btn-primary" onclick="publishArticle()">🚀 Publier</button>
</div>
</div>
<div class="preview-content" id="previewContent"></div>
</div>

<!-- Success -->
<div class="success" id="success">
<div style="font-weight:600;margin-bottom:5px">✅ Article publié avec succès !</div>
<div style="font-size:12px">L'article est maintenant visible sur votre blog Shopify.</div>
<a href="#" id="articleLink" target="_blank" style="color:#00ff88;font-size:12px">Voir l'article →</a>
</div>

<!-- Articles existants -->
<div class="articles-list" id="articlesList" style="display:none">
<div class="section-title"><span>📄</span> Articles existants</div>
<div id="articlesContainer"></div>
</div>
</main>

<script>
var selectedType = null;
var generatedArticle = null;
var BLOG_ID = BLOG_ID_PLACEHOLDER;

function selectTopic(el) {
    document.querySelectorAll('.topic').forEach(t => t.classList.remove('selected'));
    el.classList.add('selected');
    selectedType = el.dataset.type;
}

function generateArticle() {
    if (!selectedType) {
        toast('Sélectionnez un type d\\'article', 'error');
        return;
    }
    
    var subject = document.getElementById('subject').value.trim();
    if (!subject && selectedType !== 'tendance') {
        toast('Entrez un sujet/modèle', 'error');
        return;
    }
    
    document.getElementById('loading').classList.add('show');
    document.getElementById('preview').classList.remove('show');
    document.getElementById('success').classList.remove('show');
    document.getElementById('generateBtn').disabled = true;
    
    var statusEl = document.getElementById('loadingStatus');
    var statuses = [
        'Recherche des tendances actuelles...',
        'Récupération de l\\'image depuis GOAT...',
        'Recherche de vos produits correspondants...',
        'Génération du contenu SEO...',
        'Optimisation des liens internes...',
        'Finalisation de l\\'article...'
    ];
    var statusIdx = 0;
    var statusInterval = setInterval(function() {
        statusIdx = (statusIdx + 1) % statuses.length;
        statusEl.textContent = statuses[statusIdx];
    }, 2000);
    
    fetch('/api/blog/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            type: selectedType,
            subject: subject,
            keywords: document.getElementById('keywords').value,
            tone: document.getElementById('tone').value,
            length: document.getElementById('length').value
        })
    })
    .then(r => r.json())
    .then(data => {
        clearInterval(statusInterval);
        document.getElementById('loading').classList.remove('show');
        document.getElementById('generateBtn').disabled = false;
        
        if (data.error) {
            toast('Erreur: ' + data.error, 'error');
            return;
        }
        
        generatedArticle = data;
        document.getElementById('previewTitle').textContent = data.title;
        document.getElementById('previewMeta').innerHTML = 'Par KP SHOES • ' + new Date().toLocaleDateString('fr-FR', {month: 'long', year: 'numeric'});
        
        // Afficher l'image si disponible
        var imageHtml = '';
        if (data.image_url) {
            imageHtml = '<div style="margin-bottom:20px"><img src="' + data.image_url + '" style="max-width:100%;max-height:300px;border-radius:8px;object-fit:contain"></div>';
        }
        
        // Afficher les meta SEO
        var metaHtml = '';
        if (data.meta_title || data.meta_description) {
            metaHtml = '<div style="background:#1a1a2e;padding:15px;border-radius:8px;margin-bottom:20px;font-size:12px">';
            metaHtml += '<div style="color:#888;margin-bottom:5px">📊 Aperçu SEO Google</div>';
            if (data.meta_title) {
                metaHtml += '<div style="color:#1a0dab;font-size:14px;margin-bottom:3px">' + data.meta_title + '</div>';
            }
            metaHtml += '<div style="color:#006621;font-size:11px;margin-bottom:3px">https://kpshoes.fr/blogs/news/' + (data.handle || '...') + '</div>';
            if (data.meta_description) {
                metaHtml += '<div style="color:#666">' + data.meta_description + '</div>';
            }
            metaHtml += '</div>';
        }
        
        // Afficher l'extrait
        var summaryHtml = '';
        if (data.summary_html) {
            summaryHtml = '<div style="background:#667eea22;padding:15px;border-radius:8px;margin-bottom:20px;border-left:4px solid #667eea">';
            summaryHtml += '<div style="color:#667eea;font-size:11px;margin-bottom:5px;font-weight:600">📝 EXTRAIT</div>';
            summaryHtml += '<div style="font-size:13px;color:#ccc">' + data.summary_html + '</div>';
            summaryHtml += '</div>';
        }
        
        document.getElementById('previewContent').innerHTML = imageHtml + metaHtml + summaryHtml + data.body_html;
        document.getElementById('preview').classList.add('show');
    })
    .catch(e => {
        clearInterval(statusInterval);
        document.getElementById('loading').classList.remove('show');
        document.getElementById('generateBtn').disabled = false;
        toast('Erreur: ' + e.message, 'error');
    });
}

function regenerate() {
    generateArticle();
}

function publishArticle() {
    if (!generatedArticle) return;
    
    document.getElementById('preview').style.opacity = '0.5';
    
    fetch('/api/blogs/' + BLOG_ID + '/articles', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            title: generatedArticle.title,
            body_html: generatedArticle.body_html,
            author: 'KP SHOES',
            tags: generatedArticle.tags || '',
            published: true,
            image_url: generatedArticle.image_url || '',
            summary_html: generatedArticle.summary_html || '',
            meta_title: generatedArticle.meta_title || '',
            meta_description: generatedArticle.meta_description || ''
        })
    })
    .then(r => r.json())
    .then(data => {
        document.getElementById('preview').style.opacity = '1';
        
        if (data.error) {
            toast('Erreur: ' + data.error, 'error');
            return;
        }
        
        document.getElementById('preview').classList.remove('show');
        document.getElementById('success').classList.add('show');
        
        if (data.article && data.article.handle) {
            document.getElementById('articleLink').href = 'https://DOMAIN_PLACEHOLDER/blogs/news/' + data.article.handle;
        }
        
        toast('Article publié !', 'success');
    })
    .catch(e => {
        document.getElementById('preview').style.opacity = '1';
        toast('Erreur: ' + e.message, 'error');
    });
}

function loadExistingArticles() {
    var container = document.getElementById('articlesContainer');
    container.innerHTML = '<div class="loading show"><div class="spinner"></div><span>Chargement...</span></div>';
    document.getElementById('articlesList').style.display = 'block';
    
    fetch('/api/blogs/' + BLOG_ID + '/articles')
    .then(r => r.json())
    .then(data => {
        var articles = data.articles || [];
        if (articles.length === 0) {
            container.innerHTML = '<p style="color:#888;font-size:13px">Aucun article pour le moment.</p>';
            return;
        }
        
        var html = '';
        articles.forEach(function(a) {
            var img = a.image ? a.image.src : '';
            html += '<div class="article-item">';
            if (img) html += '<img src="' + img + '">';
            html += '<div class="article-info"><div class="article-title">' + a.title + '</div>';
            html += '<div class="article-date">' + new Date(a.created_at).toLocaleDateString('fr-FR') + '</div></div>';
            html += '<a href="https://DOMAIN_PLACEHOLDER/blogs/news/' + a.handle + '" target="_blank" class="btn btn-secondary" style="padding:8px 12px;font-size:11px">Voir</a>';
            html += '</div>';
        });
        container.innerHTML = html;
    })
    .catch(e => {
        container.innerHTML = '<p style="color:#ff4757">Erreur: ' + e.message + '</p>';
    });
}

function toast(msg, type) {
    var el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function() { el.remove(); }, 3000);
}
</script>
</body>
</html>'''


@app.route('/')
def home():
    return HOME_HTML


@app.route('/collections')
def collections_page():
    return COLLECTIONS_HTML


@app.route('/blog-generator')
def blog_generator():
    # Get blog ID
    r = shopify_request('blogs.json')
    blog_id = 0
    if r and r.get('blogs'):
        blog_id = r['blogs'][0]['id']
    
    html = BLOG_GENERATOR_HTML.replace('BLOG_ID_PLACEHOLDER', str(blog_id))
    html = html.replace('DOMAIN_PLACEHOLDER', SITE_DOMAIN)
    return html


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    html = PRODUCT_HTML.replace('PRODUCT_ID_PLACEHOLDER', str(product_id))
    html = html.replace('SHOP_PLACEHOLDER', SHOP)
    return html


# ══════════════════════════════════════════════════════════════
# API ROUTES
# ══════════════════════════════════════════════════════════════

@app.route('/api/products')
def api_products():
    since_id = request.args.get('since_id', '0')
    limit = request.args.get('limit', '250')
    # Utiliser fields pour ne récupérer que le nécessaire (réduit la taille de la réponse de ~80%)
    fields = 'id,title,handle,vendor,product_type,tags,images,variants,body_html'
    r = shopify_request(f'products.json?limit={limit}&since_id={since_id}&fields={fields}')
    products = r.get('products', []) if r else []
    # N'envoyer les collections qu'au premier appel
    cols = get_collections() if since_id == '0' else []
    return jsonify({'products': products, 'collections': cols})


@app.route('/api/product/<int:product_id>')
def api_product(product_id):
    r = shopify_request(f'products/{product_id}.json')
    if not r or 'product' not in r:
        return jsonify({'error': 'Not found'}), 404
    product = r['product']
    metafields = get_product_metafields(product_id)
    seo = analyze_seo(product, metafields['meta_title'], metafields['meta_description'])
    seo['meta_title'] = metafields['meta_title']
    seo['meta_description'] = metafields['meta_description']
    return jsonify({'product': product, 'seo': seo})


@app.route('/api/collections')
def api_collections():
    cols = get_collections()
    # Enrichir avec le statut SEO
    for c in cols:
        seo = get_collection_seo(c['handle'])
        c['has_seo'] = seo is not None
        if seo:
            c['seo'] = seo
    return jsonify({'collections': cols, 'count': len(cols)})


@app.route('/api/collections/<int:cid>/seo', methods=['POST'])
def api_apply_collection_seo(cid):
    """Applique le SEO optimisé à une collection"""
    cols = get_collections()
    col = next((c for c in cols if c['id'] == cid), None)
    if not col:
        return jsonify({'error': 'Collection non trouvée'}), 404
    
    success = update_collection_seo(cid, col['handle'])
    if success:
        return jsonify({'success': True, 'handle': col['handle']})
    return jsonify({'error': 'Pas de SEO défini pour cette collection'}), 400


@app.route('/api/collections/batch-seo', methods=['POST'])
def api_batch_collection_seo():
    """Applique le SEO à toutes les collections qui ont un SEO défini"""
    cols = get_collections()
    updated = []
    errors = []
    for c in cols:
        seo = get_collection_seo(c['handle'])
        if seo:
            try:
                update_collection_seo(c['id'], c['handle'])
                updated.append(c['handle'])
                time.sleep(0.5)
            except Exception as e:
                errors.append({'handle': c['handle'], 'error': str(e)})
    return jsonify({'success': True, 'updated': updated, 'errors': errors, 'count': len(updated)})


@app.route('/api/seo/apply', methods=['POST'])
def api_apply_seo():
    pid = request.json.get('product_id')
    r = shopify_request(f'products/{pid}.json')
    if not r: return jsonify({'error': 'err'}), 404
    p = r['product']
    cols = get_collections()
    update_seo_field(pid, 'meta_title', generate_meta_title(p))
    time.sleep(0.3)
    update_seo_field(pid, 'meta_description', generate_meta_description(p))
    time.sleep(0.3)
    update_seo_field(pid, 'body_html', generate_body_html(p, cols))
    time.sleep(0.3)
    fix_product_images(pid)
    return jsonify({'success': True})


@app.route('/api/seo/update', methods=['POST'])
def api_update_seo():
    pid = request.json.get('product_id')
    fields = request.json.get('fields', [])
    if not fields:
        return jsonify({'error': 'No fields'}), 400
    r = shopify_request(f'products/{pid}.json')
    if not r: return jsonify({'error': 'err'}), 404
    p = r['product']
    cols = get_collections()
    for field in fields:
        if field == 'meta_title':
            update_seo_field(pid, 'meta_title', generate_meta_title(p))
        elif field == 'meta_description':
            update_seo_field(pid, 'meta_description', generate_meta_description(p))
        elif field == 'body_html':
            update_seo_field(pid, 'body_html', generate_body_html(p, cols))
        elif field == 'images_seo':
            fix_product_images(pid)
        time.sleep(0.3)
    return jsonify({'success': True, 'updated': fields})


@app.route('/api/seo/batch', methods=['POST'])
def api_batch_seo():
    global task_progress
    pids = request.json.get('product_ids', [])
    def run():
        global task_progress
        task_progress = {'running': True, 'current': 0, 'total': len(pids), 'message': 'Demarrage...'}
        cols = get_collections()
        for i, pid in enumerate(pids):
            task_progress['current'] = i + 1
            r = shopify_request(f'products/{pid}.json')
            if r and 'product' in r:
                p = r['product']
                task_progress['message'] = p.get('title','')[:30]
                update_seo_field(pid, 'meta_title', generate_meta_title(p))
                time.sleep(0.3)
                update_seo_field(pid, 'meta_description', generate_meta_description(p))
                time.sleep(0.3)
                update_seo_field(pid, 'body_html', generate_body_html(p, cols))
            time.sleep(0.5)
        task_progress = {'running': False, 'current': len(pids), 'total': len(pids), 'message': 'Termine!'}
    Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)


# ══════════════════════════════════════════════════════════════
# GOAT API ROUTES
# ══════════════════════════════════════════════════════════════

@app.route('/api/goat/test-cdn')
def api_goat_test_cdn():
    """Test si les URLs du CDN GOAT sont accessibles. Usage: ?url=https://image.goat.com/.../1118288_01.png.png"""
    import subprocess
    url = request.args.get('url', '').strip()
    if not url:
        url = "https://image.goat.com/attachments/product_template_pictures/images/084/275/684/original/1118288_01.png.png"
    
    results = {}
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-m", "8",
             "-r", "0-0", url,
             "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
             "-H", "Referer: https://www.goat.com/"],
            capture_output=True, text=True, timeout=12)
        results['curl_range'] = {'code': r.stdout.strip(), 'ok': r.stdout.strip() in ('200', '206')}
    except Exception as e:
        results['curl_range'] = {'error': str(e)}
    
    base = "https://image.goat.com/attachments/product_template_pictures/images/084/275/684/original/1118288"
    angle_tests = {}
    for i in range(4):
        test_url = f"{base}_{i:02d}.png.png"
        exists = _goat_url_exists(test_url)
        angle_tests[f"_{i:02d}"] = exists
    results['angle_tests'] = angle_tests
    
    return jsonify({'url_tested': url, 'results': results})

@app.route('/api/goat/debug-algolia')
def api_goat_debug_algolia():
    """Dump TOUTES les données Algolia pour un SKU. Usage: ?sku=FD0689-001"""
    sku = request.args.get('sku', 'FD0689-001').strip()
    url = f"{GOAT_ALGOLIA_URL}?x-algolia-application-id={GOAT_ALGOLIA_APP_ID}&x-algolia-api-key={GOAT_ALGOLIA_API_KEY}"
    payload = {"requests": [{"indexName": "product_variants_v2", "params": f"distinct=true&maxValuesPerFacet=1&page=0&query={sku}"}]}
    raw = _goat_post(url, payload)
    if not raw: return jsonify({'error': 'Algolia request failed'}), 500
    try: data = json.loads(raw)
    except: return jsonify({'error': 'Invalid JSON', 'raw': raw[:500]}), 500
    hits = data.get('results', [{}])[0].get('hits', [])
    if not hits: return jsonify({'error': 'No hits', 'sku': sku}), 404
    
    # Trouver le bon hit
    sku_clean = sku.replace('-', ' ').replace('  ', ' ').upper()
    best = None
    for h in hits:
        h_sku = (h.get('sku', '') or '').upper()
        if h_sku == sku_clean or h_sku == sku.upper():
            best = h; break
    if not best: best = hits[0]
    
    # Extraire tous les champs contenant 'picture', 'image', 'photo', 'url'
    image_fields = {}
    all_keys = sorted(best.keys())
    for k in all_keys:
        kl = k.lower()
        if any(x in kl for x in ['picture', 'image', 'photo', 'url', 'media', 'gallery', 'asset']):
            image_fields[k] = best[k]
    
    return jsonify({
        'sku': sku,
        'hit_sku': best.get('sku'),
        'slug': best.get('slug'),
        'all_keys': all_keys,
        'image_fields': image_fields,
        'total_hits': len(hits)
    })

@app.route('/api/goat/scrape-images')
def api_goat_scrape_images():
    """Scrape la page produit GOAT pour extraire les images depuis __NEXT_DATA__. Usage: ?slug=dunk-low-..."""
    slug = request.args.get('slug', '').strip()
    sku = request.args.get('sku', '').strip()
    
    # Si SKU fourni, chercher le slug via Algolia
    if not slug and sku:
        product = goat_search(sku)
        if product: slug = product.get('slug', '')
    
    if not slug:
        return jsonify({'error': 'slug ou sku requis'}), 400
    
    page_url = f"https://www.goat.com/sneakers/{slug}"
    import subprocess
    
    # Tenter de récupérer la page HTML
    try:
        result = subprocess.run(
            ["curl", "-s", "-m", "15", "-L", page_url,
             "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
             "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
             "-H", "Accept-Language: en-US,en;q=0.5"],
            capture_output=True, text=True, timeout=20)
        html = result.stdout
    except Exception as e:
        return jsonify({'error': f'curl failed: {e}'}), 500
    
    if not html or len(html) < 100:
        return jsonify({'error': 'Empty response', 'page_url': page_url}), 500
    
    if '1020' in html and len(html) < 5000:
        return jsonify({'error': 'Cloudflare 1020 blocked', 'page_url': page_url}), 403
    
    # Chercher __NEXT_DATA__
    images = []
    next_data = None
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if match:
        try:
            next_data = json.loads(match.group(1))
            # Parcourir récursivement pour trouver les URLs d'images
            def find_images(obj, depth=0):
                if depth > 10: return
                if isinstance(obj, str):
                    if 'image.goat.com' in obj and obj not in images:
                        images.append(obj)
                elif isinstance(obj, dict):
                    for v in obj.values():
                        find_images(v, depth+1)
                elif isinstance(obj, list):
                    for item in obj:
                        find_images(item, depth+1)
            find_images(next_data)
        except json.JSONDecodeError:
            pass
    
    # Fallback: regex sur tout le HTML
    if not images:
        raw_urls = re.findall(r'https://image\.goat\.com/[^\s"\'<>]+\.(?:png|jpg|jpeg|webp)(?:\.png|\.jpg)?', html)
        for u in raw_urls:
            if u not in images:
                images.append(u)
    
    return jsonify({
        'slug': slug,
        'page_url': page_url,
        'html_length': len(html),
        'has_next_data': next_data is not None,
        'images_found': len(images),
        'images': images[:20],
        'html_preview': html[:500] if len(html) < 5000 else f"...{len(html)} chars..."
    })

@app.route('/api/goat/test-resize')
def api_goat_test_resize():
    """Test le resize d'une image GOAT en 750x500. Usage: ?url=... ou par défaut test avec HQ8708"""
    url = request.args.get('url', '').strip()
    if not url:
        url = "https://image.goat.com/1000/attachments/product_template_pictures/images/088/220/352/original/1122212_00.png.png"
    
    # Vérifier que Pillow est installé
    try:
        from PIL import Image
        pillow_ok = True
        pillow_version = Image.__version__ if hasattr(Image, '__version__') else 'unknown'
    except ImportError:
        pillow_ok = False
        pillow_version = 'NOT INSTALLED'
    
    result = {
        'pillow_installed': pillow_ok,
        'pillow_version': pillow_version,
        'url': url,
    }
    
    if pillow_ok:
        b64 = _resize_goat_image_to_750x500(url)
        result['resize_success'] = b64 is not None
        result['base64_length'] = len(b64) if b64 else 0
    
    return jsonify(result)

@app.route('/api/goat/debug-api')
def api_goat_debug_api():
    """Debug: montre exactement ce que l'API product_templates retourne. Usage: ?sku=FD0689-001"""
    sku = request.args.get('sku', 'FD0689-001').strip()
    
    # 1. Chercher le slug via Algolia
    product = goat_search(sku)
    if not product:
        return jsonify({'error': 'Produit non trouvé sur Algolia', 'sku': sku}), 404
    
    slug = product.get('slug', '')
    result = {
        'sku': sku,
        'slug': slug,
        'algolia_main_picture': product.get('main_picture_url', ''),
    }
    
    # 2. Appel API product_templates
    raw = _goat_get(f"{GOAT_PRODUCT_API}/{slug}")
    if not raw:
        result['api_status'] = 'NO_RESPONSE'
        return jsonify(result)
    
    result['raw_length'] = len(raw)
    result['raw_preview'] = raw[:300]
    
    try:
        data = json.loads(raw)
        result['api_status'] = 'OK_JSON'
        
        # Tous les champs contenant picture/image
        pic_fields = {}
        for k, v in data.items():
            kl = k.lower()
            if any(x in kl for x in ['picture', 'image', 'photo', 'media', 'gallery']):
                if isinstance(v, list):
                    pic_fields[k] = f"[{len(v)} items]"
                    if v and isinstance(v[0], dict):
                        pic_fields[f"{k}_first"] = v[0]
                        pic_fields[f"{k}_count"] = len(v)
                else:
                    pic_fields[k] = v
        result['picture_fields'] = pic_fields
        
        # Images extraites par la logique actuelle
        images = goat_get_product_images(slug)
        result['extracted_images'] = images
        result['extracted_count'] = len(images)
        
    except json.JSONDecodeError:
        result['api_status'] = 'NOT_JSON'
        if '1020' in raw[:200]:
            result['api_status'] = 'CLOUDFLARE_1020'
    
    return jsonify(result)

@app.route('/api/goat/images')
def api_goat_images():
    """Recherche les images GOAT pour un SKU via l'app 360. Gère les SKU multiples."""
    sku = request.args.get('sku', '').strip()
    if not sku:
        return jsonify({'error': 'SKU requis'}), 400
    
    log.info(f"[GOAT] Searching images for SKU: {sku}")
    
    result = get_goat_images(sku)
    
    if not result:
        return jsonify({'error': 'Produit non trouve sur GOAT'}), 404
    
    # Multi-SKU : retourner les résultats groupés
    if result.get('multi'):
        has_any = any(r.get('images') for r in result['results'])
        if not has_any:
            return jsonify({'error': 'Aucune image trouvee pour aucun des SKU'}), 404
        return jsonify({
            'multi': True,
            'results': result['results']
        })
    
    # Single SKU
    if not result.get('images'):
        return jsonify({'error': 'Aucune image trouvee'}), 404
    
    return jsonify({
        'name': result.get('name', ''),
        'sku': result.get('sku', sku),
        'images': result.get('images', []),
        'multi': False
    })


@app.route('/api/goat/apply', methods=['POST'])
def api_goat_apply():
    """Remplace les images d'un produit par celles de GOAT"""
    data = request.json
    product_id = data.get('product_id')
    images = data.get('images', [])
    
    if not product_id or not images:
        return jsonify({'error': 'product_id et images requis'}), 400
    
    try:
        # Get current product
        r = shopify_request(f'products/{product_id}.json')
        if not r or 'product' not in r:
            return jsonify({'error': 'Produit non trouve'}), 404
        
        product = r['product']
        
        # Delete existing images
        for img in product.get('images', []):
            shopify_request(f'products/{product_id}/images/{img["id"]}.json', 'DELETE')
            time.sleep(0.3)
        
        # Si une seule image (produit sans galerie), la redimensionner en 750x500
        # Détection: 1 seule image ET c'est une image GOAT (pas une galerie multi-angles)
        needs_resize = len(images) == 1 and 'image.goat.com' in images[0]
        log.info(f"[GOAT Apply] {len(images)} images, needs_resize={needs_resize}, first_url={images[0][:80]}...")
        
        # Add new images
        added = 0
        for i, img_url in enumerate(images):
            if needs_resize:
                # Télécharger et redimensionner en 750x500 fond blanc
                b64 = _resize_goat_image_to_750x500(img_url)
                if b64:
                    result = shopify_request(f'products/{product_id}/images.json', 'POST', {
                        'image': {'attachment': b64, 'position': i + 1, 'filename': f'goat_{product_id}_{i+1}.png'}
                    })
                else:
                    # Fallback: envoyer l'URL telle quelle
                    result = shopify_request(f'products/{product_id}/images.json', 'POST', {
                        'image': {'src': img_url, 'position': i + 1}
                    })
            else:
                result = shopify_request(f'products/{product_id}/images.json', 'POST', {
                    'image': {'src': img_url, 'position': i + 1}
                })
            if result:
                added += 1
            time.sleep(0.3)
        
        log.info(f"[GOAT Apply] Added {added} images to product {product_id} (resized={needs_resize})")
        
        return jsonify({'success': True, 'added': added, 'resized': needs_resize})
        
    except Exception as e:
        log.error(f"[GOAT Apply] Error: {e}")
        return jsonify({'error': str(e)}), 500


def _resize_goat_image_to_750x500(image_url):
    """Télécharge une image GOAT et la place centrée sur un canvas 750x500 fond blanc.
    Retourne le base64 PNG pour envoi à Shopify, ou None en cas d'erreur."""
    try:
        from PIL import Image
        from io import BytesIO
        import base64
        log.info(f"[GOAT Resize] Starting resize for: {image_url[:80]}...")
    except ImportError:
        log.error("[GOAT Resize] Pillow (PIL) not installed! Add 'Pillow>=10.0' to requirements.txt")
        return None
    
    try:
        # Télécharger l'image
        img_data = None
        sess = _get_goat_session()
        if sess:
            try:
                r = sess.get(image_url, timeout=15)
                log.info(f"[GOAT Resize] Download status: {r.status_code}, size: {len(r.content)} bytes")
                if r.status_code == 200:
                    img_data = r.content
            except Exception as e:
                log.warning(f"[GOAT Resize] Session download failed: {e}")
        
        if not img_data:
            import subprocess
            result = subprocess.run(
                ["curl", "-s", "-m", "15", "-L", image_url,
                 "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"],
                capture_output=True, timeout=20)
            if result.returncode == 0 and result.stdout:
                img_data = result.stdout
                log.info(f"[GOAT Resize] curl download: {len(img_data)} bytes")
            else:
                log.error(f"[GOAT Resize] curl download failed: rc={result.returncode}")
                return None
        
        if not img_data or len(img_data) < 1000:
            log.error(f"[GOAT Resize] Image data too small: {len(img_data) if img_data else 0} bytes")
            return None
        
        # Ouvrir l'image source
        src = Image.open(BytesIO(img_data)).convert('RGBA')
        src_w, src_h = src.size
        log.info(f"[GOAT Resize] Source: {src_w}x{src_h}")
        
        # Canvas cible: 750x500 fond blanc
        target_w, target_h = 750, 500
        canvas = Image.new('RGB', (target_w, target_h), (255, 255, 255))
        
        # Cadrage façon GOAT : sneaker occupe ~85% de la largeur, centrée verticalement un poil bas
        padding_h = 20   # Petit padding horizontal
        padding_top = 15  # Petit padding en haut
        padding_bottom = 25  # Un peu plus en bas (ombre/semelle)
        max_w = target_w - (padding_h * 2)
        max_h = target_h - padding_top - padding_bottom
        
        # Ratio proportionnel (sans déformer)
        ratio = min(max_w / src_w, max_h / src_h)
        new_w = int(src_w * ratio)
        new_h = int(src_h * ratio)
        
        # Redimensionner la sneaker
        resized = src.resize((new_w, new_h), Image.LANCZOS)
        
        # Centrer horizontalement, positionner verticalement avec le padding
        x = (target_w - new_w) // 2
        y = padding_top + (max_h - new_h) // 2
        
        # Coller avec gestion de la transparence
        canvas.paste(resized, (x, y), resized if resized.mode == 'RGBA' else None)
        
        # Convertir en base64 PNG
        buffer = BytesIO()
        canvas.save(buffer, format='PNG', quality=95)
        b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        log.info(f"[GOAT Resize] Resized {src_w}x{src_h} -> {new_w}x{new_h} on 750x500 canvas")
        return b64
        
    except Exception as e:
        log.error(f"[GOAT Resize] Error: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# IMAGE FIX API (renommer fichiers + texte alternatif)
# ══════════════════════════════════════════════════════════════

def shopify_graphql(query, variables=None):
    """Exécute une requête GraphQL Shopify"""
    url = f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json"
    headers = {'X-Shopify-Access-Token': ACCESS_TOKEN, 'Content-Type': 'application/json'}
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    try:
        req = Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urlopen(req, context=ctx, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        log.error(f"[Shopify GraphQL] {e}")
        return None


def rename_image_file(image_gid, new_filename):
    """Renomme un fichier image via GraphQL fileUpdate"""
    query = """
    mutation fileUpdate($files: [FileUpdateInput!]!) {
        fileUpdate(files: $files) {
            files { id alt }
            userErrors { field message }
        }
    }
    """
    variables = {
        "files": [{
            "id": image_gid,
            "filename": new_filename
        }]
    }
    log.info(f"[ImageRename] Calling GraphQL: gid={image_gid}, filename={new_filename}")
    result = shopify_graphql(query, variables)
    log.info(f"[ImageRename] GraphQL result: {result}")
    
    if not result:
        log.error("[ImageRename] GraphQL returned None")
        return False
    
    if result.get('errors'):
        log.error(f"[ImageRename] GraphQL errors: {result['errors']}")
        return False
    
    user_errors = result.get('data', {}).get('fileUpdate', {}).get('userErrors', [])
    if user_errors:
        log.error(f"[ImageRename] userErrors: {user_errors}")
        return False
    
    return True


@app.route('/api/images/test-rename/<int:product_id>')
def api_test_rename(product_id):
    """Debug: teste le renommage de la première image d'un produit"""
    r = shopify_request(f'products/{product_id}.json')
    if not r or 'product' not in r:
        return jsonify({'error': 'Produit non trouvé'})
    
    product = r['product']
    title = product['title']
    images = product.get('images', [])
    title_for_filename = title_to_filename(title)
    
    if not images:
        return jsonify({'error': 'Pas d images'})
    
    # Récupérer media GID
    gql_query = """
    query getProductMedia($id: ID!) {
        product(id: $id) {
            media(first: 5) {
                edges { node { id } }
            }
        }
    }
    """
    gql_result = shopify_graphql(gql_query, {"id": f"gid://shopify/Product/{product_id}"})
    
    if not gql_result or not gql_result.get('data', {}).get('product', {}).get('media', {}).get('edges'):
        return jsonify({'error': 'Pas de media GIDs', 'graphql_result': gql_result})
    
    media_gid = gql_result['data']['product']['media']['edges'][0]['node']['id']
    
    current_src = images[0].get('src', '')
    current_filename = current_src.split('/')[-1].split('?')[0] if current_src else ''
    ext = current_filename.split('.')[-1] if '.' in current_filename else 'jpg'
    new_filename = f"{title_for_filename}_{product_id}_1.{ext}"
    
    # Exécuter le rename
    rename_query = """
    mutation fileUpdate($files: [FileUpdateInput!]!) {
        fileUpdate(files: $files) {
            files { id alt }
            userErrors { field message }
        }
    }
    """
    rename_vars = {"files": [{"id": media_gid, "filename": new_filename}]}
    rename_result = shopify_graphql(rename_query, rename_vars)
    
    return jsonify({
        'product': title,
        'media_gid': media_gid,
        'current_filename': current_filename,
        'new_filename': new_filename,
        'rename_result': rename_result
    })


def fix_product_images(product_id):
    """Corrige les images d'un produit : nom = Titre_Produit_N.ext, alt = titre produit
    Version optimisée : 1 GET + 1 PUT produit + 1 GraphQL batch = 3 appels max"""
    import time
    r = shopify_request(f'products/{product_id}.json')
    if not r or 'product' not in r:
        return {'success': False, 'error': 'Produit non trouvé'}
    
    product = r['product']
    title = product['title']
    images = product.get('images', [])
    
    if not images:
        return {'success': True, 'fixed': 0, 'total': 0, 'title': title}
    
    title_for_filename = title_to_filename(title)
    fixed = 0
    
    # ── 1. Alt text : batch via un seul PUT produit ──
    alt_updates = []
    needs_alt = False
    for i, img in enumerate(images):
        current_alt = img.get('alt', '') or ''
        if current_alt != title:
            needs_alt = True
        alt_updates.append({'id': img['id'], 'alt': title})
    
    if needs_alt:
        update_data = {'product': {'id': product_id, 'images': alt_updates}}
        result = shopify_request(f'products/{product_id}.json', 'PUT', update_data)
        if result:
            fixed += 1
            log.info(f"[ImageFix] {title}: alt text updated for all images")
    
    # ── 2. Filename : batch via un seul GraphQL fileUpdate ──
    # D'abord récupérer les media GIDs
    gql_query = """
    query getProductMedia($id: ID!) {
        product(id: $id) {
            media(first: 50) {
                edges { node { id } }
            }
        }
    }
    """
    gql_result = shopify_graphql(gql_query, {"id": f"gid://shopify/Product/{product_id}"})
    media_gids = []
    if gql_result and gql_result.get('data', {}).get('product', {}).get('media', {}).get('edges'):
        media_gids = [e['node']['id'] for e in gql_result['data']['product']['media']['edges']]
    
    # Préparer le batch de renommage
    files_to_rename = []
    for i, img in enumerate(images):
        if i >= len(media_gids):
            break
        current_src = img.get('src', '') or ''
        current_filename = current_src.split('/')[-1].split('?')[0] if current_src else ''
        
        if title_for_filename in current_filename:
            continue  # Déjà renommé
        
        ext = 'jpg'
        if '.' in current_filename:
            ext = current_filename.split('.')[-1].lower()
        
        new_filename = f"{title_for_filename}_{product_id}_{i+1}.{ext}"
        files_to_rename.append({"id": media_gids[i], "filename": new_filename})
    
    if files_to_rename:
        # Un seul appel GraphQL pour renommer TOUTES les images
        rename_query = """
        mutation fileUpdate($files: [FileUpdateInput!]!) {
            fileUpdate(files: $files) {
                files { id }
                userErrors { field message }
            }
        }
        """
        rename_result = shopify_graphql(rename_query, {"files": files_to_rename})
        rename_errors = []
        if rename_result and not rename_result.get('errors'):
            user_errors = rename_result.get('data', {}).get('fileUpdate', {}).get('userErrors', [])
            if not user_errors:
                fixed += len(files_to_rename)
                log.info(f"[ImageFix] {title}: {len(files_to_rename)} images renamed in batch")
            else:
                rename_errors = user_errors
                log.error(f"[ImageFix] {title}: rename errors: {user_errors}")
        else:
            rename_errors = rename_result.get('errors', []) if rename_result else [{'message': 'GraphQL call failed'}]
            log.error(f"[ImageFix] {title}: GraphQL error: {rename_result}")
        
        if rename_errors:
            return {'success': True, 'fixed': fixed, 'total': len(images), 'title': title, 
                    'rename_errors': rename_errors, 'attempted_filenames': [f['filename'] for f in files_to_rename]}
    
    time.sleep(0.2)  # Petit délai entre produits
    
    return {'success': True, 'fixed': fixed, 'total': len(images), 'title': title}


@app.route('/api/images/fix', methods=['POST'])
def api_fix_images():
    """Corrige les images d'un seul produit"""
    try:
        data = request.json
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({'success': False, 'error': 'product_id manquant'}), 400
        
        result = fix_product_images(product_id)
        return jsonify(result)
    except Exception as e:
        log.error(f"[ImageFix] Error on product: {e}")
        return jsonify({'success': False, 'fixed': 0, 'total': 0, 'error': str(e)})


@app.route('/api/images/test/<int:product_id>')
def api_test_image_fix(product_id):
    """Debug: teste le fix d'images sur un produit et retourne les détails"""
    r = shopify_request(f'products/{product_id}.json')
    if not r or 'product' not in r:
        return jsonify({'error': 'Produit non trouvé'})
    
    product = r['product']
    title = product['title']
    handle = product['handle']
    images = product.get('images', [])
    title_for_filename = title_to_filename(title)
    
    # Récupérer media GIDs
    gql_query = """
    query getProductMedia($id: ID!) {
        product(id: $id) {
            media(first: 50) {
                edges { node { id } }
            }
        }
    }
    """
    gql_result = shopify_graphql(gql_query, {"id": f"gid://shopify/Product/{product_id}"})
    media_gids = []
    gql_raw = gql_result
    if gql_result and gql_result.get('data', {}).get('product', {}).get('media', {}).get('edges'):
        media_gids = [e['node']['id'] for e in gql_result['data']['product']['media']['edges']]
    
    image_details = []
    for i, img in enumerate(images):
        current_src = img.get('src', '') or ''
        current_filename = current_src.split('/')[-1].split('?')[0] if current_src else ''
        ext = current_filename.split('.')[-1] if '.' in current_filename else 'jpg'
        new_filename = f"{title_for_filename}_{product_id}_{i+1}.{ext}"
        
        image_details.append({
            'index': i+1,
            'current_alt': img.get('alt', ''),
            'new_alt': title,
            'current_filename': current_filename,
            'new_filename': new_filename,
            'media_gid': media_gids[i] if i < len(media_gids) else 'NOT FOUND',
            'img_id': img['id']
        })
    
    return jsonify({
        'product': title,
        'handle': handle,
        'images_count': len(images),
        'media_gids_count': len(media_gids),
        'graphql_raw': gql_raw,
        'images': image_details
    })


@app.route('/api/images/fix-all', methods=['POST'])
def api_fix_all_images():
    """Corrige les images de TOUS les produits via fix_product_images"""
    import time
    
    total_fixed = 0
    total_images = 0
    processed = 0
    since_id = 0
    
    for _ in range(20):
        r = shopify_request(f'products.json?limit=250&since_id={since_id}')
        if not r or 'products' not in r or not r['products']:
            break
        
        for product in r['products']:
            pid = product['id']
            result = fix_product_images(pid)
            if result.get('success'):
                total_fixed += result.get('fixed', 0)
                total_images += result.get('total', 0)
            processed += 1
            
            if processed % 10 == 0:
                log.info(f"[ImageFix] Progress: {processed} products, {total_fixed} fixed")
        
        since_id = r['products'][-1]['id']
        if len(r['products']) < 250:
            break
    
    log.info(f"[ImageFix] Done: {processed} products, {total_fixed}/{total_images} images fixed")
    
    return jsonify({
        'success': True,
        'processed': processed,
        'total_fixed': total_fixed,
        'total_images': total_images
    })


# ══════════════════════════════════════════════════════════════
# BLOG API
# ══════════════════════════════════════════════════════════════

@app.route('/api/blogs')
def api_blogs():
    """Liste tous les blogs Shopify"""
    r = shopify_request('blogs.json')
    if not r:
        return jsonify({'error': 'Impossible de récupérer les blogs. Vérifiez les permissions API (scope: read_content)'}), 403
    return jsonify(r)


@app.route('/api/blogs/<int:blog_id>/articles')
def api_blog_articles(blog_id):
    """Liste les articles d'un blog"""
    r = shopify_request(f'blogs/{blog_id}/articles.json')
    if not r:
        return jsonify({'error': 'Impossible de récupérer les articles'}), 403
    return jsonify(r)


@app.route('/api/blogs/<int:blog_id>/articles', methods=['POST'])
def api_create_article(blog_id):
    """Crée un nouvel article de blog"""
    data = request.json
    
    article_data = {
        'article': {
            'title': data.get('title', ''),
            'author': data.get('author', 'KP SHOES'),
            'body_html': data.get('body_html', ''),
            'published': data.get('published', True),
            'tags': data.get('tags', ''),
            'summary_html': data.get('summary_html', ''),  # Extrait
            'metafields': []
        }
    }
    
    # Ajouter image si fournie
    if data.get('image_url'):
        article_data['article']['image'] = {'src': data.get('image_url')}
    
    # Ajouter meta title
    if data.get('meta_title'):
        article_data['article']['metafields'].append({
            'namespace': 'global',
            'key': 'title_tag',
            'value': data.get('meta_title'),
            'type': 'single_line_text_field'
        })
    
    # Ajouter meta description
    if data.get('meta_description'):
        article_data['article']['metafields'].append({
            'namespace': 'global',
            'key': 'description_tag',
            'value': data.get('meta_description'),
            'type': 'single_line_text_field'
        })
    
    # Supprimer metafields si vide
    if not article_data['article']['metafields']:
        del article_data['article']['metafields']
    
    r = shopify_request(f'blogs/{blog_id}/articles.json', 'POST', article_data)
    if not r:
        return jsonify({'error': 'Impossible de créer l\'article. Vérifiez les permissions API (scope: write_content)'}), 403
    return jsonify({'success': True, 'article': r.get('article', {})})


@app.route('/api/blogs/<int:blog_id>/articles/<int:article_id>', methods=['PUT'])
def api_update_article(blog_id, article_id):
    """Met à jour un article de blog"""
    data = request.json
    
    article_data = {
        'article': {
            'id': article_id,
            'title': data.get('title'),
            'body_html': data.get('body_html'),
            'published': data.get('published'),
            'tags': data.get('tags')
        }
    }
    
    # Nettoyer les None
    article_data['article'] = {k: v for k, v in article_data['article'].items() if v is not None}
    
    r = shopify_request(f'blogs/{blog_id}/articles/{article_id}.json', 'PUT', article_data)
    if not r:
        return jsonify({'error': 'Impossible de modifier l\'article'}), 403
    return jsonify({'success': True, 'article': r.get('article', {})})


@app.route('/api/blogs/<int:blog_id>/articles/<int:article_id>', methods=['DELETE'])
def api_delete_article(blog_id, article_id):
    """Supprime un article de blog"""
    r = shopify_request(f'blogs/{blog_id}/articles/{article_id}.json', 'DELETE')
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════
# BLOG GENERATOR API
# ══════════════════════════════════════════════════════════════

def get_products_for_linking():
    """Récupère TOUS les produits Shopify pour créer des liens internes"""
    products = []
    since_id = 0
    
    # Boucler jusqu'à avoir tous les produits
    for _ in range(20):  # Max 20 pages = 5000 produits
        r = shopify_request(f'products.json?limit=250&since_id={since_id}')
        if not r or 'products' not in r or not r['products']:
            break
        
        for p in r['products']:
            sku = p['variants'][0].get('sku', '') if p.get('variants') else ''
            img = ''
            if p.get('images') and len(p['images']) > 0:
                img = p['images'][0].get('src', '')
            
            products.append({
                'id': p['id'],
                'title': p['title'],
                'handle': p['handle'],
                'sku': sku,
                'image': img,
                'url': f"https://{SITE_DOMAIN}/products/{p['handle']}"
            })
        
        since_id = r['products'][-1]['id']
        
        # Si moins de 250 produits retournés, on a tout
        if len(r['products']) < 250:
            break
    
    log.info(f"[Blog] Loaded {len(products)} products for linking")
    return products


def search_product_by_title(subject):
    """Recherche un produit spécifique par son titre via l'API Shopify"""
    import urllib.parse
    
    # Essayer une recherche directe
    r = shopify_request(f'products.json?title={urllib.parse.quote(subject)}&limit=5')
    if r and r.get('products'):
        for p in r['products']:
            img = ''
            if p.get('images') and len(p['images']) > 0:
                img = p['images'][0].get('src', '')
            return {
                'id': p['id'],
                'title': p['title'],
                'handle': p['handle'],
                'sku': p['variants'][0].get('sku', '') if p.get('variants') else '',
                'image': img,
                'url': f"https://{SITE_DOMAIN}/products/{p['handle']}"
            }
    
    # Fallback : recherche avec des mots-clés
    # Extraire les mots importants du sujet
    words = subject.lower().split()
    stop = ['air', 'nike', 'adidas', 'new', 'balance', 'retro', 'high', 'low', 'mid', 'og', 'sp', 'se', 'the', 'a', 'x', 'men', 'women']
    important = [w for w in words if w not in stop and len(w) > 1]
    
    # Essayer avec les 3-4 mots-clés les plus importants
    for num_words in [4, 3, 2]:
        if len(important) >= num_words:
            search_terms = ' '.join(important[:num_words])
            r = shopify_request(f'products.json?title={urllib.parse.quote(search_terms)}&limit=10')
            if r and r.get('products'):
                # Scorer les résultats
                best = None
                best_score = 0
                subject_lower = subject.lower()
                for p in r['products']:
                    title_lower = p['title'].lower()
                    score = sum(1 for w in important if w in title_lower)
                    if subject_lower in title_lower or title_lower in subject_lower:
                        score += 20
                    if score > best_score:
                        best_score = score
                        best = p
                
                if best and best_score >= 2:
                    img = ''
                    if best.get('images') and len(best['images']) > 0:
                        img = best['images'][0].get('src', '')
                    log.info(f"[Blog] Found product by search: {best['title']} (score={best_score})")
                    return {
                        'id': best['id'],
                        'title': best['title'],
                        'handle': best['handle'],
                        'sku': best['variants'][0].get('sku', '') if best.get('variants') else '',
                        'image': img,
                        'url': f"https://{SITE_DOMAIN}/products/{best['handle']}"
                    }
    
    return None


def find_matching_products(subject, products):
    """Trouve les produits correspondant au sujet - amélioré pour les noms longs et collabs"""
    matches = []
    subject_lower = subject.lower()
    
    # Nettoyer le sujet pour extraire les mots-clés importants
    subject_clean = subject_lower.replace('-', ' ')
    # Garder tous les mots significatifs
    stop_words = ['air', 'nike', 'adidas', 'new', 'balance', 'retro', 'high', 'low', 'mid', 'og', 'sp', 'se', 'the', 'le', 'la', 'de', 'a', 'x']
    keywords = [kw for kw in subject_clean.split() if len(kw) > 1]
    important_keywords = [kw for kw in keywords if kw not in stop_words]
    
    for p in products:
        title_lower = p['title'].lower()
        score = 0
        
        # Vérifier chaque mot-clé important
        for kw in important_keywords:
            if kw in title_lower:
                if kw.isdigit() or kw in ['dunk', 'jordan', 'yeezy', 'samba', 'campus', 'force', 'max', 'gel', 'mind', 'fragment', 'union', 'travis', 'sacai', 'off-white']:
                    score += 3
                else:
                    score += 2
        
        # Vérifier aussi les mots non-importants (air, nike, etc.)
        for kw in keywords:
            if kw in stop_words and kw in title_lower:
                score += 0.5
        
        # Bonus si le sujet complet est dans le titre
        if subject_lower in title_lower:
            score += 20
        
        # Bonus pour correspondances partielles fortes
        # Chercher des combinaisons de 2-3 mots clés
        for i in range(len(important_keywords) - 1):
            combo = important_keywords[i] + ' ' + important_keywords[i+1]
            if combo in title_lower:
                score += 5
        
        # Chercher le nom du modèle sans la marque
        # Ex: "Jordan 1" dans "Air Jordan 1 Retro..."
        if len(important_keywords) >= 2:
            model_combo = ' '.join(important_keywords[:3])
            if model_combo in title_lower:
                score += 8
        
        # Bonus pour les collabs
        collab_names = ['fragment', 'union', 'travis', 'sacai', 'off-white', 'fear of god', 'a ma maniere', 'patta']
        for collab in collab_names:
            if collab in subject_lower and collab in title_lower:
                score += 5
        
        if score > 0:
            matches.append((score, p))
    
    # Trier par score décroissant
    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in matches[:10]]


def generate_article_content(article_type, subject, keywords, tone, length, products, collections, research=None):
    """Génère le contenu de l'article - utilise les données de recherche web si disponibles"""
    
    # Trouver les produits et collections liés
    matching_products = find_matching_products(subject, products)
    matching_collection = find_collection(subject, collections)
    
    log.info(f"[Blog] Found {len(matching_products)} matching products for '{subject}'")
    
    # ── Chercher la paire EXACTE ──
    # D'abord via l'API Shopify (recherche directe par titre)
    exact_product = search_product_by_title(subject)
    
    # Si pas trouvé via API, chercher dans la liste chargée
    if not exact_product:
        subject_lower = subject.lower()
        for p in products:
            title_lower = p['title'].lower()
            if subject_lower in title_lower or title_lower in subject_lower:
                exact_product = p
                break
    
    # Si toujours pas, chercher avec scoring dans les matching
    if not exact_product and matching_products:
        subject_words = set(w for w in subject.lower().split() if len(w) > 2)
        best_score = 0
        for p in matching_products:
            p_words = set(w for w in p['title'].lower().split() if len(w) > 2)
            common = len(subject_words & p_words)
            if common > best_score and common >= len(subject_words) * 0.5:
                best_score = common
                exact_product = p
    
    if exact_product:
        log.info(f"[Blog] Exact product found: {exact_product['title']}")
    
    # ── Section produit dédiée ──
    product_links = ""
    if exact_product or matching_products:
        product_links = f'<h2>Acheter la {subject} sur KP SHOES</h2>'
        
        # Mettre la paire exacte en premier, bien mise en avant
        if exact_product:
            exact_img = f'<img src="{exact_product["image"]}" style="width:100%;max-width:300px;height:auto;border-radius:10px;margin:10px auto;display:block">' if exact_product.get('image') else ''
            product_links += f'''<div style="text-align:center;margin:20px 0;padding:20px;border-radius:12px">
                {exact_img}
                <div style="font-size:16px;font-weight:600;margin:10px 0;color:#333">{exact_product['title']}</div>
                <a href="{exact_product['url']}" style="display:inline-block;padding:10px 25px;background:#667eea;color:white;text-decoration:none;border-radius:8px;font-weight:600;margin:10px 0">Voir cette paire →</a>
            </div>'''
        
        # Ajouter les autres produits similaires
        other_products = [p for p in matching_products if not exact_product or p['id'] != exact_product['id']]
        if other_products:
            product_links += '<p style="margin-top:20px"><strong>Paires similaires disponibles :</strong></p>'
            product_links += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:15px;margin:10px 0">'
            for p in other_products[:5]:
                img_html = f'<img src="{p["image"]}" style="width:100%;height:120px;object-fit:contain;border-radius:8px">' if p.get('image') else '<div style="width:100%;height:120px;border-radius:8px"></div>'
                product_links += f'''<a href="{p['url']}" style="text-decoration:none;color:inherit;display:block">
                    {img_html}
                    <div style="font-size:12px;margin-top:8px;color:#333;text-align:center;line-height:1.3">{p['title'][:50]}{"..." if len(p['title']) > 50 else ""}</div>
                </a>'''
            product_links += "</div>"
    
    # Lien collection
    collection_link = ""
    if matching_collection:
        collection_link = f'<p style="margin:20px 0">👉 <strong><a href="{matching_collection["url"]}">Voir toute la collection {matching_collection["title"]}</a></strong></p>'
    
    # Construire le bloc HTML des infos web trouvées
    web_info_html = build_web_info_html(research, subject)
    
    # Stocker le produit exact pour l'image
    # On passe exact_product via un attribut sur l'article retourné
    result = None
    if article_type == "guide_taille":
        result = generate_sizing_guide(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "release":
        result = generate_release_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "tendance":
        result = generate_trend_article(subject, product_links, collection_link, tone, matching_products, web_info_html, research)
    elif article_type == "comparatif":
        result = generate_comparison_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "histoire":
        result = generate_history_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "entretien":
        result = generate_care_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "style":
        result = generate_style_article(subject, product_links, collection_link, tone, web_info_html, research)
    else:
        result = generate_custom_article(subject, keywords, product_links, collection_link, tone, web_info_html, research)
    
    # Si on a trouvé la paire exacte, utiliser son image directement
    if exact_product and exact_product.get('image'):
        result['image_url'] = exact_product['image']
        result['needs_image'] = False  # Pas besoin de chercher sur GOAT
        log.info(f"[Blog] Using exact product image: {exact_product['title']}")
    
    return result




def translate_to_french(text):
    """Traduit un texte en français via Google Translate (gratuit, pas de clé)"""
    if not text or len(text) < 10:
        return text
    
    # Détecter si c'est déjà en français
    french_indicators = [' le ', ' la ', ' les ', ' des ', ' une ', ' est ', ' sont ', ' dans ', ' pour ', ' avec ', ' cette ', ' sur ', ' qui ', ' que ']
    text_lower = text.lower()
    french_count = sum(1 for ind in french_indicators if ind in text_lower)
    if french_count >= 3:
        return text
    
    try:
        import urllib.parse
        # Protéger les noms de produits/marques avant traduction
        # Remplacer temporairement par des placeholders
        protected = {}
        protected_text = text
        brands = ['Nike Mind', 'Air Jordan', 'Air Force', 'Air Max', 'Dunk Low', 'Dunk High', 
                  'New Balance', 'Nike SB', 'Jordan Brand', 'Mind 001', 'Mind 002',
                  'Fragment', 'Union LA', 'Travis Scott', 'Off-White', 'Sacai']
        idx = 0
        for brand in brands:
            if brand in protected_text:
                placeholder = f'XBRAND{idx}X'
                protected[placeholder] = brand
                protected_text = protected_text.replace(brand, placeholder)
                idx += 1
        
        encoded = urllib.parse.quote(protected_text[:2000])
        url = f'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=fr&dt=t&q={encoded}'
        
        html = fetch_url(url, timeout=8)
        if html:
            data = json.loads(html)
            translated = ''.join([s[0] for s in data[0] if s[0]])
            if translated and len(translated) > 10:
                # Restaurer les noms protégés
                for placeholder, original in protected.items():
                    translated = translated.replace(placeholder, original)
                    # Google Translate met parfois des espaces autour
                    translated = translated.replace(placeholder.lower(), original)
                    translated = translated.replace(placeholder.replace('X', 'x'), original)
                return translated
    except Exception as e:
        log.error(f"[Translate] Error: {e}")
    
    return text


def build_web_info_html(research, subject):
    """Construit le HTML des informations trouvées sur le web, traduit en français"""
    if not research or not research.get('found'):
        return ""
    
    html = ""
    
    # Wikipedia
    wiki = research.get('wikipedia')
    if wiki and wiki.get('extract'):
        extract = wiki['extract']
        if len(extract) > 500:
            extract = extract[:500].rsplit(' ', 1)[0] + '...'
        # Traduire si en anglais
        extract = translate_to_french(extract)
        html += f'<div style="margin:20px 0">'
        html += f'<p style="margin:0">{extract}</p>'
        html += f'</div>'
    
    # Résultats de recherche
    results = research.get('search_results', [])
    if results:
        clean_results = []
        seen = set()
        
        # Mots de bruit à filtrer
        junk_patterns = [
            'fashionfootwear', 'artdesignmusic', 'cookie', 'privacy', 'subscribe',
            'newsletter', 'sign up', 'log in', 'download the', 'scan the qr',
            'some languages may be', 'accuracy may vary', 'turn on code suggestion',
            'brand ranking', 'brand directory', 'magazine', 'morefashion',
            'don\'t show again', 'app stores', 'cmd', 'copyright', 'terms of use',
            'all rights reserved', 'follow us', 'stay ahead', 'get the latest'
        ]
        
        for r in results:
            r_clean = r.strip()
            r_lower = r_clean.lower()
            
            if any(junk in r_lower for junk in junk_patterns):
                continue
            if len(r_clean) < 50:
                continue
            
            key = r_lower[:60]
            if key in seen:
                continue
            seen.add(key)
            
            if len(r_clean) > 400:
                r_clean = r_clean[:400].rsplit(' ', 1)[0] + '...'
            
            # Nettoyer les entités HTML
            r_clean = r_clean.replace('&quot;', '"').replace('&#039;', "'").replace('&amp;', '&').replace('&#x27;', "'").replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'")
            
            clean_results.append(r_clean)
        
        if clean_results:
            # Traduire chaque résultat en français
            translated_results = []
            for r in clean_results[:6]:
                translated = translate_to_french(r)
                translated_results.append(translated)
            
            html += f'<h2>Ce que l\'on sait sur la {subject}</h2>'
            html += '<div style="margin:20px 0">'
            for r in translated_results:
                html += f'<p style="margin:10px 0;line-height:1.6">{r}</p>'
            html += '</div>'
    
    return html


def generate_sizing_guide(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un guide de tailles"""
    title = f"Comment taille la {subject} ? Guide complet des tailles 2026"
    
    meta_title = f"Comment taille la {subject} ? Guide tailles 2026 | KP SHOES"[:70]
    meta_description = f"Découvrez comment taille la {subject}. Tableau des tailles EU/US/UK, conseils pour pieds larges et comparaison avec d'autres modèles. Guide complet."[:160]
    summary = f"Vous vous demandez comment taille la {subject} ? Découvrez notre guide complet avec tableau des tailles et conseils."
    
    body = f"""
<p>Vous vous demandez <strong>comment taille la {subject}</strong> ? Ce guide complet vous aide à choisir la bonne pointure. Chez <strong>KP SHOES</strong>, nous garantissons l'authenticité de chaque paire.</p>

{web_info_html}

<h2>La {subject} taille-t-elle grand ou petit ?</h2>
<p>La {subject} est réputée pour <strong>tailler normalement</strong>. Si vous êtes entre deux tailles, nous vous conseillons de prendre la taille supérieure pour plus de confort, surtout si vous avez les pieds larges.</p>

<h2>Tableau des tailles {subject}</h2>
<table style="width:100%;border-collapse:collapse;margin:20px 0">
<tr style="background:#f5f5f5"><th style="padding:12px;border:1px solid #ddd;text-align:center">EU</th><th style="padding:12px;border:1px solid #ddd;text-align:center">US Homme</th><th style="padding:12px;border:1px solid #ddd;text-align:center">US Femme</th><th style="padding:12px;border:1px solid #ddd;text-align:center">UK</th><th style="padding:12px;border:1px solid #ddd;text-align:center">CM</th></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">38</td><td style="padding:10px;border:1px solid #ddd;text-align:center">5.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7</td><td style="padding:10px;border:1px solid #ddd;text-align:center">5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">24</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">39</td><td style="padding:10px;border:1px solid #ddd;text-align:center">6.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8</td><td style="padding:10px;border:1px solid #ddd;text-align:center">6</td><td style="padding:10px;border:1px solid #ddd;text-align:center">24.5</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">40</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">6</td><td style="padding:10px;border:1px solid #ddd;text-align:center">25</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">41</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8</td><td style="padding:10px;border:1px solid #ddd;text-align:center">9.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7</td><td style="padding:10px;border:1px solid #ddd;text-align:center">26</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">42</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">10</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">26.5</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">43</td><td style="padding:10px;border:1px solid #ddd;text-align:center">9.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">27.5</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">44</td><td style="padding:10px;border:1px solid #ddd;text-align:center">10</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">9</td><td style="padding:10px;border:1px solid #ddd;text-align:center">28</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">45</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11</td><td style="padding:10px;border:1px solid #ddd;text-align:center">12.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">10</td><td style="padding:10px;border:1px solid #ddd;text-align:center">29</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">46</td><td style="padding:10px;border:1px solid #ddd;text-align:center">12</td><td style="padding:10px;border:1px solid #ddd;text-align:center">13.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11</td><td style="padding:10px;border:1px solid #ddd;text-align:center">30</td></tr>
</table>

<h2>Conseils pour bien choisir sa taille</h2>
<ul>
<li><strong>Pieds larges</strong> : Prenez une demi-taille au-dessus</li>
<li><strong>Pieds fins</strong> : Restez sur votre taille habituelle</li>
<li><strong>Entre deux tailles</strong> : Optez pour la taille supérieure</li>
<li><strong>Pour le style</strong> : Certains préfèrent une taille au-dessus pour un look plus loose</li>
</ul>

<h2>Comparaison avec d'autres modèles</h2>
<p>Si vous connaissez votre taille dans d'autres modèles, voici quelques repères :</p>
<ul>
<li>Même taille que les Nike Air Force 1</li>
<li>Même taille que les Nike Dunk Low</li>
<li>Une demi-taille au-dessus des Adidas (Samba, Campus)</li>
<li>Même taille que les New Balance 550</li>
</ul>

{collection_link}

{product_links}

<h2>FAQ - Questions fréquentes</h2>
<h3>La {subject} taille-t-elle grand ?</h3>
<p>Non, la {subject} taille normalement. Prenez votre taille habituelle Nike.</p>

<h3>Dois-je prendre une taille au-dessus ?</h3>
<p>Uniquement si vous avez les pieds larges ou si vous êtes entre deux tailles.</p>

<h3>Comment mesurer son pied ?</h3>
<p>Mesurez votre pied le soir (quand il est légèrement gonflé) du talon au bout du gros orteil, et reportez-vous au tableau ci-dessus.</p>

<p><strong>Chez KP SHOES, toutes nos sneakers sont 100% authentiques et vérifiées par nos experts.</strong> Livraison rapide et paiement sécurisé.</p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'guide taille, {subject}, sizing, pointure',
        'handle': f'guide-taille-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_release_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur les sorties"""
    import datetime
    month = datetime.datetime.now().strftime('%B %Y')
    
    title = f"Sorties {subject} {month} : Calendrier et dates de release"
    meta_title = f"Sorties {subject} 2026 : Dates et calendrier | KP SHOES"[:70]
    meta_description = f"Découvrez toutes les sorties {subject} prévues en 2026. Calendrier des releases, dates de sortie et conseils pour cop les paires limitées."[:160]
    summary = f"Toutes les sorties {subject} à ne pas manquer. Calendrier des releases, dates clés et conseils pour réussir vos achats."
    
    body = f"""
<p>Découvrez toutes les <strong>sorties {subject}</strong> prévues pour {month}. Restez informé des dernières releases et ne manquez aucune paire sur <strong>KP SHOES</strong>.</p>

<h2>Les releases {subject} à ne pas manquer</h2>
<p>L'année 2026 s'annonce riche en sorties pour les fans de {subject}. Voici les dates clés à retenir.</p>

<h2>Comment cop les {subject} en édition limitée ?</h2>
<ul>
<li><strong>Suivez les comptes officiels</strong> : Nike SNKRS, Jordan, et les réseaux sociaux des marques</li>
<li><strong>Activez les notifications</strong> : Soyez alerté dès l'annonce d'une nouvelle release</li>
<li><strong>Préparez vos comptes</strong> : Créez vos profils sur les apps de raffle à l'avance</li>
<li><strong>Achetez sur des sites de confiance</strong> : KP SHOES garantit l'authenticité de chaque paire</li>
</ul>

{collection_link}

<h2>Les coloris les plus attendus</h2>
<p>Parmi les sorties les plus anticipées, certains coloris font déjà parler d'eux dans la communauté sneakers. Les collaborations et les éditions limitées restent les plus recherchées.</p>

{product_links}

<h2>Prix et disponibilité</h2>
<p>Les prix retail varient généralement entre 110€ et 200€ selon les modèles. Sur le marché de la revente, certaines paires peuvent atteindre des prix bien plus élevés, notamment les collaborations.</p>

<p><strong>Sur KP SHOES, retrouvez ces modèles 100% authentiques avec livraison rapide et paiement sécurisé.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'sortie, release, {subject}, calendrier, 2026',
        'handle': f'sorties-{subject.lower().replace(" ", "-")}-2026',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_trend_article(subject, product_links, collection_link, tone, matching_products, web_info_html='', research=None):
    """Génère un article sur les tendances"""
    title = "Sneakers tendance 2026 : Les modèles les plus hype du moment"
    meta_title = "Sneakers tendance 2026 : Les modèles incontournables | KP SHOES"
    meta_description = "Découvrez les sneakers les plus tendance en 2026. Running rétro, classiques indémodables et collaborations de luxe. Notre sélection des modèles hype."
    summary = "Quelles sont les sneakers les plus tendance en 2026 ? Découvrez notre sélection des modèles incontournables : running rétro, classiques et collaborations."
    
    if subject:
        title = f"{subject} : Pourquoi c'est LA sneaker tendance de 2026"
        meta_title = f"{subject} : La sneaker tendance 2026 | KP SHOES"[:70]
        meta_description = f"Découvrez pourquoi la {subject} est LA sneaker tendance de 2026. Style, confort et hype : tout ce qu'il faut savoir."[:160]
        summary = f"La {subject} s'impose comme l'une des sneakers les plus tendance de 2026. Découvrez pourquoi elle fait l'unanimité."
    
    body = f"""
<p>Quelles sont les <strong>sneakers les plus tendance en 2026</strong> ? Le marché de la sneaker continue d'évoluer.</p>

{web_info_html}

<h2>Les tendances sneakers 2026</h2>

<h3>1. Le retour du running rétro</h3>
<p>Les silhouettes inspirées des années 90 et 2000 continuent de dominer. Les <strong>Asics Gel-1130</strong>, <strong>New Balance 530</strong> et <strong>Nike Air Max</strong> sont partout dans les rues.</p>

<h3>2. Les classiques indémodables</h3>
<p>La <strong>Nike Dunk Low</strong>, l'<strong>Adidas Samba</strong> et la <strong>New Balance 550</strong> restent des valeurs sûres. Ces modèles polyvalents s'adaptent à tous les styles.</p>

<h3>3. Les collaborations de luxe</h3>
<p>Les partenariats entre marques de sport et maisons de luxe continuent de faire sensation. Les drops limités créent une forte demande sur le marché du resell.</p>

{collection_link}

<h2>Notre sélection KP SHOES</h2>
{product_links}

<h2>Comment adopter la tendance ?</h2>
<ul>
<li><strong>Investissez dans des classiques</strong> : Ils ne se démodent jamais</li>
<li><strong>Osez les couleurs</strong> : Les coloris audacieux sont très recherchés</li>
<li><strong>Privilégiez la qualité</strong> : Une paire authentique dure plus longtemps</li>
</ul>

<p><strong>Chez KP SHOES, retrouvez tous les modèles tendance 100% authentiques.</strong> Notre équipe vérifie chaque paire avant expédition.</p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': 'tendance, sneakers 2026, hype, mode, streetwear',
        'handle': 'sneakers-tendance-2026',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject if subject else 'Nike Dunk Low'
    }


def generate_comparison_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article comparatif"""
    # Parser le sujet pour extraire les 2 modèles
    models = subject.split(' vs ') if ' vs ' in subject else [subject, 'Nike Dunk Low']
    model1 = models[0].strip()
    model2 = models[1].strip() if len(models) > 1 else 'Nike Dunk Low'
    
    title = f"{model1} vs {model2} : Quelle sneaker choisir en 2026 ?"
    meta_title = f"{model1} vs {model2} : Comparatif 2026 | KP SHOES"[:70]
    meta_description = f"Comparatif {model1} vs {model2}. Confort, style, prix : on vous aide à choisir la sneaker faite pour vous."[:160]
    summary = f"Vous hésitez entre {model1} et {model2} ? Notre comparatif détaillé vous aide à faire le bon choix."
    
    body = f"""
<p>Vous hésitez entre la <strong>{model1}</strong> et la <strong>{model2}</strong> ? Ce comparatif détaillé vous aide à faire le bon choix selon vos besoins et votre style.</p>

<h2>Tableau comparatif</h2>
<table style="width:100%;border-collapse:collapse;margin:20px 0">
<tr style="background:#f5f5f5"><th style="padding:12px;border:1px solid #ddd">Critère</th><th style="padding:12px;border:1px solid #ddd">{model1}</th><th style="padding:12px;border:1px solid #ddd">{model2}</th></tr>
<tr><td style="padding:10px;border:1px solid #ddd"><strong>Confort</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd"><strong>Style</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐⭐</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd"><strong>Polyvalence</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐⭐</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd"><strong>Durabilité</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td></tr>
</table>

<h2>{model1} : Points forts et faibles</h2>
<h3>✅ Avantages</h3>
<ul>
<li>Design iconique et reconnaissable</li>
<li>Large choix de coloris</li>
<li>Bonne qualité de fabrication</li>
</ul>
<h3>❌ Inconvénients</h3>
<ul>
<li>Prix parfois élevé sur le marché du resell</li>
<li>Certains coloris difficiles à trouver</li>
</ul>

<h2>{model2} : Points forts et faibles</h2>
<h3>✅ Avantages</h3>
<ul>
<li>Silhouette polyvalente</li>
<li>Confort au quotidien</li>
<li>S'accorde avec de nombreuses tenues</li>
</ul>
<h3>❌ Inconvénients</h3>
<ul>
<li>Très populaire, donc moins original</li>
</ul>

{collection_link}

<h2>Notre verdict</h2>
<p>Les deux modèles sont d'excellents choix. La <strong>{model1}</strong> conviendra aux amateurs de sneakers iconiques, tandis que la <strong>{model2}</strong> sera parfaite pour un usage quotidien polyvalent.</p>

{product_links}

<p><strong>Retrouvez ces deux modèles sur KP SHOES, 100% authentiques et vérifiés.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'comparatif, {model1}, {model2}, versus, guide achat',
        'handle': f'comparatif-{model1.lower().replace(" ", "-")}-vs-{model2.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': model1
    }


def generate_history_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur l'histoire d'un modèle avec infos web"""
    title = f"L'histoire de la {subject} : De sa création à aujourd'hui"
    meta_title = f"Histoire de la {subject} : Origines et évolution | KP SHOES"[:70]
    meta_description = f"Découvrez l'histoire fascinante de la {subject}. De ses origines à son statut d'icône streetwear, retour sur un modèle légendaire."[:160]
    summary = f"La {subject} est bien plus qu'une sneaker. Découvrez son histoire fascinante, de sa création à son statut d'icône culturelle."
    
    # Section produit
    product_section = ""
    if product_links:
        product_section = product_links
    
    body = f"""
<p>Découvrez l'histoire complète de la <strong>{subject}</strong>, une paire qui a marqué l'univers de la sneaker.</p>

{web_info_html}

{collection_link}

{product_section}

<h2>Pourquoi cette paire est-elle si recherchée ?</h2>
<ul>
<li><strong>Un design iconique</strong> : Un modèle qui a su traverser les époques</li>
<li><strong>Une qualité premium</strong> : Des matériaux sélectionnés pour une durabilité optimale</li>
<li><strong>Un héritage culturel</strong> : Une sneaker adoptée par les passionnés du monde entier</li>
</ul>

<p><strong>Retrouvez la {subject} sur KP SHOES. Chaque paire est 100% authentique et vérifiée par nos experts.</strong></p>
"""
    
    # Si pas d'info web, ajouter un message honnête
    if not web_info_html:
        body = f"""
<p>Nous n'avons pas trouvé suffisamment d'informations vérifiées sur la <strong>{subject}</strong> pour rédiger un article d'histoire complet et fiable.</p>

<p>Chez <strong>KP SHOES</strong>, nous préférons ne pas publier d'informations incorrectes. Nous vous invitons à vérifier ce modèle directement sur le site officiel de la marque.</p>

{collection_link}

{product_section}

<p><strong>Retrouvez vos sneakers sur KP SHOES - 100% authentiques et vérifiées par nos experts.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'histoire, {subject}, culture sneaker, légende, heritage',
        'handle': f'histoire-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_care_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur l'entretien"""
    title = f"Comment nettoyer et entretenir ses {subject} ? Guide complet"
    meta_title = f"Comment nettoyer ses {subject} ? Guide entretien | KP SHOES"[:70]
    meta_description = f"Découvrez comment nettoyer et entretenir vos {subject}. Conseils d'experts, erreurs à éviter et astuces pour prolonger leur durée de vie."[:160]
    summary = f"Vos {subject} méritent le meilleur entretien. Découvrez nos conseils d'experts pour les garder impeccables."
    
    body = f"""
<p>Vos <strong>{subject}</strong> méritent un entretien régulier pour rester impeccables.</p>

{web_info_html}

<h2>Le matériel nécessaire</h2>
<ul>
<li>Une brosse à poils doux</li>
<li>Un chiffon microfibre</li>
<li>Du savon de Marseille ou un nettoyant spécial sneakers</li>
<li>De l'eau tiède</li>
<li>Un spray imperméabilisant</li>
</ul>

<h2>Étapes de nettoyage</h2>
<h3>1. Préparation</h3>
<p>Retirez les lacets et les semelles intérieures. Brossez délicatement pour enlever la poussière et les saletés superficielles.</p>

<h3>2. Nettoyage</h3>
<p>Mélangez un peu de savon avec de l'eau tiède. Frottez doucement avec la brosse en faisant des mouvements circulaires. Évitez de tremper complètement vos sneakers.</p>

<h3>3. Rinçage</h3>
<p>Essuyez avec un chiffon humide pour retirer le savon. Répétez si nécessaire.</p>

<h3>4. Séchage</h3>
<p>Laissez sécher à l'air libre, loin des sources de chaleur directe. Bourrez l'intérieur avec du papier journal pour absorber l'humidité et maintenir la forme.</p>

<h2>Conseils selon les matériaux</h2>
<h3>Cuir</h3>
<p>Utilisez un nettoyant spécial cuir et appliquez une crème nourrissante après le nettoyage.</p>

<h3>Suède/Nubuck</h3>
<p>Brossez à sec avec une brosse spéciale suède. Évitez l'eau qui peut tacher le matériau.</p>

<h3>Mesh/Textile</h3>
<p>Ces matériaux supportent mieux l'eau. Vous pouvez les nettoyer plus généreusement.</p>

<h2>Erreurs à éviter</h2>
<ul>
<li>❌ <strong>Ne jamais mettre en machine</strong> : Risque de déformation et décollement</li>
<li>❌ <strong>Éviter le sèche-linge</strong> : La chaleur détériore les colles et matériaux</li>
<li>❌ <strong>Ne pas utiliser de javel</strong> : Elle jaunit et fragilise les matériaux</li>
</ul>

{collection_link}

{product_links}

<h2>Protection et stockage</h2>
<ul>
<li>Appliquez un spray imperméabilisant avant la première utilisation</li>
<li>Rangez vos sneakers dans leurs boîtes d'origine</li>
<li>Utilisez des embauchoirs pour maintenir la forme</li>
<li>Évitez l'humidité et la lumière directe du soleil</li>
</ul>

<p><strong>Chez KP SHOES, toutes nos sneakers sont livrées dans un état impeccable. 100% authentiques et vérifiées.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'entretien, nettoyage, {subject}, sneaker care, guide',
        'handle': f'entretien-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_style_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur le style"""
    title = f"Comment porter la {subject} ? Idées de looks et outfits 2026"
    meta_title = f"Comment porter la {subject} ? Idées looks 2026 | KP SHOES"[:70]
    meta_description = f"Découvrez comment porter la {subject}. Looks casual, streetwear et smart casual : nos idées d'outfits pour tous les styles."[:160]
    summary = f"La {subject} est ultra polyvalente. Découvrez nos idées de looks pour la porter avec style au quotidien."
    
    body = f"""
<p>La <strong>{subject}</strong> est une sneaker polyvalente. Découvrez nos conseils pour créer des looks tendance.</p>

{web_info_html}

<h2>Look casual quotidien</h2>
<p>Pour un style décontracté au quotidien :</p>
<ul>
<li>Jean slim ou regular + t-shirt basique + {subject}</li>
<li>Jogger + hoodie + {subject}</li>
<li>Short cargo + polo + {subject}</li>
</ul>

<h2>Look streetwear</h2>
<p>Pour un style urbain affirmé :</p>
<ul>
<li>Pantalon cargo + sweat oversize + {subject}</li>
<li>Jean baggy + bomber jacket + {subject}</li>
<li>Survêtement vintage + {subject}</li>
</ul>

<h2>Look smart casual</h2>
<p>Oui, on peut porter des sneakers au bureau (selon le dress code) :</p>
<ul>
<li>Chino + chemise + blazer léger + {subject}</li>
<li>Pantalon à pinces + pull col roulé + {subject}</li>
</ul>

{collection_link}

<h2>Les couleurs qui matchent</h2>
<h3>Avec des {subject} blanches</h3>
<p>Tout ! Le blanc est la couleur la plus polyvalente. Jean bleu, pantalon noir, couleurs vives... Tout fonctionne.</p>

<h3>Avec des {subject} noires</h3>
<p>Parfaites pour un look monochrome ou avec des couleurs neutres (gris, beige, blanc).</p>

<h3>Avec des {subject} colorées</h3>
<p>Gardez le reste de la tenue sobre pour laisser les sneakers être le point focal.</p>

{product_links}

<h2>Conseils de style</h2>
<ul>
<li><strong>Équilibrez les proportions</strong> : Sneakers chunky avec pantalon plus ajusté</li>
<li><strong>Jouez avec les textures</strong> : Cuir, denim, coton... Variez les matières</li>
<li><strong>Accessoirisez</strong> : Montre, casquette, sac assorti</li>
</ul>

<p><strong>Retrouvez la {subject} sur KP SHOES. 100% authentique, livraison rapide.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'style, outfit, {subject}, look, mode, streetwear',
        'handle': f'comment-porter-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_custom_article(subject, keywords, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article personnalisé"""
    title = f"{subject} : Tout ce que vous devez savoir en 2026"
    meta_title = f"{subject} : Guide complet 2026 | KP SHOES"[:70]
    meta_description = f"Découvrez tout ce qu'il faut savoir sur {subject}. Guide complet, conseils d'achat et sélection des meilleures paires sur KP SHOES."[:160]
    summary = f"Tout ce qu'il faut savoir sur {subject}. Guide complet et conseils d'achat par les experts KP SHOES."
    
    body = f"""
<p>Découvrez tout ce qu'il faut savoir sur <strong>{subject}</strong>. Chez <strong>KP SHOES</strong>, nous vous proposons les meilleures paires 100% authentiques.</p>

{web_info_html}

<h2>Où acheter {subject} authentique ?</h2>
<p>Pour être sûr d'obtenir une paire authentique, privilégiez les revendeurs de confiance comme <strong>KP SHOES</strong>. Nous vérifions chaque paire avant expédition.</p>

{collection_link}

{product_links}

<h2>Notre engagement qualité</h2>
<ul>
<li>✅ Authenticité garantie à 100%</li>
<li>✅ Vérification par nos experts</li>
<li>✅ Livraison rapide et sécurisée</li>
<li>✅ Service client réactif</li>
</ul>

<p><strong>Faites confiance à KP SHOES pour vos sneakers authentiques.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'{subject}, sneakers, authentique, kp shoes',
        'handle': f'{subject.lower().replace(" ", "-")}-guide-2026',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }




# ══════════════════════════════════════════════════════════════
# RECHERCHE WEB POUR LE BLOG (scraping direct des sites sneakers)
# ══════════════════════════════════════════════════════════════

def fetch_url(url, timeout=10):
    """Fetch une URL avec gestion d'erreurs"""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
        })
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        log.error(f"[Fetch] {url[:60]}: {e}")
        return None


def extract_text_from_html(html, min_length=50, max_paragraphs=15):
    """Extrait les paragraphes de texte utile d'une page HTML"""
    if not html:
        return []
    
    paragraphs = []
    
    # Extraire les <p>
    p_tags = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
    for p in p_tags:
        text = re.sub(r'<[^>]+>', '', p).strip()
        text = re.sub(r'\s+', ' ', text)
        if len(text) >= min_length and len(text) < 2000:
            lower = text.lower()
            skip = False
            # Liste étendue de bruit à filtrer
            junk_list = [
                'cookie', 'privacy policy', 'subscribe', 'newsletter', 'sign up', 
                'log in', 'accept all', 'javascript', 'copyright', 'terms of service',
                'politique de confidentialite', 'kicksfinder is an online database',
                'fashionfootwear', 'artdesignmusic', 'brand ranking', 'brand directory',
                'scan the qr', 'download the app', 'app stores', 'stay ahead of the curve',
                'get the latest', 'follow us', 'all rights reserved', 'terms of use',
                'accuracy may vary', 'some languages may be', 'don\'t show again',
                'turn on code', 'cmd', 'www.kicksfinder.com', 'online database of the most popular',
                'complete list of retailers'
            ]
            for junk in junk_list:
                if junk in lower:
                    skip = True
                    break
            # Aussi filtrer les textes qui ressemblent à des menus de navigation (mots collés sans espaces)
            if not skip and len(text) > 80:
                # Ratio espaces/texte trop bas = menu de navigation
                space_ratio = text.count(' ') / len(text)
                if space_ratio < 0.05:
                    skip = True
            if not skip:
                paragraphs.append(text)
    
    # Aussi extraire les <meta description>
    meta = re.findall(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.DOTALL)
    if not meta:
        meta = re.findall(r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']', html, re.DOTALL)
    for m in meta:
        m_clean = m.strip()
        m_lower = m_clean.lower()
        if len(m_clean) > 40 and 'kicksfinder' not in m_lower and 'online database' not in m_lower:
            paragraphs.insert(0, m_clean)
    
    return paragraphs[:max_paragraphs]


def search_wikipedia(query):
    """Recherche Wikipedia FR puis EN via l'API"""
    for lang in ['fr', 'en']:
        try:
            import urllib.parse
            search_url = f"https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit=3&format=json"
            html = fetch_url(search_url, timeout=8)
            if html:
                data = json.loads(html)
                if data and len(data) >= 4 and data[1]:
                    title = data[1][0]
                    summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
                    summary_html = fetch_url(summary_url, timeout=8)
                    if summary_html:
                        summary_data = json.loads(summary_html)
                        if summary_data.get('extract'):
                            log.info(f"[Wikipedia] Found '{title}' ({lang})")
                            return {
                                'title': summary_data.get('title', ''),
                                'extract': summary_data['extract'],
                                'lang': lang
                            }
        except Exception as e:
            log.error(f"[Wikipedia] Error ({lang}): {e}")
    return None


def search_sneaker_sites(subject):
    """Scrape les sites sneakers : URLs directes + pages de recherche -> articles -> contenu"""
    import urllib.parse
    all_results = []
    slug = subject.lower().replace(' ', '-')
    query_encoded = urllib.parse.quote(subject)
    
    subject_lower = subject.lower()
    generic = ['retro', 'high', 'low', 'mid', 'og', 'sp', 'se', 'premium', 'men', 'women', 'mens', 'womens', 'the', 'a', 'x']
    keywords = [w for w in subject_lower.split() if w not in generic and len(w) > 1]
    
    # ── ÉTAPE 1 : Construire des URLs directes intelligentes ──
    direct_urls = []
    
    # Variantes de slug pour about.nike.com
    # Ex: "Nike Mind 001" -> essayer "nike-mind-001", "nike-mind", "mind-001"
    slug_parts = slug.split('-')
    
    # Slug complet et variantes
    direct_urls.append(f"https://about.nike.com/en/newsroom/releases/{slug}-official-images")
    
    # Slug simplifié (enlever les termes génériques)
    simple_words = [w for w in subject_lower.split() if w not in generic]
    simple_slug = '-'.join(simple_words)
    direct_urls.append(f"https://about.nike.com/en/newsroom/releases/{simple_slug}-official-images")
    
    # Variantes courtes : "nike-mind" pour "Nike Mind 001"
    if len(slug_parts) >= 2:
        # Les 2-3 premiers mots
        for length in [3, 2]:
            short = '-'.join(slug_parts[:length])
            direct_urls.append(f"https://about.nike.com/en/newsroom/releases/{short}-official-images")
    
    # SneakerNews
    direct_urls.append(f"https://sneakernews.com/{slug}-release-date/")
    
    # Dédupliquer les URLs
    direct_urls = list(dict.fromkeys(direct_urls))
    
    for url in direct_urls:
        try:
            html = fetch_url(url, timeout=10)
            if html and len(html) > 5000:
                paragraphs = extract_text_from_html(html, min_length=60)
                # Vérifier pertinence : au moins 1 keyword du sujet
                relevant = [p for p in paragraphs if any(kw in p.lower() for kw in keywords[:5])]
                
                if relevant:
                    log.info(f"[Direct] {url[:60]} -> {len(relevant)} relevant paragraphs")
                    all_results.extend(relevant)
                    if len(all_results) >= 5:
                        break
        except Exception as e:
            log.error(f"[Direct] {url[:60]}: {e}")
    
    # ── ÉTAPE 2 : Pages de recherche -> liens d'articles -> scraper ──
    if len(all_results) < 3:
        search_pages = [
            f"https://sneakernews.com/?s={query_encoded}",
            f"https://hypebeast.com/search?s={query_encoded}",
        ]
        
        for search_url in search_pages:
            try:
                html = fetch_url(search_url, timeout=10)
                if not html:
                    continue
                
                # Trouver les URLs d'articles - chercher avec les mots-clés importants
                article_urls = []
                # D'abord essayer de trouver des liens qui contiennent les keywords
                all_links = re.findall(r'href="(https?://(?:sneakernews\.com|hypebeast\.com)/[^"]{20,})"', html)
                
                for link in all_links:
                    link_lower = link.lower()
                    # Compter combien de keywords sont dans l'URL
                    match_count = sum(1 for kw in keywords if kw in link_lower)
                    if match_count >= 2 and '/search' not in link_lower and '/tag/' not in link_lower and '/author/' not in link_lower:
                        article_urls.append((match_count, link))
                
                # Trier par pertinence
                article_urls.sort(key=lambda x: x[0], reverse=True)
                unique_urls = list(dict.fromkeys([u[1] for u in article_urls]))
                
                # Scraper les 2 premiers articles pertinents
                for article_url in unique_urls[:2]:
                    try:
                        article_html = fetch_url(article_url, timeout=10)
                        if article_html and len(article_html) > 5000:
                            paragraphs = extract_text_from_html(article_html, min_length=60)
                            # Filtrer pour la pertinence
                            relevant = [p for p in paragraphs if any(kw in p.lower() for kw in keywords[:5])]
                            if relevant:
                                log.info(f"[Article] {article_url[:60]} -> {len(relevant)} relevant paragraphs")
                                all_results.extend(relevant)
                    except Exception as e:
                        log.error(f"[Article] {article_url[:60]}: {e}")
                
                if len(all_results) >= 5:
                    break
            except Exception as e:
                log.error(f"[Search] {search_url[:60]}: {e}")
    
    # ── ÉTAPE 3 : JSON-LD et meta depuis nike.com ──
    if len(all_results) < 3:
        try:
            nike_search_url = f"https://www.nike.com/w?q={query_encoded}"
            html = fetch_url(nike_search_url, timeout=10)
            if html:
                json_ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
                for jld in json_ld:
                    try:
                        data = json.loads(jld)
                        desc = data.get('description', '')
                        if desc and len(desc) > 40 and any(kw in desc.lower() for kw in keywords[:3]):
                            all_results.append(desc)
                    except:
                        pass
        except Exception as e:
            log.error(f"[Nike search] {e}")
    
    return all_results


def search_brand_page(subject):
    """Scrape les pages officielles de la marque - cherche dynamiquement les bons articles"""
    import urllib.parse
    s = subject.lower()
    results = []
    keywords = [w for w in s.split() if len(w) > 2 and w not in ['the', 'retro', 'high', 'low', 'mid', 'og', 'sp', 'se']]
    
    slug = subject.lower().replace(' ', '-')
    slug_clean = slug.replace('nike-', '').replace('adidas-', '').replace('new-balance-', '')
    query_encoded = urllib.parse.quote(subject)
    
    if 'nike' in s or 'jordan' in s or 'dunk' in s or 'force' in s or 'air max' in s or 'mind' in s:
        # ── Scraper la page newsroom about.nike.com pour trouver le bon article ──
        try:
            newsroom_url = "https://about.nike.com/en/newsroom/releases"
            html = fetch_url(newsroom_url, timeout=12)
            if html:
                # Chercher les liens qui contiennent les mots-clés du sujet
                all_links = re.findall(r'href="(/en/newsroom/releases/[^"]+)"', html)
                for link in all_links:
                    link_lower = link.lower()
                    match_count = sum(1 for kw in keywords if kw in link_lower)
                    if match_count >= 2:
                        full_url = f"https://about.nike.com{link}"
                        log.info(f"[Brand] Found newsroom article: {full_url}")
                        article_html = fetch_url(full_url, timeout=10)
                        if article_html and len(article_html) > 5000:
                            paragraphs = extract_text_from_html(article_html, min_length=60)
                            relevant = [p for p in paragraphs if any(kw in p.lower() for kw in keywords[:4])]
                            if relevant:
                                results.extend(relevant)
                                log.info(f"[Brand] about.nike.com article -> {len(relevant)} paragraphs")
                        if results:
                            break
        except Exception as e:
            log.error(f"[Brand] newsroom scrape: {e}")
        
        # ── Fallback : URLs directes construites ──
        if not results:
            urls = [
                f"https://about.nike.com/en/newsroom/releases/nike-{slug_clean}-official-images",
                f"https://about.nike.com/en/newsroom/releases/{slug}-official-images",
                f"https://www.nike.com/a/nike-{slug_clean}-release-info",
                f"https://www.nike.com/a/{slug_clean}-release-info",
            ]
            for url in urls[:4]:
                try:
                    html = fetch_url(url, timeout=10)
                    if html and len(html) > 5000:
                        paragraphs = extract_text_from_html(html, min_length=60)
                        relevant = [p for p in paragraphs if any(kw in p.lower() for kw in keywords[:4])]
                        if relevant:
                            results.extend(relevant)
                            break
                except Exception as e:
                    log.error(f"[Brand] {url[:60]}: {e}")
    
    elif 'adidas' in s or 'samba' in s or 'campus' in s or 'gazelle' in s or 'yeezy' in s:
        urls = [f"https://news.adidas.com/search?q={query_encoded}"]
        for url in urls:
            try:
                html = fetch_url(url, timeout=10)
                if html and len(html) > 5000:
                    paragraphs = extract_text_from_html(html, min_length=60)
                    relevant = [p for p in paragraphs if any(kw in p.lower() for kw in keywords[:4])]
                    if relevant:
                        results.extend(relevant)
            except Exception as e:
                log.error(f"[Brand] {url[:60]}: {e}")
    
    return results


def do_web_research(subject, article_type):
    """Fait une recherche web via scraping direct des sites sneakers"""
    info = {
        'wikipedia': None,
        'search_results': [],
        'found': False
    }
    
    log.info(f"[Research] Starting for '{subject}' ({article_type})")
    
    # 1. Wikipedia (marche parfois)
    wiki = search_wikipedia(subject)
    if wiki:
        info['wikipedia'] = wiki
        info['found'] = True
    
    # 2. Scraper les sites sneakers directement
    results = search_sneaker_sites(subject)
    
    # 3. Page officielle de la marque
    brand_results = search_brand_page(subject)
    results.extend(brand_results)
    
    # 4. Dédupliquer et nettoyer
    seen = set()
    clean_results = []
    for r in results:
        key = r[:80].lower()
        if key not in seen and len(r) > 40:
            seen.add(key)
            clean_results.append(r)
    
    if clean_results:
        info['search_results'] = clean_results[:15]
        info['found'] = True
    
    log.info(f"[Research] Done: wiki={'yes' if info['wikipedia'] else 'no'}, results={len(info['search_results'])}, found={info['found']}")
    return info


@app.route('/api/blog/test-search')
def api_blog_test_search():
    """Route de test pour diagnostiquer la recherche web"""
    subject = request.args.get('q', 'Nike Mind 001')
    results = {'subject': subject, 'tests': {}}
    
    # Test 1: Wikipedia
    try:
        wiki = search_wikipedia(subject)
        results['tests']['wikipedia'] = {
            'status': 'OK' if wiki else 'NO RESULTS',
            'data': wiki
        }
    except Exception as e:
        results['tests']['wikipedia'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 2: Sneaker sites scraping
    try:
        sneaker = search_sneaker_sites(subject)
        results['tests']['sneaker_sites'] = {
            'status': 'OK' if sneaker else 'NO RESULTS',
            'count': len(sneaker),
            'data': [s[:200] for s in sneaker[:5]]
        }
    except Exception as e:
        results['tests']['sneaker_sites'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 3: Brand page
    try:
        brand = search_brand_page(subject)
        results['tests']['brand_page'] = {
            'status': 'OK' if brand else 'NO RESULTS',
            'count': len(brand),
            'data': [s[:200] for s in brand[:5]]
        }
    except Exception as e:
        results['tests']['brand_page'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 4: Full research
    try:
        full = do_web_research(subject, 'histoire')
        results['tests']['full_research'] = {
            'status': 'OK' if full.get('found') else 'NO RESULTS',
            'result_count': len(full.get('search_results', [])),
            'data': [s[:200] for s in full.get('search_results', [])[:3]]
        }
    except Exception as e:
        results['tests']['full_research'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 5: Google Translate
    try:
        test_text = "The Nike Mind 001 is a neuroscience-based footwear."
        translated = translate_to_french(test_text)
        results['tests']['google_translate'] = {
            'status': 'OK' if translated != test_text else 'FAILED',
            'original': test_text,
            'translated': translated
        }
    except Exception as e:
        results['tests']['google_translate'] = {'status': 'ERROR', 'error': str(e)}
    
    return jsonify(results)
    
    return jsonify(results)


@app.route('/api/blog/research', methods=['POST'])
def api_blog_research():
    """Endpoint de recherche web pour le blog generator"""
    data = request.json
    subject = data.get('subject', '').strip()
    article_type = data.get('type', 'custom')
    
    if not subject:
        return jsonify({'error': 'Sujet manquant'}), 400
    
    try:
        info = do_web_research(subject, article_type)
        return jsonify(info)
    except Exception as e:
        log.error(f"[Research] Error: {e}")
        return jsonify({'wikipedia': None, 'search_results': [], 'found': False})


@app.route('/api/blog/generate', methods=['POST'])
def api_generate_blog():
    """Génère un article de blog SEO"""
    data = request.json
    
    article_type = data.get('type', 'custom')
    subject = data.get('subject', '').strip()
    keywords = data.get('keywords', '')
    tone = data.get('tone', 'expert')
    length = data.get('length', 'medium')
    
    try:
        # Recherche web sur le sujet
        log.info(f"[Blog] Starting web research for '{subject}' ({article_type})")
        research = do_web_research(subject, article_type)
        log.info(f"[Blog] Research done: found={research.get('found')}")
        
        # Récupérer les produits et collections pour le maillage interne
        products = get_products_for_linking()
        collections = get_collections()
        
        # Générer le contenu avec les données de recherche
        article = generate_article_content(
            article_type, subject, keywords, tone, length,
            products, collections, research
        )
        
        # Récupérer une image depuis GOAT si nécessaire
        if article.get('needs_image') and article.get('image_search_term'):
            search_term = article.get('image_search_term', subject)
            goat_result = get_goat_images(search_term)
            if goat_result and goat_result.get('images'):
                article['image_url'] = goat_result['images'][0]
                log.info(f"[Blog] Got image from GOAT: {article['image_url'][:50]}...")
        
        # Si pas d'image GOAT, chercher dans les produits correspondants
        if not article.get('image_url'):
            matching = find_matching_products(subject, products)
            if matching:
                # Chercher l'image du premier produit
                for p in matching:
                    r = shopify_request(f'products/{p["id"]}.json')
                    if r and r.get('product', {}).get('images'):
                        article['image_url'] = r['product']['images'][0]['src']
                        log.info(f"[Blog] Got image from product: {p['title']}")
                        break
        
        return jsonify(article)
        
    except Exception as e:
        log.error(f"[Blog Generator] Error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
