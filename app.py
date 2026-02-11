"""
Shopify Manager V4 - SEO Pro Edition
Descriptions style WetTheNew / LimitedResell
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


def find_col(title, cols):
    if not title: return None
    t = title.lower()
    MODEL_PATTERNS = [
        ('jordan-4', ['jordan 4', 'aj4']), 
        ('jordan-1-high', ['jordan 1 high', 'jordan 1 retro high']), 
        ('jordan-1-low', ['jordan 1 low']),
        ('jordan-1-mid', ['jordan 1 mid']),
        ('adidas-samba', ['samba']), 
        ('adidas-campus', ['campus']), 
        ('adidas-gazelle', ['gazelle']),
        ('adidas-spezial', ['spezial', 'handball spezial']),
        ('adidas-forum', ['forum']),
        ('asics-gel-1130', ['gel-1130', 'gel 1130']),
        ('asics-gel-kayano', ['gel kayano', 'kayano 14']),
        ('asics-gel-nyc', ['gel-nyc', 'gel nyc']),
        ('ugg-tasman', ['tasman']), 
        ('ugg-tazz', ['tazz']),
        ('nike-dunk-low', ['dunk low']),
        ('nike-dunk-high', ['dunk high']),
        ('air-force-1', ['air force 1', 'af1']),
        ('air-max-1', ['air max 1']),
        ('air-max-90', ['air max 90']),
        ('air-max-95', ['air max 95']),
        ('air-max-97', ['air max 97']),
        ('new-balance-550', ['nb 550', 'new balance 550', '550']),
        ('new-balance-530', ['nb 530', 'new balance 530']),
        ('new-balance-2002r', ['2002r']),
        ('new-balance-9060', ['9060']),
        ('yeezy-slide', ['yeezy slide']),
        ('yeezy-350', ['yeezy 350', '350 v2']),
        ('yeezy-500', ['yeezy 500']),
        ('yeezy-700', ['yeezy 700']),
        ('yeezy-foam', ['foam runner', 'foam rnnr']),
    ]
    BRAND_PATTERNS = [
        ('jordan-1', ['jordan', 'air jordan']), 
        ('adidas-1', ['adidas']),
        ('asics-1', ['asics']), 
        ('nike', ['nike']),
        ('new-balance', ['new balance']), 
        ('ugg', ['ugg']),
        ('puma', ['puma']),
        ('reebok', ['reebok']),
        ('converse', ['converse', 'chuck taylor']),
        ('vans', ['vans']),
    ]
    for h, ps in MODEL_PATTERNS:
        c = next((x for x in cols if x['handle'] == h), None)
        if c:
            for p in ps:
                if p in t: return {'handle': h, 'title': c['title'], 'type': 'model'}
    for h, ps in BRAND_PATTERNS:
        c = next((x for x in cols if x['handle'] == h), None)
        if c:
            for p in ps:
                if p in t: return {'handle': h, 'title': c['title'], 'type': 'brand'}
    return None


# ══════════════════════════════════════════════════════════════
# EXTRACTION INTELLIGENTE DES INFOS PRODUIT
# ══════════════════════════════════════════════════════════════

def extract_brand(title):
    """Extrait la marque depuis le titre (PAS le vendor Shopify)"""
    t = title.lower()
    brands = [
        ('Nike', ['nike', 'dunk', 'air force', 'air max', 'air jordan', 'jordan']),
        ('Adidas', ['adidas', 'yeezy', 'samba', 'campus', 'gazelle', 'spezial', 'forum']),
        ('New Balance', ['new balance', 'nb 550', 'nb 530']),
        ('Asics', ['asics', 'gel-']),
        ('UGG', ['ugg', 'tasman', 'tazz']),
        ('Puma', ['puma', 'speedcat']),
        ('Converse', ['converse', 'chuck taylor', 'chuck 70']),
        ('Vans', ['vans', 'old skool', 'sk8-hi']),
        ('Reebok', ['reebok', 'club c']),
        ('Birkenstock', ['birkenstock', 'boston']),
        ('Salomon', ['salomon', 'xt-6', 'acs']),
        ('On Running', ['on running', 'cloudmonster']),
        ('Hoka', ['hoka', 'bondi', 'clifton']),
        ('Crocs', ['crocs']),
    ]
    # Jordan en premier si présent
    if 'jordan' in t or 'air jordan' in t:
        return 'Jordan'
    for brand, patterns in brands:
        for p in patterns:
            if p in t:
                return brand
    return 'Sneakers'


def extract_model(title):
    """Extrait le modèle précis"""
    t = title.lower()
    models = [
        ('Air Jordan 4 Retro', ['jordan 4', 'aj4']),
        ('Air Jordan 1 Retro High OG', ['jordan 1 high', 'jordan 1 retro high']),
        ('Air Jordan 1 Low', ['jordan 1 low']),
        ('Air Jordan 1 Mid', ['jordan 1 mid']),
        ('Nike Dunk Low', ['dunk low']),
        ('Nike Dunk High', ['dunk high']),
        ('Nike Air Force 1', ['air force 1', 'af1']),
        ('Nike Air Max 1', ['air max 1']),
        ('Nike Air Max 90', ['air max 90']),
        ('Adidas Samba OG', ['samba og', 'samba']),
        ('Adidas Campus 00s', ['campus 00s', 'campus']),
        ('Adidas Gazelle', ['gazelle']),
        ('Adidas Handball Spezial', ['spezial', 'handball spezial']),
        ('Adidas Forum Low', ['forum low', 'forum']),
        ('Yeezy Slide', ['yeezy slide']),
        ('Yeezy Boost 350 V2', ['yeezy 350', '350 v2']),
        ('Yeezy 500', ['yeezy 500']),
        ('Yeezy Foam Runner', ['foam runner', 'foam rnnr']),
        ('New Balance 550', ['new balance 550', 'nb 550', 'bb550']),
        ('New Balance 530', ['new balance 530', 'nb 530']),
        ('New Balance 2002R', ['2002r']),
        ('New Balance 9060', ['9060']),
        ('Asics Gel-1130', ['gel-1130', 'gel 1130']),
        ('Asics Gel-Kayano 14', ['gel kayano', 'kayano 14']),
        ('Asics Gel-NYC', ['gel-nyc', 'gel nyc']),
        ('UGG Tasman', ['tasman']),
        ('UGG Tazz', ['tazz']),
    ]
    for model, patterns in models:
        for p in patterns:
            if p in t:
                return model
    return extract_brand(title)


def extract_colorway(title):
    """Extrait le colorway depuis le titre"""
    # Entre parenthèses
    match = re.search(r'\(([^)]+)\)', title)
    if match:
        return match.group(1)
    # Après le modèle, souvent après un tiret ou espace
    parts = title.split(' ')
    # Chercher les mots de couleur
    colors = ['black', 'white', 'red', 'blue', 'green', 'grey', 'gray', 'brown', 'pink', 'purple', 'orange', 'yellow', 'navy', 'beige', 'cream', 'gold', 'silver', 'noir', 'blanc', 'gris']
    found = []
    for p in parts:
        if p.lower() in colors:
            found.append(p)
    if found:
        return ' '.join(found)
    return ''


def extract_sku(product):
    """Extrait le SKU"""
    if product.get('variants') and len(product['variants']) > 0:
        sku = product['variants'][0].get('sku', '')
        if sku:
            return sku
    return ''


# ══════════════════════════════════════════════════════════════
# DESCRIPTIONS PAR MODÈLE (style WetTheNew / LimitedResell)
# ══════════════════════════════════════════════════════════════

MODEL_DESCRIPTIONS = {
    'Air Jordan 4 Retro': """La Air Jordan 4 est l'une des silhouettes les plus emblématiques de la ligne Jordan. Conçue par Tinker Hatfield en 1989, elle a été rendue célèbre par Michael Jordan lors des playoffs NBA. Son design reconnaissable se distingue par ses ailes en mesh sur les côtés, sa languette en plastique et ses lacets à ailettes. Un modèle qui a marqué l'histoire du basketball et de la culture streetwear.""",
    
    'Air Jordan 1 Retro High OG': """La Air Jordan 1 est la sneaker qui a tout commencé. Créée en 1985 par Peter Moore pour Michael Jordan, elle a révolutionné l'industrie de la chaussure de sport. Avec son col haut caractéristique et son design intemporel, la AJ1 High OG reste aujourd'hui l'une des sneakers les plus convoitées. Chaque colorway raconte une histoire unique dans la légende Jordan.""",
    
    'Air Jordan 1 Low': """La Air Jordan 1 Low reprend le design iconique de la AJ1 dans une version basse plus décontractée. Parfaite pour un style quotidien, elle conserve l'ADN de la célèbre silhouette tout en offrant un look plus discret. Un incontournable qui se porte facilement en toute saison.""",
    
    'Nike Dunk Low': """La Nike Dunk Low, créée en 1985 comme chaussure de basketball universitaire, est devenue une icône de la culture sneakers. Son design simple mais efficace et ses nombreuses collaborations en font l'une des silhouettes les plus populaires. La construction cuir premium et les multiples colorways disponibles permettent de l'adapter à tous les styles.""",
    
    'Nike Air Force 1': """La Nike Air Force 1, créée en 1982 par Bruce Kilgore, est la première chaussure de basketball à intégrer la technologie Air. Devenue un symbole de la culture hip-hop et streetwear, l'AF1 est l'une des sneakers les plus vendues de l'histoire. Son design épuré et sa semelle épaisse caractéristique en font un classique indémodable.""",
    
    'Adidas Samba OG': """L'Adidas Samba est une légende née en 1950, initialement conçue pour le football en salle. Avec sa tige en cuir, ses trois bandes iconiques et sa semelle en gomme, elle est devenue un classique du style casual. La Samba OG perpétue cet héritage avec une construction fidèle à l'originale.""",
    
    'Adidas Campus 00s': """L'Adidas Campus 00s réinterprète le classique des années 80 avec une construction modernisée. Upper en suède premium, trois bandes contrastées et semelle en caoutchouc, elle incarne le style décontracté à l'allemande. Une sneaker polyvalente qui s'inscrit parfaitement dans la tendance terrace.""",
    
    'Adidas Gazelle': """L'Adidas Gazelle, lancée en 1966, est une icône du sportswear allemand. Initialement conçue pour l'entraînement, elle a conquis les terrains de football, les scènes musicales et la rue. Son upper en suède doux, ses trois bandes contrastées et sa silhouette élancée en font une sneaker intemporelle.""",
    
    'New Balance 550': """La New Balance 550, ressortie en 2021 après sa création en 1989, est devenue un phénomène de mode. Son design basketball vintage, son cuir premium et sa silhouette chunky mais équilibrée en font la sneaker parfaite pour le style rétro contemporain. Le gros "N" sur les côtés est devenu un symbole de bon goût.""",
    
    'New Balance 530': """La New Balance 530 combine le meilleur du running des années 90 avec un style contemporain. Sa semelle ABZORB offre un confort exceptionnel tandis que son design technique assumé s'inscrit parfaitement dans la tendance dad shoes. Une sneaker confortable et stylée.""",
    
    'Asics Gel-1130': """L'Asics Gel-1130 est une running technique des années 2000 devenue un must-have du streetwear. Sa technologie GEL visible au talon, son mesh respirant et ses overlays en cuir synthétique créent un look unique. Portée par les amateurs de mode du monde entier, elle représente parfaitement l'esthétique Y2K.""",
    
    'UGG Tasman': """La UGG Tasman est une slipper devenue incontournable du style casual. Avec sa doublure en peau de mouton authentique, son upper en suède et sa semelle Treadlite légère, elle offre un confort incomparable. Le motif tressé sur le contour lui donne son caractère unique.""",
    
    'Yeezy Slide': """La Yeezy Slide, conçue par Kanye West pour Adidas, a redéfini les standards de la sandale de luxe. Son design minimaliste en mousse EVA injectée offre un confort cloud-like unique. Devenue un phénomène culturel, elle se porte désormais aussi bien à la plage qu'en ville.""",
    
    'Yeezy Boost 350 V2': """La Yeezy Boost 350 V2 est l'une des sneakers les plus influentes de la dernière décennie. Créée par Kanye West et Adidas, elle révolutionne le design avec son upper Primeknit, sa semelle Boost ultra confortable et sa silhouette futuriste. Chaque colorway devient instantanément collector.""",
}

