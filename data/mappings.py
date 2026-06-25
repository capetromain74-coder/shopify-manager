"""
KP SHOES - Mappings collections <-> modeles, extraction marques
Handles = vrais handles Shopify (verifies via API le 2026-06-25)
"""
MODEL_COLLECTIONS = {
    'jordan-4': ['jordan 4'], 'jordan-1-high': ['jordan 1 high'], 'jordan-1-low': ['jordan 1 low'],
    'jordan-1-mid': ['jordan 1 mid'],
    # nike-sb AVANT nike-dunk : un "Nike SB Dunk" doit pointer vers la collection SB, pas Dunk
    'nike-sb': ['sb dunk', 'nike sb'],
    'nike-dunk': ['dunk'], 'air-force-1': ['air force 1'],
    'air-max': ['air max'], 'nike-vomero': ['vomero'], 'nike-sacai': ['sacai'],
    'adidas-samba': ['samba'], 'adidas-campus': ['campus'], 'adidas-gazelle': ['gazelle'],
    'adidas-spezial': ['spezial'], 'adidas-forum': ['forum'], 'adidas-superstar': ['superstar'],
    'yeezy-slide': ['yeezy slide'],
    'yeezy-350': ['yeezy 350', '350 v2'], 'yeezy-700': ['yeezy 700', '700 v3'],
    'new-balance-550': ['550'], 'new-balance-530': ['530'], 'new-balance-2002r': ['2002r'],
    'new-balance-9060': ['9060'], 'new-balance-740': ['new balance 740'],
    'asics-gel-1130': ['gel-1130', 'gel 1130'],
    'asics-gel-kayano': ['kayano'], 'asics-gel-nyc': ['gel-nyc', 'gel nyc'],
    'ugg-tasman': ['tasman'], 'ugg-tazz': ['tazz'], 'ugg-ultra-mini': ['ultra mini'],
    'ugg-classic-mini': ['classic mini'], 'ugg-lowmel': ['lowmel'],
    'travis-scott': ['travis scott'], 'off-white': ['off-white'], 'supreme': ['supreme'],
    'streetwear': ['essentials', 'hoodie', 'sweatshirt', 'sweater', 'sweatpant', 'sweatshort', 'tee ', 't-shirt', 'crewneck', 'jacket', 'pants', 'pant ', 'short ', 'shorts', 'polo', 'jersey', 'vest ', 'pullover', 'anorak', 'puffer', 'fleece', 'bomber', 'balaclava'],
}
BRAND_COLLECTIONS = {
    'air-jordan': ['jordan'], 'nike': ['nike', 'nocta', 'blazer'], 'adidas': ['adidas'],
    'yeezy': ['yeezy', 'foam runner'], 'new-balance': ['new balance'], 'asics': ['asics'],
    'ugg': ['ugg'], 'puma': ['puma'], 'crocs': ['crocs'], 'birkenstock': ['birkenstock'],
    'converse': ['converse'], 'salomon': ['salomon'], 'timberland': ['timberland'],
    'maison-mihara': ['mihara', 'mmy', 'maison mihara'], 'vans': ['vans'],
    'saucony': ['saucony'], 'patta': ['patta'], 'the-north-face': ['north face'],
    'bape': ['bape', 'bathing ape'], 'dior': ['dior'], 'denim-tears': ['denim tears'],
    'fear-of-god': ['fear of god', 'essentials'],
}
EXCLUDED = ['tout-nos-modeles', 'meilleures-ventes', 'moins-de-150', 'livraison-48h', 'pour-enfants', 'sport', 'autre-marques', 'accessoires', 'nouveautes', 'sneakers', 'stock-x-sneakers']
