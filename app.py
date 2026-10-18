"""
KP SHOES - Plateforme de Gestion Shopify V9
Architecture modulaire avec Blueprints Flask.

Structure:
    app.py          - Ce fichier (factory + entry point)
    config.py       - Configuration centralisee
    services/       - Logique metier
        shopify.py      - Client Shopify REST + GraphQL
        goat_client.py  - Client GOAT (Algolia + web-api)
        seo_engine.py   - Moteur SEO (analyse + generation)
        image_manager.py - Gestion images (resize, rename, alt)
    routes/         - Endpoints API (Blueprints)
        pages.py        - Pages HTML
        products.py     - API produits
        seo.py          - API SEO
        goat.py         - API GOAT images
        images.py       - API images (fix alt/filename)
        collections.py  - API collections
        competitor.py   - API competitor scanning
        price_tracker.py - API price drop tracker
    data/           - Donnees statiques
        descriptions.py     - Descriptions modeles/colorways
        collections_seo.py  - SEO des collections
        mappings.py         - Mappings collections <-> modeles
    templates/      - Templates HTML (separes du Python)
"""

import os
import sys
from flask import Flask


def create_app():
    """Factory Flask avec enregistrement des Blueprints."""
    app = Flask(__name__)

    # Enregistrer les Blueprints
    from routes.pages import pages_bp
    from routes.products import products_bp
    from routes.seo import seo_bp
    from routes.goat import goat_bp
    from routes.images import images_bp
    from routes.collections import collections_bp
    from routes.competitor import competitor_bp
    from routes.price_tracker import price_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(seo_bp)
    app.register_blueprint(goat_bp)
    app.register_blueprint(images_bp)
    app.register_blueprint(collections_bp)
    app.register_blueprint(competitor_bp)
    app.register_blueprint(price_bp)

    @app.route('/health')
    def health():
        """Ping de maintien en eveil (cron-job.org) : public, leger, n'expose rien."""
        return 'ok', 200, {'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store'}

    _install_password_protection(app)
    return app


# Routes laissees accessibles sans mot de passe : celles appelees par le cron
# du price tracker (qui a deja sa propre protection par CRON_TOKEN) et deux
# routes de lecture seule.
_PUBLIC_PATHS = ('/health', '/api/price/run', '/api/price/status', '/api/price/last-run')


def _install_password_protection(app):
    """Protege toute l'app par mot de passe (HTTP Basic).

    Inactif tant que la variable d'environnement APP_PASSWORD n'est pas definie
    -> aucun risque de se bloquer en deployant. Une fois definie, le navigateur
    demande l'identifiant une seule fois puis le renvoie automatiquement pour
    toutes les pages et appels de l'app (n'importe quel nom d'utilisateur,
    seul le mot de passe compte).
    """
    import hmac
    from flask import request, Response

    @app.before_request
    def _require_password():
        password = os.environ.get('APP_PASSWORD', '')
        if not password or request.path in _PUBLIC_PATHS:
            return None
        auth = request.authorization
        if auth and auth.password and hmac.compare_digest(
                auth.password.encode('utf-8'), password.encode('utf-8')):
            return None
        return Response('Acces reserve.', 401,
                        {'WWW-Authenticate': 'Basic realm="KP SHOES", charset="UTF-8"'})


# Instance au niveau module pour Render (gunicorn app:app fonctionne directement)
app = create_app()

# ══════════════════════════════════════════════════════════════
# IMAGE SCANNER - Détection de nouvelles images GOAT
# ══════════════════════════════════════════════════════════════

import time, re, logging
from flask import jsonify, request
from services.shopify import shopify_request
from services.goat_client import get_images as get_goat_images

log = logging.getLogger("kpshoes.image_scanner")


@app.route('/api/products/single-image-page')
def api_products_single_image_page():
    """Récupère UNE page de produits (250 max) et filtre selon le nombre d'images.
    Sneakers: < 5 images. Vêtements: 1 seule image. Lunettes: exclues."""
    since_id = request.args.get('since_id', '0')
    r = shopify_request(f'products.json?limit=250&since_id={since_id}&fields=id,title,handle,images,variants')
    if not r or not r.get('products'):
        return jsonify({'products': [], 'has_more': False, 'next_since_id': '0', 'page_total': 0})

    products = r['products']
    filtered = []
    clothing_kw = ['hoodie', 'sweatshirt', 'sweatpant', 'tee ', 't-shirt', 'crewneck', 'jacket',
                   'pants', 'pant ', 'shorts', 'short ', 'polo', 'jersey', 'vest ', 'pullover',
                   'fleece', 'bomber', 'balaclava', 'anorak', 'puffer']

    for p in products:
        img_count = len(p.get('images', []))
        if img_count == 0:
            continue
        title_lower = p['title'].lower()
        # Exclure lunettes
        if 'lunette' in title_lower or 'sunglasses' in title_lower or 'glasses' in title_lower:
            continue
        # Vêtements : seulement si 1 image
        is_clothing = any(kw in title_lower for kw in clothing_kw)
        if is_clothing and img_count != 1:
            continue
        # Sneakers : seulement si < 5 images
        if not is_clothing and img_count >= 5:
            continue

        sku = p['variants'][0].get('sku', '') if p.get('variants') else ''
        filtered.append({
            'id': p['id'],
            'title': p['title'],
            'handle': p.get('handle', ''),
            'sku': sku,
            'image_url': p['images'][0]['src'] if p.get('images') else '',
            'image_count': img_count,
        })

    has_more = len(products) >= 250
    next_id = str(products[-1]['id']) if products else '0'

    return jsonify({
        'products': filtered,
        'page_total': len(products),
        'has_more': has_more,
        'next_since_id': next_id,
    })


@app.route('/api/goat/check-new-images')
def api_goat_check_new_images():
    """Vérifie si GOAT a plus d'images disponibles pour un SKU donné."""
    sku = request.args.get('sku', '').strip()
    title = request.args.get('title', '').strip()
    if not sku:
        return jsonify({'error': 'SKU requis'}), 400

    # Les objets de collection ne sont pas sur GOAT : on ne cherche pas
    from services.seo_engine import is_collectible
    if title and is_collectible(title):
        return jsonify({'sku': sku, 'goat_found': False, 'goat_images': 0,
                        'images': [], 'collectible': True})

    sku_clean = re.sub(r':\d+$', '', sku)
    result = get_goat_images(sku_clean)

    if not result or not result.get('images'):
        return jsonify({'sku': sku, 'goat_found': False, 'goat_images': 0, 'images': []})

    images = result.get('images', [])
    # "Nouvelles photos" = GOAT en propose PLUS que la fiche n'en a deja.
    # (Avant : on comparait a 1, donc une fiche a 2 photos pour laquelle GOAT
    # n'en a que 2 etait annoncee a tort comme ayant de nouvelles photos.)
    try:
        current = int(request.args.get('current', '1') or 1)
    except ValueError:
        current = 1
    return jsonify({
        'sku': sku,
        'goat_found': True,
        'goat_name': result.get('name', ''),
        'goat_images': len(images),
        'current_images': current,
        'images': images,
        'has_new': len(images) > current
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
