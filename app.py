"""
Shopify Manager V4 - SEO Pro Edition
Version avec timeout long pour gros catalogues
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

task_progress = {'running': False, 'current': 0, 'total': 0, 'message': ''}

# Cache
_products_cache = None
_products_cache_time = 0
_collections_cache = None


def shopify_request(endpoint, method='GET', data=None):
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    headers = {'X-Shopify-Access-Token': ACCESS_TOKEN, 'Content-Type': 'application/json'}
    try:
        req = Request(url, data=json.dumps(data).encode('utf-8') if data else None, headers=headers, method=method)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with urlopen(req, context=context, timeout=60) as response:
            return True if method == 'DELETE' else json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"[Error] {e}")
        return None


def get_all_products(use_cache=True):
    global _products_cache, _products_cache_time
    if use_cache and _products_cache and (time.time() - _products_cache_time < 300):
        return _products_cache
    
    all_products, since_id = [], 0
    while True:
        result = shopify_request(f'products.json?limit=250&since_id={since_id}')
        if result and 'products' in result and result['products']:
            all_products.extend(result['products'])
            since_id = result['products'][-1]['id']
            if len(result['products']) < 250: break
            time.sleep(0.5)
        else: break
    
    if all_products:
        _products_cache = all_products
        _products_cache_time = time.time()
    return all_products


def get_all_collections():
    global _collections_cache
    if _collections_cache: return _collections_cache
    
    all_collections = []
    for ctype in ['custom_collections', 'smart_collections']:
        result = shopify_request(f'{ctype}.json?limit=250')
        if result and ctype in result:
            for c in result[ctype]:
                all_collections.append({'id': c['id'], 'handle': c['handle'], 'title': c['title']})
    _collections_cache = all_collections
    return all_collections


MODEL_PATTERNS = [
    ('jordan-4', ['jordan 4', 'aj4']), ('jordan-1-high', ['jordan 1 high']), ('jordan-1-low', ['jordan 1 low']), ('jordan-1-mid', ['jordan 1 mid']),
    ('adidas-samba', ['samba']), ('adidas-campus', ['campus']), ('adidas-gazelle', ['gazelle']), ('adidas-spezial', ['spezial']),
    ('asics-gel-1130', ['gel-1130', 'gel 1130']), ('asics-gel-kayano', ['kayano']), ('asics-gel-nyc', ['gel-nyc']),
    ('ugg-tasman', ['tasman']), ('ugg-tazz', ['tazz']),
    ('nike-dunk-low', ['dunk low']), ('nike-dunk-high', ['dunk high']), ('air-force-1', ['air force 1', 'af1']), ('nike-p-6000', ['air max']),
    ('new-balance-550', ['550']), ('new-balance-530', ['530']), ('new-balance-2002r', ['2002r']),
    ('yeezy-slide', ['yeezy slide']), ('yeezy-350', ['yeezy 350']),
    ('birkenstock-boston', ['boston']),
]
BRAND_PATTERNS = [
    ('jordan-1', ['jordan']), ('adidas-1', ['adidas']), ('asics-1', ['asics']), ('nike', ['nike']),
    ('new-balance', ['new balance']), ('ugg', ['ugg']), ('birkenstock-1', ['birkenstock']), ('puma', ['puma']),
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


def generate_meta_title(p):
    t = p.get('title', '')
    m = f"{t} | {SITE_NAME}"
    return m if len(m) <= 60 else f"{t[:50]}... | {SITE_NAME}"

def generate_meta_description(p):
    t, sku = p.get('title', ''), extract_sku(p)
    return f"Achetez {t}" + (f" ({sku})" if sku else "") + f" ✓ 100% Authentique ✓ Livraison rapide | {SITE_NAME}"[:155]

def generate_description(product, collection):
    title, brand, sku, colorway = product.get('title', ''), extract_brand(product), extract_sku(product), extract_colorway(product)
    lines = []
    if collection:
        link = f'<a href="https://{SITE_DOMAIN}/collections/{collection["handle"]}">{collection["title"]}</a>'
        lines.append(f'<p>Découvrez la <strong>{title}</strong>, une pièce incontournable de notre collection {link}.</p>')
    else:
        lines.append(f'<p>Découvrez la <strong>{title}</strong>, signée <strong>{brand}</strong>.</p>')
    lines.append(f'<p>Un design iconique et des finitions premium{", colorway " + colorway if colorway else ""}.</p>')
    tech = [f'<strong>Marque</strong> : {brand}']
    if sku: tech.insert(0, f'<strong>SKU</strong> : {sku}')
    lines.append('<p>' + '<br>'.join(tech) + '</p>')
    lines.append(f'<p>Chez <strong>{SITE_NAME}</strong>, toutes nos sneakers sont <strong>100% authentiques</strong>.</p>')
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
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,sans-serif;background:#0a0a0f;min-height:100vh;display:flex;align-items:center;justify-content:center;color:#fff}}.c{{text-align:center}}h1{{font-size:40px;color:#00ff88;margin-bottom:10px}}.btn{{display:inline-block;padding:15px 40px;background:#00ff88;color:#000;text-decoration:none;border-radius:10px;font-weight:bold;margin-top:20px}}</style></head>
<body><div class="c"><h1>🚀 Shopify Manager V4</h1><p style="color:#888">SEO Pro Edition</p><a href="/seo" class="btn">⚡ Gestion SEO</a><p style="margin-top:20px;color:#444">{SHOP}</p></div></body></html>'''


@app.route('/seo')
def seo_page():
    return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SEO Manager</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#0a0a0f;color:#fff}
.hd{padding:12px 20px;background:#111;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #222}.logo{color:#00ff88;font-weight:bold}.back{color:#666;text-decoration:none;font-size:14px}
.stats{display:flex;gap:8px;padding:12px 20px;background:#0d0d12;flex-wrap:wrap}.st{background:#1a1a2e;padding:10px 15px;border-radius:6px;text-align:center}.st .n{font-size:20px;font-weight:bold}.st .n.g{color:#00ff88}.st .n.o{color:#f90}.st .n.r{color:#f44}.st .l{font-size:9px;color:#666}.pct{background:#00ff88;color:#000;padding:10px 20px;border-radius:6px;font-size:22px;font-weight:bold}
.ctrl{padding:10px 20px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;border-bottom:1px solid #222}input,select{padding:8px;background:#1a1a2e;border:1px solid #333;border-radius:4px;color:#fff;font-size:13px}
.btn{padding:8px 14px;border:none;border-radius:4px;cursor:pointer;font-weight:600;font-size:12px}.btn-g{background:#00ff88;color:#000}.btn-r{background:#f44;color:#fff}.btn-s{background:#333;color:#fff}
.sel{margin-left:auto;color:#666;font-size:12px}
.list{padding:10px 20px}
.item{background:#12121a;border:1px solid #222;border-radius:6px;padding:10px;margin-bottom:6px;display:grid;grid-template-columns:24px 50px 1fr 110px 60px 70px;gap:10px;align-items:center;font-size:12px}.item:hover{border-color:#333}
.ck{width:18px;height:18px;border:2px solid #444;border-radius:3px;cursor:pointer}.ck.on{background:#00ff88;border-color:#00ff88}
.img{width:50px;height:50px;border-radius:4px;object-fit:cover;background:#222}
.inf{overflow:hidden}.inf h3{font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.inf .sku{font-size:9px;color:#555}.inf .col{font-size:9px;margin-top:2px}.inf .col.g{color:#00ff88}.inf .col.p{color:#a855f7}.inf .col.r{color:#f44}
.seo{font-size:9px}.seo .ok{color:#00ff88}.seo .no{color:#f44}
.sc{font-size:10px;padding:4px 8px;border-radius:10px}.sc.h{background:#00ff8833;color:#00ff88}.sc.m{background:#f9033;color:#f90}.sc.l{background:#f4433;color:#f44}
.acts button{padding:4px 8px;font-size:10px;background:#00ff88;color:#000;border:none;border-radius:3px;cursor:pointer}
.ld{text-align:center;padding:60px}.ld .sp{width:40px;height:40px;border:3px solid #222;border-top-color:#00ff88;border-radius:50%;animation:sp 1s linear infinite;margin:0 auto 15px}@keyframes sp{to{transform:rotate(360deg)}}.ld p{color:#666;font-size:13px}.ld .sub{font-size:11px;color:#444;margin-top:8px}
.bar{position:fixed;top:0;left:0;right:0;background:#111;padding:12px 20px;border-bottom:2px solid #00ff88;display:none;z-index:99}.bar.on{display:block}.bar .t{height:6px;background:#222;border-radius:3px;margin-top:8px}.bar .f{height:100%;background:#00ff88;border-radius:3px}
.tst{position:fixed;bottom:20px;right:20px;padding:10px 16px;border-radius:6px;font-size:12px;z-index:100}.tst.s{background:#00ff88;color:#000}.tst.e{background:#f44;color:#fff}
</style></head><body>
<div class="bar" id="bar"><div style="display:flex;justify-content:space-between;font-size:12px"><span id="bmsg">Traitement...</span><span id="bcnt">0/0</span></div><div class="t"><div class="f" id="bfill"></div></div></div>
<div class="hd"><a href="/" class="back">← Retour</a><div class="logo">🚀 SEO Manager V4</div><div></div></div>
<div class="stats"><div class="st"><div class="n g" id="s1">-</div><div class="l">COMPLET</div></div><div class="st"><div class="n o" id="s2">-</div><div class="l">PARTIEL</div></div><div class="st"><div class="n r" id="s3">-</div><div class="l">SANS LIEN</div></div><div class="st"><div class="n" id="s4">-</div><div class="l">TOTAL</div></div><div class="pct" id="pct">-</div></div>
<div class="ctrl"><input type="text" id="q" placeholder="Rechercher..."><select id="f"><option value="">Tous</option><option value="missing">Sans liens</option><option value="partial">Partiel</option><option value="complete">Complet</option></select><button class="btn btn-s" onclick="reload()">🔄</button><button class="btn btn-g" onclick="doSel()">⚡ Sélection</button><button class="btn btn-r" onclick="doAll()">🚀 TOUT</button><div class="sel"><b id="sc">0</b> sél.</div></div>
<div class="list" id="list"><div class="ld"><div class="sp"></div><p>Chargement des produits...</p><p class="sub">Cela peut prendre 30-60 secondes</p></div></div>
<script>
let P=[],C=[],sel=new Set();

async function load(){
    document.getElementById('list').innerHTML='<div class="ld"><div class="sp"></div><p>Chargement des produits...</p><p class="sub">Patientez, cela peut prendre 30-60 secondes...</p></div>';
    try{
        const r=await fetch('/api/products',{signal:AbortSignal.timeout(180000)});
        const d=await r.json();
        P=d.products||[];
        C=d.collections||[];
        let c1=0,c2=0,c3=0;
        P.forEach(p=>{
            const b=(p.body_html||'').toLowerCase();
            p._lk=b.includes('kpshoes.fr/collections/');
            p._ds=(p.body_html||'').length>100;
            p._sc=(p._ds?30:0)+(p._lk?70:0);
            p._st=p._sc>=70?'complete':p._sc>=30?'partial':'missing';
            p._co=findC(p.title);
            if(p._st==='complete')c1++;else if(p._st==='partial')c2++;else c3++;
        });
        document.getElementById('s1').textContent=c1;
        document.getElementById('s2').textContent=c2;
        document.getElementById('s3').textContent=c3;
        document.getElementById('s4').textContent=P.length;
        document.getElementById('pct').textContent=P.length?Math.round(c1/P.length*100)+'%':'0%';
        filter();
    }catch(e){
        document.getElementById('list').innerHTML='<div class="ld"><p style="color:#f44">❌ Erreur: '+e.message+'</p><button onclick="load()" style="margin-top:15px;padding:10px 25px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold">🔄 Réessayer</button></div>';
    }
}

function findC(t){
    if(!t||!C.length)return null;
    t=t.toLowerCase();
    const M=[['jordan-4',['jordan 4']],['jordan-1-high',['jordan 1 high']],['jordan-1-low',['jordan 1 low']],['jordan-1-mid',['jordan 1 mid']],['adidas-samba',['samba']],['adidas-campus',['campus']],['adidas-gazelle',['gazelle']],['adidas-spezial',['spezial']],['asics-gel-1130',['gel-1130','gel 1130']],['ugg-tasman',['tasman']],['ugg-tazz',['tazz']],['nike-dunk-low',['dunk low']],['air-force-1',['air force 1']],['yeezy-slide',['yeezy slide']]];
    const B=[['jordan-1',['jordan']],['adidas-1',['adidas']],['asics-1',['asics']],['nike',['nike']],['ugg',['ugg']],['new-balance',['new balance']]];
    const A=C.map(x=>x.handle);
    for(let[h,ps]of M)if(A.includes(h))for(let p of ps)if(t.includes(p))return{h,n:C.find(x=>x.handle===h).title,t:'m'};
    for(let[h,ps]of B)if(A.includes(h))for(let p of ps)if(t.includes(p))return{h,n:C.find(x=>x.handle===h).title,t:'b'};
    return null;
}

function filter(){
    const q=document.getElementById('q').value.toLowerCase(),f=document.getElementById('f').value;
    render(P.filter(p=>{
        if(q&&!p.title.toLowerCase().includes(q)&&!(p.variants?.[0]?.sku||'').toLowerCase().includes(q))return false;
        if(f&&p._st!==f)return false;
        return true;
    }));
}

function render(L){
    if(!L.length){document.getElementById('list').innerHTML='<div class="ld"><p>Aucun produit</p></div>';return;}
    document.getElementById('list').innerHTML=L.map(p=>{
        const ck=sel.has(p.id)?'on':'';
        const sc=p._sc>=70?'h':p._sc>=30?'m':'l';
        let co='<span class="col r">Aucune</span>';
        if(p._co)co='<span class="col '+(p._co.t==='m'?'g':'p')+'">'+(p._co.t==='m'?'✓':'◉')+' '+esc(p._co.n)+'</span>';
        return '<div class="item"><div class="ck '+ck+'" onclick="tog('+p.id+')"></div><img class="img" src="'+(p.image?.src||'')+'" onerror="this.src=\'\'"><div class="inf"><h3>'+esc(p.title)+'</h3><div class="sku">'+(p.variants?.[0]?.sku||'-')+'</div>'+co+'</div><div class="seo"><div class="'+(p._ds?'ok':'no')+'">'+(p._ds?'✓':'✗')+' Desc</div><div class="'+(p._lk?'ok':'no')+'">'+(p._lk?'✓':'✗')+' Lien</div></div><div class="sc '+sc+'">'+p._sc+'%</div><div class="acts"><button onclick="doOne('+p.id+')">⚡</button></div></div>';
    }).join('');
}

function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function tog(id){sel.has(id)?sel.delete(id):sel.add(id);document.getElementById('sc').textContent=sel.size;filter();}
function reload(){P=[];C=[];sel.clear();document.getElementById('sc').textContent='0';load();}

async function doOne(id){
    toast('Application...','s');
    try{
        const r=await fetch('/api/seo/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:id})});
        const d=await r.json();
        if(d.success){toast('✓ Appliqué!','s');load();}else toast('Erreur','e');
    }catch(e){toast('Erreur','e');}
}

function doSel(){if(!sel.size)return toast('Sélectionnez des produits','e');batch([...sel]);}
function doAll(){if(confirm('Appliquer à '+P.length+' produits?'))batch(P.map(p=>p.id));}

async function batch(ids){
    document.getElementById('bar').classList.add('on');
    document.getElementById('bmsg').textContent='Démarrage...';
    document.getElementById('bcnt').textContent='0/'+ids.length;
    document.getElementById('bfill').style.width='0%';
    await fetch('/api/seo/batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_ids:ids})});
    const iv=setInterval(async()=>{
        const r=await fetch('/api/progress').then(x=>x.json());
        document.getElementById('bfill').style.width=(r.total?r.current/r.total*100:0)+'%';
        document.getElementById('bcnt').textContent=r.current+'/'+r.total;
        document.getElementById('bmsg').textContent=r.message||'Traitement...';
        if(!r.running){clearInterval(iv);document.getElementById('bar').classList.remove('on');toast('Terminé!','s');sel.clear();document.getElementById('sc').textContent='0';load();}
    },1000);
}

function toast(m,t){const e=document.createElement('div');e.className='tst '+t;e.textContent=m;document.body.appendChild(e);setTimeout(()=>e.remove(),3000);}

document.getElementById('q').addEventListener('input',filter);
document.getElementById('f').addEventListener('change',filter);
load();
</script></body></html>'''


@app.route('/api/products')
def api_products():
    products = get_all_products()
    collections = get_all_collections()
    return jsonify({'products': products, 'collections': collections})


@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)


@app.route('/api/seo/apply', methods=['POST'])
def api_apply():
    pid = request.json.get('product_id')
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
                task_progress['message'] = p.get('title','')[:30]+'...'
                col = find_best_collection(p.get('title', ''), cols)
                update_product_seo(pid, {'meta_title': generate_meta_title(p), 'meta_description': generate_meta_description(p), 'body_html': generate_description(p, col)})
            time.sleep(1)
        task_progress = {'running': False, 'current': len(pids), 'total': len(pids), 'message': f'✓ {len(pids)} produits!'}
    Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
