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


# ══════════════════════════════════════════════════════════════
# BASE DE DONNÉES SNEAKERS ENRICHIE (pour le blog)
# ══════════════════════════════════════════════════════════════

SNEAKER_DATABASE = {
    'jordan 1': {
        'full_name': 'Air Jordan 1', 'brand': 'Jordan / Nike', 'year': 1985, 'designer': 'Peter Moore',
        'materials': ['cuir pleine fleur', 'cuir synthétique', 'nubuck selon les éditions'],
        'technology': 'Semelle Air-Sole pour un amorti léger',
        'sizing': {'fit': 'taille normalement', 'advice': 'Prenez votre taille habituelle Nike. Le cuir se détend légèrement avec le temps. Les pieds larges peuvent prendre une demi-taille au-dessus.', 'vs_af1': 'même taille', 'vs_dunk': 'même taille', 'vs_adidas': 'une demi-taille au-dessus en Adidas', 'vs_nb': 'même taille'},
        'history': "Créée par Peter Moore en 1985 pour Michael Jordan, rookie aux Chicago Bulls, la Air Jordan 1 a été bannie par la NBA pour violation du code vestimentaire. Nike payait l'amende de 5 000 $ à chaque match, transformant cette interdiction en coup marketing légendaire. Le modèle a lancé la marque Jordan qui génère aujourd'hui des milliards de dollars.",
        'cultural_moments': ["Bannissement NBA en 1985", "Adoption par le hip-hop new-yorkais dans les 90s", "Collaboration Off-White x Virgil Abloh 'The Ten' (2017)", "Collaboration Travis Scott avec Swoosh inversé (2019)", "Explosion post-documentaire 'The Last Dance' (2020)"],
        'iconic_colorways': ['Chicago (rouge/blanc/noir)', 'Bred (noir/rouge)', 'Royal Blue', 'Shadow (gris/noir)', 'Mocha (marron/blanc)', 'University Blue'],
        'retail_price': '140€ - 180€',
        'care': {'main_material': 'cuir', 'tips': "Nettoyez le cuir avec un chiffon humide et du savon doux. Crème nourrissante tous les 2-3 mois. Les versions nubuck nécessitent une brosse spéciale à sec.", 'avoid': "Ne jamais mettre en machine, éviter la javel, ne pas sécher au radiateur"},
        'style': {'looks': ['Streetwear : jean baggy + hoodie oversize + AJ1', 'Casual chic : chino beige + t-shirt blanc + AJ1', 'Urbain : pantalon cargo + bomber + AJ1']},
        'comfort_rating': 3, 'style_rating': 5, 'durability_rating': 4, 'versatility_rating': 5,
    },
    'jordan 4': {
        'full_name': 'Air Jordan 4', 'brand': 'Jordan / Nike', 'year': 1989, 'designer': 'Tinker Hatfield',
        'materials': ['cuir', 'nubuck', 'mesh latéral', 'ailes plastique (wing eyelets)'],
        'technology': 'Air-Sole visible au talon, semelle herringbone',
        'sizing': {'fit': 'taille normalement à légèrement grand', 'advice': 'Prenez votre taille habituelle. Les pieds fins peuvent descendre d\'une demi-taille. La mesh latérale offre de la flexibilité.', 'vs_af1': 'même taille ou demi-taille en dessous', 'vs_dunk': 'même taille', 'vs_adidas': 'une demi-taille au-dessus en Adidas', 'vs_nb': 'même taille'},
        'history': "Dessinée par Tinker Hatfield en 1989, la AJ4 a été portée par MJ lors du célèbre 'The Shot' contre Cleveland en playoffs. Hatfield s'est inspiré des filets de construction et de l'aviation pour les wing eyelets. Le film 'Do The Right Thing' de Spike Lee (1989) a scellé son statut culturel avec la scène où Buggin' Out se fait marcher sur ses AJ4.",
        'cultural_moments': ["'The Shot' de MJ contre Cleveland (1989)", "Film 'Do The Right Thing' de Spike Lee (1989)", "Collaboration Eminem x Carhartt (2015, ultra rare)", "Collaboration Travis Scott 'Cactus Jack' (2018-2019)", "Collaboration Off-White (2020)"],
        'iconic_colorways': ['Bred (noir/rouge)', 'White Cement', 'Military Black', 'Fire Red', 'Lightning (jaune)', 'University Blue'],
        'retail_price': '200€ - 225€',
        'care': {'main_material': 'nubuck/mesh', 'tips': "Le nubuck se nettoie à sec avec une brosse spéciale. La mesh avec une brosse douce humide et savon. Les wing eyelets avec un chiffon. Spray imperméabilisant sur le nubuck.", 'avoid': "Éviter l'eau sur le nubuck, ne pas frotter trop fort la mesh, jamais en machine"},
        'style': {'looks': ['Streetwear : jean loose + t-shirt graphique + AJ4', 'Casual : jogger technique + sweat + AJ4', 'Audacieux : cargo + veste en jean + AJ4']},
        'comfort_rating': 4, 'style_rating': 5, 'durability_rating': 4, 'versatility_rating': 4,
    },
    'jordan 3': {
        'full_name': 'Air Jordan 3', 'brand': 'Jordan / Nike', 'year': 1988, 'designer': 'Tinker Hatfield',
        'materials': ['cuir pleine fleur', 'elephant print emblématique', 'mesh sur la languette'],
        'technology': 'Première Jordan avec Air visible au talon',
        'sizing': {'fit': 'taille normalement', 'advice': 'Prenez votre taille habituelle Nike. Le cuir est rigide au début mais se détend.', 'vs_af1': 'même taille', 'vs_dunk': 'même taille', 'vs_adidas': 'une demi-taille au-dessus en Adidas', 'vs_nb': 'même taille'},
        'history': "Née d'un moment crucial : MJ envisageait de quitter Nike pour Adidas. Tinker Hatfield a créé un modèle révolutionnaire avec l'elephant print, le Jumpman logo (remplaçant le Wings), et la première bulle Air visible sur une Jordan. MJ est resté chez Nike.",
        'cultural_moments': ["Première Jordan avec le logo Jumpman (1988)", "MJ remporte le concours de dunks 1988 avec les AJ3", "MJ convaincu de rester chez Nike grâce à ce modèle", "Retro 'A Ma Maniére' acclamée (2021)"],
        'iconic_colorways': ['White Cement', 'Black Cement', 'True Blue', 'Fire Red', 'Infrared 23'],
        'retail_price': '200€ - 220€',
        'care': {'main_material': 'cuir', 'tips': "L'elephant print se nettoie avec un chiffon doux légèrement humide. Crème nourrissante sur le cuir lisse. Semelle blanche : bicarbonate de soude.", 'avoid': "Ne pas frotter l'elephant print trop fort, éviter les produits chimiques"},
        'style': {'looks': ['Classique : jean slim bleu + t-shirt blanc + AJ3 White Cement', 'Streetwear : cargo + hoodie + AJ3 Black Cement', 'Smart casual : chino + polo + AJ3']},
        'comfort_rating': 3, 'style_rating': 5, 'durability_rating': 4, 'versatility_rating': 4,
    },
    'dunk low': {
        'full_name': 'Nike Dunk Low', 'brand': 'Nike', 'year': 1985, 'designer': "Programme 'Be True To Your School'",
        'materials': ['cuir', 'cuir synthétique', 'parfois suède ou toile'],
        'technology': 'Semelle vulcanisée, rembourrage au col',
        'sizing': {'fit': 'taille normalement', 'advice': 'Taille fidèlement. Le toebox peut être étroit en cuir : pieds larges, prenez une demi-taille au-dessus.', 'vs_af1': 'même taille (AF1 plus large)', 'vs_dunk': '-', 'vs_adidas': 'une demi-taille au-dessus en Adidas', 'vs_nb': 'même taille que NB 550'},
        'history': "Née en 1985 dans le programme 'Be True To Your School' avec des coloris universitaires (UNLV, Michigan, Kentucky...). Redécouverte par les skateurs dans les 2000s (Dunk SB). En 2020-2021, retour massif : LA sneaker la plus demandée au monde.",
        'cultural_moments': ["Programme 'Be True To Your School' (1985)", "Adoption par la culture skate (2000s)", "Collaboration Supreme x Nike SB Dunk (2002)", "Collaboration Travis Scott (2020)", "Off-White 'The 50' (50 coloris, 2021)"],
        'iconic_colorways': ['Panda (noir/blanc)', 'Syracuse (orange/blanc)', 'UNC (bleu/blanc)', "Valentine's Day (rose)", 'Grey Fog', 'Medium Curry'],
        'retail_price': '110€ - 130€',
        'care': {'main_material': 'cuir', 'tips': "Cuir lisse : chiffon humide + savon de Marseille. Suède : brosse spéciale. Semelle blanche : bicarbonate ou produit anti-jaunissement.", 'avoid': "Ne pas tremper, éviter la machine, pas de javel sur les semelles"},
        'style': {'looks': ['Quotidien : jean + t-shirt + Dunk Low Panda', 'Streetwear : cargo + sweat oversize + Dunk Low colorée', 'Été : short + polo + Dunk Low', 'Féminin : jupe midi + Dunk Low pastel']},
        'comfort_rating': 3, 'style_rating': 5, 'durability_rating': 4, 'versatility_rating': 5,
    },
    'air force 1': {
        'full_name': 'Nike Air Force 1', 'brand': 'Nike', 'year': 1982, 'designer': 'Bruce Kilgore',
        'materials': ['cuir pleine fleur premium', 'cuir synthétique sur certaines versions'],
        'technology': 'Première sneaker avec technologie Air encapsulée',
        'sizing': {'fit': 'taille grand', 'advice': 'Taille GRAND. Prenez une demi-taille en dessous. Le cuir est rigide au début mais se forme. Les pieds larges peuvent garder leur taille.', 'vs_af1': '-', 'vs_dunk': 'demi-taille en dessous par rapport à la Dunk', 'vs_adidas': 'même taille que votre Adidas', 'vs_nb': 'demi-taille en dessous par rapport à la NB'},
        'history': "Première sneaker Nike Air (1982), créée pour le basketball (portée par Moses Malone). Adoptée par le hip-hop de Harlem et Baltimore dans les 80-90s. Nelly lui dédie 'Air Force Ones' (2002). Plus de 2000 coloris, sneaker la plus vendue de l'histoire Nike. Collaboration Virgil Abloh x Louis Vuitton (2022).",
        'cultural_moments': ["Première sneaker Nike Air (1982)", "Culture hip-hop Harlem & Baltimore", "Chanson 'Air Force Ones' de Nelly (2002)", "Plus de 2000 coloris produits", "Collaboration Virgil Abloh x Louis Vuitton (2022)"],
        'iconic_colorways': ['Triple White', 'Triple Black', 'White/Black', 'Wheat', 'Flax', 'University Red'],
        'retail_price': '110€ - 130€',
        'care': {'main_material': 'cuir', 'tips': "Cuir blanc : savon de Marseille + eau tiède. Taches tenaces : pâte de bicarbonate. Semelle : vinaigre blanc. Lingettes nettoyantes pour entretien rapide.", 'avoid': "Jamais en machine, pas de javel (jaunit), pas sous la pluie battante"},
        'style': {'looks': ['Classique : jean slim + t-shirt blanc + AF1 white', 'Streetwear : survêtement + AF1 white', 'Smart casual : chino + blazer + AF1 white', 'Féminin : robe midi + AF1 white']},
        'comfort_rating': 3, 'style_rating': 5, 'durability_rating': 5, 'versatility_rating': 5,
    },
    'samba': {
        'full_name': 'Adidas Samba', 'brand': 'Adidas', 'year': 1950, 'designer': 'Adi Dassler',
        'materials': ['cuir pleine fleur', 'suède sur le toecap', 'semelle gomme caramel'],
        'technology': 'Semelle gomme pour adhérence en salle',
        'sizing': {'fit': 'taille grand', 'advice': "Taillent grand d'une demi-taille. Prenez une demi-taille en dessous. Le cuir se détend avec le port.", 'vs_af1': 'même taille que votre AF1', 'vs_dunk': 'demi-taille en dessous de votre Dunk', 'vs_adidas': 'standard Adidas, demi-taille en dessous', 'vs_nb': 'demi-taille en dessous de votre NB'},
        'history': "Créée en 1950 pour le football en salle sur sol gelé. Plus de 35 millions de paires vendues. Adoptée par la terrace culture UK (supporters foot anglais, années 80). Bob Marley photographié en Samba. Comeback massif 2023-2024, sneaker de l'année. Collaborations Wales Bonner, Pharrell.",
        'cultural_moments': ["Football en salle (1950)", "Terrace culture UK (années 80)", "Bob Marley en Samba", "Comeback 2023-2024, sneaker de l'année", "Collaborations Wales Bonner, Pharrell", "35+ millions de paires vendues"],
        'iconic_colorways': ['OG White/Black (gomme)', 'OG Black/White', 'Wales Bonner (crème/vert)', 'Cloud White', 'Dark Brown'],
        'retail_price': '100€ - 120€',
        'care': {'main_material': 'cuir/suède', 'tips': "Cuir : chiffon humide + savon doux. Toecap suède : brosser à sec. Semelle gomme : gomme magique. Crème nourrissante régulièrement.", 'avoid': "Ne pas tremper le suède du toe cap, pas de produits chimiques sur la gomme"},
        'style': {'looks': ['Casual chic : pantalon à pinces + chemise + Samba', 'Quotidien : jean straight + t-shirt + Samba', 'Féminin : jupe midi + Samba + chaussettes apparentes', 'Smart : blazer + pantalon fluide + Samba']},
        'comfort_rating': 3, 'style_rating': 5, 'durability_rating': 5, 'versatility_rating': 5,
    },
    'campus': {
        'full_name': 'Adidas Campus', 'brand': 'Adidas', 'year': 1983, 'designer': 'Adidas',
        'materials': ['suède premium', 'semelle caoutchouc'],
        'technology': 'Construction suède, semelle vulcanisée',
        'sizing': {'fit': 'taille grand', 'advice': "Demi-taille en dessous. Le suède ne se détend pas beaucoup.", 'vs_af1': 'même taille que votre AF1', 'vs_dunk': 'demi-taille en dessous de votre Dunk', 'vs_adidas': 'standard Adidas', 'vs_nb': 'demi-taille en dessous de votre NB'},
        'history': "À l'origine 'Tournament' dans les 70s, renommée Campus en 1983. Adoptée par les Beastie Boys dans les 80s, symbole hip-hop old school. Le modèle Campus 00s, modernisé avec semelle plus épaisse, a relancé l'engouement en 2023-2024. Collaboration Bad Bunny (2023).",
        'cultural_moments': ["Beastie Boys (années 80)", "Symbole hip-hop new-yorkais", "Retour avec Campus 00s (2023)", "Collaboration Bad Bunny (2023)", "Tendance 'quiet luxury'"],
        'iconic_colorways': ['Dark Green', 'Core Black', 'Grey', 'Burgundy', 'Light Blue'],
        'retail_price': '100€ - 110€',
        'care': {'main_material': 'suède', 'tips': "Brossez à sec avec brosse suède. Gomme à suède pour les taches. Spray imperméabilisant dès l'achat. Séchage naturel.", 'avoid': "NE JAMAIS mouiller, éviter la pluie, pas de savon liquide sur le suède"},
        'style': {'looks': ['Rétro : jean large + t-shirt vintage + Campus', 'Casual : jogger + sweat + Campus', 'Féminin : jupe plissée + Campus + chaussettes hautes']},
        'comfort_rating': 3, 'style_rating': 4, 'durability_rating': 3, 'versatility_rating': 4,
    },
    'gazelle': {
        'full_name': 'Adidas Gazelle', 'brand': 'Adidas', 'year': 1966, 'designer': 'Adidas',
        'materials': ['suède premium', 'semelle caoutchouc', 'doublure textile'],
        'technology': 'Construction légère en suède, semelle plate gomme',
        'sizing': {'fit': 'taille grand', 'advice': "Demi-taille en dessous. La Gazelle est assez étroite, les pieds larges gardent leur taille.", 'vs_af1': 'même taille que votre AF1', 'vs_dunk': 'demi-taille en dessous de votre Dunk', 'vs_adidas': 'standard Adidas (même que Samba)', 'vs_nb': 'demi-taille en dessous de votre NB'},
        'history': "Lancée en 1966, un des plus anciens modèles Adidas encore en production. Adoptée par les mods (60s), punks (70s), terrace culture (80s), Britpop/Oasis (90s). Gazelle Bold avec semelle plateforme (2023-2024). Jennie de Blackpink ambassadrice.",
        'cultural_moments': ["Mods britanniques (1960s)", "Punks (1970s)", "Terrace culture UK (1980s)", "Oasis / Gallagher (1990s)", "Gazelle Bold plateforme (2023-2024)", "Jennie de Blackpink ambassadrice"],
        'iconic_colorways': ['Bold Red/White', 'Core Black/White', 'Collegiate Green', 'Bold Blue', 'Pink/White'],
        'retail_price': '100€ - 110€',
        'care': {'main_material': 'suède', 'tips': "Brossage à sec, spray imperméabilisant. Utilisez des embauchoirs car le suède marque les plis.", 'avoid': "Éviter pluie et humidité, pas de chiffon mouillé"},
        'style': {'looks': ['British : jean slim + polo + Gazelle', 'Casual chic : pantalon tailleur + blazer + Gazelle', 'Féminin : robe courte + Gazelle Bold', 'Indie : jean délavé + t-shirt band + Gazelle']},
        'comfort_rating': 3, 'style_rating': 5, 'durability_rating': 3, 'versatility_rating': 5,
    },
    'yeezy 350': {
        'full_name': 'Yeezy Boost 350 V2', 'brand': 'Adidas / Yeezy', 'year': 2015, 'designer': 'Kanye West',
        'materials': ['Primeknit (tricot technique)', 'semelle Boost TPU', 'bande SPLY-350'],
        'technology': 'Boost (billes TPU, retour énergie maximal), tige Primeknit extensible',
        'sizing': {'fit': 'taille petit', 'advice': "Taille PETIT. Prenez une demi-taille voire une taille au-dessus. Le Primeknit est extensible mais le toebox est serré.", 'vs_af1': 'une taille au-dessus de votre AF1', 'vs_dunk': 'demi-taille au-dessus de votre Dunk', 'vs_adidas': 'demi-taille au-dessus de votre Adidas habituelle', 'vs_nb': 'demi-taille au-dessus de votre NB'},
        'history': "Collaboration Kanye West x Adidas (2015). La Turtle Dove originale est devenue la sneaker la plus convoitée de la décennie. V2 avec bande SPLY-350 (2016). Fin 2022, Adidas rompt avec Kanye suite à ses controverses. Le stock restant vendu sous 'Adidas Yeezy' (2023-2024).",
        'cultural_moments': ["Turtle Dove vendue en secondes (2015)", "V2 Beluga lance la série (2016)", "Démocratisation avec restocks (2019-2020)", "Rupture Adidas x Kanye (2022)", "Vente stock restant (2023-2024)"],
        'iconic_colorways': ['Zebra (blanc/noir)', 'Beluga (gris/orange)', 'Bred (noir/rouge)', 'Cream White', 'Sesame', 'Black Static'],
        'retail_price': '230€ - 260€',
        'care': {'main_material': 'primeknit', 'tips': "Primeknit : brosse douce + eau tiède savonneuse. Semelle Boost jaunit : produit anti-jaunissement. Aérer après chaque port.", 'avoid': "Jamais en machine (Boost se déforme), pas de javel, pas de sèche-linge"},
        'style': {'looks': ['Athleisure : jogger + t-shirt + Yeezy 350', 'Minimaliste : jean slim noir + hoodie noir + Yeezy 350', 'Streetwear : cargo + sweat oversize + Yeezy 350']},
        'comfort_rating': 5, 'style_rating': 4, 'durability_rating': 3, 'versatility_rating': 3,
    },
    'new balance 550': {
        'full_name': 'New Balance 550', 'brand': 'New Balance', 'year': 1989, 'designer': 'New Balance',
        'materials': ['cuir', 'cuir synthétique', 'mesh perforé'],
        'technology': 'Semelle encapsulée, design basketball rétro',
        'sizing': {'fit': 'taille normalement', 'advice': "Taille fidèlement. Cuir rigide au début, temps de rodage. Les pieds larges apprécient le fit NB généreux.", 'vs_af1': 'demi-taille au-dessus de votre AF1', 'vs_dunk': 'même taille', 'vs_adidas': 'demi-taille au-dessus de votre Adidas', 'vs_nb': 'standard NB'},
        'history': "Sortie en 1989 sous le nom P550 et oubliée. Ressuscitée par la collaboration Aimé Leon Dore (ALD) en 2020. Teddy Santis (fondateur ALD) nommé directeur créatif NB Made in USA. Devenue LA sneaker 'quiet luxury' et du style preppy moderne.",
        'cultural_moments': ["Sortie oubliée (1989)", "Collaboration Aimé Leon Dore (2020) = le tournant", "Teddy Santis directeur créatif NB", "Tendance 'quiet luxury' et preppy (2021-2024)", "Portée par mannequins et influenceurs mode"],
        'iconic_colorways': ['White/Green', 'White/Navy', 'White/Red', 'White/Natural', 'ALD exclusifs'],
        'retail_price': '130€ - 150€',
        'care': {'main_material': 'cuir', 'tips': "Cuir : chiffon humide + savon doux. Semelle : bicarbonate. Mesh perforé : brosse douce. Crème nourrissante pour le cuir rigide.", 'avoid': "Pas de machine, pas de javel, pas de soleil direct"},
        'style': {'looks': ['Preppy : chino + chemise Oxford + NB 550', 'Casual : jean droit + t-shirt + NB 550', 'Féminin : jupe plissée + NB 550 + chaussettes', 'Smart : pantalon à pinces + pull + NB 550']},
        'comfort_rating': 3, 'style_rating': 5, 'durability_rating': 4, 'versatility_rating': 5,
    },
    'new balance 2002r': {
        'full_name': 'New Balance 2002R', 'brand': 'New Balance', 'year': 2010, 'designer': 'New Balance',
        'materials': ['suède premium', 'mesh', 'N-ERGY dans la semelle'],
        'technology': 'N-ERGY (mousse premium), ABZORB SBS au talon',
        'sizing': {'fit': 'taille normalement', 'advice': "Taille habituelle. Fit confortable et spacieux, pieds larges à l'aise.", 'vs_af1': 'demi-taille au-dessus de votre AF1', 'vs_dunk': 'même taille', 'vs_adidas': 'demi-taille au-dessus de votre Adidas', 'vs_nb': 'standard NB'},
        'history': "Héritière de la 2002 (running premium 2000s). Relancée en 2020. Collaboration JJJJound (2021, coloris minimalistes) = grail. Edition 'Protection Pack' aspect usé/déconstruit = buzz. Segment premium de NB, populaire dans la mode parisienne et japonaise.",
        'cultural_moments': ["Running premium original (2010)", "Collaboration JJJJound minimaliste (2021)", "Protection Pack 'destroyed' (2022)", "Mode parisienne et japonaise"],
        'iconic_colorways': ['Rain Cloud (gris)', 'Protection Pack (déconstruit)', 'JJJJound Grey/Green', 'Black/Phantom', 'Incense'],
        'retail_price': '140€ - 160€',
        'care': {'main_material': 'suède/mesh', 'tips': "Suède premium : brosser à sec. Mesh : eau tiède. Embauchoirs en cèdre recommandés.", 'avoid': "Ne pas mouiller le suède, pas de machine"},
        'style': {'looks': ['Premium casual : pantalon à pinces + pull maille + 2002R', 'Streetwear élevé : cargo + hoodie + 2002R', 'Minimaliste : tout noir ou gris + 2002R']},
        'comfort_rating': 5, 'style_rating': 5, 'durability_rating': 4, 'versatility_rating': 4,
    },
    'new balance 9060': {
        'full_name': 'New Balance 9060', 'brand': 'New Balance', 'year': 2022, 'designer': 'New Balance',
        'materials': ['suède', 'mesh', 'cuir synthétique', 'semelle FuelCell'],
        'technology': 'FuelCell (mousse ultra réactive), SBS au talon',
        'sizing': {'fit': 'taille normalement', 'advice': "Taille habituelle. Volume intérieur généreux grâce à la silhouette chunky.", 'vs_af1': 'demi-taille au-dessus de votre AF1', 'vs_dunk': 'même taille', 'vs_adidas': 'demi-taille au-dessus de votre Adidas', 'vs_nb': 'standard NB'},
        'history': "Création récente (2022) fusionnant les 990, 860 et 960. Collaboration Joe Freshgoods 'Inside Voices' = succès immédiat. Semelle FuelCell = confort exceptionnel. Nouvelle icône NB.",
        'cultural_moments': ["Joe Freshgoods 'Inside Voices' (2022)", "Fusion 990/860/960", "Semelle FuelCell premium", "Nouvelle icône NB"],
        'iconic_colorways': ["Joe Freshgoods Inside Voices", 'Sea Salt', 'Rain Cloud', 'Arctic Grey', 'Mushroom'],
        'retail_price': '150€ - 170€',
        'care': {'main_material': 'suède/mesh', 'tips': "Suède : brosser à sec. Mesh : brosse douce humide. Semelle FuelCell sensible : éviter terrains abrasifs.", 'avoid': "Surfaces rugueuses usent la FuelCell, ne pas tremper"},
        'style': {'looks': ['Futuriste : pantalon tech + NB 9060 + veste technique', 'Casual : jean large + t-shirt oversize + NB 9060', 'Monochrome : tenue ton sur ton + NB 9060 colorée']},
        'comfort_rating': 5, 'style_rating': 5, 'durability_rating': 4, 'versatility_rating': 3,
    },
    'gel-1130': {
        'full_name': 'Asics Gel-1130', 'brand': 'Asics', 'year': 2008, 'designer': 'Asics',
        'materials': ['mesh technique', 'cuir synthétique', 'overlays réfléchissants'],
        'technology': 'GEL Technology (talon + avant-pied), Trusstic System (stabilité)',
        'sizing': {'fit': 'taille normalement à petit', 'advice': "Asics taille un peu petit et étroit. Pieds larges : demi-taille au-dessus. Pieds standards : taille habituelle.", 'vs_af1': 'même taille ou demi-taille au-dessus vs AF1', 'vs_dunk': 'même taille ou demi-taille au-dessus', 'vs_adidas': 'une taille au-dessus de votre Adidas', 'vs_nb': 'même taille que NB'},
        'history': "Modèle running 2008 passé inaperçu. Mis en lumière par la tendance retro-running 2022-2024. Look technique Y2K + détails réfléchissants. Collaborations Kith, Cecilie Bahnsen. Alternative accessible aux Salomon XT-6.",
        'cultural_moments': ["Running discret (2008)", "Tendance retro-running (2022)", "Collabs Kith, Cecilie Bahnsen", "Esthétique Y2K/tech", "Alternative aux Salomon XT-6"],
        'iconic_colorways': ['White/Clay Canyon', 'Silver/White', 'White/Midnight', 'Oyster Grey', 'Cream/Sage'],
        'retail_price': '120€ - 140€',
        'care': {'main_material': 'mesh', 'tips': "Mesh : brosse douce + eau savonneuse. Détails réfléchissants : chiffon doux. Retirer semelles après chaque port.", 'avoid': "Pas de machine, pas de produits abrasifs sur les réfléchissants"},
        'style': {'looks': ['Tech : pantalon technique + Gel-1130 + Gore-Tex', 'Casual : jean slim + t-shirt + Gel-1130 silver', 'Gorpcore : cargo + polaire + Gel-1130']},
        'comfort_rating': 4, 'style_rating': 4, 'durability_rating': 4, 'versatility_rating': 4,
    },
    'tasman': {
        'full_name': 'UGG Tasman', 'brand': 'UGG', 'year': 2003, 'designer': 'UGG',
        'materials': ['suède extérieur', 'doublure peau de mouton', 'coutures tressées'],
        'technology': 'UGGplush (laine/lyocell), semelle Treadlite',
        'sizing': {'fit': 'taille normalement à grand', 'advice': "Slip-on, fit plus lâche. Entre deux tailles : taille inférieure. La doublure mouton se comprime et s'adapte.", 'vs_af1': 'même taille que AF1', 'vs_dunk': 'même taille ou demi-taille en dessous', 'vs_adidas': 'même taille', 'vs_nb': 'même taille ou demi-taille en dessous'},
        'history': "Existe depuis 2003, virale en 2022-2023. Portée par Kardashian, adoptée par Gen Z. Passée de pantoufle d'intérieur à chaussure de rue tendance. Symbole de la tendance 'comfort first'. Pénuries et listes d'attente en hiver 2023.",
        'cultural_moments': ["Existence discrète (2003)", "Virale TikTok (2022-2023)", "Portée par Gigi Hadid, Kendall Jenner", "Tendance 'cozy/comfort first'", "Pénurie hiver 2023"],
        'iconic_colorways': ['Chestnut', 'Sand', 'Black', 'Mustard Seed', 'Shaded Clover'],
        'retail_price': '110€ - 130€',
        'care': {'main_material': 'suède/peau de mouton', 'tips': "Suède : brosser à sec. Doublure mouton : produit spécial UGG ou vinaigre blanc dilué. Séchage naturel. Spray imperméabilisant UGG.", 'avoid': "NE JAMAIS mouiller complètement, pas de machine, pas de radiateur (mouton rétrécit)"},
        'style': {'looks': ['Cozy : jogging + hoodie + UGG Tasman', 'Casual : jean + pull + UGG Tasman', 'Été : short + UGG Tasman']},
        'comfort_rating': 5, 'style_rating': 3, 'durability_rating': 3, 'versatility_rating': 3,
    },
    'tazz': {
        'full_name': 'UGG Tazz', 'brand': 'UGG', 'year': 2022, 'designer': 'UGG',
        'materials': ['suède', 'doublure peau de mouton', 'semelle plateforme EVA'],
        'technology': 'UGGplush, semelle plateforme surélevée (+3cm)',
        'sizing': {'fit': 'taille normalement', 'advice': "Similaire à la Tasman. Entre deux tailles : taille inférieure. Semelle plateforme ajoute ~3cm.", 'vs_af1': 'même taille', 'vs_dunk': 'même taille', 'vs_adidas': 'même taille', 'vs_nb': 'même taille'},
        'history': "Version plateforme de la Tasman (2022). Semelle surélevée conquiert Gen Z. Plus populaire que la Tasman originale. Symbole du 'platform trend' 2023-2024.",
        'cultural_moments': ["Lancement 2022, succès immédiat", "Évolution plateforme de la Tasman", "Portée par célébrités et influenceurs", "Symbole 'platform trend' 2023-2024"],
        'iconic_colorways': ['Chestnut', 'Sand', 'Black', 'Mustard Seed', 'Seal'],
        'retail_price': '130€ - 150€',
        'care': {'main_material': 'suède/peau de mouton', 'tips': "Même entretien que Tasman. Semelle plateforme : chiffon humide.", 'avoid': "Mêmes précautions que Tasman"},
        'style': {'looks': ['Cozy chic : jean + pull cachemire + UGG Tazz', 'Streetwear : jogging + cropped hoodie + UGG Tazz', 'Féminin : jupe midi + UGG Tazz']},
        'comfort_rating': 5, 'style_rating': 4, 'durability_rating': 3, 'versatility_rating': 3,
    },
}


