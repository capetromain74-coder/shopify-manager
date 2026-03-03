"""KP SHOES - Routes API Blog"""
import time, logging
from flask import Blueprint, jsonify, request
from services.shopify import shopify_request, get_collections
from services.goat_client import get_images as get_goat_images
from services.seo_engine import find_collection
from services.blog_generator import get_products_for_linking, generate_article_content, find_matching_products
from services.web_research import do_web_research
log = logging.getLogger("kpshoes.blog_routes")
blog_bp = Blueprint("blog", __name__)

@blog_bp.route('/api/blogs')
def api_blogs():
    """Liste tous les blogs Shopify"""
    r = shopify_request('blogs.json')
    if not r:
        return jsonify({'error': 'Impossible de récupérer les blogs. Vérifiez les permissions API (scope: read_content)'}), 403
    return jsonify(r)


@blog_bp.route('/api/blogs/<int:blog_id>/articles')
def api_blog_articles(blog_id):
    """Liste les articles d'un blog"""
    r = shopify_request(f'blogs/{blog_id}/articles.json')
    if not r:
        return jsonify({'error': 'Impossible de récupérer les articles'}), 403
    return jsonify(r)


@blog_bp.route('/api/blogs/<int:blog_id>/articles', methods=['POST'])
def api_create_article(blog_id):
    """Crée un nouvel article de blog"""
    data = request.json
    
    article_data = {
        'article': {
            'title': data.get('title', ''),
            'author': data.get('author', 'KP SHOES'),
            'body_html': data.get('body_html', ''),
            'published': data.get('published', True),
            'tags': data.get('tags', ''),
            'summary_html': data.get('summary_html', ''),  # Extrait
            'metafields': []
        }
    }
    
    # Ajouter image si fournie
    if data.get('image_url'):
        article_data['article']['image'] = {'src': data.get('image_url')}
    
    # Ajouter meta title
    if data.get('meta_title'):
        article_data['article']['metafields'].append({
            'namespace': 'global',
            'key': 'title_tag',
            'value': data.get('meta_title'),
            'type': 'single_line_text_field'
        })
    
    # Ajouter meta description
    if data.get('meta_description'):
        article_data['article']['metafields'].append({
            'namespace': 'global',
            'key': 'description_tag',
            'value': data.get('meta_description'),
            'type': 'single_line_text_field'
        })
    
    # Supprimer metafields si vide
    if not article_data['article']['metafields']:
        del article_data['article']['metafields']
    
    r = shopify_request(f'blogs/{blog_id}/articles.json', 'POST', article_data)
    if not r:
        return jsonify({'error': 'Impossible de créer l\'article. Vérifiez les permissions API (scope: write_content)'}), 403
    return jsonify({'success': True, 'article': r.get('article', {})})


@blog_bp.route('/api/blogs/<int:blog_id>/articles/<int:article_id>', methods=['PUT'])
def api_update_article(blog_id, article_id):
    """Met à jour un article de blog"""
    data = request.json
    
    article_data = {
        'article': {
            'id': article_id,
            'title': data.get('title'),
            'body_html': data.get('body_html'),
            'published': data.get('published'),
            'tags': data.get('tags')
        }
    }
    
    # Nettoyer les None
    article_data['article'] = {k: v for k, v in article_data['article'].items() if v is not None}
    
    r = shopify_request(f'blogs/{blog_id}/articles/{article_id}.json', 'PUT', article_data)
    if not r:
        return jsonify({'error': 'Impossible de modifier l\'article'}), 403
    return jsonify({'success': True, 'article': r.get('article', {})})


@blog_bp.route('/api/blogs/<int:blog_id>/articles/<int:article_id>', methods=['DELETE'])
def api_delete_article(blog_id, article_id):
    """Supprime un article de blog"""
    r = shopify_request(f'blogs/{blog_id}/articles/{article_id}.json', 'DELETE')
    return jsonify({'success': True})


