"""
KP SHOES - Mappings collections <-> modeles, extraction marques
Handles = vrais handles Shopify (vérifiés via API)
"""
MODEL_COLLECTIONS = {
    'jordan-4': ['jordan 4'], 'jordan-1-high': ['jordan 1 high'], 'jordan-1-low': ['jordan 1 low'],
    'jordan-1-mid': ['jordan 1 mid'], 'nike-dunk': ['dunk'], 'air-force-1': ['air force 1'],
    'air-max': ['air max'], 'nike-vomero': ['vomero'], 'nike-sacai': ['sacai'],
    'adidas-samba': ['samba'], 'adidas-campus': ['campus'], 'adidas-gazelle': ['gazelle'],
    'adidas-spezial': ['spezial'], 'adidas-forum': ['forum'], 'adidas-superstar': ['superstar'],
    'yeezy-slide': ['yeezy slide'],
    'yeezy-350': ['yeezy 350', '350 v2'], 'yeezy-700': ['yeezy 700', '700 v3'],
    'new-balance-550': ['550'], 'new-balance-530': ['530'], 'new-balance-2002r': ['2002r'],
    'new-balance-9060': ['9060'], 'asics-gel-1130': ['gel-1130', 'gel 1130'],
    'asics-gel-kayano': ['kayano'], 'asics-gel-nyc': ['gel-nyc', 'gel nyc'],
    'ugg-tasman': ['tasman'], 'ugg-tazz': ['tazz'], 'ugg-ultra-mini': ['ultra mini'],
    'travis-scott': ['travis scott'], 'off-white': ['off-white'], 'supreme': ['supreme'],
    'streetwear': ['essentials', 'hoodie', 'sweatshirt', 'sweater', 'sweatpant', 'sweatshort', 'tee ', 't-shirt', 'crewneck', 'jacket', 'pants', 'pant ', 'short ', 'shorts', 'polo', 'jersey', 'vest ', 'pullover', 'anorak', 'puffer', 'fleece', 'bomber', 'balaclava'],
}
BRAND_COLLECTIONS = {
    'air-jordan': ['jordan'], 'nike-1': ['nike', 'nocta', 'blazer'], 'adidas-1': ['adidas'],
    'yeezy-1': ['yeezy', 'foam runner'], 'new-balance-1': ['new balance'], 'asics': ['asics'],
    'ugg-1': ['ugg'], 'puma-1': ['puma'], 'crocs': ['crocs'], 'birkenstock-1': ['birkenstock'],
    'converse': ['converse'], 'salomon': ['salomon'], 'timberland': ['timberland'],
    'maison-mihara': ['mihara', 'mmy', 'maison mihara'], 'vans': ['vans'],
}
EXCLUDED = ['tout-nos-modeles', 'meilleures-ventes', 'moins-de-150', 'livraison-48h', 'pour-enfants', 'sport', 'autre-marques', 'accessoires', 'nouveautes', 'sneakers', 'stock-x-sneakers']
