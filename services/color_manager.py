"""
KP SHOES - Couleur automatique des produits.

Remplit l'attribut de categorie Shopify `shopify.color-pattern` (celui qui
alimente le filtre "Couleur" de la boutique) a partir des couleurs DEJA
definies dans la boutique (metaobjets `shopify--color-pattern`). On n'en cree
jamais de nouvelles.

Regles :
- source 1 : les mots de couleur du TITRE (le plus fiable) ;
- source 2 : la couleur GOAT, uniquement si le SKU GOAT correspond EXACTEMENT
  (GOAT renvoie sinon un produit sans rapport) ;
- aucune couleur trouvee -> on ne touche a rien (on n'invente pas) ;
- par defaut on ne remplit que les fiches SANS couleur (overwrite=False) ;
- Shopify refuse la couleur si le produit n'a pas de categorie : on pose alors
  une categorie deduite du titre (jamais d'ecrasement d'une categorie existante) ;
- les objets de collection sont ignores (pas de couleur pertinente).
"""

import re
import json
import time
import logging

from services.shopify import shopify_graphql

log = logging.getLogger('kpshoes.color')

# ── Categories de la taxonomie Shopify (posees uniquement si absentes) ──────
_TAX = 'gid://shopify/TaxonomyCategory/'
CATEGORY_NAMES = {
    'aa-8-8': 'Baskets', 'aa-8-3': 'Bottes', 'aa-8-6': 'Sandales', 'aa-8-7': 'Chaussons',
    'aa-1-13-8': 'T-shirts', 'aa-1-13-13': 'Sweats à capuche', 'aa-1-13-14': 'Sweat-shirts',
    'aa-1-13-12': 'Pulls', 'aa-1-13-6': 'Polos', 'aa-1-13-7': 'Chemises',
    'aa-1-13-9': 'Débardeurs', 'aa-1-10-2': 'Manteaux et vestes',
    'aa-1-10-6': 'Gilets et vestes sans manches', 'aa-1-12': 'Pantalons',
    'aa-1-14': 'Shorts', 'aa-2-17': 'Chapeaux', 'aa-2-3': 'Passe-montagnes',
}
# Vetements : premier motif qui correspond gagne (ordre = du plus precis au plus large)
_CLOTHING_RULES = [
    (r'balaclava|passe[- ]montagne', 'aa-2-3'),
    (r'\bbeanie\b|\bbonnet\b|\bcap\b|casquette|\bhat\b|bucket', 'aa-2-17'),
    (r'hoodie|sweat [àa] capuche|zip hood', 'aa-1-13-13'),
    (r'crewneck|sweatshirt|half zip|quarter zip|full zip', 'aa-1-13-14'),
    (r'tank top|d[ée]bardeur', 'aa-1-13-9'),
    (r'\bpolo\b', 'aa-1-13-6'),
    (r'overshirt|work ?shirt|chemise', 'aa-1-13-7'),
    (r'\bvest\b|gilet', 'aa-1-10-6'),
    (r'jacket|coat\b|puffer|parka|anorak|windbreaker|bomber|varsity|fleece|doudoune|veste', 'aa-1-10-2'),
    (r'sweater|\bpull\b|cardigan|knit', 'aa-1-13-12'),
    (r'short', 'aa-1-14'),
    (r'pant|jogger|trouser|cargo|jean', 'aa-1-12'),
    (r't-shirt|\btee\b|longsleeve|long sleeve|jersey', 'aa-1-13-8'),
]
# Chaussures : par defaut "Baskets"
_FOOTWEAR_RULES = [
    (r'\bboots?\b|botte|6-inch', 'aa-8-3'),
    (r'slipper|chausson|tasman|tazz', 'aa-8-7'),
    (r'slide|sandal|claquette|\bmule|clog|sabot|crocs|birkenstock|arizona', 'aa-8-6'),
]


def guess_category(title):
    """Categorie Shopify deduite du titre (handle court, ex. 'aa-8-8')."""
    from services.seo_engine import is_clothing
    t = (title or '').lower()
    if is_clothing(title):
        for pattern, cat in _CLOTHING_RULES:
            if re.search(pattern, t):
                return cat
        return None  # vetement non reconnu : on prefere ne rien poser
    for pattern, cat in _FOOTWEAR_RULES:
        if re.search(pattern, t):
            return cat
    return 'aa-8-8'


