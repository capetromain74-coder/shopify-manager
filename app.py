"""
KP SHOES - Plateforme de Gestion Shopify V5
Dashboard + Detail Produit + Variantes + SEO
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
            for c in r[t]:
                cols.append({'id': c['id'], 'handle': c['handle'], 'title': c['title']})
    _collections_cache = cols
    return cols


def get_product_metafields(product_id):
    r = shopify_request(f'products/{product_id}/metafields.json')
    meta_title = ''
    meta_description = ''
    if r and 'metafields' in r:
        for m in r['metafields']:
            if m.get('key') == 'title_tag':
                meta_title = m.get('value', '')
            elif m.get('key') == 'description_tag':
                meta_description = m.get('value', '')
    return {'meta_title': meta_title, 'meta_description': meta_description}


# Collections mapping
MODEL_COLLECTIONS = {
    'jordan-4': ['jordan 4'], 'jordan-1-high': ['jordan 1 high'], 'jordan-1-low': ['jordan 1 low'],
    'jordan-1-mid': ['jordan 1 mid'], 'nike-dunk': ['dunk'], 'air-force-1': ['air force 1'],
    'nike-p-6000': ['air max'], 'nike-vomero': ['vomero'], 'nike-sacail': ['sacai'],
    'adidas-samba': ['samba'], 'adidas-campus': ['campus'], 'adidas-gazelle': ['gazelle'],
    'adidas-spezial': ['spezial'], 'adidas-forum': ['forum'], 'yeezy-slide': ['yeezy slide'],
    'yeezy-351': ['yeezy 350', '350 v2'], 'yeezy-350': ['yeezy 700'],
    'new-balance-550': ['550'], 'new-balance-530': ['530'], 'new-balance-2002r': ['2002r'],
    'new-balance-9060': ['9060'], 'asics-gel-1130': ['gel-1130', 'gel 1130'],
    'asics-gel-kayano': ['kayano'], 'asics-gel-nyc': ['gel-nyc', 'gel nyc'],
    'ugg-tasman': ['tasman'], 'ugg-tazz': ['tazz'], 'ugg-ultra-mini': ['ultra mini'],
    'travis-scott': ['travis scott'], 'off-white': ['off-white'], 'supreme': ['supreme'],
}

BRAND_COLLECTIONS = {
    'jordan-1': ['jordan'], 'nike-1': ['nike', 'nocta', 'blazer'], 'adidas-1': ['adidas'],
    'yeezy-1': ['yeezy', 'foam runner'], 'new-balance-1': ['new balance'], 'asics-1': ['asics'],
    'ugg-1': ['ugg'], 'puma-1': ['puma'], 'crocs': ['crocs'], 'birkenstock-1': ['birkenstock'],
    'converse': ['converse'], 'salomon': ['salomon'], 'timberland': ['timberland'],
}

EXCLUDED = ['tout-nos-modeles', 'best-seller', 'moins-de-150', 'livraison-48h', 'pour-enfants', 'sport', 'autre-marques']


def find_collection(title, collections):
    if not title or not collections: return None
    t = title.lower()
    available = [c['handle'] for c in collections if c['handle'] not in EXCLUDED]
    for handle, keywords in MODEL_COLLECTIONS.items():
        if handle in available:
            for kw in keywords:
                if kw in t:
                    col = next((c for c in collections if c['handle'] == handle), None)
                    if col: return {'handle': col['handle'], 'title': col['title'], 'url': f"https://{SITE_DOMAIN}/collections/{col['handle']}", 'type': 'model'}
    for handle, keywords in BRAND_COLLECTIONS.items():
        if handle in available:
            for kw in keywords:
                if kw in t:
                    col = next((c for c in collections if c['handle'] == handle), None)
                    if col: return {'handle': col['handle'], 'title': col['title'], 'url': f"https://{SITE_DOMAIN}/collections/{col['handle']}", 'type': 'brand'}
    return None


def extract_brand(title):
    t = title.lower()
    if 'jordan' in t: return 'Jordan'
    if 'yeezy' in t: return 'Yeezy'
    brands = [('Nike', ['nike', 'dunk', 'air force', 'air max', 'nocta']), ('Adidas', ['adidas', 'samba', 'campus', 'gazelle']),
              ('New Balance', ['new balance']), ('Asics', ['asics']), ('UGG', ['ugg']), ('Puma', ['puma']),
              ('Crocs', ['crocs']), ('Birkenstock', ['birkenstock']), ('Salomon', ['salomon']), ('Timberland', ['timberland'])]
    for brand, kws in brands:
        for kw in kws:
            if kw in t: return brand
    return 'Sneakers'


def analyze_seo(product, meta_title, meta_description):
    title = product.get('title', '')
    body_html = product.get('body_html', '') or ''
    results = {'score': 0, 'max_score': 100, 'checks': []}
    
    # Meta Title
    check1 = {'name': 'Meta Title', 'points': 0, 'max': 25, 'status': 'error', 'message': 'Absent'}
    if meta_title:
        if SITE_NAME in meta_title and len(meta_title) <= 60:
            check1 = {'name': 'Meta Title', 'points': 25, 'max': 25, 'status': 'success', 'message': 'OK (' + str(len(meta_title)) + ' car.)'}
        elif len(meta_title) > 60:
            check1 = {'name': 'Meta Title', 'points': 10, 'max': 25, 'status': 'warning', 'message': 'Trop long (' + str(len(meta_title)) + '/60)'}
        else:
            check1 = {'name': 'Meta Title', 'points': 15, 'max': 25, 'status': 'warning', 'message': 'Manque KP SHOES'}
    results['checks'].append(check1)
    results['score'] += check1['points']
    
    # Meta Description
    check2 = {'name': 'Meta Description', 'points': 0, 'max': 25, 'status': 'error', 'message': 'Absente'}
    if meta_description:
        has_auth = '100%' in meta_description or 'authentique' in meta_description.lower()
        good_len = 100 <= len(meta_description) <= 155
        if has_auth and good_len:
            check2 = {'name': 'Meta Description', 'points': 25, 'max': 25, 'status': 'success', 'message': 'OK (' + str(len(meta_description)) + ' car.)'}
        elif good_len:
            check2 = {'name': 'Meta Description', 'points': 15, 'max': 25, 'status': 'warning', 'message': 'Manque authenticite'}
        else:
            check2 = {'name': 'Meta Description', 'points': 10, 'max': 25, 'status': 'warning', 'message': str(len(meta_description)) + ' car. (ideal: 100-155)'}
    results['checks'].append(check2)
    results['score'] += check2['points']
    
    # Description + Lien
    check3 = {'name': 'Description + Lien', 'points': 0, 'max': 35, 'status': 'error', 'message': 'Manquante'}
    has_desc = len(body_html) > 100
    has_link = 'kpshoes.fr/collections/' in body_html.lower()
    if has_desc and has_link:
        check3 = {'name': 'Description + Lien', 'points': 35, 'max': 35, 'status': 'success', 'message': 'Complete avec lien'}
    elif has_desc:
        check3 = {'name': 'Description + Lien', 'points': 15, 'max': 35, 'status': 'warning', 'message': 'OK mais sans lien'}
    results['checks'].append(check3)
    results['score'] += check3['points']
    
    # SKU
    check4 = {'name': 'SKU', 'points': 0, 'max': 15, 'status': 'error', 'message': 'Manquant'}
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    if sku:
        check4 = {'name': 'SKU', 'points': 15, 'max': 15, 'status': 'success', 'message': sku}
    results['checks'].append(check4)
    results['score'] += check4['points']
    
    if results['score'] >= 85: results['status'] = 'excellent'
    elif results['score'] >= 70: results['status'] = 'good'
    elif results['score'] >= 50: results['status'] = 'warning'
    else: results['status'] = 'poor'
    
    return results


MODEL_DESCRIPTIONS = {
    'jordan 4': "Concue par Tinker Hatfield en 1989, la Air Jordan 4 est une silhouette emblematique. Ailes en mesh, languette en plastique et lacets a ailettes.",
    'jordan 1 high': "La Air Jordan 1 High, creee en 1985, est la sneaker qui a tout commence. Col haut caracteristique et design intemporel.",
    'jordan 1 low': "Version basse de la Air Jordan 1, parfaite pour un style quotidien decontracte.",
    'dunk': "Creee en 1985, la Nike Dunk est une icone de la culture sneakers. Design simple et efficace.",
    'air force 1': "La Nike Air Force 1, creee en 1982, est la premiere chaussure avec technologie Air. Un classique.",
    'samba': "L Adidas Samba, nee en 1950, est une legende du football en salle devenue classique casual.",
    'campus': "L Adidas Campus revisite le classique des annees 80 avec suede premium.",
    'yeezy slide': "La Yeezy Slide a redefini la sandale de luxe. Mousse EVA et confort unique.",
    'yeezy 350': "La Yeezy 350 V2, upper Primeknit et semelle Boost. Une piece collector.",
    'new balance 550': "Ressortie en 2021, la NB 550 est un phenomene. Design basketball vintage.",
    'gel-1130': "L Asics Gel-1130, running Y2K devenu must-have streetwear.",
    'tasman': "La UGG Tasman, slipper avec doublure peau de mouton. Confort incomparable.",
    'crocs': "Les Crocs, design Croslite unique. Confort et legerete.",
}

DEFAULT_DESC = "Un modele alliant design contemporain et qualite premium."


def get_model_description(title):
    t = title.lower()
    for key, desc in MODEL_DESCRIPTIONS.items():
        if key in t: return desc
    return DEFAULT_DESC


def generate_seo(product, collections):
    title = product.get('title', '')
    brand = extract_brand(title)
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    collection = find_collection(title, collections)
    model_desc = get_model_description(title)
    
    meta_title = title + ' | ' + SITE_NAME
    if len(meta_title) > 60:
        meta_title = title[:47] + '... | ' + SITE_NAME
    
    if sku:
        meta_description = 'Achetez ' + title + ' (' + sku + ') | 100% Authentique | Livraison rapide | ' + SITE_NAME
    else:
        meta_description = 'Achetez ' + title + ' | 100% Authentique | Livraison rapide | ' + SITE_NAME
    meta_description = meta_description[:155]
    
    lines = []
    if collection:
        lines.append('<p>Decouvrez la <strong>' + title + '</strong> disponible sur ' + SITE_NAME + '. Retrouvez ce modele dans notre collection <a href="' + collection['url'] + '">' + collection['title'] + '</a>.</p>')
    else:
        lines.append('<p>Decouvrez la <strong>' + title + '</strong> disponible sur ' + SITE_NAME + '.</p>')
    lines.append('<p>' + model_desc + '</p>')
    tech = ['<strong>Marque</strong> : ' + brand]
    if sku: tech.insert(0, '<strong>Reference</strong> : ' + sku)
    lines.append('<p>' + '<br>'.join(tech) + '</p>')
    lines.append('<p>Chez <strong>' + SITE_NAME + '</strong>, nous garantissons l authenticite de chaque paire.</p>')
    body_html = '\n\n'.join(lines)
    
    return {'meta_title': meta_title, 'meta_description': meta_description, 'body_html': body_html, 'collection': collection}


def update_product_seo(pid, updates):
    if 'body_html' in updates:
        shopify_request(f'products/{pid}.json', 'PUT', {'product': {'id': pid, 'body_html': updates['body_html']}})
        time.sleep(0.4)
    for k, m in [('meta_title', 'title_tag'), ('meta_description', 'description_tag')]:
        if k in updates:
            shopify_request(f'products/{pid}/metafields.json', 'POST', {'metafield': {'namespace': 'global', 'key': m, 'value': updates[k], 'type': 'single_line_text_field'}})
            time.sleep(0.3)
    return True


# ══════════════════════════════════════════════════════════════
# PAGES HTML
# ══════════════════════════════════════════════════════════════

@app.route('/')
def home():
    return '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KP SHOES - Gestion</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#0a0a0f;color:#fff;min-height:100vh}
.hd{background:#111;padding:15px 20px;border-bottom:1px solid #222;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:20px;font-weight:bold;color:#00ff88}
.stats{display:flex;gap:15px;padding:15px 20px;background:#0d0d14;flex-wrap:wrap}
.st{background:#1a1a2e;padding:12px 20px;border-radius:8px;text-align:center}
.st .v{font-size:24px;font-weight:bold;color:#00ff88}
.st .l{font-size:10px;color:#666;margin-top:3px}
.main{max-width:1400px;margin:0 auto;padding:20px}
.toolbar{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}
.search{flex:1;min-width:200px;padding:10px 15px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#fff}
.filter{padding:10px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#fff}
.btn{padding:10px 20px;border:none;border-radius:8px;font-weight:600;cursor:pointer}
.btn-s{background:#333;color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:15px}
.card{background:#111;border:1px solid #222;border-radius:10px;overflow:hidden;cursor:pointer;transition:all 0.2s}
.card:hover{border-color:#00ff88}
.card img{width:100%;height:180px;object-fit:cover;background:#1a1a2e}
.card-body{padding:12px}
.card-title{font-size:12px;font-weight:600;margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card-sku{font-size:10px;color:#666;margin-bottom:8px}
.card-meta{display:flex;justify-content:space-between;align-items:center}
.card-price{font-size:14px;font-weight:bold;color:#00ff88}
.card-vars{font-size:10px;color:#888}
.badge{padding:3px 8px;border-radius:10px;font-size:9px;font-weight:600}
.badge.excellent{background:#00ff8833;color:#00ff88}
.badge.good{background:#00cc6a33;color:#00cc6a}
.badge.warning{background:#ffa50033;color:#ffa500}
.badge.poor{background:#ff475733;color:#ff4757}
.loading{text-align:center;padding:60px;color:#666}
.spinner{width:35px;height:35px;border:3px solid #222;border-top-color:#00ff88;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 15px}
@keyframes spin{to{transform:rotate(360deg)}}
.msg{padding:12px 20px;background:#00ff8815;color:#00ff88;border-radius:8px;margin-bottom:15px;display:none;font-size:13px}
.msg.on{display:block}
</style>
</head>
<body>
<header class="hd">
<div class="logo">KP SHOES</div>
<div style="color:#666;font-size:12px">Gestion Shopify</div>
</header>
<div class="stats">
<div class="st"><div class="v" id="totalP">-</div><div class="l">PRODUITS</div></div>
<div class="st"><div class="v" id="totalV">-</div><div class="l">VARIANTES</div></div>
<div class="st"><div class="v" id="seoAvg">-</div><div class="l">SEO MOY.</div></div>
<div class="st"><div class="v" id="totalC">-</div><div class="l">COLLECTIONS</div></div>
</div>
<main class="main">
<div class="msg" id="msg"></div>
<div class="toolbar">
<input type="text" class="search" id="q" placeholder="Rechercher...">
<select class="filter" id="f">
<option value="">Tous</option>
<option value="excellent">Excellent (85+)</option>
<option value="good">Bon (70-84)</option>
<option value="warning">Moyen (50-69)</option>
<option value="poor">Faible (-50)</option>
</select>
<button class="btn btn-s" onclick="reload()">Actualiser</button>
</div>
<div class="grid" id="grid"><div class="loading"><div class="spinner"></div>Chargement...</div></div>
</main>
<script>
var P=[],C=[],sinceId=0,loading=false,totalV=0;

function load(){
    if(loading)return;
    loading=true;
    showMsg("Chargement... "+P.length+" produits");
    fetch("/api/products?since_id="+sinceId+"&limit=50")
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.collections)C=d.collections;
            if(d.products&&d.products.length>0){
                for(var i=0;i<d.products.length;i++){
                    var p=d.products[i];
                    var b=(p.body_html||"").toLowerCase();
                    p._lk=b.indexOf("kpshoes.fr/collections/")>=0;
                    p._ds=(p.body_html||"").length>100;
                    p._sc=(p._ds?30:0)+(p._lk?70:0);
                    if(p._sc>=85)p._seo="excellent";
                    else if(p._sc>=70)p._seo="good";
                    else if(p._sc>=50)p._seo="warning";
                    else p._seo="poor";
                    totalV+=(p.variants||[]).length;
                    P.push(p);
                }
                sinceId=d.products[d.products.length-1].id;
                updateStats();
                filter();
                loading=false;
                if(d.products.length>=50)setTimeout(load,300);
                else showMsg("");
            }else{
                showMsg("");
                loading=false;
                filter();
            }
        })
        .catch(function(e){showMsg("Erreur: "+e.message);loading=false;});
}

function updateStats(){
    document.getElementById("totalP").textContent=P.length;
    document.getElementById("totalV").textContent=totalV;
    document.getElementById("totalC").textContent=C.length;
    var avg=0;
    for(var i=0;i<P.length;i++)avg+=P[i]._sc;
    avg=P.length?Math.round(avg/P.length):0;
    document.getElementById("seoAvg").textContent=avg+"%";
}

function showMsg(t){
    var m=document.getElementById("msg");
    m.textContent=t;
    m.className=t?"msg on":"msg";
}

function filter(){
    var q=document.getElementById("q").value.toLowerCase();
    var f=document.getElementById("f").value;
    var L=[];
    for(var i=0;i<P.length;i++){
        var p=P[i];
        if(q&&p.title.toLowerCase().indexOf(q)<0)continue;
        if(f&&p._seo!==f)continue;
        L.push(p);
    }
    render(L);
}

function render(L){
    var el=document.getElementById("grid");
    if(!L.length&&!loading){el.innerHTML="<div class='loading'>Aucun produit</div>";return;}
    var html="";
    var max=Math.min(L.length,100);
    for(var i=0;i<max;i++){
        var p=L[i];
        var img=(p.image&&p.image.src)?p.image.src:"";
        var sku=(p.variants&&p.variants[0])?p.variants[0].sku||"":"";
        var price=(p.variants&&p.variants[0])?p.variants[0].price:"0";
        var nbV=(p.variants||[]).length;
        html+="<div class='card' onclick='go("+p.id+")'>";
        html+="<img src='"+img+"'>";
        html+="<div class='card-body'>";
        html+="<div class='card-title'>"+esc(p.title)+"</div>";
        html+="<div class='card-sku'>"+sku+"</div>";
        html+="<div class='card-meta'>";
        html+="<span class='card-price'>"+price+" EUR</span>";
        html+="<span class='badge "+p._seo+"'>"+p._sc+"%</span>";
        html+="</div>";
        html+="<div class='card-vars'>"+nbV+" variante"+(nbV>1?"s":"")+"</div>";
        html+="</div></div>";
    }
    if(L.length>100)html+="<div class='loading'>100 premiers</div>";
    el.innerHTML=html;
}

function esc(s){return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function go(id){window.location.href="/product/"+id;}
function reload(){P=[];C=[];sinceId=0;totalV=0;document.getElementById("grid").innerHTML="<div class='loading'><div class='spinner'></div>Chargement...</div>";load();}

document.getElementById("q").oninput=filter;
document.getElementById("f").onchange=filter;
load();
</script>
</body>
</html>'''


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    return f'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Produit - KP SHOES</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui;background:#0a0a0f;color:#fff;min-height:100vh}}
.hd{{background:#111;padding:12px 20px;border-bottom:1px solid #222;display:flex;align-items:center;gap:20px}}
.hd a{{color:#888;text-decoration:none}}
.hd a:hover{{color:#fff}}
.hd-title{{font-size:16px;font-weight:bold;color:#00ff88}}
.main{{max-width:1200px;margin:0 auto;padding:20px}}
.top{{display:grid;grid-template-columns:380px 1fr;gap:25px;margin-bottom:25px}}
.gallery{{background:#111;border-radius:10px;overflow:hidden}}
.main-img{{width:100%;height:380px;object-fit:contain;background:#1a1a2e}}
.thumbs{{display:flex;gap:8px;padding:12px;overflow-x:auto}}
.thumb{{width:55px;height:55px;object-fit:cover;border-radius:5px;cursor:pointer;border:2px solid transparent}}
.thumb:hover,.thumb.active{{border-color:#00ff88}}
.info{{display:flex;flex-direction:column;gap:15px}}
.title{{font-size:20px;font-weight:bold}}
.sku{{color:#666;font-size:13px}}
.price{{font-size:26px;font-weight:bold;color:#00ff88}}
.seo-box{{display:flex;align-items:center;gap:15px;background:#111;padding:15px;border-radius:10px}}
.score{{width:70px;height:70px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:bold}}
.score.excellent{{background:#00ff8833;color:#00ff88;border:3px solid #00ff88}}
.score.good{{background:#00cc6a33;color:#00cc6a;border:3px solid #00cc6a}}
.score.warning{{background:#ffa50033;color:#ffa500;border:3px solid #ffa500}}
.score.poor{{background:#ff475733;color:#ff4757;border:3px solid #ff4757}}
.score-info .label{{font-size:16px;font-weight:bold}}
.score-info .sub{{font-size:12px;color:#888}}
.btns{{display:flex;gap:10px}}
.btn{{padding:12px 20px;border:none;border-radius:8px;font-weight:600;cursor:pointer;font-size:13px;text-decoration:none}}
.btn-p{{background:#00ff88;color:#000}}
.btn-s{{background:#333;color:#fff}}
.section{{background:#111;border-radius:10px;padding:18px;margin-bottom:18px}}
.section-title{{font-size:14px;font-weight:bold;margin-bottom:12px;color:#00ff88}}
.checks{{display:flex;flex-direction:column;gap:8px}}
.check{{display:flex;align-items:center;gap:12px;padding:10px 12px;background:#1a1a2e;border-radius:6px}}
.check-icon{{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px}}
.check-icon.success{{background:#00ff8833;color:#00ff88}}
.check-icon.warning{{background:#ffa50033;color:#ffa500}}
.check-icon.error{{background:#ff475733;color:#ff4757}}
.check-info{{flex:1}}
.check-name{{font-weight:600;font-size:12px}}
.check-msg{{font-size:10px;color:#888}}
.check-pts{{font-weight:bold;font-size:11px}}
.meta-box{{background:#1a1a2e;border-radius:6px;padding:12px;margin-bottom:10px}}
.meta-label{{font-size:10px;color:#666;margin-bottom:4px}}
.meta-value{{font-size:12px;word-break:break-all}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid #222;font-size:12px}}
th{{background:#1a1a2e;font-size:10px;color:#888}}
.available{{color:#00ff88}}
.unavailable{{color:#ff4757}}
.loading{{text-align:center;padding:50px;color:#666}}
.spinner{{width:35px;height:35px;border:3px solid #222;border-top-color:#00ff88;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 15px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.toast{{position:fixed;bottom:20px;right:20px;padding:10px 18px;border-radius:6px;font-size:12px;z-index:100}}
.toast.success{{background:#00ff88;color:#000}}
.toast.error{{background:#ff4757}}
@media(max-width:800px){{.top{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header class="hd">
<a href="/">← Retour</a>
<div class="hd-title">Detail Produit</div>
</header>
<main class="main" id="main">
<div class="loading"><div class="spinner"></div>Chargement...</div>
</main>
<script>
var pid={product_id};
var P=null;
var SEO=null;
var SHOP="{SHOP}";

function load(){{
    fetch("/api/product/"+pid)
        .then(function(r){{return r.json();}})
        .then(function(d){{
            if(d.error){{document.getElementById("main").innerHTML="<div class='loading'>Produit non trouve</div>";return;}}
            P=d.product;
            SEO=d.seo;
            render();
        }})
        .catch(function(e){{document.getElementById("main").innerHTML="<div class='loading'>Erreur: "+e.message+"</div>";}});
}}

function render(){{
    var p=P;
    var seo=SEO;
    var mainImg=(p.images&&p.images[0])?p.images[0].src:"";
    var sku=(p.variants&&p.variants[0])?p.variants[0].sku||"N/A":"N/A";
    var price=(p.variants&&p.variants[0])?p.variants[0].price:"0";
    
    var h="<div class='top'>";
    h+="<div class='gallery'>";
    h+="<img class='main-img' id='mainImg' src='"+mainImg+"'>";
    if(p.images&&p.images.length>1){{
        h+="<div class='thumbs'>";
        for(var i=0;i<p.images.length;i++){{
            h+="<img class='thumb"+(i===0?" active":"")+"' src='"+p.images[i].src+"' onclick='chImg(this)'>";
        }}
        h+="</div>";
    }}
    h+="</div>";
    
    h+="<div class='info'>";
    h+="<div class='title'>"+esc(p.title)+"</div>";
    h+="<div class='sku'>SKU: "+sku+" | ID: "+p.id+"</div>";
    h+="<div class='price'>"+price+" EUR</div>";
    
    h+="<div class='seo-box'>";
    h+="<div class='score "+seo.status+"'>"+seo.score+"</div>";
    h+="<div class='score-info'><div class='label'>Score SEO</div><div class='sub'>"+getLabel(seo.status)+"</div></div>";
    h+="</div>";
    
    h+="<div class='btns'>";
    h+="<button class='btn btn-p' onclick='regen()'>Regenerer SEO</button>";
    h+="<a href='https://"+SHOP+"/admin/products/"+p.id+"' target='_blank' class='btn btn-s'>Voir Shopify</a>";
    h+="</div>";
    h+="</div></div>";
    
    h+="<div class='section'><div class='section-title'>Analyse SEO</div><div class='checks'>";
    for(var i=0;i<seo.checks.length;i++){{
        var c=seo.checks[i];
        var icon=c.status==="success"?"✓":c.status==="warning"?"!":"✗";
        h+="<div class='check'>";
        h+="<div class='check-icon "+c.status+"'>"+icon+"</div>";
        h+="<div class='check-info'><div class='check-name'>"+c.name+"</div><div class='check-msg'>"+c.message+"</div></div>";
        h+="<div class='check-pts'>"+c.points+"/"+c.max+"</div>";
        h+="</div>";
    }}
    h+="</div></div>";
    
    h+="<div class='section'><div class='section-title'>Donnees SEO</div>";
    h+="<div class='meta-box'><div class='meta-label'>META TITLE</div><div class='meta-value'>"+(seo.meta_title||"Non defini")+"</div></div>";
    h+="<div class='meta-box'><div class='meta-label'>META DESCRIPTION</div><div class='meta-value'>"+(seo.meta_description||"Non definie")+"</div></div>";
    h+="<div class='meta-box'><div class='meta-label'>DESCRIPTION</div><div class='meta-value' style='max-height:150px;overflow-y:auto'>"+(p.body_html||"Non definie")+"</div></div>";
    h+="</div>";
    
    h+="<div class='section'><div class='section-title'>Variantes ("+p.variants.length+")</div>";
    h+="<table><thead><tr><th>Taille</th><th>SKU</th><th>Prix</th><th>Compare</th><th>Stock</th><th>Dispo</th></tr></thead><tbody>";
    for(var i=0;i<p.variants.length;i++){{
        var v=p.variants[i];
        var av=v.inventory_quantity>0||v.inventory_policy==="continue";
        h+="<tr>";
        h+="<td><strong>"+v.title+"</strong></td>";
        h+="<td>"+(v.sku||"-")+"</td>";
        h+="<td><strong>"+v.price+" EUR</strong></td>";
        h+="<td>"+(v.compare_at_price||"-")+"</td>";
        h+="<td>"+v.inventory_quantity+"</td>";
        h+="<td class='"+(av?"available":"unavailable")+"'>"+(av?"Oui":"Non")+"</td>";
        h+="</tr>";
    }}
    h+="</tbody></table></div>";
    
    document.getElementById("main").innerHTML=h;
}}

function getLabel(s){{
    if(s==="excellent")return"Excellent";
    if(s==="good")return"Bon";
    if(s==="warning")return"A ameliorer";
    return"Faible";
}}

function chImg(el){{
    document.getElementById("mainImg").src=el.src;
    var all=document.querySelectorAll(".thumb");
    for(var i=0;i<all.length;i++)all[i].classList.remove("active");
    el.classList.add("active");
}}

function esc(s){{return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}}

function regen(){{
    toast("Regeneration...","success");
    fetch("/api/seo/apply",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{product_id:pid}})}})
        .then(function(r){{return r.json();}})
        .then(function(d){{
            if(d.success){{toast("SEO mis a jour!","success");setTimeout(function(){{location.reload();}},1500);}}
            else{{toast("Erreur","error");}}
        }})
        .catch(function(e){{toast("Erreur","error");}});
}}

function toast(m,t){{
    var e=document.createElement("div");
    e.className="toast "+t;
    e.textContent=m;
    document.body.appendChild(e);
    setTimeout(function(){{e.remove();}},3000);
}}

load();
</script>
</body>
</html>'''


# ══════════════════════════════════════════════════════════════
# API ROUTES
# ══════════════════════════════════════════════════════════════

@app.route('/api/products')
def api_products():
    since_id = request.args.get('since_id', '0')
    limit = request.args.get('limit', '50')
    r = shopify_request(f'products.json?limit={limit}&since_id={since_id}')
    products = r.get('products', []) if r else []
    return jsonify({'products': products, 'collections': get_collections()})


@app.route('/api/product/<int:product_id>')
def api_product(product_id):
    r = shopify_request(f'products/{product_id}.json')
    if not r or 'product' not in r:
        return jsonify({'error': 'Not found'}), 404
    product = r['product']
    metafields = get_product_metafields(product_id)
    seo = analyze_seo(product, metafields['meta_title'], metafields['meta_description'])
    seo['meta_title'] = metafields['meta_title']
    seo['meta_description'] = metafields['meta_description']
    return jsonify({'product': product, 'seo': seo})


@app.route('/api/collections')
def api_collections():
    return jsonify({'collections': get_collections(), 'count': len(get_collections())})


@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)


@app.route('/api/seo/apply', methods=['POST'])
def api_apply_seo():
    pid = request.json.get('product_id')
    r = shopify_request(f'products/{pid}.json')
    if not r: return jsonify({'error': 'err'}), 404
    p = r['product']
    seo = generate_seo(p, get_collections())
    update_product_seo(pid, seo)
    return jsonify({'success': True})


@app.route('/api/seo/batch', methods=['POST'])
def api_batch_seo():
    global task_progress
    pids = request.json.get('product_ids', [])
    def run():
        global task_progress
        task_progress = {'running': True, 'current': 0, 'total': len(pids), 'message': 'Demarrage...'}
        cols = get_collections()
        for i, pid in enumerate(pids):
            task_progress['current'] = i + 1
            r = shopify_request(f'products/{pid}.json')
            if r and 'product' in r:
                p = r['product']
                task_progress['message'] = p.get('title','')[:30]
                seo = generate_seo(p, cols)
                update_product_seo(pid, seo)
            time.sleep(1)
        task_progress = {'running': False, 'current': len(pids), 'total': len(pids), 'message': 'Termine!'}
    Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


@app.route('/seo')
def seo_redirect():
    return '<meta http-equiv="refresh" content="0;url=/">'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