def get_sneaker_data(subject):
    """Trouve les données enrichies correspondant au sujet dans SNEAKER_DATABASE"""
    if not subject:
        return None
    s = subject.lower()
    best_match = None
    best_score = 0
    for key, data in SNEAKER_DATABASE.items():
        score = 0
        if key in s or s in key:
            score = len(key) + 10
        elif data.get('full_name', '').lower() in s or s in data.get('full_name', '').lower():
            score = len(data.get('full_name', '')) + 10
        else:
            key_parts = key.split()
            for part in key_parts:
                if len(part) > 1 and part in s:
                    score += len(part)
        if score > best_score:
            best_score = score
            best_match = data
    return best_match




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
    for _ in range(5):
        r = shopify_request(f'products.json?limit=50&since_id={since_id}')
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
        if len(r['products']) < 50:
            break
    
    log.info(f"[Blog] Loaded {len(products)} products for linking")
    return products


def find_matching_products(subject, products):
    """Trouve les produits correspondant au sujet"""
    matches = []
    subject_lower = subject.lower()
    
    # Nettoyer le sujet pour extraire les mots-clés importants
    # Ex: "Air Jordan 4" -> ["jordan", "4"]
    # Ex: "Nike Dunk Low" -> ["dunk", "low"]
    subject_clean = subject_lower.replace('-', ' ').replace('air ', '').replace('nike ', '').replace('adidas ', '').replace('new balance ', '')
    keywords = [kw for kw in subject_clean.split() if len(kw) > 1]
    
    for p in products:
        title_lower = p['title'].lower()
        score = 0
        
        # Vérifier chaque mot-clé
        for kw in keywords:
            if kw in title_lower:
                # Bonus si c'est un mot important (chiffre de modèle, nom du modèle)
                if kw.isdigit() or kw in ['dunk', 'jordan', 'yeezy', 'samba', 'campus', 'force', 'max', 'gel']:
                    score += 3
                else:
                    score += 1
        
        # Bonus si le sujet complet est dans le titre
        if subject_lower in title_lower:
            score += 10
        
        # Bonus pour correspondance partielle forte
        # Ex: "jordan 4" dans "Air Jordan 4 Retro Military Black"
        subject_parts = subject_lower.split()
        if len(subject_parts) >= 2:
            # Chercher "jordan 4", "dunk low", etc.
            key_combo = ' '.join(subject_parts[-2:])  # Les 2 derniers mots
            if key_combo in title_lower:
                score += 8
        
        if score > 0:
            matches.append((score, p))
    
    # Trier par score décroissant
    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in matches[:10]]