# ── Mots de couleur -> handle des couleurs de la boutique ───────────────────
# Les expressions de plusieurs mots passent avant les mots seuls.
_NICKNAMES = {  # surnoms sneakers sans mot de couleur explicite
    'reverse panda': ['noir', 'blanc'], 'panda': ['noir', 'blanc'],
    'bred': ['noir', 'rouge'], 'triple black': ['noir'], 'triple white': ['blanc'],
}
_COLOR_WORDS = [
    # bleus
    (r'navy|marine|obsidian', 'marine'),
    (r'blue|bleu|royal|cobalt|aqua|turquoise|teal|\bsky\b', 'bleu'),
    # noirs / gris
    (r'black|noir|onyx', 'noir'),
    (r'grey|gray|gris|cement|\bfog\b|smoke|pewter|graphite|charcoal|anthracite|\bash\b', 'gris'),
    # clairs
    (r'white|blanc', 'blanc'),
    (r'beige|cream|\bsail\b|\bbone\b|ivory|khaki|\btan\b|\bsand\b|oatmeal|wheat|alabaster|vanilla|taupe', 'beige'),
    # chauds
    (r'\bred\b|rouge|crimson|burgundy|maroon|cherry|scarlet|bordeaux', 'rouge'),
    (r'pink|\brose\b|fuchsia|magenta|salmon', 'rose'),
    (r'orange', 'orange'),
    (r'yellow|jaune', 'jaune'),
    (r'brown|marron|mocha|chocolate|cacao|chestnut|coffee|espresso|cognac', 'marron'),
    # autres
    (r'green|vert|olive|\bmint\b|\bsage\b|emerald|\blime\b|forest|\bpine\b|\bjade\b', 'vert'),
    (r'purple|violet|lilac|lavender|\bplum\b|grape', 'violet'),
    (r'silver|argent|chrome', 'argent'),
    (r'\bgold\b|dor[ée]', 'dore'),
    (r'multi[- ]?colou?r|multicolore|rainbow|what the', 'multicolore'),
    (r'\bcamo\b|camouflage', 'camouflage'),
    (r'l[ée]opard', 'leopard'),
    (r'python|snake', 'animal'),
]
MAX_COLORS = 3


def detect_colors(text):
    """Liste ordonnee (max 3) des handles de couleur trouves dans un texte."""
    t = ' ' + (text or '').lower() + ' '
    # la marque Off-White n'est pas une couleur
    t = re.sub(r'off[- ]white', ' ', t)
    found = []  # (position, handle)
    for nick, handles in _NICKNAMES.items():
        m = re.search(r'\b' + re.escape(nick) + r'\b', t)
        if m:
            for i, h in enumerate(handles):
                found.append((m.start() + i * 0.01, h))  # garde l'ordre du surnom
            t = t[:m.start()] + ' ' * len(nick) + t[m.end():]
    for pattern, handle in _COLOR_WORDS:
        for m in re.finditer(pattern, t):
            found.append((m.start(), handle))
    found.sort()
    result = []
    for _, h in found:
        if h not in result:
            result.append(h)
    return result[:MAX_COLORS]


# ── Couleurs existantes dans la boutique (cache 1 h) ────────────────────────
_SWATCH_CACHE = {'map': None, 'ts': 0}


def get_store_colors():
    """{handle: gid} des couleurs definies dans la boutique."""
    if _SWATCH_CACHE['map'] and time.time() - _SWATCH_CACHE['ts'] < 3600:
        return _SWATCH_CACHE['map']
    q = """query($after: String) {
      metaobjects(type: "shopify--color-pattern", first: 100, after: $after) {
        edges { node { id handle } }
        pageInfo { hasNextPage endCursor }
      }
    }"""
    colors, after = {}, None
    for _ in range(10):
        r = shopify_graphql(q, {'after': after})
        data = (((r or {}).get('data') or {}).get('metaobjects') or {})
        for e in data.get('edges', []):
            colors[e['node']['handle']] = e['node']['id']
        if not (data.get('pageInfo') or {}).get('hasNextPage'):
            break
        after = data['pageInfo']['endCursor']
    if colors:
        _SWATCH_CACHE.update(map=colors, ts=time.time())
    return colors


