"""
============================================
🛍️ SHOPIFY MANAGER V2 - Gestion Site + SEO + IA
============================================
"""

from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
import json
import ssl
import threading
import time
import os
import re

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
except ImportError:
    pass

app = Flask(__name__)

# ============================================
# CONFIGURATION
# ============================================
SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'
SITE_NAME = os.environ.get('SITE_NAME', 'Capet Shop')

# État des tâches en cours
task_progress = {
    'running': False,
    'current': 0,
    'total': 0,
    'message': '',
    'type': ''
}

# Tâches planifiées
scheduled_tasks = []
task_id_counter = 1

# ============================================
# API SHOPIFY
# ============================================

def shopify_request(endpoint, method='GET', data=None, retries=3):
    """Fait une requête à l'API Shopify avec retry"""
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    
    body = json.dumps(data).encode('utf-8') if data else None
    
    for attempt in range(retries):
        try:
            req = Request(url, data=body, headers=headers, method=method)
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with urlopen(req, context=context, timeout=30) as response:
                if response.status in [200, 201]:
                    return json.loads(response.read().decode('utf-8'))
                elif response.status == 204:
                    return {'success': True}
                return None
        except HTTPError as e:
            if e.code == 429:  # Rate limit
                time.sleep(2)
                continue
            print(f"Erreur API {e.code}: {e.read().decode()}")
            return None
        except Exception as e:
            print(f"Erreur: {e}")
            if attempt < retries - 1:
                time.sleep(1)
                continue
            return None
    return None


def get_all_products(include_metafields=False):
    """Récupère TOUS les produits avec pagination"""
    global task_progress
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
            
            # Pause pour éviter rate limit
            time.sleep(0.5)
        else:
            break
    
    print(f"[API] Total: {len(all_products)} produits")
    return all_products


def get_product_metafields(product_id):
    """Récupère les metafields SEO d'un produit"""
    result = shopify_request(f'products/{product_id}/metafields.json')
    if result and 'metafields' in result:
        metafields = {}
        for mf in result['metafields']:
            if mf.get('namespace') == 'global':
                if mf.get('key') == 'title_tag':
                    metafields['meta_title'] = mf.get('value', '')
                elif mf.get('key') == 'description_tag':
                    metafields['meta_description'] = mf.get('value', '')
        return metafields
    return {}


def get_products_with_seo(limit=100):
    """Récupère les produits avec leurs données SEO (metafields)"""
    products = get_all_products()
    
    # Pour la page SEO, on récupère les metafields des premiers produits
    # (pour éviter trop de requêtes API)
    for i, product in enumerate(products[:limit]):
        metafields = get_product_metafields(product['id'])
        product['seo_meta_title'] = metafields.get('meta_title', '')
        product['seo_meta_description'] = metafields.get('meta_description', '')
        
        if i % 10 == 0:
            print(f"[SEO] Récupéré metafields pour {i+1}/{min(len(products), limit)} produits...")
        
        time.sleep(0.3)  # Éviter rate limit
    
    return products


def add_tag_to_product(product_id, tag):
    """Ajoute une balise à un produit"""
    product_data = shopify_request(f'products/{product_id}.json')
    if product_data:
        current_tags = product_data['product'].get('tags', '')
        tags_list = [t.strip() for t in current_tags.split(',') if t.strip()]
        if tag not in tags_list:
            tags_list.append(tag)
        new_tags = ', '.join(tags_list)
        return shopify_request(f'products/{product_id}.json', 'PUT', {
            'product': {'id': product_id, 'tags': new_tags}
        })
    return None


def delete_product(product_id):
    """Supprime un produit"""
    url = f"https://{SHOP}/admin/api/{API_VERSION}/products/{product_id}.json"
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    req = Request(url, headers=headers, method='DELETE')
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with urlopen(req, context=context, timeout=30) as response:
            return True
    except Exception as e:
        print(f"Erreur suppression {product_id}: {e}")
        return False


def delete_products_batch(product_ids):
    """Supprime des produits avec progression"""
    global task_progress
    
    task_progress = {
        'running': True,
        'current': 0,
        'total': len(product_ids),
        'message': 'Suppression en cours...',
        'type': 'delete'
    }
    
    deleted = 0
    for i, pid in enumerate(product_ids):
        if delete_product(pid):
            deleted += 1
        
        task_progress['current'] = i + 1
        task_progress['message'] = f'Supprimé {deleted}/{i+1} produits...'
        
        # Pause entre chaque suppression pour éviter rate limit
        time.sleep(0.6)
    
    task_progress['running'] = False
    task_progress['message'] = f'Terminé ! {deleted} produits supprimés.'
    
    return deleted


def update_product_seo(product_id, seo_data):
    """Met à jour les données SEO d'un produit via metafields"""
    success = True
    
    # Mettre à jour le titre du produit si fourni
    if 'title' in seo_data:
        result = shopify_request(f'products/{product_id}.json', 'PUT', {
            'product': {'id': product_id, 'title': seo_data['title']}
        })
        if not result:
            success = False
    
    # Mettre à jour le handle si fourni
    if 'handle' in seo_data:
        result = shopify_request(f'products/{product_id}.json', 'PUT', {
            'product': {'id': product_id, 'handle': seo_data['handle']}
        })
        if not result:
            success = False
    
    # Mettre à jour la description HTML si fournie
    if 'body_html' in seo_data:
        result = shopify_request(f'products/{product_id}.json', 'PUT', {
            'product': {'id': product_id, 'body_html': seo_data['body_html']}
        })
        if not result:
            success = False
    
    # Mettre à jour le Meta Title via metafield
    if 'meta_title' in seo_data or 'metafields_global_title_tag' in seo_data:
        meta_title = seo_data.get('meta_title') or seo_data.get('metafields_global_title_tag')
        result = shopify_request(f'products/{product_id}/metafields.json', 'POST', {
            'metafield': {
                'namespace': 'global',
                'key': 'title_tag',
                'value': meta_title,
                'type': 'single_line_text_field'
            }
        })
        if not result:
            # Essayer de mettre à jour si le metafield existe déjà
            metafields = shopify_request(f'products/{product_id}/metafields.json')
            if metafields and 'metafields' in metafields:
                for mf in metafields['metafields']:
                    if mf.get('namespace') == 'global' and mf.get('key') == 'title_tag':
                        shopify_request(f'products/{product_id}/metafields/{mf["id"]}.json', 'PUT', {
                            'metafield': {'id': mf['id'], 'value': meta_title}
                        })
                        break
    
    # Mettre à jour la Meta Description via metafield
    if 'meta_description' in seo_data or 'metafields_global_description_tag' in seo_data:
        meta_desc = seo_data.get('meta_description') or seo_data.get('metafields_global_description_tag')
        result = shopify_request(f'products/{product_id}/metafields.json', 'POST', {
            'metafield': {
                'namespace': 'global',
                'key': 'description_tag',
                'value': meta_desc,
                'type': 'single_line_text_field'
            }
        })
        if not result:
            # Essayer de mettre à jour si le metafield existe déjà
            metafields = shopify_request(f'products/{product_id}/metafields.json')
            if metafields and 'metafields' in metafields:
                for mf in metafields['metafields']:
                    if mf.get('namespace') == 'global' and mf.get('key') == 'description_tag':
                        shopify_request(f'products/{product_id}/metafields/{mf["id"]}.json', 'PUT', {
                            'metafield': {'id': mf['id'], 'value': meta_desc}
                        })
                        break
    
    return success


