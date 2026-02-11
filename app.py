"""
Shopify Manager V4.3 - Instant Load Edition
- Produits chargés EN BACKGROUND au démarrage
- Page s'affiche IMMÉDIATEMENT
- Frontend poll et affiche progressivement
"""

from flask import Flask, jsonify, request
import json, os, time, re, ssl
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from datetime import datetime
from threading import Thread, Lock

app = Flask(__name__)

SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'
SITE_NAME = os.environ.get('SITE_NAME', 'KP SHOES')
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'kpshoes.fr')
BENEFITS = ["100% Authentique", "Livraison rapide", "Paiement 3x sans frais"]

_lock = Lock()
_store = {
    'products': [], 'collections': [],
    'products_loading': False, 'products_ready': False,
    'products_error': None, 'products_loaded_at': None,
    'collections_loaded_at': None,
}
CACHE_TTL = 300

task_progress = {
    'running': False, 'current': 0, 'total': 0,
    'message': '', 'success_count': 0, 'error_count': 0
}

try:
    import certifi
    _ssl_ctx = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _ssl_ctx = ssl.create_default_context()


def shopify_request(endpoint, method='GET', data=None, retries=3):
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    headers = {'X-Shopify-Access-Token': ACCESS_TOKEN, 'Content-Type': 'application/json'}
    body = json.dumps(data).encode('utf-8') if data else None
    for attempt in range(retries):
        try:
            req = Request(url, data=body, headers=headers, method=method)
            with urlopen(req, context=_ssl_ctx, timeout=30) as resp:
                return True if method == 'DELETE' else json.loads(resp.read().decode('utf-8'))
        except HTTPError as e:
            if e.code == 429:
                wait = float(e.headers.get('Retry-After', 2 * (attempt + 1)))
                print(f"[429] Rate limited, wait {wait}s")
                time.sleep(wait); continue
            elif e.code >= 500:
                time.sleep(2 * (attempt + 1)); continue
            else:
                try: msg = e.read().decode('utf-8', errors='replace')[:200]
                except: msg = str(e)
                print(f"[API {e.code}] {msg}"); return None
        except Exception as e:
            print(f"[API Error] {type(e).__name__}: {e}")
            if attempt < retries - 1: time.sleep(1); continue
            return None
    return None


# ═══ BACKGROUND LOADING ═══
def _bg_load_products():
    global _store
    with _lock:
        if _store['products_loading']: return
        _store['products_loading'] = True
        _store['products_error'] = None
    print("[BG] Loading products...")
    t0 = time.time()
    all_prods, since_id, page = [], 0, 0
    while True:
        result = shopify_request(f'products.json?limit=250&since_id={since_id}')
        if not result or 'products' not in result or not result['products']: break
        batch = result['products']
        all_prods.extend(batch)
        page += 1
        print(f"[BG] Page {page}: +{len(batch)} (total: {len(all_prods)})")
        with _lock:
            _store['products'] = list(all_prods)
        since_id = batch[-1]['id']
        if len(batch) < 250: break
        time.sleep(0.5)
    elapsed = round(time.time() - t0, 1)
    with _lock:
        _store['products'] = all_prods
        _store['products_loading'] = False
        _store['products_ready'] = True
        _store['products_loaded_at'] = datetime.now()
    print(f"[BG] Done: {len(all_prods)} products in {elapsed}s")

def _bg_load_collections():
    global _store
    cols = []
    for ctype in ['custom_collections', 'smart_collections']:
        r = shopify_request(f'{ctype}.json?limit=250')
        if r and ctype in r:
            for c in r[ctype]:
                cols.append({'id': c['id'], 'handle': c['handle'], 'title': c['title']})
    with _lock:
        _store['collections'] = cols
        _store['collections_loaded_at'] = datetime.now()
    print(f"[BG] {len(cols)} collections loaded")

def start_background_load():
    Thread(target=_bg_load_collections, daemon=True).start()
    Thread(target=_bg_load_products, daemon=True).start()

def ensure_products_fresh():
    with _lock:
        if _store['products_loading']: return
        t = _store['products_loaded_at']
        if t and (datetime.now() - t).total_seconds() < CACHE_TTL: return
    Thread(target=_bg_load_products, daemon=True).start()

def get_collections():
    with _lock:
        t = _store['collections_loaded_at']
    if not t or (datetime.now() - t).total_seconds() > CACHE_TTL * 2:
        _bg_load_collections()
    with _lock:
        return list(_store['collections'])