def _norm_sku(s):
    return re.sub(r'[\s\-_]', '', (s or '').upper())


def goat_colors(sku):
    """Couleur(s) GOAT, uniquement si le produit GOAT a EXACTEMENT ce SKU."""
    if not sku:
        return []
    try:
        from services.goat_client import search as goat_search, get_product_details
        product = goat_search(sku)
        if not product or _norm_sku(product.get('sku')) != _norm_sku(sku):
            return []  # pas de correspondance exacte : on ne prend pas le risque
        details = get_product_details(product['slug']) or {}
        return detect_colors(details.get('color', ''))
    except Exception as e:
        log.warning(f"[Color] GOAT indisponible pour {sku}: {e}")
        return []


# ── Application sur un produit ───────────────────────────────────────────────
def apply_color(product_id, overwrite=False):
    """Pose la couleur (et la categorie si absente). Retourne un dict de statut."""
    from services.seo_engine import is_collectible

    gid = f'gid://shopify/Product/{product_id}'
    r = shopify_graphql("""query($id: ID!) {
      product(id: $id) {
        title
        category { id name }
        variants(first: 1) { edges { node { sku } } }
        color: metafield(namespace: "shopify", key: "color-pattern") { value }
      }
    }""", {'id': gid})
    p = (((r or {}).get('data') or {}).get('product'))
    if not p:
        return {'status': 'error', 'message': 'Produit introuvable'}

    title = p.get('title', '')
    if is_collectible(title):
        return {'status': 'skipped', 'reason': 'objet de collection'}
    if p.get('color') and p['color'].get('value') not in (None, '', '[]') and not overwrite:
        return {'status': 'skipped', 'reason': 'couleur deja renseignee'}

    # 1) titre, 2) GOAT (SKU exact)
    handles = detect_colors(title)
    source = 'titre'
    if not handles:
        edges = (p.get('variants') or {}).get('edges') or []
        sku = edges[0]['node'].get('sku', '') if edges else ''
        handles = goat_colors(sku)
        source = 'GOAT'
    if not handles:
        return {'status': 'skipped', 'reason': 'aucune couleur identifiable'}

    store = get_store_colors()
    gids = [store[h] for h in handles if h in store]
    labels = [h for h in handles if h in store]
    if not gids:
        return {'status': 'skipped', 'reason': 'couleur(s) absente(s) de la boutique: ' + ', '.join(handles)}

    # Shopify exige une categorie pour accepter la couleur
    category_set = None
    if not p.get('category'):
        cat = guess_category(title)
        if not cat:
            return {'status': 'skipped', 'reason': 'categorie impossible a determiner'}
        u = shopify_graphql("""mutation($id: ID!, $cat: ID!) {
          productUpdate(product: {id: $id, category: $cat}) { userErrors { message } }
        }""", {'id': gid, 'cat': _TAX + cat})
        errs = ((((u or {}).get('data') or {}).get('productUpdate') or {}).get('userErrors')) or []
        if errs or not u:
            return {'status': 'error', 'message': 'categorie refusee: ' + str(errs)}
        category_set = CATEGORY_NAMES.get(cat, cat)

    m = shopify_graphql("""mutation($mf: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $mf) { userErrors { message code } }
    }""", {'mf': [{
        'ownerId': gid, 'namespace': 'shopify', 'key': 'color-pattern',
        'type': 'list.metaobject_reference', 'value': json.dumps(gids),
    }]})
    errs = ((((m or {}).get('data') or {}).get('metafieldsSet') or {}).get('userErrors')) or []
    if errs or not m:
        return {'status': 'error', 'message': 'couleur refusee: ' + str(errs)}

    log.info(f"[Color] {title}: {labels} (source {source})" +
             (f", categorie posee: {category_set}" if category_set else ''))
    return {'status': 'ok', 'colors': labels, 'source': source, 'category_set': category_set}
