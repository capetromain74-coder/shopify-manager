"""
Shopify Manager V4 - AI SEO Edition
Génération intelligente de descriptions SEO avec recherche WetTheNew, Limited Resell, StockX
"""

from flask import Flask, jsonify, request, render_template_string
import json
import os
import time
import re
import ssl
import html
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from datetime import datetime
from threading import Thread

app = Flask(__name__)

# Configuration
SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'

# Configuration SEO
SITE_NAME = os.environ.get('SITE_NAME', 'KP SHOES')
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'kpshoes.fr')

# Bénéfices pour les meta descriptions
BENEFITS = ["100% Authentique", "Livraison rapide", "Paiement 3x sans frais"]

# Cache des collections
collections_cache = {
    'data': [],
    'last_update': None
}

# Progress tracking
task_progress = {
    'running': False,
    'current': 0,
    'total': 0,
    'message': '',
    'type': '',
    'success_count': 0,
    'error_count': 0,
    'logs': []
}


# ============================================
# UTILITAIRES API
# ============================================

def shopify_request(endpoint, method='GET', data=None):
    """Requête API Shopify"""
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    
    try:
        if data:
            req = Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method=method)
        else:
            req = Request(url, headers=headers, method=method)
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        with urlopen(req, context=context, timeout=30) as response:
            if method == 'DELETE':
                return True
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as e:
        print(f"[Shopify API Error] {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"[Shopify Error] {e}")
        return None


def web_search(query):
    """Recherche web via DuckDuckGo HTML (pas d'API key requise)"""
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = Request(url, headers=headers)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        with urlopen(req, context=context, timeout=15) as response:
            html_content = response.read().decode('utf-8', errors='ignore')
            return html_content
    except Exception as e:
        print(f"[Search Error] {e}")
        return None


def fetch_url(url):
    """Récupère le contenu d'une URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8'
        }
        req = Request(url, headers=headers)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        with urlopen(req, context=context, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[Fetch Error] {url}: {e}")
        return None


# ============================================
# GESTION DES COLLECTIONS
# ============================================

def get_all_collections():
    """Récupère toutes les collections (custom + smart) depuis Shopify"""
    global collections_cache
    
    # Cache de 10 minutes
    if collections_cache['last_update']:
        age = (datetime.now() - collections_cache['last_update']).seconds
        if age < 600 and collections_cache['data']:
            return collections_cache['data']
    
    all_collections = []
    
    # Custom collections
    result = shopify_request('custom_collections.json?limit=250')
    if result and 'custom_collections' in result:
        for c in result['custom_collections']:
            all_collections.append({
                'id': c['id'],
                'handle': c['handle'],
                'title': c['title']
            })
    
    # Smart collections
    result = shopify_request('smart_collections.json?limit=250')
    if result and 'smart_collections' in result:
        for c in result['smart_collections']:
            all_collections.append({
                'id': c['id'],
                'handle': c['handle'],
                'title': c['title']
            })
    
    collections_cache['data'] = all_collections
    collections_cache['last_update'] = datetime.now()
    
    print(f"[Collections] {len(all_collections)} collections chargées")
    return all_collections


def find_best_collection(product_title, collections):
    """Trouve la meilleure collection pour un produit"""
    title_lower = product_title.lower()
    
    # Dictionnaire de mapping titre -> patterns
    model_patterns = {
        # Jordan
        'jordan-4': ['jordan 4', 'jordan4', 'aj4', 'air jordan 4'],
        'jordan-1-low': ['jordan 1 low', 'aj1 low'],
        'jordan-1-mid': ['jordan 1 mid', 'aj1 mid'],
        'jordan-1-high': ['jordan 1 high', 'aj1 high', 'jordan 1 retro high'],
        'jordan-1': ['jordan 1', 'aj1', 'air jordan 1'],
        'jordan-3': ['jordan 3', 'aj3', 'air jordan 3'],
        'jordan-5': ['jordan 5', 'aj5', 'air jordan 5'],
        'jordan-6': ['jordan 6', 'aj6', 'air jordan 6'],
        'jordan-11': ['jordan 11', 'aj11', 'air jordan 11'],
        
        # Nike
        'nike-dunk-low': ['dunk low'],
        'nike-dunk-high': ['dunk high'],
        'nike-dunk': ['dunk'],
        'air-force-1': ['air force 1', 'af1', 'force 1'],
        'nike-p-6000': ['air max', 'airmax'],
        
        # Adidas
        'adidas-samba': ['samba'],
        'adidas-campus': ['campus'],
        'adidas-gazelle': ['gazelle'],
        'adidas-spezial': ['spezial', 'handball spezial'],
        'adidas-forum': ['forum'],
        
        # New Balance
        'new-balance-550': ['new balance 550', 'nb 550', 'nb550'],
        'new-balance-530': ['new balance 530', 'nb 530'],
        'new-balance-2002r': ['new balance 2002', 'nb 2002'],
        'new-balance-990': ['new balance 990', 'nb 990'],
        
        # Asics
        'asics-gel-1130': ['gel-1130', 'gel 1130'],
        'asics-gel-kayano': ['gel-kayano', 'gel kayano', 'kayano'],
        'asics-gel-nyc': ['gel-nyc', 'gel nyc'],
        
        # Yeezy
        'yeezy-350': ['yeezy 350', 'yeezy boost 350'],
        'yeezy-500': ['yeezy 500'],
        'yeezy-700': ['yeezy 700'],
        'yeezy-slide': ['yeezy slide'],
        'yeezy-foam': ['yeezy foam', 'foam runner', 'foam rnnr'],
    }
    
    # Mapping marques
    brand_patterns = {
        'jordan-1': ['jordan', 'air jordan'],
        'adidas-1': ['adidas', 'yeezy'],
        'asics-1': ['asics', 'onitsuka'],
        'nike': ['nike'],
        'new-balance': ['new balance', 'nb'],
        'puma': ['puma'],
        'birkenstock-1': ['birkenstock'],
        'ugg': ['ugg'],
    }
    
    # Créer un set des handles disponibles
    available_handles = {c['handle'] for c in collections}
    
    # 1. Chercher d'abord un modèle précis
    for handle, patterns in model_patterns.items():
        if handle in available_handles:
            for pattern in patterns:
                if pattern in title_lower:
                    # Trouver le titre de la collection
                    for c in collections:
                        if c['handle'] == handle:
                            return {'handle': handle, 'title': c['title']}
    
    # 2. Sinon chercher la marque
    for handle, patterns in brand_patterns.items():
        if handle in available_handles:
            for pattern in patterns:
                if pattern in title_lower:
                    for c in collections:
                        if c['handle'] == handle:
                            return {'handle': handle, 'title': c['title']}
    
    # 3. Fallback: collection générale
    if 'tout-nos-modeles' in available_handles:
        return {'handle': 'tout-nos-modeles', 'title': 'Tous nos modèles'}
    
    return None


# ============================================
# EXTRACTION D'INFORMATIONS PRODUIT
# ============================================

def extract_sku(product):
    """Extrait le SKU"""
    if product.get('variants') and len(product['variants']) > 0:
        return product['variants'][0].get('sku', '')
    return ''


def extract_brand(product):
    """Extrait la marque"""
    title = product.get('title', '')
    brands = ['Adidas', 'Nike', 'Air Jordan', 'Jordan', 'New Balance', 'Puma', 
              'Asics', 'Converse', 'Vans', 'Reebok', 'UGG', 'Yeezy', 'Salomon',
              'On Running', 'Hoka', 'Crocs', 'Birkenstock', 'Timberland']
    
    for brand in brands:
        if brand.lower() in title.lower():
            return brand
    return product.get('vendor', '')


def extract_colorway(product):
    """Extrait le colorway du titre"""
    title = product.get('title', '')
    match = re.search(r'\(([^)]+)\)', title)
    if match:
        return match.group(1)
    return ''


def strip_html(text):
    """Supprime les balises HTML"""
    if not text:
        return ''
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


# ============================================
# RECHERCHE D'INFORMATIONS EXTERNES (IA)
# ============================================

def search_product_info(product_title, sku):
    """Recherche des informations sur WetTheNew, Limited Resell, StockX"""
    info = {
        'release_date': None,
        'colorway_code': None,
        'description': None,
        'retail_price': None,
        'source': None
    }
    
    search_query = sku if sku else product_title
    
    # Recherche sur les différentes sources
    sources = [
        ('wethenew.com', f'site:wethenew.com {search_query}'),
        ('limitedresell.com', f'site:limitedresell.com {search_query}'),
        ('stockx.com', f'site:stockx.com {search_query}')
    ]
    
    for source_name, query in sources:
        try:
            html_content = web_search(query)
            if html_content and source_name in html_content.lower():
                info['source'] = source_name
                
                # Extraire la date de sortie
                date_patterns = [
                    r'date de sortie[:\s]*([a-zéû]+ \d{4})',
                    r'release date[:\s]*([a-z]+ \d{4})',
                    r'sortie[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        info['release_date'] = match.group(1)
                        break
                
                # Extraire le colorway
                colorway_patterns = [
                    r'colorway[:\s]*([A-Z][A-Z\-\/\s]+)',
                    r'coloris[:\s]*([A-Z][A-Z\-\/\s]+)',
                ]
                for pattern in colorway_patterns:
                    match = re.search(pattern, html_content)
                    if match:
                        info['colorway_code'] = match.group(1).strip()[:50]
                        break
                
                if info['release_date'] or info['colorway_code']:
                    break
                    
        except Exception as e:
            print(f"[Search Error] {source_name}: {e}")
            continue
    
    return info


# ============================================
# GÉNÉRATION SEO
# ============================================

def generate_meta_title(product):
    """Génère le Meta Title optimisé"""
    title = product.get('title', '')
    meta_title = f"{title} | {SITE_NAME}"
    
    if len(meta_title) > 60:
        max_len = 60 - len(f" | {SITE_NAME}") - 3
        meta_title = f"{title[:max_len]}... | {SITE_NAME}"
    
    return meta_title


def generate_meta_description(product):
    """Génère la Meta Description optimisée"""
    title = product.get('title', '')
    sku = extract_sku(product)
    
    if sku:
        base = f"Achetez la {title} (SKU: {sku}) sur {SITE_NAME}"
    else:
        base = f"Achetez la {title} sur {SITE_NAME}"
    
    benefits_str = " ✓ ".join(BENEFITS)
    meta_desc = f"{base} ✓ {benefits_str}."
    
    if len(meta_desc) > 155:
        meta_desc = f"Achetez la {title} ✓ {BENEFITS[0]} ✓ {BENEFITS[1]} - {SITE_NAME}"
        if len(meta_desc) > 155:
            meta_desc = meta_desc[:152] + "..."
    
    return meta_desc


def generate_description_with_links(product, collections, external_info=None):
    """
    Génère une description produit optimisée SEO avec liens internes
    Style inspiré de WetTheNew et Limited Resell
    """
    title = product.get('title', '')
    brand = extract_brand(product)
    sku = extract_sku(product)
    colorway = extract_colorway(product)
    current_desc = strip_html(product.get('body_html', ''))
    
    # Trouver la meilleure collection
    collection = find_best_collection(title, collections)
    
    # Construire la description
    lines = []
    
    # Paragraphe 1: Introduction avec lien collection
    if collection:
        collection_link = f'<a href="https://{SITE_DOMAIN}/collections/{collection["handle"]}">{collection["title"]}</a>'
        intro = f'<p>Découvrez la <strong>{title}</strong>, une pièce incontournable de notre collection {collection_link}.</p>'
    else:
        intro = f'<p>Découvrez la <strong>{title}</strong>, une sneaker iconique signée {brand}.</p>'
    lines.append(intro)
    
    # Paragraphe 2: Description du produit
    if current_desc and len(current_desc) > 30:
        # Nettoyer et utiliser la description existante
        desc_clean = current_desc[:500] if len(current_desc) > 500 else current_desc
        lines.append(f'<p>{desc_clean}</p>')
    else:
        # Description générique basée sur la marque
        generic_desc = f"Cette {brand} se distingue par son design unique et ses finitions de qualité."
        if colorway:
            generic_desc += f" Le coloris {colorway} apporte une touche distinctive à ce modèle."
        lines.append(f'<p>{generic_desc}</p>')
    
    # Paragraphe 3: Données techniques
    tech_lines = []
    if sku:
        tech_lines.append(f'<strong>SKU</strong> : {sku}')
    if colorway:
        tech_lines.append(f'<strong>Colorway</strong> : {colorway}')
    if external_info and external_info.get('colorway_code'):
        tech_lines.append(f'<strong>Code couleur</strong> : {external_info["colorway_code"]}')
    if external_info and external_info.get('release_date'):
        tech_lines.append(f'<strong>Date de sortie</strong> : {external_info["release_date"]}')
    tech_lines.append(f'<strong>Marque</strong> : {brand}')
    
    if tech_lines:
        lines.append('<p>' + '<br>'.join(tech_lines) + '</p>')
    
    # Paragraphe 4: Authenticité et avantages
    lines.append(f'''<p>Chez <strong>{SITE_NAME}</strong>, toutes nos sneakers sont <strong>100% authentiques</strong> 
et vérifiées par nos experts. Livraison rapide en France métropolitaine et paiement en 3x sans frais disponible.</p>''')
    
    return '\n'.join(lines)


def calculate_seo_score(product):
    """Calcule un score SEO pour le produit"""
    score = 0
    details = []
    
    # Meta title (via metafields - on vérifie si le titre est formaté)
    title = product.get('title', '')
    if title and len(title) > 10:
        score += 25
        details.append('✅ Titre présent')
    else:
        details.append('❌ Titre manquant')
    
    # SKU
    sku = extract_sku(product)
    if sku:
        score += 25
        details.append('✅ SKU présent')
    else:
        details.append('❌ SKU manquant')
    
    # Description
    body = product.get('body_html', '')
    if body and len(strip_html(body)) > 100:
        score += 25
        details.append('✅ Description présente')
        # Bonus si contient un lien
        if '<a href=' in body.lower():
            score += 15
            details.append('✅ Liens internes')
        else:
            details.append('⚠️ Pas de liens internes')
    else:
        details.append('❌ Description manquante/courte')
    
    # Handle optimisé
    handle = product.get('handle', '')
    if handle and len(handle) > 5 and '-' in handle:
        score += 10
        details.append('✅ URL optimisée')
    else:
        details.append('⚠️ URL à optimiser')
    
    return min(score, 100), details


# ============================================
# ROUTES API PRODUITS
# ============================================

def get_all_products():
    """Récupère tous les produits"""
    all_products = []
    since_id = 0
    
    while True:
        endpoint = f'products.json?limit=250&since_id={since_id}'
        result = shopify_request(endpoint)
        
        if result and 'products' in result and len(result['products']) > 0:
            products = result['products']
            all_products.extend(products)
            since_id = products[-1]['id']
            
            if len(products) < 250:
                break
            time.sleep(0.5)
        else:
            break
    
    return all_products


def update_product_seo(product_id, seo_data):
    """Met à jour les données SEO d'un produit"""
    success = True
    
    # Mise à jour du produit (handle, body_html)
    product_update = {'product': {'id': product_id}}
    
    if 'handle' in seo_data:
        product_update['product']['handle'] = seo_data['handle']
    if 'body_html' in seo_data:
        product_update['product']['body_html'] = seo_data['body_html']
    
    if len(product_update['product']) > 1:
        result = shopify_request(f'products/{product_id}.json', 'PUT', product_update)
        if not result:
            success = False
        time.sleep(0.4)
    
    # Meta Title
    if 'meta_title' in seo_data:
        result = shopify_request(f'products/{product_id}/metafields.json', 'POST', {
            'metafield': {
                'namespace': 'global',
                'key': 'title_tag',
                'value': seo_data['meta_title'],
                'type': 'single_line_text_field'
            }
        })
        time.sleep(0.3)
    
    # Meta Description
    if 'meta_description' in seo_data:
        result = shopify_request(f'products/{product_id}/metafields.json', 'POST', {
            'metafield': {
                'namespace': 'global',
                'key': 'description_tag',
                'value': seo_data['meta_description'],
                'type': 'single_line_text_field'
            }
        })
        time.sleep(0.3)
    
    return success


# ============================================
# ROUTES API
# ============================================

@app.route('/')
def home():
    return HOME_HTML


@app.route('/seo')
def seo_page():
    return SEO_HTML


@app.route('/api/collections')
def api_collections():
    """Liste toutes les collections"""
    collections = get_all_collections()
    return jsonify({'collections': collections, 'count': len(collections)})


@app.route('/api/products')
def api_products():
    """Liste tous les produits avec score SEO"""
    products = get_all_products()
    collections = get_all_collections()
    
    # Ajouter le score SEO à chaque produit
    for p in products:
        score, details = calculate_seo_score(p)
        p['seo_score'] = score
        p['seo_details'] = details
        
        # Trouver la collection associée
        collection = find_best_collection(p.get('title', ''), collections)
        p['matched_collection'] = collection
    
    # Stats globales
    total = len(products)
    seo_complete = len([p for p in products if p['seo_score'] >= 75])
    seo_partial = len([p for p in products if 25 <= p['seo_score'] < 75])
    seo_missing = len([p for p in products if p['seo_score'] < 25])
    
    return jsonify({
        'products': products,
        'stats': {
            'total': total,
            'seo_complete': seo_complete,
            'seo_partial': seo_partial,
            'seo_missing': seo_missing,
            'percentage_complete': round(seo_complete / total * 100, 1) if total > 0 else 0
        }
    })


@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)