# ═══ COLLECTION MATCHING ═══
MODEL_MAPPINGS = [
    ('ugg-tasman', ['ugg tasman', 'tasman slipper', 'tasman chestnut', 'tasman black']),
    ('ugg-tazz', ['ugg tazz', 'tazz slipper']),
    ('jordan-4', ['jordan 4', 'aj4', 'air jordan 4']),
    ('jordan-1-low', ['jordan 1 low', 'aj1 low']),
    ('jordan-1-mid', ['jordan 1 mid', 'aj1 mid']),
    ('jordan-1-high', ['jordan 1 high', 'aj1 high', 'jordan 1 retro high']),
    ('nike-dunk-low', ['dunk low']), ('nike-dunk-high', ['dunk high']),
    ('air-force-1', ['air force 1', 'af1']),
    ('nike-air-max', ['air max']),
    ('nike-p-6000', ['p-6000', 'p6000']),
    ('adidas-samba', ['samba']), ('adidas-campus', ['campus']),
    ('adidas-gazelle', ['gazelle']), ('adidas-spezial', ['spezial']),
    ('adidas-forum', ['forum']),
    ('new-balance-550', ['new balance 550', 'nb 550']),
    ('new-balance-530', ['new balance 530']),
    ('new-balance-2002r', ['2002r']),
    ('asics-gel-1130', ['gel-1130', 'gel 1130']),
    ('asics-gel-kayano', ['kayano']),
    ('asics-gel-nyc', ['gel-nyc', 'gel nyc']),
    ('yeezy-350', ['yeezy 350']), ('yeezy-500', ['yeezy 500']),
    ('yeezy-slide', ['yeezy slide']), ('yeezy-foam', ['foam runner']),
    ('birkenstock-boston', ['boston']),
]
BRAND_MAPPINGS = [
    ('jordan-1', ['jordan', 'air jordan']),
    ('adidas-1', ['adidas']), ('asics-1', ['asics']),
    ('ugg', ['ugg']), ('nike', ['nike']),
    ('new-balance', ['new balance']), ('puma', ['puma']),
    ('birkenstock-1', ['birkenstock']), ('yeezy', ['yeezy']), ('bape', ['bape']),
]

def find_best_collection(title, collections):
    tl = title.lower()
    avail = {c['handle']: c['title'] for c in collections}
    for h, pats in MODEL_MAPPINGS:
        if h in avail:
            for p in pats:
                if p in tl: return {'handle': h, 'title': avail[h], 'type': 'model'}
    for h, pats in BRAND_MAPPINGS:
        if h in avail:
            for p in pats:
                if p in tl: return {'handle': h, 'title': avail[h], 'type': 'brand'}
    return None


# ═══ SEO HELPERS ═══
def strip_html(t):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', t)).strip() if t else ''

def extract_sku(p):
    v = p.get('variants')
    return v[0].get('sku', '') if v else ''

def extract_brand(p):
    t = p.get('title', '')
    for b in ['Air Jordan','New Balance','Birkenstock','Adidas','Nike','Jordan','Puma','Asics','UGG','Yeezy','BAPE']:
        if b.lower() in t.lower(): return b
    return p.get('vendor', 'Sneakers')

def extract_colorway(p):
    m = re.search(r'\(([^)]+)\)', p.get('title', ''))
    return m.group(1) if m else ''

def check_seo_status(product, metafields=None):
    s = {
        'meta_title': {'exists':False,'value':None,'needs_update':True},
        'meta_description': {'exists':False,'value':None,'needs_update':True},
        'description': {'exists':False,'value':None,'has_links':False,'needs_update':True}
    }
    if metafields and metafields.get('meta_title'):
        mt = metafields['meta_title']
        s['meta_title'].update({'exists':True,'value':mt})
        if SITE_NAME.lower() in mt.lower(): s['meta_title']['needs_update'] = False
    if metafields and metafields.get('meta_description'):
        md = metafields['meta_description']
        s['meta_description'].update({'exists':True,'value':md})
        if len(md) >= 50 and ('authentique' in md.lower() or SITE_NAME.lower() in md.lower()):
            s['meta_description']['needs_update'] = False
    body = product.get('body_html','') or ''
    if body and len(body.strip()) > 100:
        s['description'].update({'exists':True,'value':body[:200]+('...' if len(body)>200 else '')})
        if '<a href=' in body.lower() and SITE_DOMAIN in body.lower():
            s['description'].update({'has_links':True,'needs_update':False})
    return s

def calculate_seo_score(ss):
    sc = 0
    if not ss['meta_title']['needs_update']: sc += 30
    elif ss['meta_title']['exists']: sc += 15
    if not ss['meta_description']['needs_update']: sc += 30
    elif ss['meta_description']['exists']: sc += 15
    if not ss['description']['needs_update']: sc += 40
    elif ss['description']['exists']: sc += 20
    return sc

def generate_meta_title(p):
    t = p.get('title','')
    m = f"{t} | {SITE_NAME}"
    if len(m) > 60: m = f"{t[:60-len(SITE_NAME)-6]}... | {SITE_NAME}"
    return m

def generate_meta_description(p):
    t, sku = p.get('title',''), extract_sku(p)
    base = f"Achetez la {t}" + (f" (SKU: {sku})" if sku else "") + f" sur {SITE_NAME}"
    m = f"{base} ✓ " + " ✓ ".join(BENEFITS) + "."
    if len(m) > 155: m = f"Achetez la {t} ✓ {BENEFITS[0]} ✓ {BENEFITS[1]} - {SITE_NAME}"[:155]
    return m

