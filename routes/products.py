"""
KP SHOES - Routes API produits
"""

from flask import Blueprint, jsonify, request
from services.shopify import shopify_request, get_collections, get_product_metafields
from services.seo_engine import analyze_seo

products_bp = Blueprint('products', __name__)


@products_bp.route('/api/products')
def api_products():
    since_id = request.args.get('since_id', '0')
    limit = request.args.get('limit', '250')
    fields = 'id,title,handle,vendor,product_type,tags,images,variants,body_html'
    r = shopify_request(f'products.json?limit={limit}&since_id={since_id}&fields={fields}')
    products = r.get('products', []) if r else []
    cols = get_collections() if since_id == '0' else []
    return jsonify({'products': products, 'collections': cols})


@products_bp.route('/api/product/<int:product_id>')
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
