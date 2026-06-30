"""
KP SHOES - Gestionnaire d'images
Resize GOAT, renommage fichiers, correction alt text.
"""

import re
import time
import logging

from config import GOAT_CANVAS_WIDTH, GOAT_CANVAS_HEIGHT
from services.shopify import shopify_request, shopify_graphql
from services.seo_engine import title_to_filename
from services.goat_client import _get_session as _get_goat_session

log = logging.getLogger('kpshoes.images')


def _resize_goat_image_to_750x500(image_url):
    """Télécharge une image GOAT et la place centrée sur un canvas 750x500 fond blanc.
    Retourne le base64 PNG pour envoi à Shopify, ou None en cas d'erreur."""
    try:
        from PIL import Image
        from io import BytesIO
        import base64
        log.info(f"[GOAT Resize] Starting resize for: {image_url[:80]}...")
    except ImportError:
        log.error("[GOAT Resize] Pillow (PIL) not installed! Add 'Pillow>=10.0' to requirements.txt")
        return None
    
    try:
        # Télécharger l'image
        img_data = None
        sess = _get_goat_session()
        if sess:
            try:
                r = sess.get(image_url, timeout=15)
                log.info(f"[GOAT Resize] Download status: {r.status_code}, size: {len(r.content)} bytes")
                if r.status_code == 200:
                    img_data = r.content
            except Exception as e:
                log.warning(f"[GOAT Resize] Session download failed: {e}")
        
        if not img_data:
            import subprocess
            result = subprocess.run(
                ["curl", "-s", "-m", "15", "-L", image_url,
                 "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"],
                capture_output=True, timeout=20)
            if result.returncode == 0 and result.stdout:
                img_data = result.stdout
                log.info(f"[GOAT Resize] curl download: {len(img_data)} bytes")
            else:
                log.error(f"[GOAT Resize] curl download failed: rc={result.returncode}")
                return None
        
        if not img_data or len(img_data) < 1000:
            log.error(f"[GOAT Resize] Image data too small: {len(img_data) if img_data else 0} bytes")
            return None
        
        # Ouvrir l'image source
        src = Image.open(BytesIO(img_data)).convert('RGBA')
        src_w, src_h = src.size
        log.info(f"[GOAT Resize] Source: {src_w}x{src_h}")
        
        # Canvas cible: 750x500 fond blanc
        target_w, target_h = 750, 500
        
        # Stratégie : l'image GOAT _00 est carrée (1:1) avec la sneaker centrée.
        # Les images galerie GOAT (medium) sont 750x500 avec la sneaker qui occupe ~88% de la largeur.
        # On reproduit ce cadrage.
        
        # 1. Redimensionner : largeur = 95% du canvas (légère marge latérale)
        sneaker_width = int(target_w * 0.95)
        scale = sneaker_width / src_w
        new_w = sneaker_width
        new_h = int(src_h * scale)
        resized = src.resize((new_w, new_h), Image.LANCZOS)
        log.info(f"[GOAT Resize] Scaled to: {new_w}x{new_h}")
        
        # 2. Créer le canvas blanc 750x500
        canvas = Image.new('RGB', (target_w, target_h), (255, 255, 255))
        
        # 3. Centrer horizontalement
        x = (target_w - new_w) // 2
        
        # 4. Position verticale : sneaker positionnée bas comme les images galerie GOAT
        #    Plus de blanc au-dessus, semelle proche du bord inférieur
        if new_h <= target_h:
            space = target_h - new_h
            y = int(space * 0.70)  # 70% du vide au-dessus, 30% en dessous
            canvas.paste(resized, (x, y), resized if resized.mode == 'RGBA' else None)
        else:
            crop_top = int((new_h - target_h) * 0.35)  # Couper 35% du haut excédentaire
            cropped = resized.crop((0, crop_top, new_w, crop_top + target_h))
            canvas.paste(cropped, (x, 0), cropped if cropped.mode == 'RGBA' else None)
            log.info(f"[GOAT Resize] Vertical crop: top={crop_top}, height={target_h}")
        
        # Convertir en base64 PNG
        buffer = BytesIO()
        canvas.save(buffer, format='PNG', quality=95)
        b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        log.info(f"[GOAT Resize] Done: {src_w}x{src_h} -> 750x500 canvas")
        return b64
        
    except Exception as e:
        log.error(f"[GOAT Resize] Error: {e}")
        return None


