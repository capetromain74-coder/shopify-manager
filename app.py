"""
Shopify Manager V4 - SEO Pro Edition
Basé sur V3 qui fonctionne + nouvelles fonctionnalités SEO
"""

from flask import Flask, jsonify, request
import json
import os
import time
import re
import ssl
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from threading import Thread

app = Flask(__name__)

# Configuration - IDENTIQUE à V3
SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'

SITE_NAME = os.environ.get('SITE_NAME', 'KP SHOES')
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'kpshoes.fr')
BENEFITS = ["100% Authentique", "Livraison rapide", "Paiement 3x sans frais"]

task_progress = {
    'running': False,
    'current': 0,
    'total': 0,
    'message': '',
    'type': ''
}


# ═══════════════════════════════════════════════════════════════
# FONCTIONS API SHOPIFY - IDENTIQUES à V3
# ═══════════════════════════════════════════════════════════════

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
    """Récupère TOUS les produits avec pagination - IDENTIQUE à V3"""
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


def get_all_collections():
    """Récupère toutes les collections"""
    all_collections = []
    for ctype in ['custom_collections', 'smart_collections']:
        result = shopify_request(f'{ctype}.json?limit=250')
        if result and ctype in result:
            for c in result[ctype]:
                all_collections.append({
                    'id': c['id'],
                    'handle': c['handle'],
                    'title': c['title']
                })
    return all_collections


# ═══════════════════════════════════════════════════════════════
# MATCHING COLLECTIONS - NOUVEAU V4
# ═══════════════════════════════════════════════════════════════

MODEL_PATTERNS = [
    ('jordan-4', ['jordan 4', 'aj4', 'air jordan 4']),
    ('jordan-1-high', ['jordan 1 high', 'jordan 1 retro high']),
    ('jordan-1-low', ['jordan 1 low']),
    ('jordan-1-mid', ['jordan 1 mid']),
    ('nike-dunk-low', ['dunk low']),
    ('nike-dunk-high', ['dunk high']),
    ('air-force-1', ['air force 1', 'af1']),
    ('nike-p-6000', ['air max', 'p-6000']),
    ('adidas-samba', ['samba']),
    ('adidas-campus', ['campus']),
    ('adidas-gazelle', ['gazelle']),
    ('adidas-spezial', ['spezial']),
    ('adidas-forum', ['forum']),
    ('asics-gel-1130', ['gel-1130', 'gel 1130']),
    ('asics-gel-kayano', ['kayano']),
    ('asics-gel-nyc', ['gel-nyc', 'gel nyc']),
    ('ugg-tasman', ['tasman']),
    ('ugg-tazz', ['tazz']),
    ('new-balance-550', ['new balance 550', '550']),
    ('new-balance-530', ['530']),
    ('new-balance-2002r', ['2002r']),
    ('new-balance-9060', ['9060']),
    ('yeezy-slide', ['yeezy slide']),
    ('yeezy-350', ['yeezy 350']),
    ('yeezy-500', ['yeezy 500']),
    ('yeezy-700', ['yeezy 700']),
    ('yeezy-foam', ['foam runner']),
    ('birkenstock-boston', ['boston']),
]

BRAND_PATTERNS = [
    ('jordan-1', ['jordan', 'air jordan']),
    ('adidas-1', ['adidas', 'yeezy']),
    ('asics-1', ['asics']),
    ('nike', ['nike']),
    ('new-balance', ['new balance']),
    ('ugg', ['ugg']),
    ('birkenstock-1', ['birkenstock']),
    ('puma', ['puma']),
    ('bape', ['bape']),
]

EXCLUDED = ['tout-nos-modeles', 'all', 'best-seller', 'moins-de-150', 'livraison-48h', 'pour-enfants', 'sport', 'autre-marques']


def find_best_collection(title, collections):
    """Trouve la meilleure collection: modèle > marque"""
    if not title or not collections:
        return None
    
    tl = title.lower()
    available = {c['handle']: c['title'] for c in collections if c['handle'] not in EXCLUDED}
    
    # Priorité 1: Modèle
    for handle, patterns in MODEL_PATTERNS:
        if handle in available:
            for p in patterns:
                if p in tl:
                    return {'handle': handle, 'title': available[handle], 'match_type': 'model'}
    
    # Priorité 2: Marque
    for handle, patterns in BRAND_PATTERNS:
        if handle in available:
            for p in patterns:
                if p in tl:
                    return {'handle': handle, 'title': available[handle], 'match_type': 'brand'}
    
    return None


