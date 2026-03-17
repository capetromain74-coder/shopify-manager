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
        blog_generator.py - Generation articles de blog
        web_research.py   - Recherche web pour blog
    routes/         - Endpoints API (Blueprints)
        pages.py        - Pages HTML
        products.py     - API produits
        seo.py          - API SEO
        goat.py         - API GOAT images
        images.py       - API images (fix alt/filename)
        collections.py  - API collections
        blog.py         - API blog
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
    from routes.blog import blog_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(seo_bp)
    app.register_blueprint(goat_bp)
    app.register_blueprint(images_bp)
    app.register_blueprint(collections_bp)
    app.register_blueprint(blog_bp)

    return app


# Instance au niveau module pour Render (gunicorn app:app fonctionne directement)
app = create_app()

# ══════════════════════════════════════════════════════════════
# IMAGE SCANNER - Détection de nouvelles images GOAT
# Ajouter ce code dans app.py, avant le if __name__ == '__main__'
# ══════════════════════════════════════════════════════════════

@app.route('/image-scanner')
def image_scanner_page():
    return open('templates/image_scanner.html').read()


@app.route('/api/products/single-image')
def api_products_single_image():
    """Récupère tous les produits avec 1 seule image."""
    since_id = 0
    single_image_products = []
    total_scanned = 0

    while True:
        r = shopify_request(f'products.json?limit=250&since_id={since_id}&fields=id,title,handle,images,variants')
        if not r or not r.get('products'):
            break
        products = r['products']
        total_scanned += len(products)

        for p in products:
            img_count = len(p.get('images', []))
            if img_count == 1:
                sku = p['variants'][0].get('sku', '') if p.get('variants') else ''
                single_image_products.append({
                    'id': p['id'],
                    'title': p['title'],
                    'handle': p.get('handle', ''),
                    'sku': sku,
                    'image_url': p['images'][0]['src'] if p.get('images') else '',
                })

        if len(products) < 250:
            break
        since_id = products[-1]['id']
        time.sleep(0.5)

    log.info(f"[Image Scanner] Scanned {total_scanned} products, found {len(single_image_products)} with 1 image")
    return jsonify({
        'products': single_image_products,
        'count': len(single_image_products),
        'total_scanned': total_scanned
    })


@app.route('/api/goat/check-new-images')
def api_goat_check_new_images():
    """Vérifie si GOAT a plus d'images disponibles pour un SKU donné."""
    sku = request.args.get('sku', '').strip()
    title = request.args.get('title', '').strip()
    if not sku:
        return jsonify({'error': 'SKU requis'}), 400

    sku_clean = re.sub(r':\d+$', '', sku)
    result = get_goat_images(sku_clean)

    if not result or not result.get('images'):
        return jsonify({
            'sku': sku,
            'goat_found': False,
            'goat_images': 0,
            'images': []
        })

    images = result.get('images', [])
    return jsonify({
        'sku': sku,
        'goat_found': True,
        'goat_name': result.get('name', ''),
        'goat_images': len(images),
        'images': images,
        'has_new': len(images) > 1
    })
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
