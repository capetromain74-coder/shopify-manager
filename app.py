"""
Shopify Manager V4 - Version Pagination
Charge les produits par lots de 50 pour éviter les timeouts
"""

from flask import Flask, jsonify, request
import json, os, time, re, ssl
from urllib.request import Request, urlopen
from threading import Thread

app = Flask(__name__)

SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'
SITE_NAME = os.environ.get('SITE_NAME', 'KP SHOES')
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'kpshoes.fr')

task_progress = {'running': False, 'current': 0, 'total': 0, 'message': ''}
_collections_cache = None


def shopify_request(endpoint, method='GET', data=None):
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    headers = {'X-Shopify-Access-Token': ACCESS_TOKEN, 'Content-Type': 'application/json'}
    try:
        req = Request(url, data=json.dumps(data).encode('utf-8') if data else None, headers=headers, method=method)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urlopen(req, context=ctx, timeout=30) as r:
            return True if method == 'DELETE' else json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f"[Err] {e}")
        return None


def get_collections():
    global _collections_cache
    if _collections_cache: return _collections_cache
    cols = []
    for t in ['custom_collections', 'smart_collections']:
        r = shopify_request(f'{t}.json?limit=250')
        if r and t in r:
            cols.extend([{'id': c['id'], 'handle': c['handle'], 'title': c['title']} for c in r[t]])
    _collections_cache = cols
    return cols


MODEL_PATTERNS = [('jordan-4', ['jordan 4']), ('jordan-1-high', ['jordan 1 high']), ('jordan-1-low', ['jordan 1 low']), ('jordan-1-mid', ['jordan 1 mid']), ('adidas-samba', ['samba']), ('adidas-campus', ['campus']), ('adidas-gazelle', ['gazelle']), ('adidas-spezial', ['spezial']), ('asics-gel-1130', ['gel-1130', 'gel 1130']), ('ugg-tasman', ['tasman']), ('ugg-tazz', ['tazz']), ('nike-dunk-low', ['dunk low']), ('air-force-1', ['air force 1']), ('yeezy-slide', ['yeezy slide'])]
BRAND_PATTERNS = [('jordan-1', ['jordan']), ('adidas-1', ['adidas']), ('asics-1', ['asics']), ('nike', ['nike']), ('ugg', ['ugg']), ('new-balance', ['new balance'])]


def find_col(title, cols):
    if not title: return None
    t = title.lower()
    av = [c['handle'] for c in cols]
    for h, ps in MODEL_PATTERNS:
        if h in av:
            for p in ps:
                if p in t: return {'handle': h, 'title': next(c['title'] for c in cols if c['handle']==h), 'type': 'model'}
    for h, ps in BRAND_PATTERNS:
        if h in av:
            for p in ps:
                if p in t: return {'handle': h, 'title': next(c['title'] for c in cols if c['handle']==h), 'type': 'brand'}
    return None


def gen_title(p): return (p.get('title','')[:50] + ' | ' + SITE_NAME)[:60]
def gen_desc(p): return f"Achetez {p.get('title','')} ✓ 100% Authentique ✓ Livraison rapide | {SITE_NAME}"[:155]
def gen_body(p, col):
    title, brand = p.get('title',''), p.get('vendor','Sneakers')
    sku = p['variants'][0].get('sku','') if p.get('variants') else ''
    if col:
        link = f'<a href="https://{SITE_DOMAIN}/collections/{col["handle"]}">{col["title"]}</a>'
        intro = f'<p>Découvrez la <strong>{title}</strong>, de notre collection {link}.</p>'
    else:
        intro = f'<p>Découvrez la <strong>{title}</strong> par <strong>{brand}</strong>.</p>'
    tech = f'<p><strong>SKU</strong>: {sku}<br><strong>Marque</strong>: {brand}</p>' if sku else f'<p><strong>Marque</strong>: {brand}</p>'
    return intro + '<p>Design iconique, finitions premium.</p>' + tech + f'<p>Chez <strong>{SITE_NAME}</strong>, 100% authentique.</p>'


def update_seo(pid, updates):
    if 'body_html' in updates:
        shopify_request(f'products/{pid}.json', 'PUT', {'product': {'id': pid, 'body_html': updates['body_html']}})
        time.sleep(0.4)
    for k, m in [('meta_title', 'title_tag'), ('meta_description', 'description_tag')]:
        if k in updates:
            shopify_request(f'products/{pid}/metafields.json', 'POST', {'metafield': {'namespace': 'global', 'key': m, 'value': updates[k], 'type': 'single_line_text_field'}})
            time.sleep(0.3)
    return True


