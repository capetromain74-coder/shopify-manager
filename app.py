"""
Shopify Manager V4 - SEO Pro Edition
Basé sur V3 + retry/timeout améliorés + fonctionnalités SEO
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

task_progress = {'running': False, 'current': 0, 'total': 0, 'message': ''}

# Cache produits pour éviter les requêtes répétées
_products_cache = None
_products_cache_time = 0
_collections_cache = None


def shopify_request(endpoint, method='GET', data=None, retries=3):
    """Requête Shopify avec retry automatique"""
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    headers = {'X-Shopify-Access-Token': ACCESS_TOKEN, 'Content-Type': 'application/json'}
    
    for attempt in range(retries):
        try:
            if data:
                req = Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method=method)
            else:
                req = Request(url, headers=headers, method=method)
            
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with urlopen(req, context=context, timeout=45) as response:
                if method == 'DELETE':
                    return True
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"[Attempt {attempt+1}/{retries}] Error: {e}")
            if attempt < retries - 1:
                time.sleep(1)
            else:
                return None
    return None


def get_all_products(use_cache=True):
    """Récupère tous les produits avec cache de 2 minutes"""
    global _products_cache, _products_cache_time
    
    # Utiliser le cache si disponible et récent
    if use_cache and _products_cache and (time.time() - _products_cache_time < 120):
        print(f"[Cache] Retour de {len(_products_cache)} produits depuis le cache")
        return _products_cache
    
    all_products = []
    since_id = 0
    
    while True:
        result = shopify_request(f'products.json?limit=250&since_id={since_id}')
        
        if result and 'products' in result and len(result['products']) > 0:
            all_products.extend(result['products'])
            since_id = result['products'][-1]['id']
            print(f"[API] {len(all_products)} produits...")
            
            if len(result['products']) < 250:
                break
            time.sleep(0.5)
        else:
            break
    
    if all_products:
        _products_cache = all_products
        _products_cache_time = time.time()
    
    return all_products


def get_all_collections():
    """Récupère toutes les collections avec cache"""
    global _collections_cache
    
    if _collections_cache:
        return _collections_cache
    
    all_collections = []
    for ctype in ['custom_collections', 'smart_collections']:
        result = shopify_request(f'{ctype}.json?limit=250')
        if result and ctype in result:
            for c in result[ctype]:
                all_collections.append({'id': c['id'], 'handle': c['handle'], 'title': c['title']})
    
    _collections_cache = all_collections
    return all_collections


# Matching collections
MODEL_PATTERNS = [
    ('jordan-4', ['jordan 4', 'aj4']), ('jordan-1-high', ['jordan 1 high']), ('jordan-1-low', ['jordan 1 low']), ('jordan-1-mid', ['jordan 1 mid']),
    ('adidas-samba', ['samba']), ('adidas-campus', ['campus']), ('adidas-gazelle', ['gazelle']), ('adidas-spezial', ['spezial']), ('adidas-forum', ['forum']),
    ('asics-gel-1130', ['gel-1130', 'gel 1130']), ('asics-gel-kayano', ['kayano']), ('asics-gel-nyc', ['gel-nyc']),
    ('ugg-tasman', ['tasman']), ('ugg-tazz', ['tazz']),
    ('nike-dunk-low', ['dunk low']), ('nike-dunk-high', ['dunk high']), ('air-force-1', ['air force 1', 'af1']), ('nike-p-6000', ['air max']),
    ('new-balance-550', ['550']), ('new-balance-530', ['530']), ('new-balance-2002r', ['2002r']), ('new-balance-9060', ['9060']),
    ('yeezy-slide', ['yeezy slide']), ('yeezy-350', ['yeezy 350']), ('yeezy-500', ['yeezy 500']),
    ('birkenstock-boston', ['boston']),
]
BRAND_PATTERNS = [
    ('jordan-1', ['jordan']), ('adidas-1', ['adidas']), ('asics-1', ['asics']), ('nike', ['nike']),
    ('new-balance', ['new balance']), ('ugg', ['ugg']), ('birkenstock-1', ['birkenstock']), ('puma', ['puma']), ('bape', ['bape']),
]
EXCLUDED = ['tout-nos-modeles', 'all', 'best-seller', 'moins-de-150', 'livraison-48h', 'pour-enfants', 'sport', 'autre-marques']


def find_best_collection(title, collections):
    if not title: return None
    tl = title.lower()
    avail = {c['handle']: c['title'] for c in collections if c['handle'] not in EXCLUDED}
    for h, ps in MODEL_PATTERNS:
        if h in avail:
            for p in ps:
                if p in tl: return {'handle': h, 'title': avail[h], 'type': 'model'}
    for h, ps in BRAND_PATTERNS:
        if h in avail:
            for p in ps:
                if p in tl: return {'handle': h, 'title': avail[h], 'type': 'brand'}
    return None


def extract_sku(p): return p['variants'][0].get('sku', '') if p.get('variants') else ''
def extract_brand(p):
    t = p.get('title', '').lower()
    for b, ps in [('Air Jordan', ['jordan']), ('Nike', ['nike']), ('Adidas', ['adidas']), ('Yeezy', ['yeezy']), ('New Balance', ['new balance']), ('Asics', ['asics']), ('UGG', ['ugg']), ('Puma', ['puma'])]:
        for pat in ps:
            if pat in t: return b
    return p.get('vendor', 'Sneakers')
def extract_colorway(p):
    m = re.search(r'\(([^)]+)\)', p.get('title', ''))
    return m.group(1) if m else ''
def strip_html(h): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h or '')).strip()


def generate_meta_title(p):
    t = p.get('title', '')
    m = f"{t} | {SITE_NAME}"
    return m if len(m) <= 60 else f"{t[:50]}... | {SITE_NAME}"

def generate_meta_description(p):
    t, sku = p.get('title', ''), extract_sku(p)
    base = f"Achetez {t}" + (f" ({sku})" if sku else "") + f" sur {SITE_NAME}"
    m = f"{base} ✓ " + " ✓ ".join(BENEFITS)
    return m if len(m) <= 155 else m[:152] + "..."

def generate_description(product, collection):
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
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#0a0a0f,#1a1a2e);min-height:100vh;display:flex;align-items:center;justify-content:center;color:#fff}}.c{{text-align:center;padding:40px}}h1{{font-size:42px;color:#00ff88;margin-bottom:10px}}.v{{color:#8b5cf6;margin-bottom:30px}}.btn{{display:inline-block;padding:15px 40px;background:#00ff88;color:#000;text-decoration:none;border-radius:10px;font-weight:bold;margin:10px}}.st{{margin-top:20px;color:#666}}</style></head>
<body><div class="c"><h1>🚀 Shopify Manager</h1><div class="v">V4 - SEO Pro</div><a href="/seo" class="btn">⚡ Gestion SEO</a><div class="st">✅ {SHOP}</div></div></body></html>'''


@app.route('/seo')
def seo_page():
    return '''<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SEO Manager V4</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#0a0a0f;color:#fff;min-height:100vh}
.hd{padding:15px 20px;background:#111;border-bottom:1px solid #333;display:flex;justify-content:space-between;align-items:center}.logo{font-size:18px;font-weight:bold;color:#00ff88}.back{color:#666;text-decoration:none}
.stats{display:flex;gap:10px;padding:15px 20px;background:#111;flex-wrap:wrap}.stat{background:#1a1a2e;padding:12px 18px;border-radius:8px;text-align:center}.sv{font-size:22px;font-weight:bold}.sv.g{color:#00ff88}.sv.o{color:#ffa500}.sv.r{color:#ff4757}.sl{font-size:9px;color:#666;margin-top:3px}.pct{background:#00ff88;color:#000;padding:12px 20px;border-radius:8px;font-size:24px;font-weight:bold}
.ctrl{padding:12px 20px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;border-bottom:1px solid #222}input,select{padding:8px 12px;background:#1a1a2e;border:1px solid #333;border-radius:6px;color:#fff}
.btn{padding:8px 16px;border:none;border-radius:6px;font-weight:600;cursor:pointer}.btn-g{background:#00ff88;color:#000}.btn-r{background:#ff4757;color:#fff}.btn-s{background:#333;color:#fff}
.info{margin-left:auto;color:#666;font-size:13px}
.list{padding:15px 20px}
.item{background:#1a1a2e;border:1px solid #2a2a3a;border-radius:8px;padding:12px;margin-bottom:8px;display:grid;grid-template-columns:28px 55px 1fr 130px 70px 90px;gap:12px;align-items:center}.item:hover{border-color:#444}
.ck{width:20px;height:20px;border:2px solid #444;border-radius:4px;cursor:pointer;display:flex;align-items:center;justify-content:center}.ck.on{background:#00ff88;border-color:#00ff88}.ck.on::after{content:'✓';color:#000;font-size:11px}
.img{width:55px;height:55px;border-radius:6px;object-fit:cover;background:#333}
.inf h3{font-size:12px;margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sku{font-size:9px;color:#666}.col{font-size:9px;margin-top:2px}.col.m{color:#00ff88}.col.b{color:#8b5cf6}.col.n{color:#ff4757}
.seo{font-size:10px}.si{margin-bottom:2px}.si.ok{color:#00ff88}.si.no{color:#ff4757}
.sc{padding:5px 10px;border-radius:12px;font-size:11px;font-weight:bold}.sc.h{background:rgba(0,255,136,0.15);color:#00ff88}.sc.m{background:rgba(255,165,0,0.15);color:#ffa500}.sc.l{background:rgba(255,71,87,0.15);color:#ff4757}
.acts button{padding:5px 10px;font-size:10px;border:none;border-radius:4px;cursor:pointer;background:#00ff88;color:#000}
.bar{position:fixed;top:0;left:0;right:0;background:#1a1a2e;padding:15px 20px;z-index:100;display:none;border-bottom:2px solid #00ff88}.bar.on{display:block}.trk{height:6px;background:#333;border-radius:3px;margin:8px 0}.fill{height:100%;background:#00ff88;border-radius:3px;transition:width 0.3s}
.ld{text-align:center;padding:50px;color:#666}.sp{width:35px;height:35px;border:3px solid #333;border-top-color:#00ff88;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 10px}@keyframes spin{to{transform:rotate(360deg)}}
.tst{position:fixed;bottom:20px;right:20px;padding:10px 18px;border-radius:6px;font-size:13px;z-index:200}.tst.s{background:#00ff88;color:#000}.tst.e{background:#ff4757;color:#fff}
.err{background:#ff4757;color:#fff;padding:15px;border-radius:8px;margin:20px;text-align:center}
.retry{margin-top:10px;padding:8px 20px;background:#fff;color:#ff4757;border:none;border-radius:6px;cursor:pointer;font-weight:bold}
</style></head><body>
<div class="bar" id="bar"><div style="display:flex;justify-content:space-between;font-size:13px"><span>⚡ Génération SEO...</span><span id="cnt">0/0</span></div><div class="trk"><div class="fill" id="fill"></div></div><div id="msg" style="font-size:11px;color:#888">Init...</div></div>
<header class="hd"><a href="/" class="back">← Retour</a><div class="logo">🚀 SEO Manager V4</div><div></div></header>
<div class="stats"><div class="stat"><div class="sv g" id="st1">-</div><div class="sl">COMPLET</div></div><div class="stat"><div class="sv o" id="st2">-</div><div class="sl">PARTIEL</div></div><div class="stat"><div class="sv r" id="st3">-</div><div class="sl">SANS LIENS</div></div><div class="stat"><div class="sv" id="st4">-</div><div class="sl">TOTAL</div></div><div class="pct" id="pct">-%</div></div>
<div class="ctrl"><input type="text" id="q" placeholder="Rechercher..."><select id="f"><option value="">Tous</option><option value="missing">❌ Sans liens</option><option value="partial">⚠️ Partiel</option><option value="complete">✅ Complet</option></select><button class="btn btn-s" onclick="load()">🔄</button><button class="btn btn-g" onclick="doSel()">⚡ Sélection</button><button class="btn btn-r" onclick="doAll()">🚀 TOUT</button><div class="info"><strong id="selc">0</strong> sél.</div></div>
<div class="list" id="list"><div class="ld"><div class="sp"></div>Chargement...</div></div>
<script>
let P=[],C=[],sel=new Set(),loading=false;

async function load(){
    if(loading) return;
    loading = true;
    document.getElementById('list').innerHTML='<div class="ld"><div class="sp"></div>Chargement des produits...</div>';
    
    try{
        // Retry jusqu'à 3 fois avec délai
        let data = null;
        for(let i=0; i<3; i++){
            try{
                const controller = new AbortController();
                const timeout = setTimeout(() => controller.abort(), 60000);
                const r = await fetch('/api/products', {signal: controller.signal});
                clearTimeout(timeout);
                data = await r.json();
                if(data.products) break;
            }catch(e){
                console.log('Tentative '+(i+1)+' échouée:', e);
                if(i < 2) await new Promise(r => setTimeout(r, 2000));
            }
        }
        
        if(!data || !data.products){
            throw new Error('Impossible de charger les produits');
        }
        
        P = data.products;
        C = data.collections || [];
        
        // Calcul stats côté client
        let c1=0,c2=0,c3=0;
        P.forEach(p => {
            const b = (p.body_html||'').toLowerCase();
            p._link = b.includes('kpshoes.fr/collections/');
            p._desc = (p.body_html||'').length > 100;
            p._score = (p._desc?30:0)+(p._link?70:0);
            p._status = p._score>=70?'complete':p._score>=30?'partial':'missing';
            p._col = findCol(p.title);
            if(p._status==='complete')c1++;else if(p._status==='partial')c2++;else c3++;
        });
        
        document.getElementById('st1').textContent=c1;
        document.getElementById('st2').textContent=c2;
        document.getElementById('st3').textContent=c3;
        document.getElementById('st4').textContent=P.length;
        document.getElementById('pct').textContent=P.length?Math.round(c1/P.length*100)+'%':'0%';
        
        filter();
    }catch(e){
        document.getElementById('list').innerHTML='<div class="err">❌ '+e.message+'<br><button class="retry" onclick="load()">🔄 Réessayer</button></div>';
    }
    loading = false;
}

function findCol(t){
    if(!t||!C.length)return null;
    t=t.toLowerCase();
    const models=[['jordan-4',['jordan 4']],['jordan-1-high',['jordan 1 high']],['jordan-1-low',['jordan 1 low']],['jordan-1-mid',['jordan 1 mid']],['adidas-samba',['samba']],['adidas-campus',['campus']],['adidas-gazelle',['gazelle']],['adidas-spezial',['spezial']],['asics-gel-1130',['gel-1130','gel 1130']],['ugg-tasman',['tasman']],['ugg-tazz',['tazz']],['nike-dunk-low',['dunk low']],['air-force-1',['air force 1']],['yeezy-slide',['yeezy slide']]];
    const brands=[['jordan-1',['jordan']],['adidas-1',['adidas']],['asics-1',['asics']],['nike',['nike']],['ugg',['ugg']],['new-balance',['new balance']]];
    const av=C.map(x=>x.handle);
    for(let[h,ps]of models)if(av.includes(h))for(let p of ps)if(t.includes(p))return{h,title:C.find(x=>x.handle===h).title,type:'model'};
    for(let[h,ps]of brands)if(av.includes(h))for(let p of ps)if(t.includes(p))return{h,title:C.find(x=>x.handle===h).title,type:'brand'};
    return null;
}

function filter(){
    const q=document.getElementById('q').value.toLowerCase(),f=document.getElementById('f').value;
    show(P.filter(p=>{
        if(q&&!p.title.toLowerCase().includes(q))return false;
        if(f==='missing')return p._status==='missing';
        if(f==='partial')return p._status==='partial';
        if(f==='complete')return p._status==='complete';
        return true;
    }));
}

function show(L){
    if(!L.length){document.getElementById('list').innerHTML='<div class="ld">Aucun produit</div>';return;}
    document.getElementById('list').innerHTML=L.map(p=>{
        const ck=sel.has(p.id)?'on':'',sc=p._score>=70?'h':p._score>=30?'m':'l';
        let col='<span class="col n">⚠️ Aucune</span>';
        if(p._col)col='<span class="col '+(p._col.type==='model'?'m':'b')+'">'+(p._col.type==='model'?'✅':'📁')+' '+esc(p._col.title)+'</span>';
        return '<div class="item"><div class="ck '+ck+'" onclick="tog('+p.id+')"></div><img class="img" src="'+(p.image?.src||'')+'" onerror="this.style.background=\'#333\'"><div class="inf"><h3>'+esc(p.title)+'</h3><div class="sku">'+(p.variants?.[0]?.sku||'')+'</div>'+col+'</div><div class="seo"><div class="si '+(p._desc?'ok':'no')+'">'+(p._desc?'✅':'❌')+' Desc</div><div class="si '+(p._link?'ok':'no')+'">'+(p._link?'✅':'❌')+' Lien</div></div><div class="sc '+sc+'">'+p._score+'%</div><div class="acts"><button onclick="doOne('+p.id+')">⚡</button></div></div>';
    }).join('');
}

function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function tog(id){sel.has(id)?sel.delete(id):sel.add(id);document.getElementById('selc').textContent=sel.size;filter();}

async function doOne(id){
    toast('⏳ Application...','s');
    try{
        const r=await fetch('/api/seo/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:id})});
        const d=await r.json();
        d.success?toast('✅ OK!','s'):toast('❌ Erreur','e');
        load();
    }catch(e){toast('❌ '+e.message,'e');}
}

function doSel(){if(!sel.size){toast('Sélectionnez des produits','e');return;}batch(Array.from(sel));}
function doAll(){if(!confirm('Appliquer SEO à '+P.length+' produits?'))return;batch(P.map(p=>p.id));}

async function batch(ids){
    document.getElementById('bar').classList.add('on');
    await fetch('/api/seo/batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_ids:ids})});
    const iv=setInterval(async()=>{
        const r=await fetch('/api/progress').then(x=>x.json());
        document.getElementById('fill').style.width=(r.total?r.current/r.total*100:0)+'%';
        document.getElementById('cnt').textContent=r.current+'/'+r.total;
        document.getElementById('msg').textContent=r.message;
        if(!r.running){clearInterval(iv);document.getElementById('bar').classList.remove('on');toast(r.message,'s');sel.clear();document.getElementById('selc').textContent='0';load();}
    },1000);
}

function toast(m,t){document.querySelectorAll('.tst').forEach(e=>e.remove());const e=document.createElement('div');e.className='tst '+t;e.textContent=m;document.body.appendChild(e);setTimeout(()=>e.remove(),3000);}

document.getElementById('q').addEventListener('input',filter);
document.getElementById('f').addEventListener('change',filter);
load();
</script></body></html>'''


@app.route('/api/products')
def api_products():
    """Retourne produits + collections"""
    products = get_all_products()
    collections = get_all_collections()
    return jsonify({'products': products, 'collections': collections})


@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)


@app.route('/api/seo/apply', methods=['POST'])
def api_apply():
    data = request.json
    pid = data.get('product_id')
    r = shopify_request(f'products/{pid}.json')
    if not r: return jsonify({'error': 'Not found'}), 404
    p = r['product']
    col = find_best_collection(p.get('title', ''), get_all_collections())
    updates = {'meta_title': generate_meta_title(p), 'meta_description': generate_meta_description(p), 'body_html': generate_description(p, col)}
    return jsonify({'success': update_product_seo(pid, updates)})


@app.route('/api/seo/batch', methods=['POST'])
def api_batch():
    global task_progress
    pids = request.json.get('product_ids', [])
    def run():
        global task_progress
        task_progress = {'running': True, 'current': 0, 'total': len(pids), 'message': 'Démarrage...'}
        cols = get_all_collections()
        for i, pid in enumerate(pids):
            task_progress['current'] = i + 1
            r = shopify_request(f'products/{pid}.json')
            if r and 'product' in r:
                p = r['product']
                task_progress['message'] = f'#{i+1} {p.get("title","")[:25]}...'
                col = find_best_collection(p.get('title', ''), cols)
                update_product_seo(pid, {'meta_title': generate_meta_title(p), 'meta_description': generate_meta_description(p), 'body_html': generate_description(p, col)})
            time.sleep(1)
        task_progress = {'running': False, 'current': len(pids), 'total': len(pids), 'message': f'✅ {len(pids)} produits traités!'}
    Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


if __name__ == '__main__':
    print(f"[V4] {SHOP} - Token: {'OK' if ACCESS_TOKEN else 'MISSING'}")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
