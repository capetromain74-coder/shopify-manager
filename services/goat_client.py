"""
KP SHOES - Client GOAT (Algolia + web-api + CDN)
Sessions curl_cffi, rotation TLS, fallbacks subprocess.
"""

import json
import re
import time
import logging
import subprocess
from threading import Lock

from config import (
    GOAT_ALGOLIA_URL, GOAT_ALGOLIA_APP_ID, GOAT_ALGOLIA_API_KEY,
    GOAT_PRODUCT_API, GOAT_TLS_PROFILES, GOAT_SESSION_TTL
)

log = logging.getLogger('kpshoes.goat')

_session_lock = Lock()
_goat_session = None
_goat_session_time = 0
_goat_impersonate_idx = 0

def _get_session(force_new=False, rotate_profile=False):
    """Crée/réutilise une session curl_cffi. Renouvelle toutes les 60s ou si force_new."""
    global _goat_session, _goat_session_time, _goat_impersonate_idx
    now = time.time()
    if _goat_session is not None and not force_new and not rotate_profile and (now - _goat_session_time) < 60:
        return _goat_session
    try:
        from curl_cffi.requests import Session
        if _goat_session:
            try: _goat_session.close()
            except Exception: pass
        if rotate_profile:
            _goat_impersonate_idx = (_goat_impersonate_idx + 1) % len(GOAT_TLS_PROFILES)
        profile = GOAT_TLS_PROFILES[_goat_impersonate_idx]
        _goat_session = Session(impersonate=profile)
        _goat_session_time = now
        log.info(f"[GOAT] New curl_cffi session created (profile={profile})")
    except ImportError:
        log.warning("[GOAT] curl_cffi not available, using subprocess curl")
        _goat_session = None
    return _goat_session

def _goat_get(url):
    """GET avec retry : tente plusieurs profils TLS si Cloudflare bloque."""
    for attempt in range(4):
        sess = _get_session(force_new=(attempt > 0), rotate_profile=(attempt > 1))
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
    sess = _get_session()
    if sess:
        try:
            r = sess.post(url, json=json_data, timeout=20)
            if r.status_code == 200: return r.text
            log.warning(f"[GOAT] POST {url[:60]}... -> {r.status_code}")
        except Exception as e:
            log.warning(f"[GOAT] curl_cffi POST failed: {e}")
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

def search(sku, title=None):
    """Recherche un produit GOAT via Algolia. Retourne slug + image principale.
    Si Algolia ne trouve rien et qu'un titre est fourni, tente de deviner le slug."""
    url = f"{GOAT_ALGOLIA_URL}?x-algolia-application-id={GOAT_ALGOLIA_APP_ID}&x-algolia-api-key={GOAT_ALGOLIA_API_KEY}"
    payload = {"requests": [{"indexName": "product_variants_v2", "params": f"distinct=true&maxValuesPerFacet=1&page=0&query={sku}"}]}
    raw = _goat_post(url, payload)
    if not raw: return None
    try: data = json.loads(raw)
    except (json.JSONDecodeError, ValueError): return None
    hits = data.get('results', [{}])[0].get('hits', [])
    if hits:
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
    # Fallback: pas dans Algolia (vetements/apparel) - tenter via slug direct
    if not hits and title:
        log.info(f"[GOAT] Algolia miss for {sku}, trying slug fallback with title: {title[:50]}")
        result = search_by_slug(title, sku)
        if result:
            return result
    return None


def search_by_slug(title, sku=''):
    """Tente de trouver un produit GOAT en construisant un slug à partir du titre.
    Utile pour les vêtements qui ne sont pas dans l'index Algolia."""
    import re as _re
    # Nettoyer le titre: enlever les quotes, parenthèses, caractères spéciaux
    clean = title.strip()
    clean = _re.sub(r"['''\"]", '', clean)
    clean = _re.sub(r'\([^)]*\)', '', clean)  # enlever (FW24) etc
    clean = clean.strip()
    # Slugifier
    slug_base = _re.sub(r'[^a-z0-9]+', '-', clean.lower()).strip('-')
    
    # Essayer plusieurs variantes de slug
    slugs_to_try = [slug_base]
    if sku:
        sku_slug = _re.sub(r'[^a-z0-9]+', '-', sku.lower()).strip('-')
        slugs_to_try.insert(0, f"{slug_base}-{sku_slug}")
    
    for slug in slugs_to_try:
        raw = _goat_get(f"{GOAT_PRODUCT_API}/{slug}")
        if raw:
            try:
                data = json.loads(raw)
                if data.get('name'):
                    log.info(f"[GOAT] Slug fallback found: {slug}")
                    return {
                        'name': data.get('name', ''),
                        'sku': data.get('sku', sku),
                        'slug': slug,
                        'brand': data.get('brandName', ''),
                        'main_picture_url': data.get('mainPictureUrl', '') or data.get('pictureUrl', ''),
                    }
            except (json.JSONDecodeError, ValueError):
                pass
    
    log.info(f"[GOAT] Slug fallback failed for: {title[:50]}")
    return None

