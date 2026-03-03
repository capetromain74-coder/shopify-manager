"""
KP SHOES - Configuration centralisée
Toutes les variables d'environnement et constantes sont ici.
"""

import os
import logging

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger('kpshoes')

# ── Shopify ──
SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'

# ── Site ──
SITE_NAME = os.environ.get('SITE_NAME', 'KP SHOES')
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'kpshoes.fr')

# ── GOAT (clés Algolia publiques, mais mieux en env vars) ──
GOAT_ALGOLIA_URL = os.environ.get(
    'GOAT_ALGOLIA_URL',
    'https://2fwotdvm2o-dsn.algolia.net/1/indexes/*/queries'
)
GOAT_ALGOLIA_APP_ID = os.environ.get('GOAT_ALGOLIA_APP_ID', '2FWOTDVM2O')
GOAT_ALGOLIA_API_KEY = os.environ.get('GOAT_ALGOLIA_API_KEY', 'ac96de6fef0e02bb95d433d8d5c7038a')
GOAT_PRODUCT_API = os.environ.get(
    'GOAT_PRODUCT_API',
    'https://www.goat.com/web-api/v1/product_templates'
)

# ── GOAT TLS profiles pour rotation anti-Cloudflare ──
GOAT_TLS_PROFILES = ["chrome", "chrome110", "chrome116", "safari", "safari_ios"]

# ── Cache TTL (secondes) ──
COLLECTIONS_CACHE_TTL = int(os.environ.get('COLLECTIONS_CACHE_TTL', '300'))  # 5 min
GOAT_SESSION_TTL = 60  # Renouveler la session GOAT toutes les 60s

# ── Rate limiting Shopify (ms entre requêtes) ──
SHOPIFY_REQUEST_DELAY = 0.3

# ── Image resize ──
GOAT_CANVAS_WIDTH = 750
GOAT_CANVAS_HEIGHT = 500
