"""
KP SHOES - Plateforme de Gestion Shopify V8
Avec import photos GOAT via curl_cffi
"""

from flask import Flask, jsonify, request
import json, os, time, re, ssl, logging
from urllib.request import Request, urlopen
from urllib.parse import quote
from threading import Thread

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

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
        print(f"[Shopify Err] {e}")
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


# ══════════════════════════════════════════════════════════════
# GOAT IMAGES via App 360 (microservice)
# ══════════════════════════════════════════════════════════════

# URL de l'app 360 qui récupère les photos GOAT
GOAT_SERVICE_URL = os.environ.get('GOAT_SERVICE_URL', 'https://shopify-360-viewer.onrender.com')

def get_goat_images(sku):
    """Récupère les images GOAT via l'app 360."""
    try:
        import urllib.request
        import json
        
        url = f"{GOAT_SERVICE_URL}/api/goat/search"
        data = json.dumps({"sku": sku}).encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            method='POST'
        )
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, context=ctx, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
        
        if result.get('success') and result.get('product'):
            product = result['product']
            return {
                'name': product.get('name', ''),
                'sku': product.get('sku', sku),
                'images': product.get('images', [])
            }
        
        return None
        
    except Exception as e:
        log.error(f"[GOAT Service] Error: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# Collections & SEO
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


def analyze_seo(product, meta_title, meta_description):
    body_html = product.get('body_html', '') or ''
    results = {'score': 0, 'max_score': 100, 'checks': []}
    
    check1 = {'name': 'Meta Title', 'points': 0, 'max': 25, 'status': 'error', 'message': 'Absent'}
    if meta_title:
        if SITE_NAME in meta_title and len(meta_title) <= 60:
            check1 = {'name': 'Meta Title', 'points': 25, 'max': 25, 'status': 'success', 'message': 'OK (' + str(len(meta_title)) + ' car.)'}
        elif len(meta_title) > 60:
            check1 = {'name': 'Meta Title', 'points': 10, 'max': 25, 'status': 'warning', 'message': 'Trop long'}
        else:
            check1 = {'name': 'Meta Title', 'points': 15, 'max': 25, 'status': 'warning', 'message': 'Manque KP SHOES'}
    results['checks'].append(check1)
    results['score'] += check1['points']
    
    check2 = {'name': 'Meta Description', 'points': 0, 'max': 25, 'status': 'error', 'message': 'Absente'}
    if meta_description:
        has_auth = '100%' in meta_description or 'authentique' in meta_description.lower()
        good_len = 100 <= len(meta_description) <= 155
        if has_auth and good_len:
            check2 = {'name': 'Meta Description', 'points': 25, 'max': 25, 'status': 'success', 'message': 'OK'}
        elif good_len:
            check2 = {'name': 'Meta Description', 'points': 15, 'max': 25, 'status': 'warning', 'message': 'Manque authenticite'}
        else:
            check2 = {'name': 'Meta Description', 'points': 10, 'max': 25, 'status': 'warning', 'message': 'Longueur incorrecte'}
    results['checks'].append(check2)
    results['score'] += check2['points']
    
    check3 = {'name': 'Description + Lien', 'points': 0, 'max': 35, 'status': 'error', 'message': 'Manquante'}
    has_desc = len(body_html) > 100
    has_link = 'kpshoes.fr/collections/' in body_html.lower()
    if has_desc and has_link:
        check3 = {'name': 'Description + Lien', 'points': 35, 'max': 35, 'status': 'success', 'message': 'Complete avec lien'}
    elif has_desc:
        check3 = {'name': 'Description + Lien', 'points': 15, 'max': 35, 'status': 'warning', 'message': 'Sans lien'}
    results['checks'].append(check3)
    results['score'] += check3['points']
    
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
    'jordan 4': "Conçue par Tinker Hatfield en 1989, la Air Jordan 4 est une silhouette emblématique qui a marqué l'histoire du basketball et de la culture streetwear.",
    'jordan 3': "La Air Jordan 3, première collaboration entre Michael Jordan et Tinker Hatfield en 1988, a révolutionné le design des sneakers avec son fameux elephant print.",
    'jordan 6': "La Air Jordan 6, portée par MJ lors de son premier titre NBA en 1991, est reconnaissable à son spoiler arrière unique et son design avant-gardiste.",
    'jordan 1 high': "La Air Jordan 1 High, créée en 1985, est la sneaker qui a tout commencé. Un modèle iconique qui a défié les règles de la NBA et lancé un empire.",
    'jordan 1 low': "Version basse de la légendaire Air Jordan 1, parfaite pour un style quotidien sans compromis sur le look emblématique.",
    'jordan 1 mid': "La Air Jordan 1 Mid offre le parfait équilibre entre la High et la Low, avec un style polyvalent adapté à toutes les occasions.",
    'dunk': "Créée en 1985 pour le basketball universitaire, la Nike Dunk est devenue une icône de la culture sneakers et du skateboarding.",
    'dunk low': "La Nike Dunk Low, version basse du classique de 1985, est devenue un incontournable du streetwear moderne.",
    'dunk high': "La Nike Dunk High conserve l'ADN original du modèle de 1985 avec sa silhouette montante reconnaissable entre toutes.",
    'air force 1': "La Nike Air Force 1, créée en 1982, est un classique intemporel. Première sneaker à intégrer la technologie Air, elle reste une référence absolue.",
    'air max': "La gamme Air Max de Nike révolutionne le confort avec sa bulle d'air visible, alliant technologie de pointe et design audacieux.",
    'samba': "L'Adidas Samba, née en 1950 pour le football en salle, est devenue une légende du style casual et une icône de la mode.",
    'campus': "L'Adidas Campus revisite le classique des années 80 avec son design épuré en daim, parfait pour un look rétro-moderne.",
    'gazelle': "L'Adidas Gazelle, créée en 1966, est un modèle vintage intemporel qui traverse les décennies sans prendre une ride.",
    'spezial': "L'Adidas Spezial, née dans les années 70 pour le handball, incarne l'esprit terrace culture et le style casual européen.",
    'yeezy slide': "La Yeezy Slide de Kanye West a redéfini la sandale de luxe avec son design minimaliste et son confort incomparable.",
    'yeezy 350': "La Yeezy 350 V2, collaboration iconique entre Kanye West et Adidas, est devenue une pièce collector incontournable.",
    'yeezy 700': "La Yeezy 700 Wave Runner marque le retour du chunky sneaker avec son design audacieux et ses multiples textures.",
    'new balance 550': "La New Balance 550, ressortie des archives de 1989, incarne le revival du design basketball vintage des années 80.",
    'new balance 530': "La New Balance 530, avec son design running rétro des années 90, offre un look chunky très tendance.",
    'new balance 2002r': "La New Balance 2002R combine le confort moderne avec l'esthétique classique des années 2000.",
    'new balance 9060': "La New Balance 9060 représente la nouvelle génération de sneakers avec son design futuriste et ses lignes audacieuses.",
    'gel-1130': "L'Asics Gel-1130, modèle running de 2008 ressuscité, est devenue un must-have du streetwear contemporain.",
    'gel-kayano': "L'Asics Gel-Kayano combine performance technique et style streetwear avec son design distinctif.",
    'gel-nyc': "L'Asics Gel-NYC fusionne plusieurs modèles iconiques pour créer une silhouette unique et contemporaine.",
    'tasman': "La UGG Tasman, avec sa doublure en peau de mouton et son design slip-on, offre un confort incomparable.",
    'tazz': "La UGG Tazz revisite le classique Tasman avec une semelle plateforme tendance.",
    'ultra mini': "La UGG Ultra Mini est la version compacte et moderne du classique boot UGG.",
    'crocs': "Les Crocs, avec leur design unique en Croslite, offrent un confort et une légèreté incomparables.",
    'travis scott': "Les collaborations Travis Scott x Nike sont devenues des pièces de collection très recherchées.",
    'off-white': "Les collaborations Off-White x Nike de Virgil Abloh ont révolutionné le monde des sneakers avec leur esthétique déconstructiviste.",
}

DEFAULT_DESC = "Un modèle qui allie design contemporain et qualité premium."


def get_model_description(title):
    t = title.lower()
    for key, desc in MODEL_DESCRIPTIONS.items():
        if key in t: return desc
    return DEFAULT_DESC


def generate_meta_title(product):
    title = product.get('title', '')
    meta_title = title + ' | ' + SITE_NAME
    if len(meta_title) > 60:
        meta_title = title[:47] + '... | ' + SITE_NAME
    return meta_title


def generate_meta_description(product):
    title = product.get('title', '')
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    if sku:
        return f"Achetez la {title} ({sku}) sur {SITE_NAME}. 100% Authentique, vérifié par nos experts. Livraison rapide et paiement sécurisé."[:155]
    return f"Achetez la {title} sur {SITE_NAME}. 100% Authentique, vérifié par nos experts. Livraison rapide et paiement sécurisé."[:155]


def generate_body_html(product, collections):
    title = product.get('title', '')
    brand = extract_brand(title)
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    collection = find_collection(title, collections)
    model_desc = get_model_description(title)
    
    lines = []
    
    # Paragraphe 1: Introduction avec lien collection
    if collection:
        lines.append(f'<p>Découvrez la <strong>{title}</strong> disponible sur {SITE_NAME}. Retrouvez ce modèle et bien d\'autres dans notre collection <a href="{collection["url"]}">{collection["title"]}</a>.</p>')
    else:
        lines.append(f'<p>Découvrez la <strong>{title}</strong> disponible sur {SITE_NAME}.</p>')
    
    # Paragraphe 2: Description du modèle + texte générique
    lines.append(f'<p>{model_desc} Cette paire se distingue par ses finitions soignées et son confort au quotidien. Une pièce polyvalente qui s\'adapte à tous les styles.</p>')
    
    # Paragraphe 3: Caractéristiques techniques
    tech_lines = []
    if sku:
        tech_lines.append(f'<strong>Référence</strong> : {sku}')
    tech_lines.append(f'<strong>Marque</strong> : {brand}')
    lines.append('<p>' + '<br>'.join(tech_lines) + '</p>')
    
    # Paragraphe 4: Garanties KP SHOES
    lines.append(f'<p>Chez <strong>{SITE_NAME}</strong>, nous garantissons l\'authenticité de chaque paire. Toutes nos sneakers sont vérifiées par nos experts avant expédition. Livraison rapide et paiement sécurisé.</p>')
    
    return '\n\n'.join(lines)


def update_seo_field(pid, field, value):
    if field == 'body_html':
        shopify_request(f'products/{pid}.json', 'PUT', {'product': {'id': pid, 'body_html': value}})
    elif field == 'meta_title':
        shopify_request(f'products/{pid}/metafields.json', 'POST', {'metafield': {'namespace': 'global', 'key': 'title_tag', 'value': value, 'type': 'single_line_text_field'}})
    elif field == 'meta_description':
        shopify_request(f'products/{pid}/metafields.json', 'POST', {'metafield': {'namespace': 'global', 'key': 'description_tag', 'value': value, 'type': 'single_line_text_field'}})
    return True


# ══════════════════════════════════════════════════════════════
# PAGES HTML
# ══════════════════════════════════════════════════════════════

