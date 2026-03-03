"""
KP SHOES - Routes pages HTML
Sert les templates pour la SPA.
"""

import os
from flask import Blueprint

pages_bp = Blueprint('pages', __name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')


def _read_template(filename):
    path = os.path.join(TEMPLATE_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


@pages_bp.route('/')
def home():
    return _read_template('home.html')


@pages_bp.route('/collections')
def collections_page():
    return _read_template('collections.html')


@pages_bp.route('/blog-generator')
def blog_generator():
    from services.shopify import shopify_request
    from config import SITE_DOMAIN
    r = shopify_request('blogs.json')
    blog_id = 0
    if r and r.get('blogs'):
        blog_id = r['blogs'][0]['id']
    html = _read_template('blog_generator.html')
    html = html.replace('BLOG_ID_PLACEHOLDER', str(blog_id))
    html = html.replace('DOMAIN_PLACEHOLDER', SITE_DOMAIN)
    return html


@pages_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    from config import SHOP
    html = _read_template('product.html')
    html = html.replace('PRODUCT_ID_PLACEHOLDER', str(product_id))
    html = html.replace('SHOP_PLACEHOLDER', SHOP)
    return html
