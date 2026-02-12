"""
KP SHOES - Plateforme de Gestion Shopify
Version 5.0 - Dashboard Produits + Détails + Variantes + SEO
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
    """Récupère les metafields SEO d'un produit"""
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


# ══════════════════════════════════════════════════════════════
# COLLECTIONS MAPPING
# ══════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════
# ANALYSE SEO - Basée sur nos critères
# ══════════════════════════════════════════════════════════════

def analyze_seo(product, meta_title, meta_description):
    """Analyse complète SEO d'un produit"""
    title = product.get('title', '')
    body_html = product.get('body_html', '') or ''
    
    results = {
        'score': 0,
        'max_score': 100,
        'checks': []
    }
    
    # 1. META TITLE (25 points)
    meta_title_check = {'name': 'Meta Title', 'points': 0, 'max': 25, 'status': 'error', 'message': ''}
    if meta_title:
        if SITE_NAME in meta_title and len(meta_title) <= 60:
            meta_title_check['points'] = 25
            meta_title_check['status'] = 'success'
            meta_title_check['message'] = f'OK ({len(meta_title)} caractères)'
        elif len(meta_title) > 60:
            meta_title_check['points'] = 10
            meta_title_check['status'] = 'warning'
            meta_title_check['message'] = f'Trop long ({len(meta_title)}/60 caractères)'
        else:
            meta_title_check['points'] = 15
            meta_title_check['status'] = 'warning'
            meta_title_check['message'] = f'Manque "{SITE_NAME}"'
    else:
        meta_title_check['message'] = 'Absent'
    results['checks'].append(meta_title_check)
    results['score'] += meta_title_check['points']
    
    # 2. META DESCRIPTION (25 points)
    meta_desc_check = {'name': 'Meta Description', 'points': 0, 'max': 25, 'status': 'error', 'message': ''}
    if meta_description:
        has_auth = '100%' in meta_description or 'authentique' in meta_description.lower()
        good_length = 100 <= len(meta_description) <= 155
        if has_auth and good_length:
            meta_desc_check['points'] = 25
            meta_desc_check['status'] = 'success'
            meta_desc_check['message'] = f'OK ({len(meta_description)} caractères)'
        elif good_length:
            meta_desc_check['points'] = 15
            meta_desc_check['status'] = 'warning'
            meta_desc_check['message'] = 'Manque mention authenticité'
        else:
            meta_desc_check['points'] = 10
            meta_desc_check['status'] = 'warning'
            meta_desc_check['message'] = f'Longueur: {len(meta_description)} (idéal: 100-155)'
    else:
        meta_desc_check['message'] = 'Absente'
    results['checks'].append(meta_desc_check)
    results['score'] += meta_desc_check['points']
    
    # 3. DESCRIPTION avec lien collection (35 points)
    desc_check = {'name': 'Description + Lien', 'points': 0, 'max': 35, 'status': 'error', 'message': ''}
    has_desc = len(body_html) > 100
    has_link = f'{SITE_DOMAIN}/collections/' in body_html.lower()
    if has_desc and has_link:
        desc_check['points'] = 35
        desc_check['status'] = 'success'
        desc_check['message'] = 'Description complète avec lien interne'
    elif has_desc:
        desc_check['points'] = 15
        desc_check['status'] = 'warning'
        desc_check['message'] = 'Description OK mais sans lien collection'
    else:
        desc_check['message'] = 'Description manquante ou trop courte'
    results['checks'].append(desc_check)
    results['score'] += desc_check['points']
    
    # 4. INFOS TECHNIQUES - SKU (15 points)
    sku_check = {'name': 'SKU/Référence', 'points': 0, 'max': 15, 'status': 'error', 'message': ''}
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    if sku:
        sku_check['points'] = 15
        sku_check['status'] = 'success'
        sku_check['message'] = f'SKU: {sku}'
    else:
        sku_check['message'] = 'SKU manquant'
    results['checks'].append(sku_check)
    results['score'] += sku_check['points']
    
    # Statut global
    if results['score'] >= 85:
        results['status'] = 'excellent'
    elif results['score'] >= 70:
        results['status'] = 'good'
    elif results['score'] >= 50:
        results['status'] = 'warning'
    else:
        results['status'] = 'poor'
    
    return results