HOME_HTML = '''<!DOCTYPE html>
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
<div style="display:flex;gap:10px;align-items:center">
<a href="/blog-generator" style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:8px 16px;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600">✨ Générateur Blog</a>
<span style="color:#666;font-size:12px">Gestion Shopify V8</span>
</div>
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
<option value="excellent">Excellent</option>
<option value="good">Bon</option>
<option value="warning">Moyen</option>
<option value="poor">Faible</option>
</select>
<button class="btn btn-s" onclick="reload()">Actualiser</button>
</div>
<div class="grid" id="grid"><div class="loading"><div class="spinner"></div>Chargement...</div></div>
</main>
<script>
var P=[],C=[],sinceId=0,loading=false,totalV=0;
function load(){
    if(loading)return;loading=true;
    document.getElementById("msg").textContent="Chargement... "+P.length+" produits";
    document.getElementById("msg").className="msg on";
    fetch("/api/products?since_id="+sinceId+"&limit=50").then(function(r){return r.json();}).then(function(d){
        if(d.collections)C=d.collections;
        if(d.products&&d.products.length>0){
            for(var i=0;i<d.products.length;i++){
                var p=d.products[i];
                var b=(p.body_html||"").toLowerCase();
                p._lk=b.indexOf("kpshoes.fr/collections/")>=0;
                p._ds=(p.body_html||"").length>100;
                p._sc=(p._ds?30:0)+(p._lk?70:0);
                if(p._sc>=85)p._seo="excellent";else if(p._sc>=70)p._seo="good";else if(p._sc>=50)p._seo="warning";else p._seo="poor";
                totalV+=(p.variants||[]).length;P.push(p);
            }
            sinceId=d.products[d.products.length-1].id;updateStats();filter();loading=false;
            if(d.products.length>=50)setTimeout(load,100);else{document.getElementById("msg").className="msg";}
        }else{document.getElementById("msg").className="msg";loading=false;filter();}
    }).catch(function(e){document.getElementById("msg").textContent="Erreur: "+e.message;loading=false;});
}
function updateStats(){
    document.getElementById("totalP").textContent=P.length;
    document.getElementById("totalV").textContent=totalV;
    document.getElementById("totalC").textContent=C.length;
    var avg=0;for(var i=0;i<P.length;i++)avg+=P[i]._sc;
    avg=P.length?Math.round(avg/P.length):0;
    document.getElementById("seoAvg").textContent=avg+"%";
}
function filter(){
    var q=document.getElementById("q").value.toLowerCase();
    var f=document.getElementById("f").value;
    var L=[];for(var i=0;i<P.length;i++){var p=P[i];if(q&&p.title.toLowerCase().indexOf(q)<0)continue;if(f&&p._seo!==f)continue;L.push(p);}
    render(L);
}
function render(L){
    var el=document.getElementById("grid");
    if(!L.length&&!loading){el.innerHTML="<div class='loading'>Aucun produit</div>";return;}
    var html="";var max=Math.min(L.length,100);
    for(var i=0;i<max;i++){
        var p=L[i];var img=(p.image&&p.image.src)?p.image.src:"";
        var sku=(p.variants&&p.variants[0])?p.variants[0].sku||"":"";
        var price=(p.variants&&p.variants[0])?p.variants[0].price:"0";
        html+="<div class='card' onclick='go("+p.id+")'><img src='"+img+"'><div class='card-body'>";
        html+="<div class='card-title'>"+esc(p.title)+"</div><div class='card-sku'>"+sku+"</div>";
        html+="<div class='card-meta'><span class='card-price'>"+price+" EUR</span><span class='badge "+p._seo+"'>"+p._sc+"%</span></div>";
        html+="</div></div>";
    }
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


PRODUCT_HTML = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Produit - KP SHOES</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#0a0a0f;color:#fff;min-height:100vh}
.hd{background:#111;padding:12px 20px;border-bottom:1px solid #222;display:flex;align-items:center;gap:20px}
.hd a{color:#888;text-decoration:none}.hd a:hover{color:#fff}
.hd-title{font-size:16px;font-weight:bold;color:#00ff88}
.main{max-width:1200px;margin:0 auto;padding:20px}
.top{display:grid;grid-template-columns:350px 1fr;gap:25px;margin-bottom:25px}
.gallery{background:#111;border-radius:10px;overflow:hidden}
.main-img{width:100%;height:350px;object-fit:contain;background:#1a1a2e}
.thumbs{display:flex;gap:8px;padding:10px;overflow-x:auto}
.thumb{width:50px;height:50px;object-fit:cover;border-radius:5px;cursor:pointer;border:2px solid transparent}
.thumb:hover,.thumb.active{border-color:#00ff88}
.info{display:flex;flex-direction:column;gap:12px}
.title{font-size:18px;font-weight:bold}
.sku{color:#666;font-size:12px}
.price{font-size:24px;font-weight:bold;color:#00ff88}
.seo-box{display:flex;align-items:center;gap:15px;background:#111;padding:12px;border-radius:8px}
.score{width:60px;height:60px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:bold}
.score.excellent{background:#00ff8833;color:#00ff88;border:3px solid #00ff88}
.score.good{background:#00cc6a33;color:#00cc6a;border:3px solid #00cc6a}
.score.warning{background:#ffa50033;color:#ffa500;border:3px solid #ffa500}
.score.poor{background:#ff475733;color:#ff4757;border:3px solid #ff4757}
.btns{display:flex;gap:8px;flex-wrap:wrap}
.btn{padding:10px 16px;border:none;border-radius:6px;font-weight:600;cursor:pointer;font-size:12px;text-decoration:none}
.btn-p{background:#00ff88;color:#000}.btn-s{background:#333;color:#fff}.btn-o{background:#ff9500;color:#000}.btn-g{background:#3b82f6;color:#fff}
.section{background:#111;border-radius:10px;padding:15px;margin-bottom:15px}
.section-title{font-size:13px;font-weight:bold;margin-bottom:10px;color:#00ff88;display:flex;justify-content:space-between;align-items:center}
.checks{display:flex;flex-direction:column;gap:6px}
.check{display:flex;align-items:center;gap:10px;padding:8px 10px;background:#1a1a2e;border-radius:6px;cursor:pointer;border:2px solid transparent}
.check:hover{border-color:#333}.check.selected{border-color:#00ff88;background:#00ff8815}
.check-icon{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px}
.check-icon.success{background:#00ff8833;color:#00ff88}
.check-icon.warning{background:#ffa50033;color:#ffa500}
.check-icon.error{background:#ff475733;color:#ff4757}
.check-info{flex:1}.check-name{font-weight:600;font-size:11px}.check-msg{font-size:9px;color:#888}
.check-pts{font-weight:bold;font-size:10px}
.meta-box{background:#1a1a2e;border-radius:6px;padding:10px;margin-bottom:8px}
.meta-label{font-size:9px;color:#666;margin-bottom:3px}
.meta-value{font-size:11px;word-break:break-all}
table{width:100%;border-collapse:collapse}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #222;font-size:11px}
th{background:#1a1a2e;font-size:9px;color:#888}
.loading{text-align:center;padding:40px;color:#666}
.spinner{width:30px;height:30px;border:3px solid #222;border-top-color:#00ff88;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 10px}
@keyframes spin{to{transform:rotate(360deg)}}
.toast{position:fixed;bottom:20px;right:20px;padding:10px 18px;border-radius:6px;font-size:12px;z-index:100}
.toast.success{background:#00ff88;color:#000}.toast.error{background:#ff4757}
.goat-preview{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);z-index:200;overflow-y:auto;padding:20px}
.goat-preview.show{display:block}
.goat-content{max-width:800px;margin:0 auto;background:#111;border-radius:10px;padding:20px}
.goat-close{position:absolute;top:20px;right:20px;background:#333;border:none;color:#fff;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:20px}
.goat-images{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:20px 0}
.goat-images img{width:100%;height:150px;object-fit:contain;background:#1a1a2e;border-radius:8px;border:2px solid transparent}
.goat-images img.selected{border-color:#00ff88}
@media(max-width:800px){.top{grid-template-columns:1fr}}
</style>
</head>
<body>
<header class="hd">
<a href="/">← Retour</a>
<div class="hd-title">Detail Produit</div>
</header>
<main class="main" id="main"><div class="loading"><div class="spinner"></div>Chargement...</div></main>

<!-- Modal GOAT Preview -->
<div class="goat-preview" id="goatPreview">
<button class="goat-close" onclick="closeGoat()">×</button>
<div class="goat-content">
<h2 style="margin-bottom:10px">Photos GOAT</h2>
<p id="goatStatus" style="color:#888;font-size:12px;margin-bottom:15px">Recherche en cours...</p>
<div class="goat-images" id="goatImages"></div>
<div style="display:flex;gap:10px;margin-top:15px">
<button class="btn btn-p" onclick="applyGoatImages()">Remplacer les photos</button>
<button class="btn btn-s" onclick="closeGoat()">Annuler</button>
</div>
</div>
</div>

<script>
var pid=PRODUCT_ID_PLACEHOLDER;
var P=null;
var SEO=null;
var SHOP_URL="SHOP_PLACEHOLDER";
var selectedFields=[];
var goatImages=[];

function load(){
    fetch("/api/product/"+pid).then(function(r){return r.json();}).then(function(d){
        if(d.error){document.getElementById("main").innerHTML="<div class='loading'>Produit non trouve</div>";return;}
        P=d.product;SEO=d.seo;render();
    }).catch(function(e){document.getElementById("main").innerHTML="<div class='loading'>Erreur: "+e.message+"</div>";});
}

function render(){
    var p=P;var seo=SEO;
    var mainImg=(p.images&&p.images[0])?p.images[0].src:"";
    var sku=(p.variants&&p.variants[0])?p.variants[0].sku||"N/A":"N/A";
    var price=(p.variants&&p.variants[0])?p.variants[0].price:"0";
    
    var h="<div class='top'><div class='gallery'><img class='main-img' id='mainImg' src='"+mainImg+"'>";
    if(p.images&&p.images.length>1){h+="<div class='thumbs'>";for(var i=0;i<p.images.length;i++){h+="<img class='thumb"+(i===0?" active":"")+"' src='"+p.images[i].src+"' onclick='chImg(this)'>";}h+="</div>";}
    h+="</div><div class='info'>";
    h+="<div class='title'>"+esc(p.title)+"</div>";
    h+="<div class='sku'>SKU: "+sku+" | ID: "+p.id+"</div>";
    h+="<div class='price'>"+price+" EUR</div>";
    h+="<div class='seo-box'><div class='score "+seo.status+"'>"+seo.score+"</div><div><div style='font-weight:bold'>Score SEO</div><div style='font-size:11px;color:#888'>"+getLabel(seo.status)+"</div></div></div>";
    h+="<div class='btns'>";
    h+="<button class='btn btn-p' onclick='regenSelected()'>Modifier Selection</button>";
    h+="<button class='btn btn-s' onclick='regenAll()'>Tout Regenerer</button>";
    h+="<button class='btn btn-g' onclick='openGoat()'>📷 Photos GOAT</button>";
    h+="<a href='https://"+SHOP_URL+"/admin/products/"+p.id+"' target='_blank' class='btn btn-s'>Shopify</a>";
    h+="</div></div></div>";
    
    h+="<div class='section'><div class='section-title'>Analyse SEO <span style='font-size:10px;color:#888;font-weight:normal'>Cliquez pour selectionner</span></div><div class='checks'>";
    var fields=["meta_title","meta_description","body_html",""];
    for(var i=0;i<seo.checks.length;i++){
        var c=seo.checks[i];
        var icon=c.status==="success"?"✓":c.status==="warning"?"!":"✗";
        var fld=fields[i]||"";
        h+="<div class='check' data-field='"+fld+"' onclick='toggleField(this)'>";
        h+="<div class='check-icon "+c.status+"'>"+icon+"</div>";
        h+="<div class='check-info'><div class='check-name'>"+c.name+"</div><div class='check-msg'>"+c.message+"</div></div>";
        h+="<div class='check-pts'>"+c.points+"/"+c.max+"</div></div>";
    }
    h+="</div></div>";
    
    h+="<div class='section'><div class='section-title'>Donnees SEO</div>";
    h+="<div class='meta-box'><div class='meta-label'>META TITLE</div><div class='meta-value'>"+(seo.meta_title||"Non defini")+"</div></div>";
    h+="<div class='meta-box'><div class='meta-label'>META DESCRIPTION</div><div class='meta-value'>"+(seo.meta_description||"Non definie")+"</div></div>";
    h+="<div class='meta-box'><div class='meta-label'>DESCRIPTION</div><div class='meta-value' style='max-height:80px;overflow-y:auto'>"+(p.body_html||"Non definie")+"</div></div>";
    h+="</div>";
    
    h+="<div class='section'><div class='section-title'>Images ("+p.images.length+")</div>";
    h+="<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:10px'>";
    for(var i=0;i<p.images.length;i++){
        h+="<img src='"+p.images[i].src+"' style='width:100%;height:100px;object-fit:contain;background:#1a1a2e;border-radius:6px'>";
    }
    h+="</div></div>";
    
    h+="<div class='section'><div class='section-title'>Variantes ("+p.variants.length+")</div>";
    h+="<table><thead><tr><th>Taille</th><th>SKU</th><th>Prix</th><th>Stock</th></tr></thead><tbody>";
    for(var i=0;i<p.variants.length;i++){
        var v=p.variants[i];
        h+="<tr><td><strong>"+v.title+"</strong></td><td>"+(v.sku||"-")+"</td><td>"+v.price+" EUR</td><td>"+v.inventory_quantity+"</td></tr>";
    }
    h+="</tbody></table></div>";
    
    document.getElementById("main").innerHTML=h;
}

function getLabel(s){if(s==="excellent")return"Excellent";if(s==="good")return"Bon";if(s==="warning")return"A ameliorer";return"Faible";}
function chImg(el){document.getElementById("mainImg").src=el.src;var all=document.querySelectorAll(".thumb");for(var i=0;i<all.length;i++)all[i].classList.remove("active");el.classList.add("active");}
function esc(s){return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

function toggleField(el){
    var field=el.getAttribute("data-field");
    if(!field)return;
    var idx=selectedFields.indexOf(field);
    if(idx>=0){selectedFields.splice(idx,1);el.classList.remove("selected");}
    else{selectedFields.push(field);el.classList.add("selected");}
}

function regenSelected(){
    if(selectedFields.length===0){toast("Selectionnez des elements","error");return;}
    toast("Mise a jour...","success");
    fetch("/api/seo/update",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:pid,fields:selectedFields})})
        .then(function(r){return r.json();}).then(function(d){
            if(d.success){toast("Mis a jour!","success");setTimeout(function(){location.reload();},1500);}
            else{toast("Erreur","error");}
        }).catch(function(){toast("Erreur","error");});
}

function regenAll(){
    toast("Regeneration...","success");
    fetch("/api/seo/apply",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:pid})})
        .then(function(r){return r.json();}).then(function(d){
            if(d.success){toast("SEO mis a jour!","success");setTimeout(function(){location.reload();},1500);}
            else{toast("Erreur","error");}
        }).catch(function(){toast("Erreur","error");});
}

// ===== GOAT Functions =====
function openGoat(){
    var sku=(P.variants&&P.variants[0])?P.variants[0].sku:"";
    if(!sku){toast("Pas de SKU","error");return;}
    
    document.getElementById("goatPreview").classList.add("show");
    document.getElementById("goatStatus").innerHTML="🔍 Recherche pour <strong>"+sku+"</strong>...<br><small style='color:#888'>(peut prendre 30-60s si le serveur est en veille)</small>";
    document.getElementById("goatImages").innerHTML="<div class='spinner'></div>";
    goatImages=[];
    
    fetch("/api/goat/images?sku="+encodeURIComponent(sku))
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.error){
                document.getElementById("goatStatus").innerHTML="<span style='color:#ff4757'>❌ "+d.error+"</span>";
                document.getElementById("goatImages").innerHTML="";
                return;
            }
            goatImages=d.images||[];
            document.getElementById("goatStatus").innerHTML="✅ <strong>"+d.name+"</strong> - "+goatImages.length+" photos trouvées<br><small style='color:#888'>Cliquez sur une image pour la désélectionner</small>";
            var html="";
            for(var i=0;i<goatImages.length;i++){
                html+="<img src='"+goatImages[i]+"' class='selected' onclick='toggleGoatImg(this,"+i+")'>";
            }
            document.getElementById("goatImages").innerHTML=html;
        })
        .catch(function(e){
            document.getElementById("goatStatus").innerHTML="<span style='color:#ff4757'>❌ Erreur: "+e.message+"</span>";
            document.getElementById("goatImages").innerHTML="";
        });
}

function closeGoat(){
    document.getElementById("goatPreview").classList.remove("show");
}

function toggleGoatImg(el,idx){
    el.classList.toggle("selected");
}

function applyGoatImages(){
    var selected=[];
    var imgs=document.querySelectorAll("#goatImages img.selected");
    for(var i=0;i<imgs.length;i++){
        selected.push(imgs[i].src);
    }
    if(selected.length===0){toast("Selectionnez au moins une image","error");return;}
    
    // Désactiver le bouton et montrer le loader
    var btn=document.querySelector(".goat-content .btn-p");
    btn.disabled=true;
    btn.innerHTML="<span class='spinner' style='width:16px;height:16px;display:inline-block;vertical-align:middle;margin-right:8px'></span>Remplacement en cours...";
    document.getElementById("goatStatus").textContent="⏳ Suppression des anciennes photos et ajout des nouvelles ("+selected.length+" photos)...";
    
    fetch("/api/goat/apply",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({product_id:pid,images:selected})
    })
    .then(function(r){return r.json();})
    .then(function(d){
        if(d.success){
            document.getElementById("goatStatus").innerHTML="<span style='color:#00ff88;font-size:16px'>✅ "+d.added+" photos remplacées avec succès!</span>";
            btn.innerHTML="✅ Terminé!";
            btn.style.background="#00ff88";
            toast("Photos remplacees! Rechargement...","success");
            setTimeout(function(){location.reload();},2000);
        }else{
            document.getElementById("goatStatus").innerHTML="<span style='color:#ff4757'>❌ Erreur: "+d.error+"</span>";
            btn.disabled=false;
            btn.innerHTML="Remplacer les photos";
            toast("Erreur: "+d.error,"error");
        }
    })
    .catch(function(e){
        document.getElementById("goatStatus").innerHTML="<span style='color:#ff4757'>❌ Erreur: "+e.message+"</span>";
        btn.disabled=false;
        btn.innerHTML="Remplacer les photos";
        toast("Erreur: "+e.message,"error");
    });
}

function toast(m,t){var e=document.createElement("div");e.className="toast "+t;e.textContent=m;document.body.appendChild(e);setTimeout(function(){e.remove();},3000);}

load();
</script>
</body>
</html>'''


