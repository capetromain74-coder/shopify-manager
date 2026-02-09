"""
============================================
🛍️ SHOPIFY PRODUCT MANAGER - Version Render
============================================
"""

from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
import json
import ssl
import threading
import time
import os

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
except ImportError:
    pass

app = Flask(__name__)

# ============================================
# TES IDENTIFIANTS SHOPIFY (via variables d'environnement)
# ============================================
SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'

# Tâches planifiées
scheduled_tasks = []
task_id_counter = 1

# ============================================
# FONCTIONS API SHOPIFY
# ============================================

def shopify_request(endpoint, method='GET', data=None):
    """Fait une requête à l'API Shopify"""
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    
    body = json.dumps(data).encode('utf-8') if data else None
    req = Request(url, data=body, headers=headers, method=method)
    
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    
    try:
        with urlopen(req, context=context) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
            return None
    except HTTPError as e:
        print(f"Erreur API: {e.code} - {e.read().decode()}")
        return None
    except Exception as e:
        print(f"Erreur: {e}")
        return None


def get_all_products():
    """Récupère tous les produits (avec pagination)"""
    all_products = []
    endpoint = 'products.json?limit=250'
    
    while endpoint:
        result = shopify_request(endpoint)
        if result and 'products' in result:
            all_products.extend(result['products'])
            
            # Vérifier s'il y a une page suivante via le lien "next"
            # Shopify utilise cursor-based pagination
            if len(result['products']) == 250:
                # Récupérer le dernier ID pour la pagination
                last_id = result['products'][-1]['id']
                endpoint = f'products.json?limit=250&since_id={last_id}'
            else:
                endpoint = None
        else:
            break
    
    return all_products


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


def remove_tag_from_product(product_id, tag):
    """Supprime une balise d'un produit"""
    product_data = shopify_request(f'products/{product_id}.json')
    if product_data:
        current_tags = product_data['product'].get('tags', '')
        tags_list = [t.strip() for t in current_tags.split(',') if t.strip() and t.strip() != tag]
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
        with urlopen(req, context=context) as response:
            return True
    except:
        return False


# ============================================
# PLANIFICATEUR DE TÂCHES
# ============================================

def run_scheduled_task(task):
    """Exécute une tâche planifiée"""
    global scheduled_tasks
    
    print(f"[TÂCHE] Exécution: {task['action']} pour balise '{task['tag']}'")
    
    if task['action'] == 'delete-without-tag':
        products = get_all_products()
        count = 0
        for p in products:
            tags = p.get('tags', '').lower()
            if task['tag'].lower() not in tags:
                if delete_product(p['id']):
                    count += 1
                    print(f"  Supprimé: {p['title']}")
        print(f"[TÂCHE] Terminé: {count} produits supprimés")
    
    elif task['action'] == 'add-tag-all':
        products = get_all_products()
        count = 0
        for p in products:
            if add_tag_to_product(p['id'], task['tag']):
                count += 1
        print(f"[TÂCHE] Terminé: balise ajoutée à {count} produits")
    
    scheduled_tasks = [t for t in scheduled_tasks if t['id'] != task['id']]


def schedule_checker():
    """Vérifie les tâches planifiées toutes les 30 secondes"""
    while True:
        now = datetime.now()
        for task in scheduled_tasks[:]:
            try:
                task_time = datetime.fromisoformat(task['scheduled_at'].replace('Z', ''))
                if now >= task_time:
                    run_scheduled_task(task)
            except Exception as e:
                print(f"Erreur tâche: {e}")
        time.sleep(30)


# Démarrer le vérificateur
checker_thread = threading.Thread(target=schedule_checker, daemon=True)
checker_thread.start()


# ============================================
# ROUTES API
# ============================================

@app.route('/api/products')
def api_get_products():
    products = get_all_products()
    return jsonify({'products': products})


@app.route('/api/products/add-tag', methods=['POST'])
def api_add_tag():
    data = request.json
    product_ids = data.get('product_ids', [])
    tag = data.get('tag', '')
    count = 0
    for pid in product_ids:
        if add_tag_to_product(pid, tag):
            count += 1
    return jsonify({'success': True, 'count': count})