def generate_article_content(article_type, subject, keywords, tone, length, products, collections):
    """Génère le contenu de l'article selon le type"""
    
    # Trouver les produits et collections liés
    matching_products = find_matching_products(subject, products)
    matching_collection = find_collection(subject, collections)
    
    log.info(f"[Blog] Found {len(matching_products)} matching products for '{subject}'")
    
    # Liens vers produits - VERSION AMÉLIORÉE avec images
    product_links = ""
    if matching_products:
        product_links = "<h3>Découvrez sur KP SHOES</h3>"
        product_links += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:15px;margin:20px 0">'
        
        for p in matching_products[:6]:  # Max 6 produits
            img_html = ""
            if p.get('image'):
                img_html = f'<img src="{p["image"]}" style="width:100%;height:120px;object-fit:contain;background:#f5f5f5;border-radius:8px">'
            else:
                img_html = '<div style="width:100%;height:120px;background:#f5f5f5;border-radius:8px"></div>'
            
            product_links += f'''<a href="{p['url']}" style="text-decoration:none;color:inherit;display:block">
                {img_html}
                <div style="font-size:12px;margin-top:8px;color:#333;text-align:center;line-height:1.3">{p['title'][:50]}{"..." if len(p['title']) > 50 else ""}</div>
            </a>'''
        
        product_links += "</div>"
    
    # Lien collection
    collection_link = ""
    if matching_collection:
        collection_link = f'<p style="margin:20px 0">👉 <strong><a href="{matching_collection["url"]}">Voir toute la collection {matching_collection["title"]}</a></strong></p>'
    
    # Générer selon le type
    if article_type == "guide_taille":
        return generate_sizing_guide(subject, product_links, collection_link, tone)
    elif article_type == "release":
        return generate_release_article(subject, product_links, collection_link, tone)
    elif article_type == "tendance":
        return generate_trend_article(subject, product_links, collection_link, tone, matching_products)
    elif article_type == "comparatif":
        return generate_comparison_article(subject, product_links, collection_link, tone)
    elif article_type == "histoire":
        return generate_history_article(subject, product_links, collection_link, tone)
    elif article_type == "entretien":
        return generate_care_article(subject, product_links, collection_link, tone)
    elif article_type == "style":
        return generate_style_article(subject, product_links, collection_link, tone)
    else:
        return generate_custom_article(subject, keywords, product_links, collection_link, tone)