# ══════════════════════════════════════════════════════════════
# GÉNÉRATION SEO (mêmes règles qu'avant)
# ══════════════════════════════════════════════════════════════

MODEL_DESCRIPTIONS = {
    'jordan 4': """Conçue par Tinker Hatfield en 1989, la Air Jordan 4 est l'une des silhouettes les plus emblématiques de la ligne Jordan. Rendue célèbre par Michael Jordan lors des playoffs NBA, elle se distingue par ses ailes en mesh, sa languette en plastique et ses lacets à ailettes.""",
    'jordan 1 high': """La Air Jordan 1 High, créée en 1985 par Peter Moore, est la sneaker qui a tout commencé. Avec son col haut caractéristique et son design intemporel, elle reste aujourd'hui l'une des sneakers les plus convoitées au monde.""",
    'jordan 1 low': """Version basse de l'iconique Air Jordan 1, cette silhouette reprend l'ADN de la légendaire sneaker dans un format plus décontracté. Parfaite pour un style quotidien.""",
    'dunk': """Créée en 1985 comme chaussure de basketball universitaire, la Nike Dunk est devenue une icône de la culture sneakers. Son design simple mais efficace en font l'une des silhouettes les plus populaires.""",
    'air force 1': """Créée en 1982 par Bruce Kilgore, la Nike Air Force 1 est la première chaussure de basketball à intégrer la technologie Air. Un classique indémodable.""",
    'samba': """L'Adidas Samba est une légende née en 1950, initialement conçue pour le football en salle. Avec sa tige en cuir et ses trois bandes iconiques, elle est devenue un classique du style casual.""",
    'campus': """L'Adidas Campus réinterprète le classique des années 80 avec une construction modernisée. Upper en suède premium et trois bandes contrastées.""",
    'yeezy slide': """La Yeezy Slide a redéfini les standards de la sandale de luxe. Son design minimaliste en mousse EVA offre un confort cloud-like unique.""",
    'yeezy 350': """La Yeezy Boost 350 V2 est l'une des sneakers les plus influentes de la dernière décennie. Son upper Primeknit et sa semelle Boost en font une pièce collector.""",
    'new balance 550': """Ressortie en 2021, la New Balance 550 est devenue un phénomène de mode. Son design basketball vintage en fait la sneaker parfaite pour le style rétro.""",
    'gel-1130': """L'Asics Gel-1130 est une running technique des années 2000 devenue un must-have du streetwear. Son design Y2K est très recherché.""",
    'tasman': """La UGG Tasman est une slipper incontournable. Doublure en peau de mouton authentique pour un confort incomparable.""",
    'crocs': """Les Crocs sont devenues un phénomène de mode. Design unique en Croslite, légèreté et confort incomparables.""",
}

DEFAULT_DESC = """Un modèle qui allie design contemporain et qualité premium. Finitions soignées et confort au quotidien."""


def get_model_description(title):
    t = title.lower()
    for key, desc in MODEL_DESCRIPTIONS.items():
        if key in t: return desc
    return DEFAULT_DESC


def generate_seo(product, collections):
    """Génère les SEO pour un produit"""
    title = product.get('title', '')
    brand = extract_brand(title)
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    collection = find_collection(title, collections)
    model_desc = get_model_description(title)
    
    # Meta Title
    meta_title = f"{title} | {SITE_NAME}"
    if len(meta_title) > 60:
        meta_title = title[:47] + "... | " + SITE_NAME
    
    # Meta Description
    if sku:
        meta_description = f"Achetez {title} ({sku}) | 100% Authentique | Livraison rapide | {SITE_NAME}"[:155]
    else:
        meta_description = f"Achetez {title} | 100% Authentique | Livraison rapide | {SITE_NAME}"[:155]
    
    # Description HTML
    lines = []
    if collection:
        link = f'<a href="{collection["url"]}">{collection["title"]}</a>'
        lines.append(f'<p>Découvrez la <strong>{title}</strong> disponible sur {SITE_NAME}. Retrouvez ce modèle dans notre collection {link}.</p>')
    else:
        lines.append(f'<p>Découvrez la <strong>{title}</strong> disponible sur {SITE_NAME}.</p>')
    lines.append(f'<p>{model_desc}</p>')
    tech = [f'<strong>Marque</strong> : {brand}']
    if sku: tech.insert(0, f'<strong>Référence</strong> : {sku}')
    lines.append('<p>' + '<br>'.join(tech) + '</p>')
    lines.append(f'<p>Chez <strong>{SITE_NAME}</strong>, nous garantissons l\'authenticité de chaque paire. Toutes nos sneakers sont vérifiées par nos experts avant expédition.</p>')
    body_html = '\n\n'.join(lines)
    
    return {
        'meta_title': meta_title,
        'meta_description': meta_description,
        'body_html': body_html,
        'collection': collection
    }


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
# ROUTES - PAGES HTML
# ══════════════════════════════════════════════════════════════