@app.route('/api/products/remove-tag', methods=['POST'])
def api_remove_tag():
    data = request.json
    product_ids = data.get('product_ids', [])
    tag = data.get('tag', '')
    count = 0
    for pid in product_ids:
        if remove_tag_from_product(pid, tag):
            count += 1
    return jsonify({'success': True, 'count': count})


@app.route('/api/products/delete', methods=['POST'])
def api_delete_products():
    data = request.json
    product_ids = data.get('product_ids', [])
    count = 0
    for pid in product_ids:
        if delete_product(pid):
            count += 1
    return jsonify({'success': True, 'count': count})


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
# PAGE PRINCIPALE
# ============================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


HTML_TEMPLATE = '''
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
        }
        
        .header {
            padding: 20px 40px;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(0,0,0,0.3);
        }
        
        .logo { font-size: 24px; font-weight: bold; }
        .logo span { color: #00ff88; }
        
        .status {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: rgba(0,255,136,0.1);
            border-radius: 20px;
            font-size: 14px;
        }
        
        .status-dot {
            width: 8px; height: 8px;
            background: #00ff88;
            border-radius: 50%;
            box-shadow: 0 0 10px #00ff88;
        }
        
        .container { max-width: 1400px; margin: 0 auto; padding: 30px; }
        
        .tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 30px;
            background: #1a1a2e;
            padding: 4px;
            border-radius: 10px;
            width: fit-content;
        }
        
        .tab {
            padding: 12px 24px;
            border: none;
            background: transparent;
            color: #888;
            cursor: pointer;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .tab.active { background: #00ff88; color: #000; }
        .tab:hover:not(.active) { color: #fff; }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: #1a1a2e;
            padding: 24px;
            border-radius: 12px;
            border: 1px solid #333;
        }
        
        .stat-label { color: #888; font-size: 13px; margin-bottom: 8px; }
        .stat-value { font-size: 32px; font-weight: bold; }
        .stat-value.green { color: #00ff88; }
        
        .controls {
            background: #1a1a2e;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: flex-end;
        }
        
        .control-group { display: flex; flex-direction: column; gap: 6px; }
        .control-group label { font-size: 12px; color: #888; text-transform: uppercase; }
        
        input, select {
            padding: 12px 16px;
            background: #0a0a0f;
            border: 1px solid #333;
            border-radius: 8px;
            color: #fff;
            font-size: 14px;
            min-width: 180px;
        }
        
        input:focus, select:focus { outline: none; border-color: #00ff88; }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: all 0.2s;
        }
        
        .btn-primary { background: linear-gradient(135deg, #00ff88, #00cc6a); color: #000; }
        .btn-danger { background: #ff4757; color: #fff; }
        .btn-secondary { background: #333; color: #fff; }
        .btn:hover { transform: translateY(-1px); opacity: 0.9; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        
        .selected-info {
            padding: 8px 16px;
            background: #0a0a0f;
            border-radius: 8px;
            font-size: 13px;
            color: #888;
        }
        
        .selected-info strong { color: #00ff88; }
        
        .products-table {
            background: #1a1a2e;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #333;
        }
        
        .table-header {
            display: grid;
            grid-template-columns: 50px 70px 1fr 250px 100px;
            gap: 16px;
            padding: 16px 24px;
            background: #0a0a0f;
            font-size: 12px;
            text-transform: uppercase;
            color: #888;
            font-weight: 600;
        }
        
        .table-row {
            display: grid;
            grid-template-columns: 50px 70px 1fr 250px 100px;
            gap: 16px;
            padding: 16px 24px;
            border-bottom: 1px solid #2a2a3a;
            align-items: center;
            transition: background 0.2s;
        }
        
        .table-row:hover { background: rgba(255,255,255,0.02); }
        .table-row:last-child { border-bottom: none; }
        
        .checkbox {
            width: 22px; height: 22px;
            border: 2px solid #444;
            border-radius: 5px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }
        
        .checkbox:hover { border-color: #00ff88; }
        .checkbox.checked { background: #00ff88; border-color: #00ff88; }
        .checkbox.checked::after { content: '✓'; color: #000; font-size: 14px; font-weight: bold; }
        
        .product-image {
            width: 50px; height: 50px;
            background: #333;
            border-radius: 8px;
            object-fit: cover;
        }
        
        .product-title { font-weight: 500; margin-bottom: 4px; }
        .product-vendor { font-size: 13px; color: #666; }
        
        .tags { display: flex; flex-wrap: wrap; gap: 6px; }
        
        .tag {
            padding: 4px 10px;
            background: #0a0a0f;
            border: 1px solid #333;
            border-radius: 6px;
            font-size: 12px;
            color: #888;
        }
        
        .tag.highlight { background: rgba(0,255,136,0.15); border-color: #00ff88; color: #00ff88; }
        
        .no-tags { color: #555; font-style: italic; font-size: 13px; }
        
        .price { font-family: 'SF Mono', Monaco, monospace; font-weight: 500; color: #00ff88; }
        
        .empty-state { text-align: center; padding: 60px; color: #666; }
        .empty-state .icon { font-size: 48px; margin-bottom: 16px; }
        .empty-state h3 { color: #fff; margin-bottom: 8px; }
        
        .loading { text-align: center; padding: 60px; }
        
        .spinner {
            width: 40px; height: 40px;
            border: 3px solid #333;
            border-top-color: #00ff88;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.85);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        
        .modal-overlay.show { display: flex; }
        
        .modal {
            background: #1a1a2e;
            padding: 32px;
            border-radius: 16px;
            width: 100%;
            max-width: 450px;
            border: 1px solid #333;
            animation: modalIn 0.3s ease;
        }
        
        @keyframes modalIn {
            from { opacity: 0; transform: scale(0.95) translateY(20px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
        }
        
        .modal h2 { margin-bottom: 24px; display: flex; align-items: center; gap: 12px; }
        .modal .control-group { margin-bottom: 20px; }
        .modal input, .modal select { width: 100%; }
        
        .modal-actions { display: flex; gap: 12px; margin-top: 28px; }
        .modal-actions .btn { flex: 1; justify-content: center; }
        
        .task-card {
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .task-info h4 { margin-bottom: 6px; font-weight: 500; }
        .task-info p { font-size: 13px; color: #00ff88; font-family: monospace; }
        
        .toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 16px 24px;
            border-radius: 10px;
            font-weight: 500;
            z-index: 2000;
            animation: slideIn 0.3s ease;
        }
        
        .toast.success { background: #00ff88; color: #000; }
        .toast.error { background: #ff4757; color: #fff; }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(100px); }
            to { opacity: 1; transform: translateX(0); }
        }
        
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        @media (max-width: 900px) {
            .header { padding: 16px 20px; flex-direction: column; gap: 12px; }
            .container { padding: 20px; }
            .table-header, .table-row {
                grid-template-columns: 40px 1fr 100px;
            }
            .table-header > *:nth-child(2),
            .table-row > *:nth-child(2),
            .table-header > *:nth-child(4),
            .table-row > *:nth-child(4) { display: none; }
            .controls { flex-direction: column; align-items: stretch; }
            .control-group { width: 100%; }
            input, select { width: 100%; min-width: auto; }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">🛍️ Shopify<span>Manager</span></div>
        <div class="status">
            <div class="status-dot"></div>
            Connecté à capet-shop
        </div>
    </header>
    
    <main class="container">
        <div class="tabs">
            <button class="tab active" onclick="showTab('products')">📦 Produits</button>
            <button class="tab" onclick="showTab('tasks')">⏰ Tâches planifiées</button>
        </div>
        
        <!-- Tab Produits -->
        <div id="products-tab" class="tab-content active">
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
                <div class="stat-card">
                    <div class="stat-label">Tâches actives</div>
                    <div class="stat-value" id="active-tasks">0</div>
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
        </div>
        
        <!-- Tab Tâches -->
        <div id="tasks-tab" class="tab-content">
            <h2 style="margin-bottom: 24px;">⏰ Tâches planifiées</h2>
            <div id="tasks-list">
                <div class="empty-state">
                    <div class="icon">📅</div>
                    <h3>Aucune tâche planifiée</h3>
                    <p>Planifiez des tâches depuis l'onglet Produits</p>
                </div>
            </div>
        </div>
    </main>
    
    <!-- Modal Planification -->
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
        let tasks = [];
        
        // Charger les produits au démarrage
        document.addEventListener('DOMContentLoaded', () => {
            loadProducts();
            loadTasks();
            
            // Filtrage en temps réel
            document.getElementById('search-tag').addEventListener('input', filterProducts);
            document.getElementById('filter-mode').addEventListener('change', filterProducts);
        });
        
        async function loadProducts() {
            document.getElementById('products-list').innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Chargement des produits...</p>
                </div>
            `;
            
            try {
                const response = await fetch('/api/products');
                const data = await response.json();
                products = data.products || [];
                filterProducts();
                document.getElementById('total-products').textContent = products.length;
            } catch (error) {
                document.getElementById('products-list').innerHTML = `
                    <div class="empty-state">
                        <div class="icon">❌</div>
                        <h3>Erreur de chargement</h3>
                        <p>${error.message}</p>
                    </div>
                `;
            }
        }
        
        function filterProducts() {
            const searchTag = document.getElementById('search-tag').value.toLowerCase();
            const filterMode = document.getElementById('filter-mode').value;
            
            if (filterMode === 'all' || !searchTag) {
                filteredProducts = products;
            } else if (filterMode === 'with') {
                filteredProducts = products.filter(p => 
                    (p.tags || '').toLowerCase().includes(searchTag)
                );
            } else if (filterMode === 'without') {
                filteredProducts = products.filter(p => 
                    !(p.tags || '').toLowerCase().includes(searchTag)
                );
            }
            
            document.getElementById('filtered-products').textContent = filteredProducts.length;
            renderProducts();
        }
        
        function renderProducts() {
            const container = document.getElementById('products-list');
            const searchTag = document.getElementById('search-tag').value.toLowerCase();
            
            if (filteredProducts.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">📭</div>
                        <h3>Aucun produit trouvé</h3>
                        <p>Modifiez vos filtres ou actualisez la liste</p>
                    </div>
                `;
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
                        <img class="product-image" src="${imageUrl}" alt="${product.title}" onerror="this.style.display='none'">
                        <div>
                            <div class="product-title">${product.title}</div>
                            <div class="product-vendor">${product.vendor || ''}</div>
                        </div>
                        <div class="tags">
                            ${tags.length > 0 
                                ? tags.map(tag => `<span class="tag ${searchTag && tag.toLowerCase().includes(searchTag) ? 'highlight' : ''}">${tag}</span>`).join('')
                                : '<span class="no-tags">Aucune balise</span>'
                            }
                        </div>
                        <div class="price">${price} €</div>
                    </div>
                `;
            }).join('');
            
            updateSelectionUI();
        }
        
        function toggleProduct(id) {
            if (selectedIds.has(id)) {
                selectedIds.delete(id);
            } else {
                selectedIds.add(id);
            }
            renderProducts();
        }
        
        function toggleSelectAll() {
            if (selectedIds.size === filteredProducts.length) {
                selectedIds.clear();
            } else {
                filteredProducts.forEach(p => selectedIds.add(p.id));
            }
            renderProducts();
        }
        
        function updateSelectionUI() {
            document.getElementById('selected-products').textContent = selectedIds.size;
            document.getElementById('selection-count').textContent = selectedIds.size;
            
            const selectAll = document.getElementById('select-all');
            if (selectedIds.size === filteredProducts.length && filteredProducts.length > 0) {
                selectAll.classList.add('checked');
            } else {
                selectAll.classList.remove('checked');
            }
        }
        
        async function addTagToSelected() {
            const tag = document.getElementById('new-tag').value.trim();
            if (!tag) {
                showToast('Entrez une balise', 'error');
                return;
            }
            if (selectedIds.size === 0) {
                showToast('Sélectionnez des produits', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/products/add-tag', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product_ids: Array.from(selectedIds), tag })
                });
                const data = await response.json();
                
                showToast(`Balise "${tag}" ajoutée à ${data.count} produit(s)`, 'success');
                document.getElementById('new-tag').value = '';
                selectedIds.clear();
                loadProducts();
            } catch (error) {
                showToast('Erreur: ' + error.message, 'error');
            }
        }
        
        async function deleteSelected() {
            if (selectedIds.size === 0) {
                showToast('Sélectionnez des produits', 'error');
                return;
            }
            
            if (!confirm(`Supprimer ${selectedIds.size} produit(s) ? Cette action est irréversible.`)) {
                return;
            }
            
            try {
                const response = await fetch('/api/products/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product_ids: Array.from(selectedIds) })
                });
                const data = await response.json();
                
                showToast(`${data.count} produit(s) supprimé(s)`, 'success');
                selectedIds.clear();
                loadProducts();
            } catch (error) {
                showToast('Erreur: ' + error.message, 'error');
            }
        }
        
        // Tabs
        function showTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            
            document.querySelector(`.tab[onclick="showTab('${tab}')"]`).classList.add('active');
            document.getElementById(`${tab}-tab`).classList.add('active');
            
            if (tab === 'tasks') loadTasks();
        }
        
        // Scheduler
        function openScheduler() {
            document.getElementById('scheduler-modal').classList.add('show');
            document.getElementById('schedule-date').valueAsDate = new Date();
        }
        
        function closeScheduler() {
            document.getElementById('scheduler-modal').classList.remove('show');
        }
        
        async function scheduleTask() {
            const action = document.getElementById('schedule-action').value;
            const tag = document.getElementById('schedule-tag').value.trim();
            const date = document.getElementById('schedule-date').value;
            const time = document.getElementById('schedule-time').value;
            
            if (!tag || !date || !time) {
                showToast('Remplissez tous les champs', 'error');
                return;
            }
            
            const scheduledAt = `${date}T${time}:00`;
            
            try {
                const response = await fetch('/api/tasks/schedule', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, tag, scheduled_at: scheduledAt })
                });
                const data = await response.json();
                
                showToast('Tâche planifiée !', 'success');
                closeScheduler();
                loadTasks();
            } catch (error) {
                showToast('Erreur: ' + error.message, 'error');
            }
        }
        
        async function loadTasks() {
            try {
                const response = await fetch('/api/tasks');
                const data = await response.json();
                tasks = data.tasks || [];
                
                document.getElementById('active-tasks').textContent = tasks.length;
                renderTasks();
            } catch (error) {
                console.error('Erreur chargement tâches:', error);
            }
        }
        
        function renderTasks() {
            const container = document.getElementById('tasks-list');
            
            if (tasks.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">📅</div>
                        <h3>Aucune tâche planifiée</h3>
                        <p>Planifiez des tâches depuis l'onglet Produits</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = tasks.map(task => {
                const actionText = task.action === 'delete-without-tag' 
                    ? `🗑️ Supprimer produits sans "${task.tag}"`
                    : `🏷️ Ajouter "${task.tag}" à tous les produits`;
                
                const date = new Date(task.scheduled_at);
                const dateStr = date.toLocaleDateString('fr-FR');
                const timeStr = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
                
                return `
                    <div class="task-card">
                        <div class="task-info">
                            <h4>${actionText}</h4>
                            <p>📅 ${dateStr} à ${timeStr}</p>
                        </div>
                        <button class="btn btn-danger" onclick="deleteTask(${task.id})">Annuler</button>
                    </div>
                `;
            }).join('');
        }
        
        async function deleteTask(taskId) {
            try {
                await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
                showToast('Tâche annulée', 'success');
                loadTasks();
            } catch (error) {
                showToast('Erreur: ' + error.message, 'error');
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
# DÉMARRAGE
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'''
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║   🛍️  SHOPIFY PRODUCT MANAGER                              ║
║                                                            ║
║   Serveur démarré sur http://localhost:{port}               ║
║                                                            ║
║   Boutique: {SHOP}                        
║                                                            ║
╚════════════════════════════════════════════════════════════╝
    ''')
    app.run(host='0.0.0.0', port=port, debug=False)
