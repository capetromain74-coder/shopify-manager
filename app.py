"""
Shopify Manager V3 - SEO Pro Edition
Basé sur l'analyse SEO de WetTheNew et Limited Resell
"""

from flask import Flask, jsonify, request, Response
import json
import os
import time
import re
import ssl
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from datetime import datetime, timedelta
from threading import Thread

app = Flask(__name__)

# Configuration
SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'

# Configuration SEO - Personnalise ces valeurs !
SITE_NAME = os.environ.get('SITE_NAME', 'KP SHOES')
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'kpshoes.fr')

# Bénéfices pour les meta descriptions
BENEFITS = [
    "100% Authentique",
    "Livraison rapide", 
    "Paiement 3x sans frais"
]

# Progress tracking
task_progress = {
    'running': False,
    'current': 0,
    'total': 0,
    'message': '',
    'type': ''
}


def shopify_request(endpoint, method='GET', data=None):
    """Fait une requête à l'API Shopify"""
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
        print(f"[API Error] {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"[Error] {e}")
        return None


def get_all_products():
    """Récupère TOUS les produits avec pagination"""
    all_products = []
    since_id = 0
    
    while True:
        endpoint = f'products.json?limit=250&since_id={since_id}'
        result = shopify_request(endpoint)
        
        if result and 'products' in result and len(result['products']) > 0:
            products = result['products']
            all_products.extend(products)
            since_id = products[-1]['id']
            print(f"[API] Récupéré {len(all_products)} produits...")
            
            if len(products) < 250:
                break
            time.sleep(0.5)
        else:
            break
    
    return all_products


def slugify(text):
    """Convertit un texte en slug URL"""
    if not text:
        return ''
    # Minuscules
    text = text.lower()
    # Remplacer les accents
    accents = {'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e', 'à': 'a', 'â': 'a', 'ä': 'a',
               'ù': 'u', 'û': 'u', 'ü': 'u', 'ô': 'o', 'ö': 'o', 'î': 'i', 'ï': 'i',
               'ç': 'c', 'ñ': 'n'}
    for acc, rep in accents.items():
        text = text.replace(acc, rep)
    # Garder uniquement lettres, chiffres, tirets
    text = re.sub(r'[^a-z0-9\-]', '-', text)
    # Supprimer tirets multiples
    text = re.sub(r'-+', '-', text)
    # Supprimer tirets début/fin
    text = text.strip('-')
    return text


def extract_sku(product):
    """Extrait le SKU du produit"""
    if product.get('variants') and len(product['variants']) > 0:
        return product['variants'][0].get('sku', '')
    return ''


def extract_brand(product):
    """Extrait la marque du titre du produit"""
    title = product.get('title', '')
    # Marques courantes
    brands = ['Adidas', 'Nike', 'Air Jordan', 'Jordan', 'New Balance', 'Puma', 
              'Asics', 'Converse', 'Vans', 'Reebok', 'UGG', 'Yeezy', 'Salomon',
              'On Running', 'Hoka', 'Crocs', 'Birkenstock', 'Dr. Martens']
    
    title_lower = title.lower()
    for brand in brands:
        if brand.lower() in title_lower:
            return brand
    
    # Sinon prendre le vendor ou le premier mot
    return product.get('vendor', title.split()[0] if title else '')


def extract_colorway(product):
    """Extrait le colorway du titre"""
    title = product.get('title', '')
    # Chercher entre parenthèses
    match = re.search(r'\(([^)]+)\)', title)
    if match:
        return match.group(1)
    # Sinon chercher après le dernier tiret ou espace
    parts = title.split(' - ')
    if len(parts) > 1:
        return parts[-1]
    return ''


def strip_html(html):
    """Supprime les balises HTML"""
    if not html:
        return ''
    clean = re.sub(r'<[^>]+>', ' ', html)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


# ============================================
# GÉNÉRATION SEO PROFESSIONNELLE
# ============================================

def generate_meta_title(product):
    """
    Génère un Meta Title optimisé SEO
    Format: {Nom Produit} | {Site} (max 60 car.)
    """
    title = product.get('title', '')
    meta_title = f"{title} | {SITE_NAME}"
    
    # Tronquer si > 60 caractères
    if len(meta_title) > 60:
        # Garder le nom du site, tronquer le titre
        max_title_len = 60 - len(f" | {SITE_NAME}") - 3  # -3 pour "..."
        meta_title = f"{title[:max_title_len]}... | {SITE_NAME}"
    
    return meta_title


def generate_meta_description(product):
    """
    Génère une Meta Description optimisée SEO
    Format: Achetez la {Nom} (SKU: {SKU}) sur {Site} ✓ Bénéfice1 ✓ Bénéfice2 ✓ Bénéfice3.
    Max 155 caractères
    """
    title = product.get('title', '')
    sku = extract_sku(product)
    
    # Format avec SKU si disponible
    if sku:
        base = f"Achetez la {title} (SKU: {sku}) sur {SITE_NAME}"
    else:
        base = f"Achetez la {title} sur {SITE_NAME}"
    
    # Ajouter les bénéfices
    benefits_str = " ✓ ".join(BENEFITS)
    meta_desc = f"{base} ✓ {benefits_str}."
    
    # Tronquer si > 155 caractères
    if len(meta_desc) > 155:
        # Version courte sans tous les bénéfices
        if sku:
            meta_desc = f"Achetez la {title} (SKU: {sku}) ✓ {BENEFITS[0]} ✓ {BENEFITS[1]} - {SITE_NAME}"
        else:
            meta_desc = f"Achetez la {title} ✓ {BENEFITS[0]} ✓ {BENEFITS[1]} ✓ {BENEFITS[2]} - {SITE_NAME}"
        
        if len(meta_desc) > 155:
            meta_desc = meta_desc[:152] + "..."
    
    return meta_desc


def generate_product_description(product):
    """
    Génère une description produit optimisée SEO
    Inclut: nom, marque, SKU, colorway, description
    """
    title = product.get('title', '')
    brand = extract_brand(product)
    sku = extract_sku(product)
    colorway = extract_colorway(product)
    current_desc = strip_html(product.get('body_html', ''))
    
    # Construction de la description
    lines = []
    
    # Paragraphe 1: Présentation
    if current_desc and len(current_desc) > 50:
        # Utiliser la description existante si elle est bonne
        lines.append(f"<p>{current_desc}</p>")
    else:
        # Générer une description basique
        lines.append(f"<p>Découvrez la <strong>{title}</strong>, une sneaker iconique de la marque {brand}.</p>")
    
    # Paragraphe 2: Données techniques
    tech_lines = []
    if sku:
        tech_lines.append(f"<strong>SKU</strong> : {sku}")
    if colorway:
        tech_lines.append(f"<strong>Colorway</strong> : {colorway}")
    tech_lines.append(f"<strong>Marque</strong> : {brand}")
    
    if tech_lines:
        lines.append("<p>" + "<br>".join(tech_lines) + "</p>")
    
    # Paragraphe 3: Authenticité
    lines.append(f"<p>Chez <strong>{SITE_NAME}</strong>, toutes nos sneakers sont <strong>100% authentiques</strong> et livrées dans leur boîte d'origine avec un certificat d'authenticité.</p>")
    
    return "\n".join(lines)


def generate_handle(product):
    """Génère un handle/URL optimisé"""
    title = product.get('title', '')
    return slugify(title)


def generate_all_seo(product):
    """Génère toutes les données SEO pour un produit"""
    return {
        'meta_title': generate_meta_title(product),
        'meta_description': generate_meta_description(product),
        'handle': generate_handle(product),
        'body_html': generate_product_description(product)
    }


# ============================================
# MISE À JOUR SHOPIFY
# ============================================

def update_product_seo(product_id, seo_data):
    """Met à jour les données SEO d'un produit"""
    success = True
    
    # Mise à jour des champs produit (handle, body_html)
    product_update = {'product': {'id': product_id}}
    
    if 'handle' in seo_data:
        product_update['product']['handle'] = seo_data['handle']
    
    if 'body_html' in seo_data:
        product_update['product']['body_html'] = seo_data['body_html']
    
    if len(product_update['product']) > 1:
        result = shopify_request(f'products/{product_id}.json', 'PUT', product_update)
        if not result:
            success = False
        time.sleep(0.3)
    
    # Mise à jour du Meta Title via metafield
    if 'meta_title' in seo_data:
        # D'abord essayer de créer
        result = shopify_request(f'products/{product_id}/metafields.json', 'POST', {
            'metafield': {
                'namespace': 'global',
                'key': 'title_tag',
                'value': seo_data['meta_title'],
                'type': 'single_line_text_field'
            }
        })
        
        if not result:
            # Si échec, chercher et mettre à jour l'existant
            metafields = shopify_request(f'products/{product_id}/metafields.json')
            if metafields and 'metafields' in metafields:
                for mf in metafields['metafields']:
                    if mf.get('namespace') == 'global' and mf.get('key') == 'title_tag':
                        shopify_request(f'metafields/{mf["id"]}.json', 'PUT', {
                            'metafield': {'id': mf['id'], 'value': seo_data['meta_title']}
                        })
                        break
        time.sleep(0.3)
    
    # Mise à jour de la Meta Description via metafield
    if 'meta_description' in seo_data:
        result = shopify_request(f'products/{product_id}/metafields.json', 'POST', {
            'metafield': {
                'namespace': 'global',
                'key': 'description_tag',
                'value': seo_data['meta_description'],
                'type': 'single_line_text_field'
            }
        })
        
        if not result:
            metafields = shopify_request(f'products/{product_id}/metafields.json')
            if metafields and 'metafields' in metafields:
                for mf in metafields['metafields']:
                    if mf.get('namespace') == 'global' and mf.get('key') == 'description_tag':
                        shopify_request(f'metafields/{mf["id"]}.json', 'PUT', {
                            'metafield': {'id': mf['id'], 'value': seo_data['meta_description']}
                        })
                        break
        time.sleep(0.3)
    
    return success


# ============================================
# ROUTES API
# ============================================

@app.route('/')
def home():
    return HOME_TEMPLATE


@app.route('/site')
def site_management():
    return SITE_TEMPLATE


@app.route('/seo')
def seo_management():
    return SEO_TEMPLATE


@app.route('/api/products')
def api_get_products():
    products = get_all_products()
    return jsonify({'products': products})


@app.route('/api/products/<int:product_id>')
def api_get_product(product_id):
    result = shopify_request(f'products/{product_id}.json')
    if result and 'product' in result:
        return jsonify(result['product'])
    return jsonify({'error': 'Product not found'}), 404


@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)


