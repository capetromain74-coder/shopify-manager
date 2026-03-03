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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
