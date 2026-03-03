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
    
    # Récupérer media GID
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
    new_filename = f"{title_for_filename}_{product_id}_1.{ext}"
    
    # Exécuter le rename
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


def fix_product_images(product_id):
    """Corrige les images d'un produit : nom = Titre_Produit_N.ext, alt = titre produit
    Version optimisée : 1 GET + 1 PUT produit + 1 GraphQL batch = 3 appels max"""
    import time
    r = shopify_request(f'products/{product_id}.json')
    if not r or 'product' not in r:
        return {'success': False, 'error': 'Produit non trouvé'}
    
    product = r['product']
    title = product['title']
    images = product.get('images', [])
    
    if not images:
        return {'success': True, 'fixed': 0, 'total': 0, 'title': title}
    
    title_for_filename = title_to_filename(title)
    fixed = 0
    
    # ── 1. Alt text : batch via un seul PUT produit ──
    alt_updates = []
    needs_alt = False
    for i, img in enumerate(images):
        current_alt = img.get('alt', '') or ''
        if current_alt != title:
            needs_alt = True
        alt_updates.append({'id': img['id'], 'alt': title})
    
    if needs_alt:
        update_data = {'product': {'id': product_id, 'images': alt_updates}}
        result = shopify_request(f'products/{product_id}.json', 'PUT', update_data)
        if result:
            fixed += 1
            log.info(f"[ImageFix] {title}: alt text updated for all images")
    
    # ── 2. Filename : batch via un seul GraphQL fileUpdate ──
    # D'abord récupérer les media GIDs
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
    if gql_result and gql_result.get('data', {}).get('product', {}).get('media', {}).get('edges'):
        media_gids = [e['node']['id'] for e in gql_result['data']['product']['media']['edges']]
    
    # Préparer le batch de renommage
    files_to_rename = []
    for i, img in enumerate(images):
        if i >= len(media_gids):
            break
        current_src = img.get('src', '') or ''
        current_filename = current_src.split('/')[-1].split('?')[0] if current_src else ''
        
        if title_for_filename in current_filename:
            continue  # Déjà renommé
        
        ext = 'jpg'
        if '.' in current_filename:
            ext = current_filename.split('.')[-1].lower()
        
        new_filename = f"{title_for_filename}_{product_id}_{i+1}.{ext}"
        files_to_rename.append({"id": media_gids[i], "filename": new_filename})
    
    if files_to_rename:
        # Un seul appel GraphQL pour renommer TOUTES les images
        rename_query = """
        mutation fileUpdate($files: [FileUpdateInput!]!) {
            fileUpdate(files: $files) {
                files { id }
                userErrors { field message }
            }
        }
        """
        rename_result = shopify_graphql(rename_query, {"files": files_to_rename})
        rename_errors = []
        if rename_result and not rename_result.get('errors'):
            user_errors = rename_result.get('data', {}).get('fileUpdate', {}).get('userErrors', [])
            if not user_errors:
                fixed += len(files_to_rename)
                log.info(f"[ImageFix] {title}: {len(files_to_rename)} images renamed in batch")
            else:
                rename_errors = user_errors
                log.error(f"[ImageFix] {title}: rename errors: {user_errors}")
        else:
            rename_errors = rename_result.get('errors', []) if rename_result else [{'message': 'GraphQL call failed'}]
            log.error(f"[ImageFix] {title}: GraphQL error: {rename_result}")
        
        if rename_errors:
            return {'success': True, 'fixed': fixed, 'total': len(images), 'title': title, 
                    'rename_errors': rename_errors, 'attempted_filenames': [f['filename'] for f in files_to_rename]}
    
    time.sleep(0.2)  # Petit délai entre produits
    
    return {'success': True, 'fixed': fixed, 'total': len(images), 'title': title}


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
    
    # Récupérer media GIDs
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
        new_filename = f"{title_for_filename}_{product_id}_{i+1}.{ext}"
        
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
    import time
    
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