@app.route('/api/seo/preview/<int:product_id>')
def api_seo_preview(product_id):
    """Prévisualise les données SEO générées pour un produit"""
    result = shopify_request(f'products/{product_id}.json')
    if result and 'product' in result:
        product = result['product']
        seo = generate_all_seo(product)
        return jsonify({
            'product': product,
            'generated_seo': seo,
            'current_seo': {
                'title': product.get('title'),
                'handle': product.get('handle'),
                'body_html': product.get('body_html')
            }
        })
    return jsonify({'error': 'Product not found'}), 404


@app.route('/api/seo/generate', methods=['POST'])
def api_generate_seo_single():
    """Génère et applique le SEO pour un seul produit"""
    data = request.json
    product_id = data.get('product_id')
    fields = data.get('fields', ['meta_title', 'meta_description', 'handle', 'body_html'])
    
    result = shopify_request(f'products/{product_id}.json')
    if not result or 'product' not in result:
        return jsonify({'error': 'Product not found'}), 404
    
    product = result['product']
    all_seo = generate_all_seo(product)
    
    # Filtrer les champs demandés
    seo_data = {k: v for k, v in all_seo.items() if k in fields}
    
    # Appliquer
    success = update_product_seo(product_id, seo_data)
    
    return jsonify({
        'success': success,
        'applied_seo': seo_data
    })


@app.route('/api/seo/generate-batch', methods=['POST'])
def api_generate_seo_batch():
    """Génère et applique le SEO pour plusieurs produits"""
    global task_progress
    
    data = request.json
    product_ids = data.get('product_ids', [])
    fields = data.get('fields', ['meta_title', 'meta_description'])
    
    if not product_ids:
        return jsonify({'error': 'No products selected'}), 400
    
    def process_batch():
        global task_progress
        task_progress = {
            'running': True,
            'current': 0,
            'total': len(product_ids),
            'message': 'Démarrage...',
            'type': 'seo_batch',
            'results': []
        }
        
        for i, pid in enumerate(product_ids):
            task_progress['current'] = i + 1
            task_progress['message'] = f'Traitement produit {i+1}/{len(product_ids)}'
            
            # Récupérer le produit
            result = shopify_request(f'products/{pid}.json')
            if result and 'product' in result:
                product = result['product']
                all_seo = generate_all_seo(product)
                seo_data = {k: v for k, v in all_seo.items() if k in fields}
                
                success = update_product_seo(pid, seo_data)
                task_progress['results'].append({
                    'id': pid,
                    'title': product.get('title'),
                    'success': success
                })
            
            time.sleep(0.5)  # Rate limit
        
        task_progress['running'] = False
        task_progress['message'] = f'Terminé ! {len(product_ids)} produits mis à jour.'
    
    thread = Thread(target=process_batch)
    thread.start()
    
    return jsonify({'status': 'started', 'total': len(product_ids)})