@app.route('/')
def home():
    return '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KP SHOES - Gestion Shopify</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#0a0a0f;color:#fff;min-height:100vh}
.header{background:linear-gradient(135deg,#111 0%,#1a1a2e 100%);padding:20px;border-bottom:1px solid #222}
.header-content{max-width:1400px;margin:0 auto;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:24px;font-weight:bold;color:#00ff88}
.logo span{color:#fff}
.nav{display:flex;gap:15px}
.nav a{color:#888;text-decoration:none;padding:8px 16px;border-radius:6px;transition:all 0.2s}
.nav a:hover,.nav a.active{color:#fff;background:#222}

.stats-bar{background:#111;padding:15px 20px;border-bottom:1px solid #222}
.stats-content{max-width:1400px;margin:0 auto;display:flex;gap:20px;flex-wrap:wrap}
.stat-card{background:#1a1a2e;padding:15px 25px;border-radius:10px;text-align:center}
.stat-value{font-size:28px;font-weight:bold;color:#00ff88}
.stat-label{font-size:11px;color:#666;margin-top:5px}

.main{max-width:1400px;margin:0 auto;padding:20px}
.toolbar{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
.search{flex:1;min-width:200px;padding:10px 15px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#fff;font-size:14px}
.filter{padding:10px 15px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#fff}
.btn{padding:10px 20px;border:none;border-radius:8px;font-weight:600;cursor:pointer;transition:all 0.2s}
.btn-primary{background:#00ff88;color:#000}
.btn-primary:hover{background:#00cc6a}
.btn-secondary{background:#333;color:#fff}
.btn-danger{background:#ff4757;color:#fff}

.products-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:15px}
.product-card{background:#111;border:1px solid #222;border-radius:12px;overflow:hidden;cursor:pointer;transition:all 0.2s}
.product-card:hover{border-color:#00ff88;transform:translateY(-2px)}
.product-image{width:100%;height:200px;object-fit:cover;background:#1a1a2e}
.product-info{padding:15px}
.product-title{font-size:13px;font-weight:600;margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.product-sku{font-size:11px;color:#666;margin-bottom:10px}
.product-meta{display:flex;justify-content:space-between;align-items:center}
.product-price{font-size:16px;font-weight:bold;color:#00ff88}
.product-variants{font-size:11px;color:#888}
.seo-badge{padding:4px 10px;border-radius:20px;font-size:10px;font-weight:600}
.seo-badge.excellent{background:#00ff8833;color:#00ff88}
.seo-badge.good{background:#00ff8822;color:#00cc6a}
.seo-badge.warning{background:#ffa50033;color:#ffa500}
.seo-badge.poor{background:#ff475733;color:#ff4757}

.loading{text-align:center;padding:60px}
.spinner{width:40px;height:40px;border:3px solid #222;border-top-color:#00ff88;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 15px}
@keyframes spin{to{transform:rotate(360deg)}}

.msg{padding:15px 20px;background:#00ff8815;color:#00ff88;border-radius:8px;margin-bottom:20px;display:none}
.msg.on{display:block}
</style>
</head>
<body>
<header class="header">
<div class="header-content">
<div class="logo">KP <span>SHOES</span></div>
<nav class="nav">
<a href="/" class="active">Produits</a>
<a href="/seo">SEO Manager</a>
</nav>
</div>
</header>

<div class="stats-bar">
<div class="stats-content">
<div class="stat-card"><div class="stat-value" id="totalProducts">-</div><div class="stat-label">PRODUITS</div></div>
<div class="stat-card"><div class="stat-value" id="totalVariants">-</div><div class="stat-label">VARIANTES</div></div>
<div class="stat-card"><div class="stat-value" id="seoScore">-</div><div class="stat-label">SCORE SEO</div></div>
<div class="stat-card"><div class="stat-value" id="collections">-</div><div class="stat-label">COLLECTIONS</div></div>
</div>
</div>

<main class="main">
<div class="msg" id="msg"></div>
<div class="toolbar">
<input type="text" class="search" id="search" placeholder="Rechercher un produit...">
<select class="filter" id="filterSeo">
<option value="">Tous les SEO</option>
<option value="excellent">Excellent (85+)</option>
<option value="good">Bon (70-84)</option>
<option value="warning">Moyen (50-69)</option>
<option value="poor">Faible (-50)</option>
</select>
<button class="btn btn-secondary" onclick="reload()">Actualiser</button>
</div>
<div class="products-grid" id="products">
<div class="loading"><div class="spinner"></div>Chargement des produits...</div>
</div>
</main>

<script>
var P=[], C=[], sinceId=0, loading=false, totalVariants=0;

function loadProducts(){
    if(loading) return;
    loading=true;
    showMsg("Chargement... "+P.length+" produits");
    fetch("/api/products?since_id="+sinceId+"&limit=50")
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.collections) C=d.collections;
            if(d.products && d.products.length>0){
                d.products.forEach(function(p){
                    var b=(p.body_html||"").toLowerCase();
                    p._lk=b.indexOf("kpshoes.fr/collections/")>=0;
                    p._ds=(p.body_html||"").length>100;
                    p._sc=(p._ds?30:0)+(p._lk?70:0);
                    if(p._sc>=85) p._seo="excellent";
                    else if(p._sc>=70) p._seo="good";
                    else if(p._sc>=50) p._seo="warning";
                    else p._seo="poor";
                    totalVariants += (p.variants||[]).length;
                    P.push(p);
                });
                sinceId=d.products[d.products.length-1].id;
                updateStats();
                filter();
                loading=false;
                if(d.products.length>=50) setTimeout(loadProducts,300);
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
    document.getElementById("totalProducts").textContent=P.length;
    document.getElementById("totalVariants").textContent=totalVariants;
    document.getElementById("collections").textContent=C.length;
    var avgSeo=0;
    P.forEach(function(p){avgSeo+=p._sc;});
    avgSeo=P.length?Math.round(avgSeo/P.length):0;
    document.getElementById("seoScore").textContent=avgSeo+"%";
}

function showMsg(t){
    var m=document.getElementById("msg");
    m.textContent=t;
    m.className=t?"msg on":"msg";
}

function filter(){
    var q=document.getElementById("search").value.toLowerCase();
    var f=document.getElementById("filterSeo").value;
    var L=P.filter(function(p){
        if(q && p.title.toLowerCase().indexOf(q)<0) return false;
        if(f && p._seo!==f) return false;
        return true;
    });
    render(L);
}

function render(L){
    var el=document.getElementById("products");
    if(!L.length && !loading){
        el.innerHTML="<div class='loading'>Aucun produit trouvé</div>";
        return;
    }
    var html="";
    L.slice(0,100).forEach(function(p){
        var img=(p.image&&p.image.src)?p.image.src:"";
        var sku=(p.variants&&p.variants[0])?p.variants[0].sku||"":"";
        var price=(p.variants&&p.variants[0])?p.variants[0].price:"0";
        var nbVar=(p.variants||[]).length;
        html+='<div class="product-card" onclick="openProduct('+p.id+')">';
        html+='<img class="product-image" src="'+img+'">';
        html+='<div class="product-info">';
        html+='<div class="product-title">'+esc(p.title)+'</div>';
        html+='<div class="product-sku">'+sku+'</div>';
        html+='<div class="product-meta">';
        html+='<span class="product-price">'+price+' EUR</span>';
        html+='<span class="seo-badge '+p._seo+'">SEO '+p._sc+'%</span>';
        html+='</div>';
        html+='<div class="product-variants">'+nbVar+' variante'+(nbVar>1?'s':'')+'</div>';
        html+='</div></div>';
    });
    if(L.length>100) html+="<div class='loading'>100 premiers affichés</div>";
    el.innerHTML=html;
}

function esc(s){return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

function openProduct(id){
    window.location.href="/product/"+id;
}

function reload(){
    P=[];C=[];sinceId=0;totalVariants=0;
    document.getElementById("products").innerHTML="<div class='loading'><div class='spinner'></div>Chargement...</div>";
    loadProducts();
}

document.getElementById("search").oninput=filter;
document.getElementById("filterSeo").onchange=filter;
loadProducts();
</script>
</body>
</html>'''


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    return '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Détail Produit - KP SHOES</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#0a0a0f;color:#fff;min-height:100vh}
.header{background:#111;padding:15px 20px;border-bottom:1px solid #222;display:flex;align-items:center;gap:20px}
.back{color:#888;text-decoration:none;display:flex;align-items:center;gap:5px}
.back:hover{color:#fff}
.header-title{font-size:18px;font-weight:bold;color:#00ff88}

.main{max-width:1200px;margin:0 auto;padding:20px}
.product-header{display:grid;grid-template-columns:400px 1fr;gap:30px;margin-bottom:30px}
.gallery{background:#111;border-radius:12px;overflow:hidden}
.main-image{width:100%;height:400px;object-fit:contain;background:#1a1a2e}
.thumbnails{display:flex;gap:10px;padding:15px;overflow-x:auto}
.thumb{width:60px;height:60px;object-fit:cover;border-radius:6px;cursor:pointer;border:2px solid transparent}
.thumb:hover,.thumb.active{border-color:#00ff88}

.product-details{display:flex;flex-direction:column;gap:20px}
.product-title{font-size:24px;font-weight:bold}
.product-sku{color:#666;font-size:14px}
.product-price{font-size:28px;font-weight:bold;color:#00ff88}

.section{background:#111;border-radius:12px;padding:20px;margin-bottom:20px}
.section-title{font-size:16px;font-weight:bold;margin-bottom:15px;color:#00ff88;display:flex;align-items:center;gap:10px}
.section-title .icon{font-size:20px}

.seo-score{display:flex;align-items:center;gap:20px;margin-bottom:20px}
.score-circle{width:80px;height:80px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:bold}
.score-circle.excellent{background:#00ff8833;color:#00ff88;border:3px solid #00ff88}
.score-circle.good{background:#00cc6a33;color:#00cc6a;border:3px solid #00cc6a}
.score-circle.warning{background:#ffa50033;color:#ffa500;border:3px solid #ffa500}
.score-circle.poor{background:#ff475733;color:#ff4757;border:3px solid #ff4757}
.score-label{font-size:14px;color:#888}

.seo-checks{display:flex;flex-direction:column;gap:10px}
.seo-check{display:flex;align-items:center;gap:15px;padding:12px 15px;background:#1a1a2e;border-radius:8px}
.check-icon{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px}
.check-icon.success{background:#00ff8833;color:#00ff88}
.check-icon.warning{background:#ffa50033;color:#ffa500}
.check-icon.error{background:#ff475733;color:#ff4757}
.check-info{flex:1}
.check-name{font-weight:600;font-size:13px}
.check-message{font-size:11px;color:#888;margin-top:2px}
.check-points{font-weight:bold;font-size:12px}

.meta-box{background:#1a1a2e;border-radius:8px;padding:15px;margin-bottom:15px}
.meta-label{font-size:11px;color:#666;margin-bottom:5px}
.meta-value{font-size:13px;word-break:break-all}

.variants-table{width:100%;border-collapse:collapse}
.variants-table th,.variants-table td{padding:12px 15px;text-align:left;border-bottom:1px solid #222}
.variants-table th{background:#1a1a2e;font-size:11px;color:#888;font-weight:600}
.variants-table td{font-size:13px}
.variant-available{color:#00ff88}
.variant-unavailable{color:#ff4757}
.variant-price{font-weight:bold}

.btn{padding:12px 24px;border:none;border-radius:8px;font-weight:600;cursor:pointer;font-size:14px}
.btn-primary{background:#00ff88;color:#000}
.btn-secondary{background:#333;color:#fff}
.btn-group{display:flex;gap:10px;margin-top:20px}

.loading{text-align:center;padding:60px;color:#888}
.spinner{width:40px;height:40px;border:3px solid #222;border-top-color:#00ff88;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 15px}
@keyframes spin{to{transform:rotate(360deg)}}

.toast{position:fixed;bottom:20px;right:20px;padding:12px 20px;border-radius:8px;font-size:13px;z-index:100}
.toast.success{background:#00ff88;color:#000}
.toast.error{background:#ff4757;color:#fff}
</style>
</head>
<body>
<header class="header">
<a href="/" class="back">← Retour</a>
<div class="header-title">Détail Produit</div>
</header>

<main class="main" id="main">
<div class="loading"><div class="spinner"></div>Chargement du produit...</div>
</main>

<script>
var productId = ''' + str(product_id) + ''';
var product = null;
var seoData = null;

function loadProduct(){
    fetch("/api/product/"+productId)
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.error){
                document.getElementById("main").innerHTML="<div class='loading'>Produit non trouvé</div>";
                return;
            }
            product=d.product;
            seoData=d.seo;
            render();
        })
        .catch(function(e){
            document.getElementById("main").innerHTML="<div class='loading'>Erreur: "+e.message+"</div>";
        });
}

function render(){
    var p=product;
    var seo=seoData;
    var mainImg=(p.images&&p.images[0])?p.images[0].src:"";
    var sku=(p.variants&&p.variants[0])?p.variants[0].sku||"N/A":"N/A";
    var price=(p.variants&&p.variants[0])?p.variants[0].price:"0";
    
    var html='<div class="product-header">';
    
    // Gallery
    html+='<div class="gallery">';
    html+='<img class="main-image" id="mainImage" src="'+mainImg+'">';
    if(p.images && p.images.length>1){
        html+='<div class="thumbnails">';
        p.images.forEach(function(img,i){
            html+='<img class="thumb'+(i===0?" active":"")+'" src="'+img.src+'" onclick="changeImage(this,\''+img.src+'\')">';
        });
        html+='</div>';
    }
    html+='</div>';
    
    // Details
    html+='<div class="product-details">';
    html+='<div class="product-title">'+esc(p.title)+'</div>';
    html+='<div class="product-sku">SKU: '+sku+' | ID: '+p.id+'</div>';
    html+='<div class="product-price">'+price+' EUR</div>';
    
    // SEO Score
    html+='<div class="seo-score">';
    html+='<div class="score-circle '+seo.status+'">'+seo.score+'</div>';
    html+='<div><div style="font-size:18px;font-weight:bold">Score SEO</div><div class="score-label">'+getStatusLabel(seo.status)+'</div></div>';
    html+='</div>';
    
    html+='<div class="btn-group">';
    html+='<button class="btn btn-primary" onclick="regenerateSeo()">Régénérer SEO</button>';
    html+='<a href="https://'+window.location.hostname.replace("shopify-manager-yzj3.onrender.com","")+'capet-shop.myshopify.com/admin/products/'+p.id+'" target="_blank" class="btn btn-secondary">Voir sur Shopify</a>';
    html+='</div>';
    html+='</div></div>';
    
    // SEO Section
    html+='<div class="section">';
    html+='<div class="section-title"><span class="icon">🎯</span> Analyse SEO</div>';
    html+='<div class="seo-checks">';
    seo.checks.forEach(function(check){
        html+='<div class="seo-check">';
        html+='<div class="check-icon '+check.status+'">'+(check.status==="success"?"✓":check.status==="warning"?"!":"✗")+'</div>';
        html+='<div class="check-info"><div class="check-name">'+check.name+'</div><div class="check-message">'+check.message+'</div></div>';
        html+='<div class="check-points">'+check.points+'/'+check.max+'</div>';
        html+='</div>';
    });
    html+='</div></div>';
    
    // Meta Data
    html+='<div class="section">';
    html+='<div class="section-title"><span class="icon">📝</span> Données SEO</div>';
    html+='<div class="meta-box"><div class="meta-label">META TITLE</div><div class="meta-value">'+(seo.meta_title||"<em>Non défini</em>")+'</div></div>';
    html+='<div class="meta-box"><div class="meta-label">META DESCRIPTION</div><div class="meta-value">'+(seo.meta_description||"<em>Non définie</em>")+'</div></div>';
    html+='<div class="meta-box"><div class="meta-label">DESCRIPTION</div><div class="meta-value" style="max-height:200px;overflow-y:auto">'+(p.body_html||"<em>Non définie</em>")+'</div></div>';
    html+='</div>';
    
    // Variants
    html+='<div class="section">';
    html+='<div class="section-title"><span class="icon">📦</span> Variantes ('+p.variants.length+')</div>';
    html+='<table class="variants-table">';
    html+='<thead><tr><th>Taille</th><th>SKU</th><th>Prix</th><th>Compare</th><th>Stock</th><th>Disponible</th></tr></thead>';
    html+='<tbody>';
    p.variants.forEach(function(v){
        var available=v.inventory_quantity>0 || v.inventory_policy==="continue";
        html+='<tr>';
        html+='<td><strong>'+v.title+'</strong></td>';
        html+='<td>'+v.sku+'</td>';
        html+='<td class="variant-price">'+v.price+' EUR</td>';
        html+='<td>'+(v.compare_at_price||"-")+'</td>';
        html+='<td>'+v.inventory_quantity+'</td>';
        html+='<td class="'+(available?"variant-available":"variant-unavailable")+'">'+(available?"Oui":"Non")+'</td>';
        html+='</tr>';
    });
    html+='</tbody></table>';
    html+='</div>';
    
    document.getElementById("main").innerHTML=html;
}

function getStatusLabel(status){
    if(status==="excellent") return "Excellent - Très bien optimisé";
    if(status==="good") return "Bon - Bien optimisé";
    if(status==="warning") return "Moyen - À améliorer";
    return "Faible - Optimisation requise";
}

function changeImage(thumb, src){
    document.getElementById("mainImage").src=src;
    document.querySelectorAll(".thumb").forEach(function(t){t.classList.remove("active");});
    thumb.classList.add("active");
}

function esc(s){return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

function regenerateSeo(){
    toast("Régénération SEO...","success");
    fetch("/api/seo/apply",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:productId})})
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.success){
                toast("SEO mis à jour!","success");
                setTimeout(function(){location.reload();},1500);
            }else{
                toast("Erreur","error");
            }
        })
        .catch(function(e){toast("Erreur: "+e.message,"error");});
}

function toast(msg,type){
    var t=document.createElement("div");
    t.className="toast "+type;
    t.textContent=msg;
    document.body.appendChild(t);
    setTimeout(function(){t.remove();},3000);
}

loadProduct();
</script>
</body>
</html>'''


# ══════════════════════════════════════════════════════════════
# ROUTES API
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
    """Récupère un produit avec toutes ses infos + analyse SEO"""
    r = shopify_request(f'products/{product_id}.json')
    if not r or 'product' not in r:
        return jsonify({'error': 'Product not found'}), 404
    
    product = r['product']
    metafields = get_product_metafields(product_id)
    seo_analysis = analyze_seo(product, metafields['meta_title'], metafields['meta_description'])
    seo_analysis['meta_title'] = metafields['meta_title']
    seo_analysis['meta_description'] = metafields['meta_description']
    
    return jsonify({
        'product': product,
        'seo': seo_analysis
    })


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
    return jsonify({'success': True, 'collection': seo.get('collection')})


@app.route('/api/seo/batch', methods=['POST'])
def api_batch_seo():
    global task_progress
    pids = request.json.get('product_ids', [])
    def run():
        global task_progress
        task_progress = {'running': True, 'current': 0, 'total': len(pids), 'message': 'Démarrage...'}
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
        task_progress = {'running': False, 'current': len(pids), 'total': len(pids), 'message': f'Terminé! {len(pids)} produits'}
    Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


# Ancienne route SEO pour compatibilité
@app.route('/seo')
def seo_page():
    return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta http-equiv="refresh" content="0;url=/"></head><body>Redirection...</body></html>'''


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