@app.route('/api/seo/preview/<int:product_id>')
def api_seo_preview(product_id):
    """Prévisualise le SEO généré pour un produit"""
    result = shopify_request(f'products/{product_id}.json')
    if not result or 'product' not in result:
        return jsonify({'error': 'Produit non trouvé'}), 404
    
    product = result['product']
    collections = get_all_collections()
    
    # Rechercher des infos externes
    sku = extract_sku(product)
    external_info = search_product_info(product.get('title', ''), sku)
    
    # Générer le SEO
    generated = {
        'meta_title': generate_meta_title(product),
        'meta_description': generate_meta_description(product),
        'body_html': generate_description_with_links(product, collections, external_info)
    }
    
    collection = find_best_collection(product.get('title', ''), collections)
    
    return jsonify({
        'product': product,
        'generated': generated,
        'matched_collection': collection,
        'external_info': external_info
    })


@app.route('/api/seo/generate-single', methods=['POST'])
def api_generate_single():
    """Génère et applique le SEO pour un seul produit"""
    data = request.json
    product_id = data.get('product_id')
    use_ai = data.get('use_ai', True)
    
    result = shopify_request(f'products/{product_id}.json')
    if not result or 'product' not in result:
        return jsonify({'error': 'Produit non trouvé'}), 404
    
    product = result['product']
    collections = get_all_collections()
    
    # Rechercher infos externes si IA activée
    external_info = None
    if use_ai:
        sku = extract_sku(product)
        external_info = search_product_info(product.get('title', ''), sku)
    
    # Générer le SEO
    seo_data = {
        'meta_title': generate_meta_title(product),
        'meta_description': generate_meta_description(product),
        'body_html': generate_description_with_links(product, collections, external_info)
    }
    
    # Appliquer
    success = update_product_seo(product_id, seo_data)
    
    return jsonify({
        'success': success,
        'applied': seo_data,
        'external_info': external_info
    })