@blog_bp.route('/api/blog/test-search')
def api_blog_test_search():
    """Route de test pour diagnostiquer la recherche web"""
    subject = request.args.get('q', 'Nike Mind 001')
    results = {'subject': subject, 'tests': {}}
    
    # Test 1: Wikipedia
    try:
        wiki = search_wikipedia(subject)
        results['tests']['wikipedia'] = {
            'status': 'OK' if wiki else 'NO RESULTS',
            'data': wiki
        }
    except Exception as e:
        results['tests']['wikipedia'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 2: Sneaker sites scraping
    try:
        sneaker = search_sneaker_sites(subject)
        results['tests']['sneaker_sites'] = {
            'status': 'OK' if sneaker else 'NO RESULTS',
            'count': len(sneaker),
            'data': [s[:200] for s in sneaker[:5]]
        }
    except Exception as e:
        results['tests']['sneaker_sites'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 3: Brand page
    try:
        brand = search_brand_page(subject)
        results['tests']['brand_page'] = {
            'status': 'OK' if brand else 'NO RESULTS',
            'count': len(brand),
            'data': [s[:200] for s in brand[:5]]
        }
    except Exception as e:
        results['tests']['brand_page'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 4: Full research
    try:
        full = do_web_research(subject, 'histoire')
        results['tests']['full_research'] = {
            'status': 'OK' if full.get('found') else 'NO RESULTS',
            'result_count': len(full.get('search_results', [])),
            'data': [s[:200] for s in full.get('search_results', [])[:3]]
        }
    except Exception as e:
        results['tests']['full_research'] = {'status': 'ERROR', 'error': str(e)}
    
    # Test 5: Google Translate
    try:
        test_text = "The Nike Mind 001 is a neuroscience-based footwear."
        translated = translate_to_french(test_text)
        results['tests']['google_translate'] = {
            'status': 'OK' if translated != test_text else 'FAILED',
            'original': test_text,
            'translated': translated
        }
    except Exception as e:
        results['tests']['google_translate'] = {'status': 'ERROR', 'error': str(e)}
    
    return jsonify(results)
    
    return jsonify(results)


@blog_bp.route('/api/blog/research', methods=['POST'])
def api_blog_research():
    """Endpoint de recherche web pour le blog generator"""
    data = request.json
    subject = data.get('subject', '').strip()
    article_type = data.get('type', 'custom')
    
    if not subject:
        return jsonify({'error': 'Sujet manquant'}), 400
    
    try:
        info = do_web_research(subject, article_type)
        return jsonify(info)
    except Exception as e:
        log.error(f"[Research] Error: {e}")
        return jsonify({'wikipedia': None, 'search_results': [], 'found': False})


@blog_bp.route('/api/blog/generate', methods=['POST'])
def api_generate_blog():
    """Génère un article de blog SEO"""
    data = request.json
    
    article_type = data.get('type', 'custom')
    subject = data.get('subject', '').strip()
    keywords = data.get('keywords', '')
    tone = data.get('tone', 'expert')
    length = data.get('length', 'medium')
    
    try:
        # Recherche web sur le sujet
        log.info(f"[Blog] Starting web research for '{subject}' ({article_type})")
        research = do_web_research(subject, article_type)
        log.info(f"[Blog] Research done: found={research.get('found')}")
        
        # Récupérer les produits et collections pour le maillage interne
        products = get_products_for_linking()
        collections = get_collections()
        
        # Générer le contenu avec les données de recherche
        article = generate_article_content(
            article_type, subject, keywords, tone, length,
            products, collections, research
        )
        
        # Récupérer une image depuis GOAT si nécessaire
        if article.get('needs_image') and article.get('image_search_term'):
            search_term = article.get('image_search_term', subject)
            goat_result = get_goat_images(search_term)
            if goat_result and goat_result.get('images'):
                article['image_url'] = goat_result['images'][0]
                log.info(f"[Blog] Got image from GOAT: {article['image_url'][:50]}...")
        
        # Si pas d'image GOAT, chercher dans les produits correspondants
        if not article.get('image_url'):
            matching = find_matching_products(subject, products)
            if matching:
                # Chercher l'image du premier produit
                for p in matching:
                    r = shopify_request(f'products/{p["id"]}.json')
                    if r and r.get('product', {}).get('images'):
                        article['image_url'] = r['product']['images'][0]['src']
                        log.info(f"[Blog] Got image from product: {p['title']}")
                        break
        
        return jsonify(article)
        
    except Exception as e:
        log.error(f"[Blog Generator] Error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