def generate_sizing_guide(subject, product_links, collection_link, tone):
    """Génère un guide de tailles"""
    title = f"Comment taille la {subject} ? Guide complet des tailles 2026"
    
    # Meta SEO
    meta_title = f"Comment taille la {subject} ? Guide tailles 2026 | KP SHOES"[:70]
    meta_description = f"Découvrez comment taille la {subject}. Tableau des tailles EU/US/UK, conseils pour pieds larges et comparaison avec d'autres modèles. Guide complet."[:160]
    
    # Extrait
    summary = f"Vous vous demandez comment taille la {subject} ? Découvrez notre guide complet avec tableau des tailles, conseils pour bien choisir et comparaisons avec d'autres modèles."
    
    body = f"""
<p>Vous vous demandez <strong>comment taille la {subject}</strong> ? Ce guide complet vous aide à choisir la bonne pointure pour éviter les mauvaises surprises. Chez <strong>KP SHOES</strong>, nous garantissons l'authenticité de chaque paire.</p>

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


def generate_release_article(subject, product_links, collection_link, tone):
    """Génère un article sur les sorties enrichi avec SNEAKER_DATABASE"""
    import datetime
    data = get_sneaker_data(subject)
    full_name = data['full_name'] if data else subject
    month = datetime.datetime.now().strftime('%B %Y')
    
    title = f"Sorties {full_name} 2026 : Calendrier des releases et dates de sortie"
    meta_title = f"Sorties {full_name} 2026 : Dates releases | KP SHOES"[:70]
    meta_description = f"Découvrez toutes les sorties {full_name} prévues en 2026. Calendrier des releases, coloris attendus et conseils pour cop les paires limitées."[:160]
    summary = f"Toutes les sorties {full_name} à ne pas manquer en 2026. Calendrier, coloris attendus et conseils d'achat."
    
    # Colorways depuis la base
    colorways_html = ""
    if data and data.get('iconic_colorways'):
        colorways_html = f"<h2>Les coloris les plus recherchés de la {full_name}</h2>"
        colorways_html += "<p>Voici les coloris qui génèrent la plus forte demande :</p><ul>"
        for cw in data['iconic_colorways']:
            colorways_html += f"<li><strong>{cw}</strong></li>"
        colorways_html += "</ul>"
        colorways_html += f"<p>En 2026, de nouvelles déclinaisons et collaborations inédites sont attendues.</p>"
    else:
        colorways_html = f"<h2>Les coloris les plus attendus</h2>\n<p>Les versions OG, collaborations et éditions limitées de la {full_name} restent les plus recherchées.</p>"
    
    # Collabs
    collabs_html = ""
    if data and data.get('cultural_moments'):
        collabs = [m for m in data['cultural_moments'] if any(w in m.lower() for w in ['collab', ' x ', 'travis', 'off-white', 'virgil', 'jjjjound', 'aimé', 'wales'])]
        if collabs:
            collabs_html = f"<h2>Les collaborations marquantes de la {full_name}</h2><ul>"
            for c in collabs:
                collabs_html += f"<li>{c}</li>"
            collabs_html += "</ul><p>De nouvelles collaborations sont régulièrement annoncées.</p>"
    
    retail_price = data.get('retail_price', '110€ - 200€') if data else '110€ - 200€'
    brand_name = data.get('brand', 'la marque') if data else 'la marque'
    
    body = f"""
<p>Découvrez toutes les <strong>sorties {full_name}</strong> prévues pour 2026. Restez informé des dernières releases et ne manquez aucune paire sur <strong>KP SHOES</strong>.</p>

<h2>Les releases {full_name} à ne pas manquer en 2026</h2>
<p>L'année 2026 s'annonce riche en sorties pour la {full_name}. Entre rééditions de coloris classiques, nouvelles collaborations et éditions limitées, les occasions ne manqueront pas. {brand_name} continue d'alimenter la hype avec des drops réguliers.</p>

{colorways_html}

{collabs_html}

<h2>Comment cop les {full_name} en édition limitée ?</h2>
<ul>
<li><strong>Suivez les comptes officiels</strong> : Les annonces passent d'abord par les réseaux sociaux de {brand_name}</li>
<li><strong>Utilisez les apps de raffle</strong> : SNKRS (Nike), Confirmed (Adidas), ou les raffles boutiques</li>
<li><strong>Préparez-vous à l'avance</strong> : Comptes créés, paiement enregistré, notifications activées</li>
<li><strong>Misez sur les revendeurs de confiance</strong> : <strong>KP SHOES</strong> garantit l'authenticité de chaque paire</li>
</ul>