@app.route('/api/seo/generate-batch', methods=['POST'])
def api_generate_batch():
    """Génère le SEO pour plusieurs produits"""
    global task_progress
    
    data = request.json
    product_ids = data.get('product_ids', [])
    use_ai = data.get('use_ai', False)  # Désactivé par défaut pour batch (trop lent)
    
    if not product_ids:
        return jsonify({'error': 'Aucun produit sélectionné'}), 400
    
    def process_batch():
        global task_progress
        task_progress = {
            'running': True,
            'current': 0,
            'total': len(product_ids),
            'message': 'Chargement des collections...',
            'type': 'seo_batch',
            'success_count': 0,
            'error_count': 0,
            'logs': []
        }
        
        collections = get_all_collections()
        
        for i, pid in enumerate(product_ids):
            task_progress['current'] = i + 1
            
            # Récupérer le produit
            result = shopify_request(f'products/{pid}.json')
            if result and 'product' in result:
                product = result['product']
                product_title = product.get('title', 'Inconnu')[:40]
                
                task_progress['message'] = f'#{i+1} {product_title}...'
                
                # Recherche externe si IA activée
                external_info = None
                if use_ai:
                    sku = extract_sku(product)
                    external_info = search_product_info(product.get('title', ''), sku)
                    time.sleep(0.5)  # Rate limit recherche
                
                # Générer le SEO
                seo_data = {
                    'meta_title': generate_meta_title(product),
                    'meta_description': generate_meta_description(product),
                    'body_html': generate_description_with_links(product, collections, external_info)
                }
                
                # Appliquer
                success = update_product_seo(pid, seo_data)
                
                if success:
                    task_progress['success_count'] += 1
                    task_progress['logs'].append(f'✅ {product_title}')
                else:
                    task_progress['error_count'] += 1
                    task_progress['logs'].append(f'❌ {product_title}')
            else:
                task_progress['error_count'] += 1
            
            # Rate limit Shopify
            time.sleep(1.0)
        
        task_progress['running'] = False
        task_progress['message'] = f'Terminé ! {task_progress["success_count"]} réussis, {task_progress["error_count"]} erreurs'
    
    thread = Thread(target=process_batch)
    thread.start()
    
    return jsonify({'status': 'started', 'total': len(product_ids)})