def generate_description(product, collection):
    title, brand = product.get('title',''), extract_brand(product)
    sku, colorway = extract_sku(product), extract_colorway(product)
    current = strip_html(product.get('body_html',''))
    lines = []
    if collection:
        lnk = f'<a href="https://{SITE_DOMAIN}/collections/{collection["handle"]}">{collection["title"]}</a>'
        lines.append(f'<p>Découvrez la <strong>{title}</strong>, une pièce incontournable de notre collection {lnk}.</p>')
    else:
        lines.append(f'<p>Découvrez la <strong>{title}</strong>, signée {brand}.</p>')
    if current and len(current) > 50:
        lines.append(f'<p>{current[:400]}{"..." if len(current) > 400 else ""}</p>')
    else:
        lines.append(f'<p>Cette {brand} se distingue par son design unique et ses finitions de qualité.</p>')
    tech = []
    if sku: tech.append(f'<strong>SKU</strong> : {sku}')
    if colorway: tech.append(f'<strong>Colorway</strong> : {colorway}')
    tech.append(f'<strong>Marque</strong> : {brand}')
    lines.append('<p>' + '<br>'.join(tech) + '</p>')
    lines.append(f'<p>Chez <strong>{SITE_NAME}</strong>, toutes nos sneakers sont <strong>100% authentiques</strong> et vérifiées par nos experts.</p>')
    return '\n'.join(lines)

def get_product_metafields(pid):
    r = shopify_request(f'products/{pid}/metafields.json')
    mt, md, mt_id, md_id = None, None, None, None
    if r and 'metafields' in r:
        for mf in r['metafields']:
            if mf.get('namespace') == 'global':
                if mf.get('key') == 'title_tag': mt, mt_id = mf.get('value'), mf.get('id')
                elif mf.get('key') == 'description_tag': md, md_id = mf.get('value'), mf.get('id')
    return {'meta_title':mt,'meta_description':md,'meta_title_id':mt_id,'meta_description_id':md_id}

def update_product_seo(pid, updates, existing_metafields=None):
    ok = True
    if 'body_html' in updates:
        r = shopify_request(f'products/{pid}.json','PUT',{'product':{'id':pid,'body_html':updates['body_html']}})
        if not r: ok = False
        time.sleep(0.4)
    for key, ns_key in [('meta_title','title_tag'),('meta_description','description_tag')]:
        if key in updates:
            mf_id = (existing_metafields or {}).get(f'{key}_id')
            if mf_id:
                shopify_request(f'products/{pid}/metafields/{mf_id}.json','PUT',
                    {'metafield':{'id':mf_id,'value':updates[key]}})
            else:
                shopify_request(f'products/{pid}/metafields.json','POST',
                    {'metafield':{'namespace':'global','key':ns_key,'value':updates[key],'type':'single_line_text_field'}})
            time.sleep(0.3)
    return ok


# ═══ ROUTES ═══
@app.route('/')
def home():
    return HOME_HTML

@app.route('/seo')
def seo_page():
    return SEO_HTML

@app.route('/api/collections')
def api_collections():
    c = get_collections()
    return jsonify({'collections':c,'count':len(c)})

@app.route('/api/products/status')
def api_products_status():
    with _lock:
        return jsonify({
            'loading':_store['products_loading'],
            'ready':_store['products_ready'],
            'count':len(_store['products']),
            'error':_store['products_error'],
        })

@app.route('/api/products')
def api_products():
    ensure_products_fresh()
    with _lock:
        products = list(_store['products'])
        loading = _store['products_loading']
        ready = _store['products_ready']
    collections = get_collections()
    result, stats = [], {'total':0,'seo_complete':0,'seo_partial':0,'seo_missing':0}
    for p in products:
        col = find_best_collection(p.get('title',''), collections)
        body = p.get('body_html','') or ''
        has_desc = len(strip_html(body)) > 100
        has_links = '<a href=' in body.lower() and SITE_DOMAIN in body.lower()
        score = (30 if has_desc else 0) + (40 if has_links else 0)
        stats['total'] += 1
        if score >= 70: stats['seo_complete'] += 1
        elif score >= 30: stats['seo_partial'] += 1
        else: stats['seo_missing'] += 1
        result.append({
            'id':p['id'],'title':p['title'],'handle':p['handle'],
            'image':(p.get('image') or {}).get('src'),
            'sku':extract_sku(p),'collection':col,
            'seo_score':score,'has_description':has_desc,'has_links':has_links,
        })
    stats['percentage_complete'] = round(stats['seo_complete']/stats['total']*100,1) if stats['total']>0 else 0
    return jsonify({'products':result,'stats':stats,'loading':loading,'ready':ready})