def _upgrade_image_quality(url):
    """Convertit une URL d'image GOAT vers la qualité 'original' (normale/max).
    GOAT sert les images galerie en /medium/ (~27Ko). La version /original/ (~160Ko)
    est la meilleure qualité. On bascule simplement le segment du chemin."""
    if not url:
        return url
    if '/medium/' in url:
        return url.replace('/medium/', '/original/')
    if '/grid/' in url:
        return url.replace('/grid/', '/original/')
    return url


def get_product_images(slug):
    """Récupère TOUTES les images d'un produit via web-api. Gère les produits à 1 seule image."""
    raw = _goat_get(f"{GOAT_PRODUCT_API}/{slug}")
    if not raw: return []
    try: data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
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
                # mainPictureUrl est servi en /medium/ : on bascule en /original/ (qualité normale/max)
                url = pic.get('mainPictureUrl', '')
            elif isinstance(pic, str):
                url = pic
            else:
                continue
            url = _upgrade_image_quality(url)
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


def get_product_details(slug):
    """Récupère les détails texte d'un produit GOAT (description, couleurs, matières, story).
    Utilisé pour générer des descriptions produit précises."""
    raw = _goat_get(f"{GOAT_PRODUCT_API}/{slug}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None

    details = {
        'name': data.get('name', ''),
        'color': data.get('color', ''),
        'details': data.get('details', ''),
        'story': data.get('story', '') or data.get('storyHtml', ''),
        'upper_material': data.get('upperMaterial', ''),
        'midsole': data.get('midsole', ''),
        'silhouette': data.get('silhouette', ''),
        'designer': data.get('designer', ''),
        'release_date': data.get('releaseDate', '') or data.get('releaseDateUnix', ''),
        'nickname': data.get('nickname', ''),
        'category': data.get('category', ''),
        # Champs vetements
        'productCategory': data.get('productCategory', ''),
        'productType': data.get('productType', ''),
        'composition': data.get('composition', ''),
        'season': data.get('season', ''),
        'fit': data.get('fit', ''),
        'taxonomyLevel3': data.get('taxonomyLevel3', ''),
        'brandName': data.get('brandName', ''),
    }

    # Nettoyer le HTML du story si présent
    if details['story']:
        details['story'] = re.sub(r'<[^>]+>', '', details['story']).strip()
    if details['details']:
        details['details'] = re.sub(r'<[^>]+>', '', details['details']).strip()

    # Vérifier qu'on a au moins quelque chose d'utile
    has_data = any(details.get(k) for k in ['color', 'details', 'story', 'upper_material', 'composition', 'productCategory'])
    if not has_data:
        log.info(f"[GOAT] No useful text data for {slug}")
        return None

    log.info(f"[GOAT] Got details for {slug}: color={details['color'][:30]}, material={details['upper_material'][:30]}, story={'yes' if details['story'] else 'no'}")
    return details


def discover_image_angles(base_url):
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
        
        if _url_exists(test_url):
            extra_images.append(test_url)
            consecutive_misses = 0
            log.info(f"[GOAT] ✓ Found angle _{i:02d}")
        else:
            consecutive_misses += 1
            if consecutive_misses >= 2 and i > current_angle:
                break  # 2 ratés d'affilée après l'angle courant = on arrête
    
    log.info(f"[GOAT] Discovered {len(extra_images)} additional angles")
    return extra_images


def _url_exists(url):
    """Vérifie si une URL d'image GOAT existe via GET request (HEAD souvent bloqué par CDN)."""
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
    sess = _get_session()
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


def get_images(sku, title=None):
    """Récupère les images GOAT pour un SKU. Gère les SKU multiples (ex: 0951301/0951303).
    Stratégie: Algolia pour trouver le produit + découverte d'angles sur le CDN.
    Pour les vêtements (non trouvés via Algolia), utilise le titre pour deviner le slug.
    """
    try:
        sku = re.sub(r':\d+$', '', sku.strip())
        skus = [s.strip() for s in sku.replace('/', ' ').replace('|', ' ').split() if s.strip()]
        if not skus: skus = [sku]
        
        if len(skus) == 1:
            product = search(skus[0], title=title)
            if not product or not product.get('slug'): return None
            
            # 1. Essayer l'API produit (peut être bloquée par Cloudflare)
            images = get_product_images(product['slug'])
            
            # 2. Si l'API échoue/retourne peu, utiliser l'image Algolia + découverte d'angles
            if len(images) <= 1:
                main_url = images[0] if images else product.get('main_picture_url', '')
                if main_url:
                    if not images:
                        images = [main_url]
                    # Découvrir les angles supplémentaires sur le CDN
                    extra = discover_image_angles(main_url)
                    for url in extra:
                        if url not in images:
                            images.append(url)
                    log.info(f"[GOAT] Total after angle discovery: {len(images)} images")
            
            if not images: return None
            return {'name': product.get('name', ''), 'sku': product.get('sku', sku), 'images': images, 'multi': False}
        
        results = []
        for s in skus:
            try:
                product = search(s)
                if product and product.get('slug'):
                    images = get_product_images(product['slug'])
                    # Même logique de fallback + angle discovery
                    if len(images) <= 1:
                        main_url = images[0] if images else product.get('main_picture_url', '')
                        if main_url:
                            if not images:
                                images = [main_url]
                            extra = discover_image_angles(main_url)
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