# ============================================
# TEMPLATES HTML
# ============================================

HOME_HTML = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shopify Manager V4 - AI SEO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
        }
        .container { text-align: center; padding: 40px; }
        .logo { font-size: 70px; margin-bottom: 20px; animation: float 3s ease-in-out infinite; }
        @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        h1 { font-size: 48px; margin-bottom: 10px; background: linear-gradient(135deg, #00ff88, #00cc6a); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .version { display: inline-block; background: linear-gradient(135deg, #ff6b6b, #ee5a24); padding: 6px 16px; border-radius: 20px; font-size: 14px; margin-bottom: 20px; font-weight: bold; }
        .subtitle { color: #888; font-size: 18px; margin-bottom: 50px; }
        .features { display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; margin-bottom: 40px; }
        .feature { background: rgba(255,255,255,0.05); padding: 8px 16px; border-radius: 20px; font-size: 13px; color: #aaa; }
        .btn-main { display: inline-block; padding: 20px 60px; background: linear-gradient(135deg, #00ff88, #00cc6a); color: #000; text-decoration: none; border-radius: 12px; font-size: 18px; font-weight: bold; transition: all 0.3s; }
        .btn-main:hover { transform: translateY(-3px); box-shadow: 0 10px 30px rgba(0,255,136,0.3); }
        .stats { margin-top: 50px; display: flex; gap: 30px; justify-content: center; }
        .stat { text-align: center; }
        .stat-value { font-size: 32px; font-weight: bold; color: #00ff88; }
        .stat-label { font-size: 12px; color: #666; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🤖</div>
        <h1>Shopify Manager</h1>
        <div class="version">V4 - AI SEO Edition</div>
        <p class="subtitle">Génération intelligente de descriptions SEO avec IA</p>
        
        <div class="features">
            <div class="feature">🔗 Liens internes auto</div>
            <div class="feature">🔍 Recherche WetTheNew</div>
            <div class="feature">📊 Score SEO</div>
            <div class="feature">⚡ Batch processing</div>
        </div>
        
        <a href="/seo" class="btn-main">🚀 Lancer l'optimisation SEO</a>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value" id="total-products">-</div>
                <div class="stat-label">Produits</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="total-collections">-</div>
                <div class="stat-label">Collections</div>
            </div>
        </div>
    </div>
    
    <script>
        fetch('/api/collections').then(r => r.json()).then(d => {
            document.getElementById('total-collections').textContent = d.count;
        });
        fetch('/api/products').then(r => r.json()).then(d => {
            document.getElementById('total-products').textContent = d.stats.total;
        });
    </script>
</body>
</html>
'''

SEO_HTML = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 SEO AI | Shopify Manager V4</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0f; min-height: 100vh; color: #fff; }
        
        .header { padding: 20px 30px; background: rgba(0,0,0,0.5); border-bottom: 1px solid #222; display: flex; justify-content: space-between; align-items: center; }
        .header-left { display: flex; align-items: center; gap: 20px; }
        .back-btn { padding: 10px 20px; background: #222; border: none; border-radius: 8px; color: #fff; text-decoration: none; }
        .logo { font-size: 20px; font-weight: bold; }
        .logo span { color: #00ff88; }
        
        .stats-bar { display: flex; gap: 20px; padding: 20px 30px; background: linear-gradient(90deg, rgba(0,255,136,0.1), rgba(139,92,246,0.1)); border-bottom: 1px solid #222; flex-wrap: wrap; }
        .stat-box { background: rgba(0,0,0,0.3); padding: 15px 25px; border-radius: 10px; text-align: center; min-width: 120px; }
        .stat-box.highlight { border: 1px solid #00ff88; }
        .stat-value { font-size: 28px; font-weight: bold; }
        .stat-value.green { color: #00ff88; }
        .stat-value.orange { color: #ffa502; }
        .stat-value.red { color: #ff4757; }
        .stat-label { font-size: 11px; color: #666; margin-top: 5px; text-transform: uppercase; }
        
        .container { max-width: 1600px; margin: 0 auto; padding: 20px 30px; }
        
        .controls { display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; align-items: flex-end; }
        .control-group { display: flex; flex-direction: column; gap: 6px; }
        .control-group label { font-size: 11px; color: #666; text-transform: uppercase; }
        .control-group input, .control-group select { padding: 12px 16px; background: #1a1a2e; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 14px; min-width: 200px; }
        
        .btn { padding: 12px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; }
        .btn-primary { background: linear-gradient(135deg, #00ff88, #00cc6a); color: #000; }
        .btn-ai { background: linear-gradient(135deg, #ff6b6b, #ee5a24); color: #fff; }
        .btn-secondary { background: #333; color: #fff; }
        .btn:hover { opacity: 0.9; transform: translateY(-1px); }
        
        .products-grid { display: grid; gap: 15px; }
        .product-card { background: #1a1a2e; border: 1px solid #2a2a3a; border-radius: 12px; padding: 20px; display: grid; grid-template-columns: auto 1fr 1fr auto; gap: 20px; align-items: center; }
        .product-card:hover { border-color: #444; }
        
        .product-check { width: 24px; height: 24px; border: 2px solid #444; border-radius: 6px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .product-check.checked { background: #00ff88; border-color: #00ff88; }
        .product-check.checked::after { content: '✓'; color: #000; font-weight: bold; }
        
        .product-info { display: flex; gap: 15px; align-items: center; }
        .product-image { width: 60px; height: 60px; border-radius: 8px; object-fit: cover; background: #333; }
        .product-title { font-weight: 500; font-size: 14px; margin-bottom: 4px; }
        .product-sku { font-size: 11px; color: #666; font-family: monospace; }
        .product-collection { font-size: 11px; color: #8b5cf6; margin-top: 4px; }
        
        .product-seo { font-size: 12px; }
        .seo-preview { background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; margin-bottom: 8px; }
        .seo-preview-title { color: #00ff88; font-weight: 500; margin-bottom: 4px; }
        .seo-preview-desc { color: #888; font-size: 11px; }
        
        .product-score { text-align: center; min-width: 80px; }
        .score-circle { width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px; margin: 0 auto 5px; }
        .score-circle.high { background: rgba(0,255,136,0.2); color: #00ff88; border: 2px solid #00ff88; }
        .score-circle.medium { background: rgba(255,165,2,0.2); color: #ffa502; border: 2px solid #ffa502; }
        .score-circle.low { background: rgba(255,71,87,0.2); color: #ff4757; border: 2px solid #ff4757; }
        .score-label { font-size: 10px; color: #666; }
        
        .product-actions { display: flex; flex-direction: column; gap: 8px; }
        .action-btn { padding: 8px 16px; font-size: 12px; border: none; border-radius: 6px; cursor: pointer; }
        .action-btn.preview { background: #333; color: #fff; }
        .action-btn.apply { background: #00ff88; color: #000; }
        .action-btn.ai { background: linear-gradient(135deg, #ff6b6b, #ee5a24); color: #fff; }
        
        .progress-bar { position: fixed; top: 0; left: 0; right: 0; background: #1a1a2e; padding: 25px 40px; z-index: 1000; border-bottom: 2px solid #00ff88; display: none; }
        .progress-bar.show { display: block; }
        .progress-header { display: flex; justify-content: space-between; margin-bottom: 15px; }
        .progress-track { height: 12px; background: #333; border-radius: 6px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #00ff88, #8b5cf6); transition: width 0.3s; }
        .progress-text { margin-top: 12px; color: #888; font-size: 14px; }
        
        .modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.9); display: none; align-items: center; justify-content: center; z-index: 2000; }
        .modal.show { display: flex; }
        .modal-content { background: #1a1a2e; padding: 30px; border-radius: 16px; max-width: 800px; width: 90%; max-height: 90vh; overflow-y: auto; }
        .modal h2 { margin-bottom: 20px; }
        .modal-preview { background: #0a0a0f; padding: 20px; border-radius: 10px; margin: 15px 0; }
        .modal-preview h4 { color: #00ff88; margin-bottom: 10px; font-size: 14px; }
        .modal-preview pre { white-space: pre-wrap; font-size: 12px; color: #aaa; }
        .modal-actions { display: flex; gap: 15px; margin-top: 25px; }
        .modal-actions .btn { flex: 1; justify-content: center; }
        
        .loading { text-align: center; padding: 60px; }
        .spinner { width: 50px; height: 50px; border: 4px solid #333; border-top-color: #00ff88; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .toast { position: fixed; bottom: 24px; right: 24px; padding: 16px 24px; border-radius: 10px; z-index: 3000; animation: slideIn 0.3s; }
        .toast.success { background: #00ff88; color: #000; }
        .toast.error { background: #ff4757; color: #fff; }
        @keyframes slideIn { from { transform: translateX(100px); opacity: 0; } }
        
        .empty-state { text-align: center; padding: 60px; color: #666; }
    </style>
</head>
<body>
    <div class="progress-bar" id="progress-bar">
        <div class="progress-header">
            <h3>🤖 Génération SEO en cours...</h3>
            <span id="progress-count">0 / 0</span>
        </div>
        <div class="progress-track">
            <div class="progress-fill" id="progress-fill"></div>
        </div>
        <p class="progress-text" id="progress-text">Initialisation...</p>
    </div>

    <header class="header">
        <div class="header-left">
            <a href="/" class="back-btn">← Accueil</a>
            <div class="logo">🤖 SEO <span>AI</span></div>
        </div>
    </header>
    
    <div class="stats-bar">
        <div class="stat-box highlight">
            <div class="stat-value green" id="stat-complete">-</div>
            <div class="stat-label">SEO Complet (75%+)</div>
        </div>
        <div class="stat-box">
            <div class="stat-value orange" id="stat-partial">-</div>
            <div class="stat-label">SEO Partiel</div>
        </div>
        <div class="stat-box">
            <div class="stat-value red" id="stat-missing">-</div>
            <div class="stat-label">SEO Manquant</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" id="stat-total">-</div>
            <div class="stat-label">Total Produits</div>
        </div>
        <div class="stat-box">
            <div class="stat-value green" id="stat-percent">-%</div>
            <div class="stat-label">Taux d'optimisation</div>
        </div>
    </div>
    
    <main class="container">
        <div class="controls">
            <div class="control-group">
                <label>Rechercher</label>
                <input type="text" id="search" placeholder="Nom, SKU...">
            </div>
            <div class="control-group">
                <label>Filtrer par score</label>
                <select id="filter-score">
                    <option value="all">Tous</option>
                    <option value="low">❌ SEO manquant (&lt;25%)</option>
                    <option value="medium">⚠️ SEO partiel (25-74%)</option>
                    <option value="high">✅ SEO complet (75%+)</option>
                </select>
            </div>
            <button class="btn btn-secondary" onclick="loadProducts()">🔄 Actualiser</button>
            <button class="btn btn-primary" onclick="generateSelected()">⚡ Générer sélection</button>
            <button class="btn btn-ai" onclick="generateAll()">🚀 Générer TOUT (IA)</button>
            <div style="margin-left:auto; color:#666; font-size:13px;">
                <strong id="selected-count">0</strong> sélectionné(s)
            </div>
        </div>
        
        <div class="products-grid" id="products-grid">
            <div class="loading">
                <div class="spinner"></div>
                <p>Chargement des produits...</p>
            </div>
        </div>
    </main>
    
    <div class="modal" id="preview-modal">
        <div class="modal-content">
            <h2>🔍 Prévisualisation SEO</h2>
            <div id="preview-content"></div>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeModal()">Fermer</button>
                <button class="btn btn-primary" onclick="applyPreview()">✅ Appliquer ce SEO</button>
            </div>
        </div>
    </div>

    <script>
        let products = [];
        let selectedIds = new Set();
        let currentPreviewId = null;
        
        async function loadProducts() {
            document.getElementById('products-grid').innerHTML = '<div class="loading"><div class="spinner"></div><p>Chargement...</p></div>';
            
            try {
                const response = await fetch('/api/products');
                const data = await response.json();
                products = data.products || [];
                
                // Mettre à jour les stats
                document.getElementById('stat-complete').textContent = data.stats.seo_complete;
                document.getElementById('stat-partial').textContent = data.stats.seo_partial;
                document.getElementById('stat-missing').textContent = data.stats.seo_missing;
                document.getElementById('stat-total').textContent = data.stats.total;
                document.getElementById('stat-percent').textContent = data.stats.percentage_complete + '%';
                
                filterProducts();
            } catch (error) {
                document.getElementById('products-grid').innerHTML = '<div class="empty-state">Erreur de chargement</div>';
            }
        }
        
        function filterProducts() {
            const search = document.getElementById('search').value.toLowerCase();
            const scoreFilter = document.getElementById('filter-score').value;
            
            let filtered = products.filter(p => {
                const matchSearch = !search || 
                    p.title.toLowerCase().includes(search) ||
                    (p.variants?.[0]?.sku || '').toLowerCase().includes(search);
                
                let matchScore = true;
                if (scoreFilter === 'low') matchScore = p.seo_score < 25;
                else if (scoreFilter === 'medium') matchScore = p.seo_score >= 25 && p.seo_score < 75;
                else if (scoreFilter === 'high') matchScore = p.seo_score >= 75;
                
                return matchSearch && matchScore;
            });
            
            renderProducts(filtered);
        }
        
        function renderProducts(list) {
            const grid = document.getElementById('products-grid');
            
            if (list.length === 0) {
                grid.innerHTML = '<div class="empty-state">Aucun produit trouvé</div>';
                return;
            }
            
            grid.innerHTML = list.map(p => {
                const isSelected = selectedIds.has(p.id);
                const sku = p.variants?.[0]?.sku || 'N/A';
                const imageUrl = p.image?.src || '';
                const score = p.seo_score || 0;
                const scoreClass = score >= 75 ? 'high' : score >= 25 ? 'medium' : 'low';
                const collection = p.matched_collection;
                
                // Générer preview du meta title
                const metaTitle = p.title + ' | ''' + SITE_NAME + '''';
                
                return `
                    <div class="product-card">
                        <div class="product-check ${isSelected ? 'checked' : ''}" onclick="toggleSelect(${p.id})"></div>
                        
                        <div class="product-info">
                            <img class="product-image" src="${imageUrl}" onerror="this.style.display='none'">
                            <div>
                                <div class="product-title">${p.title.substring(0, 50)}${p.title.length > 50 ? '...' : ''}</div>
                                <div class="product-sku">SKU: ${sku}</div>
                                ${collection ? `<div class="product-collection">📁 ${collection.title}</div>` : '<div class="product-collection" style="color:#ff4757;">⚠️ Pas de collection</div>'}
                            </div>
                        </div>
                        
                        <div class="product-seo">
                            <div class="seo-preview">
                                <div class="seo-preview-title">${metaTitle.substring(0, 60)}</div>
                                <div class="seo-preview-desc">Achetez la ${p.title.substring(0, 30)}... sur ${SITE_NAME}</div>
                            </div>
                        </div>
                        
                        <div class="product-score">
                            <div class="score-circle ${scoreClass}">${score}%</div>
                            <div class="score-label">Score SEO</div>
                        </div>
                        
                        <div class="product-actions">
                            <button class="action-btn preview" onclick="showPreview(${p.id})">👁️ Préview</button>
                            <button class="action-btn ai" onclick="generateOne(${p.id})">🤖 IA</button>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function toggleSelect(id) {
            if (selectedIds.has(id)) {
                selectedIds.delete(id);
            } else {
                selectedIds.add(id);
            }
            document.getElementById('selected-count').textContent = selectedIds.size;
            filterProducts();
        }
        
        async function showPreview(productId) {
            currentPreviewId = productId;
            document.getElementById('preview-content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            document.getElementById('preview-modal').classList.add('show');
            
            try {
                const response = await fetch(`/api/seo/preview/${productId}`);
                const data = await response.json();
                
                const html = `
                    <p><strong>Produit:</strong> ${data.product.title}</p>
                    ${data.matched_collection ? `<p><strong>Collection:</strong> ${data.matched_collection.title}</p>` : ''}
                    ${data.external_info?.source ? `<p><strong>Source IA:</strong> ${data.external_info.source}</p>` : ''}
                    
                    <div class="modal-preview">
                        <h4>📝 Meta Title</h4>
                        <pre>${data.generated.meta_title}</pre>
                    </div>
                    
                    <div class="modal-preview">
                        <h4>📄 Meta Description</h4>
                        <pre>${data.generated.meta_description}</pre>
                    </div>
                    
                    <div class="modal-preview">
                        <h4>📖 Description avec liens</h4>
                        <pre>${escapeHtml(data.generated.body_html)}</pre>
                    </div>
                `;
                
                document.getElementById('preview-content').innerHTML = html;
            } catch (error) {
                document.getElementById('preview-content').innerHTML = '<p>Erreur de chargement</p>';
            }
        }
        
        function escapeHtml(text) {
            return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }
        
        function closeModal() {
            document.getElementById('preview-modal').classList.remove('show');
        }
        
        async function applyPreview() {
            if (!currentPreviewId) return;
            closeModal();
            
            showToast('Application en cours...', 'success');
            
            try {
                const response = await fetch('/api/seo/generate-single', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ product_id: currentPreviewId, use_ai: true })
                });
                
                const result = await response.json();
                if (result.success) {
                    showToast('SEO appliqué avec succès !', 'success');
                    loadProducts();
                } else {
                    showToast('Erreur lors de l\\'application', 'error');
                }
            } catch (error) {
                showToast('Erreur: ' + error.message, 'error');
            }
        }
        
        async function generateOne(productId) {
            showToast('Génération IA en cours...', 'success');
            
            try {
                const response = await fetch('/api/seo/generate-single', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ product_id: productId, use_ai: true })
                });
                
                const result = await response.json();
                if (result.success) {
                    showToast('SEO généré avec succès !', 'success');
                    loadProducts();
                } else {
                    showToast('Erreur', 'error');
                }
            } catch (error) {
                showToast('Erreur: ' + error.message, 'error');
            }
        }
        
        async function generateSelected() {
            if (selectedIds.size === 0) {
                showToast('Sélectionnez des produits', 'error');
                return;
            }
            
            startBatch(Array.from(selectedIds), false);
        }
        
        async function generateAll() {
            if (!confirm(`Générer le SEO pour ${products.length} produits ?\\nCela prendra environ ${Math.ceil(products.length * 1.2 / 60)} minutes.`)) {
                return;
            }
            
            const allIds = products.map(p => p.id);
            startBatch(allIds, false);
        }
        
        async function startBatch(ids, useAi) {
            showProgress();
            
            try {
                await fetch('/api/seo/generate-batch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ product_ids: ids, use_ai: useAi })
                });
                
                monitorProgress();
            } catch (error) {
                hideProgress();
                showToast('Erreur: ' + error.message, 'error');
            }
        }
        
        let progressInterval;
        
        function monitorProgress() {
            progressInterval = setInterval(async () => {
                try {
                    const response = await fetch('/api/progress');
                    const prog = await response.json();
                    
                    const pct = prog.total > 0 ? (prog.current / prog.total * 100) : 0;
                    document.getElementById('progress-fill').style.width = pct + '%';
                    document.getElementById('progress-count').textContent = `${prog.current} / ${prog.total}`;
                    document.getElementById('progress-text').textContent = prog.message;
                    
                    if (!prog.running) {
                        clearInterval(progressInterval);
                        hideProgress();
                        showToast(`Terminé ! ${prog.success_count} réussis`, 'success');
                        selectedIds.clear();
                        loadProducts();
                    }
                } catch (e) {
                    console.error(e);
                }
            }, 800);
        }
        
        function showProgress() {
            document.getElementById('progress-bar').classList.add('show');
        }
        
        function hideProgress() {
            document.getElementById('progress-bar').classList.remove('show');
        }
        
        function showToast(message, type) {
            const existing = document.querySelector('.toast');
            if (existing) existing.remove();
            
            const toast = document.createElement('div');
            toast.className = 'toast ' + type;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 4000);
        }
        
        // Event listeners
        document.getElementById('search').addEventListener('input', filterProducts);
        document.getElementById('filter-score').addEventListener('change', filterProducts);
        
        // Init
        const SITE_NAME = "''' + SITE_NAME + '''";
        loadProducts();
    </script>
</body>
</html>
'''


if __name__ == '__main__':
    print(f"[V4] Démarrage - Shop: {SHOP}")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