@app.route('/api/product/<int:product_id>/seo-status')
def api_product_seo_status(product_id):
    r = shopify_request(f'products/{product_id}.json')
    if not r: return jsonify({'error':'Not found'}),404
    p = r['product']
    mf = get_product_metafields(product_id)
    cols = get_collections()
    col = find_best_collection(p.get('title',''),cols)
    ss = check_seo_status(p,mf)
    return jsonify({
        'product':{'id':p['id'],'title':p['title'],'sku':extract_sku(p)},
        'collection':col,'seo_status':ss,'score':calculate_seo_score(ss),
        'generated':{'meta_title':generate_meta_title(p),'meta_description':generate_meta_description(p),'description':generate_description(p,col)}
    })

@app.route('/api/seo/apply', methods=['POST'])
def api_apply_seo():
    data = request.json
    pid, fields = data.get('product_id'), data.get('fields',[])
    if not pid or not fields: return jsonify({'error':'Missing'}),400
    r = shopify_request(f'products/{pid}.json')
    if not r: return jsonify({'error':'Not found'}),404
    p = r['product']
    col = find_best_collection(p.get('title',''),get_collections())
    mf = get_product_metafields(pid)
    u = {}
    if 'meta_title' in fields: u['meta_title'] = generate_meta_title(p)
    if 'meta_description' in fields: u['meta_description'] = generate_meta_description(p)
    if 'description' in fields: u['body_html'] = generate_description(p,col)
    ok = update_product_seo(pid,u,existing_metafields=mf)
    if ok:
        with _lock: _store['products_loaded_at'] = None
    return jsonify({'success':ok,'applied_fields':list(u.keys())})

@app.route('/api/seo/batch', methods=['POST'])
def api_batch_seo():
    global task_progress
    data = request.json
    pids, fields = data.get('product_ids',[]), data.get('fields',['description'])
    if not pids: return jsonify({'error':'No products'}),400
    if task_progress.get('running'): return jsonify({'error':'Batch déjà en cours'}),409
    def process():
        global task_progress
        task_progress = {'running':True,'current':0,'total':len(pids),'message':'Démarrage...','success_count':0,'error_count':0}
        cols = get_collections()
        for i, pid in enumerate(pids):
            task_progress['current'] = i + 1
            r = shopify_request(f'products/{pid}.json')
            if r and 'product' in r:
                p = r['product']
                task_progress['message'] = f'#{i+1}/{len(pids)} {p.get("title","")[:30]}...'
                col = find_best_collection(p.get('title',''),cols)
                mf = get_product_metafields(pid) if ('meta_title' in fields or 'meta_description' in fields) else None
                u = {}
                if 'meta_title' in fields: u['meta_title'] = generate_meta_title(p)
                if 'meta_description' in fields: u['meta_description'] = generate_meta_description(p)
                if 'description' in fields: u['body_html'] = generate_description(p,col)
                if u and update_product_seo(pid,u,existing_metafields=mf): task_progress['success_count'] += 1
                else: task_progress['error_count'] += 1
            else: task_progress['error_count'] += 1
            time.sleep(1.0)
        task_progress['running'] = False
        task_progress['message'] = f'Terminé! {task_progress["success_count"]} OK, {task_progress["error_count"]} erreurs'
        with _lock: _store['products_loaded_at'] = None
    Thread(target=process, daemon=True).start()
    return jsonify({'status':'started','total':len(pids)})

@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)

@app.route('/api/cache/clear', methods=['POST'])
def api_clear_cache():
    with _lock:
        _store['products'] = []; _store['products_ready'] = False
        _store['products_loaded_at'] = None
        _store['collections'] = []; _store['collections_loaded_at'] = None
    start_background_load()
    return jsonify({'success':True})


# ═══ HTML TEMPLATES ═══
HOME_HTML = '''<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Shopify Manager V4.3</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:linear-gradient(135deg,#0a0a0f,#1a1a2e);min-height:100vh;display:flex;align-items:center;justify-content:center;color:#fff}
.c{text-align:center;padding:40px}.logo{font-size:70px;margin-bottom:20px}
h1{font-size:48px;background:linear-gradient(135deg,#00ff88,#00cc6a);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.v{background:#8b5cf6;padding:6px 16px;border-radius:20px;font-size:14px;margin:15px 0 30px;display:inline-block}
.f{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:40px}
.f span{background:rgba(255,255,255,0.1);padding:8px 16px;border-radius:20px;font-size:12px}
.btn{display:inline-block;padding:18px 50px;background:linear-gradient(135deg,#00ff88,#00cc6a);color:#000;text-decoration:none;border-radius:12px;font-size:18px;font-weight:bold;transition:transform .2s,box-shadow .2s}
.btn:hover{transform:translateY(-2px);box-shadow:0 8px 25px rgba(0,255,136,0.3)}
</style></head><body>
<div class="c">
<div class="logo">🤖</div><h1>Shopify Manager</h1>
<div class="v">V4.3 — Instant Load</div>
<div class="f"><span>⚡ Chargement background</span><span>🔄 Retry auto (429)</span><span>✅ Upsert metafields</span><span>🔒 SSL vérifié</span></div>
<a href="/seo" class="btn">🚀 Gestion SEO</a>
</div></body></html>'''