BLOG_GENERATOR_HTML = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Générateur Blog SEO - KP SHOES</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#0a0a0f;color:#fff;min-height:100vh}
.hd{background:#111;padding:12px 20px;border-bottom:1px solid #222;display:flex;align-items:center;gap:20px}
.hd a{color:#888;text-decoration:none}.hd a:hover{color:#fff}
.hd-title{font-size:16px;font-weight:bold;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.main{max-width:1000px;margin:0 auto;padding:20px}
.intro{background:linear-gradient(135deg,#667eea22,#764ba222);border:1px solid #667eea44;border-radius:12px;padding:20px;margin-bottom:25px}
.intro h1{font-size:24px;margin-bottom:10px;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.intro p{color:#888;font-size:13px;line-height:1.6}
.section{background:#111;border-radius:12px;padding:20px;margin-bottom:20px;border:1px solid #222}
.section-title{font-size:14px;font-weight:bold;margin-bottom:15px;color:#fff;display:flex;align-items:center;gap:10px}
.section-title span{font-size:18px}
.topics{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
.topic{background:#1a1a2e;border:2px solid #333;border-radius:8px;padding:15px;cursor:pointer;transition:all 0.2s}
.topic:hover{border-color:#667eea}
.topic.selected{border-color:#667eea;background:#667eea22}
.topic-icon{font-size:24px;margin-bottom:8px}
.topic-name{font-weight:600;font-size:13px;margin-bottom:4px}
.topic-desc{font-size:10px;color:#888}
.form-group{margin-bottom:15px}
.form-group label{display:block;font-size:11px;color:#888;margin-bottom:5px}
.form-group input,.form-group select,.form-group textarea{width:100%;padding:10px 12px;background:#1a1a2e;border:1px solid #333;border-radius:6px;color:#fff;font-size:13px}
.form-group textarea{min-height:100px;resize:vertical}
.btn{padding:12px 24px;border:none;border-radius:8px;font-weight:600;cursor:pointer;font-size:13px;transition:all 0.2s}
.btn-primary{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 5px 20px #667eea44}
.btn-primary:disabled{opacity:0.5;cursor:not-allowed;transform:none}
.btn-secondary{background:#333;color:#fff}
.preview{background:#1a1a2e;border-radius:8px;padding:20px;margin-top:20px;display:none}
.preview.show{display:block}
.preview-title{font-size:18px;font-weight:bold;margin-bottom:10px}
.preview-meta{font-size:11px;color:#888;margin-bottom:15px}
.preview-content{font-size:13px;line-height:1.8;color:#ccc}
.preview-content h2{font-size:16px;color:#fff;margin:20px 0 10px}
.preview-content h3{font-size:14px;color:#fff;margin:15px 0 8px}
.preview-content p{margin-bottom:12px}
.preview-content a{color:#667eea}
.preview-content img{max-width:100%;border-radius:8px;margin:15px 0}
.preview-content ul{margin:10px 0 10px 20px}
.preview-content li{margin-bottom:5px}
.loading{display:none;align-items:center;gap:10px;padding:20px;background:#1a1a2e;border-radius:8px;margin-top:20px}
.loading.show{display:flex}
.spinner{width:24px;height:24px;border:3px solid #333;border-top-color:#667eea;border-radius:50%;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.success{background:#00ff8822;border:1px solid #00ff88;color:#00ff88;padding:15px;border-radius:8px;margin-top:20px;display:none}
.success.show{display:block}
.toast{position:fixed;bottom:20px;right:20px;padding:12px 20px;border-radius:8px;font-size:13px;z-index:1000}
.toast.success{background:#00ff88;color:#000}
.toast.error{background:#ff4757;color:#fff}
.articles-list{margin-top:20px}
.article-item{background:#1a1a2e;border-radius:8px;padding:15px;margin-bottom:10px;display:flex;gap:15px;align-items:center}
.article-item img{width:80px;height:80px;object-fit:cover;border-radius:6px}
.article-info{flex:1}
.article-title{font-weight:600;font-size:14px;margin-bottom:5px}
.article-date{font-size:11px;color:#888}
.keywords-input{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.keyword-tag{background:#667eea33;color:#667eea;padding:4px 10px;border-radius:15px;font-size:11px;display:flex;align-items:center;gap:5px}
.keyword-tag button{background:none;border:none;color:#667eea;cursor:pointer;font-size:14px}
</style>
</head>
<body>
<header class="hd">
<a href="/">← Retour</a>
<div class="hd-title">✨ Générateur Blog SEO</div>
</header>

<main class="main">
<div class="intro">
<h1>Générateur d'Articles SEO</h1>
<p>Créez des articles de blog optimisés pour le référencement, basés sur les tendances actuelles des sneakers. Les articles incluent automatiquement des liens vers vos produits et collections, des images GOAT, et sont structurés pour maximiser votre visibilité Google.</p>
</div>

<!-- Type d'article -->
<div class="section">
<div class="section-title"><span>📝</span> Type d'article</div>
<div class="topics" id="topics">
<div class="topic" data-type="release" onclick="selectTopic(this)">
<div class="topic-icon">📅</div>
<div class="topic-name">Calendrier Sorties</div>
<div class="topic-desc">Prochaines releases Nike, Jordan, Adidas...</div>
</div>
<div class="topic" data-type="guide_taille" onclick="selectTopic(this)">
<div class="topic-icon">📏</div>
<div class="topic-name">Guide de Tailles</div>
<div class="topic-desc">Comment taille la Jordan 4, Dunk Low...</div>
</div>
<div class="topic" data-type="tendance" onclick="selectTopic(this)">
<div class="topic-icon">🔥</div>
<div class="topic-name">Tendances 2026</div>
<div class="topic-desc">Les sneakers les plus hype du moment</div>
</div>
<div class="topic" data-type="comparatif" onclick="selectTopic(this)">
<div class="topic-icon">⚖️</div>
<div class="topic-name">Comparatif</div>
<div class="topic-desc">Jordan 4 vs Dunk Low, quelle choisir ?</div>
</div>
<div class="topic" data-type="histoire" onclick="selectTopic(this)">
<div class="topic-icon">📚</div>
<div class="topic-name">Histoire & Culture</div>
<div class="topic-desc">L'histoire de la Air Jordan 1, Nike Dunk...</div>
</div>
<div class="topic" data-type="entretien" onclick="selectTopic(this)">
<div class="topic-icon">🧹</div>
<div class="topic-name">Entretien</div>
<div class="topic-desc">Nettoyer ses sneakers, déjaunir semelles...</div>
</div>
<div class="topic" data-type="style" onclick="selectTopic(this)">
<div class="topic-icon">👔</div>
<div class="topic-name">Style & Outfit</div>
<div class="topic-desc">Comment porter ses sneakers au quotidien</div>
</div>
<div class="topic" data-type="custom" onclick="selectTopic(this)">
<div class="topic-icon">✏️</div>
<div class="topic-name">Article Libre</div>
<div class="topic-desc">Écrivez sur le sujet de votre choix</div>
</div>
</div>
</div>

<!-- Configuration -->
<div class="section">
<div class="section-title"><span>⚙️</span> Configuration</div>
<div class="form-group">
<label>Modèle/Sujet principal</label>
<input type="text" id="subject" placeholder="Ex: Air Jordan 4, Nike Dunk Low Panda, Yeezy 350...">
</div>
<div class="form-group">
<label>Mots-clés SEO (séparés par des virgules)</label>
<input type="text" id="keywords" placeholder="Ex: acheter jordan 4, jordan 4 pas cher, taille jordan 4">
</div>
<div class="form-group">
<label>Ton de l'article</label>
<select id="tone">
<option value="expert">Expert & Informatif</option>
<option value="casual">Casual & Accessible</option>
<option value="hype">Hype & Enthousiaste</option>
</select>
</div>
<div class="form-group">
<label>Longueur</label>
<select id="length">
<option value="medium">Moyen (~1500 mots)</option>
<option value="long">Long (~2500 mots)</option>
<option value="short">Court (~800 mots)</option>
</select>
</div>
</div>

<!-- Actions -->
<div style="display:flex;gap:10px;flex-wrap:wrap">
<button class="btn btn-primary" id="generateBtn" onclick="generateArticle()">✨ Générer l'article</button>
<button class="btn btn-secondary" onclick="loadExistingArticles()">📄 Voir articles existants</button>
</div>

<!-- Loading -->
<div class="loading" id="loading">
<div class="spinner"></div>
<div>
<div style="font-weight:600">Génération en cours...</div>
<div style="font-size:11px;color:#888" id="loadingStatus">Recherche des tendances actuelles...</div>
</div>
</div>

<!-- Preview -->
<div class="preview" id="preview">
<div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:15px">
<div>
<div class="preview-title" id="previewTitle">Titre de l'article</div>
<div class="preview-meta" id="previewMeta">Par KP SHOES • Février 2026</div>
</div>
<div style="display:flex;gap:8px">
<button class="btn btn-secondary" onclick="regenerate()">🔄 Régénérer</button>
<button class="btn btn-primary" onclick="publishArticle()">🚀 Publier</button>
</div>
</div>
<div class="preview-content" id="previewContent"></div>
</div>

<!-- Success -->
<div class="success" id="success">
<div style="font-weight:600;margin-bottom:5px">✅ Article publié avec succès !</div>
<div style="font-size:12px">L'article est maintenant visible sur votre blog Shopify.</div>
<a href="#" id="articleLink" target="_blank" style="color:#00ff88;font-size:12px">Voir l'article →</a>
</div>

<!-- Articles existants -->
<div class="articles-list" id="articlesList" style="display:none">
<div class="section-title"><span>📄</span> Articles existants</div>
<div id="articlesContainer"></div>
</div>
</main>

<script>
var selectedType = null;
var generatedArticle = null;
var BLOG_ID = BLOG_ID_PLACEHOLDER;

function selectTopic(el) {
    document.querySelectorAll('.topic').forEach(t => t.classList.remove('selected'));
    el.classList.add('selected');
    selectedType = el.dataset.type;
}

function generateArticle() {
    if (!selectedType) {
        toast('Sélectionnez un type d\\'article', 'error');
        return;
    }
    
    var subject = document.getElementById('subject').value.trim();
    if (!subject && selectedType !== 'tendance') {
        toast('Entrez un sujet/modèle', 'error');
        return;
    }
    
    document.getElementById('loading').classList.add('show');
    document.getElementById('preview').classList.remove('show');
    document.getElementById('success').classList.remove('show');
    document.getElementById('generateBtn').disabled = true;
    
    var statusEl = document.getElementById('loadingStatus');
    var statuses = [
        'Recherche des tendances actuelles...',
        'Récupération de l\\'image depuis GOAT...',
        'Recherche de vos produits correspondants...',
        'Génération du contenu SEO...',
        'Optimisation des liens internes...',
        'Finalisation de l\\'article...'
    ];
    var statusIdx = 0;
    var statusInterval = setInterval(function() {
        statusIdx = (statusIdx + 1) % statuses.length;
        statusEl.textContent = statuses[statusIdx];
    }, 2000);
    
    fetch('/api/blog/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            type: selectedType,
            subject: subject,
            keywords: document.getElementById('keywords').value,
            tone: document.getElementById('tone').value,
            length: document.getElementById('length').value
        })
    })
    .then(r => r.json())
    .then(data => {
        clearInterval(statusInterval);
        document.getElementById('loading').classList.remove('show');
        document.getElementById('generateBtn').disabled = false;
        
        if (data.error) {
            toast('Erreur: ' + data.error, 'error');
            return;
        }
        
        generatedArticle = data;
        document.getElementById('previewTitle').textContent = data.title;
        document.getElementById('previewMeta').innerHTML = 'Par KP SHOES • ' + new Date().toLocaleDateString('fr-FR', {month: 'long', year: 'numeric'});
        
        // Afficher l'image si disponible
        var imageHtml = '';
        if (data.image_url) {
            imageHtml = '<div style="margin-bottom:20px"><img src="' + data.image_url + '" style="max-width:100%;max-height:300px;border-radius:8px;object-fit:contain"></div>';
        }
        
        // Afficher les meta SEO
        var metaHtml = '';
        if (data.meta_title || data.meta_description) {
            metaHtml = '<div style="background:#1a1a2e;padding:15px;border-radius:8px;margin-bottom:20px;font-size:12px">';
            metaHtml += '<div style="color:#888;margin-bottom:5px">📊 Aperçu SEO Google</div>';
            if (data.meta_title) {
                metaHtml += '<div style="color:#1a0dab;font-size:14px;margin-bottom:3px">' + data.meta_title + '</div>';
            }
            metaHtml += '<div style="color:#006621;font-size:11px;margin-bottom:3px">https://kpshoes.fr/blogs/news/' + (data.handle || '...') + '</div>';
            if (data.meta_description) {
                metaHtml += '<div style="color:#666">' + data.meta_description + '</div>';
            }
            metaHtml += '</div>';
        }
        
        // Afficher l'extrait
        var summaryHtml = '';
        if (data.summary_html) {
            summaryHtml = '<div style="background:#667eea22;padding:15px;border-radius:8px;margin-bottom:20px;border-left:4px solid #667eea">';
            summaryHtml += '<div style="color:#667eea;font-size:11px;margin-bottom:5px;font-weight:600">📝 EXTRAIT</div>';
            summaryHtml += '<div style="font-size:13px;color:#ccc">' + data.summary_html + '</div>';
            summaryHtml += '</div>';
        }
        
        document.getElementById('previewContent').innerHTML = imageHtml + metaHtml + summaryHtml + data.body_html;
        document.getElementById('preview').classList.add('show');
    })
    .catch(e => {
        clearInterval(statusInterval);
        document.getElementById('loading').classList.remove('show');
        document.getElementById('generateBtn').disabled = false;
        toast('Erreur: ' + e.message, 'error');
    });
}

function regenerate() {
    generateArticle();
}

function publishArticle() {
    if (!generatedArticle) return;
    
    document.getElementById('preview').style.opacity = '0.5';
    
    fetch('/api/blogs/' + BLOG_ID + '/articles', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            title: generatedArticle.title,
            body_html: generatedArticle.body_html,
            author: 'KP SHOES',
            tags: generatedArticle.tags || '',
            published: true,
            image_url: generatedArticle.image_url || '',
            summary_html: generatedArticle.summary_html || '',
            meta_title: generatedArticle.meta_title || '',
            meta_description: generatedArticle.meta_description || ''
        })
    })
    .then(r => r.json())
    .then(data => {
        document.getElementById('preview').style.opacity = '1';
        
        if (data.error) {
            toast('Erreur: ' + data.error, 'error');
            return;
        }
        
        document.getElementById('preview').classList.remove('show');
        document.getElementById('success').classList.add('show');
        
        if (data.article && data.article.handle) {
            document.getElementById('articleLink').href = 'https://DOMAIN_PLACEHOLDER/blogs/news/' + data.article.handle;
        }
        
        toast('Article publié !', 'success');
    })
    .catch(e => {
        document.getElementById('preview').style.opacity = '1';
        toast('Erreur: ' + e.message, 'error');
    });
}

function loadExistingArticles() {
    var container = document.getElementById('articlesContainer');
    container.innerHTML = '<div class="loading show"><div class="spinner"></div><span>Chargement...</span></div>';
    document.getElementById('articlesList').style.display = 'block';
    
    fetch('/api/blogs/' + BLOG_ID + '/articles')
    .then(r => r.json())
    .then(data => {
        var articles = data.articles || [];
        if (articles.length === 0) {
            container.innerHTML = '<p style="color:#888;font-size:13px">Aucun article pour le moment.</p>';
            return;
        }
        
        var html = '';
        articles.forEach(function(a) {
            var img = a.image ? a.image.src : '';
            html += '<div class="article-item">';
            if (img) html += '<img src="' + img + '">';
            html += '<div class="article-info"><div class="article-title">' + a.title + '</div>';
            html += '<div class="article-date">' + new Date(a.created_at).toLocaleDateString('fr-FR') + '</div></div>';
            html += '<a href="https://DOMAIN_PLACEHOLDER/blogs/news/' + a.handle + '" target="_blank" class="btn btn-secondary" style="padding:8px 12px;font-size:11px">Voir</a>';
            html += '</div>';
        });
        container.innerHTML = html;
    })
    .catch(e => {
        container.innerHTML = '<p style="color:#ff4757">Erreur: ' + e.message + '</p>';
    });
}

function toast(msg, type) {
    var el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function() { el.remove(); }, 3000);
}
</script>
</body>
</html>'''


@app.route('/')
def home():
    return HOME_HTML


@app.route('/blog-generator')
def blog_generator():
    # Get blog ID
    r = shopify_request('blogs.json')
    blog_id = 0
    if r and r.get('blogs'):
        blog_id = r['blogs'][0]['id']
    
    html = BLOG_GENERATOR_HTML.replace('BLOG_ID_PLACEHOLDER', str(blog_id))
    html = html.replace('DOMAIN_PLACEHOLDER', SITE_DOMAIN)
    return html


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    html = PRODUCT_HTML.replace('PRODUCT_ID_PLACEHOLDER', str(product_id))
    html = html.replace('SHOP_PLACEHOLDER', SHOP)
    return html


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


@app.route('/api/seo/apply', methods=['POST'])
def api_apply_seo():
    pid = request.json.get('product_id')
    r = shopify_request(f'products/{pid}.json')
    if not r: return jsonify({'error': 'err'}), 404
    p = r['product']
    cols = get_collections()
    update_seo_field(pid, 'meta_title', generate_meta_title(p))
    time.sleep(0.3)
    update_seo_field(pid, 'meta_description', generate_meta_description(p))
    time.sleep(0.3)
    update_seo_field(pid, 'body_html', generate_body_html(p, cols))
    return jsonify({'success': True})


@app.route('/api/seo/update', methods=['POST'])
def api_update_seo():
    pid = request.json.get('product_id')
    fields = request.json.get('fields', [])
    if not fields:
        return jsonify({'error': 'No fields'}), 400
    r = shopify_request(f'products/{pid}.json')
    if not r: return jsonify({'error': 'err'}), 404
    p = r['product']
    cols = get_collections()
    for field in fields:
        if field == 'meta_title':
            update_seo_field(pid, 'meta_title', generate_meta_title(p))
        elif field == 'meta_description':
            update_seo_field(pid, 'meta_description', generate_meta_description(p))
        elif field == 'body_html':
            update_seo_field(pid, 'body_html', generate_body_html(p, cols))
        time.sleep(0.3)
    return jsonify({'success': True, 'updated': fields})


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
                update_seo_field(pid, 'meta_title', generate_meta_title(p))
                time.sleep(0.3)
                update_seo_field(pid, 'meta_description', generate_meta_description(p))
                time.sleep(0.3)
                update_seo_field(pid, 'body_html', generate_body_html(p, cols))
            time.sleep(0.5)
        task_progress = {'running': False, 'current': len(pids), 'total': len(pids), 'message': 'Termine!'}
    Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)


# ══════════════════════════════════════════════════════════════
# GOAT API ROUTES
# ══════════════════════════════════════════════════════════════

@app.route('/api/goat/images')
def api_goat_images():
    """Recherche les images GOAT pour un SKU via l'app 360"""
    sku = request.args.get('sku', '').strip()
    if not sku:
        return jsonify({'error': 'SKU requis'}), 400
    
    log.info(f"[GOAT] Searching images for SKU: {sku}")
    
    result = get_goat_images(sku)
    
    if not result:
        return jsonify({'error': 'Produit non trouve sur GOAT'}), 404
    
    if not result.get('images'):
        return jsonify({'error': 'Aucune image trouvee'}), 404
    
    return jsonify({
        'name': result.get('name', ''),
        'sku': result.get('sku', sku),
        'images': result.get('images', [])
    })


@app.route('/api/goat/apply', methods=['POST'])
def api_goat_apply():
    """Remplace les images d'un produit par celles de GOAT"""
    data = request.json
    product_id = data.get('product_id')
    images = data.get('images', [])
    
    if not product_id or not images:
        return jsonify({'error': 'product_id et images requis'}), 400
    
    try:
        # Get current product
        r = shopify_request(f'products/{product_id}.json')
        if not r or 'product' not in r:
            return jsonify({'error': 'Produit non trouve'}), 404
        
        product = r['product']
        
        # Delete existing images
        for img in product.get('images', []):
            shopify_request(f'products/{product_id}/images/{img["id"]}.json', 'DELETE')
            time.sleep(0.3)
        
        # Add new images
        added = 0
        for i, img_url in enumerate(images):
            result = shopify_request(f'products/{product_id}/images.json', 'POST', {
                'image': {'src': img_url, 'position': i + 1}
            })
            if result:
                added += 1
            time.sleep(0.3)
        
        log.info(f"[GOAT Apply] Added {added} images to product {product_id}")
        
        return jsonify({'success': True, 'added': added})
        
    except Exception as e:
        log.error(f"[GOAT Apply] Error: {e}")
        return jsonify({'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════
# BLOG API
# ══════════════════════════════════════════════════════════════

@app.route('/api/blogs')
def api_blogs():
    """Liste tous les blogs Shopify"""
    r = shopify_request('blogs.json')
    if not r:
        return jsonify({'error': 'Impossible de récupérer les blogs. Vérifiez les permissions API (scope: read_content)'}), 403
    return jsonify(r)


@app.route('/api/blogs/<int:blog_id>/articles')
def api_blog_articles(blog_id):
    """Liste les articles d'un blog"""
    r = shopify_request(f'blogs/{blog_id}/articles.json')
    if not r:
        return jsonify({'error': 'Impossible de récupérer les articles'}), 403
    return jsonify(r)


@app.route('/api/blogs/<int:blog_id>/articles', methods=['POST'])
def api_create_article(blog_id):
    """Crée un nouvel article de blog"""
    data = request.json
    
    article_data = {
        'article': {
            'title': data.get('title', ''),
            'author': data.get('author', 'KP SHOES'),
            'body_html': data.get('body_html', ''),
            'published': data.get('published', True),
            'tags': data.get('tags', ''),
            'summary_html': data.get('summary_html', ''),  # Extrait
            'metafields': []
        }
    }
    
    # Ajouter image si fournie
    if data.get('image_url'):
        article_data['article']['image'] = {'src': data.get('image_url')}
    
    # Ajouter meta title
    if data.get('meta_title'):
        article_data['article']['metafields'].append({
            'namespace': 'global',
            'key': 'title_tag',
            'value': data.get('meta_title'),
            'type': 'single_line_text_field'
        })
    
    # Ajouter meta description
    if data.get('meta_description'):
        article_data['article']['metafields'].append({
            'namespace': 'global',
            'key': 'description_tag',
            'value': data.get('meta_description'),
            'type': 'single_line_text_field'
        })
    
    # Supprimer metafields si vide
    if not article_data['article']['metafields']:
        del article_data['article']['metafields']
    
    r = shopify_request(f'blogs/{blog_id}/articles.json', 'POST', article_data)
    if not r:
        return jsonify({'error': 'Impossible de créer l\'article. Vérifiez les permissions API (scope: write_content)'}), 403
    return jsonify({'success': True, 'article': r.get('article', {})})


@app.route('/api/blogs/<int:blog_id>/articles/<int:article_id>', methods=['PUT'])
def api_update_article(blog_id, article_id):
    """Met à jour un article de blog"""
    data = request.json
    
    article_data = {
        'article': {
            'id': article_id,
            'title': data.get('title'),
            'body_html': data.get('body_html'),
            'published': data.get('published'),
            'tags': data.get('tags')
        }
    }
    
    # Nettoyer les None
    article_data['article'] = {k: v for k, v in article_data['article'].items() if v is not None}
    
    r = shopify_request(f'blogs/{blog_id}/articles/{article_id}.json', 'PUT', article_data)
    if not r:
        return jsonify({'error': 'Impossible de modifier l\'article'}), 403
    return jsonify({'success': True, 'article': r.get('article', {})})


@app.route('/api/blogs/<int:blog_id>/articles/<int:article_id>', methods=['DELETE'])
def api_delete_article(blog_id, article_id):
    """Supprime un article de blog"""
    r = shopify_request(f'blogs/{blog_id}/articles/{article_id}.json', 'DELETE')
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════
# BLOG GENERATOR API
# ══════════════════════════════════════════════════════════════

def get_products_for_linking():
    """Récupère les produits pour créer des liens internes"""
    products = []
    since_id = 0
    
    # Récupérer jusqu'à 250 produits (5 pages de 50)
    for _ in range(2):
        r = shopify_request(f'products.json?limit=250&since_id={since_id}')
        if not r or 'products' not in r or not r['products']:
            break
        
        for p in r['products']:
            sku = p['variants'][0].get('sku', '') if p.get('variants') else ''
            img = ''
            if p.get('images') and len(p['images']) > 0:
                img = p['images'][0].get('src', '')
            
            products.append({
                'id': p['id'],
                'title': p['title'],
                'handle': p['handle'],
                'sku': sku,
                'image': img,
                'url': f"https://{SITE_DOMAIN}/products/{p['handle']}"
            })
        
        since_id = r['products'][-1]['id']
        
        # Si moins de 50 produits, on a tout récupéré
        if len(r['products']) < 250:
            break
    
    log.info(f"[Blog] Loaded {len(products)} products for linking")
    return products


def find_matching_products(subject, products):
    """Trouve les produits correspondant au sujet - amélioré pour les noms longs et collabs"""
    matches = []
    subject_lower = subject.lower()
    
    # Nettoyer le sujet pour extraire les mots-clés importants
    subject_clean = subject_lower.replace('-', ' ')
    # Garder tous les mots significatifs
    stop_words = ['air', 'nike', 'adidas', 'new', 'balance', 'retro', 'high', 'low', 'mid', 'og', 'sp', 'se', 'the', 'le', 'la', 'de', 'a', 'x']
    keywords = [kw for kw in subject_clean.split() if len(kw) > 1]
    important_keywords = [kw for kw in keywords if kw not in stop_words]
    
    for p in products:
        title_lower = p['title'].lower()
        score = 0
        
        # Vérifier chaque mot-clé important
        for kw in important_keywords:
            if kw in title_lower:
                if kw.isdigit() or kw in ['dunk', 'jordan', 'yeezy', 'samba', 'campus', 'force', 'max', 'gel', 'mind', 'fragment', 'union', 'travis', 'sacai', 'off-white']:
                    score += 3
                else:
                    score += 2
        
        # Vérifier aussi les mots non-importants (air, nike, etc.)
        for kw in keywords:
            if kw in stop_words and kw in title_lower:
                score += 0.5
        
        # Bonus si le sujet complet est dans le titre
        if subject_lower in title_lower:
            score += 20
        
        # Bonus pour correspondances partielles fortes
        # Chercher des combinaisons de 2-3 mots clés
        for i in range(len(important_keywords) - 1):
            combo = important_keywords[i] + ' ' + important_keywords[i+1]
            if combo in title_lower:
                score += 5
        
        # Chercher le nom du modèle sans la marque
        # Ex: "Jordan 1" dans "Air Jordan 1 Retro..."
        if len(important_keywords) >= 2:
            model_combo = ' '.join(important_keywords[:3])
            if model_combo in title_lower:
                score += 8
        
        # Bonus pour les collabs
        collab_names = ['fragment', 'union', 'travis', 'sacai', 'off-white', 'fear of god', 'a ma maniere', 'patta']
        for collab in collab_names:
            if collab in subject_lower and collab in title_lower:
                score += 5
        
        if score > 0:
            matches.append((score, p))
    
    # Trier par score décroissant
    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in matches[:10]]


def generate_article_content(article_type, subject, keywords, tone, length, products, collections, research=None):
    """Génère le contenu de l'article - utilise les données de recherche web si disponibles"""
    
    # Trouver les produits et collections liés
    matching_products = find_matching_products(subject, products)
    matching_collection = find_collection(subject, collections)
    
    log.info(f"[Blog] Found {len(matching_products)} matching products for '{subject}'")
    
    # ── Chercher la paire EXACTE dans les produits ──
    exact_product = None
    subject_lower = subject.lower()
    for p in products:
        title_lower = p['title'].lower()
        # Match exact ou quasi-exact
        if subject_lower in title_lower or title_lower in subject_lower:
            exact_product = p
            break
    
    # Si pas de match exact, chercher avec les mots-clés importants (au moins 80% de match)
    if not exact_product and matching_products:
        subject_words = set(w for w in subject_lower.split() if len(w) > 2)
        best_score = 0
        for p in matching_products:
            p_words = set(w for w in p['title'].lower().split() if len(w) > 2)
            common = len(subject_words & p_words)
            if common > best_score and common >= len(subject_words) * 0.5:
                best_score = common
                exact_product = p
    
    if exact_product:
        log.info(f"[Blog] Exact product found: {exact_product['title']}")
    
    # ── Section produit dédiée ──
    product_links = ""
    if exact_product or matching_products:
        product_links = f'<h2>Acheter la {subject} sur KP SHOES</h2>'
        
        # Mettre la paire exacte en premier, bien mise en avant
        if exact_product:
            exact_img = f'<img src="{exact_product["image"]}" style="width:100%;max-width:300px;height:auto;border-radius:10px;margin:10px auto;display:block">' if exact_product.get('image') else ''
            product_links += f'''<div style="text-align:center;margin:20px 0;padding:20px;background:#f5f5f5;border-radius:12px">
                {exact_img}
                <div style="font-size:16px;font-weight:600;margin:10px 0;color:#333">{exact_product['title']}</div>
                <a href="{exact_product['url']}" style="display:inline-block;padding:10px 25px;background:#667eea;color:white;text-decoration:none;border-radius:8px;font-weight:600;margin:10px 0">Voir cette paire →</a>
            </div>'''
        
        # Ajouter les autres produits similaires
        other_products = [p for p in matching_products if not exact_product or p['id'] != exact_product['id']]
        if other_products:
            product_links += '<p style="margin-top:20px"><strong>Paires similaires disponibles :</strong></p>'
            product_links += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:15px;margin:10px 0">'
            for p in other_products[:5]:
                img_html = f'<img src="{p["image"]}" style="width:100%;height:120px;object-fit:contain;background:#f5f5f5;border-radius:8px">' if p.get('image') else '<div style="width:100%;height:120px;background:#f5f5f5;border-radius:8px"></div>'
                product_links += f'''<a href="{p['url']}" style="text-decoration:none;color:inherit;display:block">
                    {img_html}
                    <div style="font-size:12px;margin-top:8px;color:#333;text-align:center;line-height:1.3">{p['title'][:50]}{"..." if len(p['title']) > 50 else ""}</div>
                </a>'''
            product_links += "</div>"
    
    # Lien collection
    collection_link = ""
    if matching_collection:
        collection_link = f'<p style="margin:20px 0">👉 <strong><a href="{matching_collection["url"]}">Voir toute la collection {matching_collection["title"]}</a></strong></p>'
    
    # Construire le bloc HTML des infos web trouvées
    web_info_html = build_web_info_html(research, subject)
    
    # Stocker le produit exact pour l'image
    # On passe exact_product via un attribut sur l'article retourné
    result = None
    if article_type == "guide_taille":
        result = generate_sizing_guide(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "release":
        result = generate_release_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "tendance":
        result = generate_trend_article(subject, product_links, collection_link, tone, matching_products, web_info_html, research)
    elif article_type == "comparatif":
        result = generate_comparison_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "histoire":
        result = generate_history_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "entretien":
        result = generate_care_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "style":
        result = generate_style_article(subject, product_links, collection_link, tone, web_info_html, research)
    else:
        result = generate_custom_article(subject, keywords, product_links, collection_link, tone, web_info_html, research)
    
    # Si on a trouvé la paire exacte, utiliser son image directement
    if exact_product and exact_product.get('image'):
        result['image_url'] = exact_product['image']
        result['needs_image'] = False  # Pas besoin de chercher sur GOAT
        log.info(f"[Blog] Using exact product image: {exact_product['title']}")
    
    return result




def translate_to_french(text):
    """Traduit un texte en français via Google Translate (gratuit, pas de clé)"""
    if not text or len(text) < 10:
        return text
    
    # Détecter si c'est déjà en français (heuristique simple)
    french_indicators = [' le ', ' la ', ' les ', ' des ', ' une ', ' est ', ' sont ', ' dans ', ' pour ', ' avec ', ' cette ', ' sur ', ' qui ', ' que ']
    text_lower = text.lower()
    french_count = sum(1 for ind in french_indicators if ind in text_lower)
    if french_count >= 3:
        return text  # Déjà en français
    
    try:
        import urllib.parse
        # API Google Translate gratuite (endpoint non-officiel mais fonctionnel)
        encoded = urllib.parse.quote(text[:1000])  # Limiter à 1000 chars par requête
        url = f'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=fr&dt=t&q={encoded}'
        
        html = fetch_url(url, timeout=8)
        if html:
            data = json.loads(html)
            translated = ''.join([s[0] for s in data[0] if s[0]])
            if translated and len(translated) > 10:
                return translated
    except Exception as e:
        log.error(f"[Translate] Error: {e}")
    
    return text  # Retourner l'original si la traduction échoue


def build_web_info_html(research, subject):
    """Construit le HTML des informations trouvées sur le web, traduit en français"""
    if not research or not research.get('found'):
        return ""
    
    html = ""
    
    # Wikipedia
    wiki = research.get('wikipedia')
    if wiki and wiki.get('extract'):
        extract = wiki['extract']
        if len(extract) > 500:
            extract = extract[:500].rsplit(' ', 1)[0] + '...'
        # Traduire si en anglais
        extract = translate_to_french(extract)
        html += f'<div style="background:#f0f4ff;padding:20px;border-radius:10px;margin:20px 0;border-left:4px solid #667eea">'
        html += f'<p style="margin:0">{extract}</p>'
        html += f'</div>'
    
    # Résultats de recherche
    results = research.get('search_results', [])
    if results:
        clean_results = []
        seen = set()
        
        # Mots de bruit à filtrer
        junk_patterns = [
            'fashionfootwear', 'artdesignmusic', 'cookie', 'privacy', 'subscribe',
            'newsletter', 'sign up', 'log in', 'download the', 'scan the qr',
            'some languages may be', 'accuracy may vary', 'turn on code suggestion',
            'brand ranking', 'brand directory', 'magazine', 'morefashion',
            'don\'t show again', 'app stores', 'cmd', 'copyright', 'terms of use',
            'all rights reserved', 'follow us', 'stay ahead', 'get the latest'
        ]
        
        for r in results:
            r_clean = r.strip()
            r_lower = r_clean.lower()
            
            if any(junk in r_lower for junk in junk_patterns):
                continue
            if len(r_clean) < 50:
                continue
            
            key = r_lower[:60]
            if key in seen:
                continue
            seen.add(key)
            
            if len(r_clean) > 400:
                r_clean = r_clean[:400].rsplit(' ', 1)[0] + '...'
            
            # Nettoyer les entités HTML
            r_clean = r_clean.replace('&quot;', '"').replace('&#039;', "'").replace('&amp;', '&').replace('&#x27;', "'").replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'")
            
            clean_results.append(r_clean)
        
        if clean_results:
            # Traduire chaque résultat en français
            translated_results = []
            for r in clean_results[:6]:
                translated = translate_to_french(r)
                translated_results.append(translated)
            
            html += f'<h2>Ce que l\'on sait sur la {subject}</h2>'
            html += '<div style="margin:20px 0;padding:15px;background:#f8f9fa;border-radius:10px">'
            for r in translated_results:
                html += f'<p style="margin:10px 0;line-height:1.6">{r}</p>'
            html += '</div>'
    
    return html


def generate_sizing_guide(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un guide de tailles"""
    title = f"Comment taille la {subject} ? Guide complet des tailles 2026"
    
    meta_title = f"Comment taille la {subject} ? Guide tailles 2026 | KP SHOES"[:70]
    meta_description = f"Découvrez comment taille la {subject}. Tableau des tailles EU/US/UK, conseils pour pieds larges et comparaison avec d'autres modèles. Guide complet."[:160]
    summary = f"Vous vous demandez comment taille la {subject} ? Découvrez notre guide complet avec tableau des tailles et conseils."
    
    body = f"""
<p>Vous vous demandez <strong>comment taille la {subject}</strong> ? Ce guide complet vous aide à choisir la bonne pointure. Chez <strong>KP SHOES</strong>, nous garantissons l'authenticité de chaque paire.</p>

{web_info_html}

<h2>La {subject} taille-t-elle grand ou petit ?</h2>
<p>La {subject} est réputée pour <strong>tailler normalement</strong>. Si vous êtes entre deux tailles, nous vous conseillons de prendre la taille supérieure pour plus de confort, surtout si vous avez les pieds larges.</p>

<h2>Tableau des tailles {subject}</h2>
<table style="width:100%;border-collapse:collapse;margin:20px 0">
<tr style="background:#f5f5f5"><th style="padding:12px;border:1px solid #ddd;text-align:center">EU</th><th style="padding:12px;border:1px solid #ddd;text-align:center">US Homme</th><th style="padding:12px;border:1px solid #ddd;text-align:center">US Femme</th><th style="padding:12px;border:1px solid #ddd;text-align:center">UK</th><th style="padding:12px;border:1px solid #ddd;text-align:center">CM</th></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">38</td><td style="padding:10px;border:1px solid #ddd;text-align:center">5.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7</td><td style="padding:10px;border:1px solid #ddd;text-align:center">5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">24</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">39</td><td style="padding:10px;border:1px solid #ddd;text-align:center">6.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8</td><td style="padding:10px;border:1px solid #ddd;text-align:center">6</td><td style="padding:10px;border:1px solid #ddd;text-align:center">24.5</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">40</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">6</td><td style="padding:10px;border:1px solid #ddd;text-align:center">25</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">41</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8</td><td style="padding:10px;border:1px solid #ddd;text-align:center">9.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7</td><td style="padding:10px;border:1px solid #ddd;text-align:center">26</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">42</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">10</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">26.5</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">43</td><td style="padding:10px;border:1px solid #ddd;text-align:center">9.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">27.5</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">44</td><td style="padding:10px;border:1px solid #ddd;text-align:center">10</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">9</td><td style="padding:10px;border:1px solid #ddd;text-align:center">28</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">45</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11</td><td style="padding:10px;border:1px solid #ddd;text-align:center">12.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">10</td><td style="padding:10px;border:1px solid #ddd;text-align:center">29</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">46</td><td style="padding:10px;border:1px solid #ddd;text-align:center">12</td><td style="padding:10px;border:1px solid #ddd;text-align:center">13.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11</td><td style="padding:10px;border:1px solid #ddd;text-align:center">30</td></tr>
</table>

<h2>Conseils pour bien choisir sa taille</h2>
<ul>
<li><strong>Pieds larges</strong> : Prenez une demi-taille au-dessus</li>
<li><strong>Pieds fins</strong> : Restez sur votre taille habituelle</li>
<li><strong>Entre deux tailles</strong> : Optez pour la taille supérieure</li>
<li><strong>Pour le style</strong> : Certains préfèrent une taille au-dessus pour un look plus loose</li>
</ul>

<h2>Comparaison avec d'autres modèles</h2>
<p>Si vous connaissez votre taille dans d'autres modèles, voici quelques repères :</p>
<ul>
<li>Même taille que les Nike Air Force 1</li>
<li>Même taille que les Nike Dunk Low</li>
<li>Une demi-taille au-dessus des Adidas (Samba, Campus)</li>
<li>Même taille que les New Balance 550</li>
</ul>

{collection_link}

{product_links}

<h2>FAQ - Questions fréquentes</h2>
<h3>La {subject} taille-t-elle grand ?</h3>
<p>Non, la {subject} taille normalement. Prenez votre taille habituelle Nike.</p>

<h3>Dois-je prendre une taille au-dessus ?</h3>
<p>Uniquement si vous avez les pieds larges ou si vous êtes entre deux tailles.</p>

<h3>Comment mesurer son pied ?</h3>
<p>Mesurez votre pied le soir (quand il est légèrement gonflé) du talon au bout du gros orteil, et reportez-vous au tableau ci-dessus.</p>

<p><strong>Chez KP SHOES, toutes nos sneakers sont 100% authentiques et vérifiées par nos experts.</strong> Livraison rapide et paiement sécurisé.</p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'guide taille, {subject}, sizing, pointure',
        'handle': f'guide-taille-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_release_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur les sorties"""
    import datetime
    month = datetime.datetime.now().strftime('%B %Y')
    
    title = f"Sorties {subject} {month} : Calendrier et dates de release"
    meta_title = f"Sorties {subject} 2026 : Dates et calendrier | KP SHOES"[:70]
    meta_description = f"Découvrez toutes les sorties {subject} prévues en 2026. Calendrier des releases, dates de sortie et conseils pour cop les paires limitées."[:160]
    summary = f"Toutes les sorties {subject} à ne pas manquer. Calendrier des releases, dates clés et conseils pour réussir vos achats."
    
    body = f"""
<p>Découvrez toutes les <strong>sorties {subject}</strong> prévues pour {month}. Restez informé des dernières releases et ne manquez aucune paire sur <strong>KP SHOES</strong>.</p>

<h2>Les releases {subject} à ne pas manquer</h2>
<p>L'année 2026 s'annonce riche en sorties pour les fans de {subject}. Voici les dates clés à retenir.</p>

<h2>Comment cop les {subject} en édition limitée ?</h2>
<ul>
<li><strong>Suivez les comptes officiels</strong> : Nike SNKRS, Jordan, et les réseaux sociaux des marques</li>
<li><strong>Activez les notifications</strong> : Soyez alerté dès l'annonce d'une nouvelle release</li>
<li><strong>Préparez vos comptes</strong> : Créez vos profils sur les apps de raffle à l'avance</li>
<li><strong>Achetez sur des sites de confiance</strong> : KP SHOES garantit l'authenticité de chaque paire</li>
</ul>

{collection_link}

<h2>Les coloris les plus attendus</h2>
<p>Parmi les sorties les plus anticipées, certains coloris font déjà parler d'eux dans la communauté sneakers. Les collaborations et les éditions limitées restent les plus recherchées.</p>

{product_links}

<h2>Prix et disponibilité</h2>
<p>Les prix retail varient généralement entre 110€ et 200€ selon les modèles. Sur le marché de la revente, certaines paires peuvent atteindre des prix bien plus élevés, notamment les collaborations.</p>

<p><strong>Sur KP SHOES, retrouvez ces modèles 100% authentiques avec livraison rapide et paiement sécurisé.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'sortie, release, {subject}, calendrier, 2026',
        'handle': f'sorties-{subject.lower().replace(" ", "-")}-2026',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_trend_article(subject, product_links, collection_link, tone, matching_products, web_info_html='', research=None):
    """Génère un article sur les tendances"""
    title = "Sneakers tendance 2026 : Les modèles les plus hype du moment"
    meta_title = "Sneakers tendance 2026 : Les modèles incontournables | KP SHOES"
    meta_description = "Découvrez les sneakers les plus tendance en 2026. Running rétro, classiques indémodables et collaborations de luxe. Notre sélection des modèles hype."
    summary = "Quelles sont les sneakers les plus tendance en 2026 ? Découvrez notre sélection des modèles incontournables : running rétro, classiques et collaborations."
    
    if subject:
        title = f"{subject} : Pourquoi c'est LA sneaker tendance de 2026"
        meta_title = f"{subject} : La sneaker tendance 2026 | KP SHOES"[:70]
        meta_description = f"Découvrez pourquoi la {subject} est LA sneaker tendance de 2026. Style, confort et hype : tout ce qu'il faut savoir."[:160]
        summary = f"La {subject} s'impose comme l'une des sneakers les plus tendance de 2026. Découvrez pourquoi elle fait l'unanimité."
    
    body = f"""
<p>Quelles sont les <strong>sneakers les plus tendance en 2026</strong> ? Le marché de la sneaker continue d'évoluer.</p>

{web_info_html}

<h2>Les tendances sneakers 2026</h2>

<h3>1. Le retour du running rétro</h3>
<p>Les silhouettes inspirées des années 90 et 2000 continuent de dominer. Les <strong>Asics Gel-1130</strong>, <strong>New Balance 530</strong> et <strong>Nike Air Max</strong> sont partout dans les rues.</p>

<h3>2. Les classiques indémodables</h3>
<p>La <strong>Nike Dunk Low</strong>, l'<strong>Adidas Samba</strong> et la <strong>New Balance 550</strong> restent des valeurs sûres. Ces modèles polyvalents s'adaptent à tous les styles.</p>

<h3>3. Les collaborations de luxe</h3>
<p>Les partenariats entre marques de sport et maisons de luxe continuent de faire sensation. Les drops limités créent une forte demande sur le marché du resell.</p>

{collection_link}

<h2>Notre sélection KP SHOES</h2>
{product_links}

<h2>Comment adopter la tendance ?</h2>
<ul>
<li><strong>Investissez dans des classiques</strong> : Ils ne se démodent jamais</li>
<li><strong>Osez les couleurs</strong> : Les coloris audacieux sont très recherchés</li>
<li><strong>Privilégiez la qualité</strong> : Une paire authentique dure plus longtemps</li>
</ul>

<p><strong>Chez KP SHOES, retrouvez tous les modèles tendance 100% authentiques.</strong> Notre équipe vérifie chaque paire avant expédition.</p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': 'tendance, sneakers 2026, hype, mode, streetwear',
        'handle': 'sneakers-tendance-2026',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject if subject else 'Nike Dunk Low'
    }


def generate_comparison_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article comparatif"""
    # Parser le sujet pour extraire les 2 modèles
    models = subject.split(' vs ') if ' vs ' in subject else [subject, 'Nike Dunk Low']
    model1 = models[0].strip()
    model2 = models[1].strip() if len(models) > 1 else 'Nike Dunk Low'
    
    title = f"{model1} vs {model2} : Quelle sneaker choisir en 2026 ?"
    meta_title = f"{model1} vs {model2} : Comparatif 2026 | KP SHOES"[:70]
    meta_description = f"Comparatif {model1} vs {model2}. Confort, style, prix : on vous aide à choisir la sneaker faite pour vous."[:160]
    summary = f"Vous hésitez entre {model1} et {model2} ? Notre comparatif détaillé vous aide à faire le bon choix."
    
    body = f"""
<p>Vous hésitez entre la <strong>{model1}</strong> et la <strong>{model2}</strong> ? Ce comparatif détaillé vous aide à faire le bon choix selon vos besoins et votre style.</p>

<h2>Tableau comparatif</h2>
<table style="width:100%;border-collapse:collapse;margin:20px 0">
<tr style="background:#f5f5f5"><th style="padding:12px;border:1px solid #ddd">Critère</th><th style="padding:12px;border:1px solid #ddd">{model1}</th><th style="padding:12px;border:1px solid #ddd">{model2}</th></tr>
<tr><td style="padding:10px;border:1px solid #ddd"><strong>Confort</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd"><strong>Style</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐⭐</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd"><strong>Polyvalence</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐⭐</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd"><strong>Durabilité</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td></tr>
</table>

<h2>{model1} : Points forts et faibles</h2>
<h3>✅ Avantages</h3>
<ul>
<li>Design iconique et reconnaissable</li>
<li>Large choix de coloris</li>
<li>Bonne qualité de fabrication</li>
</ul>
<h3>❌ Inconvénients</h3>
<ul>
<li>Prix parfois élevé sur le marché du resell</li>
<li>Certains coloris difficiles à trouver</li>
</ul>

<h2>{model2} : Points forts et faibles</h2>
<h3>✅ Avantages</h3>
<ul>
<li>Silhouette polyvalente</li>
<li>Confort au quotidien</li>
<li>S'accorde avec de nombreuses tenues</li>
</ul>
<h3>❌ Inconvénients</h3>
<ul>
<li>Très populaire, donc moins original</li>
</ul>

{collection_link}

<h2>Notre verdict</h2>
<p>Les deux modèles sont d'excellents choix. La <strong>{model1}</strong> conviendra aux amateurs de sneakers iconiques, tandis que la <strong>{model2}</strong> sera parfaite pour un usage quotidien polyvalent.</p>

{product_links}

<p><strong>Retrouvez ces deux modèles sur KP SHOES, 100% authentiques et vérifiés.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'comparatif, {model1}, {model2}, versus, guide achat',
        'handle': f'comparatif-{model1.lower().replace(" ", "-")}-vs-{model2.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': model1
    }


def generate_history_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur l'histoire d'un modèle avec infos web"""
    title = f"L'histoire de la {subject} : De sa création à aujourd'hui"
    meta_title = f"Histoire de la {subject} : Origines et évolution | KP SHOES"[:70]
    meta_description = f"Découvrez l'histoire fascinante de la {subject}. De ses origines à son statut d'icône streetwear, retour sur un modèle légendaire."[:160]
    summary = f"La {subject} est bien plus qu'une sneaker. Découvrez son histoire fascinante, de sa création à son statut d'icône culturelle."
    
    # Section produit
    product_section = ""
    if product_links:
        product_section = product_links
    
    body = f"""
<p>Découvrez l'histoire complète de la <strong>{subject}</strong>, une paire qui a marqué l'univers de la sneaker.</p>

{web_info_html}

{collection_link}

{product_section}

<h2>Pourquoi cette paire est-elle si recherchée ?</h2>
<ul>
<li><strong>Un design iconique</strong> : Un modèle qui a su traverser les époques</li>
<li><strong>Une qualité premium</strong> : Des matériaux sélectionnés pour une durabilité optimale</li>
<li><strong>Un héritage culturel</strong> : Une sneaker adoptée par les passionnés du monde entier</li>
</ul>

<p><strong>Retrouvez la {subject} sur KP SHOES. Chaque paire est 100% authentique et vérifiée par nos experts.</strong></p>
"""
    
    # Si pas d'info web, ajouter un message honnête
    if not web_info_html:
        body = f"""
<p>Nous n'avons pas trouvé suffisamment d'informations vérifiées sur la <strong>{subject}</strong> pour rédiger un article d'histoire complet et fiable.</p>

<p>Chez <strong>KP SHOES</strong>, nous préférons ne pas publier d'informations incorrectes. Nous vous invitons à vérifier ce modèle directement sur le site officiel de la marque.</p>

{collection_link}

{product_section}

<p><strong>Retrouvez vos sneakers sur KP SHOES - 100% authentiques et vérifiées par nos experts.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'histoire, {subject}, culture sneaker, légende, heritage',
        'handle': f'histoire-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_care_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur l'entretien"""
    title = f"Comment nettoyer et entretenir ses {subject} ? Guide complet"
    meta_title = f"Comment nettoyer ses {subject} ? Guide entretien | KP SHOES"[:70]
    meta_description = f"Découvrez comment nettoyer et entretenir vos {subject}. Conseils d'experts, erreurs à éviter et astuces pour prolonger leur durée de vie."[:160]
    summary = f"Vos {subject} méritent le meilleur entretien. Découvrez nos conseils d'experts pour les garder impeccables."
    
    body = f"""
<p>Vos <strong>{subject}</strong> méritent un entretien régulier pour rester impeccables.</p>

{web_info_html}

<h2>Le matériel nécessaire</h2>
<ul>
<li>Une brosse à poils doux</li>
<li>Un chiffon microfibre</li>
<li>Du savon de Marseille ou un nettoyant spécial sneakers</li>
<li>De l'eau tiède</li>
<li>Un spray imperméabilisant</li>
</ul>

<h2>Étapes de nettoyage</h2>
<h3>1. Préparation</h3>
<p>Retirez les lacets et les semelles intérieures. Brossez délicatement pour enlever la poussière et les saletés superficielles.</p>

<h3>2. Nettoyage</h3>
<p>Mélangez un peu de savon avec de l'eau tiède. Frottez doucement avec la brosse en faisant des mouvements circulaires. Évitez de tremper complètement vos sneakers.</p>

<h3>3. Rinçage</h3>
<p>Essuyez avec un chiffon humide pour retirer le savon. Répétez si nécessaire.</p>

<h3>4. Séchage</h3>
<p>Laissez sécher à l'air libre, loin des sources de chaleur directe. Bourrez l'intérieur avec du papier journal pour absorber l'humidité et maintenir la forme.</p>

<h2>Conseils selon les matériaux</h2>
<h3>Cuir</h3>
<p>Utilisez un nettoyant spécial cuir et appliquez une crème nourrissante après le nettoyage.</p>

<h3>Suède/Nubuck</h3>
<p>Brossez à sec avec une brosse spéciale suède. Évitez l'eau qui peut tacher le matériau.</p>

<h3>Mesh/Textile</h3>
<p>Ces matériaux supportent mieux l'eau. Vous pouvez les nettoyer plus généreusement.</p>

<h2>Erreurs à éviter</h2>
<ul>
<li>❌ <strong>Ne jamais mettre en machine</strong> : Risque de déformation et décollement</li>
<li>❌ <strong>Éviter le sèche-linge</strong> : La chaleur détériore les colles et matériaux</li>
<li>❌ <strong>Ne pas utiliser de javel</strong> : Elle jaunit et fragilise les matériaux</li>
</ul>

{collection_link}

{product_links}

<h2>Protection et stockage</h2>
<ul>
<li>Appliquez un spray imperméabilisant avant la première utilisation</li>
<li>Rangez vos sneakers dans leurs boîtes d'origine</li>
<li>Utilisez des embauchoirs pour maintenir la forme</li>
<li>Évitez l'humidité et la lumière directe du soleil</li>
</ul>

<p><strong>Chez KP SHOES, toutes nos sneakers sont livrées dans un état impeccable. 100% authentiques et vérifiées.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'entretien, nettoyage, {subject}, sneaker care, guide',
        'handle': f'entretien-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_style_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur le style"""
    title = f"Comment porter la {subject} ? Idées de looks et outfits 2026"
    meta_title = f"Comment porter la {subject} ? Idées looks 2026 | KP SHOES"[:70]
    meta_description = f"Découvrez comment porter la {subject}. Looks casual, streetwear et smart casual : nos idées d'outfits pour tous les styles."[:160]
    summary = f"La {subject} est ultra polyvalente. Découvrez nos idées de looks pour la porter avec style au quotidien."
    
    body = f"""
<p>La <strong>{subject}</strong> est une sneaker polyvalente. Découvrez nos conseils pour créer des looks tendance.</p>

{web_info_html}

<h2>Look casual quotidien</h2>
<p>Pour un style décontracté au quotidien :</p>
<ul>
<li>Jean slim ou regular + t-shirt basique + {subject}</li>
<li>Jogger + hoodie + {subject}</li>
<li>Short cargo + polo + {subject}</li>
</ul>

<h2>Look streetwear</h2>
<p>Pour un style urbain affirmé :</p>
<ul>
<li>Pantalon cargo + sweat oversize + {subject}</li>
<li>Jean baggy + bomber jacket + {subject}</li>
<li>Survêtement vintage + {subject}</li>
</ul>

<h2>Look smart casual</h2>
<p>Oui, on peut porter des sneakers au bureau (selon le dress code) :</p>
<ul>
<li>Chino + chemise + blazer léger + {subject}</li>
<li>Pantalon à pinces + pull col roulé + {subject}</li>
</ul>

{collection_link}

<h2>Les couleurs qui matchent</h2>
<h3>Avec des {subject} blanches</h3>
<p>Tout ! Le blanc est la couleur la plus polyvalente. Jean bleu, pantalon noir, couleurs vives... Tout fonctionne.</p>

<h3>Avec des {subject} noires</h3>
<p>Parfaites pour un look monochrome ou avec des couleurs neutres (gris, beige, blanc).</p>

<h3>Avec des {subject} colorées</h3>
<p>Gardez le reste de la tenue sobre pour laisser les sneakers être le point focal.</p>

{product_links}

<h2>Conseils de style</h2>
<ul>
<li><strong>Équilibrez les proportions</strong> : Sneakers chunky avec pantalon plus ajusté</li>
<li><strong>Jouez avec les textures</strong> : Cuir, denim, coton... Variez les matières</li>
<li><strong>Accessoirisez</strong> : Montre, casquette, sac assorti</li>
</ul>

<p><strong>Retrouvez la {subject} sur KP SHOES. 100% authentique, livraison rapide.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'style, outfit, {subject}, look, mode, streetwear',
        'handle': f'comment-porter-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_custom_article(subject, keywords, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article personnalisé"""
    title = f"{subject} : Tout ce que vous devez savoir en 2026"
    meta_title = f"{subject} : Guide complet 2026 | KP SHOES"[:70]
    meta_description = f"Découvrez tout ce qu'il faut savoir sur {subject}. Guide complet, conseils d'achat et sélection des meilleures paires sur KP SHOES."[:160]
    summary = f"Tout ce qu'il faut savoir sur {subject}. Guide complet et conseils d'achat par les experts KP SHOES."
    
    body = f"""
<p>Découvrez tout ce qu'il faut savoir sur <strong>{subject}</strong>. Chez <strong>KP SHOES</strong>, nous vous proposons les meilleures paires 100% authentiques.</p>

{web_info_html}

<h2>Où acheter {subject} authentique ?</h2>
<p>Pour être sûr d'obtenir une paire authentique, privilégiez les revendeurs de confiance comme <strong>KP SHOES</strong>. Nous vérifions chaque paire avant expédition.</p>

{collection_link}

{product_links}

<h2>Notre engagement qualité</h2>
<ul>
<li>✅ Authenticité garantie à 100%</li>
<li>✅ Vérification par nos experts</li>
<li>✅ Livraison rapide et sécurisée</li>
<li>✅ Service client réactif</li>
</ul>

<p><strong>Faites confiance à KP SHOES pour vos sneakers authentiques.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'{subject}, sneakers, authentique, kp shoes',
        'handle': f'{subject.lower().replace(" ", "-")}-guide-2026',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }




# ══════════════════════════════════════════════════════════════
# RECHERCHE WEB POUR LE BLOG (scraping direct des sites sneakers)
# ══════════════════════════════════════════════════════════════

def fetch_url(url, timeout=10):
    """Fetch une URL avec gestion d'erreurs"""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
        })
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        log.error(f"[Fetch] {url[:60]}: {e}")
        return None


def extract_text_from_html(html, min_length=50, max_paragraphs=15):
    """Extrait les paragraphes de texte utile d'une page HTML"""
    if not html:
        return []
    
    paragraphs = []
    
    # Extraire les <p>
    p_tags = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
    for p in p_tags:
        text = re.sub(r'<[^>]+>', '', p).strip()
        text = re.sub(r'\s+', ' ', text)
        if len(text) >= min_length and len(text) < 2000:
            # Filtrer le contenu inutile
            lower = text.lower()
            skip = False
            for junk in ['cookie', 'privacy policy', 'subscribe', 'newsletter', 'sign up', 'log in', 
                         'accept all', 'javascript', 'copyright', 'terms of service', 'politique de confidentialite']:
                if junk in lower:
                    skip = True
                    break
            if not skip:
                paragraphs.append(text)
    
    # Aussi extraire les <meta description>
    meta = re.findall(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.DOTALL)
    if not meta:
        meta = re.findall(r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']', html, re.DOTALL)
    for m in meta:
        if len(m) > 40:
            paragraphs.insert(0, m.strip())
    
    return paragraphs[:max_paragraphs]


def search_wikipedia(query):
    """Recherche Wikipedia FR puis EN via l'API"""
    for lang in ['fr', 'en']:
        try:
            import urllib.parse
            search_url = f"https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit=3&format=json"
            html = fetch_url(search_url, timeout=8)
            if html:
                data = json.loads(html)
                if data and len(data) >= 4 and data[1]:
                    title = data[1][0]
                    summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
                    summary_html = fetch_url(summary_url, timeout=8)
                    if summary_html:
                        summary_data = json.loads(summary_html)
                        if summary_data.get('extract'):
                            log.info(f"[Wikipedia] Found '{title}' ({lang})")
                            return {
                                'title': summary_data.get('title', ''),
                                'extract': summary_data['extract'],
                                'lang': lang
                            }
        except Exception as e:
            log.error(f"[Wikipedia] Error ({lang}): {e}")
    return None


def search_sneaker_sites(subject):
    """Scrape les sites sneakers : pages de recherche -> URLs d'articles -> contenu"""
    import urllib.parse
    all_results = []
    slug = subject.lower().replace(' ', '-')
    query_encoded = urllib.parse.quote(subject)
    
    # Extraire les mots-clés importants du sujet pour matcher les articles
    subject_lower = subject.lower()
    # Enlever les termes génériques pour garder le modèle
    generic = ['retro', 'high', 'low', 'mid', 'og', 'sp', 'se', 'premium', 'men', 'women', 'mens', 'womens']
    keywords = [w for w in subject_lower.split() if w not in generic and len(w) > 1]
    
    # ── ÉTAPE 1 : URLs directes construites dynamiquement ──
    # Construire des slugs intelligents
    # Ex: "Air Jordan 1 Retro High OG SP Fragment x Union LA" -> essayer "air-jordan-1-fragment-union"
    direct_urls = []
    
    # Slug complet
    direct_urls.append(f"https://about.nike.com/en/newsroom/releases/{slug}-official-images")
    direct_urls.append(f"https://about.nike.com/en/newsroom/releases/{slug}")
    
    # Slug simplifié (sans retro/high/og/sp etc)
    simple_words = [w for w in subject_lower.replace('x ', '').split() if w not in generic]
    simple_slug = '-'.join(simple_words)
    if simple_slug != slug:
        direct_urls.append(f"https://about.nike.com/en/newsroom/releases/{simple_slug}-official-images")
    
    # SneakerNews pattern
    direct_urls.append(f"https://sneakernews.com/{slug}-release-date/")
    
    for url in direct_urls:
        try:
            html = fetch_url(url, timeout=10)
            if html and len(html) > 5000:
                paragraphs = extract_text_from_html(html, min_length=60)
                # Vérifier que le contenu parle bien du sujet (au moins 1 keyword)
                relevant = []
                for p in paragraphs:
                    p_lower = p.lower()
                    if any(kw in p_lower for kw in keywords[:5]):
                        relevant.append(p)
                
                if relevant:
                    log.info(f"[Direct] {url[:60]} -> {len(relevant)} relevant paragraphs")
                    all_results.extend(relevant)
                    if len(all_results) >= 5:
                        break
        except Exception as e:
            log.error(f"[Direct] {url[:60]}: {e}")
    
    # ── ÉTAPE 2 : Pages de recherche -> trouver les liens d'articles -> scraper ──
    if len(all_results) < 3:
        search_pages = [
            f"https://sneakernews.com/?s={query_encoded}",
            f"https://hypebeast.com/search?s={query_encoded}",
        ]
        
        for search_url in search_pages:
            try:
                html = fetch_url(search_url, timeout=10)
                if not html:
                    continue
                
                # Trouver les URLs d'articles - chercher avec les mots-clés importants
                article_urls = []
                # D'abord essayer de trouver des liens qui contiennent les keywords
                all_links = re.findall(r'href="(https?://(?:sneakernews\.com|hypebeast\.com)/[^"]{20,})"', html)
                
                for link in all_links:
                    link_lower = link.lower()
                    # Compter combien de keywords sont dans l'URL
                    match_count = sum(1 for kw in keywords if kw in link_lower)
                    if match_count >= 2 and '/search' not in link_lower and '/tag/' not in link_lower and '/author/' not in link_lower:
                        article_urls.append((match_count, link))
                
                # Trier par pertinence
                article_urls.sort(key=lambda x: x[0], reverse=True)
                unique_urls = list(dict.fromkeys([u[1] for u in article_urls]))
                
                # Scraper les 2 premiers articles pertinents
                for article_url in unique_urls[:2]:
                    try:
                        article_html = fetch_url(article_url, timeout=10)
                        if article_html and len(article_html) > 5000:
                            paragraphs = extract_text_from_html(article_html, min_length=60)
                            # Filtrer pour la pertinence
                            relevant = [p for p in paragraphs if any(kw in p.lower() for kw in keywords[:5])]
                            if relevant:
                                log.info(f"[Article] {article_url[:60]} -> {len(relevant)} relevant paragraphs")
                                all_results.extend(relevant)
                    except Exception as e:
                        log.error(f"[Article] {article_url[:60]}: {e}")
                
                if len(all_results) >= 5:
                    break
            except Exception as e:
                log.error(f"[Search] {search_url[:60]}: {e}")
    
    # ── ÉTAPE 3 : JSON-LD et meta depuis nike.com ──
    if len(all_results) < 3:
        try:
            nike_search_url = f"https://www.nike.com/w?q={query_encoded}"
            html = fetch_url(nike_search_url, timeout=10)
            if html:
                json_ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
                for jld in json_ld:
                    try:
                        data = json.loads(jld)
                        desc = data.get('description', '')
                        if desc and len(desc) > 40 and any(kw in desc.lower() for kw in keywords[:3]):
                            all_results.append(desc)
                    except:
                        pass
        except Exception as e:
            log.error(f"[Nike search] {e}")
    
    return all_results


def search_brand_page(subject):
    """Scrape les pages officielles de la marque"""
    import urllib.parse
    s = subject.lower()
    results = []
    
    # Construire des slugs variés
    slug = subject.lower().replace(' ', '-')
    slug_clean = slug.replace('nike-', '').replace('adidas-', '').replace('new-balance-', '')
    query_encoded = urllib.parse.quote(subject)
    
    urls = []
    if 'nike' in s or 'jordan' in s or 'dunk' in s or 'force' in s or 'air max' in s or 'mind' in s:
        urls = [
            f"https://about.nike.com/en/newsroom/releases/nike-{slug_clean}-official-images",
            f"https://about.nike.com/en/newsroom/releases/{slug}-official-images",
            f"https://www.nike.com/a/nike-{slug_clean}-release-info",
            f"https://www.nike.com/a/{slug_clean}-release-info",
        ]
    elif 'adidas' in s or 'samba' in s or 'campus' in s or 'gazelle' in s or 'yeezy' in s:
        urls = [
            f"https://news.adidas.com/search?q={query_encoded}",
        ]
    elif 'new balance' in s or 'nb ' in s:
        slug_nb = slug.replace('new-balance-', '')
        urls = [
            f"https://www.newbalance.com/search/?q={query_encoded}",
        ]
    elif 'asics' in s or 'gel' in s:
        urls = [
            f"https://www.asics.com/us/en-us/search?q={query_encoded}",
        ]
    elif 'ugg' in s or 'tasman' in s or 'tazz' in s:
        urls = [
            f"https://www.ugg.com/search?q={query_encoded}",
        ]
    
    for url in urls[:4]:
        try:
            html = fetch_url(url, timeout=10)
            if html and len(html) > 5000:
                paragraphs = extract_text_from_html(html, min_length=60)
                if paragraphs:
                    log.info(f"[Brand] {url[:60]} -> {len(paragraphs)} paragraphs")
                    results.extend(paragraphs)
                    if len(results) >= 5:
                        break
        except Exception as e:
            log.error(f"[Brand] {url[:60]}: {e}")
    
    return results


def do_web_research(subject, article_type):
    """Fait une recherche web via scraping direct des sites sneakers"""
    info = {
        'wikipedia': None,
        'search_results': [],
        'found': False
    }
    
    log.info(f"[Research] Starting for '{subject}' ({article_type})")
    
    # 1. Wikipedia (marche parfois)
    wiki = search_wikipedia(subject)
    if wiki:
        info['wikipedia'] = wiki
        info['found'] = True
    
    # 2. Scraper les sites sneakers directement
    results = search_sneaker_sites(subject)
    
    # 3. Page officielle de la marque
    brand_results = search_brand_page(subject)
    results.extend(brand_results)
    
    # 4. Dédupliquer et nettoyer
    seen = set()
    clean_results = []
    for r in results:
        key = r[:80].lower()
        if key not in seen and len(r) > 40:
            seen.add(key)
            clean_results.append(r)
    
    if clean_results:
        info['search_results'] = clean_results[:15]
        info['found'] = True
    
    log.info(f"[Research] Done: wiki={'yes' if info['wikipedia'] else 'no'}, results={len(info['search_results'])}, found={info['found']}")
    return info


@app.route('/api/blog/test-search')
def api_blog_test_search():
    """Route de test pour diagnostiquer la recherche web"""
    subject = request.args.get('q', 'Nike Mind 001')
    results = {'subject': subject, 'tests': {}}
    
    # Test 1: Wikipedia
    try:
        wiki = search_wikipedia(subject)
        results['tests']['wikipedia'] = {
            'status': 'OK' if wiki else 'NO RESULTS',
            'data': wiki
        }
    except Exception as e:
        results['tests']['wikipedia'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 2: Sneaker sites scraping
    try:
        sneaker = search_sneaker_sites(subject)
        results['tests']['sneaker_sites'] = {
            'status': 'OK' if sneaker else 'NO RESULTS',
            'count': len(sneaker),
            'data': [s[:200] for s in sneaker[:5]]
        }
    except Exception as e:
        results['tests']['sneaker_sites'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 3: Brand page
    try:
        brand = search_brand_page(subject)
        results['tests']['brand_page'] = {
            'status': 'OK' if brand else 'NO RESULTS',
            'count': len(brand),
            'data': [s[:200] for s in brand[:5]]
        }
    except Exception as e:
        results['tests']['brand_page'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 4: Full research
    try:
        full = do_web_research(subject, 'histoire')
        results['tests']['full_research'] = {
            'status': 'OK' if full.get('found') else 'NO RESULTS',
            'result_count': len(full.get('search_results', [])),
            'data': [s[:200] for s in full.get('search_results', [])[:3]]
        }
    except Exception as e:
        results['tests']['full_research'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 5: Google Translate
    try:
        test_text = "The Nike Mind 001 is a neuroscience-based footwear."
        translated = translate_to_french(test_text)
        results['tests']['google_translate'] = {
            'status': 'OK' if translated != test_text else 'FAILED',
            'original': test_text,
            'translated': translated
        }
    except Exception as e:
        results['tests']['google_translate'] = {'status': 'ERROR', 'error': str(e)}
    
    return jsonify(results)
    
    return jsonify(results)


@app.route('/api/blog/research', methods=['POST'])
def api_blog_research():
    """Endpoint de recherche web pour le blog generator"""
    data = request.json
    subject = data.get('subject', '').strip()
    article_type = data.get('type', 'custom')
    
    if not subject:
        return jsonify({'error': 'Sujet manquant'}), 400
    
    try:
        info = do_web_research(subject, article_type)
        return jsonify(info)
    except Exception as e:
        log.error(f"[Research] Error: {e}")
        return jsonify({'wikipedia': None, 'search_results': [], 'found': False})


@app.route('/api/blog/generate', methods=['POST'])
def api_generate_blog():
    """Génère un article de blog SEO"""
    data = request.json
    
    article_type = data.get('type', 'custom')
    subject = data.get('subject', '').strip()
    keywords = data.get('keywords', '')
    tone = data.get('tone', 'expert')
    length = data.get('length', 'medium')
    
    try:
        # Recherche web sur le sujet
        log.info(f"[Blog] Starting web research for '{subject}' ({article_type})")
        research = do_web_research(subject, article_type)
        log.info(f"[Blog] Research done: found={research.get('found')}")
        
        # Récupérer les produits et collections pour le maillage interne
        products = get_products_for_linking()
        collections = get_collections()
        
        # Générer le contenu avec les données de recherche
        article = generate_article_content(
            article_type, subject, keywords, tone, length,
            products, collections, research
        )
        
        # Récupérer une image depuis GOAT si nécessaire
        if article.get('needs_image') and article.get('image_search_term'):
            search_term = article.get('image_search_term', subject)
            goat_result = get_goat_images(search_term)
            if goat_result and goat_result.get('images'):
                article['image_url'] = goat_result['images'][0]
                log.info(f"[Blog] Got image from GOAT: {article['image_url'][:50]}...")
        
        # Si pas d'image GOAT, chercher dans les produits correspondants
        if not article.get('image_url'):
            matching = find_matching_products(subject, products)
            if matching:
                # Chercher l'image du premier produit
                for p in matching:
                    r = shopify_request(f'products/{p["id"]}.json')
                    if r and r.get('product', {}).get('images'):
                        article['image_url'] = r['product']['images'][0]['src']
                        log.info(f"[Blog] Got image from product: {p['title']}")
                        break
        
        return jsonify(article)
        
    except Exception as e:
        log.error(f"[Blog Generator] Error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
