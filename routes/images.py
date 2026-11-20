"""KP SHOES - Routes API Images"""
import time, logging
from flask import Blueprint, jsonify, request
from services.shopify import shopify_request, shopify_graphql
from services.image_manager import fix_product_images
from services.seo_engine import title_to_filename
log = logging.getLogger("kpshoes.image_routes")
images_bp = Blueprint("images", __name__)

@images_bp.route('/api/images/test-rename/<int:product_id>')
def api_test_rename(product_id):
    """Debug: teste le renommage de la première image d'un produit"""
    r = shopify_request(f'products/{product_id}.json')
    if not r or 'product' not in r:
        return jsonify({'error': 'Produit non trouvé'})
    
    product = r['product']
    title = product['title']
    images = product.get('images', [])
    title_for_filename = title_to_filename(title)
    
    if not images:
        return jsonify({'error': 'Pas d images'})
    
    gql_query = """
    query getProductMedia($id: ID!) {
        product(id: $id) {
            media(first: 5) {
                edges { node { id } }
            }
        }
    }
    """
    gql_result = shopify_graphql(gql_query, {"id": f"gid://shopify/Product/{product_id}"})
    
    if not gql_result or not gql_result.get('data', {}).get('product', {}).get('media', {}).get('edges'):
        return jsonify({'error': 'Pas de media GIDs', 'graphql_result': gql_result})
    
    media_gid = gql_result['data']['product']['media']['edges'][0]['node']['id']
    
    current_src = images[0].get('src', '')
    current_filename = current_src.split('/')[-1].split('?')[0] if current_src else ''
    ext = current_filename.split('.')[-1] if '.' in current_filename else 'jpg'
    new_filename = f"{title_for_filename}_1.{ext}"
    
    rename_query = """
    mutation fileUpdate($files: [FileUpdateInput!]!) {
        fileUpdate(files: $files) {
            files { id alt }
            userErrors { field message }
        }
    }
    """
    rename_vars = {"files": [{"id": media_gid, "filename": new_filename}]}
    rename_result = shopify_graphql(rename_query, rename_vars)
    
    return jsonify({
        'product': title,
        'media_gid': media_gid,
        'current_filename': current_filename,
        'new_filename': new_filename,
        'rename_result': rename_result
    })


@images_bp.route('/api/images/fix', methods=['POST'])
def api_fix_images():
    """Corrige les images d'un seul produit"""
    try:
        data = request.json
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({'success': False, 'error': 'product_id manquant'}), 400
        
        result = fix_product_images(product_id)
        return jsonify(result)
    except Exception as e:
        log.error(f"[ImageFix] Error on product: {e}")
        return jsonify({'success': False, 'fixed': 0, 'total': 0, 'error': str(e)})


@images_bp.route('/api/images/test/<int:product_id>')
def api_test_image_fix(product_id):
    """Debug: teste le fix d'images sur un produit et retourne les détails"""
    r = shopify_request(f'products/{product_id}.json')
    if not r or 'product' not in r:
        return jsonify({'error': 'Produit non trouvé'})
    
    product = r['product']
    title = product['title']
    handle = product['handle']
    images = product.get('images', [])
    title_for_filename = title_to_filename(title)
    
    gql_query = """
    query getProductMedia($id: ID!) {
        product(id: $id) {
            media(first: 50) {
                edges { node { id } }
            }
        }
    }
    """
    gql_result = shopify_graphql(gql_query, {"id": f"gid://shopify/Product/{product_id}"})
    media_gids = []
    gql_raw = gql_result
    if gql_result and gql_result.get('data', {}).get('product', {}).get('media', {}).get('edges'):
        media_gids = [e['node']['id'] for e in gql_result['data']['product']['media']['edges']]
    
    image_details = []
    for i, img in enumerate(images):
        current_src = img.get('src', '') or ''
        current_filename = current_src.split('/')[-1].split('?')[0] if current_src else ''
        ext = current_filename.split('.')[-1] if '.' in current_filename else 'jpg'
        new_filename = f"{title_for_filename}_{i+1}.{ext}"
        
        image_details.append({
            'index': i+1,
            'current_alt': img.get('alt', ''),
            'new_alt': title,
            'current_filename': current_filename,
            'new_filename': new_filename,
            'media_gid': media_gids[i] if i < len(media_gids) else 'NOT FOUND',
            'img_id': img['id']
        })
    
    return jsonify({
        'product': title,
        'handle': handle,
        'images_count': len(images),
        'media_gids_count': len(media_gids),
        'graphql_raw': gql_raw,
        'images': image_details
    })