def download_goat_image_b64(image_url):
    """Telecharge une image GOAT (qualite d'origine, SANS resize) et renvoie son base64.
    But: l'uploader a Shopify en 'attachment' au lieu de 'src'. L'upload par 'src'
    echoue SILENCIEUSEMENT quand Shopify n'arrive pas a telecharger depuis GOAT
    (blocage Cloudflare cote serveurs Shopify) -> le bot croyait avoir mis 8 photos
    alors qu'il n'en restait que 3. En fournissant les octets, l'image est garantie."""
    try:
        import base64
    except ImportError:
        return None
    import time as _time
    img_data = None
    # Jusqu'a 3 tentatives : session curl_cffi (rotation TLS si echec), puis curl.
    for attempt in range(3):
        sess = _get_goat_session(force_new=(attempt > 0), rotate_profile=(attempt > 0))
        if sess:
            try:
                r = sess.get(image_url, timeout=20, headers={'Referer': 'https://www.goat.com/'})
                if r.status_code == 200 and r.content and len(r.content) >= 1000:
                    img_data = r.content
                    break
            except Exception as e:
                log.warning(f"[GOAT DL] Session download attempt {attempt+1} failed: {e}")
        # Fallback subprocess curl
        import subprocess
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "20", "-L", image_url,
                 "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                 "-H", "Referer: https://www.goat.com/"],
                capture_output=True, timeout=25)
            if result.returncode == 0 and result.stdout and len(result.stdout) >= 1000:
                img_data = result.stdout
                break
        except Exception as e:
            log.warning(f"[GOAT DL] curl download attempt {attempt+1} failed: {e}")
        _time.sleep(1 + attempt)  # backoff avant la prochaine tentative
    if not img_data or len(img_data) < 1000:
        log.warning(f"[GOAT DL] Echec telechargement apres retries: {image_url[:70]}")
        return None
    return base64.b64encode(img_data).decode('utf-8')




def rename_image_file(image_gid, new_filename):
    """Renomme un fichier image via GraphQL fileUpdate"""
    query = """
    mutation fileUpdate($files: [FileUpdateInput!]!) {
        fileUpdate(files: $files) {
            files { id alt }
            userErrors { field message }
        }
    }
    """
    variables = {
        "files": [{
            "id": image_gid,
            "filename": new_filename
        }]
    }
    log.info(f"[ImageRename] Calling GraphQL: gid={image_gid}, filename={new_filename}")
    result = shopify_graphql(query, variables)
    log.info(f"[ImageRename] GraphQL result: {result}")
    
    if not result:
        log.error("[ImageRename] GraphQL returned None")
        return False
    
    if result.get('errors'):
        log.error(f"[ImageRename] GraphQL errors: {result['errors']}")
        return False
    
    user_errors = result.get('data', {}).get('fileUpdate', {}).get('userErrors', [])
    if user_errors:
        log.error(f"[ImageRename] userErrors: {user_errors}")
        return False
    
    return True




def fix_product_images(product_id):
    """Corrige les images d'un produit : nom = Titre_Produit_N.ext, alt = titre produit
    Version optimisée : 1 GET + 1 PUT produit + 1 GraphQL batch = 3 appels max"""
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
        
        name_without_ext = current_filename.rsplit('.', 1)[0] if '.' in current_filename else current_filename
        if name_without_ext == f"{title_for_filename}_{i+1}":
            continue  # Déjà exactement correct
        
        ext = 'jpg'
        if '.' in current_filename:
            ext = current_filename.split('.')[-1].lower()
        
        new_filename = f"{title_for_filename}_{i+1}.{ext}"
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