{collection_link}

<h2>Prix et disponibilité</h2>
<p>Le prix retail de la {full_name} se situe entre <strong>{retail_price}</strong>. Sur le marché du resell, certains coloris (collaborations, éditions limitées) atteignent 2 à 10 fois le prix retail.</p>
<p>Sur <strong>KP SHOES</strong>, nous proposons ces modèles au meilleur prix avec <strong>garantie d'authenticité 100%</strong>.</p>

{product_links}

<p><strong>Sur KP SHOES, retrouvez les {full_name} 100% authentiques avec livraison rapide et paiement sécurisé.</strong></p>
"""
    
    return {
        'title': title, 'body_html': body,
        'tags': f'sortie, release, {subject}, calendrier, 2026, {full_name}',
        'handle': f'sorties-{subject.lower().replace(" ", "-")}-2026',
        'meta_title': meta_title, 'meta_description': meta_description,
        'summary_html': summary, 'needs_image': True, 'image_search_term': subject
    }

def generate_trend_article(subject, product_links, collection_link, tone, matching_products):
    """Génère un article sur les tendances enrichi avec SNEAKER_DATABASE"""
    data = get_sneaker_data(subject) if subject else None
    
    if subject and data:
        full_name = data['full_name']
        title = f"{full_name} : Pourquoi c'est LA sneaker tendance de 2026"
        meta_title = f"{full_name} : Sneaker tendance 2026 | KP SHOES"[:70]
        meta_description = f"Découvrez pourquoi la {full_name} est LA sneaker tendance de 2026. Histoire, style et conseils pour l'adopter."[:160]
        summary = f"La {full_name} s'impose comme l'une des sneakers les plus tendance de 2026."
    else:
        full_name = subject or 'Sneakers'
        title = "Sneakers tendance 2026 : Les modèles les plus hype du moment"
        meta_title = "Sneakers tendance 2026 : Les incontournables | KP SHOES"[:70]
        meta_description = "Découvrez les sneakers les plus tendance en 2026. Running rétro, classiques et collaborations. Notre sélection."[:160]
        summary = "Quelles sont les sneakers les plus tendance en 2026 ? Notre sélection des modèles incontournables."
    
    # Construire le contenu spécifique si on a les données
    specific_html = ""
    if data:
        year = data.get('year', '')
        cultural = data.get('cultural_moments', [])
        style_info = data.get('style', {})
        looks = style_info.get('looks', [])
        colorways = data.get('iconic_colorways', [])
        
        cultural_html = ""
        if cultural:
            cultural_html = f"<h2>Pourquoi la {full_name} est-elle si hype ?</h2><p>Son parcours explique son statut iconique :</p><ul>"
            for c in cultural[-5:]:
                cultural_html += f"<li>{c}</li>"
            cultural_html += "</ul>"
        
        looks_html = ""
        if looks:
            looks_html = f"<h2>Comment porter la {full_name} en 2026</h2><ul>"
            for look in looks:
                parts = look.split(' : ', 1)
                if len(parts) == 2:
                    looks_html += f"<li><strong>{parts[0]}</strong> : {parts[1]}</li>"
                else:
                    looks_html += f"<li>{look}</li>"
            looks_html += "</ul>"
        
        colorways_html = ""
        if colorways:
            colorways_html = f"<h2>Les coloris les plus recherchés</h2><ul>"
            for cw in colorways[:5]:
                colorways_html += f"<li><strong>{cw}</strong></li>"
            colorways_html += "</ul>"
        
        history_snippet = data.get('history', '')
        if len(history_snippet) > 300:
            history_snippet = history_snippet[:300] + '...'
        
        specific_html = f"""
<h2>L'histoire derrière le succès</h2>
<p>{history_snippet}</p>

{cultural_html}

{colorways_html}

{looks_html}
"""
    else:
        specific_html = """
<h2>Les tendances sneakers 2026</h2>

<h3>1. Le retour du running rétro</h3>
<p>Les silhouettes des années 90-2000 dominent. Les <strong>Asics Gel-1130</strong>, <strong>New Balance 530</strong> et <strong>New Balance 2002R</strong> sont partout dans les rues, portées par la tendance Y2K et gorpcore.</p>

<h3>2. Les classiques Adidas</h3>
<p>La <strong>Samba</strong>, la <strong>Gazelle</strong> et la <strong>Campus</strong> continuent leur règne. Portées par la terrace culture et le style casual chic européen, elles ne montrent aucun signe de ralentissement.</p>

<h3>3. Les indémodables Nike</h3>
<p>La <strong>Nike Dunk Low</strong>, la <strong>Air Force 1</strong> et les <strong>Air Jordan 1</strong> restent des valeurs sûres. Universelles et faciles à porter, elles s'adaptent à tous les styles.</p>

<h3>4. New Balance, la marque du moment</h3>
<p>Avec la <strong>550</strong> (style preppy), la <strong>2002R</strong> (premium casual) et la <strong>9060</strong> (futuriste), New Balance domine le segment mode. La marque attire les amateurs de 'quiet luxury'.</p>

<h3>5. Les collaborations et éditions limitées</h3>
<p>Les partenariats avec des designers et artistes (Travis Scott, Wales Bonner, JJJJound, Aimé Leon Dore) créent des pièces collector ultra recherchées.</p>
"""
    
    body = f"""
<p>Quelles sont les <strong>sneakers les plus tendance en 2026</strong> ? Entre retours de classiques, nouvelles silhouettes et collaborations exceptionnelles, le marché de la sneaker ne cesse d'évoluer.</p>

{specific_html}

{collection_link}

<h2>Notre sélection KP SHOES</h2>
{product_links}

<h2>Comment adopter la tendance ?</h2>
<ul>
<li><strong>Investissez dans des classiques</strong> : Les modèles iconiques ne se démodent jamais et prennent même de la valeur</li>
<li><strong>Osez les couleurs</strong> : Les coloris audacieux sont très recherchés et permettent de se démarquer</li>
<li><strong>Mixez les styles</strong> : N'hésitez pas à porter des sneakers techniques avec une tenue habillée, c'est la tendance</li>
<li><strong>Privilégiez l'authenticité</strong> : Une paire authentique dure plus longtemps et conserve sa valeur</li>
</ul>

<p><strong>Chez KP SHOES, retrouvez tous les modèles tendance 100% authentiques.</strong> Notre équipe vérifie chaque paire avant expédition.</p>
"""
    
    handle = f'{subject.lower().replace(" ", "-")}-tendance-2026' if subject else 'sneakers-tendance-2026'
    
    return {
        'title': title, 'body_html': body,
        'tags': f'tendance, sneakers 2026, hype, mode, {subject}',
        'handle': handle,
        'meta_title': meta_title, 'meta_description': meta_description,
        'summary_html': summary, 'needs_image': True,
        'image_search_term': subject if subject else 'Nike Dunk Low'
    }

def generate_comparison_article(subject, product_links, collection_link, tone):
    """Génère un article comparatif enrichi avec SNEAKER_DATABASE"""
    models = subject.split(' vs ') if ' vs ' in subject else [subject, 'Nike Dunk Low']
    model1 = models[0].strip()
    model2 = models[1].strip() if len(models) > 1 else 'Nike Dunk Low'
    
    data1 = get_sneaker_data(model1)
    data2 = get_sneaker_data(model2)
    
    name1 = data1['full_name'] if data1 else model1
    name2 = data2['full_name'] if data2 else model2
    
    title = f"{name1} vs {name2} : Quelle sneaker choisir en 2026 ?"
    meta_title = f"{name1} vs {name2} : Comparatif 2026 | KP SHOES"[:70]
    meta_description = f"Comparatif {name1} vs {name2}. Confort, style, taille, prix : on vous aide à choisir la sneaker faite pour vous."[:160]
    summary = f"Vous hésitez entre {name1} et {name2} ? Notre comparatif détaillé vous aide à faire le bon choix."
    
    # Ratings
    def stars(rating):
        return '⭐' * rating + '☆' * (5 - rating) if rating else '⭐⭐⭐⭐'
    
    c1 = data1.get('comfort_rating', 4) if data1 else 4
    c2 = data2.get('comfort_rating', 4) if data2 else 4
    s1 = data1.get('style_rating', 4) if data1 else 4
    s2 = data2.get('style_rating', 4) if data2 else 4
    d1 = data1.get('durability_rating', 4) if data1 else 4
    d2 = data2.get('durability_rating', 4) if data2 else 4
    v1 = data1.get('versatility_rating', 4) if data1 else 4
    v2 = data2.get('versatility_rating', 4) if data2 else 4
    
    # Infos spécifiques
    year1 = data1.get('year', '?') if data1 else '?'
    year2 = data2.get('year', '?') if data2 else '?'
    price1 = data1.get('retail_price', '~150€') if data1 else '~150€'
    price2 = data2.get('retail_price', '~150€') if data2 else '~150€'
    mat1 = ', '.join(data1.get('materials', ['cuir'])) if data1 else 'cuir'
    mat2 = ', '.join(data2.get('materials', ['cuir'])) if data2 else 'cuir'
    fit1 = data1['sizing']['fit'] if data1 and data1.get('sizing') else 'taille normalement'
    fit2 = data2['sizing']['fit'] if data2 and data2.get('sizing') else 'taille normalement'
    
    # Points forts/faibles spécifiques
    def get_pros_cons(data, name):
        pros = []
        cons = []
        if data:
            if data.get('comfort_rating', 0) >= 4: pros.append("Confort exceptionnel au quotidien")
            elif data.get('comfort_rating', 0) <= 2: cons.append("Confort limité, nécessite un temps de rodage")
            
            if data.get('style_rating', 0) >= 4: pros.append("Design iconique très recherché")
            if data.get('versatility_rating', 0) >= 4: pros.append("Ultra polyvalente, s'accorde avec tout")
            elif data.get('versatility_rating', 0) <= 3: cons.append("Moins polyvalente, style plus spécifique")
            
            if data.get('durability_rating', 0) >= 4: pros.append("Matériaux durables, excellente longévité")
            elif data.get('durability_rating', 0) <= 3: cons.append("Matériaux plus fragiles, nécessite un entretien régulier")
            
            if data.get('history'): pros.append(f"Riche héritage culturel depuis {data.get('year', '?')}")
            
            if 'petit' in fit1 if data == data1 else 'petit' in fit2: cons.append("Taille petit, attention au sizing")
            if 'grand' in fit1 if data == data1 else 'grand' in fit2: cons.append("Taille grand, prendre une demi-taille en dessous")
        
        if not pros: pros = ["Design apprécié", "Large choix de coloris", "Bonne qualité"]
        if not cons: cons = ["Certains coloris difficiles à trouver"]
        return pros[:4], cons[:3]
    
    pros1, cons1 = get_pros_cons(data1, name1)
    pros2, cons2 = get_pros_cons(data2, name2)
    
    # Verdict
    score1 = c1 + s1 + d1 + v1
    score2 = c2 + s2 + d2 + v2
    if score1 > score2:
        verdict = f"Sur l'ensemble de nos critères, la <strong>{name1}</strong> prend un léger avantage grâce à {'son confort supérieur' if c1 > c2 else 'sa plus grande polyvalence' if v1 > v2 else 'son design iconique'}. Cependant, la <strong>{name2}</strong> reste un excellent choix{', surtout si vous recherchez plus de polyvalence' if v2 > v1 else ', notamment pour son rapport qualité-prix' if 'moins' in price2.lower() else ''}."
    elif score2 > score1:
        verdict = f"La <strong>{name2}</strong> se démarque légèrement grâce à {'son confort supérieur' if c2 > c1 else 'sa plus grande polyvalence' if v2 > v1 else 'son design iconique'}. Mais la <strong>{name1}</strong> n'est pas en reste{', avec un style unique et reconnaissable' if s1 >= 4 else ''}."
    else:
        verdict = f"Les deux modèles sont au coude à coude ! La <strong>{name1}</strong> et la <strong>{name2}</strong> sont toutes deux d'excellents choix. Votre décision dépendra de votre style personnel et de l'usage que vous comptez en faire."
    
    body = f"""
