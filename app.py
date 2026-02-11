"""
Shopify Manager V4 - SEO Pro Edition
Avec génération IA, matching collections intelligent, stats SEO
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

SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'
SITE_NAME = os.environ.get('SITE_NAME', 'KP SHOES')
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'kpshoes.fr')
BENEFITS = ["100% Authentique", "Livraison rapide", "Paiement 3x sans frais"]

task_progress = {'running': False, 'current': 0, 'total': 0, 'message': '', 'success_count': 0, 'error_count': 0}
_collections_cache = None
_collections_cache_time = 0

def shopify_request(endpoint, method='GET', data=None):
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    headers = {'X-Shopify-Access-Token': ACCESS_TOKEN, 'Content-Type': 'application/json'}
    try:
        req = Request(url, data=json.dumps(data).encode('utf-8') if data else None, headers=headers, method=method)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with urlopen(req, context=context, timeout=30) as response:
            return True if method == 'DELETE' else json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"[Error] {e}")
        return None

def get_all_products():
    all_products, since_id = [], 0
    while True:
        result = shopify_request(f'products.json?limit=250&since_id={since_id}')
        if result and 'products' in result and result['products']:
            all_products.extend(result['products'])
            since_id = result['products'][-1]['id']
            if len(result['products']) < 250: break
            time.sleep(0.5)
        else: break
    return all_products

def get_all_collections(force_refresh=False):
    global _collections_cache, _collections_cache_time
    if not force_refresh and _collections_cache and (time.time() - _collections_cache_time < 300):
        return _collections_cache
    all_collections = []
    for ctype in ['custom_collections', 'smart_collections']:
        result = shopify_request(f'{ctype}.json?limit=250')
        if result and ctype in result:
            all_collections.extend([{'id': c['id'], 'handle': c['handle'], 'title': c['title']} for c in result[ctype]])
    _collections_cache, _collections_cache_time = all_collections, time.time()
    return all_collections

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
    ('new-balance-550', ['550']),
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

EXCLUDED = ['tout-nos-modeles', 'all', 'best-seller', 'moins-de-150', 'livraison-48h', 'pour-enfants', 'sport', 'autre-marques', 'tous-nos-vetements', 'frontpage']

def find_best_collection(title, collections):
    if not title: return None
    tl = title.lower()
    available = {c['handle']: c['title'] for c in collections if c['handle'] not in EXCLUDED}
    for handle, patterns in MODEL_PATTERNS:
        if handle in available:
            for p in patterns:
                if p in tl: return {'handle': handle, 'title': available[handle], 'match_type': 'model'}
    for handle, patterns in BRAND_PATTERNS:
        if handle in available:
            for p in patterns:
                if p in tl: return {'handle': handle, 'title': available[handle], 'match_type': 'brand'}
    return None

def extract_sku(p): return p['variants'][0].get('sku', '') if p.get('variants') else ''
def extract_brand(p):
    t = p.get('title', '').lower()
    for b, pats in [('Air Jordan', ['jordan']), ('Nike', ['nike', 'dunk']), ('Adidas', ['adidas']), ('Yeezy', ['yeezy']), ('New Balance', ['new balance']), ('Asics', ['asics']), ('UGG', ['ugg']), ('Puma', ['puma']), ('Birkenstock', ['birkenstock'])]:
        for pat in pats:
            if pat in t: return b
    return p.get('vendor', 'Sneakers')
def extract_colorway(p):
    m = re.search(r'\(([^)]+)\)', p.get('title', ''))
    return m.group(1) if m else ''
def strip_html(h): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h or '')).strip()

def generate_meta_title(p):
    t = p.get('title', '')
    m = f"{t} | {SITE_NAME}"
    return m if len(m) <= 60 else f"{t[:60-len(SITE_NAME)-7]}... | {SITE_NAME}"

def generate_meta_description(p):
    t, sku = p.get('title', ''), extract_sku(p)
    base = f"Achetez la {t}" + (f" (SKU: {sku})" if sku else "") + f" sur {SITE_NAME}"
    m = f"{base} ✓ " + " ✓ ".join(BENEFITS) + "."
    return m if len(m) <= 155 else m[:152] + "..."

def generate_description_ai(product, collection):
    title, brand, sku, colorway = product.get('title', ''), extract_brand(product), extract_sku(product), extract_colorway(product)
    lines = []
    if collection:
        link = f'<a href="https://{SITE_DOMAIN}/collections/{collection["handle"]}">{collection["title"]}</a>'
        lines.append(f'<p>Découvrez la <strong>{title}</strong>, une pièce incontournable de notre collection {link}.</p>')
    else:
        lines.append(f'<p>Découvrez la <strong>{title}</strong>, signée <strong>{brand}</strong>.</p>')
    if colorway:
        lines.append(f'<p>Cette sneaker arbore le colorway "<strong>{colorway}</strong>". Un design qui allie style et authenticité.</p>')
    else:
        lines.append(f'<p>Un design iconique et des finitions premium, fidèle à l\'héritage {brand}.</p>')
    tech = [f'<strong>Marque</strong> : {brand}']
    if sku: tech.insert(0, f'<strong>SKU</strong> : {sku}')
    if colorway: tech.insert(1, f'<strong>Colorway</strong> : {colorway}')
    lines.append('<p>' + '<br>'.join(tech) + '</p>')
    lines.append(f'<p>Chez <strong>{SITE_NAME}</strong>, toutes nos sneakers sont <strong>100% authentiques</strong> et vérifiées par nos experts.</p>')
    return '\n'.join(lines)

def check_seo_status(p):
    body = p.get('body_html', '') or ''
    has_desc = len(strip_html(body)) > 100
    has_link = f'{SITE_DOMAIN}/collections/' in body.lower()
    score = (30 if has_desc else 0) + (70 if has_link else 0)
    return {'has_description': has_desc, 'has_internal_link': has_link, 'score': score, 'status': 'complete' if score >= 70 else 'partial' if score >= 30 else 'missing'}

def update_product_seo(pid, updates):
    ok = True
    if 'body_html' in updates:
        if not shopify_request(f'products/{pid}.json', 'PUT', {'product': {'id': pid, 'body_html': updates['body_html']}}): ok = False
        time.sleep(0.4)
    for key, mkey in [('meta_title', 'title_tag'), ('meta_description', 'description_tag')]:
        if key in updates:
            shopify_request(f'products/{pid}/metafields.json', 'POST', {'metafield': {'namespace': 'global', 'key': mkey, 'value': updates[key], 'type': 'single_line_text_field'}})
            time.sleep(0.3)
    return ok

@app.route('/')
def home():
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Shopify Manager V4</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#0a0a0f,#1a1a2e);min-height:100vh;display:flex;align-items:center;justify-content:center;color:#fff}}.c{{text-align:center;padding:40px}}.logo{{font-size:70px;margin-bottom:20px}}h1{{font-size:48px;background:linear-gradient(135deg,#00ff88,#00cc6a);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}.v{{background:linear-gradient(135deg,#8b5cf6,#6d28d9);color:#fff;padding:6px 16px;border-radius:20px;font-size:14px;margin:15px 0 30px;display:inline-block;font-weight:bold}}.btn{{display:inline-block;padding:18px 50px;background:linear-gradient(135deg,#00ff88,#00cc6a);color:#000;text-decoration:none;border-radius:12px;font-size:18px;font-weight:bold}}.status{{margin-top:30px;color:#666;font-size:14px}}</style></head>
<body><div class="c"><div class="logo">🚀</div><h1>Shopify Manager</h1><div class="v">V4 - SEO Pro + IA</div><a href="/seo" class="btn">⚡ Gestion SEO</a><div class="status">✅ Connecté à {SHOP}</div></div></body></html>'''

@app.route('/seo')
def seo_page():
    return '''<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>SEO Manager V4</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#0a0a0f;min-height:100vh;color:#fff}
.hd{padding:15px 30px;background:#111;border-bottom:1px solid #333;display:flex;justify-content:space-between;align-items:center}.logo{font-size:20px;font-weight:bold}.logo span{background:linear-gradient(135deg,#00ff88,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.back{color:#888;text-decoration:none}
.stats{display:flex;gap:20px;padding:20px 30px;background:linear-gradient(90deg,rgba(0,255,136,0.05),rgba(139,92,246,0.05));border-bottom:1px solid #222;flex-wrap:wrap;align-items:center}.stat{background:rgba(0,0,0,0.3);padding:15px 25px;border-radius:12px;text-align:center;min-width:100px}.sv{font-size:28px;font-weight:bold}.sv.g{color:#00ff88}.sv.o{color:#ffa502}.sv.r{color:#ff4757}.sv.p{color:#8b5cf6}.sl{font-size:10px;color:#666;margin-top:5px;text-transform:uppercase}.sp{background:linear-gradient(135deg,#00ff88,#00cc6a);color:#000;padding:20px 30px;border-radius:12px;font-size:32px;font-weight:bold}
.ctrl{padding:20px 30px;display:flex;gap:15px;flex-wrap:wrap;align-items:flex-end;border-bottom:1px solid #222}.cg{display:flex;flex-direction:column;gap:5px}.cg label{font-size:10px;color:#666;text-transform:uppercase}.cg input,.cg select{padding:10px 14px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#fff;font-size:14px;min-width:180px}
.btn{padding:12px 24px;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;transition:all 0.2s}.btn:hover{transform:translateY(-2px)}.btn-p{background:linear-gradient(135deg,#00ff88,#00cc6a);color:#000}.btn-d{background:linear-gradient(135deg,#ff4757,#ff3344);color:#fff}.btn-s{background:#333;color:#fff}
.fs{display:flex;gap:10px;align-items:center;background:#1a1a2e;padding:8px 15px;border-radius:8px;border:1px solid #333}.fs label{font-size:12px;display:flex;align-items:center;gap:6px;cursor:pointer}.fs input{width:16px;height:16px;accent-color:#00ff88}
.si{margin-left:auto;background:#1a1a2e;padding:10px 20px;border-radius:8px;font-size:13px}.si strong{color:#8b5cf6;font-size:18px}
.prods{padding:20px 30px;display:flex;flex-direction:column;gap:12px}
.prod{background:#1a1a2e;border:1px solid #2a2a3a;border-radius:12px;padding:15px 20px;display:grid;grid-template-columns:35px 70px 1fr 180px 100px 120px;gap:20px;align-items:center;transition:all 0.2s}.prod:hover{border-color:#444}.prod.sel{border-color:#8b5cf6;background:rgba(139,92,246,0.1)}
.chk{width:24px;height:24px;border:2px solid #444;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center}.chk.on{background:#00ff88;border-color:#00ff88}.chk.on::after{content:'✓';color:#000;font-weight:bold}
.pimg{width:70px;height:70px;border-radius:10px;object-fit:cover;background:#333}
.pinfo h3{font-size:14px;font-weight:600;margin-bottom:5px}.psku{font-size:11px;color:#666;font-family:monospace;margin-bottom:4px}.pcol{font-size:11px;padding:3px 8px;border-radius:4px;display:inline-block}.pcol.m{background:rgba(0,255,136,0.2);color:#00ff88}.pcol.b{background:rgba(139,92,246,0.2);color:#8b5cf6}.pcol.n{background:rgba(255,71,87,0.2);color:#ff4757}
.sst{font-size:12px}.si2{display:flex;align-items:center;gap:6px;margin-bottom:4px}.si2.ok{color:#00ff88}.si2.ms{color:#ff4757}
.scb{display:inline-block;padding:8px 16px;border-radius:20px;font-weight:bold;font-size:14px}.scb.h{background:rgba(0,255,136,0.2);color:#00ff88}.scb.md{background:rgba(255,165,2,0.2);color:#ffa502}.scb.l{background:rgba(255,71,87,0.2);color:#ff4757}
.acts{display:flex;gap:8px}.abtn{padding:8px 12px;font-size:12px;border:none;border-radius:6px;cursor:pointer}.abtn.v{background:#333;color:#fff}.abtn.a{background:#00ff88;color:#000}
.pov{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);display:none;align-items:center;justify-content:center;z-index:1000}.pov.sh{display:flex}.pbox{background:#1a1a2e;padding:40px;border-radius:16px;width:500px;text-align:center}.pbox h2{margin-bottom:20px}.ptr{height:12px;background:#333;border-radius:6px;overflow:hidden;margin-bottom:15px}.pfl{height:100%;background:linear-gradient(90deg,#00ff88,#8b5cf6);transition:width 0.3s}.ptx{color:#888;font-size:14px}.pct{font-size:24px;font-weight:bold;color:#00ff88;margin-top:10px}
.mov{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);display:none;align-items:center;justify-content:center;z-index:1000;padding:20px}.mov.sh{display:flex}.mod{background:#1a1a2e;border-radius:16px;width:100%;max-width:800px;max-height:90vh;overflow:hidden}.mhd{padding:20px;border-bottom:1px solid #333;display:flex;justify-content:space-between;align-items:center}.mhd h2{font-size:18px}.mx{background:none;border:none;color:#888;font-size:28px;cursor:pointer}.mbd{padding:20px;overflow-y:auto;max-height:60vh}.mft{padding:20px;border-top:1px solid #333;display:flex;gap:10px;justify-content:flex-end}
.psec{margin-bottom:20px}.psec h4{font-size:13px;color:#888;margin-bottom:10px}.pcur{background:#0a0a0f;padding:12px;border-radius:8px;font-size:12px;color:#888;border-left:3px solid #444;margin-bottom:8px}.pgen{background:#0a0a0f;padding:12px;border-radius:8px;font-size:12px;color:#00ff88;border-left:3px solid #00ff88}.pgen pre{white-space:pre-wrap;font-family:inherit}
.tst{position:fixed;bottom:30px;right:30px;padding:15px 25px;border-radius:10px;font-weight:500;z-index:2000;animation:sIn 0.3s}.tst.s{background:#00ff88;color:#000}.tst.e{background:#ff4757;color:#fff}@keyframes sIn{from{transform:translateX(100px);opacity:0}to{transform:translateX(0);opacity:1}}
.ld{text-align:center;padding:60px}.spin{width:50px;height:50px;border:4px solid #333;border-top-color:#00ff88;border-radius:50%;animation:sp 1s linear infinite;margin:0 auto 20px}@keyframes sp{to{transform:rotate(360deg)}}
</style></head><body>
<div class="pov" id="pov"><div class="pbox"><h2>⚡ Génération SEO...</h2><div class="ptr"><div class="pfl" id="pfl"></div></div><div class="ptx" id="ptx">Init...</div><div class="pct" id="pct">0/0</div></div></div>
<div class="mov" id="mov"><div class="mod"><div class="mhd"><h2 id="mt">Aperçu</h2><button class="mx" onclick="cMod()">×</button></div><div class="mbd" id="mbd"></div><div class="mft"><button class="btn btn-s" onclick="cMod()">Fermer</button><button class="btn btn-p" onclick="aMod()">✅ Appliquer</button></div></div></div>
<header class="hd"><a href="/" class="back">← Accueil</a><div class="logo">🚀 SEO <span>Manager V4</span></div><div></div></header>
<div class="stats"><div class="stat"><div class="sv g" id="s1">-</div><div class="sl">✅ Complet</div></div><div class="stat"><div class="sv o" id="s2">-</div><div class="sl">⚠️ Partiel</div></div><div class="stat"><div class="sv r" id="s3">-</div><div class="sl">❌ Sans liens</div></div><div class="stat"><div class="sv" id="s4">-</div><div class="sl">Total</div></div><div class="stat"><div class="sv p" id="s5">-</div><div class="sl">Collections</div></div><div class="sp" id="s6">-%</div></div>
<div class="ctrl"><div class="cg"><label>Rechercher</label><input type="text" id="src" placeholder="Nom, SKU..."></div><div class="cg"><label>Filtrer</label><select id="flt"><option value="all">Tous</option><option value="missing">❌ Sans liens</option><option value="partial">⚠️ Partiel</option><option value="complete">✅ Complet</option></select></div><div class="fs"><span style="font-size:11px;color:#888">Appliquer:</span><label><input type="checkbox" id="ft"> Title</label><label><input type="checkbox" id="fd"> Desc</label><label><input type="checkbox" id="fb" checked> Body</label></div><button class="btn btn-s" onclick="load()">🔄</button><button class="btn btn-p" onclick="aSel()">⚡ Sélection</button><button class="btn btn-d" onclick="aAll()">🚀 TOUT LE SITE</button><div class="si"><strong id="sc">0</strong> sélectionné(s)</div></div>
<div class="prods" id="prods"><div class="ld"><div class="spin"></div><p>Chargement...</p></div></div>
<script>
let P=[],C=[],sel=new Set(),curId=null;
async function load(){
    document.getElementById('prods').innerHTML='<div class="ld"><div class="spin"></div><p>Chargement...</p></div>';
    try{
        const r=await fetch('/api/products');const d=await r.json();
        P=d.products||[];C=d.collections||[];
        document.getElementById('s1').textContent=d.stats.complete;
        document.getElementById('s2').textContent=d.stats.partial;
        document.getElementById('s3').textContent=d.stats.missing;
        document.getElementById('s4').textContent=d.stats.total;
        document.getElementById('s5').textContent=C.length;
        document.getElementById('s6').textContent=d.stats.percent_complete+'%';
        filter();
    }catch(e){document.getElementById('prods').innerHTML='<div class="ld">❌ '+e.message+'</div>';}
}
function filter(){
    const s=document.getElementById('src').value.toLowerCase(),f=document.getElementById('flt').value;
    render(P.filter(p=>{
        if(s&&!p.title.toLowerCase().includes(s)&&!(p.sku||'').toLowerCase().includes(s))return false;
        if(f==='missing')return p.seo_status==='missing';
        if(f==='partial')return p.seo_status==='partial';
        if(f==='complete')return p.seo_status==='complete';
        return true;
    }));
}
function render(L){
    const el=document.getElementById('prods');
    if(!L.length){el.innerHTML='<div class="ld">Aucun produit</div>';return;}
    el.innerHTML=L.map(p=>{
        const ck=sel.has(p.id)?'on':'',sc=p.seo_score>=70?'h':p.seo_score>=30?'md':'l';
        let cc='n',ct='⚠️ Aucune';
        if(p.collection){cc=p.collection.match_type==='model'?'m':'b';ct=(p.collection.match_type==='model'?'✅ ':'📁 ')+p.collection.title;}
        return '<div class="prod'+(sel.has(p.id)?' sel':'')+'"><div class="chk '+ck+'" onclick="tog('+p.id+')"></div><img class="pimg" src="'+(p.image||'')+'" onerror="this.style.background=\'#333\'"><div class="pinfo"><h3>'+esc(p.title.substring(0,45))+(p.title.length>45?'...':'')+'</h3><div class="psku">SKU: '+(p.sku||'N/A')+'</div><div class="pcol '+cc+'">'+ct+'</div></div><div class="sst"><div class="si2 '+(p.has_description?'ok':'ms')+'">'+(p.has_description?'✅':'❌')+' Description</div><div class="si2 '+(p.has_internal_link?'ok':'ms')+'">'+(p.has_internal_link?'✅':'❌')+' Lien interne</div></div><div class="scb '+sc+'">'+p.seo_score+'%</div><div class="acts"><button class="abtn v" onclick="view('+p.id+')">👁️</button><button class="abtn a" onclick="aOne('+p.id+')">⚡</button></div></div>';
    }).join('');
}
function esc(t){return (t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function tog(id){sel.has(id)?sel.delete(id):sel.add(id);document.getElementById('sc').textContent=sel.size;filter();}
function gF(){const f=[];if(document.getElementById('ft').checked)f.push('meta_title');if(document.getElementById('fd').checked)f.push('meta_description');if(document.getElementById('fb').checked)f.push('body_html');return f;}
async function view(id){
    curId=id;document.getElementById('mbd').innerHTML='<div class="ld"><div class="spin"></div></div>';document.getElementById('mov').classList.add('sh');
    try{
        const r=await fetch('/api/product/'+id+'/preview');const d=await r.json();
        document.getElementById('mt').textContent=d.product.title;
        let h='<p style="margin-bottom:15px"><strong>Collection:</strong> '+(d.collection?(d.collection.match_type==='model'?'✅ Modèle':'📁 Marque')+' - '+esc(d.collection.title):'<span style="color:#ff4757">⚠️ Aucune</span>')+'</p>';
        h+='<div class="psec"><h4>Meta Title</h4><div class="pgen">'+esc(d.generated.meta_title)+'</div></div>';
        h+='<div class="psec"><h4>Meta Description</h4><div class="pgen">'+esc(d.generated.meta_description)+'</div></div>';
        h+='<div class="psec"><h4>Description '+(d.seo_status.has_internal_link?'<span style="color:#00ff88">✅ Lien OK</span>':'<span style="color:#ff4757">❌ Sans lien</span>')+'</h4>';
        if(d.current_body)h+='<div class="pcur"><strong>Actuel:</strong> '+esc(d.current_body.substring(0,150))+'...</div>';
        h+='<div class="pgen"><pre>'+esc(d.generated.body_html)+'</pre></div></div>';
        document.getElementById('mbd').innerHTML=h;
    }catch(e){document.getElementById('mbd').innerHTML='<div class="ld">❌ '+e.message+'</div>';}
}
function cMod(){document.getElementById('mov').classList.remove('sh');curId=null;}
async function aMod(){if(!curId)return;cMod();await aOne(curId);}
async function aOne(id){
    const f=gF();if(!f.length){toast('Cochez un champ','e');return;}
    toast('Application...','s');
    try{
        const r=await fetch('/api/seo/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:id,fields:f})});
        const d=await r.json();
        if(d.success){toast('✅ SEO appliqué!','s');load();}else toast('❌ Erreur','e');
    }catch(e){toast('❌ '+e.message,'e');}
}
async function aSel(){if(!sel.size){toast('Sélectionnez des produits','e');return;}const f=gF();if(!f.length){toast('Cochez un champ','e');return;}batch(Array.from(sel),f);}
async function aAll(){const f=gF();if(!f.length){toast('Cochez un champ','e');return;}if(!confirm('Appliquer à '+P.length+' produits?'))return;batch(P.map(p=>p.id),f);}
async function batch(ids,f){
    sPov();
    try{await fetch('/api/seo/batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_ids:ids,fields:f})});mon();}
    catch(e){hPov();toast('❌ '+e.message,'e');}
}
function mon(){
    const iv=setInterval(async()=>{
        try{
            const r=await fetch('/api/progress');const p=await r.json();
            document.getElementById('pfl').style.width=(p.total>0?p.current/p.total*100:0)+'%';
            document.getElementById('ptx').textContent=p.message;
            document.getElementById('pct').textContent=p.current+'/'+p.total;
            if(!p.running){clearInterval(iv);hPov();toast(p.message,'s');sel.clear();document.getElementById('sc').textContent='0';load();}
        }catch(e){}
    },800);
}
function sPov(){document.getElementById('pov').classList.add('sh');}
function hPov(){document.getElementById('pov').classList.remove('sh');}
function toast(m,t){document.querySelectorAll('.tst').forEach(e=>e.remove());const e=document.createElement('div');e.className='tst '+t;e.textContent=m;document.body.appendChild(e);setTimeout(()=>e.remove(),4000);}
document.getElementById('src').addEventListener('input',filter);
document.getElementById('flt').addEventListener('change',filter);
load();
</script></body></html>'''

@app.route('/api/products')
def api_products():
    products, collections = get_all_products(), get_all_collections()
    result, stats = [], {'complete': 0, 'partial': 0, 'missing': 0, 'total': 0}
    for p in products:
        seo = check_seo_status(p)
        col = find_best_collection(p.get('title', ''), collections)
        stats['total'] += 1
        stats[seo['status']] += 1
        result.append({'id': p['id'], 'title': p['title'], 'handle': p['handle'], 'image': (p.get('image') or {}).get('src'), 'sku': extract_sku(p), 'collection': col, 'seo_score': seo['score'], 'seo_status': seo['status'], 'has_description': seo['has_description'], 'has_internal_link': seo['has_internal_link']})
    stats['percent_complete'] = round(stats['complete'] / stats['total'] * 100, 1) if stats['total'] else 0
    return jsonify({'products': result, 'collections': [{'handle': c['handle'], 'title': c['title']} for c in collections], 'stats': stats})

@app.route('/api/product/<int:pid>/preview')
def api_preview(pid):
    r = shopify_request(f'products/{pid}.json')
    if not r: return jsonify({'error': 'Not found'}), 404
    p = r['product']
    cols = get_all_collections()
    col = find_best_collection(p.get('title', ''), cols)
    seo = check_seo_status(p)
    return jsonify({'product': {'id': p['id'], 'title': p['title'], 'sku': extract_sku(p)}, 'collection': col, 'seo_status': seo, 'current_body': strip_html(p.get('body_html', ''))[:500], 'generated': {'meta_title': generate_meta_title(p), 'meta_description': generate_meta_description(p), 'body_html': generate_description_ai(p, col)}})

@app.route('/api/seo/apply', methods=['POST'])
def api_apply():
    data = request.json
    pid, fields = data.get('product_id'), data.get('fields', ['body_html'])
    r = shopify_request(f'products/{pid}.json')
    if not r: return jsonify({'error': 'Not found'}), 404
    p = r['product']
    col = find_best_collection(p.get('title', ''), get_all_collections())
    updates = {}
    if 'meta_title' in fields: updates['meta_title'] = generate_meta_title(p)
    if 'meta_description' in fields: updates['meta_description'] = generate_meta_description(p)
    if 'body_html' in fields: updates['body_html'] = generate_description_ai(p, col)
    return jsonify({'success': update_product_seo(pid, updates), 'collection': col})

@app.route('/api/seo/batch', methods=['POST'])
def api_batch():
    global task_progress
    data = request.json
    pids, fields = data.get('product_ids', []), data.get('fields', ['body_html'])
    def process():
        global task_progress
        task_progress = {'running': True, 'current': 0, 'total': len(pids), 'message': 'Chargement...', 'success_count': 0, 'error_count': 0}
        cols = get_all_collections(True)
        for i, pid in enumerate(pids):
            task_progress['current'] = i + 1
            r = shopify_request(f'products/{pid}.json')
            if r and 'product' in r:
                p = r['product']
                task_progress['message'] = f'#{i+1}/{len(pids)} {p.get("title","")[:30]}...'
                col = find_best_collection(p.get('title', ''), cols)
                updates = {}
                if 'meta_title' in fields: updates['meta_title'] = generate_meta_title(p)
                if 'meta_description' in fields: updates['meta_description'] = generate_meta_description(p)
                if 'body_html' in fields: updates['body_html'] = generate_description_ai(p, col)
                if updates and update_product_seo(pid, updates): task_progress['success_count'] += 1
                else: task_progress['error_count'] += 1
            else: task_progress['error_count'] += 1
            time.sleep(1.0)
        task_progress['running'] = False
        task_progress['message'] = f"✅ Terminé! {task_progress['success_count']} OK, {task_progress['error_count']} erreurs"
    Thread(target=process, daemon=True).start()
    return jsonify({'status': 'started', 'total': len(pids)})

@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)

@app.route('/api/collections')
def api_collections():
    c = get_all_collections(True)
    return jsonify({'collections': c, 'count': len(c)})

if __name__ == '__main__':
    print(f"[V4] Shop: {SHOP}, Token: {'OK' if ACCESS_TOKEN else 'MISSING'}")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