# ═══════════════════════════════════════════════════════════════
# FONCTIONS SEO - BASÉES SUR V3
# ═══════════════════════════════════════════════════════════════

def extract_sku(product):
    if product.get('variants') and len(product['variants']) > 0:
        return product['variants'][0].get('sku', '')
    return ''


def extract_brand(product):
    title = product.get('title', '').lower()
    brands = ['Air Jordan', 'Nike', 'Adidas', 'Yeezy', 'New Balance', 'Asics', 'UGG', 'Puma', 'Birkenstock', 'Converse', 'Vans']
    for brand in brands:
        if brand.lower() in title:
            return brand
    return product.get('vendor', 'Sneakers')


def extract_colorway(product):
    title = product.get('title', '')
    match = re.search(r'\(([^)]+)\)', title)
    if match:
        return match.group(1)
    return ''


def strip_html(html):
    if not html:
        return ''
    clean = re.sub(r'<[^>]+>', ' ', html)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def generate_meta_title(product):
    title = product.get('title', '')
    meta = f"{title} | {SITE_NAME}"
    if len(meta) > 60:
        max_len = 60 - len(f" | {SITE_NAME}") - 3
        meta = f"{title[:max_len]}... | {SITE_NAME}"
    return meta


def generate_meta_description(product):
    title = product.get('title', '')
    sku = extract_sku(product)
    if sku:
        base = f"Achetez la {title} (SKU: {sku}) sur {SITE_NAME}"
    else:
        base = f"Achetez la {title} sur {SITE_NAME}"
    meta = f"{base} ✓ " + " ✓ ".join(BENEFITS) + "."
    if len(meta) > 155:
        meta = meta[:152] + "..."
    return meta


def generate_description(product, collection=None):
    """Génère une description avec lien interne vers la collection"""
    title = product.get('title', '')
    brand = extract_brand(product)
    sku = extract_sku(product)
    colorway = extract_colorway(product)
    
    lines = []
    
    # Paragraphe 1: Intro avec lien collection
    if collection:
        link = f'<a href="https://{SITE_DOMAIN}/collections/{collection["handle"]}">{collection["title"]}</a>'
        lines.append(f'<p>Découvrez la <strong>{title}</strong>, une pièce incontournable de notre collection {link}.</p>')
    else:
        lines.append(f'<p>Découvrez la <strong>{title}</strong>, signée <strong>{brand}</strong>.</p>')
    
    # Paragraphe 2: Description
    if colorway:
        lines.append(f'<p>Cette sneaker arbore le colorway "<strong>{colorway}</strong>". Un design qui allie style et authenticité.</p>')
    else:
        lines.append(f'<p>Un design iconique et des finitions premium, fidèle à l\'héritage {brand}.</p>')
    
    # Paragraphe 3: Infos techniques
    tech = []
    if sku:
        tech.append(f'<strong>SKU</strong> : {sku}')
    if colorway:
        tech.append(f'<strong>Colorway</strong> : {colorway}')
    tech.append(f'<strong>Marque</strong> : {brand}')
    lines.append('<p>' + '<br>'.join(tech) + '</p>')
    
    # Paragraphe 4: Authenticité
    lines.append(f'<p>Chez <strong>{SITE_NAME}</strong>, toutes nos sneakers sont <strong>100% authentiques</strong> et vérifiées par nos experts.</p>')
    
    return '\n'.join(lines)


def check_seo_status(product):
    """Vérifie si le produit a un bon SEO"""
    body = product.get('body_html', '') or ''
    has_desc = len(strip_html(body)) > 100
    has_link = f'{SITE_DOMAIN}/collections/' in body.lower()
    score = (30 if has_desc else 0) + (70 if has_link else 0)
    status = 'complete' if score >= 70 else 'partial' if score >= 30 else 'missing'
    return {'has_description': has_desc, 'has_internal_link': has_link, 'score': score, 'status': status}