SEO_HTML = '''<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SEO Manager V4.3</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0f;min-height:100vh;color:#fff}
.hd{padding:15px 30px;background:#111;border-bottom:1px solid #222;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:18px;font-weight:bold}.logo span{color:#00ff88}
.back{color:#888;text-decoration:none}.back:hover{color:#fff}
.load-banner{padding:12px 30px;background:linear-gradient(90deg,#1a1a2e,#2a1a3e);border-bottom:1px solid #333;display:none;align-items:center;gap:15px}
.load-banner.sh{display:flex}
.load-banner .mini-sp{width:20px;height:20px;border:2px solid #333;border-top-color:#8b5cf6;border-radius:50%;animation:spin .8s linear infinite;flex-shrink:0}
.load-banner .txt{font-size:13px;color:#aaa}.load-banner .cnt{color:#8b5cf6;font-weight:bold}
.stats{display:flex;gap:15px;padding:20px 30px;background:linear-gradient(90deg,rgba(0,255,136,0.08),rgba(139,92,246,0.08));flex-wrap:wrap}
.stat{background:rgba(0,0,0,0.3);padding:12px 20px;border-radius:8px;text-align:center}
.sv{font-size:24px;font-weight:bold}.sv.g{color:#00ff88}.sv.o{color:#ffa502}.sv.r{color:#ff4757}
.sl{font-size:10px;color:#666;margin-top:4px}
.ctrl{padding:20px 30px;display:flex;gap:15px;flex-wrap:wrap;align-items:flex-end;border-bottom:1px solid #222}
.cg{display:flex;flex-direction:column;gap:5px}
.cg label{font-size:10px;color:#666;text-transform:uppercase;letter-spacing:.5px}
.cg input,.cg select{padding:10px 14px;background:#1a1a2e;border:1px solid #333;border-radius:6px;color:#fff;font-size:13px;outline:none}
.cg input:focus,.cg select:focus{border-color:#00ff88}
.fs{display:flex;gap:10px;align-items:center;background:#1a1a2e;padding:10px 15px;border-radius:8px;border:1px solid #333}
.fs label{font-size:12px;display:flex;align-items:center;gap:5px;cursor:pointer}
.fs input[type="checkbox"]{width:16px;height:16px;accent-color:#00ff88}
.btn{padding:10px 20px;border:none;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;transition:opacity .2s}.btn:hover{opacity:0.85}
.bp{background:#00ff88;color:#000}.bd{background:#ff6b6b;color:#fff}.bs{background:#333;color:#fff}
.prods{padding:20px 30px;display:flex;flex-direction:column;gap:10px}
.prod{background:#1a1a2e;border:1px solid #2a2a3a;border-radius:10px;padding:15px;display:grid;grid-template-columns:30px 60px 1fr 150px 80px 100px;gap:15px;align-items:center;transition:border-color .2s}
.prod:hover{border-color:#444}
.pck{width:22px;height:22px;border:2px solid #444;border-radius:5px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s}
.pck.chk{background:#00ff88;border-color:#00ff88}.pck.chk::after{content:'✓';color:#000;font-weight:bold}
.pim{width:60px;height:60px;border-radius:8px;object-fit:cover;background:#333}
.pin h3{font-size:13px;margin-bottom:4px}
.psku{font-size:11px;color:#666;font-family:monospace}
.pcol{font-size:11px;margin-top:4px}.pcol.f{color:#00ff88}.pcol.b{color:#8b5cf6}.pcol.n{color:#ff4757}
.pst{font-size:11px}.si{display:flex;align-items:center;gap:5px;margin-bottom:3px}.sok{color:#00ff88}.sms{color:#ff4757}
.psc{text-align:center}
.scb{display:inline-block;padding:6px 10px;border-radius:15px;font-weight:bold;font-size:12px}
.scb.h{background:rgba(0,255,136,0.2);color:#00ff88}.scb.m{background:rgba(255,165,2,0.2);color:#ffa502}.scb.l{background:rgba(255,71,87,0.2);color:#ff4757}
.pac{display:flex;gap:5px}
.ab{padding:6px 10px;font-size:11px;border:none;border-radius:4px;cursor:pointer;transition:opacity .2s}.ab:hover{opacity:0.8}.ab.v{background:#333;color:#fff}.ab.a{background:#00ff88;color:#000}
.mod{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);display:none;align-items:center;justify-content:center;z-index:1000;padding:20px}
.mod.sh{display:flex}
.mc{background:#1a1a2e;border-radius:12px;max-width:900px;width:100%;max-height:90vh;overflow-y:auto}
.mh{padding:20px;border-bottom:1px solid #333;display:flex;justify-content:space-between}.mh h2{font-size:18px}
.mx{background:none;border:none;color:#888;font-size:24px;cursor:pointer}.mx:hover{color:#fff}
.mb{padding:20px}
.ss{margin-bottom:20px}.ss h4{font-size:13px;color:#888;margin-bottom:10px;display:flex;align-items:center;gap:10px}
.ss .bg{font-size:10px;padding:2px 8px;border-radius:10px}.ss .bg.ok{background:#00ff88;color:#000}.ss .bg.ms{background:#ff4757;color:#fff}
.sc{background:#0a0a0f;padding:12px;border-radius:6px;font-size:12px;color:#888;margin-bottom:8px;border-left:3px solid #444;word-break:break-word}
.sg{background:#0a0a0f;padding:12px;border-radius:6px;font-size:12px;color:#00ff88;border-left:3px solid #00ff88;word-break:break-word}
.sg pre{white-space:pre-wrap;font-family:inherit}
.mfs{margin-top:20px;padding:15px;background:#0a0a0f;border-radius:8px}.mfs h4{margin-bottom:10px;font-size:13px}
.mfs label{display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:13px;cursor:pointer}
.ma{padding:20px;border-top:1px solid #333;display:flex;gap:10px;justify-content:flex-end}
.pb{position:fixed;top:0;left:0;right:0;background:#1a1a2e;padding:20px 30px;z-index:2000;border-bottom:2px solid #00ff88;display:none}.pb.sh{display:block}
.ph{display:flex;justify-content:space-between;margin-bottom:10px}
.pt{height:8px;background:#333;border-radius:4px;overflow:hidden}
.pf{height:100%;background:linear-gradient(90deg,#00ff88,#8b5cf6);transition:width 0.3s}
.px{margin-top:8px;font-size:13px;color:#888}
.tst{position:fixed;bottom:20px;right:20px;padding:12px 20px;border-radius:8px;z-index:3000;animation:fadeIn .2s}
.tst.s{background:#00ff88;color:#000}.tst.e{background:#ff4757;color:#fff}
.ld{text-align:center;padding:60px;color:#666}
.sp{width:40px;height:40px;border:3px solid #333;border-top-color:#00ff88;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 15px}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
</style></head><body>

<div class="pb" id="pb"><div class="ph"><strong>Génération SEO...</strong><span id="pc">0/0</span></div><div class="pt"><div class="pf" id="pf"></div></div><div class="px" id="px">Init...</div></div>

<header class="hd"><a href="/" class="back">← Accueil</a><div class="logo">🤖 SEO <span>Manager</span> <small style="color:#8b5cf6;font-size:11px">v4.3</small></div><div></div></header>

<div class="load-banner" id="loadBanner"><div class="mini-sp"></div><span class="txt">Chargement depuis Shopify... <span class="cnt" id="loadCount">0</span> produits chargés</span></div>

<div class="stats">
<div class="stat"><div class="sv g" id="s1">-</div><div class="sl">Complet</div></div>
<div class="stat"><div class="sv o" id="s2">-</div><div class="sl">Partiel</div></div>
<div class="stat"><div class="sv r" id="s3">-</div><div class="sl">Manquant</div></div>
<div class="stat"><div class="sv" id="s4">-</div><div class="sl">Total</div></div>
<div class="stat"><div class="sv g" id="s5">-%</div><div class="sl">Optimisé</div></div>
</div>

<div class="ctrl">
<div class="cg"><label>Rechercher</label><input type="text" id="src" placeholder="Nom, SKU..."></div>
<div class="cg"><label>Filtrer</label><select id="flt"><option value="all">Tous</option><option value="missing">❌ Sans liens</option><option value="partial">⚠️ Partiel</option><option value="complete">✅ Complet</option></select></div>
<div class="fs"><span style="font-size:11px;color:#888">Champs:</span><label><input type="checkbox" id="ft"> Title</label><label><input type="checkbox" id="fd"> Desc</label><label><input type="checkbox" id="fb" checked> Body</label></div>
<button class="btn bs" onclick="forceReload()">🔄</button>
<button class="btn bp" onclick="applySel()">⚡ Sélection</button>
<button class="btn bd" onclick="applyAll()">🚀 TOUT</button>
<div style="margin-left:auto;font-size:12px;color:#888"><strong id="sc">0</strong> sélect.</div>
</div>

<div class="prods" id="prods"><div class="ld"><div class="sp"></div>Chargement...</div></div>

<div class="mod" id="mod"><div class="mc">
<div class="mh"><h2 id="mt">Détails</h2><button class="mx" onclick="closeMod()">×</button></div>
<div class="mb" id="mmb"></div>
<div class="ma"><button class="btn bs" onclick="closeMod()">Fermer</button><button class="btn bp" onclick="applyMod()">✅ Appliquer</button></div>
</div></div>

<script>
let P=[],sel=new Set(),curId=null,pollTimer=null,prevCount=-1;

async function load(){
  try{
    const r=await fetch('/api/products');
    const d=await r.json();
    P=d.products;
    document.getElementById('s1').textContent=d.stats.seo_complete;
    document.getElementById('s2').textContent=d.stats.seo_partial;
    document.getElementById('s3').textContent=d.stats.seo_missing;
    document.getElementById('s4').textContent=d.stats.total;
    document.getElementById('s5').textContent=d.stats.percentage_complete+'%';
    filter();
    if(d.loading&&!d.ready){showLB(d.stats.total);startPoll();}
    else{hideLB();stopPoll();}
  }catch(e){document.getElementById('prods').innerHTML='<div class="ld">❌ Erreur de connexion</div>';}
}

function showLB(n){document.getElementById('loadBanner').classList.add('sh');document.getElementById('loadCount').textContent=n;}
function hideLB(){document.getElementById('loadBanner').classList.remove('sh');}

function startPoll(){
  if(pollTimer)return;
  pollTimer=setInterval(async()=>{
    try{
      const r=await fetch('/api/products/status');
      const s=await r.json();
      document.getElementById('loadCount').textContent=s.count;
      if(s.count!==prevCount){prevCount=s.count;load();}
      if(!s.loading||s.ready){hideLB();stopPoll();if(s.count!==P.length)load();}
    }catch(e){}
  },2000);
}
function stopPoll(){if(pollTimer){clearInterval(pollTimer);pollTimer=null;}}

async function forceReload(){
  toast('Rechargement...','s');
  await fetch('/api/cache/clear',{method:'POST'});
  prevCount=-1;P=[];
  document.getElementById('prods').innerHTML='<div class="ld"><div class="sp"></div>Rechargement depuis Shopify...</div>';
  setTimeout(load,500);
}

function filter(){
  const s=document.getElementById('src').value.toLowerCase();
  const f=document.getElementById('flt').value;
  const L=P.filter(p=>{
    if(s&&!p.title.toLowerCase().includes(s)&&!(p.sku||'').toLowerCase().includes(s))return false;
    if(f==='missing')return !p.has_links;if(f==='complete')return p.has_links;
    if(f==='partial')return p.has_description&&!p.has_links;return true;
  });
  render(L);
}

function render(L){
  const el=document.getElementById('prods');
  if(!L.length&&P.length===0){el.innerHTML='<div class="ld"><div class="sp"></div>En attente des produits...</div>';return;}
  if(!L.length){el.innerHTML='<div class="ld">Aucun produit trouvé</div>';return;}
  const B=40;let html='';
  for(let i=0;i<Math.min(B,L.length);i++)html+=card(L[i]);
  el.innerHTML=html;
  if(L.length>B){
    let loaded=B;
    const snt=document.createElement('div');snt.style.height='1px';el.appendChild(snt);
    const obs=new IntersectionObserver(e=>{
      if(e[0].isIntersecting&&loaded<L.length){
        let c='';const end=Math.min(loaded+B,L.length);
        for(let i=loaded;i<end;i++)c+=card(L[i]);
        snt.insertAdjacentHTML('beforebegin',c);loaded=end;
        if(loaded>=L.length)obs.disconnect();
      }
    },{rootMargin:'300px'});
    obs.observe(snt);
  }
}

function card(p){
  const ck=sel.has(p.id)?'chk':'';
  const sc=p.seo_score>=70?'h':p.seo_score>=30?'m':'l';
  let cc='n',ct='⚠️ Aucune';
  if(p.collection){cc=p.collection.type==='model'?'f':'b';ct=(p.collection.type==='model'?'✅ ':'📁 ')+p.collection.title;}
  return '<div class="prod"><div class="pck '+ck+'" onclick="tog('+p.id+')"></div>'+
    '<img class="pim" src="'+(p.image||'')+'" loading="lazy" onerror="this.style.background=\'#333\';this.onerror=null">'+
    '<div class="pin"><h3>'+esc(p.title.substring(0,50))+(p.title.length>50?'...':'')+'</h3>'+
    '<div class="psku">'+(p.sku||'N/A')+'</div><div class="pcol '+cc+'">'+ct+'</div></div>'+
    '<div class="pst"><div class="si '+(p.has_description?'sok':'sms')+'">'+(p.has_description?'✅':'❌')+' Desc</div>'+
    '<div class="si '+(p.has_links?'sok':'sms')+'">'+(p.has_links?'✅':'❌')+' Liens</div></div>'+
    '<div class="psc"><span class="scb '+sc+'">'+p.seo_score+'%</span></div>'+
    '<div class="pac"><button class="ab v" onclick="view('+p.id+')">👁️</button>'+
    '<button class="ab a" onclick="applyOne('+p.id+')">⚡</button></div></div>';
}

function tog(id){sel.has(id)?sel.delete(id):sel.add(id);document.getElementById('sc').textContent=sel.size;
  document.querySelectorAll('.pck').forEach(el=>{if(el.getAttribute('onclick')?.includes(id))el.classList.toggle('chk');});}
function esc(t){return(t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

async function view(id){
  curId=id;document.getElementById('mmb').innerHTML='<div class="ld"><div class="sp"></div></div>';
  document.getElementById('mod').classList.add('sh');
  try{
    const r=await fetch('/api/product/'+id+'/seo-status');const d=await r.json();
    const s=d.seo_status,g=d.generated;
    let h='<p><b>Produit:</b> '+esc(d.product.title)+'</p>';
    if(d.collection)h+='<p><b>Collection:</b> '+esc(d.collection.title)+' ('+d.collection.type+')</p>';
    h+='<p><b>Score:</b> '+d.score+'%</p><hr style="border-color:#333;margin:15px 0">';
    h+=seoB('Meta Title',s.meta_title,g.meta_title);
    h+=seoB('Meta Desc',s.meta_description,g.meta_description);
    h+='<div class="ss"><h4>Description <span class="bg '+(s.description.needs_update?'ms':'ok')+'">'+(s.description.needs_update?'À modifier':'OK')+'</span>'+(s.description.has_links?' 🔗':'')+'</h4>';
    h+='<div class="sc">'+(s.description.value?esc(s.description.value):'Aucune')+'</div>';
    h+='<div class="sg"><pre>'+esc(g.description)+'</pre></div></div>';
    h+='<div class="mfs"><h4>Appliquer:</h4>';
    h+='<label><input type="checkbox" id="mft" '+(s.meta_title.needs_update?'checked':'')+'> Meta Title</label>';
    h+='<label><input type="checkbox" id="mfd" '+(s.meta_description.needs_update?'checked':'')+'> Meta Desc</label>';
    h+='<label><input type="checkbox" id="mfb" '+(s.description.needs_update?'checked':'')+'> Description</label></div>';
    document.getElementById('mmb').innerHTML=h;document.getElementById('mt').textContent=d.product.title;
  }catch(e){document.getElementById('mmb').innerHTML='<div class="ld">❌ Erreur</div>';}
}
function seoB(lbl,st,gen){
  return '<div class="ss"><h4>'+lbl+' <span class="bg '+(st.needs_update?'ms':'ok')+'">'+(st.needs_update?'À modifier':'OK')+'</span></h4>'+
    '<div class="sc">'+(st.value?esc(st.value):'Aucun')+'</div><div class="sg">'+esc(gen)+'</div></div>';
}

function closeMod(){document.getElementById('mod').classList.remove('sh');curId=null;}
async function applyMod(){
  if(!curId)return;const f=[];
  if(document.getElementById('mft').checked)f.push('meta_title');
  if(document.getElementById('mfd').checked)f.push('meta_description');
  if(document.getElementById('mfb').checked)f.push('description');
  if(!f.length){toast('Sélectionnez un champ','e');return;}
  closeMod();toast('Application...','s');
  try{const r=await fetch('/api/seo/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:curId,fields:f})});
    if((await r.json()).success){toast('✅ Appliqué!','s');load();}else toast('❌ Erreur','e');
  }catch(e){toast('❌ Erreur','e');}
}

function getF(){const f=[];if(document.getElementById('ft').checked)f.push('meta_title');if(document.getElementById('fd').checked)f.push('meta_description');if(document.getElementById('fb').checked)f.push('description');return f;}

async function applyOne(id){const f=getF();if(!f.length){toast('Cochez un champ','e');return;}toast('Application...','s');
  try{const r=await fetch('/api/seo/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:id,fields:f})});
    if((await r.json()).success){toast('✅ OK!','s');load();}else toast('❌ Erreur','e');
  }catch(e){toast('❌ Erreur','e');}}

async function applySel(){if(!sel.size){toast('Sélectionnez','e');return;}const f=getF();if(!f.length){toast('Cochez un champ','e');return;}batch(Array.from(sel),f);}
async function applyAll(){const f=getF();if(!f.length){toast('Cochez un champ','e');return;}if(!confirm('Modifier '+f.join(', ')+' pour '+P.length+' produits ?'))return;batch(P.map(p=>p.id),f);}

async function batch(ids,f){showPB();
  try{const r=await fetch('/api/seo/batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_ids:ids,fields:f})});
    const d=await r.json();if(d.error){toast('❌ '+d.error,'e');hidePB();return;}mon();
  }catch(e){toast('❌ Erreur','e');hidePB();}}

function mon(){const iv=setInterval(async()=>{try{const r=await fetch('/api/progress');const p=await r.json();
  document.getElementById('pf').style.width=(p.total>0?p.current/p.total*100:0)+'%';
  document.getElementById('pc').textContent=p.current+'/'+p.total;document.getElementById('px').textContent=p.message;
  if(!p.running){clearInterval(iv);hidePB();toast(p.message,'s');sel.clear();document.getElementById('sc').textContent='0';load();}
}catch(e){}},800);}

function showPB(){document.getElementById('pb').classList.add('sh');}
function hidePB(){document.getElementById('pb').classList.remove('sh');}
function toast(m,t){document.querySelectorAll('.tst').forEach(e=>e.remove());const e=document.createElement('div');e.className='tst '+t;e.textContent=m;document.body.appendChild(e);setTimeout(()=>e.remove(),4000);}

let st;document.getElementById('src').addEventListener('input',()=>{clearTimeout(st);st=setTimeout(filter,150);});
document.getElementById('flt').addEventListener('change',filter);
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMod();});
load();
</script></body></html>'''


# ═══ STARTUP ═══
start_background_load()

if __name__ == '__main__':
    print(f"[V4.3] Shop: {SHOP}")
    print(f"[V4.3] Background loading started...")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