def update_products_seo_batch(updates):
    """Met à jour le SEO de plusieurs produits avec progression"""
    global task_progress
    
    task_progress = {
        'running': True,
        'current': 0,
        'total': len(updates),
        'message': 'Mise à jour SEO en cours...',
        'type': 'seo'
    }
    
    updated = 0
    for i, update in enumerate(updates):
        product_id = update['id']
        seo_data = update['seo']
        
        if update_product_seo(product_id, seo_data):
            updated += 1
        
        task_progress['current'] = i + 1
        task_progress['message'] = f'Mis à jour {updated}/{i+1} produits...'
        
        time.sleep(0.6)
    
    task_progress['running'] = False
    task_progress['message'] = f'Terminé ! {updated} produits mis à jour.'
    
    return updated


# ============================================
# GÉNÉRATION SEO AVEC IA (via API Anthropic intégrée)
# ============================================

def generate_seo_content(product, content_type):
    """Génère du contenu SEO pour un produit"""
    
    title = product.get('title', '')
    vendor = product.get('vendor', '')
    product_type = product.get('product_type', '')
    tags = product.get('tags', '')
    
    # Extraire SKU du premier variant
    sku = ''
    if product.get('variants'):
        sku = product['variants'][0].get('sku', '')
    
    # Générer selon le type
    if content_type == 'meta_title':
        # Format: {product_name} | {site_name}
        meta_title = f"{title} | {SITE_NAME}"
        if len(meta_title) > 60:
            meta_title = f"{title[:50]}... | {SITE_NAME}"
        return meta_title
    
    elif content_type == 'meta_description':
        # Format avec SKU et bénéfices
        desc = f"Achetez la {title}"
        if sku:
            desc += f" (SKU: {sku})"
        desc += f" ✓ 100% Authentique ✓ Livraison rapide ✓ Paiement sécurisé. Disponible sur {SITE_NAME}."
        if len(desc) > 160:
            desc = desc[:157] + "..."
        return desc
    
    elif content_type == 'handle':
        # Générer un slug propre
        handle = title.lower()
        handle = re.sub(r'[^a-z0-9\s-]', '', handle)
        handle = re.sub(r'\s+', '-', handle)
        handle = re.sub(r'-+', '-', handle)
        return handle.strip('-')
    
    elif content_type == 'description_short':
        desc = f"La {title} est une pièce incontournable"
        if vendor:
            desc += f" de la collection {vendor}"
        desc += "."
        if sku:
            desc += f" Référence : {sku}."
        return desc
    
    elif content_type == 'description_long':
        desc = f"""<h2>{title}</h2>
<p>La {title} est une pièce emblématique qui combine style et qualité. """
        if vendor:
            desc += f"Créée par {vendor}, cette sneaker "
        else:
            desc += "Cette sneaker "
        desc += """s'inscrit dans la lignée des modèles les plus recherchés.</p>

<h3>Caractéristiques</h3>
<ul>
<li>Design premium et authentique</li>
<li>Matériaux de haute qualité</li>
<li>Confort optimal pour un usage quotidien</li>
</ul>
"""
        if sku:
            desc += f"\n<p><strong>SKU :</strong> {sku}</p>"
        
        desc += f"""
<h3>Pourquoi acheter sur {SITE_NAME} ?</h3>
<ul>
<li>✓ 100% Authentique - Garantie d'authenticité</li>
<li>✓ Livraison rapide et sécurisée</li>
<li>✓ Service client disponible</li>
</ul>
"""
        return desc
    
    return ''


# ============================================
# ROUTES API
# ============================================

@app.route('/api/products')
def api_get_products():
    products = get_all_products()
    return jsonify({'products': products})


@app.route('/api/products/seo')
def api_get_products_seo():
    """Récupère les produits avec leurs metafields SEO"""
    products = get_all_products()
    
    # Récupérer les metafields pour chaque produit (avec progression)
    global task_progress
    task_progress = {
        'running': True,
        'current': 0,
        'total': len(products),
        'message': 'Chargement des données SEO...',
        'type': 'load_seo'
    }
    
    for i, product in enumerate(products):
        metafields = get_product_metafields(product['id'])
        product['seo_meta_title'] = metafields.get('meta_title', '')
        product['seo_meta_description'] = metafields.get('meta_description', '')
        
        task_progress['current'] = i + 1
        task_progress['message'] = f'Chargement SEO: {i+1}/{len(products)}'
        
        time.sleep(0.2)  # Éviter rate limit
    
    task_progress['running'] = False
    task_progress['message'] = 'Chargement terminé'
    
    return jsonify({'products': products})


@app.route('/api/progress')
def api_get_progress():
    return jsonify(task_progress)


@app.route('/api/products/add-tag', methods=['POST'])
def api_add_tag():
    data = request.json
    product_ids = data.get('product_ids', [])
    tag = data.get('tag', '')
    
    global task_progress
    task_progress = {
        'running': True,
        'current': 0,
        'total': len(product_ids),
        'message': 'Ajout de balise en cours...',
        'type': 'tag'
    }
    
    count = 0
    for i, pid in enumerate(product_ids):
        if add_tag_to_product(pid, tag):
            count += 1
        task_progress['current'] = i + 1
        task_progress['message'] = f'Ajouté à {count}/{i+1} produits...'
        time.sleep(0.5)
    
    task_progress['running'] = False
    task_progress['message'] = f'Terminé ! Balise ajoutée à {count} produits.'
    
    return jsonify({'success': True, 'count': count})