def update_product_seo(product_id, updates):
    """Met à jour le SEO d'un produit"""
    success = True
    
    if 'body_html' in updates:
        result = shopify_request(f'products/{product_id}.json', 'PUT', {
            'product': {'id': product_id, 'body_html': updates['body_html']}
        })
        if not result:
            success = False
        time.sleep(0.4)
    
    if 'meta_title' in updates:
        shopify_request(f'products/{product_id}/metafields.json', 'POST', {
            'metafield': {
                'namespace': 'global',
                'key': 'title_tag',
                'value': updates['meta_title'],
                'type': 'single_line_text_field'
            }
        })
        time.sleep(0.3)
    
    if 'meta_description' in updates:
        shopify_request(f'products/{product_id}/metafields.json', 'POST', {
            'metafield': {
                'namespace': 'global',
                'key': 'description_tag',
                'value': updates['meta_description'],
                'type': 'single_line_text_field'
            }
        })
        time.sleep(0.3)
    
    return success


# ═══════════════════════════════════════════════════════════════
# ROUTES - STRUCTURE IDENTIQUE à V3
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def home():
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Shopify Manager V4</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#0a0a0f,#1a1a2e);min-height:100vh;display:flex;align-items:center;justify-content:center;color:#fff}}.c{{text-align:center;padding:40px}}.logo{{font-size:70px;margin-bottom:20px}}h1{{font-size:48px;background:linear-gradient(135deg,#00ff88,#00cc6a);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}.v{{background:linear-gradient(135deg,#8b5cf6,#6d28d9);color:#fff;padding:6px 16px;border-radius:20px;font-size:14px;margin:15px 0 30px;display:inline-block;font-weight:bold}}.btn{{display:inline-block;padding:18px 50px;background:linear-gradient(135deg,#00ff88,#00cc6a);color:#000;text-decoration:none;border-radius:12px;font-size:18px;font-weight:bold;margin:10px}}.status{{margin-top:30px;color:#666;font-size:14px}}</style></head>
<body><div class="c"><div class="logo">🚀</div><h1>Shopify Manager</h1><div class="v">V4 - SEO Pro</div><br><a href="/seo" class="btn">⚡ Gestion SEO</a><div class="status">✅ Connecté à {SHOP}</div></div></body></html>'''


@app.route('/seo')
def seo_page():
    return '''<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>SEO Manager V4</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#0a0a0f;min-height:100vh;color:#fff}
