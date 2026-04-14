"""KP SHOES - Routes API GOAT"""
import json, re, time, logging, subprocess
from flask import Blueprint, jsonify, request
from services.shopify import shopify_request
from services.goat_client import search as goat_search, get_product_images as goat_get_product_images, get_images as get_goat_images, _get_session as _get_goat_session, _url_exists as _goat_url_exists, _goat_get, _goat_post
from services.image_manager import _resize_goat_image_to_750x500
from config import GOAT_ALGOLIA_URL, GOAT_ALGOLIA_APP_ID, GOAT_ALGOLIA_API_KEY, GOAT_PRODUCT_API
log = logging.getLogger("kpshoes.goat_routes")
goat_bp = Blueprint("goat", __name__)

@goat_bp.route('/api/goat/test-cdn')
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

@goat_bp.route('/api/goat/debug-algolia')
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

@goat_bp.route('/api/goat/scrape-images')
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

@goat_bp.route('/api/goat/test-resize')
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

@goat_bp.route('/api/goat/debug-api')
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

@goat_bp.route('/api/goat/images')
def api_goat_images():
    """Recherche les images GOAT pour un SKU via l'app 360. Gère les SKU multiples."""
    sku = request.args.get('sku', '').strip()
    title = request.args.get('title', '').strip()
    if not sku:
        return jsonify({'error': 'SKU requis'}), 400
    
    log.info(f"[GOAT] Searching images for SKU: {sku}" + (f" (title: {title[:40]})" if title else ""))
    
    result = get_goat_images(sku, title=title if title else None)
    
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


@goat_bp.route('/api/goat/images-by-slug')
def api_goat_images_by_slug():
    """Recherche les images GOAT directement via un slug (pour vêtements/apparel)."""
    slug = request.args.get('slug', '').strip()
    if not slug:
        return jsonify({'error': 'Slug requis'}), 400
    
    log.info(f"[GOAT] Searching images by slug: {slug}")
    
    images = goat_get_product_images(slug)
    if not images:
        return jsonify({'error': 'Aucune image trouvee pour ce produit'}), 404
    
    # Récupérer aussi le nom
    raw = _goat_get(f"https://www.goat.com/web-api/v1/product_templates/{slug}")
    name = ''
    if raw:
        try:
            import json as _json
            data = _json.loads(raw)
            name = data.get('name', '')
        except:
            pass
    
    return jsonify({
        'name': name,
        'slug': slug,
        'images': images,
    })


@goat_bp.route('/api/goat/apply', methods=['POST'])
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
        # Exception: pas de resize pour les vêtements (le crop rogne mal les images)
        product_title = product.get('title', '').lower()
        clothing_kw = ['hoodie', 'sweatshirt', 'sweater', 'sweatpant', 'sweatshort', 'tee ', 't-shirt',
                       'crewneck', 'jacket', 'pant ', 'pants', 'short ', 'shorts', 'polo', 'jersey', 'vest ']
        is_clothing_product = any(kw in product_title for kw in clothing_kw)
        needs_resize = len(images) == 1 and 'image.goat.com' in images[0] and not is_clothing_product
        log.info(f"[GOAT Apply] {len(images)} images, needs_resize={needs_resize}, is_clothing={is_clothing_product}, first_url={images[0][:80]}...")
        
        # Add new images
        added = 0
        for i, img_url in enumerate(images):
            if needs_resize:
                # Télécharger et redimensionner en 750x500 fond blanc
                b64 = _resize_goat_image_to_750x500(img_url)
                if b64:
                    result = shopify_request(f'products/{product_id}/images.json', 'POST', {
                        'image': {'attachment': b64, 'position': i + 1, 'filename': f'goat_{i+1}.png'}
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
