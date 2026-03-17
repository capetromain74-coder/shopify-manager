"""KP SHOES - Routes API Collections"""
import time
from flask import Blueprint, jsonify, request
from services.shopify import shopify_request, get_collections
from data.collections_seo import COLLECTION_SEO
from services.seo_engine import update_seo_field

collections_bp = Blueprint('collections', __name__)


def get_collection_seo(handle):
    return COLLECTION_SEO.get(handle, None)


def update_collection_seo(collection_id, handle):
    seo = get_collection_seo(handle)
    if not seo:
        return False
    for ctype in ['custom_collections', 'smart_collections']:
        singular = ctype.rstrip('s')
        r = shopify_request(f'{ctype}/{collection_id}.json')
        if r and singular in r:
            update_data = {singular: {
                'id': collection_id,
                'body_html': seo['description'],
            }}
            shopify_request(f'{ctype}/{collection_id}.json', 'PUT', update_data)
            time.sleep(0.3)
            shopify_request(f'collections/{collection_id}/metafields.json', 'POST',
                {'metafield': {'namespace': 'global', 'key': 'title_tag', 'value': seo['meta_title'], 'type': 'single_line_text_field'}})
            time.sleep(0.3)
            shopify_request(f'collections/{collection_id}/metafields.json', 'POST',
                {'metafield': {'namespace': 'global', 'key': 'description_tag', 'value': seo['meta_description'], 'type': 'single_line_text_field'}})
            return True
    return False


@collections_bp.route('/api/collections')
def api_collections():
    cols = get_collections()
    for c in cols:
        seo_def = get_collection_seo(c['handle'])
        c['has_seo_def'] = seo_def is not None  # SEO défini dans le code
        if seo_def:
            c['seo'] = seo_def
        else:
            c['seo'] = {'meta_title': '', 'meta_description': '', 'description': ''}
        
        # Vérifier le SEO réellement appliqué sur Shopify
        score = 0
        checks = {'meta_title': False, 'meta_description': False, 'body_html': False}
        
        # Chercher les metafields pour meta_title et meta_description
        try:
            mf = shopify_request(f'collections/{c["id"]}/metafields.json')
            if mf and 'metafields' in mf:
                for m in mf['metafields']:
                    if m.get('key') == 'title_tag' and m.get('value'):
                        checks['meta_title'] = True
                        c['live_meta_title'] = m['value']
                        score += 35
                    if m.get('key') == 'description_tag' and m.get('value'):
                        checks['meta_description'] = True
                        c['live_meta_description'] = m['value']
                        score += 35
        except:
            pass
        
        # Vérifier body_html sur la collection
        try:
            for ctype in ['custom_collections', 'smart_collections']:
                singular = ctype.rstrip('s')
                r = shopify_request(f'{ctype}/{c["id"]}.json')
                if r and singular in r:
                    body = r[singular].get('body_html', '') or ''
                    if len(body) > 50:
                        checks['body_html'] = True
                        score += 30
                    break
        except:
            pass
        
        c['score'] = score
        c['checks'] = checks
        c['has_seo_applied'] = score >= 70
        time.sleep(0.2)  # Rate limit Shopify
    
    return jsonify({'collections': cols, 'count': len(cols)})


@collections_bp.route('/api/collections/<int:cid>/seo', methods=['POST'])
def api_apply_collection_seo(cid):
    cols = get_collections()
    col = next((c for c in cols if c['id'] == cid), None)
    if not col:
        return jsonify({'error': 'Collection non trouvee'}), 404
    success = update_collection_seo(cid, col['handle'])
    if success:
        return jsonify({'success': True, 'handle': col['handle']})
    return jsonify({'error': 'Pas de SEO defini pour cette collection'}), 400


@collections_bp.route('/api/collections/batch-seo', methods=['POST'])
def api_batch_collection_seo():
    cols = get_collections()
    updated = []
    errors = []
    for c in cols:
        seo = get_collection_seo(c['handle'])
        if seo:
            try:
                update_collection_seo(c['id'], c['handle'])
                updated.append(c['handle'])
                time.sleep(0.5)
            except Exception as e:
                errors.append({'handle': c['handle'], 'error': str(e)})
    return jsonify({'success': True, 'updated': updated, 'errors': errors, 'count': len(updated)})