@app.route('/api/products/delete', methods=['POST'])
def api_delete_products():
    data = request.json
    product_ids = data.get('product_ids', [])
    
    # Lancer en arrière-plan
    def delete_task():
        delete_products_batch(product_ids)
    
    thread = threading.Thread(target=delete_task)
    thread.start()
    
    return jsonify({'success': True, 'message': 'Suppression lancée'})


@app.route('/api/products/update-seo', methods=['POST'])
def api_update_seo():
    data = request.json
    updates = data.get('updates', [])
    
    def update_task():
        update_products_seo_batch(updates)
    
    thread = threading.Thread(target=update_task)
    thread.start()
    
    return jsonify({'success': True, 'message': 'Mise à jour SEO lancée'})


@app.route('/api/seo/generate', methods=['POST'])
def api_generate_seo():
    data = request.json
    product = data.get('product', {})
    content_type = data.get('type', 'meta_title')
    
    content = generate_seo_content(product, content_type)
    return jsonify({'content': content})


@app.route('/api/seo/generate-batch', methods=['POST'])
def api_generate_seo_batch():
    data = request.json
    product_ids = data.get('product_ids', [])
    fields = data.get('fields', ['meta_title', 'meta_description'])
    
    global task_progress
    task_progress = {
        'running': True,
        'current': 0,
        'total': len(product_ids),
        'message': 'Génération SEO en cours...',
        'type': 'generate'
    }
    
    # Récupérer tous les produits
    all_products = get_all_products()
    products_dict = {p['id']: p for p in all_products}
    
    updates = []
    for i, pid in enumerate(product_ids):
        if pid in products_dict:
            product = products_dict[pid]
            seo_data = {}
            
            if 'meta_title' in fields:
                seo_data['meta_title'] = generate_seo_content(product, 'meta_title')
            
            if 'meta_description' in fields:
                seo_data['meta_description'] = generate_seo_content(product, 'meta_description')
            
            if 'handle' in fields:
                seo_data['handle'] = generate_seo_content(product, 'handle')
            
            if 'description' in fields:
                seo_data['body_html'] = generate_seo_content(product, 'description_long')
            
            # Appliquer la mise à jour
            if update_product_seo(pid, seo_data):
                updates.append(pid)
        
        task_progress['current'] = i + 1
        task_progress['message'] = f'Généré pour {len(updates)}/{i+1} produits...'
        time.sleep(0.6)
    
    task_progress['running'] = False
    task_progress['message'] = f'Terminé ! SEO généré pour {len(updates)} produits.'
    
    return jsonify({'success': True, 'updated': len(updates)})


@app.route('/api/tasks')
def api_get_tasks():
    return jsonify({'tasks': scheduled_tasks})


@app.route('/api/tasks/schedule', methods=['POST'])
def api_schedule_task():
    global task_id_counter
    data = request.json
    task = {
        'id': task_id_counter,
        'action': data.get('action'),
        'tag': data.get('tag'),
        'scheduled_at': data.get('scheduled_at'),
        'created_at': datetime.now().isoformat()
    }
    task_id_counter += 1
    scheduled_tasks.append(task)
    return jsonify({'success': True, 'task': task})


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def api_delete_task(task_id):
    global scheduled_tasks
    scheduled_tasks = [t for t in scheduled_tasks if t['id'] != task_id]
    return jsonify({'success': True})


# ============================================
# PAGES
# ============================================

@app.route('/')
def index():
    return render_template_string(HOME_TEMPLATE)


@app.route('/site')
def site_management():
    return render_template_string(SITE_TEMPLATE)


@app.route('/seo')
def seo_management():
    return render_template_string(SEO_TEMPLATE)


# ============================================
# TEMPLATES HTML
# ============================================