.hd{padding:15px 30px;background:#111;border-bottom:1px solid #333;display:flex;justify-content:space-between;align-items:center}.logo{font-size:20px;font-weight:bold}.logo span{color:#00ff88}.back{color:#888;text-decoration:none}
.stats{display:flex;gap:15px;padding:20px 30px;background:linear-gradient(90deg,rgba(0,255,136,0.05),rgba(139,92,246,0.05));flex-wrap:wrap;align-items:center}.stat{background:rgba(0,0,0,0.3);padding:12px 20px;border-radius:10px;text-align:center}.sv{font-size:24px;font-weight:bold}.sv.g{color:#00ff88}.sv.o{color:#ffa502}.sv.r{color:#ff4757}.sl{font-size:10px;color:#666;margin-top:4px}.sp{background:#00ff88;color:#000;padding:15px 25px;border-radius:10px;font-size:28px;font-weight:bold}
.ctrl{padding:15px 30px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;border-bottom:1px solid #222}.cg input,.cg select{padding:10px;background:#1a1a2e;border:1px solid #333;border-radius:6px;color:#fff}.btn{padding:10px 20px;border:none;border-radius:6px;font-weight:600;cursor:pointer}.btn-p{background:#00ff88;color:#000}.btn-d{background:#ff4757;color:#fff}.btn-s{background:#333;color:#fff}
.prods{padding:20px 30px}.prod{background:#1a1a2e;border:1px solid #333;border-radius:10px;padding:12px 15px;margin-bottom:10px;display:grid;grid-template-columns:30px 60px 1fr 150px 80px 100px;gap:15px;align-items:center}.prod:hover{border-color:#444}
.chk{width:20px;height:20px;border:2px solid #444;border-radius:4px;cursor:pointer;display:flex;align-items:center;justify-content:center}.chk.on{background:#00ff88;border-color:#00ff88}.chk.on::after{content:'✓';color:#000;font-size:12px;font-weight:bold}
.pimg{width:60px;height:60px;border-radius:8px;object-fit:cover;background:#333}.pinfo h3{font-size:13px;margin-bottom:3px}.psku{font-size:10px;color:#666}.pcol{font-size:10px;margin-top:3px}.pcol.m{color:#00ff88}.pcol.b{color:#8b5cf6}.pcol.n{color:#ff4757}
.sst{font-size:11px}.si{margin-bottom:2px}.si.ok{color:#00ff88}.si.ms{color:#ff4757}
.scb{padding:6px 12px;border-radius:15px;font-size:12px;font-weight:bold}.scb.h{background:rgba(0,255,136,0.2);color:#00ff88}.scb.m{background:rgba(255,165,2,0.2);color:#ffa502}.scb.l{background:rgba(255,71,87,0.2);color:#ff4757}
.acts button{padding:6px 10px;font-size:11px;border:none;border-radius:4px;cursor:pointer;margin-right:5px}.acts .v{background:#333;color:#fff}.acts .a{background:#00ff88;color:#000}
.pbar{position:fixed;top:0;left:0;right:0;background:#1a1a2e;padding:20px 30px;z-index:100;display:none;border-bottom:2px solid #00ff88}.pbar.sh{display:block}.ptr{height:8px;background:#333;border-radius:4px;margin:10px 0}.pfl{height:100%;background:#00ff88;border-radius:4px;transition:width 0.3s}
.ld{text-align:center;padding:60px;color:#888}.spin{width:40px;height:40px;border:3px solid #333;border-top-color:#00ff88;border-radius:50%;animation:sp 1s linear infinite;margin:0 auto 15px}@keyframes sp{to{transform:rotate(360deg)}}
.tst{position:fixed;bottom:20px;right:20px;padding:12px 20px;border-radius:8px;z-index:200}.tst.s{background:#00ff88;color:#000}.tst.e{background:#ff4757;color:#fff}
</style></head><body>
<div class="pbar" id="pbar"><div style="display:flex;justify-content:space-between"><strong>Génération SEO...</strong><span id="pct">0/0</span></div><div class="ptr"><div class="pfl" id="pfl"></div></div><div id="ptx" style="font-size:12px;color:#888">Init...</div></div>
<header class="hd"><a href="/" class="back">← Accueil</a><div class="logo">🚀 SEO <span>Manager V4</span></div><div></div></header>
<div class="stats"><div class="stat"><div class="sv g" id="s1">-</div><div class="sl">✅ Complet</div></div><div class="stat"><div class="sv o" id="s2">-</div><div class="sl">⚠️ Partiel</div></div><div class="stat"><div class="sv r" id="s3">-</div><div class="sl">❌ Sans liens</div></div><div class="stat"><div class="sv" id="s4">-</div><div class="sl">Total</div></div><div class="sp" id="s5">-%</div></div>
<div class="ctrl"><div class="cg"><input type="text" id="src" placeholder="Rechercher..."></div><div class="cg"><select id="flt"><option value="all">Tous</option><option value="missing">❌ Sans liens</option><option value="partial">⚠️ Partiel</option><option value="complete">✅ Complet</option></select></div><button class="btn btn-s" onclick="load()">🔄</button><button class="btn btn-p" onclick="aSel()">⚡ Sélection</button><button class="btn btn-d" onclick="aAll()">🚀 TOUT</button><div style="margin-left:auto;color:#888"><strong id="sc">0</strong> sél.</div></div>
<div class="prods" id="prods"><div class="ld"><div class="spin"></div>Chargement...</div></div>
<script>
let P=[],C=[],sel=new Set();

async function load(){
    document.getElementById('prods').innerHTML='<div class="ld"><div class="spin"></div>Chargement...</div>';
    try{
        // Charger produits et collections en parallèle
        const [pRes, cRes] = await Promise.all([
            fetch('/api/products').then(r=>r.json()),
            fetch('/api/collections').then(r=>r.json())
        ]);
        P = pRes.products || [];
        C = cRes.collections || [];
        
        // Calculer stats SEO côté client
        let complete=0, partial=0, missing=0;
        P.forEach(p => {
            const body = p.body_html || '';
            const hasLink = body.toLowerCase().includes('kpshoes.fr/collections/');
            const hasDesc = body.length > 100;
            p.has_link = hasLink;
            p.has_desc = hasDesc;
            p.score = (hasDesc?30:0) + (hasLink?70:0);
            p.status = p.score>=70?'complete':p.score>=30?'partial':'missing';
            p.collection = findCollection(p.title);
            if(p.status==='complete') complete++;
            else if(p.status==='partial') partial++;
            else missing++;
        });
        
        document.getElementById('s1').textContent = complete;
        document.getElementById('s2').textContent = partial;
        document.getElementById('s3').textContent = missing;
        document.getElementById('s4').textContent = P.length;
        document.getElementById('s5').textContent = P.length ? Math.round(complete/P.length*100)+'%' : '0%';
        
        filter();
    }catch(e){
        document.getElementById('prods').innerHTML='<div class="ld">❌ Erreur: '+e.message+'</div>';
    }
}

function findCollection(title){
    if(!title) return null;
    const t = title.toLowerCase();
    const models = [
        ['jordan-4', ['jordan 4','aj4']],
        ['jordan-1-high', ['jordan 1 high']],
        ['jordan-1-low', ['jordan 1 low']],
        ['jordan-1-mid', ['jordan 1 mid']],
        ['adidas-samba', ['samba']],
        ['adidas-campus', ['campus']],
        ['adidas-gazelle', ['gazelle']],
        ['adidas-spezial', ['spezial']],
        ['asics-gel-1130', ['gel-1130','gel 1130']],
        ['asics-gel-kayano', ['kayano']],
        ['ugg-tasman', ['tasman']],
        ['ugg-tazz', ['tazz']],
        ['nike-dunk-low', ['dunk low']],
        ['air-force-1', ['air force 1']],
        ['yeezy-slide', ['yeezy slide']],
    ];
    const brands = [
        ['jordan-1', ['jordan']],
        ['adidas-1', ['adidas']],
        ['asics-1', ['asics']],
        ['nike', ['nike']],
        ['ugg', ['ugg']],
        ['new-balance', ['new balance']],
    ];
    const avail = C.map(c=>c.handle);
    for(let [h,ps] of models){
        if(avail.includes(h)){
            for(let p of ps) if(t.includes(p)) return {handle:h, title:C.find(c=>c.handle===h).title, type:'model'};
        }
    }
    for(let [h,ps] of brands){
        if(avail.includes(h)){
            for(let p of ps) if(t.includes(p)) return {handle:h, title:C.find(c=>c.handle===h).title, type:'brand'};
        }
    }
    return null;
}

function filter(){
    const s=document.getElementById('src').value.toLowerCase();
    const f=document.getElementById('flt').value;
    render(P.filter(p=>{
        if(s && !p.title.toLowerCase().includes(s)) return false;
        if(f==='missing') return p.status==='missing';
        if(f==='partial') return p.status==='partial';
        if(f==='complete') return p.status==='complete';
        return true;
    }));
}

function render(L){
    if(!L.length){document.getElementById('prods').innerHTML='<div class="ld">Aucun produit</div>';return;}
    document.getElementById('prods').innerHTML = L.map(p=>{
        const ck = sel.has(p.id)?'on':'';
        const sc = p.score>=70?'h':p.score>=30?'m':'l';
        let col = '<span class="pcol n">⚠️ Aucune</span>';
        if(p.collection){
            col = '<span class="pcol '+(p.collection.type==='model'?'m':'b')+'">'+(p.collection.type==='model'?'✅':'📁')+' '+esc(p.collection.title)+'</span>';
        }
        const img = p.image?.src || '';
        const sku = p.variants?.[0]?.sku || 'N/A';
        return '<div class="prod"><div class="chk '+ck+'" onclick="tog('+p.id+')"></div><img class="pimg" src="'+img+'" onerror="this.style.background=\'#333\'"><div class="pinfo"><h3>'+esc(p.title.substring(0,40))+(p.title.length>40?'...':'')+'</h3><div class="psku">'+sku+'</div>'+col+'</div><div class="sst"><div class="si '+(p.has_desc?'ok':'ms')+'">'+(p.has_desc?'✅':'❌')+' Desc</div><div class="si '+(p.has_link?'ok':'ms')+'">'+(p.has_link?'✅':'❌')+' Lien</div></div><div class="scb '+sc+'">'+p.score+'%</div><div class="acts"><button class="a" onclick="aOne('+p.id+')">⚡</button></div></div>';
    }).join('');
}

function esc(t){return (t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function tog(id){sel.has(id)?sel.delete(id):sel.add(id);document.getElementById('sc').textContent=sel.size;filter();}

async function aOne(id){
    toast('Application...','s');
    try{
        const r=await fetch('/api/seo/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:id})});
        const d=await r.json();
        if(d.success){toast('✅ OK!','s');load();}else toast('❌ Erreur','e');
    }catch(e){toast('❌ '+e.message,'e');}
}

async function aSel(){
    if(!sel.size){toast('Sélectionnez des produits','e');return;}
    batch(Array.from(sel));
}

async function aAll(){
    if(!confirm('Appliquer à '+P.length+' produits?')) return;
    batch(P.map(p=>p.id));
}

async function batch(ids){
    sPbar();
    try{
        await fetch('/api/seo/batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_ids:ids})});
        mon();
    }catch(e){hPbar();toast('❌ '+e.message,'e');}
}

function mon(){
    const iv=setInterval(async()=>{
        const r=await fetch('/api/progress').then(r=>r.json());
        document.getElementById('pfl').style.width=(r.total?r.current/r.total*100:0)+'%';
        document.getElementById('pct').textContent=r.current+'/'+r.total;
        document.getElementById('ptx').textContent=r.message;
        if(!r.running){clearInterval(iv);hPbar();toast(r.message,'s');sel.clear();document.getElementById('sc').textContent='0';load();}
    },800);
}

function sPbar(){document.getElementById('pbar').classList.add('sh');}
function hPbar(){document.getElementById('pbar').classList.remove('sh');}
function toast(m,t){document.querySelectorAll('.tst').forEach(e=>e.remove());const e=document.createElement('div');e.className='tst '+t;e.textContent=m;document.body.appendChild(e);setTimeout(()=>e.remove(),3000);}

document.getElementById('src').addEventListener('input',filter);
document.getElementById('flt').addEventListener('change',filter);
load();
</script></body></html>'''


# ═══════════════════════════════════════════════════════════════
# API ROUTES - SIMPLES COMME V3
# ═══════════════════════════════════════════════════════════════

@app.route('/api/products')
def api_products():
    """Retourne les produits BRUTS comme V3"""
    products = get_all_products()
    return jsonify({'products': products})


@app.route('/api/collections')
def api_collections():
    """Retourne les collections"""
    collections = get_all_collections()
    return jsonify({'collections': collections})


@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)


@app.route('/api/seo/apply', methods=['POST'])
def api_apply_seo():
    """Applique le SEO à un produit"""
    data = request.json
    product_id = data.get('product_id')
    
    result = shopify_request(f'products/{product_id}.json')
    if not result or 'product' not in result:
        return jsonify({'error': 'Not found'}), 404
    
    product = result['product']
    collections = get_all_collections()
    collection = find_best_collection(product.get('title', ''), collections)
    
    updates = {
        'meta_title': generate_meta_title(product),
        'meta_description': generate_meta_description(product),
        'body_html': generate_description(product, collection)
    }
    
    success = update_product_seo(product_id, updates)
    return jsonify({'success': success, 'collection': collection})


@app.route('/api/seo/batch', methods=['POST'])
def api_batch_seo():
    """Applique le SEO en batch"""
    global task_progress
    
    data = request.json
    product_ids = data.get('product_ids', [])
    
    def process():
        global task_progress
        task_progress = {
            'running': True,
            'current': 0,
            'total': len(product_ids),
            'message': 'Démarrage...',
            'type': 'seo'
        }
        
        collections = get_all_collections()
        
        for i, pid in enumerate(product_ids):
            task_progress['current'] = i + 1
            
            result = shopify_request(f'products/{pid}.json')
            if result and 'product' in result:
                product = result['product']
                task_progress['message'] = f'#{i+1} {product.get("title", "")[:30]}...'
                
                collection = find_best_collection(product.get('title', ''), collections)
                
                updates = {
                    'meta_title': generate_meta_title(product),
                    'meta_description': generate_meta_description(product),
                    'body_html': generate_description(product, collection)
                }
                
                update_product_seo(pid, updates)
            
            time.sleep(1.0)
        
        task_progress['running'] = False
        task_progress['message'] = f'✅ Terminé! {len(product_ids)} produits'
    
    Thread(target=process, daemon=True).start()
    return jsonify({'status': 'started', 'total': len(product_ids)})


if __name__ == '__main__':
    print(f"[V4] Shop: {SHOP}")
    print(f"[V4] Token: {'SET' if ACCESS_TOKEN else 'MISSING!'}")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