@images_bp.route('/api/images/fix-all', methods=['POST'])
def api_fix_all_images():
    """Corrige les images de TOUS les produits via fix_product_images"""
    total_fixed = 0
    total_images = 0
    processed = 0
    since_id = 0
    
    for _ in range(20):
        r = shopify_request(f'products.json?limit=250&since_id={since_id}')
        if not r or 'products' not in r or not r['products']:
            break
        
        for product in r['products']:
            pid = product['id']
            result = fix_product_images(pid)
            if result.get('success'):
                total_fixed += result.get('fixed', 0)
                total_images += result.get('total', 0)
            processed += 1
            
            if processed % 10 == 0:
                log.info(f"[ImageFix] Progress: {processed} products, {total_fixed} fixed")
        
        since_id = r['products'][-1]['id']
        if len(r['products']) < 250:
            break
    
    log.info(f"[ImageFix] Done: {processed} products, {total_fixed}/{total_images} images fixed")
    
    return jsonify({
        'success': True,
        'processed': processed,
        'total_fixed': total_fixed,
        'total_images': total_images
    })


# ── Retrait des photos 2, 5 et 7 (sets GOAT de 8 photos ou plus) ──
# Ces vues font doublon (zoom profil, 2e semelle, talon seul). Le tag
# 'photos_257' marque une fiche deja nettoyee pour ne JAMAIS la retoucher
# (sinon une fiche a 12 photos -> 9 serait recoupee au passage suivant).
DROP_TAG = 'photos_257'


@images_bp.route('/api/images/drop-extra', methods=['POST'])
def api_drop_extra_photos():
    from services.goat_client import DROP_POSITIONS, DROP_MIN_SET
    data = request.get_json(silent=True) or {}
    product_id = data.get('product_id')
    dry_run = bool(data.get('dry_run'))
    if not product_id:
        return jsonify({'error': 'product_id requis'}), 400
    r = shopify_request(f'products/{product_id}.json?fields=id,title,tags,images')
    if not r or 'product' not in r:
        return jsonify({'error': 'Produit non trouve'}), 404
    product = r['product']
    tags = [t.strip() for t in (product.get('tags') or '').split(',') if t.strip()]
    images = sorted(product.get('images', []), key=lambda im: im.get('position', 0))
    if DROP_TAG in tags:
        return jsonify({'skipped': True, 'reason': 'deja nettoyee', 'count': len(images)})
    if len(images) < DROP_MIN_SET:
        return jsonify({'skipped': True, 'reason': f'{len(images)} photos (< {DROP_MIN_SET})', 'count': len(images)})
    to_drop = [im for i, im in enumerate(images, 1) if i in DROP_POSITIONS]
    if dry_run:
        return jsonify({'dry_run': True, 'count': len(images), 'would_remove': [im.get('src') for im in to_drop]})
    # Tag AVANT de supprimer : si le serveur coupe au milieu, la fiche ne sera
    # jamais recoupee au passage suivant (pas de risque de retirer une bonne photo).
    tags.append(DROP_TAG)
    if not shopify_request(f'products/{product_id}.json', 'PUT',
                           {'product': {'id': product_id, 'tags': ', '.join(tags)}}):
        return jsonify({'error': 'Impossible de poser le tag, rien supprime'}), 502
    removed = 0
    for im in to_drop:
        if shopify_request(f"products/{product_id}/images/{im['id']}.json", 'DELETE'):
            removed += 1
        time.sleep(0.3)
    after = shopify_request(f'products/{product_id}.json?fields=id,images')
    real = len(after['product'].get('images', [])) if after and 'product' in after else None
    log.info(f"[Drop257] product {product_id}: {len(images)} -> {real} (retirees {removed}/{len(to_drop)})")
    return jsonify({'success': removed == len(to_drop), 'removed': removed,
                    'before': len(images), 'after': real})