HOME_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛍️ Shopify Manager</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
            min-height: 100vh;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            text-align: center;
            padding: 40px;
        }
        .logo { font-size: 64px; margin-bottom: 20px; }
        h1 { font-size: 48px; margin-bottom: 10px; }
        h1 span { color: #00ff88; }
        .subtitle { color: #888; font-size: 18px; margin-bottom: 50px; }
        .buttons { display: flex; gap: 30px; justify-content: center; flex-wrap: wrap; }
        .btn-card {
            background: #1a1a2e;
            border: 2px solid #333;
            border-radius: 20px;
            padding: 40px 50px;
            text-decoration: none;
            color: #fff;
            transition: all 0.3s;
            min-width: 250px;
        }
        .btn-card:hover {
            border-color: #00ff88;
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0,255,136,0.2);
        }
        .btn-card .icon { font-size: 48px; margin-bottom: 15px; }
        .btn-card h2 { font-size: 24px; margin-bottom: 10px; }
        .btn-card p { color: #888; font-size: 14px; }
        .status {
            margin-top: 50px;
            padding: 15px 30px;
            background: rgba(0,255,136,0.1);
            border-radius: 30px;
            display: inline-flex;
            align-items: center;
            gap: 10px;
        }
        .status-dot {
            width: 10px; height: 10px;
            background: #00ff88;
            border-radius: 50%;
            box-shadow: 0 0 10px #00ff88;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🛍️</div>
        <h1>Shopify<span>Manager</span></h1>
        <p class="subtitle">Gestion complète de ta boutique</p>
        
        <div class="buttons">
            <a href="/site" class="btn-card">
                <div class="icon">🏷️</div>
                <h2>Gestion Site</h2>
                <p>Balises, suppression, filtres</p>
            </a>
            <a href="/seo" class="btn-card">
                <div class="icon">🔍</div>
                <h2>Gestion SEO</h2>
                <p>Meta titles, descriptions, URLs</p>
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

SITE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏷️ Gestion Site | Shopify Manager</title>
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
        .logo span { color: #00ff88; }
        .status { display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: rgba(0,255,136,0.1); border-radius: 20px; font-size: 14px; }
        .status-dot { width: 8px; height: 8px; background: #00ff88; border-radius: 50%; box-shadow: 0 0 10px #00ff88; }
        
        .container { max-width: 1400px; margin: 0 auto; padding: 30px; }
        
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #1a1a2e; padding: 24px; border-radius: 12px; border: 1px solid #333; }
        .stat-label { color: #888; font-size: 13px; margin-bottom: 8px; }
        .stat-value { font-size: 32px; font-weight: bold; }
        .stat-value.green { color: #00ff88; }
        
        .controls { background: #1a1a2e; padding: 20px; border-radius: 12px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 15px; align-items: flex-end; }
        .control-group { display: flex; flex-direction: column; gap: 6px; }
        .control-group label { font-size: 12px; color: #888; text-transform: uppercase; }
        
        input, select { padding: 12px 16px; background: #0a0a0f; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 14px; min-width: 180px; }
        input:focus, select:focus { outline: none; border-color: #00ff88; }
        
        .btn { padding: 12px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; transition: all 0.2s; }
        .btn-primary { background: linear-gradient(135deg, #00ff88, #00cc6a); color: #000; }
        .btn-danger { background: #ff4757; color: #fff; }
        .btn-secondary { background: #333; color: #fff; }
        .btn:hover { transform: translateY(-1px); opacity: 0.9; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        
        .selected-info { padding: 8px 16px; background: #0a0a0f; border-radius: 8px; font-size: 13px; color: #888; }
        .selected-info strong { color: #00ff88; }
        
        .products-table { background: #1a1a2e; border-radius: 12px; overflow: hidden; border: 1px solid #333; }
        .table-header { display: grid; grid-template-columns: 50px 70px 1fr 250px 100px; gap: 16px; padding: 16px 24px; background: #0a0a0f; font-size: 12px; text-transform: uppercase; color: #888; font-weight: 600; }
        .table-row { display: grid; grid-template-columns: 50px 70px 1fr 250px 100px; gap: 16px; padding: 16px 24px; border-bottom: 1px solid #2a2a3a; align-items: center; transition: background 0.2s; }
        .table-row:hover { background: rgba(255,255,255,0.02); }
        
        .checkbox { width: 22px; height: 22px; border: 2px solid #444; border-radius: 5px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
        .checkbox:hover { border-color: #00ff88; }
        .checkbox.checked { background: #00ff88; border-color: #00ff88; }
        .checkbox.checked::after { content: '✓'; color: #000; font-size: 14px; font-weight: bold; }
        
        .product-image { width: 50px; height: 50px; background: #333; border-radius: 8px; object-fit: cover; }
        .product-title { font-weight: 500; margin-bottom: 4px; }
        .product-vendor { font-size: 13px; color: #666; }
        
        .tags { display: flex; flex-wrap: wrap; gap: 6px; }
        .tag { padding: 4px 10px; background: #0a0a0f; border: 1px solid #333; border-radius: 6px; font-size: 12px; color: #888; }
        .tag.highlight { background: rgba(0,255,136,0.15); border-color: #00ff88; color: #00ff88; }
        .no-tags { color: #555; font-style: italic; font-size: 13px; }
        .price { font-family: 'SF Mono', Monaco, monospace; font-weight: 500; color: #00ff88; }
        
        .empty-state { text-align: center; padding: 60px; color: #666; }
        .empty-state .icon { font-size: 48px; margin-bottom: 16px; }
        .empty-state h3 { color: #fff; margin-bottom: 8px; }
        
        .loading { text-align: center; padding: 60px; }
        .spinner { width: 40px; height: 40px; border: 3px solid #333; border-top-color: #00ff88; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .progress-bar { position: fixed; top: 0; left: 0; right: 0; background: #1a1a2e; padding: 20px; z-index: 1000; border-bottom: 1px solid #333; display: none; }
        .progress-bar.show { display: block; }
        .progress-bar h3 { margin-bottom: 10px; }
        .progress-track { height: 10px; background: #333; border-radius: 5px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #00ff88, #00cc6a); transition: width 0.3s; }
        .progress-text { margin-top: 10px; font-size: 14px; color: #888; }
        
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.85); display: none; align-items: center; justify-content: center; z-index: 1000; }
        .modal-overlay.show { display: flex; }
        .modal { background: #1a1a2e; padding: 32px; border-radius: 16px; width: 100%; max-width: 450px; border: 1px solid #333; }
        .modal h2 { margin-bottom: 24px; display: flex; align-items: center; gap: 12px; }
        .modal .control-group { margin-bottom: 20px; }
        .modal input, .modal select { width: 100%; }
        .modal-actions { display: flex; gap: 12px; margin-top: 28px; }
        .modal-actions .btn { flex: 1; justify-content: center; }
        
        .toast { position: fixed; bottom: 24px; right: 24px; padding: 16px 24px; border-radius: 10px; font-weight: 500; z-index: 2000; animation: slideIn 0.3s ease; }
        .toast.success { background: #00ff88; color: #000; }
        .toast.error { background: #ff4757; color: #fff; }
        @keyframes slideIn { from { opacity: 0; transform: translateX(100px); } to { opacity: 1; transform: translateX(0); } }
    </style>
</head>
<body>
    <div class="progress-bar" id="progress-bar">
        <h3 id="progress-title">⏳ Traitement en cours...</h3>
        <div class="progress-track">
            <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
        </div>
        <p class="progress-text" id="progress-text">Initialisation...</p>
    </div>

    <header class="header">
        <div class="header-left">
            <a href="/" class="back-btn">← Retour</a>
            <div class="logo">🏷️ Gestion <span>Site</span></div>
        </div>
        <div class="status">
            <div class="status-dot"></div>
            Connecté
        </div>
    </header>
    
    <main class="container">
        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Total produits</div>
                <div class="stat-value" id="total-products">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Produits filtrés</div>
                <div class="stat-value green" id="filtered-products">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Sélectionnés</div>
                <div class="stat-value" id="selected-products">0</div>
            </div>
        </div>
        
        <div class="controls">
            <div class="control-group">
                <label>Rechercher par balise</label>
                <input type="text" id="search-tag" placeholder="Entrez une balise...">
            </div>
            <div class="control-group">
                <label>Filtrer</label>
                <select id="filter-mode">
                    <option value="all">Tous les produits</option>
                    <option value="with">Avec cette balise</option>
                    <option value="without">Sans cette balise</option>
                </select>
            </div>
            <button class="btn btn-secondary" onclick="loadProducts()">🔄 Actualiser</button>
        </div>
        
        <div class="controls">
            <div class="control-group">
                <label>Nouvelle balise</label>
                <input type="text" id="new-tag" placeholder="Nom de la balise...">
            </div>
            <button class="btn btn-primary" onclick="addTagToSelected()">🏷️ Ajouter balise</button>
            <button class="btn btn-danger" onclick="deleteSelected()">🗑️ Supprimer</button>
            <button class="btn btn-secondary" onclick="openScheduler()">📅 Planifier</button>
            <div class="selected-info">
                <strong id="selection-count">0</strong> sélectionné(s)
            </div>
        </div>
        
        <div class="products-table">
            <div class="table-header">
                <div class="checkbox" id="select-all" onclick="toggleSelectAll()"></div>
                <div>Image</div>
                <div>Produit</div>
                <div>Balises</div>
                <div>Prix</div>
            </div>
            <div id="products-list">
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Chargement des produits...</p>
                </div>
            </div>
        </div>
    </main>
    
    <div class="modal-overlay" id="scheduler-modal">
        <div class="modal">
            <h2>📅 Planifier une tâche</h2>
            <div class="control-group">
                <label>Action</label>
                <select id="schedule-action">
                    <option value="delete-without-tag">Supprimer produits sans balise</option>
                    <option value="add-tag-all">Ajouter balise à tous les produits</option>
                </select>
            </div>
            <div class="control-group">
                <label>Balise concernée</label>
                <input type="text" id="schedule-tag" placeholder="Nom de la balise">
            </div>
            <div class="control-group">
                <label>Date</label>
                <input type="date" id="schedule-date">
            </div>
            <div class="control-group">
                <label>Heure</label>
                <input type="time" id="schedule-time">
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeScheduler()">Annuler</button>
                <button class="btn btn-primary" onclick="scheduleTask()">Planifier</button>
            </div>
        </div>
    </div>
    
    <script>
        let products = [];
        let filteredProducts = [];
        let selectedIds = new Set();
        let progressInterval = null;
        
        document.addEventListener('DOMContentLoaded', () => {
            loadProducts();
            document.getElementById('search-tag').addEventListener('input', filterProducts);
            document.getElementById('filter-mode').addEventListener('change', filterProducts);
        });
        
        async function loadProducts() {
            document.getElementById('products-list').innerHTML = '<div class="loading"><div class="spinner"></div><p>Chargement des produits...</p></div>';
            
            try {
                const response = await fetch('/api/products');
                const data = await response.json();
                products = data.products || [];
                filterProducts();
                document.getElementById('total-products').textContent = products.length;
            } catch (error) {
                document.getElementById('products-list').innerHTML = '<div class="empty-state"><div class="icon">❌</div><h3>Erreur de chargement</h3></div>';
            }
        }
        
        function filterProducts() {
            const searchTag = document.getElementById('search-tag').value.toLowerCase();
            const filterMode = document.getElementById('filter-mode').value;
            
            if (filterMode === 'all' || !searchTag) {
                filteredProducts = products;
            } else if (filterMode === 'with') {
                filteredProducts = products.filter(p => (p.tags || '').toLowerCase().includes(searchTag));
            } else if (filterMode === 'without') {
                filteredProducts = products.filter(p => !(p.tags || '').toLowerCase().includes(searchTag));
            }
            
            document.getElementById('filtered-products').textContent = filteredProducts.length;
            renderProducts();
        }
        
        function renderProducts() {
            const container = document.getElementById('products-list');
            const searchTag = document.getElementById('search-tag').value.toLowerCase();
            
            if (filteredProducts.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="icon">📭</div><h3>Aucun produit trouvé</h3></div>';
                return;
            }
            
            container.innerHTML = filteredProducts.map(product => {
                const isSelected = selectedIds.has(product.id);
                const tags = product.tags ? product.tags.split(', ').filter(t => t) : [];
                const imageUrl = product.image?.src || product.images?.[0]?.src || '';
                const price = product.variants?.[0]?.price || '0.00';
                
                return `
                    <div class="table-row">
                        <div class="checkbox ${isSelected ? 'checked' : ''}" onclick="toggleProduct(${product.id})"></div>
                        <img class="product-image" src="${imageUrl}" alt="" onerror="this.style.display='none'">
                        <div>
                            <div class="product-title">${product.title}</div>
                            <div class="product-vendor">${product.vendor || ''}</div>
                        </div>
                        <div class="tags">
                            ${tags.length > 0 
                                ? tags.map(tag => `<span class="tag ${searchTag && tag.toLowerCase().includes(searchTag) ? 'highlight' : ''}">${tag}</span>`).join('')
                                : '<span class="no-tags">Aucune balise</span>'}
                        </div>
                        <div class="price">${price} €</div>
                    </div>
                `;
            }).join('');
            
            updateSelectionUI();
        }
        
        function toggleProduct(id) {
            if (selectedIds.has(id)) selectedIds.delete(id);
            else selectedIds.add(id);
            renderProducts();
        }
        
        function toggleSelectAll() {
            if (selectedIds.size === filteredProducts.length) selectedIds.clear();
            else filteredProducts.forEach(p => selectedIds.add(p.id));
            renderProducts();
        }
        
        function updateSelectionUI() {
            document.getElementById('selected-products').textContent = selectedIds.size;
            document.getElementById('selection-count').textContent = selectedIds.size;
            const selectAll = document.getElementById('select-all');
            if (selectedIds.size === filteredProducts.length && filteredProducts.length > 0) selectAll.classList.add('checked');
            else selectAll.classList.remove('checked');
        }
        
        function startProgressMonitor() {
            document.getElementById('progress-bar').classList.add('show');
            progressInterval = setInterval(async () => {
                try {
                    const response = await fetch('/api/progress');
                    const data = await response.json();
                    
                    const percent = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
                    document.getElementById('progress-fill').style.width = percent + '%';
                    document.getElementById('progress-text').textContent = data.message;
                    
                    if (!data.running) {
                        clearInterval(progressInterval);
                        setTimeout(() => {
                            document.getElementById('progress-bar').classList.remove('show');
                            loadProducts();
                            showToast(data.message, 'success');
                        }, 1000);
                    }
                } catch (e) {}
            }, 500);
        }
        
        async function addTagToSelected() {
            const tag = document.getElementById('new-tag').value.trim();
            if (!tag) return showToast('Entrez une balise', 'error');
            if (selectedIds.size === 0) return showToast('Sélectionnez des produits', 'error');
            
            try {
                fetch('/api/products/add-tag', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product_ids: Array.from(selectedIds), tag })
                });
                startProgressMonitor();
                document.getElementById('new-tag').value = '';
                selectedIds.clear();
            } catch (error) {
                showToast('Erreur: ' + error.message, 'error');
            }
        }
        
        async function deleteSelected() {
            if (selectedIds.size === 0) return showToast('Sélectionnez des produits', 'error');
            if (!confirm(`Supprimer ${selectedIds.size} produit(s) ? Cette action est irréversible.`)) return;
            
            try {
                fetch('/api/products/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product_ids: Array.from(selectedIds) })
                });
                startProgressMonitor();
                selectedIds.clear();
            } catch (error) {
                showToast('Erreur: ' + error.message, 'error');
            }
        }
        
        function openScheduler() { document.getElementById('scheduler-modal').classList.add('show'); }
        function closeScheduler() { document.getElementById('scheduler-modal').classList.remove('show'); }
        
        async function scheduleTask() {
            const action = document.getElementById('schedule-action').value;
            const tag = document.getElementById('schedule-tag').value.trim();
            const date = document.getElementById('schedule-date').value;
            const time = document.getElementById('schedule-time').value;
            
            if (!tag || !date || !time) return showToast('Remplissez tous les champs', 'error');
            
            try {
                await fetch('/api/tasks/schedule', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, tag, scheduled_at: `${date}T${time}:00` })
                });
                showToast('Tâche planifiée !', 'success');
                closeScheduler();
            } catch (error) {
                showToast('Erreur', 'error');
            }
        }
        
        function showToast(message, type) {
            const existing = document.querySelector('.toast');
            if (existing) existing.remove();
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 4000);
        }
    </script>
</body>
</html>
'''

SEO_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔍 Gestion SEO | Shopify Manager</title>
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
        .back-btn { padding: 10px 20px; background: #333; border: none; border-radius: 8px; color: #fff; text-decoration: none; font-size: 14px; }
        .back-btn:hover { background: #444; }
        .logo { font-size: 20px; font-weight: bold; }
        .logo span { color: #00ff88; }
        
        .container { max-width: 1600px; margin: 0 auto; padding: 30px; }
        
        .controls { background: #1a1a2e; padding: 20px; border-radius: 12px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 15px; align-items: flex-end; }
        .control-group { display: flex; flex-direction: column; gap: 6px; }
        .control-group label { font-size: 12px; color: #888; text-transform: uppercase; }
        
        input, select { padding: 12px 16px; background: #0a0a0f; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 14px; min-width: 180px; }
        input:focus, select:focus { outline: none; border-color: #00ff88; }
        
        .btn { padding: 12px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; transition: all 0.2s; }
        .btn-primary { background: linear-gradient(135deg, #00ff88, #00cc6a); color: #000; }
        .btn-ai { background: linear-gradient(135deg, #8b5cf6, #6d28d9); color: #fff; }
        .btn-secondary { background: #333; color: #fff; }
        .btn:hover { transform: translateY(-1px); opacity: 0.9; }
        
        .selected-info { padding: 8px 16px; background: #0a0a0f; border-radius: 8px; font-size: 13px; color: #888; }
        .selected-info strong { color: #00ff88; }
        
        .seo-table { background: #1a1a2e; border-radius: 12px; overflow-x: auto; border: 1px solid #333; }
        .seo-table table { width: 100%; border-collapse: collapse; min-width: 1200px; }
        .seo-table th { padding: 16px; background: #0a0a0f; font-size: 12px; text-transform: uppercase; color: #888; font-weight: 600; text-align: left; position: sticky; top: 0; }
        .seo-table td { padding: 12px 16px; border-bottom: 1px solid #2a2a3a; vertical-align: top; }
        .seo-table tr:hover { background: rgba(255,255,255,0.02); }
        
        .checkbox { width: 22px; height: 22px; border: 2px solid #444; border-radius: 5px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .checkbox.checked { background: #00ff88; border-color: #00ff88; }
        .checkbox.checked::after { content: '✓'; color: #000; font-size: 14px; font-weight: bold; }
        
        .product-cell { display: flex; align-items: center; gap: 12px; }
        .product-image { width: 40px; height: 40px; border-radius: 6px; object-fit: cover; background: #333; }
        .product-title { font-weight: 500; font-size: 13px; }
        .product-sku { font-size: 11px; color: #666; font-family: monospace; }
        
        .seo-field { font-size: 12px; max-width: 250px; }
        .seo-field.missing { color: #ff4757; font-style: italic; }
        .seo-field.ok { color: #888; }
        .seo-field.long { color: #ffa502; }
        
        .char-count { font-size: 10px; color: #666; }
        .char-count.warning { color: #ffa502; }
        .char-count.error { color: #ff4757; }
        
        .progress-bar { position: fixed; top: 0; left: 0; right: 0; background: #1a1a2e; padding: 20px; z-index: 1000; border-bottom: 1px solid #333; display: none; }
        .progress-bar.show { display: block; }
        .progress-track { height: 10px; background: #333; border-radius: 5px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #8b5cf6, #6d28d9); transition: width 0.3s; }
        .progress-text { margin-top: 10px; font-size: 14px; color: #888; }
        
        .loading { text-align: center; padding: 60px; }
        .spinner { width: 40px; height: 40px; border: 3px solid #333; border-top-color: #00ff88; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.85); display: none; align-items: center; justify-content: center; z-index: 1000; }
        .modal-overlay.show { display: flex; }
        .modal { background: #1a1a2e; padding: 32px; border-radius: 16px; width: 100%; max-width: 600px; border: 1px solid #333; max-height: 90vh; overflow-y: auto; }
        .modal h2 { margin-bottom: 24px; }
        .modal .control-group { margin-bottom: 20px; }
        .modal input, .modal select, .modal textarea { width: 100%; }
        .modal textarea { min-height: 100px; resize: vertical; font-family: inherit; }
        .modal-actions { display: flex; gap: 12px; margin-top: 28px; }
        .modal-actions .btn { flex: 1; justify-content: center; }
        
        .checkbox-group { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }
        .checkbox-label { display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: #0a0a0f; border: 1px solid #333; border-radius: 8px; cursor: pointer; }
        .checkbox-label input { display: none; }
        .checkbox-label.checked { border-color: #00ff88; background: rgba(0,255,136,0.1); }
        
        .toast { position: fixed; bottom: 24px; right: 24px; padding: 16px 24px; border-radius: 10px; font-weight: 500; z-index: 2000; animation: slideIn 0.3s ease; }
        .toast.success { background: #00ff88; color: #000; }
        .toast.error { background: #ff4757; color: #fff; }
        @keyframes slideIn { from { opacity: 0; transform: translateX(100px); } to { opacity: 1; transform: translateX(0); } }
    </style>
</head>
<body>
    <div class="progress-bar" id="progress-bar">
        <h3>🤖 Génération SEO en cours...</h3>
        <div class="progress-track">
            <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
        </div>
        <p class="progress-text" id="progress-text">Initialisation...</p>
    </div>

    <header class="header">
        <div class="header-left">
            <a href="/" class="back-btn">← Retour</a>
            <div class="logo">🔍 Gestion <span>SEO</span></div>
        </div>
    </header>
    
    <main class="container">
        <div class="controls">
            <div class="control-group">
                <label>Rechercher</label>
                <input type="text" id="search" placeholder="Nom, SKU...">
            </div>
            <div class="control-group">
                <label>Filtrer par statut SEO</label>
                <select id="filter-seo">
                    <option value="all">Tous</option>
                    <option value="missing-meta">Sans Meta Title</option>
                    <option value="missing-desc">Sans Meta Description</option>
                    <option value="missing-both">Sans les deux</option>
                </select>
            </div>
            <button class="btn btn-secondary" onclick="loadProducts()">🔄 Actualiser</button>
            <button class="btn btn-ai" onclick="openGenerateModal()">🤖 Générer SEO avec IA</button>
            <div class="selected-info">
                <strong id="selection-count">0</strong> sélectionné(s)
            </div>
        </div>
        
        <div class="seo-table">
            <table>
                <thead>
                    <tr>
                        <th style="width:50px"><div class="checkbox" id="select-all" onclick="toggleSelectAll()"></div></th>
                        <th style="width:200px">Produit</th>
                        <th style="width:250px">Meta Title</th>
                        <th style="width:300px">Meta Description</th>
                        <th style="width:150px">Handle (URL)</th>
                        <th style="width:100px">Actions</th>
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
            <h2>🤖 Générer le SEO avec IA</h2>
            <p style="color:#888;margin-bottom:20px;">Sélectionnez les champs à générer pour les <strong id="modal-count">0</strong> produits sélectionnés.</p>
            
            <div class="control-group">
                <label>Champs à générer</label>
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
                    <label class="checkbox-label" data-field="description">
                        <input type="checkbox"> Description longue
                    </label>
                </div>
            </div>
            
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeGenerateModal()">Annuler</button>
                <button class="btn btn-ai" onclick="generateSEO()">🚀 Générer</button>
            </div>
        </div>
    </div>
    
    <div class="modal-overlay" id="edit-modal">
        <div class="modal">
            <h2>✏️ Modifier SEO</h2>
            <input type="hidden" id="edit-product-id">
            
            <div class="control-group">
                <label>Meta Title (max 60 car.)</label>
                <input type="text" id="edit-meta-title" maxlength="70">
                <span class="char-count" id="title-count">0/60</span>
            </div>
            
            <div class="control-group">
                <label>Meta Description (max 160 car.)</label>
                <textarea id="edit-meta-desc" maxlength="170"></textarea>
                <span class="char-count" id="desc-count">0/160</span>
            </div>
            
            <div class="control-group">
                <label>Handle (URL)</label>
                <input type="text" id="edit-handle">
            </div>
            
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeEditModal()">Annuler</button>
                <button class="btn btn-primary" onclick="saveProductSEO()">💾 Sauvegarder</button>
            </div>
        </div>
    </div>
    
    <script>
        let products = [];
        let filteredProducts = [];
        let selectedIds = new Set();
        let progressInterval = null;
        
        document.addEventListener('DOMContentLoaded', () => {
            loadProducts();
            document.getElementById('search').addEventListener('input', filterProducts);
            document.getElementById('filter-seo').addEventListener('change', filterProducts);
            
            document.getElementById('edit-meta-title').addEventListener('input', updateCharCount);
            document.getElementById('edit-meta-desc').addEventListener('input', updateCharCount);
            
            document.querySelectorAll('.checkbox-label').forEach(label => {
                label.addEventListener('click', () => label.classList.toggle('checked'));
            });
        });
        
        function updateCharCount() {
            const titleLen = document.getElementById('edit-meta-title').value.length;
            const descLen = document.getElementById('edit-meta-desc').value.length;
            
            const titleCount = document.getElementById('title-count');
            titleCount.textContent = `${titleLen}/60`;
            titleCount.className = 'char-count' + (titleLen > 60 ? ' error' : titleLen > 50 ? ' warning' : '');
            
            const descCount = document.getElementById('desc-count');
            descCount.textContent = `${descLen}/160`;
            descCount.className = 'char-count' + (descLen > 160 ? ' error' : descLen > 140 ? ' warning' : '');
        }
        
        async function loadProducts() {
            document.getElementById('products-list').innerHTML = '<tr><td colspan="6" class="loading"><div class="spinner"></div><p>Chargement des produits et données SEO...<br><small>Cela peut prendre quelques minutes</small></p></td></tr>';
            
            try {
                const response = await fetch('/api/products/seo');
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
                const matchSearch = !search || 
                    p.title.toLowerCase().includes(search) ||
                    (p.variants?.[0]?.sku || '').toLowerCase().includes(search);
                
                if (!matchSearch) return false;
                
                const metaTitle = p.seo_meta_title || '';
                const metaDesc = p.seo_meta_description || '';
                
                if (filter === 'missing-meta') return !metaTitle;
                if (filter === 'missing-desc') return !metaDesc;
                if (filter === 'missing-both') return !metaTitle && !metaDesc;
                
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
                const sku = p.variants?.[0]?.sku || '';
                const metaTitle = p.seo_meta_title || '';
                const metaDesc = p.seo_meta_description || '';
                const handle = p.handle || '';
                
                const titleClass = !metaTitle ? 'missing' : metaTitle.length > 60 ? 'long' : 'ok';
                const descClass = !metaDesc ? 'missing' : metaDesc.length > 160 ? 'long' : 'ok';
                
                return `
                    <tr>
                        <td><div class="checkbox ${isSelected ? 'checked' : ''}" onclick="toggleProduct(${p.id})"></div></td>
                        <td>
                            <div class="product-cell">
                                <img class="product-image" src="${imageUrl}" onerror="this.style.display='none'">
                                <div>
                                    <div class="product-title">${p.title.substring(0, 40)}${p.title.length > 40 ? '...' : ''}</div>
                                    <div class="product-sku">${sku}</div>
                                </div>
                            </div>
                        </td>
                        <td>
                            <div class="seo-field ${titleClass}">${metaTitle || '⚠️ Non défini'}</div>
                            ${metaTitle ? `<div class="char-count ${metaTitle.length > 60 ? 'error' : ''}">${metaTitle.length}/60</div>` : ''}
                        </td>
                        <td>
                            <div class="seo-field ${descClass}">${metaDesc ? metaDesc.substring(0, 80) + '...' : '⚠️ Non défini'}</div>
                            ${metaDesc ? `<div class="char-count ${metaDesc.length > 160 ? 'error' : ''}">${metaDesc.length}/160</div>` : ''}
                        </td>
                        <td><div class="seo-field ok">/products/${handle}</div></td>
                        <td><button class="btn btn-secondary" style="padding:8px 12px;font-size:12px;" onclick='openEditModal(${JSON.stringify(p).replace(/'/g, "\\'")})'>✏️</button></td>
                    </tr>
                `;
            }).join('');
            
            updateSelectionUI();
        }
        
        function toggleProduct(id) {
            if (selectedIds.has(id)) selectedIds.delete(id);
            else selectedIds.add(id);
            renderProducts();
        }
        
        function toggleSelectAll() {
            if (selectedIds.size === filteredProducts.length) selectedIds.clear();
            else filteredProducts.forEach(p => selectedIds.add(p.id));
            renderProducts();
        }
        
        function updateSelectionUI() {
            document.getElementById('selection-count').textContent = selectedIds.size;
            const selectAll = document.getElementById('select-all');
            if (selectedIds.size === filteredProducts.length && filteredProducts.length > 0) selectAll.classList.add('checked');
            else selectAll.classList.remove('checked');
        }
        
        function openGenerateModal() {
            if (selectedIds.size === 0) return showToast('Sélectionnez des produits', 'error');
            document.getElementById('modal-count').textContent = selectedIds.size;
            document.getElementById('generate-modal').classList.add('show');
        }
        
        function closeGenerateModal() {
            document.getElementById('generate-modal').classList.remove('show');
        }
        
        async function generateSEO() {
            const fields = [];
            document.querySelectorAll('.checkbox-label.checked').forEach(label => {
                fields.push(label.dataset.field);
            });
            
            if (fields.length === 0) return showToast('Sélectionnez au moins un champ', 'error');
            
            closeGenerateModal();
            document.getElementById('progress-bar').classList.add('show');
            
            try {
                fetch('/api/seo/generate-batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product_ids: Array.from(selectedIds), fields })
                });
                
                progressInterval = setInterval(async () => {
                    const response = await fetch('/api/progress');
                    const data = await response.json();
                    
                    const percent = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
                    document.getElementById('progress-fill').style.width = percent + '%';
                    document.getElementById('progress-text').textContent = data.message;
                    
                    if (!data.running) {
                        clearInterval(progressInterval);
                        setTimeout(() => {
                            document.getElementById('progress-bar').classList.remove('show');
                            loadProducts();
                            showToast(data.message, 'success');
                        }, 1000);
                    }
                }, 500);
                
                selectedIds.clear();
            } catch (error) {
                showToast('Erreur', 'error');
            }
        }
        
        function openEditModal(product) {
            document.getElementById('edit-product-id').value = product.id;
            document.getElementById('edit-meta-title').value = product.seo_meta_title || '';
            document.getElementById('edit-meta-desc').value = product.seo_meta_description || '';
            document.getElementById('edit-handle').value = product.handle || '';
            updateCharCount();
            document.getElementById('edit-modal').classList.add('show');
        }
        
        function closeEditModal() {
            document.getElementById('edit-modal').classList.remove('show');
        }
        
        async function saveProductSEO() {
            const productId = document.getElementById('edit-product-id').value;
            const updates = [{
                id: parseInt(productId),
                seo: {
                    meta_title: document.getElementById('edit-meta-title').value,
                    meta_description: document.getElementById('edit-meta-desc').value,
                    handle: document.getElementById('edit-handle').value
                }
            }];
            
            try {
                await fetch('/api/products/update-seo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ updates })
                });
                showToast('SEO mis à jour !', 'success');
                closeEditModal();
                loadProducts();
            } catch (error) {
                showToast('Erreur', 'error');
            }
        }
        
        function showToast(message, type) {
            const existing = document.querySelector('.toast');
            if (existing) existing.remove();
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 4000);
        }
    </script>
</body>
</html>
'''

# ============================================
# PLANIFICATEUR
# ============================================

def run_scheduled_task(task):
    global scheduled_tasks
    print(f"[TÂCHE] Exécution: {task['action']} pour balise '{task['tag']}'")
    
    if task['action'] == 'delete-without-tag':
        products = get_all_products()
        to_delete = [p['id'] for p in products if task['tag'].lower() not in (p.get('tags', '') or '').lower()]
        delete_products_batch(to_delete)
    
    elif task['action'] == 'add-tag-all':
        products = get_all_products()
        for p in products:
            add_tag_to_product(p['id'], task['tag'])
            time.sleep(0.5)
    
    scheduled_tasks = [t for t in scheduled_tasks if t['id'] != task['id']]


def schedule_checker():
    while True:
        now = datetime.now()
        for task in scheduled_tasks[:]:
            try:
                task_time = datetime.fromisoformat(task['scheduled_at'].replace('Z', ''))
                if now >= task_time:
                    thread = threading.Thread(target=run_scheduled_task, args=(task,))
                    thread.start()
            except Exception as e:
                print(f"Erreur tâche: {e}")
        time.sleep(30)


checker_thread = threading.Thread(target=schedule_checker, daemon=True)
checker_thread.start()

# ============================================
# DÉMARRAGE
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'''
╔════════════════════════════════════════════════════════════╗
║   🛍️  SHOPIFY MANAGER V2                                   ║
║   Serveur démarré sur http://localhost:{port}               ║
╚════════════════════════════════════════════════════════════╝
    ''')
    app.run(host='0.0.0.0', port=port, debug=False)