<p>Vous hésitez entre la <strong>{name1}</strong> et la <strong>{name2}</strong> ? Ce comparatif détaillé basé sur notre expertise vous aide à faire le bon choix.</p>

<h2>Tableau comparatif détaillé</h2>
<table style="width:100%;border-collapse:collapse;margin:20px 0">
<tr style="background:#f5f5f5"><th style="padding:12px;border:1px solid #ddd">Critère</th><th style="padding:12px;border:1px solid #ddd">{name1}</th><th style="padding:12px;border:1px solid #ddd">{name2}</th></tr>
<tr><td style="padding:10px;border:1px solid #ddd"><strong>Année de création</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">{year1}</td><td style="padding:10px;border:1px solid #ddd;text-align:center">{year2}</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd"><strong>Confort</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">{stars(c1)}</td><td style="padding:10px;border:1px solid #ddd;text-align:center">{stars(c2)}</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd"><strong>Style</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">{stars(s1)}</td><td style="padding:10px;border:1px solid #ddd;text-align:center">{stars(s2)}</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd"><strong>Polyvalence</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">{stars(v1)}</td><td style="padding:10px;border:1px solid #ddd;text-align:center">{stars(v2)}</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd"><strong>Durabilité</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">{stars(d1)}</td><td style="padding:10px;border:1px solid #ddd;text-align:center">{stars(d2)}</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd"><strong>Matériaux</strong></td><td style="padding:10px;border:1px solid #ddd">{mat1}</td><td style="padding:10px;border:1px solid #ddd">{mat2}</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd"><strong>Taille</strong></td><td style="padding:10px;border:1px solid #ddd">{fit1}</td><td style="padding:10px;border:1px solid #ddd">{fit2}</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd"><strong>Prix retail</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">{price1}</td><td style="padding:10px;border:1px solid #ddd;text-align:center">{price2}</td></tr>
</table>

<h2>{name1} : Points forts et faibles</h2>
<h3>✅ Avantages</h3>
<ul>""" + ''.join(f'<li>{p}</li>' for p in pros1) + f"""</ul>
<h3>❌ Inconvénients</h3>
<ul>""" + ''.join(f'<li>{c}</li>' for c in cons1) + f"""</ul>

<h2>{name2} : Points forts et faibles</h2>
<h3>✅ Avantages</h3>
<ul>""" + ''.join(f'<li>{p}</li>' for p in pros2) + f"""</ul>
<h3>❌ Inconvénients</h3>
<ul>""" + ''.join(f'<li>{c}</li>' for c in cons2) + f"""</ul>

{collection_link}

<h2>Notre verdict</h2>
<p>{verdict}</p>
<p>Dans les deux cas, <strong>achetez toujours authentique</strong>. Les contrefaçons n'offrent ni le même confort, ni la même durabilité, ni la même satisfaction.</p>

{product_links}

<p><strong>Retrouvez ces deux modèles sur KP SHOES, 100% authentiques et vérifiés par nos experts.</strong></p>
"""
    
    return {
        'title': title, 'body_html': body,
        'tags': f'comparatif, {model1}, {model2}, versus, guide achat',
        'handle': f'comparatif-{model1.lower().replace(" ", "-")}-vs-{model2.lower().replace(" ", "-")}',
        'meta_title': meta_title, 'meta_description': meta_description,
        'summary_html': summary, 'needs_image': True, 'image_search_term': model1
    }

def generate_history_article(subject, product_links, collection_link, tone):
    """Génère un article histoire enrichi avec SNEAKER_DATABASE"""
    data = get_sneaker_data(subject)
    full_name = data['full_name'] if data else subject
    
    title = f"L'histoire de la {full_name} : De sa création à aujourd'hui"
    meta_title = f"Histoire de la {full_name} : Origines et évolution | KP SHOES"[:70]
    meta_description = f"Découvrez l'histoire fascinante de la {full_name}. De ses origines à son statut d'icône streetwear, retour sur un modèle légendaire."[:160]
    summary = f"La {full_name} est bien plus qu'une sneaker. Découvrez son histoire, de sa création à son statut d'icône culturelle."
    
    # Contenu enrichi depuis la base
    if data:
        year = data.get('year', '')
        designer = data.get('designer', '')
        history = data.get('history', '')
        cultural = data.get('cultural_moments', [])
        colorways = data.get('iconic_colorways', [])
        materials = ', '.join(data.get('materials', []))
        tech = data.get('technology', '')
        brand = data.get('brand', '')
        
        # Section origines
        origins_html = f"""<h2>Les origines ({year})</h2>
<p>{history}</p>
<p>Créée par <strong>{designer}</strong>{' pour ' + brand if brand else ''}, la {full_name} était construite avec {materials}. Sa technologie : {tech}.</p>"""
        
        # Section moments culturels
        cultural_html = ""
        if cultural:
            cultural_html = f"<h2>Les moments clés de la {full_name}</h2><p>Chronologie des événements qui ont forgé sa légende :</p><ul>"
            for c in cultural:
                cultural_html += f"<li><strong>{c}</strong></li>"
            cultural_html += "</ul>"
        
        # Section colorways
        colorways_html = ""
        if colorways:
            colorways_html = f"<h2>Les coloris emblématiques</h2><p>Certains coloris sont devenus des légendes à part entière :</p><ul>"
            for cw in colorways:
                colorways_html += f"<li><strong>{cw}</strong></li>"
            colorways_html += "</ul>"
            colorways_html += "<p>Les coloris OG (originaux) restent les plus recherchés par les collectionneurs, tandis que les collaborations limitées atteignent des prix records sur le marché du resell.</p>"
        
    else:
        origins_html = f"""<h2>Les origines</h2>
<p>Créée pour répondre aux besoins des athlètes professionnels, la {full_name} a rapidement dépassé le cadre sportif pour devenir un symbole de la culture urbaine. Son design innovant et son confort ont séduit des millions de personnes.</p>"""
        cultural_html = ""
        colorways_html = f"""<h2>Les coloris emblématiques</h2>
<ul>
<li>Les versions OG (Original) restent les plus recherchées</li>
<li>Les collaborations limitées atteignent des prix records</li>
<li>Les coloris rétro séduisent les collectionneurs</li>
</ul>"""
    
    body = f"""
<p>La <strong>{full_name}</strong> est bien plus qu'une simple paire de sneakers. C'est une icône qui a marqué l'histoire de la culture streetwear et du sport. Découvrez son parcours fascinant.</p>

{origins_html}

<h2>L'évolution à travers les décennies</h2>
<h3>Les premières années</h3>
<p>À ses débuts, la {full_name} était avant tout un produit technique. Sa conception répondait à des critères de performance stricts. Mais son design distinctif a rapidement attiré l'attention au-delà du sport.</p>

<h3>La consécration streetwear</h3>
<p>C'est dans les années 90-2000 que la {full_name} a véritablement conquis les rues. Adoptée par les rappeurs, les skateurs et les amateurs de mode, elle est devenue un incontournable du style urbain. Les célébrités et les artistes l'ont portée sur scène et dans leurs clips, amplifiant son influence culturelle.</p>

<h3>Aujourd'hui</h3>
<p>En 2026, la {full_name} continue de fasciner. Les rééditions, les collaborations avec des designers de renom et les éditions limitées maintiennent l'engouement. Elle reste l'une des silhouettes les plus recherchées au monde.</p>

{cultural_html}

{colorways_html}

{collection_link}

{product_links}

<h2>Pourquoi la {full_name} est-elle si populaire ?</h2>
<ul>
<li><strong>Un design intemporel</strong> : Ses lignes n'ont pas pris une ride depuis sa création</li>
<li><strong>Un héritage culturel fort</strong> : Portée par des légendes du sport, de la musique et de la mode</li>
<li><strong>Une qualité reconnue</strong> : Des matériaux premium pour une durabilité éprouvée</li>
<li><strong>Une communauté passionnée</strong> : Des millions de fans et collectionneurs à travers le monde</li>
</ul>