DEFAULT_DESCRIPTION = """Un modèle qui allie design contemporain et qualité premium. Cette sneaker se distingue par ses finitions soignées et son confort au quotidien. Une pièce polyvalente qui s'adapte à tous les styles, du casual au plus recherché."""


def generate_description(product, collection):
    """Génère une description style WetTheNew/LimitedResell"""
    title = product.get('title', '')
    brand = extract_brand(title)
    model = extract_model(title)
    colorway = extract_colorway(title)
    sku = extract_sku(product)
    
    # Récupérer la description du modèle ou utiliser la générique
    model_desc = MODEL_DESCRIPTIONS.get(model, DEFAULT_DESCRIPTION)
    
    lines = []
    
    # === PARAGRAPHE 1: Intro avec lien collection ===
    if collection:
        link = f'<a href="https://{SITE_DOMAIN}/collections/{collection["handle"]}">{collection["title"]}</a>'
        if colorway:
            lines.append(f'<p>Découvrez la <strong>{model}</strong> "{colorway}" disponible sur {SITE_NAME}. Retrouvez tous nos modèles dans la collection {link}.</p>')
        else:
            lines.append(f'<p>Découvrez la <strong>{model}</strong> disponible sur {SITE_NAME}. Retrouvez tous nos modèles dans la collection {link}.</p>')
    else:
        if colorway:
            lines.append(f'<p>Découvrez la <strong>{model}</strong> "{colorway}" disponible sur {SITE_NAME}.</p>')
        else:
            lines.append(f'<p>Découvrez la <strong>{model}</strong> disponible sur {SITE_NAME}.</p>')
    
    # === PARAGRAPHE 2: Histoire/Description du modèle ===
    lines.append(f'<p>{model_desc}</p>')
    
    # === PARAGRAPHE 3: Colorway spécifique (si disponible) ===
    if colorway:
        lines.append(f'<p>Ce coloris "{colorway}" apporte une touche unique à cette silhouette iconique. Un choix parfait pour se démarquer tout en restant fidèle à l\'esprit de la marque {brand}.</p>')
    
    # === PARAGRAPHE 4: Infos techniques ===
    tech_info = []
    if sku:
        tech_info.append(f'<strong>Référence (SKU)</strong> : {sku}')
    if colorway:
        tech_info.append(f'<strong>Coloris</strong> : {colorway}')
    tech_info.append(f'<strong>Marque</strong> : {brand}')
    tech_info.append(f'<strong>Modèle</strong> : {model}')
    
    lines.append('<p>' + '<br>'.join(tech_info) + '</p>')
    
    # === PARAGRAPHE 5: Garantie authenticité ===
    lines.append(f'<p>Chez <strong>{SITE_NAME}</strong>, nous garantissons l\'authenticité de chaque paire. Toutes nos sneakers sont vérifiées par nos experts avant expédition. Livraison rapide et paiement sécurisé.</p>')
    
    return '\n\n'.join(lines)