@app.route('/api/seo/update', methods=['POST'])
def api_update_seo():
    """Met à jour manuellement les données SEO d'un produit"""
    data = request.json
    product_id = data.get('product_id')
    seo_data = {
        'meta_title': data.get('meta_title'),
        'meta_description': data.get('meta_description'),
        'handle': data.get('handle')
    }
    
    # Filtrer les valeurs None
    seo_data = {k: v for k, v in seo_data.items() if v is not None}
    
    success = update_product_seo(product_id, seo_data)
    return jsonify({'success': success})


# ============================================
# Routes pour la gestion du site (V2)
# ============================================

@app.route('/api/tags')
def api_get_tags():
    products = get_all_products()
    tags = {}
    for p in products:
        for tag in (p.get('tags') or '').split(', '):
            tag = tag.strip()
            if tag:
                tags[tag] = tags.get(tag, 0) + 1
    return jsonify({'tags': tags})


@app.route('/api/products/add-tags', methods=['POST'])
def api_add_tags():
    global task_progress
    data = request.json
    product_ids = data.get('product_ids', [])
    new_tags = data.get('tags', [])
    
    if not product_ids or not new_tags:
        return jsonify({'error': 'Missing data'}), 400
    
    def process():
        global task_progress
        task_progress = {'running': True, 'current': 0, 'total': len(product_ids), 'message': 'Ajout des balises...', 'type': 'add_tags'}
        
        for i, pid in enumerate(product_ids):
            task_progress['current'] = i + 1
            task_progress['message'] = f'Traitement {i+1}/{len(product_ids)}'
            
            result = shopify_request(f'products/{pid}.json')
            if result and 'product' in result:
                current_tags = result['product'].get('tags', '')
                all_tags = set(t.strip() for t in current_tags.split(',') if t.strip())
                all_tags.update(new_tags)
                
                shopify_request(f'products/{pid}.json', 'PUT', {
                    'product': {'id': pid, 'tags': ', '.join(all_tags)}
                })
            time.sleep(0.5)
        
        task_progress['running'] = False
        task_progress['message'] = 'Terminé !'
    
    Thread(target=process).start()
    return jsonify({'status': 'started'})


@app.route('/api/products/remove-tags', methods=['POST'])
def api_remove_tags():
    global task_progress
    data = request.json
    product_ids = data.get('product_ids', [])
    tags_to_remove = data.get('tags', [])
    
    def process():
        global task_progress
        task_progress = {'running': True, 'current': 0, 'total': len(product_ids), 'message': 'Suppression des balises...', 'type': 'remove_tags'}
        
        for i, pid in enumerate(product_ids):
            task_progress['current'] = i + 1
            
            result = shopify_request(f'products/{pid}.json')
            if result and 'product' in result:
                current_tags = result['product'].get('tags', '')
                tags = set(t.strip() for t in current_tags.split(',') if t.strip())
                tags -= set(tags_to_remove)
                
                shopify_request(f'products/{pid}.json', 'PUT', {
                    'product': {'id': pid, 'tags': ', '.join(tags)}
                })
            time.sleep(0.5)
        
        task_progress['running'] = False
    
    Thread(target=process).start()
    return jsonify({'status': 'started'})


@app.route('/api/products/delete', methods=['POST'])
def api_delete_products():
    global task_progress
    data = request.json
    product_ids = data.get('product_ids', [])
    
    def process():
        global task_progress
        task_progress = {'running': True, 'current': 0, 'total': len(product_ids), 'message': 'Suppression...', 'type': 'delete'}
        
        for i, pid in enumerate(product_ids):
            task_progress['current'] = i + 1
            task_progress['message'] = f'Suppression {i+1}/{len(product_ids)}'
            shopify_request(f'products/{pid}.json', 'DELETE')
            time.sleep(0.6)
        
        task_progress['running'] = False
        task_progress['message'] = f'{len(product_ids)} produits supprimés'
    
    Thread(target=process).start()
    return jsonify({'status': 'started'})


# ============================================
# TEMPLATES HTML
# ============================================