<p><strong>Retrouvez la {full_name} sur KP SHOES. Chaque paire est 100% authentique et vérifiée par nos experts.</strong></p>
"""
    
    return {
        'title': title, 'body_html': body,
        'tags': f'histoire, {subject}, culture sneaker, héritage, {full_name}',
        'handle': f'histoire-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title, 'meta_description': meta_description,
        'summary_html': summary, 'needs_image': True, 'image_search_term': subject
    }

def generate_care_article(subject, product_links, collection_link, tone):
    """Génère un article entretien enrichi avec SNEAKER_DATABASE"""
    data = get_sneaker_data(subject)
    full_name = data['full_name'] if data else subject
    
    title = f"Comment nettoyer et entretenir ses {full_name} ? Guide complet"
    meta_title = f"Comment nettoyer ses {full_name} ? Guide entretien | KP SHOES"[:70]
    meta_description = f"Découvrez comment nettoyer et entretenir vos {full_name}. Conseils d'experts adaptés aux matériaux, erreurs à éviter."[:160]
    summary = f"Vos {full_name} méritent le meilleur entretien. Découvrez nos conseils d'experts adaptés à leurs matériaux."
    
    # Infos spécifiques
    if data and data.get('care'):
        care = data['care']
        main_material = care.get('main_material', 'cuir')
        specific_tips = care.get('tips', '')
        avoid = care.get('avoid', '')
        materials = data.get('materials', [])
        materials_str = ', '.join(materials) if materials else 'cuir et textile'
    else:
        main_material = 'cuir'
        specific_tips = "Nettoyez avec un chiffon humide et du savon doux."
        avoid = "Ne jamais mettre en machine, éviter la javel"
        materials_str = 'cuir et textile'
    
    # Section spécifique au matériau principal
    material_section = ""
    if 'suède' in main_material.lower() or 'suede' in main_material.lower() or 'nubuck' in main_material.lower():
        material_section = f"""