def gen_title(p): 
    title = p.get('title', '')
    model = extract_model(title)
    colorway = extract_colorway(title)
    if colorway:
        meta = f"{model} {colorway} | {SITE_NAME}"
    else:
        meta = f"{model} | {SITE_NAME}"
    return meta[:60]


def gen_desc(p):
    title = p.get('title', '')
    model = extract_model(title)
    brand = extract_brand(title)
    colorway = extract_colorway(title)
    sku = extract_sku(p)
    
    if colorway and sku:
        return f"Achetez la {model} {colorway} ({sku}) | 100% Authentique | Livraison rapide | {SITE_NAME}"[:155]
    elif colorway:
        return f"Achetez la {model} {colorway} | 100% Authentique | Livraison rapide | {SITE_NAME}"[:155]
    else:
        return f"Achetez la {model} | 100% Authentique | Livraison rapide | {SITE_NAME}"[:155]


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
    return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>V4</title>
<style>body{font-family:system-ui;background:#0a0a0f;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}a{background:#00ff88;color:#000;padding:15px 40px;border-radius:8px;text-decoration:none;font-weight:bold}</style></head>
<body><div style="text-align:center"><h1 style="color:#00ff88">Shopify Manager V4</h1><p style="color:#666;margin:15px">Descriptions SEO Pro</p><a href="/seo">Gestion SEO</a></div></body></html>'''


@app.route('/seo')
def seo():
    return '''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SEO Manager</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#0a0a0f;color:#fff}
.hd{padding:10px 15px;background:#111;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #222}
.hd a{color:#666;text-decoration:none}
.hd b{color:#00ff88}
.stats{display:flex;gap:8px;padding:10px 15px;background:#0d0d14;flex-wrap:wrap}
.st{background:#1a1a2e;padding:8px 14px;border-radius:6px;text-align:center}
.st .v{font-size:18px;font-weight:bold}
.st .v.g{color:#0f8}
.st .v.o{color:#fa0}
.st .v.r{color:#f55}
.st .l{font-size:8px;color:#555}
.pct{background:#0f8;color:#000;padding:8px 16px;border-radius:6px;font-size:20px;font-weight:bold}
.ctrl{padding:10px 15px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;border-bottom:1px solid #222}
input,select{padding:7px 10px;background:#1a1a2e;border:1px solid #333;border-radius:4px;color:#fff;font-size:12px}
button{padding:7px 14px;border:none;border-radius:4px;cursor:pointer;font-weight:600;font-size:11px}
.bg{background:#0f8;color:#000}
.br{background:#f55;color:#fff}
.bs{background:#333;color:#fff}
.info{margin-left:auto;font-size:11px;color:#555}
.msg{padding:10px 15px;font-size:11px;color:#0f8;background:#0f81a;display:none}
.msg.on{display:block}
#list{padding:10px 15px}
.pr{background:#111;border:1px solid #222;border-radius:6px;padding:8px 10px;margin-bottom:5px;display:grid;grid-template-columns:22px 45px 1fr 90px 50px 60px;gap:8px;align-items:center;font-size:11px}
.ck{width:16px;height:16px;border:2px solid #444;border-radius:3px;cursor:pointer}
.ck.on{background:#0f8;border-color:#0f8}
.im{width:45px;height:45px;border-radius:4px;object-fit:cover;background:#222}
.ti{overflow:hidden}
.ti h4{font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:2px}
.ti .sk{font-size:8px;color:#444}
.ti .co{font-size:8px;margin-top:1px}
.ti .co.g{color:#0f8}
.ti .co.p{color:#a5f}
.ti .co.n{color:#f55}
.se{font-size:8px}
.se .ok{color:#0f8}
.se .no{color:#f55}
.sc{font-size:9px;padding:3px 7px;border-radius:8px}
.sc.h{background:#0f82;color:#0f8}
.sc.m{background:#fa02;color:#fa0}
.sc.l{background:#f552;color:#f55}
.pr button{padding:3px 7px;font-size:9px}
.ld{text-align:center;padding:40px;color:#555}
.sp{width:30px;height:30px;border:3px solid #222;border-top-color:#0f8;border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 10px}
@keyframes spin{to{transform:rotate(360deg)}}
.bar{position:fixed;top:0;left:0;right:0;background:#111;padding:10px 15px;border-bottom:2px solid #0f8;display:none;z-index:99;font-size:11px}
.bar.on{display:block}
.bar .tr{height:5px;background:#222;border-radius:3px;margin-top:6px}
.bar .fl{height:100%;background:#0f8;border-radius:3px}
.toast{position:fixed;bottom:15px;right:15px;padding:8px 14px;border-radius:5px;font-size:11px;z-index:100}
.toast.s{background:#0f8;color:#000}
.toast.e{background:#f55}
</style>
</head>
<body>
<div class="bar" id="bar">
<div style="display:flex;justify-content:space-between"><span id="bm">...</span><span id="bc">0/0</span></div>
<div class="tr"><div class="fl" id="bf"></div></div>
</div>
<div class="hd"><a href="/">Retour</a><b>SEO V4 Pro</b><span></span></div>
<div class="stats">
<div class="st"><div class="v g" id="s1">-</div><div class="l">OK</div></div>
<div class="st"><div class="v o" id="s2">-</div><div class="l">PARTIEL</div></div>
<div class="st"><div class="v r" id="s3">-</div><div class="l">MANQUE</div></div>
<div class="st"><div class="v" id="s4">-</div><div class="l">TOTAL</div></div>
<div class="pct" id="pct">-</div>
</div>
<div class="ctrl">
<input id="q" placeholder="Rechercher...">
<select id="f"><option value="">Tous</option><option value="missing">Sans lien</option><option value="partial">Partiel</option><option value="complete">Complet</option></select>
<button class="bs" onclick="reload()">Actualiser</button>
<button class="bg" onclick="doSel()">Selection</button>
<button class="br" onclick="doAll()">TOUT</button>
<div class="info"><b id="sc">0</b> sel.</div>
</div>
<div class="msg" id="msg"></div>
<div id="list"><div class="ld"><div class="sp"></div>Chargement...</div></div>
<script>
var P=[];
var C=[];
var sel={};
var sinceId=0;
var loading=false;

function loadMore(){
    if(loading) return;
    loading=true;
    showMsg("Chargement... "+P.length+" produits");
    fetch("/api/products?since_id="+sinceId+"&limit=50")
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.collections) C=d.collections;
            if(d.products && d.products.length>0){
                for(var i=0;i<d.products.length;i++){
                    var p=d.products[i];
                    var b=(p.body_html||"").toLowerCase();
                    p._lk=b.indexOf("kpshoes.fr/collections/")>=0;
                    p._ds=(p.body_html||"").length>100;
                    p._sc=(p._ds?30:0)+(p._lk?70:0);
                    p._st=p._sc>=70?"complete":p._sc>=30?"partial":"missing";
                    p._co=findC(p.title);
                    P.push(p);
                }
                sinceId=d.products[d.products.length-1].id;
                updateStats();
                filter();
                loading=false;
                if(d.products.length>=50){
                    setTimeout(loadMore,300);
                }else{
                    showMsg("");
                }
            }else{
                showMsg("");
                loading=false;
                filter();
            }
        })
        .catch(function(e){
            showMsg("Erreur: "+e.message);
            loading=false;
        });
}

function findC(t){
    if(!t||!C.length) return null;
    t=t.toLowerCase();
    var M=[["jordan-4",["jordan 4"]],["jordan-1-high",["jordan 1 high"]],["jordan-1-low",["jordan 1 low"]],["adidas-samba",["samba"]],["adidas-campus",["campus"]],["adidas-gazelle",["gazelle"]],["adidas-spezial",["spezial"]],["asics-gel-1130",["gel-1130"]],["asics-gel-kayano",["kayano"]],["ugg-tasman",["tasman"]],["ugg-tazz",["tazz"]],["nike-dunk-low",["dunk low"]],["nike-dunk-high",["dunk high"]],["air-force-1",["air force 1"]],["new-balance-550",["550"]],["new-balance-530",["530"]],["yeezy-slide",["yeezy slide"]],["yeezy-350",["yeezy 350"]]];
    var B=[["jordan-1",["jordan"]],["adidas-1",["adidas"]],["asics-1",["asics"]],["nike",["nike"]],["ugg",["ugg"]],["new-balance",["new balance"]],["puma",["puma"]]];
    var i,j,k,h,ps,c;
    for(i=0;i<M.length;i++){
        h=M[i][0];
        ps=M[i][1];
        c=null;
        for(j=0;j<C.length;j++){if(C[j].handle===h){c=C[j];break;}}
        if(c){
            for(k=0;k<ps.length;k++){
                if(t.indexOf(ps[k])>=0) return {h:h,n:c.title,t:"m"};
            }
        }
    }
    for(i=0;i<B.length;i++){
        h=B[i][0];
        ps=B[i][1];
        c=null;
        for(j=0;j<C.length;j++){if(C[j].handle===h){c=C[j];break;}}
        if(c){
            for(k=0;k<ps.length;k++){
                if(t.indexOf(ps[k])>=0) return {h:h,n:c.title,t:"b"};
            }
        }
    }
    return null;
}

function updateStats(){
    var c1=0,c2=0,c3=0,i;
    for(i=0;i<P.length;i++){
        if(P[i]._st==="complete") c1++;
        else if(P[i]._st==="partial") c2++;
        else c3++;
    }
    document.getElementById("s1").textContent=c1;
    document.getElementById("s2").textContent=c2;
    document.getElementById("s3").textContent=c3;
    document.getElementById("s4").textContent=P.length;
    document.getElementById("pct").textContent=P.length?Math.round(c1/P.length*100)+"%":"0%";
}

function showMsg(t){
    var m=document.getElementById("msg");
    m.textContent=t;
    if(t){m.className="msg on";}else{m.className="msg";}
}

function filter(){
    var q=document.getElementById("q").value.toLowerCase();
    var f=document.getElementById("f").value;
    var L=[],i,p;
    for(i=0;i<P.length;i++){
        p=P[i];
        if(q && p.title.toLowerCase().indexOf(q)<0) continue;
        if(f && p._st!==f) continue;
        L.push(p);
    }
    render(L);
}

function render(L){
    var el=document.getElementById("list");
    if(!L.length && !loading){
        el.innerHTML="<div class='ld'>Aucun produit</div>";
        return;
    }
    var html="";
    var max=Math.min(L.length,200);
    var i,p,ck,sc,co,img,sku;
    for(i=0;i<max;i++){
        p=L[i];
        ck=sel[p.id]?"on":"";
        sc=p._sc>=70?"h":p._sc>=30?"m":"l";
        co="<span class='co n'>-</span>";
        if(p._co){
            co="<span class='co "+(p._co.t==="m"?"g":"p")+"'>"+(p._co.t==="m"?"V":"O")+" "+esc(p._co.n)+"</span>";
        }
        img=(p.image && p.image.src)?p.image.src:"";
        sku=(p.variants && p.variants[0] && p.variants[0].sku)?p.variants[0].sku:"-";
        html+="<div class='pr'>";
        html+="<div class='ck "+ck+"' data-id='"+p.id+"'></div>";
        html+="<img class='im' src='"+img+"'>";
        html+="<div class='ti'><h4>"+esc(p.title)+"</h4><div class='sk'>"+sku+"</div>"+co+"</div>";
        html+="<div class='se'><div class='"+(p._ds?"ok":"no")+"'>"+(p._ds?"V":"X")+" Desc</div><div class='"+(p._lk?"ok":"no")+"'>"+(p._lk?"V":"X")+" Lien</div></div>";
        html+="<div class='sc "+sc+"'>"+p._sc+"%</div>";
        html+="<div><button class='bg' data-pid='"+p.id+"'>GO</button></div>";
        html+="</div>";
    }
    if(L.length>200){
        html+="<div class='ld'>200 max affiches</div>";
    }
    el.innerHTML=html;
    
    var cks=document.querySelectorAll(".ck");
    for(i=0;i<cks.length;i++){
        cks[i].onclick=function(){
            var id=parseInt(this.getAttribute("data-id"));
            tog(id);
        };
    }
    var btns=document.querySelectorAll(".pr button");
    for(i=0;i<btns.length;i++){
        btns[i].onclick=function(){
            var id=parseInt(this.getAttribute("data-pid"));
            doOne(id);
        };
    }
}

function esc(s){
    if(!s) return "";
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function tog(id){
    if(sel[id]){delete sel[id];}else{sel[id]=true;}
    var cnt=0;
    for(var k in sel){if(sel.hasOwnProperty(k))cnt++;}
    document.getElementById("sc").textContent=cnt;
    filter();
}

function getSelIds(){
    var ids=[];
    for(var k in sel){if(sel.hasOwnProperty(k))ids.push(parseInt(k));}
    return ids;
}

function reload(){
    P=[];
    C=[];
    sinceId=0;
    sel={};
    document.getElementById("sc").textContent="0";
    document.getElementById("list").innerHTML="<div class='ld'><div class='sp'></div>Chargement...</div>";
    loadMore();
}

function doOne(id){
    toast("Application...","s");
    fetch("/api/seo/apply",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:id})})
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.success){
                toast("OK!","s");
                for(var i=0;i<P.length;i++){
                    if(P[i].id===id){
                        P[i]._lk=true;
                        P[i]._ds=true;
                        P[i]._sc=100;
                        P[i]._st="complete";
                        break;
                    }
                }
                updateStats();
                filter();
            }else{
                toast("Erreur","e");
            }
        })
        .catch(function(e){toast("Erreur","e");});
}

function doSel(){
    var ids=getSelIds();
    if(!ids.length){toast("Selectionnez","e");return;}
    batch(ids);
}

function doAll(){
    if(!confirm("Appliquer a "+P.length+" produits?")) return;
    var ids=[],i;
    for(i=0;i<P.length;i++){ids.push(P[i].id);}
    batch(ids);
}

function batch(ids){
    document.getElementById("bar").className="bar on";
    fetch("/api/seo/batch",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_ids:ids})})
        .then(function(){
            checkProgress();
        });
}

function checkProgress(){
    fetch("/api/progress")
        .then(function(r){return r.json();})
        .then(function(r){
            var pct=r.total?Math.round(r.current/r.total*100):0;
            document.getElementById("bf").style.width=pct+"%";
            document.getElementById("bc").textContent=r.current+"/"+r.total;
            document.getElementById("bm").textContent=r.message||"...";
            if(!r.running){
                document.getElementById("bar").className="bar";
                toast("Termine!","s");
                sel={};
                document.getElementById("sc").textContent="0";
                reload();
            }else{
                setTimeout(checkProgress,1000);
            }
        });
}

function toast(m,t){
    var e=document.createElement("div");
    e.className="toast "+t;
    e.textContent=m;
    document.body.appendChild(e);
    setTimeout(function(){if(e.parentNode)e.parentNode.removeChild(e);},2000);
}

document.getElementById("q").oninput=filter;
document.getElementById("f").onchange=filter;
loadMore();
</script>
</body>
</html>'''


@app.route('/api/products')
def api_products():
    since_id = request.args.get('since_id', '0')
    limit = request.args.get('limit', '50')
    r = shopify_request(f'products.json?limit={limit}&since_id={since_id}')
    products = r.get('products', []) if r else []
    return jsonify({'products': products, 'collections': get_collections()})


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
    update_seo(pid, {'meta_title': gen_title(p), 'meta_description': gen_desc(p), 'body_html': generate_description(p, col)})
    return jsonify({'success': True})


@app.route('/api/seo/batch', methods=['POST'])
def api_batch():
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
                col = find_col(p.get('title', ''), cols)
                update_seo(pid, {'meta_title': gen_title(p), 'meta_description': gen_desc(p), 'body_html': generate_description(p, col)})
            time.sleep(1)
        task_progress = {'running': False, 'current': len(pids), 'total': len(pids), 'message': 'Termine! '+str(len(pids))+' produits'}
    Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