@app.route('/')
def home():
    return f'<html><head><meta charset="UTF-8"><title>V4</title><style>body{{font-family:system-ui;background:#0a0a0f;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}a{{background:#00ff88;color:#000;padding:15px 40px;border-radius:8px;text-decoration:none;font-weight:bold}}</style></head><body><div style="text-align:center"><h1 style="color:#00ff88">🚀 Shopify Manager V4</h1><p style="color:#666;margin:20px 0">{SHOP}</p><a href="/seo">⚡ Gestion SEO</a></div></body></html>'


@app.route('/seo')
def seo():
    return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SEO</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui;background:#0a0a0f;color:#fff}
.h{padding:10px 15px;background:#111;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #222}.h a{color:#666;text-decoration:none;font-size:13px}.h b{color:#00ff88}
.s{display:flex;gap:8px;padding:10px 15px;background:#0d0d14;flex-wrap:wrap}.s div{background:#1a1a2e;padding:8px 14px;border-radius:6px;text-align:center}.s .v{font-size:18px;font-weight:bold}.s .v.g{color:#0f8}.s .v.o{color:#fa0}.s .v.r{color:#f55}.s .l{font-size:8px;color:#555}.s .p{background:#0f8;color:#000;padding:8px 16px;border-radius:6px;font-size:20px;font-weight:bold}
.c{padding:10px 15px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;border-bottom:1px solid #222}input,select{padding:7px 10px;background:#1a1a2e;border:1px solid #333;border-radius:4px;color:#fff;font-size:12px}
button{padding:7px 14px;border:none;border-radius:4px;cursor:pointer;font-weight:600;font-size:11px}.bg{background:#0f8;color:#000}.br{background:#f55;color:#fff}.bs{background:#333;color:#fff}
.i{margin-left:auto;font-size:11px;color:#555}
.m{padding:10px 15px;font-size:11px;color:#888;background:#111;display:none}.m.on{display:block}
#list{padding:10px 15px}
.p{background:#111;border:1px solid #222;border-radius:6px;padding:8px 10px;margin-bottom:5px;display:grid;grid-template-columns:22px 45px 1fr 90px 50px 60px;gap:8px;align-items:center;font-size:11px}
.ck{width:16px;height:16px;border:2px solid #444;border-radius:3px;cursor:pointer}.ck.on{background:#0f8;border-color:#0f8}
.im{width:45px;height:45px;border-radius:4px;object-fit:cover;background:#222}
.in h4{font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:2px}.in .sk{font-size:8px;color:#444}.in .co{font-size:8px;margin-top:1px}.in .co.g{color:#0f8}.in .co.p{color:#a5f}.in .co.r{color:#f55}
.se{font-size:8px}.se .ok{color:#0f8}.se .no{color:#f55}
.sc{font-size:9px;padding:3px 7px;border-radius:8px}.sc.h{background:#0f82;color:#0f8}.sc.m{background:#fa02;color:#fa0}.sc.l{background:#f552;color:#f55}
.p button{padding:3px 7px;font-size:9px}
.ld{text-align:center;padding:40px;color:#555}.sp{width:30px;height:30px;border:3px solid #222;border-top-color:#0f8;border-radius:50%;animation:sp .8s linear infinite;margin:0 auto 10px}@keyframes sp{to{transform:rotate(360deg)}}
.bar{position:fixed;top:0;left:0;right:0;background:#111;padding:10px 15px;border-bottom:2px solid #0f8;display:none;z-index:99;font-size:11px}.bar.on{display:block}.bar .t{height:5px;background:#222;border-radius:3px;margin-top:6px}.bar .f{height:100%;background:#0f8;border-radius:3px}
.toast{position:fixed;bottom:15px;right:15px;padding:8px 14px;border-radius:5px;font-size:11px;z-index:100}.toast.s{background:#0f8;color:#000}.toast.e{background:#f55}
</style></head><body>
<div class="bar" id="bar"><div style="display:flex;justify-content:space-between"><span id="bm">...</span><span id="bc">0/0</span></div><div class="t"><div class="f" id="bf"></div></div></div>
<div class="h"><a href="/">← Retour</a><b>🚀 SEO V4</b><span></span></div>
<div class="s"><div><div class="v g" id="s1">-</div><div class="l">OK</div></div><div><div class="v o" id="s2">-</div><div class="l">PARTIEL</div></div><div><div class="v r" id="s3">-</div><div class="l">MANQUE</div></div><div><div class="v" id="s4">-</div><div class="l">TOTAL</div></div><div class="p" id="pct">-</div></div>
<div class="c"><input id="q" placeholder="Rechercher..."><select id="f"><option value="">Tous</option><option value="missing">Sans lien</option><option value="partial">Partiel</option><option value="complete">Complet</option></select><button class="bs" onclick="reload()">🔄</button><button class="bg" onclick="doSel()">⚡ Sél.</button><button class="br" onclick="doAll()">🚀 Tout</button><div class="i"><b id="sc">0</b> sél.</div></div>
<div class="m" id="msg"></div>
<div id="list"><div class="ld"><div class="sp"></div>Chargement...</div></div>
<script>
let P=[],C=[],sel=new Set(),sinceId=0,loading=false,total=0;

async function loadMore(){
    if(loading)return;
    loading=true;
    msg('Chargement en cours... ('+P.length+' produits)');
    try{
        const r=await fetch('/api/products?since_id='+sinceId+'&limit=50');
        const d=await r.json();
        if(d.collections)C=d.collections;
        if(d.products&&d.products.length){
            d.products.forEach(p=>{
                const b=(p.body_html||'').toLowerCase();
                p._lk=b.includes('kpshoes.fr/collections/');
                p._ds=(p.body_html||'').length>100;
                p._sc=(p._ds?30:0)+(p._lk?70:0);
                p._st=p._sc>=70?'complete':p._sc>=30?'partial':'missing';
                p._co=findC(p.title);
                P.push(p);
            });
            sinceId=d.products[d.products.length-1].id;
            updateStats();
            filter();
            if(d.products.length>=50){
                setTimeout(loadMore,500);
            }else{
                msg('');
                loading=false;
            }
        }else{
            msg('');
            loading=false;
        }
    }catch(e){
        msg('Erreur: '+e.message+' <button onclick="loadMore()">Réessayer</button>');
        loading=false;
    }
}

function findC(t){
    if(!t||!C.length)return null;
    t=t.toLowerCase();
    const M=[['jordan-4',['jordan 4']],['jordan-1-high',['jordan 1 high']],['jordan-1-low',['jordan 1 low']],['adidas-samba',['samba']],['adidas-campus',['campus']],['adidas-gazelle',['gazelle']],['asics-gel-1130',['gel-1130']],['ugg-tasman',['tasman']],['ugg-tazz',['tazz']],['nike-dunk-low',['dunk low']],['air-force-1',['air force 1']]];
    const B=[['jordan-1',['jordan']],['adidas-1',['adidas']],['asics-1',['asics']],['nike',['nike']],['ugg',['ugg']],['new-balance',['new balance']]];
    for(let[h,ps]of M){let c=C.find(x=>x.handle===h);if(c)for(let p of ps)if(t.includes(p))return{h,n:c.title,t:'m'};}
    for(let[h,ps]of B){let c=C.find(x=>x.handle===h);if(c)for(let p of ps)if(t.includes(p))return{h,n:c.title,t:'b'};}
    return null;
}

function updateStats(){
    let c1=0,c2=0,c3=0;
    P.forEach(p=>{if(p._st==='complete')c1++;else if(p._st==='partial')c2++;else c3++;});
    document.getElementById('s1').textContent=c1;
    document.getElementById('s2').textContent=c2;
    document.getElementById('s3').textContent=c3;
    document.getElementById('s4').textContent=P.length;
    document.getElementById('pct').textContent=P.length?Math.round(c1/P.length*100)+'%':'0%';
}

function msg(t){const m=document.getElementById('msg');m.innerHTML=t;m.classList.toggle('on',!!t);}

function filter(){
    const q=document.getElementById('q').value.toLowerCase(),f=document.getElementById('f').value;
    render(P.filter(p=>{
        if(q&&!p.title.toLowerCase().includes(q))return false;
        if(f&&p._st!==f)return false;
        return true;
    }));
}

function render(L){
    if(!L.length&&!loading){document.getElementById('list').innerHTML='<div class="ld">Aucun produit</div>';return;}
    document.getElementById('list').innerHTML=L.slice(0,200).map(p=>{
        const ck=sel.has(p.id)?'on':'';
        const sc=p._sc>=70?'h':p._sc>=30?'m':'l';
        let co='<span class="co r">-</span>';
        if(p._co)co='<span class="co '+(p._co.t==='m'?'g':'p')+'">'+(p._co.t==='m'?'✓':'◉')+' '+esc(p._co.n)+'</span>';
        return '<div class="p"><div class="ck '+ck+'" onclick="tog('+p.id+')"></div><img class="im" src="'+(p.image?.src||'')+'" onerror="this.src=\'\'"><div class="in"><h4>'+esc(p.title)+'</h4><div class="sk">'+(p.variants?.[0]?.sku||'-')+'</div>'+co+'</div><div class="se"><div class="'+(p._ds?'ok':'no')+'">'+(p._ds?'✓':'✗')+' Desc</div><div class="'+(p._lk?'ok':'no')+'">'+(p._lk?'✓':'✗')+' Lien</div></div><div class="sc '+sc+'">'+p._sc+'%</div><div><button class="bg" onclick="doOne('+p.id+')">⚡</button></div></div>';
    }).join('')+(L.length>200?'<div class="ld">Affichage limité à 200. Utilisez la recherche.</div>':'');
}

function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function tog(id){sel.has(id)?sel.delete(id):sel.add(id);document.getElementById('sc').textContent=sel.size;filter();}
function reload(){P=[];C=[];sinceId=0;sel.clear();document.getElementById('sc').textContent='0';document.getElementById('list').innerHTML='<div class="ld"><div class="sp"></div>Chargement...</div>';loadMore();}

async function doOne(id){
    toast('...','s');
    try{
        await fetch('/api/seo/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:id})});
        toast('OK!','s');
        const i=P.findIndex(p=>p.id===id);
        if(i>=0){P[i]._lk=true;P[i]._ds=true;P[i]._sc=100;P[i]._st='complete';updateStats();filter();}
    }catch(e){toast('Err','e');}
}

function doSel(){if(!sel.size)return toast('Sélectionnez','e');batch([...sel]);}
function doAll(){if(confirm('Appliquer à '+P.length+' produits?'))batch(P.map(p=>p.id));}

async function batch(ids){
    document.getElementById('bar').classList.add('on');
    await fetch('/api/seo/batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_ids:ids})});
    const iv=setInterval(async()=>{
        const r=await fetch('/api/progress').then(x=>x.json());
        document.getElementById('bf').style.width=(r.total?r.current/r.total*100:0)+'%';
        document.getElementById('bc').textContent=r.current+'/'+r.total;
        document.getElementById('bm').textContent=r.message||'...';
        if(!r.running){clearInterval(iv);document.getElementById('bar').classList.remove('on');toast('Fini!','s');sel.clear();document.getElementById('sc').textContent='0';reload();}
    },1000);
}

function toast(m,t){const e=document.createElement('div');e.className='toast '+t;e.textContent=m;document.body.appendChild(e);setTimeout(()=>e.remove(),2000);}

document.getElementById('q').addEventListener('input',filter);
document.getElementById('f').addEventListener('change',filter);
loadMore();
</script></body></html>'''


@app.route('/api/products')
def api_products():
    """Charge les produits par lots de 50"""
    since_id = request.args.get('since_id', '0')
    limit = request.args.get('limit', '50')
    
    r = shopify_request(f'products.json?limit={limit}&since_id={since_id}')
    products = r.get('products', []) if r else []
    
    return jsonify({
        'products': products,
        'collections': get_collections()
    })


@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)


@app.route('/api/seo/apply', methods=['POST'])
def api_apply():
    pid = request.json.get('product_id')
    r = shopify_request(f'products/{pid}.json')
    if not r: return jsonify({'error': 'err'}), 404
    p = r['product']
    col = find_col(p.get('title', ''), get_collections())
    update_seo(pid, {'meta_title': gen_title(p), 'meta_description': gen_desc(p), 'body_html': gen_body(p, col)})
    return jsonify({'success': True})


@app.route('/api/seo/batch', methods=['POST'])
def api_batch():
    global task_progress
    pids = request.json.get('product_ids', [])
    def run():
        global task_progress
        task_progress = {'running': True, 'current': 0, 'total': len(pids), 'message': 'Start...'}
        cols = get_collections()
        for i, pid in enumerate(pids):
            task_progress['current'] = i + 1
            r = shopify_request(f'products/{pid}.json')
            if r and 'product' in r:
                p = r['product']
                task_progress['message'] = p.get('title','')[:25]
                col = find_col(p.get('title', ''), cols)
                update_seo(pid, {'meta_title': gen_title(p), 'meta_description': gen_desc(p), 'body_html': gen_body(p, col)})
            time.sleep(1)
        task_progress = {'running': False, 'current': len(pids), 'total': len(pids), 'message': f'OK {len(pids)}!'}
    Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