<h2>Entretien spécifique du suède/nubuck de la {full_name}</h2>
<p>Le suède est le matériau dominant de la {full_name}. Il nécessite un entretien particulier :</p>
<ul>
<li><strong>Brossage régulier</strong> : Utilisez une brosse à suède (poils en crêpe ou laiton) pour éliminer la poussière et raviver le velours. Brossez toujours dans le même sens.</li>
<li><strong>Taches sèches</strong> : Utilisez une gomme à suède (ou une gomme d'écolier propre) en frottant délicatement la zone tachée.</li>
<li><strong>Taches humides</strong> : Tamponnez immédiatement avec un chiffon sec. Ne frottez JAMAIS une tache humide sur du suède.</li>
<li><strong>Protection</strong> : Appliquez un spray imperméabilisant spécial suède <strong>dès l'achat</strong>, avant même de les porter. Renouvelez toutes les 2-3 semaines.</li>
</ul>
<p><strong>⚠️ Règle d'or</strong> : Le suède et l'eau ne font pas bon ménage. Évitez de porter vos {full_name} par temps de pluie.</p>"""

    elif 'primeknit' in main_material.lower() or 'mesh' in main_material.lower():
        material_section = f"""
<h2>Entretien spécifique du {'Primeknit' if 'primeknit' in main_material.lower() else 'mesh'} de la {full_name}</h2>
<p>La tige en {'Primeknit' if 'primeknit' in main_material.lower() else 'mesh technique'} est plus facile à entretenir que le cuir ou le suède :</p>
<ul>
<li><strong>Nettoyage courant</strong> : Brosse douce (brosse à dents souple) avec de l'eau tiède et un peu de savon de Marseille ou de liquide vaisselle doux.</li>
<li><strong>Taches tenaces</strong> : Appliquez du bicarbonate de soude en pâte, laissez agir 15 minutes, puis brossez doucement.</li>
<li><strong>Séchage</strong> : Bourrez l'intérieur de papier journal et laissez sécher à l'air libre, loin de toute source de chaleur.</li>
<li><strong>La semelle {'Boost' if 'primeknit' in main_material.lower() else ''}</strong> : {'Elle jaunit avec le temps. Utilisez un produit anti-jaunissement ou du peroxyde d hydrogène au soleil.' if 'primeknit' in main_material.lower() else 'Nettoyez-la avec un chiffon humide.'}</li>
</ul>"""

    elif 'cuir' in main_material.lower():
        material_section = f"""
<h2>Entretien spécifique du cuir de la {full_name}</h2>
<p>Le cuir est un matériau noble qui récompense un bon entretien :</p>
<ul>
<li><strong>Nettoyage courant</strong> : Chiffon microfibre légèrement humide avec une goutte de savon de Marseille. Essuyez en mouvements circulaires.</li>
<li><strong>Nourrissage</strong> : Appliquez une crème nourrissante pour cuir tous les 2-3 mois pour éviter le dessèchement et les craquelures.</li>
<li><strong>Cuir blanc</strong> : Pour les taches, faites une pâte de bicarbonate de soude + eau. Appliquez, laissez sécher, puis brossez doucement.</li>
<li><strong>Plis du cuir</strong> : Utilisez des embauchoirs en cèdre pour maintenir la forme entre les ports.</li>
</ul>"""

    elif 'peau de mouton' in main_material.lower() or 'mouton' in main_material.lower():
        material_section = f"""
<h2>Entretien spécifique de la peau de mouton de la {full_name}</h2>
<p>La doublure en peau de mouton est délicate mais peut durer des années avec un bon entretien :</p>
<ul>
<li><strong>Intérieur</strong> : Saupoudrez de bicarbonate de soude, laissez agir toute la nuit, puis secouez. Cela absorbe les odeurs et l'humidité.</li>
<li><strong>Extérieur en suède</strong> : Brossez à sec avec une brosse à suède. Pas d'eau !</li>
<li><strong>Odeurs</strong> : Utilisez du vinaigre blanc dilué (1:1 avec de l'eau) en spray léger sur l'intérieur.</li>
<li><strong>Protection</strong> : Spray imperméabilisant UGG ou équivalent dès l'achat.</li>
</ul>
<p><strong>⚠️ Important</strong> : Ne JAMAIS tremper ni passer en machine. La peau de mouton rétrécit à la chaleur.</p>"""

    body = f"""
<p>Vos <strong>{full_name}</strong> méritent un entretien adapté à leurs matériaux ({materials_str}). Découvrez nos conseils d'experts pour les garder impeccables le plus longtemps possible.</p>

<h2>Ce qu'il vous faut</h2>
<ul>
<li>Une brosse à poils doux (brosse à dents souple en dépannage)</li>
<li>Un chiffon microfibre</li>
<li>Du savon de Marseille ou nettoyant spécial sneakers</li>
<li>De l'eau tiède</li>
<li>Un spray imperméabilisant{' spécial suède' if 'suède' in main_material.lower() else ''}</li>
{'<li>Une brosse à suède et une gomme à suède</li>' if 'suède' in main_material.lower() else ''}
{'<li>Une crème nourrissante pour cuir</li>' if 'cuir' in main_material.lower() else ''}
<li>Des embauchoirs (en cèdre idéalement)</li>
</ul>

<h2>Étapes de nettoyage de la {full_name}</h2>
<h3>1. Préparation</h3>
<p>Retirez les lacets et les semelles intérieures. Brossez délicatement pour enlever poussière et saletés superficielles. Lavez les lacets séparément dans une bassine d'eau tiède savonneuse.</p>

<h3>2. Nettoyage adapté</h3>
<p>{specific_tips}</p>

<h3>3. Rinçage et séchage</h3>
<p>Essuyez avec un chiffon propre légèrement humide. Bourrez l'intérieur avec du papier journal (à changer toutes les 2 heures). Laissez sécher à l'air libre, <strong>jamais</strong> en plein soleil ni près d'un radiateur.</p>

{material_section}

<h2>Erreurs à éviter avec vos {full_name}</h2>
<ul>
<li>❌ <strong>Ne JAMAIS mettre en machine</strong> : Déformation, décollage de la semelle, dégradation des matériaux</li>
<li>❌ <strong>Pas de sèche-linge ni radiateur</strong> : La chaleur détériore les colles et déforme les matériaux</li>
<li>❌ <strong>Pas de javel</strong> : Elle jaunit les matériaux blancs et fragilise les fibres</li>
<li>❌ <strong>{avoid}</strong></li>
</ul>

{collection_link}

{product_links}

<h2>Protection et stockage</h2>
<ul>
<li>Appliquez un spray imperméabilisant <strong>avant la première utilisation</strong></li>
<li>Rangez vos {full_name} dans leur boîte d'origine avec du papier de soie</li>
<li>Utilisez des embauchoirs en cèdre pour maintenir la forme et absorber l'humidité</li>
<li>Évitez l'humidité et la lumière directe du soleil (le cuir et le suède se décolorent)</li>
<li>Alternez vos paires : ne portez pas la même deux jours consécutifs</li>
</ul>

<p><strong>Chez KP SHOES, toutes nos sneakers sont livrées dans un état impeccable. 100% authentiques et vérifiées par nos experts.</strong></p>
"""
    
    return {
        'title': title, 'body_html': body,
        'tags': f'entretien, nettoyage, {subject}, sneaker care, {full_name}',
        'handle': f'entretien-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title, 'meta_description': meta_description,
        'summary_html': summary, 'needs_image': True, 'image_search_term': subject
    }

def generate_style_article(subject, product_links, collection_link, tone):
    """Génère un article style enrichi avec SNEAKER_DATABASE"""
    data = get_sneaker_data(subject)
    full_name = data['full_name'] if data else subject
    
    title = f"Comment porter la {full_name} ? Idées de looks et outfits 2026"
    meta_title = f"Comment porter la {full_name} ? Looks 2026 | KP SHOES"[:70]
    meta_description = f"Découvrez comment porter la {full_name}. Looks casual, streetwear et smart casual : nos idées d'outfits pour tous les styles."[:160]
    summary = f"La {full_name} est ultra polyvalente. Découvrez nos idées de looks pour la porter avec style."
    
    # Looks spécifiques
    if data and data.get('style'):
        looks = data['style'].get('looks', [])
        colorways = data.get('iconic_colorways', [])
    else:
        looks = []
        colorways = []
    
    looks_html = ""
    if looks:
        looks_html = f"<h2>Nos idées de looks avec la {full_name}</h2><ul>"
        for look in looks:
            parts = look.split(' : ', 1)
            if len(parts) == 2:
                looks_html += f"<li><strong>{parts[0]}</strong> : {parts[1]}</li>"
            else:
                looks_html += f"<li>{look}</li>"
        looks_html += "</ul>"
    else:
        looks_html = f"""<h2>Nos idées de looks</h2>
<h3>Look casual quotidien</h3>
<p>Jean slim ou regular + t-shirt basique + {full_name}. Le combo simple et efficace.</p>
<h3>Look streetwear</h3>
<p>Pantalon cargo + sweat oversize + {full_name}. Le style urbain affirmé.</p>
<h3>Look smart casual</h3>
<p>Chino + chemise + blazer léger + {full_name}. Oui, les sneakers passent au bureau.</p>"""
    
    # Couleurs avec colorways spécifiques
    colors_html = ""
    if colorways:
        # Séparer les coloris par famille
        whites = [c for c in colorways if any(w in c.lower() for w in ['white', 'blanc', 'cream', 'triple white'])]
        blacks = [c for c in colorways if any(w in c.lower() for w in ['black', 'noir', 'triple black'])]
        colors = [c for c in colorways if c not in whites and c not in blacks]
        
        colors_html = "<h2>Quel coloris choisir selon votre style ?</h2>"
        if whites:
            cw_str = ', '.join(whites[:2])
            colors_html += f"""<h3>Coloris clairs ({cw_str}...)</h3>
<p>Le choix le plus polyvalent. Se porte avec absolument tout : jean bleu, pantalon noir, couleurs vives. Idéal si c'est votre première {full_name}.</p>"""
        if blacks:
            cw_str = ', '.join(blacks[:2])
            colors_html += f"""<h3>Coloris sombres ({cw_str}...)</h3>
<p>Parfaits pour un look monochrome ou urbain. Se combinent avec des couleurs neutres (gris, beige, blanc) pour un style maîtrisé.</p>"""
        if colors:
            cw_str = ', '.join(colors[:3])
            colors_html += f"""<h3>Coloris signature ({cw_str}...)</h3>
<p>Les coloris emblématiques font de vos {full_name} la pièce maîtresse de la tenue. Gardez le reste de l'outfit sobre (tons neutres) pour les laisser briller.</p>"""
    else:
        colors_html = f"""<h2>Les couleurs qui matchent</h2>
<h3>Avec des {full_name} blanches</h3>
<p>Tout ! Le blanc est la couleur la plus polyvalente.</p>
<h3>Avec des {full_name} noires</h3>
<p>Parfaites pour un look monochrome ou avec des couleurs neutres.</p>
<h3>Avec des {full_name} colorées</h3>
<p>Gardez le reste sobre pour laisser les sneakers comme point focal.</p>"""
    
    body = f"""
<p>La <strong>{full_name}</strong> est bien plus qu'une sneaker : c'est un accessoire de mode à part entière. Découvrez nos conseils pour créer des looks tendance avec cette paire {'iconique' if data and data.get('year', 2020) < 2000 else 'incontournable'}.</p>

{looks_html}

{colors_html}

{collection_link}

{product_links}

<h2>Règles de style avec des sneakers</h2>
<ul>
<li><strong>Équilibrez les proportions</strong> : {'Sneaker à semelle épaisse = pantalon plus ajusté ou droit' if data and data.get('comfort_rating', 3) >= 4 else 'Sneaker basse et fine = pantalon large ou slim, tout fonctionne'}</li>
<li><strong>Jouez avec les textures</strong> : Cuir, denim, coton, maille... Variez les matières pour un look travaillé</li>
<li><strong>Accessoirisez</strong> : Montre, casquette, sac assorti ou en contraste</li>
<li><strong>Soignez vos sneakers</strong> : Une paire propre et bien entretenue change tout le look</li>
<li><strong>Assumez votre style</strong> : Les sneakers se portent avec confiance, pas avec des excuses</li>
</ul>

<h2>Erreurs à éviter</h2>
<ul>
<li>❌ Porter des sneakers abîmées ou sales avec une tenue soignée</li>
<li>❌ Trop de logos et de marques dans la même tenue</li>
<li>❌ Des chaussettes blanches de sport avec un look habillé (optez pour des chaussettes invisibles ou des chaussettes assorties)</li>
<li>❌ Forcer l'association sneakers + costume strict (sauf si le dress code le permet)</li>
</ul>

<p><strong>Retrouvez la {full_name} sur KP SHOES. 100% authentique, livraison rapide.</strong></p>
"""
    
    return {
        'title': title, 'body_html': body,
        'tags': f'style, outfit, {subject}, look, mode, streetwear, {full_name}',
        'handle': f'comment-porter-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title, 'meta_description': meta_description,
        'summary_html': summary, 'needs_image': True, 'image_search_term': subject
    }

def generate_custom_article(subject, keywords, product_links, collection_link, tone):
    """Génère un article personnalisé enrichi avec SNEAKER_DATABASE"""
    data = get_sneaker_data(subject)
    full_name = data['full_name'] if data else subject
    
    title = f"{full_name} : Tout ce que vous devez savoir en 2026"
    meta_title = f"{full_name} : Guide complet 2026 | KP SHOES"[:70]
    meta_description = f"Tout savoir sur la {full_name}. Histoire, taille, style, entretien et où acheter authentique. Guide complet KP SHOES."[:160]
    summary = f"Tout ce qu'il faut savoir sur la {full_name}. Guide complet par les experts KP SHOES."
    
    if data:
        year = data.get('year', '')
        designer = data.get('designer', '')
        history = data.get('history', '')
        materials = ', '.join(data.get('materials', []))
        tech = data.get('technology', '')
        retail_price = data.get('retail_price', '')
        sizing = data.get('sizing', {})
        fit = sizing.get('fit', 'taille normalement')
        advice = sizing.get('advice', '')
        care = data.get('care', {})
        care_tips = care.get('tips', '')
        style_info = data.get('style', {})
        looks = style_info.get('looks', [])
        colorways = data.get('iconic_colorways', [])
        cultural = data.get('cultural_moments', [])
        brand = data.get('brand', '')
        
        body = f"""
<p>Découvrez tout ce qu'il faut savoir sur la <strong>{full_name}</strong>. Histoire, taille, style, entretien : notre guide complet pour devenir incollable sur ce modèle {'légendaire' if year and year < 2000 else 'incontournable'}.</p>

<h2>Fiche technique</h2>
<table style="width:100%;border-collapse:collapse;margin:20px 0">
<tr style="background:#f5f5f5"><td style="padding:10px;border:1px solid #ddd;font-weight:bold;width:35%">Nom complet</td><td style="padding:10px;border:1px solid #ddd">{full_name}</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;font-weight:bold">Marque</td><td style="padding:10px;border:1px solid #ddd">{brand}</td></tr>
<tr style="background:#f5f5f5"><td style="padding:10px;border:1px solid #ddd;font-weight:bold">Année de création</td><td style="padding:10px;border:1px solid #ddd">{year}</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;font-weight:bold">Designer</td><td style="padding:10px;border:1px solid #ddd">{designer}</td></tr>
<tr style="background:#f5f5f9"><td style="padding:10px;border:1px solid #ddd;font-weight:bold">Matériaux</td><td style="padding:10px;border:1px solid #ddd">{materials}</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;font-weight:bold">Technologie</td><td style="padding:10px;border:1px solid #ddd">{tech}</td></tr>
<tr style="background:#f5f5f5"><td style="padding:10px;border:1px solid #ddd;font-weight:bold">Prix retail</td><td style="padding:10px;border:1px solid #ddd">{retail_price}</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;font-weight:bold">Taille</td><td style="padding:10px;border:1px solid #ddd">{fit}</td></tr>
</table>

<h2>L'histoire de la {full_name}</h2>
<p>{history}</p>
"""
        
        if cultural:
            body += f"<h2>Les moments clés</h2><ul>"
            for c in cultural:
                body += f"<li>{c}</li>"
            body += "</ul>"
        
        if colorways:
            body += f"<h2>Les coloris iconiques</h2><ul>"
            for cw in colorways:
                body += f"<li><strong>{cw}</strong></li>"
            body += "</ul>"
        
        body += f"""
{collection_link}

<h2>Comment taille la {full_name} ?</h2>
<p>La {full_name} <strong>{fit}</strong>. {advice}</p>
<p>👉 Consultez notre <a href="https://{SITE_DOMAIN}/blogs/news/guide-taille-{subject.lower().replace(' ', '-')}">guide complet des tailles {full_name}</a> pour plus de détails.</p>
"""
        
        if looks:
            body += f"<h2>Comment la porter ?</h2><ul>"
            for look in looks:
                parts = look.split(' : ', 1)
                if len(parts) == 2:
                    body += f"<li><strong>{parts[0]}</strong> : {parts[1]}</li>"
                else:
                    body += f"<li>{look}</li>"
            body += "</ul>"
        
        if care_tips:
            body += f"""
<h2>Entretien</h2>
<p>{care_tips}</p>
"""
        
        body += f"""
<h2>Où acheter la {full_name} authentique ?</h2>
<p>Pour être sûr d'obtenir une paire authentique, privilégiez les revendeurs de confiance comme <strong>KP SHOES</strong>. Nous vérifions chaque paire avant expédition et garantissons l'authenticité à 100%.</p>

{product_links}

<p><strong>Faites confiance à KP SHOES pour vos sneakers authentiques. Livraison rapide et paiement sécurisé.</strong></p>
"""
    else:
        body = f"""
<p>Découvrez tout ce qu'il faut savoir sur <strong>{full_name}</strong>. Chez <strong>KP SHOES</strong>, nous vous proposons les meilleures paires 100% authentiques.</p>

<h2>Pourquoi choisir {full_name} ?</h2>
<p>{full_name} représente le meilleur de la culture sneaker. Que vous soyez collectionneur ou simplement à la recherche d'une paire de qualité, c'est un excellent choix.</p>

<h2>Où acheter {full_name} authentique ?</h2>
<p>Pour garantir l'authenticité, privilégiez <strong>KP SHOES</strong>. Nous vérifions chaque paire avant expédition.</p>

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
        'title': title, 'body_html': body,
        'tags': f'{subject}, sneakers, authentique, kp shoes, {full_name}',
        'handle': f'{subject.lower().replace(" ", "-")}-guide-2026',
        'meta_title': meta_title, 'meta_description': meta_description,
        'summary_html': summary, 'needs_image': True, 'image_search_term': subject
    }

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
        # Récupérer les produits et collections pour le maillage interne
        products = get_products_for_linking()
        collections = get_collections()
        
        # Générer le contenu
        article = generate_article_content(
            article_type, subject, keywords, tone, length,
            products, collections
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