HOME_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shopify Manager V3 - SEO Pro</title>
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
        .container {
            text-align: center;
            padding: 40px;
        }
        .logo {
            font-size: 60px;
            margin-bottom: 20px;
            animation: float 3s ease-in-out infinite;
        }
        @keyframes float {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }
        h1 {
            font-size: 42px;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #00ff88, #00cc6a);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        h1 span { color: #fff; -webkit-text-fill-color: #fff; }
        .version {
            display: inline-block;
            background: linear-gradient(135deg, #8b5cf6, #6d28d9);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            margin-bottom: 20px;
        }
        .subtitle {
            color: #888;
            font-size: 18px;
            margin-bottom: 50px;
        }
        .buttons {
            display: flex;
            gap: 30px;
            justify-content: center;
            flex-wrap: wrap;
        }
        .btn-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid #333;
            border-radius: 20px;
            padding: 40px;
            width: 280px;
            text-decoration: none;
            color: #fff;
            transition: all 0.3s;
        }
        .btn-card:hover {
            transform: translateY(-5px);
            border-color: #00ff88;
            background: rgba(0,255,136,0.05);
        }
        .btn-card.seo {
            border-color: #8b5cf6;
        }
        .btn-card.seo:hover {
            border-color: #a78bfa;
            background: rgba(139,92,246,0.1);
        }
        .btn-card .icon {
            font-size: 50px;
            margin-bottom: 20px;
        }
        .btn-card h2 {
            font-size: 22px;
            margin-bottom: 10px;
        }
        .btn-card p {
            color: #888;
            font-size: 14px;
        }
        .status {
            margin-top: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            font-size: 14px;
            color: #888;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            background: #00ff88;
            border-radius: 50%;
            box-shadow: 0 0 15px #00ff88;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🚀</div>
        <h1>Shopify<span>Manager</span></h1>
        <div class="version">V3 - SEO Pro Edition</div>
        <p class="subtitle">Optimisation SEO basée sur WetTheNew & Limited Resell</p>
        
        <div class="buttons">
            <a href="/site" class="btn-card">
                <div class="icon">🏷️</div>
                <h2>Gestion Site</h2>
                <p>Balises, suppression, filtres</p>
            </a>
            <a href="/seo" class="btn-card seo">
                <div class="icon">🔍</div>
                <h2>Gestion SEO Pro</h2>
                <p>Meta titles, descriptions, URLs optimisés</p>
            </a>
        </div>
        
        <div class="status">
            <div class="status-dot"></div>
            Connecté à ''' + SHOP + '''
        </div>
    </div>
</body>
</html>
'''

SEO_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔍 Gestion SEO Pro | Shopify Manager V3</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
            min-height: 100vh;
            color: #fff;
        }
        .header {
            padding: 20px 40px;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(0,0,0,0.3);
        }
        .header-left { display: flex; align-items: center; gap: 20px; }
        .back-btn {
            padding: 10px 20px;
            background: #333;
            border: none;
            border-radius: 8px;
            color: #fff;
            text-decoration: none;
            font-size: 14px;
        }
        .back-btn:hover { background: #444; }
        .logo { font-size: 20px; font-weight: bold; }
        .logo span { color: #8b5cf6; }
        
        .container { max-width: 1600px; margin: 0 auto; padding: 30px; }
        
        .seo-info {
            background: linear-gradient(135deg, rgba(139,92,246,0.2), rgba(109,40,217,0.2));
            border: 1px solid #8b5cf6;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .seo-info h3 { color: #a78bfa; margin-bottom: 10px; }
        .seo-info p { color: #888; font-size: 14px; line-height: 1.6; }
        .seo-info code { background: #333; padding: 2px 6px; border-radius: 4px; color: #00ff88; }
        
        .controls {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            align-items: flex-end;
        }
        .control-group { display: flex; flex-direction: column; gap: 6px; }
        .control-group label { font-size: 12px; color: #888; text-transform: uppercase; }
        .control-group input, .control-group select {
            padding: 10px 14px;
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 8px;
            color: #fff;
            font-size: 14px;
            min-width: 200px;
        }
        
        .btn { padding: 12px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; transition: all 0.2s; }
        .btn-primary { background: linear-gradient(135deg, #00ff88, #00cc6a); color: #000; }
        .btn-ai { background: linear-gradient(135deg, #8b5cf6, #6d28d9); color: #fff; }
        .btn-secondary { background: #333; color: #fff; }
        .btn:hover { transform: translateY(-1px); opacity: 0.9; }
        
        .selected-info { padding: 8px 16px; background: #0a0a0f; border-radius: 8px; font-size: 13px; color: #888; }
        .selected-info strong { color: #8b5cf6; }
        
        .seo-table { background: #1a1a2e; border-radius: 12px; overflow-x: auto; border: 1px solid #333; }
        .seo-table table { width: 100%; border-collapse: collapse; min-width: 1400px; }
        .seo-table th { padding: 16px; background: #0a0a0f; font-size: 12px; text-transform: uppercase; color: #888; font-weight: 600; text-align: left; position: sticky; top: 0; }
        .seo-table td { padding: 12px 16px; border-bottom: 1px solid #2a2a3a; vertical-align: top; }
        .seo-table tr:hover { background: rgba(255,255,255,0.02); }
        
        .checkbox { width: 22px; height: 22px; border: 2px solid #444; border-radius: 5px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .checkbox.checked { background: #8b5cf6; border-color: #8b5cf6; }
        .checkbox.checked::after { content: '✓'; color: #fff; font-size: 14px; font-weight: bold; }
        
        .product-cell { display: flex; align-items: center; gap: 12px; }
        .product-image { width: 50px; height: 50px; border-radius: 8px; object-fit: cover; background: #333; }
        .product-title { font-weight: 500; font-size: 13px; }
        .product-sku { font-size: 11px; color: #666; font-family: monospace; margin-top: 4px; }
        .product-brand { font-size: 10px; color: #8b5cf6; margin-top: 2px; }
        
        .seo-field { font-size: 12px; max-width: 280px; word-wrap: break-word; }
        .seo-field.empty { color: #ff4757; font-style: italic; }
        .seo-field.ok { color: #00ff88; }
        .seo-field.warning { color: #ffa502; }
        .seo-field.preview { color: #8b5cf6; background: rgba(139,92,246,0.1); padding: 8px; border-radius: 6px; border: 1px dashed #8b5cf6; }
        
        .char-count { font-size: 10px; color: #666; margin-top: 4px; }
        .char-count.ok { color: #00ff88; }
        .char-count.warning { color: #ffa502; }
        .char-count.error { color: #ff4757; }
        
        .progress-bar { position: fixed; top: 0; left: 0; right: 0; background: #1a1a2e; padding: 20px; z-index: 1000; border-bottom: 1px solid #333; display: none; }
        .progress-bar.show { display: block; }
        .progress-track { height: 10px; background: #333; border-radius: 5px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #8b5cf6, #6d28d9); transition: width 0.3s; }
        .progress-text { margin-top: 10px; font-size: 14px; color: #888; }
        
        .loading { text-align: center; padding: 60px; }
        .spinner { width: 40px; height: 40px; border: 3px solid #333; border-top-color: #8b5cf6; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.85); display: none; align-items: center; justify-content: center; z-index: 1000; }
        .modal-overlay.show { display: flex; }
        .modal { background: #1a1a2e; padding: 32px; border-radius: 16px; width: 100%; max-width: 700px; border: 1px solid #333; max-height: 90vh; overflow-y: auto; }
        .modal h2 { margin-bottom: 10px; }
        .modal .subtitle { color: #888; font-size: 14px; margin-bottom: 24px; }
        .modal .control-group { margin-bottom: 20px; }
        .modal input, .modal select, .modal textarea { width: 100%; }
        .modal textarea { min-height: 100px; resize: vertical; font-family: inherit; }
        .modal-actions { display: flex; gap: 12px; margin-top: 28px; }
        .modal-actions .btn { flex: 1; justify-content: center; }
        
        .checkbox-group { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }
        .checkbox-label { display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: #0a0a0f; border: 1px solid #333; border-radius: 8px; cursor: pointer; font-size: 13px; }
        .checkbox-label input { display: none; }
        .checkbox-label.checked { border-color: #8b5cf6; background: rgba(139,92,246,0.1); }
        
        .toast { position: fixed; bottom: 24px; right: 24px; padding: 16px 24px; border-radius: 10px; font-weight: 500; z-index: 2000; animation: slideIn 0.3s ease; }
        .toast.success { background: #00ff88; color: #000; }
        .toast.error { background: #ff4757; color: #fff; }
        @keyframes slideIn { from { transform: translateX(100px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        
        .action-btns { display: flex; gap: 6px; }
        .action-btn { padding: 6px 10px; font-size: 11px; border: none; border-radius: 5px; cursor: pointer; }
        .action-btn.preview { background: #333; color: #fff; }
        .action-btn.apply { background: #8b5cf6; color: #fff; }
        .action-btn:hover { opacity: 0.8; }
    </style>
</head>
<body>
    <div class="progress-bar" id="progress-bar">
        <div class="progress-track">
            <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
        </div>
        <p class="progress-text" id="progress-text">Initialisation...</p>
    </div>

    <header class="header">
        <div class="header-left">
            <a href="/" class="back-btn">← Retour</a>
            <div class="logo">🔍 Gestion <span>SEO Pro</span></div>
        </div>
    </header>
    
    <main class="container">
        <div class="seo-info">
            <h3>💡 Formules SEO optimisées</h3>
            <p>
                <strong>Meta Title :</strong> <code>{Nom Produit} | ''' + SITE_NAME + '''</code> (max 60 car.)<br>
                <strong>Meta Description :</strong> <code>Achetez la {Nom} (SKU: {SKU}) sur ''' + SITE_NAME + ''' ✓ 100% Authentique ✓ Livraison rapide ✓ Paiement 3x.</code> (max 155 car.)
            </p>
        </div>
        
        <div class="controls">
            <div class="control-group">
                <label>Rechercher</label>
                <input type="text" id="search" placeholder="Nom, SKU, marque...">
            </div>
            <div class="control-group">
                <label>Filtrer</label>
                <select id="filter-seo">
                    <option value="all">Tous les produits</option>
                    <option value="needs-seo">Besoin d'optimisation SEO</option>
                </select>
            </div>
            <button class="btn btn-secondary" onclick="loadProducts()">🔄 Actualiser</button>
            <button class="btn btn-ai" onclick="openGenerateModal()">🤖 Générer SEO en masse</button>
            <div class="selected-info">
                <strong id="selection-count">0</strong> sélectionné(s)
            </div>
        </div>
        
        <div class="seo-table">
            <table>
                <thead>
                    <tr>
                        <th style="width:50px"><div class="checkbox" id="select-all" onclick="toggleSelectAll()"></div></th>
                        <th style="width:220px">Produit</th>
                        <th style="width:300px">Meta Title (actuel → généré)</th>
                        <th style="width:350px">Meta Description (générée)</th>
                        <th style="width:150px">Handle</th>
                        <th style="width:120px">Actions</th>
                    </tr>
                </thead>
                <tbody id="products-list">
                    <tr><td colspan="6" class="loading"><div class="spinner"></div><p>Chargement...</p></td></tr>
                </tbody>
            </table>
        </div>
    </main>
    
    <div class="modal-overlay" id="generate-modal">
        <div class="modal">
            <h2>🤖 Générer le SEO optimisé</h2>
            <p class="subtitle">Génération basée sur les formules WetTheNew & Limited Resell pour <strong id="modal-count">0</strong> produits.</p>
            
            <div class="control-group">
                <label>Champs à générer et appliquer</label>
                <div class="checkbox-group" id="fields-checkboxes">
                    <label class="checkbox-label checked" data-field="meta_title">
                        <input type="checkbox" checked> Meta Title
                    </label>
                    <label class="checkbox-label checked" data-field="meta_description">
                        <input type="checkbox" checked> Meta Description
                    </label>
                    <label class="checkbox-label" data-field="handle">
                        <input type="checkbox"> Handle (URL)
                    </label>
                    <label class="checkbox-label" data-field="body_html">
                        <input type="checkbox"> Description produit
                    </label>
                </div>
            </div>
            
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeModal('generate-modal')">Annuler</button>
                <button class="btn btn-ai" onclick="generateBatch()">🚀 Générer et appliquer</button>
            </div>
        </div>
    </div>
    
    <div class="modal-overlay" id="edit-modal">
        <div class="modal">
            <h2>✏️ Modifier le SEO</h2>
            <input type="hidden" id="edit-product-id">
            
            <div class="control-group">
                <label>Meta Title (max 60 car.)</label>
                <input type="text" id="edit-meta-title" maxlength="70" oninput="updateEditCharCount()">
                <div class="char-count" id="edit-title-count">0/60</div>
            </div>
            
            <div class="control-group">
                <label>Meta Description (max 155 car.)</label>
                <textarea id="edit-meta-desc" maxlength="200" oninput="updateEditCharCount()"></textarea>
                <div class="char-count" id="edit-desc-count">0/155</div>
            </div>
            
            <div class="control-group">
                <label>Handle (URL)</label>
                <input type="text" id="edit-handle">
            </div>
            
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeModal('edit-modal')">Annuler</button>
                <button class="btn btn-primary" onclick="saveEdit()">💾 Sauvegarder</button>
            </div>
        </div>
    </div>

    <script>
        let products = [];
        let filteredProducts = [];
        let selectedIds = new Set();
        
        // Fonctions SEO (côté client pour preview)
        function generateMetaTitle(product) {
            const siteName = "''' + SITE_NAME + '''";
            let title = product.title + " | " + siteName;
            if (title.length > 60) {
                const maxLen = 60 - siteName.length - 7;
                title = product.title.substring(0, maxLen) + "... | " + siteName;
            }
            return title;
        }
        
        function generateMetaDesc(product) {
            const siteName = "''' + SITE_NAME + '''";
            const sku = product.variants?.[0]?.sku || '';
            const benefits = "100% Authentique ✓ Livraison rapide ✓ Paiement 3x";
            
            let desc;
            if (sku) {
                desc = `Achetez la ${product.title} (SKU: ${sku}) sur ${siteName} ✓ ${benefits}.`;
            } else {
                desc = `Achetez la ${product.title} sur ${siteName} ✓ ${benefits}.`;
            }
            
            if (desc.length > 155) {
                desc = desc.substring(0, 152) + "...";
            }
            return desc;
        }
        
        async function loadProducts() {
            document.getElementById('products-list').innerHTML = '<tr><td colspan="6" class="loading"><div class="spinner"></div><p>Chargement des produits...</p></td></tr>';
            
            try {
                const response = await fetch('/api/products');
                const data = await response.json();
                products = data.products || [];
                filterProducts();
            } catch (error) {
                document.getElementById('products-list').innerHTML = '<tr><td colspan="6">Erreur de chargement</td></tr>';
            }
        }
        
        function filterProducts() {
            const search = document.getElementById('search').value.toLowerCase();
            const filter = document.getElementById('filter-seo').value;
            
            filteredProducts = products.filter(p => {
                const sku = p.variants?.[0]?.sku || '';
                const matchSearch = !search || 
                    p.title.toLowerCase().includes(search) ||
                    sku.toLowerCase().includes(search) ||
                    (p.vendor || '').toLowerCase().includes(search);
                
                if (!matchSearch) return false;
                
                // Filtre "needs-seo" : produits qui n'ont pas de meta title personnalisé
                if (filter === 'needs-seo') {
                    // On considère qu'un produit a besoin de SEO si son title n'a pas de | dedans
                    return true; // Pour l'instant, montrer tous
                }
                
                return true;
            });
            
            renderProducts();
        }
        
        function renderProducts() {
            const tbody = document.getElementById('products-list');
            
            if (filteredProducts.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:40px;color:#666;">Aucun produit trouvé</td></tr>';
                return;
            }
            
            tbody.innerHTML = filteredProducts.map(p => {
                const isSelected = selectedIds.has(p.id);
                const imageUrl = p.image?.src || '';
                const sku = p.variants?.[0]?.sku || 'N/A';
                const brand = p.vendor || p.title.split(' ')[0];
                const handle = p.handle || '';
                
                // Générer les previews SEO
                const generatedTitle = generateMetaTitle(p);
                const generatedDesc = generateMetaDesc(p);
                
                const titleLen = generatedTitle.length;
                const descLen = generatedDesc.length;
                
                const titleClass = titleLen <= 60 ? 'ok' : 'warning';
                const descClass = descLen <= 155 ? 'ok' : 'warning';
                
                return `
                    <tr>
                        <td><div class="checkbox ${isSelected ? 'checked' : ''}" onclick="toggleProduct(${p.id})"></div></td>
                        <td>
                            <div class="product-cell">
                                <img class="product-image" src="${imageUrl}" onerror="this.style.display='none'">
                                <div>
                                    <div class="product-title">${p.title.substring(0, 35)}${p.title.length > 35 ? '...' : ''}</div>
                                    <div class="product-sku">SKU: ${sku}</div>
                                    <div class="product-brand">${brand}</div>
                                </div>
                            </div>
                        </td>
                        <td>
                            <div class="seo-field preview">${generatedTitle}</div>
                            <div class="char-count ${titleClass}">${titleLen}/60 caractères</div>
                        </td>
                        <td>
                            <div class="seo-field preview">${generatedDesc.substring(0, 100)}${generatedDesc.length > 100 ? '...' : ''}</div>
                            <div class="char-count ${descClass}">${descLen}/155 caractères</div>
                        </td>
                        <td><div class="seo-field ok">/products/${handle}</div></td>
                        <td>
                            <div class="action-btns">
                                <button class="action-btn apply" onclick="applySeoSingle(${p.id})">✓ Appliquer</button>
                                <button class="action-btn preview" onclick="openEditModal(${p.id})">✏️</button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        }
        
        function toggleProduct(id) {
            if (selectedIds.has(id)) {
                selectedIds.delete(id);
            } else {
                selectedIds.add(id);
            }
            updateSelectionUI();
            renderProducts();
        }
        
        function toggleSelectAll() {
            const allSelected = filteredProducts.every(p => selectedIds.has(p.id));
            if (allSelected) {
                filteredProducts.forEach(p => selectedIds.delete(p.id));
            } else {
                filteredProducts.forEach(p => selectedIds.add(p.id));
            }
            updateSelectionUI();
            renderProducts();
        }
        
        function updateSelectionUI() {
            document.getElementById('selection-count').textContent = selectedIds.size;
            const selectAll = document.getElementById('select-all');
            const allSelected = filteredProducts.length > 0 && filteredProducts.every(p => selectedIds.has(p.id));
            selectAll.classList.toggle('checked', allSelected);
        }
        
        // Appliquer SEO pour un seul produit
        async function applySeoSingle(productId) {
            showToast('Application du SEO...', 'success');
            
            try {
                const response = await fetch('/api/seo/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        product_id: productId,
                        fields: ['meta_title', 'meta_description']
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    showToast('SEO appliqué avec succès !', 'success');
                } else {
                    showToast('Erreur lors de l\\'application', 'error');
                }
            } catch (error) {
                showToast('Erreur: ' + error.message, 'error');
            }
        }
        
        // Modal génération en masse
        function openGenerateModal() {
            if (selectedIds.size === 0) {
                showToast('Sélectionnez au moins un produit', 'error');
                return;
            }
            document.getElementById('modal-count').textContent = selectedIds.size;
            document.getElementById('generate-modal').classList.add('show');
        }
        
        function closeModal(id) {
            document.getElementById(id).classList.remove('show');
        }
        
        async function generateBatch() {
            const checkboxes = document.querySelectorAll('#fields-checkboxes .checkbox-label.checked');
            const fields = Array.from(checkboxes).map(cb => cb.dataset.field);
            
            if (fields.length === 0) {
                showToast('Sélectionnez au moins un champ', 'error');
                return;
            }
            
            closeModal('generate-modal');
            showProgress();
            
            try {
                const response = await fetch('/api/seo/generate-batch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        product_ids: Array.from(selectedIds),
                        fields: fields
                    })
                });
                
                // Suivre la progression
                const progressInterval = setInterval(async () => {
                    const prog = await fetch('/api/progress').then(r => r.json());
                    updateProgress(prog.current, prog.total, prog.message);
                    
                    if (!prog.running) {
                        clearInterval(progressInterval);
                        hideProgress();
                        showToast(prog.message, 'success');
                        selectedIds.clear();
                        updateSelectionUI();
                        loadProducts();
                    }
                }, 500);
                
            } catch (error) {
                hideProgress();
                showToast('Erreur: ' + error.message, 'error');
            }
        }
        
        // Modal édition manuelle
        function openEditModal(productId) {
            const product = products.find(p => p.id === productId);
            if (!product) return;
            
            document.getElementById('edit-product-id').value = productId;
            document.getElementById('edit-meta-title').value = generateMetaTitle(product);
            document.getElementById('edit-meta-desc').value = generateMetaDesc(product);
            document.getElementById('edit-handle').value = product.handle || '';
            updateEditCharCount();
            document.getElementById('edit-modal').classList.add('show');
        }
        
        function updateEditCharCount() {
            const titleLen = document.getElementById('edit-meta-title').value.length;
            const descLen = document.getElementById('edit-meta-desc').value.length;
            
            const titleCount = document.getElementById('edit-title-count');
            const descCount = document.getElementById('edit-desc-count');
            
            titleCount.textContent = `${titleLen}/60`;
            titleCount.className = 'char-count ' + (titleLen <= 60 ? 'ok' : titleLen <= 70 ? 'warning' : 'error');
            
            descCount.textContent = `${descLen}/155`;
            descCount.className = 'char-count ' + (descLen <= 155 ? 'ok' : descLen <= 170 ? 'warning' : 'error');
        }
        
        async function saveEdit() {
            const productId = document.getElementById('edit-product-id').value;
            const data = {
                product_id: parseInt(productId),
                meta_title: document.getElementById('edit-meta-title').value,
                meta_description: document.getElementById('edit-meta-desc').value,
                handle: document.getElementById('edit-handle').value
            };
            
            try {
                const response = await fetch('/api/seo/update', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                closeModal('edit-modal');
                
                if (result.success) {
                    showToast('SEO mis à jour !', 'success');
                } else {
                    showToast('Erreur lors de la mise à jour', 'error');
                }
            } catch (error) {
                showToast('Erreur: ' + error.message, 'error');
            }
        }
        
        // Checkbox toggle
        document.querySelectorAll('.checkbox-label').forEach(label => {
            label.addEventListener('click', () => {
                label.classList.toggle('checked');
            });
        });
        
        // Progress
        function showProgress() {
            document.getElementById('progress-bar').classList.add('show');
        }
        function hideProgress() {
            document.getElementById('progress-bar').classList.remove('show');
        }
        function updateProgress(current, total, message) {
            const pct = total > 0 ? (current / total * 100) : 0;
            document.getElementById('progress-fill').style.width = pct + '%';
            document.getElementById('progress-text').textContent = message;
        }
        
        // Toast
        function showToast(message, type) {
            const existing = document.querySelector('.toast');
            if (existing) existing.remove();
            
            const toast = document.createElement('div');
            toast.className = 'toast ' + type;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
        
        // Event listeners
        document.getElementById('search').addEventListener('input', filterProducts);
        document.getElementById('filter-seo').addEventListener('change', filterProducts);
        
        // Init
        loadProducts();
    </script>
</body>
</html>
'''

SITE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏷️ Gestion Site | Shopify Manager V3</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
            min-height: 100vh;
            color: #fff;
        }
        .header {
            padding: 20px 40px;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(0,0,0,0.3);
        }
        .header-left { display: flex; align-items: center; gap: 20px; }
        .back-btn {
            padding: 10px 20px;
            background: #333;
            border: none;
            border-radius: 8px;
            color: #fff;
            text-decoration: none;
        }
        .logo { font-size: 20px; font-weight: bold; }
        .logo span { color: #00ff88; }
        
        .container { max-width: 1400px; margin: 0 auto; padding: 30px; }
        
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: rgba(255,255,255,0.05); border: 1px solid #333; border-radius: 12px; padding: 20px; }
        .stat-card h3 { font-size: 32px; color: #00ff88; }
        .stat-card p { color: #888; font-size: 14px; }
        
        .controls { display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; align-items: flex-end; }
        .control-group { display: flex; flex-direction: column; gap: 6px; }
        .control-group label { font-size: 12px; color: #888; text-transform: uppercase; }
        .control-group input, .control-group select { padding: 10px 14px; background: #1a1a2e; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 14px; min-width: 200px; }
        
        .btn { padding: 12px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
        .btn-primary { background: linear-gradient(135deg, #00ff88, #00cc6a); color: #000; }
        .btn-danger { background: #ff4757; color: #fff; }
        .btn-secondary { background: #333; color: #fff; }
        
        .products-table { background: #1a1a2e; border-radius: 12px; overflow: hidden; border: 1px solid #333; }
        .products-table table { width: 100%; border-collapse: collapse; }
        .products-table th { padding: 16px; background: #0a0a0f; font-size: 12px; text-transform: uppercase; color: #888; text-align: left; }
        .products-table td { padding: 12px 16px; border-bottom: 1px solid #2a2a3a; }
        
        .checkbox { width: 22px; height: 22px; border: 2px solid #444; border-radius: 5px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .checkbox.checked { background: #00ff88; border-color: #00ff88; }
        .checkbox.checked::after { content: '✓'; color: #000; font-size: 14px; }
        
        .product-cell { display: flex; align-items: center; gap: 12px; }
        .product-image { width: 50px; height: 50px; border-radius: 8px; object-fit: cover; }
        .tag { display: inline-block; padding: 4px 10px; background: #333; border-radius: 20px; font-size: 11px; margin: 2px; }
        
        .progress-bar { position: fixed; top: 0; left: 0; right: 0; background: #1a1a2e; padding: 20px; z-index: 1000; border-bottom: 1px solid #333; display: none; }
        .progress-bar.show { display: block; }
        .progress-track { height: 10px; background: #333; border-radius: 5px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #00ff88, #00cc6a); transition: width 0.3s; }
        
        .loading { text-align: center; padding: 60px; }
        .spinner { width: 40px; height: 40px; border: 3px solid #333; border-top-color: #00ff88; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto; }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); display: none; align-items: center; justify-content: center; z-index: 1000; }
        .modal-overlay.show { display: flex; }
        .modal { background: #1a1a2e; padding: 30px; border-radius: 16px; width: 90%; max-width: 500px; }
        
        .toast { position: fixed; bottom: 24px; right: 24px; padding: 16px 24px; border-radius: 10px; z-index: 2000; }
        .toast.success { background: #00ff88; color: #000; }
        .toast.error { background: #ff4757; color: #fff; }
    </style>
</head>
<body>
    <div class="progress-bar" id="progress-bar">
        <div class="progress-track">
            <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
        </div>
        <p style="margin-top:10px;color:#888;" id="progress-text">Traitement en cours...</p>
    </div>

    <header class="header">
        <div class="header-left">
            <a href="/" class="back-btn">← Retour</a>
            <div class="logo">🏷️ Gestion <span>Site</span></div>
        </div>
    </header>
    
    <main class="container">
        <div class="stats">
            <div class="stat-card">
                <h3 id="total-products">-</h3>
                <p>Produits total</p>
            </div>
            <div class="stat-card">
                <h3 id="total-tags">-</h3>
                <p>Balises uniques</p>
            </div>
            <div class="stat-card">
                <h3 id="selected-count">0</h3>
                <p>Sélectionnés</p>
            </div>
        </div>
        
        <div class="controls">
            <div class="control-group">
                <label>Rechercher</label>
                <input type="text" id="search" placeholder="Nom, SKU...">
            </div>
            <div class="control-group">
                <label>Filtrer par balise</label>
                <select id="filter-tag">
                    <option value="">Toutes les balises</option>
                </select>
            </div>
            <button class="btn btn-secondary" onclick="loadData()">🔄 Actualiser</button>
            <button class="btn btn-primary" onclick="openAddTagModal()">+ Ajouter balise</button>
            <button class="btn btn-danger" onclick="openDeleteModal()">🗑️ Supprimer</button>
        </div>
        
        <div class="products-table">
            <table>
                <thead>
                    <tr>
                        <th style="width:50px"><div class="checkbox" id="select-all" onclick="toggleSelectAll()"></div></th>
                        <th>Produit</th>
                        <th>SKU</th>
                        <th>Balises</th>
                        <th>Prix</th>
                    </tr>
                </thead>
                <tbody id="products-list">
                    <tr><td colspan="5" class="loading"><div class="spinner"></div></td></tr>
                </tbody>
            </table>
        </div>
    </main>
    
    <div class="modal-overlay" id="add-tag-modal">
        <div class="modal">
            <h2 style="margin-bottom:20px;">Ajouter une balise</h2>
            <input type="text" id="new-tag" placeholder="Nom de la balise" style="width:100%;padding:12px;background:#0a0a0f;border:1px solid #333;border-radius:8px;color:#fff;margin-bottom:20px;">
            <div style="display:flex;gap:10px;">
                <button class="btn btn-secondary" onclick="closeModal('add-tag-modal')" style="flex:1;">Annuler</button>
                <button class="btn btn-primary" onclick="addTag()" style="flex:1;">Ajouter</button>
            </div>
        </div>
    </div>
    
    <div class="modal-overlay" id="delete-modal">
        <div class="modal">
            <h2 style="margin-bottom:20px;">⚠️ Confirmer la suppression</h2>
            <p style="color:#888;margin-bottom:20px;">Supprimer <strong id="delete-count">0</strong> produit(s) ?</p>
            <div style="display:flex;gap:10px;">
                <button class="btn btn-secondary" onclick="closeModal('delete-modal')" style="flex:1;">Annuler</button>
                <button class="btn btn-danger" onclick="deleteProducts()" style="flex:1;">Supprimer</button>
            </div>
        </div>
    </div>

    <script>
        let products = [];
        let tags = {};
        let selectedIds = new Set();
        
        async function loadData() {
            document.getElementById('products-list').innerHTML = '<tr><td colspan="5" class="loading"><div class="spinner"></div></td></tr>';
            
            const [productsRes, tagsRes] = await Promise.all([
                fetch('/api/products').then(r => r.json()),
                fetch('/api/tags').then(r => r.json())
            ]);
            
            products = productsRes.products || [];
            tags = tagsRes.tags || {};
            
            document.getElementById('total-products').textContent = products.length;
            document.getElementById('total-tags').textContent = Object.keys(tags).length;
            
            const select = document.getElementById('filter-tag');
            select.innerHTML = '<option value="">Toutes les balises</option>' +
                Object.entries(tags).sort((a,b) => b[1] - a[1]).map(([tag, count]) => 
                    `<option value="${tag}">${tag} (${count})</option>`
                ).join('');
            
            filterProducts();
        }
        
        function filterProducts() {
            const search = document.getElementById('search').value.toLowerCase();
            const tagFilter = document.getElementById('filter-tag').value;
            
            let filtered = products.filter(p => {
                const matchSearch = !search || p.title.toLowerCase().includes(search) || (p.variants?.[0]?.sku || '').toLowerCase().includes(search);
                const matchTag = !tagFilter || (p.tags || '').split(', ').includes(tagFilter);
                return matchSearch && matchTag;
            });
            
            renderProducts(filtered);
        }
        
        function renderProducts(list) {
            const tbody = document.getElementById('products-list');
            tbody.innerHTML = list.map(p => {
                const isSelected = selectedIds.has(p.id);
                const tagsHtml = (p.tags || '').split(', ').filter(t => t).slice(0, 5).map(t => `<span class="tag">${t}</span>`).join('');
                return `
                    <tr>
                        <td><div class="checkbox ${isSelected ? 'checked' : ''}" onclick="toggleProduct(${p.id})"></div></td>
                        <td>
                            <div class="product-cell">
                                <img class="product-image" src="${p.image?.src || ''}" onerror="this.style.display='none'">
                                <span>${p.title.substring(0, 50)}${p.title.length > 50 ? '...' : ''}</span>
                            </div>
                        </td>
                        <td style="font-family:monospace;font-size:12px;color:#888;">${p.variants?.[0]?.sku || 'N/A'}</td>
                        <td>${tagsHtml}</td>
                        <td>${p.variants?.[0]?.price || '0'}€</td>
                    </tr>
                `;
            }).join('');
        }
        
        function toggleProduct(id) {
            if (selectedIds.has(id)) selectedIds.delete(id);
            else selectedIds.add(id);
            updateSelection();
            filterProducts();
        }
        
        function toggleSelectAll() {
            const visible = products.filter(p => {
                const search = document.getElementById('search').value.toLowerCase();
                const tagFilter = document.getElementById('filter-tag').value;
                const matchSearch = !search || p.title.toLowerCase().includes(search);
                const matchTag = !tagFilter || (p.tags || '').includes(tagFilter);
                return matchSearch && matchTag;
            });
            
            const allSelected = visible.every(p => selectedIds.has(p.id));
            visible.forEach(p => allSelected ? selectedIds.delete(p.id) : selectedIds.add(p.id));
            updateSelection();
            filterProducts();
        }
        
        function updateSelection() {
            document.getElementById('selected-count').textContent = selectedIds.size;
            document.getElementById('select-all').classList.toggle('checked', selectedIds.size > 0);
        }
        
        function openAddTagModal() {
            if (selectedIds.size === 0) { showToast('Sélectionnez des produits', 'error'); return; }
            document.getElementById('add-tag-modal').classList.add('show');
        }
        
        function openDeleteModal() {
            if (selectedIds.size === 0) { showToast('Sélectionnez des produits', 'error'); return; }
            document.getElementById('delete-count').textContent = selectedIds.size;
            document.getElementById('delete-modal').classList.add('show');
        }
        
        function closeModal(id) {
            document.getElementById(id).classList.remove('show');
        }
        
        async function addTag() {
            const tag = document.getElementById('new-tag').value.trim();
            if (!tag) return;
            
            closeModal('add-tag-modal');
            showProgress();
            
            await fetch('/api/products/add-tags', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ product_ids: Array.from(selectedIds), tags: [tag] })
            });
            
            monitorProgress(() => {
                selectedIds.clear();
                loadData();
            });
        }
        
        async function deleteProducts() {
            closeModal('delete-modal');
            showProgress();
            
            await fetch('/api/products/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ product_ids: Array.from(selectedIds) })
            });
            
            monitorProgress(() => {
                selectedIds.clear();
                loadData();
            });
        }
        
        function showProgress() { document.getElementById('progress-bar').classList.add('show'); }
        function hideProgress() { document.getElementById('progress-bar').classList.remove('show'); }
        
        async function monitorProgress(callback) {
            const interval = setInterval(async () => {
                const prog = await fetch('/api/progress').then(r => r.json());
                const pct = prog.total > 0 ? (prog.current / prog.total * 100) : 0;
                document.getElementById('progress-fill').style.width = pct + '%';
                document.getElementById('progress-text').textContent = prog.message;
                
                if (!prog.running) {
                    clearInterval(interval);
                    hideProgress();
                    showToast('Opération terminée !', 'success');
                    callback();
                }
            }, 500);
        }
        
        function showToast(msg, type) {
            const toast = document.createElement('div');
            toast.className = 'toast ' + type;
            toast.textContent = msg;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
        
        document.getElementById('search').addEventListener('input', filterProducts);
        document.getElementById('filter-tag').addEventListener('change', filterProducts);
        
        loadData();
    </script>
</body>
</html>
'''


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
