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
<div style="color:#666;font-size:12px">Gestion Shopify V8</div>
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
            if(d.products.length>=50)setTimeout(load,300);else{document.getElementById("msg").className="msg";}
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


@app.route('/')
def home():
    return HOME_HTML


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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
