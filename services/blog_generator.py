"""
KP SHOES - Generateur de blog SEO
"""

import re
import logging
import urllib.parse

from config import SITE_NAME, SITE_DOMAIN
from services.shopify import shopify_request, get_collections
from services.seo_engine import find_collection
from services.goat_client import get_images as get_goat_images

log = logging.getLogger("kpshoes.blog")


def get_products_for_linking():
    """Récupère TOUS les produits Shopify pour créer des liens internes"""
    products = []
    since_id = 0
    
    # Boucler jusqu'à avoir tous les produits
    for _ in range(20):  # Max 20 pages = 5000 produits
        r = shopify_request(f'products.json?limit=250&since_id={since_id}')
        if not r or 'products' not in r or not r['products']:
            break
        
        for p in r['products']:
            sku = p['variants'][0].get('sku', '') if p.get('variants') else ''
            img = ''
            if p.get('images') and len(p['images']) > 0:
                img = p['images'][0].get('src', '')
            
            products.append({
                'id': p['id'],
                'title': p['title'],
                'handle': p['handle'],
                'sku': sku,
                'image': img,
                'url': f"https://{SITE_DOMAIN}/products/{p['handle']}"
            })
        
        since_id = r['products'][-1]['id']
        
        # Si moins de 250 produits retournés, on a tout
        if len(r['products']) < 250:
            break
    
    log.info(f"[Blog] Loaded {len(products)} products for linking")
    return products


def search_product_by_title(subject):
    """Recherche un produit spécifique par son titre via l'API Shopify"""
    import urllib.parse
    
    # Essayer une recherche directe
    r = shopify_request(f'products.json?title={urllib.parse.quote(subject)}&limit=5')
    if r and r.get('products'):
        for p in r['products']:
            img = ''
            if p.get('images') and len(p['images']) > 0:
                img = p['images'][0].get('src', '')
            return {
                'id': p['id'],
                'title': p['title'],
                'handle': p['handle'],
                'sku': p['variants'][0].get('sku', '') if p.get('variants') else '',
                'image': img,
                'url': f"https://{SITE_DOMAIN}/products/{p['handle']}"
            }
    
    # Fallback : recherche avec des mots-clés
    # Extraire les mots importants du sujet
    words = subject.lower().split()
    stop = ['air', 'nike', 'adidas', 'new', 'balance', 'retro', 'high', 'low', 'mid', 'og', 'sp', 'se', 'the', 'a', 'x', 'men', 'women']
    important = [w for w in words if w not in stop and len(w) > 1]
    
    # Essayer avec les 3-4 mots-clés les plus importants
    for num_words in [4, 3, 2]:
        if len(important) >= num_words:
            search_terms = ' '.join(important[:num_words])
            r = shopify_request(f'products.json?title={urllib.parse.quote(search_terms)}&limit=10')
            if r and r.get('products'):
                # Scorer les résultats
                best = None
                best_score = 0
                subject_lower = subject.lower()
                for p in r['products']:
                    title_lower = p['title'].lower()
                    score = sum(1 for w in important if w in title_lower)
                    if subject_lower in title_lower or title_lower in subject_lower:
                        score += 20
                    if score > best_score:
                        best_score = score
                        best = p
                
                if best and best_score >= 2:
                    img = ''
                    if best.get('images') and len(best['images']) > 0:
                        img = best['images'][0].get('src', '')
                    log.info(f"[Blog] Found product by search: {best['title']} (score={best_score})")
                    return {
                        'id': best['id'],
                        'title': best['title'],
                        'handle': best['handle'],
                        'sku': best['variants'][0].get('sku', '') if best.get('variants') else '',
                        'image': img,
                        'url': f"https://{SITE_DOMAIN}/products/{best['handle']}"
                    }
    
    return None


def find_matching_products(subject, products):
    """Trouve les produits correspondant au sujet - amélioré pour les noms longs et collabs"""
    matches = []
    subject_lower = subject.lower()
    
    # Nettoyer le sujet pour extraire les mots-clés importants
    subject_clean = subject_lower.replace('-', ' ')
    # Garder tous les mots significatifs
    stop_words = ['air', 'nike', 'adidas', 'new', 'balance', 'retro', 'high', 'low', 'mid', 'og', 'sp', 'se', 'the', 'le', 'la', 'de', 'a', 'x']
    keywords = [kw for kw in subject_clean.split() if len(kw) > 1]
    important_keywords = [kw for kw in keywords if kw not in stop_words]
    
    for p in products:
        title_lower = p['title'].lower()
        score = 0
        
        # Vérifier chaque mot-clé important
        for kw in important_keywords:
            if kw in title_lower:
                if kw.isdigit() or kw in ['dunk', 'jordan', 'yeezy', 'samba', 'campus', 'force', 'max', 'gel', 'mind', 'fragment', 'union', 'travis', 'sacai', 'off-white']:
                    score += 3
                else:
                    score += 2
        
        # Vérifier aussi les mots non-importants (air, nike, etc.)
        for kw in keywords:
            if kw in stop_words and kw in title_lower:
                score += 0.5
        
        # Bonus si le sujet complet est dans le titre
        if subject_lower in title_lower:
            score += 20
        
        # Bonus pour correspondances partielles fortes
        # Chercher des combinaisons de 2-3 mots clés
        for i in range(len(important_keywords) - 1):
            combo = important_keywords[i] + ' ' + important_keywords[i+1]
            if combo in title_lower:
                score += 5
        
        # Chercher le nom du modèle sans la marque
        # Ex: "Jordan 1" dans "Air Jordan 1 Retro..."
        if len(important_keywords) >= 2:
            model_combo = ' '.join(important_keywords[:3])
            if model_combo in title_lower:
                score += 8
        
        # Bonus pour les collabs
        collab_names = ['fragment', 'union', 'travis', 'sacai', 'off-white', 'fear of god', 'a ma maniere', 'patta']
        for collab in collab_names:
            if collab in subject_lower and collab in title_lower:
                score += 5
        
        if score > 0:
            matches.append((score, p))
    
    # Trier par score décroissant
    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in matches[:10]]


def generate_article_content(article_type, subject, keywords, tone, length, products, collections, research=None):
    """Génère le contenu de l'article - utilise les données de recherche web si disponibles"""
    
    # Trouver les produits et collections liés
    matching_products = find_matching_products(subject, products)
    matching_collection = find_collection(subject, collections)
    
    log.info(f"[Blog] Found {len(matching_products)} matching products for '{subject}'")
    
    # ── Chercher la paire EXACTE ──
    # D'abord via l'API Shopify (recherche directe par titre)
    exact_product = search_product_by_title(subject)
    
    # Si pas trouvé via API, chercher dans la liste chargée
    if not exact_product:
        subject_lower = subject.lower()
        for p in products:
            title_lower = p['title'].lower()
            if subject_lower in title_lower or title_lower in subject_lower:
                exact_product = p
                break
    
    # Si toujours pas, chercher avec scoring dans les matching
    if not exact_product and matching_products:
        subject_words = set(w for w in subject.lower().split() if len(w) > 2)
        best_score = 0
        for p in matching_products:
            p_words = set(w for w in p['title'].lower().split() if len(w) > 2)
            common = len(subject_words & p_words)
            if common > best_score and common >= len(subject_words) * 0.5:
                best_score = common
                exact_product = p
    
    if exact_product:
        log.info(f"[Blog] Exact product found: {exact_product['title']}")
    
    # ── Section produit dédiée ──
    product_links = ""
    if exact_product or matching_products:
        product_links = f'<h2>Acheter la {subject} sur KP SHOES</h2>'
        
        # Mettre la paire exacte en premier, bien mise en avant
        if exact_product:
            exact_img = f'<img src="{exact_product["image"]}" style="width:100%;max-width:300px;height:auto;border-radius:10px;margin:10px auto;display:block">' if exact_product.get('image') else ''
            product_links += f'''<div style="text-align:center;margin:20px 0;padding:20px;border-radius:12px">
                {exact_img}
                <div style="font-size:16px;font-weight:600;margin:10px 0;color:#333">{exact_product['title']}</div>
                <a href="{exact_product['url']}" style="display:inline-block;padding:10px 25px;background:#667eea;color:white;text-decoration:none;border-radius:8px;font-weight:600;margin:10px 0">Voir cette paire →</a>
            </div>'''
        
        # Ajouter les autres produits similaires
        other_products = [p for p in matching_products if not exact_product or p['id'] != exact_product['id']]
        if other_products:
            product_links += '<p style="margin-top:20px"><strong>Paires similaires disponibles :</strong></p>'
            product_links += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:15px;margin:10px 0">'
            for p in other_products[:5]:
                img_html = f'<img src="{p["image"]}" style="width:100%;height:120px;object-fit:contain;border-radius:8px">' if p.get('image') else '<div style="width:100%;height:120px;border-radius:8px"></div>'
                product_links += f'''<a href="{p['url']}" style="text-decoration:none;color:inherit;display:block">
                    {img_html}
                    <div style="font-size:12px;margin-top:8px;color:#333;text-align:center;line-height:1.3">{p['title'][:50]}{"..." if len(p['title']) > 50 else ""}</div>
                </a>'''
            product_links += "</div>"
    
    # Lien collection
    collection_link = ""
    if matching_collection:
        collection_link = f'<p style="margin:20px 0">👉 <strong><a href="{matching_collection["url"]}">Voir toute la collection {matching_collection["title"]}</a></strong></p>'
    
    # Construire le bloc HTML des infos web trouvées
    web_info_html = build_web_info_html(research, subject)
    
    # Stocker le produit exact pour l'image
    # On passe exact_product via un attribut sur l'article retourné
    result = None
    if article_type == "guide_taille":
        result = generate_sizing_guide(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "release":
        result = generate_release_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "tendance":
        result = generate_trend_article(subject, product_links, collection_link, tone, matching_products, web_info_html, research)
    elif article_type == "comparatif":
        result = generate_comparison_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "histoire":
        result = generate_history_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "entretien":
        result = generate_care_article(subject, product_links, collection_link, tone, web_info_html, research)
    elif article_type == "style":
        result = generate_style_article(subject, product_links, collection_link, tone, web_info_html, research)
    else:
        result = generate_custom_article(subject, keywords, product_links, collection_link, tone, web_info_html, research)
    
    # Si on a trouvé la paire exacte, utiliser son image directement
    if exact_product and exact_product.get('image'):
        result['image_url'] = exact_product['image']
        result['needs_image'] = False  # Pas besoin de chercher sur GOAT
        log.info(f"[Blog] Using exact product image: {exact_product['title']}")
    
    return result




def translate_to_french(text):
    """Traduit un texte en français via Google Translate (gratuit, pas de clé)"""
    if not text or len(text) < 10:
        return text
    
    # Détecter si c'est déjà en français
    french_indicators = [' le ', ' la ', ' les ', ' des ', ' une ', ' est ', ' sont ', ' dans ', ' pour ', ' avec ', ' cette ', ' sur ', ' qui ', ' que ']
    text_lower = text.lower()
    french_count = sum(1 for ind in french_indicators if ind in text_lower)
    if french_count >= 3:
        return text
    
    try:
        import urllib.parse
        # Protéger les noms de produits/marques avant traduction
        # Remplacer temporairement par des placeholders
        protected = {}
        protected_text = text
        brands = ['Nike Mind', 'Air Jordan', 'Air Force', 'Air Max', 'Dunk Low', 'Dunk High', 
                  'New Balance', 'Nike SB', 'Jordan Brand', 'Mind 001', 'Mind 002',
                  'Fragment', 'Union LA', 'Travis Scott', 'Off-White', 'Sacai']
        idx = 0
        for brand in brands:
            if brand in protected_text:
                placeholder = f'XBRAND{idx}X'
                protected[placeholder] = brand
                protected_text = protected_text.replace(brand, placeholder)
                idx += 1
        
        encoded = urllib.parse.quote(protected_text[:2000])
        url = f'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=fr&dt=t&q={encoded}'
        
        html = fetch_url(url, timeout=8)
        if html:
            data = json.loads(html)
            translated = ''.join([s[0] for s in data[0] if s[0]])
            if translated and len(translated) > 10:
                # Restaurer les noms protégés
                for placeholder, original in protected.items():
                    translated = translated.replace(placeholder, original)
                    # Google Translate met parfois des espaces autour
                    translated = translated.replace(placeholder.lower(), original)
                    translated = translated.replace(placeholder.replace('X', 'x'), original)
                return translated
    except Exception as e:
        log.error(f"[Translate] Error: {e}")
    
    return text


def build_web_info_html(research, subject):
    """Construit le HTML des informations trouvées sur le web, traduit en français"""
    if not research or not research.get('found'):
        return ""
    
    html = ""
    
    # Wikipedia
    wiki = research.get('wikipedia')
    if wiki and wiki.get('extract'):
        extract = wiki['extract']
        if len(extract) > 500:
            extract = extract[:500].rsplit(' ', 1)[0] + '...'
        # Traduire si en anglais
        extract = translate_to_french(extract)
        html += f'<div style="margin:20px 0">'
        html += f'<p style="margin:0">{extract}</p>'
        html += f'</div>'
    
    # Résultats de recherche
    results = research.get('search_results', [])
    if results:
        clean_results = []
        seen = set()
        
        # Mots de bruit à filtrer
        junk_patterns = [
            'fashionfootwear', 'artdesignmusic', 'cookie', 'privacy', 'subscribe',
            'newsletter', 'sign up', 'log in', 'download the', 'scan the qr',
            'some languages may be', 'accuracy may vary', 'turn on code suggestion',
            'brand ranking', 'brand directory', 'magazine', 'morefashion',
            'don\'t show again', 'app stores', 'cmd', 'copyright', 'terms of use',
            'all rights reserved', 'follow us', 'stay ahead', 'get the latest'
        ]
        
        for r in results:
            r_clean = r.strip()
            r_lower = r_clean.lower()
            
            if any(junk in r_lower for junk in junk_patterns):
                continue
            if len(r_clean) < 50:
                continue
            
            key = r_lower[:60]
            if key in seen:
                continue
            seen.add(key)
            
            if len(r_clean) > 400:
                r_clean = r_clean[:400].rsplit(' ', 1)[0] + '...'
            
            # Nettoyer les entités HTML
            r_clean = r_clean.replace('&quot;', '"').replace('&#039;', "'").replace('&amp;', '&').replace('&#x27;', "'").replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'")
            
            clean_results.append(r_clean)
        
        if clean_results:
            # Traduire chaque résultat en français
            translated_results = []
            for r in clean_results[:6]:
                translated = translate_to_french(r)
                translated_results.append(translated)
            
            html += f'<h2>Ce que l\'on sait sur la {subject}</h2>'
            html += '<div style="margin:20px 0">'
            for r in translated_results:
                html += f'<p style="margin:10px 0;line-height:1.6">{r}</p>'
            html += '</div>'
    
    return html


def generate_sizing_guide(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un guide de tailles"""
    title = f"Comment taille la {subject} ? Guide complet des tailles 2026"
    
    meta_title = f"Comment taille la {subject} ? Guide tailles 2026 | KP SHOES"[:70]
    meta_description = f"Découvrez comment taille la {subject}. Tableau des tailles EU/US/UK, conseils pour pieds larges et comparaison avec d'autres modèles. Guide complet."[:160]
    summary = f"Vous vous demandez comment taille la {subject} ? Découvrez notre guide complet avec tableau des tailles et conseils."
    
    body = f"""
<p>Vous vous demandez <strong>comment taille la {subject}</strong> ? Ce guide complet vous aide à choisir la bonne pointure. Chez <strong>KP SHOES</strong>, nous garantissons l'authenticité de chaque paire.</p>

{web_info_html}

<h2>La {subject} taille-t-elle grand ou petit ?</h2>
<p>La {subject} est réputée pour <strong>tailler normalement</strong>. Si vous êtes entre deux tailles, nous vous conseillons de prendre la taille supérieure pour plus de confort, surtout si vous avez les pieds larges.</p>

<h2>Tableau des tailles {subject}</h2>
<table style="width:100%;border-collapse:collapse;margin:20px 0">
<tr style="background:#f5f5f5"><th style="padding:12px;border:1px solid #ddd;text-align:center">EU</th><th style="padding:12px;border:1px solid #ddd;text-align:center">US Homme</th><th style="padding:12px;border:1px solid #ddd;text-align:center">US Femme</th><th style="padding:12px;border:1px solid #ddd;text-align:center">UK</th><th style="padding:12px;border:1px solid #ddd;text-align:center">CM</th></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">38</td><td style="padding:10px;border:1px solid #ddd;text-align:center">5.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7</td><td style="padding:10px;border:1px solid #ddd;text-align:center">5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">24</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">39</td><td style="padding:10px;border:1px solid #ddd;text-align:center">6.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8</td><td style="padding:10px;border:1px solid #ddd;text-align:center">6</td><td style="padding:10px;border:1px solid #ddd;text-align:center">24.5</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">40</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">6</td><td style="padding:10px;border:1px solid #ddd;text-align:center">25</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">41</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8</td><td style="padding:10px;border:1px solid #ddd;text-align:center">9.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7</td><td style="padding:10px;border:1px solid #ddd;text-align:center">26</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">42</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">10</td><td style="padding:10px;border:1px solid #ddd;text-align:center">7.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">26.5</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">43</td><td style="padding:10px;border:1px solid #ddd;text-align:center">9.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11</td><td style="padding:10px;border:1px solid #ddd;text-align:center">8.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">27.5</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">44</td><td style="padding:10px;border:1px solid #ddd;text-align:center">10</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">9</td><td style="padding:10px;border:1px solid #ddd;text-align:center">28</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd;text-align:center">45</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11</td><td style="padding:10px;border:1px solid #ddd;text-align:center">12.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">10</td><td style="padding:10px;border:1px solid #ddd;text-align:center">29</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd;text-align:center">46</td><td style="padding:10px;border:1px solid #ddd;text-align:center">12</td><td style="padding:10px;border:1px solid #ddd;text-align:center">13.5</td><td style="padding:10px;border:1px solid #ddd;text-align:center">11</td><td style="padding:10px;border:1px solid #ddd;text-align:center">30</td></tr>
</table>

<h2>Conseils pour bien choisir sa taille</h2>
<ul>
<li><strong>Pieds larges</strong> : Prenez une demi-taille au-dessus</li>
<li><strong>Pieds fins</strong> : Restez sur votre taille habituelle</li>
<li><strong>Entre deux tailles</strong> : Optez pour la taille supérieure</li>
<li><strong>Pour le style</strong> : Certains préfèrent une taille au-dessus pour un look plus loose</li>
</ul>

<h2>Comparaison avec d'autres modèles</h2>
<p>Si vous connaissez votre taille dans d'autres modèles, voici quelques repères :</p>
<ul>
<li>Même taille que les Nike Air Force 1</li>
<li>Même taille que les Nike Dunk Low</li>
<li>Une demi-taille au-dessus des Adidas (Samba, Campus)</li>
<li>Même taille que les New Balance 550</li>
</ul>

{collection_link}

{product_links}

<h2>FAQ - Questions fréquentes</h2>
<h3>La {subject} taille-t-elle grand ?</h3>
<p>Non, la {subject} taille normalement. Prenez votre taille habituelle Nike.</p>

<h3>Dois-je prendre une taille au-dessus ?</h3>
<p>Uniquement si vous avez les pieds larges ou si vous êtes entre deux tailles.</p>

<h3>Comment mesurer son pied ?</h3>
<p>Mesurez votre pied le soir (quand il est légèrement gonflé) du talon au bout du gros orteil, et reportez-vous au tableau ci-dessus.</p>

<p><strong>Chez KP SHOES, toutes nos sneakers sont 100% authentiques et vérifiées par nos experts.</strong> Livraison rapide et paiement sécurisé.</p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'guide taille, {subject}, sizing, pointure',
        'handle': f'guide-taille-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_release_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur les sorties"""
    import datetime
    month = datetime.datetime.now().strftime('%B %Y')
    
    title = f"Sorties {subject} {month} : Calendrier et dates de release"
    meta_title = f"Sorties {subject} 2026 : Dates et calendrier | KP SHOES"[:70]
    meta_description = f"Découvrez toutes les sorties {subject} prévues en 2026. Calendrier des releases, dates de sortie et conseils pour cop les paires limitées."[:160]
    summary = f"Toutes les sorties {subject} à ne pas manquer. Calendrier des releases, dates clés et conseils pour réussir vos achats."
    
    body = f"""
<p>Découvrez toutes les <strong>sorties {subject}</strong> prévues pour {month}. Restez informé des dernières releases et ne manquez aucune paire sur <strong>KP SHOES</strong>.</p>

<h2>Les releases {subject} à ne pas manquer</h2>
<p>L'année 2026 s'annonce riche en sorties pour les fans de {subject}. Voici les dates clés à retenir.</p>

<h2>Comment cop les {subject} en édition limitée ?</h2>
<ul>
<li><strong>Suivez les comptes officiels</strong> : Nike SNKRS, Jordan, et les réseaux sociaux des marques</li>
<li><strong>Activez les notifications</strong> : Soyez alerté dès l'annonce d'une nouvelle release</li>
<li><strong>Préparez vos comptes</strong> : Créez vos profils sur les apps de raffle à l'avance</li>
<li><strong>Achetez sur des sites de confiance</strong> : KP SHOES garantit l'authenticité de chaque paire</li>
</ul>

{collection_link}

<h2>Les coloris les plus attendus</h2>
<p>Parmi les sorties les plus anticipées, certains coloris font déjà parler d'eux dans la communauté sneakers. Les collaborations et les éditions limitées restent les plus recherchées.</p>

{product_links}

<h2>Prix et disponibilité</h2>
<p>Les prix retail varient généralement entre 110€ et 200€ selon les modèles. Sur le marché de la revente, certaines paires peuvent atteindre des prix bien plus élevés, notamment les collaborations.</p>

<p><strong>Sur KP SHOES, retrouvez ces modèles 100% authentiques avec livraison rapide et paiement sécurisé.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'sortie, release, {subject}, calendrier, 2026',
        'handle': f'sorties-{subject.lower().replace(" ", "-")}-2026',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_trend_article(subject, product_links, collection_link, tone, matching_products, web_info_html='', research=None):
    """Génère un article sur les tendances"""
    title = "Sneakers tendance 2026 : Les modèles les plus hype du moment"
    meta_title = "Sneakers tendance 2026 : Les modèles incontournables | KP SHOES"
    meta_description = "Découvrez les sneakers les plus tendance en 2026. Running rétro, classiques indémodables et collaborations de luxe. Notre sélection des modèles hype."
    summary = "Quelles sont les sneakers les plus tendance en 2026 ? Découvrez notre sélection des modèles incontournables : running rétro, classiques et collaborations."
    
    if subject:
        title = f"{subject} : Pourquoi c'est LA sneaker tendance de 2026"
        meta_title = f"{subject} : La sneaker tendance 2026 | KP SHOES"[:70]
        meta_description = f"Découvrez pourquoi la {subject} est LA sneaker tendance de 2026. Style, confort et hype : tout ce qu'il faut savoir."[:160]
        summary = f"La {subject} s'impose comme l'une des sneakers les plus tendance de 2026. Découvrez pourquoi elle fait l'unanimité."
    
    body = f"""
<p>Quelles sont les <strong>sneakers les plus tendance en 2026</strong> ? Le marché de la sneaker continue d'évoluer.</p>

{web_info_html}

<h2>Les tendances sneakers 2026</h2>

<h3>1. Le retour du running rétro</h3>
<p>Les silhouettes inspirées des années 90 et 2000 continuent de dominer. Les <strong>Asics Gel-1130</strong>, <strong>New Balance 530</strong> et <strong>Nike Air Max</strong> sont partout dans les rues.</p>

<h3>2. Les classiques indémodables</h3>
<p>La <strong>Nike Dunk Low</strong>, l'<strong>Adidas Samba</strong> et la <strong>New Balance 550</strong> restent des valeurs sûres. Ces modèles polyvalents s'adaptent à tous les styles.</p>

<h3>3. Les collaborations de luxe</h3>
<p>Les partenariats entre marques de sport et maisons de luxe continuent de faire sensation. Les drops limités créent une forte demande sur le marché du resell.</p>

{collection_link}

<h2>Notre sélection KP SHOES</h2>
{product_links}

<h2>Comment adopter la tendance ?</h2>
<ul>
<li><strong>Investissez dans des classiques</strong> : Ils ne se démodent jamais</li>
<li><strong>Osez les couleurs</strong> : Les coloris audacieux sont très recherchés</li>
<li><strong>Privilégiez la qualité</strong> : Une paire authentique dure plus longtemps</li>
</ul>

<p><strong>Chez KP SHOES, retrouvez tous les modèles tendance 100% authentiques.</strong> Notre équipe vérifie chaque paire avant expédition.</p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': 'tendance, sneakers 2026, hype, mode, streetwear',
        'handle': 'sneakers-tendance-2026',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject if subject else 'Nike Dunk Low'
    }


def generate_comparison_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article comparatif"""
    # Parser le sujet pour extraire les 2 modèles
    models = subject.split(' vs ') if ' vs ' in subject else [subject, 'Nike Dunk Low']
    model1 = models[0].strip()
    model2 = models[1].strip() if len(models) > 1 else 'Nike Dunk Low'
    
    title = f"{model1} vs {model2} : Quelle sneaker choisir en 2026 ?"
    meta_title = f"{model1} vs {model2} : Comparatif 2026 | KP SHOES"[:70]
    meta_description = f"Comparatif {model1} vs {model2}. Confort, style, prix : on vous aide à choisir la sneaker faite pour vous."[:160]
    summary = f"Vous hésitez entre {model1} et {model2} ? Notre comparatif détaillé vous aide à faire le bon choix."
    
    body = f"""
<p>Vous hésitez entre la <strong>{model1}</strong> et la <strong>{model2}</strong> ? Ce comparatif détaillé vous aide à faire le bon choix selon vos besoins et votre style.</p>

<h2>Tableau comparatif</h2>
<table style="width:100%;border-collapse:collapse;margin:20px 0">
<tr style="background:#f5f5f5"><th style="padding:12px;border:1px solid #ddd">Critère</th><th style="padding:12px;border:1px solid #ddd">{model1}</th><th style="padding:12px;border:1px solid #ddd">{model2}</th></tr>
<tr><td style="padding:10px;border:1px solid #ddd"><strong>Confort</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd"><strong>Style</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐⭐</td></tr>
<tr><td style="padding:10px;border:1px solid #ddd"><strong>Polyvalence</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐⭐</td></tr>
<tr style="background:#f9f9f9"><td style="padding:10px;border:1px solid #ddd"><strong>Durabilité</strong></td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td><td style="padding:10px;border:1px solid #ddd;text-align:center">⭐⭐⭐⭐</td></tr>
</table>

<h2>{model1} : Points forts et faibles</h2>
<h3>✅ Avantages</h3>
<ul>
<li>Design iconique et reconnaissable</li>
<li>Large choix de coloris</li>
<li>Bonne qualité de fabrication</li>
</ul>
<h3>❌ Inconvénients</h3>
<ul>
<li>Prix parfois élevé sur le marché du resell</li>
<li>Certains coloris difficiles à trouver</li>
</ul>

<h2>{model2} : Points forts et faibles</h2>
<h3>✅ Avantages</h3>
<ul>
<li>Silhouette polyvalente</li>
<li>Confort au quotidien</li>
<li>S'accorde avec de nombreuses tenues</li>
</ul>
<h3>❌ Inconvénients</h3>
<ul>
<li>Très populaire, donc moins original</li>
</ul>

{collection_link}

<h2>Notre verdict</h2>
<p>Les deux modèles sont d'excellents choix. La <strong>{model1}</strong> conviendra aux amateurs de sneakers iconiques, tandis que la <strong>{model2}</strong> sera parfaite pour un usage quotidien polyvalent.</p>

{product_links}

<p><strong>Retrouvez ces deux modèles sur KP SHOES, 100% authentiques et vérifiés.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'comparatif, {model1}, {model2}, versus, guide achat',
        'handle': f'comparatif-{model1.lower().replace(" ", "-")}-vs-{model2.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': model1
    }


def generate_history_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur l'histoire d'un modèle avec infos web"""
    title = f"L'histoire de la {subject} : De sa création à aujourd'hui"
    meta_title = f"Histoire de la {subject} : Origines et évolution | KP SHOES"[:70]
    meta_description = f"Découvrez l'histoire fascinante de la {subject}. De ses origines à son statut d'icône streetwear, retour sur un modèle légendaire."[:160]
    summary = f"La {subject} est bien plus qu'une sneaker. Découvrez son histoire fascinante, de sa création à son statut d'icône culturelle."
    
    # Section produit
    product_section = ""
    if product_links:
        product_section = product_links
    
    body = f"""
<p>Découvrez l'histoire complète de la <strong>{subject}</strong>, une paire qui a marqué l'univers de la sneaker.</p>

{web_info_html}

{collection_link}

{product_section}

<h2>Pourquoi cette paire est-elle si recherchée ?</h2>
<ul>
<li><strong>Un design iconique</strong> : Un modèle qui a su traverser les époques</li>
<li><strong>Une qualité premium</strong> : Des matériaux sélectionnés pour une durabilité optimale</li>
<li><strong>Un héritage culturel</strong> : Une sneaker adoptée par les passionnés du monde entier</li>
</ul>

<p><strong>Retrouvez la {subject} sur KP SHOES. Chaque paire est 100% authentique et vérifiée par nos experts.</strong></p>
"""
    
    # Si pas d'info web, ajouter un message honnête
    if not web_info_html:
        body = f"""
<p>Nous n'avons pas trouvé suffisamment d'informations vérifiées sur la <strong>{subject}</strong> pour rédiger un article d'histoire complet et fiable.</p>

<p>Chez <strong>KP SHOES</strong>, nous préférons ne pas publier d'informations incorrectes. Nous vous invitons à vérifier ce modèle directement sur le site officiel de la marque.</p>

{collection_link}

{product_section}

<p><strong>Retrouvez vos sneakers sur KP SHOES - 100% authentiques et vérifiées par nos experts.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'histoire, {subject}, culture sneaker, légende, heritage',
        'handle': f'histoire-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_care_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur l'entretien"""
    title = f"Comment nettoyer et entretenir ses {subject} ? Guide complet"
    meta_title = f"Comment nettoyer ses {subject} ? Guide entretien | KP SHOES"[:70]
    meta_description = f"Découvrez comment nettoyer et entretenir vos {subject}. Conseils d'experts, erreurs à éviter et astuces pour prolonger leur durée de vie."[:160]
    summary = f"Vos {subject} méritent le meilleur entretien. Découvrez nos conseils d'experts pour les garder impeccables."
    
    body = f"""
<p>Vos <strong>{subject}</strong> méritent un entretien régulier pour rester impeccables.</p>

{web_info_html}

<h2>Le matériel nécessaire</h2>
<ul>
<li>Une brosse à poils doux</li>
<li>Un chiffon microfibre</li>
<li>Du savon de Marseille ou un nettoyant spécial sneakers</li>
<li>De l'eau tiède</li>
<li>Un spray imperméabilisant</li>
</ul>

<h2>Étapes de nettoyage</h2>
<h3>1. Préparation</h3>
<p>Retirez les lacets et les semelles intérieures. Brossez délicatement pour enlever la poussière et les saletés superficielles.</p>

<h3>2. Nettoyage</h3>
<p>Mélangez un peu de savon avec de l'eau tiède. Frottez doucement avec la brosse en faisant des mouvements circulaires. Évitez de tremper complètement vos sneakers.</p>

<h3>3. Rinçage</h3>
<p>Essuyez avec un chiffon humide pour retirer le savon. Répétez si nécessaire.</p>

<h3>4. Séchage</h3>
<p>Laissez sécher à l'air libre, loin des sources de chaleur directe. Bourrez l'intérieur avec du papier journal pour absorber l'humidité et maintenir la forme.</p>

<h2>Conseils selon les matériaux</h2>
<h3>Cuir</h3>
<p>Utilisez un nettoyant spécial cuir et appliquez une crème nourrissante après le nettoyage.</p>

<h3>Suède/Nubuck</h3>
<p>Brossez à sec avec une brosse spéciale suède. Évitez l'eau qui peut tacher le matériau.</p>

<h3>Mesh/Textile</h3>
<p>Ces matériaux supportent mieux l'eau. Vous pouvez les nettoyer plus généreusement.</p>

<h2>Erreurs à éviter</h2>
<ul>
<li>❌ <strong>Ne jamais mettre en machine</strong> : Risque de déformation et décollement</li>
<li>❌ <strong>Éviter le sèche-linge</strong> : La chaleur détériore les colles et matériaux</li>
<li>❌ <strong>Ne pas utiliser de javel</strong> : Elle jaunit et fragilise les matériaux</li>
</ul>

{collection_link}

{product_links}

<h2>Protection et stockage</h2>
<ul>
<li>Appliquez un spray imperméabilisant avant la première utilisation</li>
<li>Rangez vos sneakers dans leurs boîtes d'origine</li>
<li>Utilisez des embauchoirs pour maintenir la forme</li>
<li>Évitez l'humidité et la lumière directe du soleil</li>
</ul>

<p><strong>Chez KP SHOES, toutes nos sneakers sont livrées dans un état impeccable. 100% authentiques et vérifiées.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'entretien, nettoyage, {subject}, sneaker care, guide',
        'handle': f'entretien-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_style_article(subject, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article sur le style"""
    title = f"Comment porter la {subject} ? Idées de looks et outfits 2026"
    meta_title = f"Comment porter la {subject} ? Idées looks 2026 | KP SHOES"[:70]
    meta_description = f"Découvrez comment porter la {subject}. Looks casual, streetwear et smart casual : nos idées d'outfits pour tous les styles."[:160]
    summary = f"La {subject} est ultra polyvalente. Découvrez nos idées de looks pour la porter avec style au quotidien."
    
    body = f"""
<p>La <strong>{subject}</strong> est une sneaker polyvalente. Découvrez nos conseils pour créer des looks tendance.</p>

{web_info_html}

<h2>Look casual quotidien</h2>
<p>Pour un style décontracté au quotidien :</p>
<ul>
<li>Jean slim ou regular + t-shirt basique + {subject}</li>
<li>Jogger + hoodie + {subject}</li>
<li>Short cargo + polo + {subject}</li>
</ul>

<h2>Look streetwear</h2>
<p>Pour un style urbain affirmé :</p>
<ul>
<li>Pantalon cargo + sweat oversize + {subject}</li>
<li>Jean baggy + bomber jacket + {subject}</li>
<li>Survêtement vintage + {subject}</li>
</ul>

<h2>Look smart casual</h2>
<p>Oui, on peut porter des sneakers au bureau (selon le dress code) :</p>
<ul>
<li>Chino + chemise + blazer léger + {subject}</li>
<li>Pantalon à pinces + pull col roulé + {subject}</li>
</ul>

{collection_link}

<h2>Les couleurs qui matchent</h2>
<h3>Avec des {subject} blanches</h3>
<p>Tout ! Le blanc est la couleur la plus polyvalente. Jean bleu, pantalon noir, couleurs vives... Tout fonctionne.</p>

<h3>Avec des {subject} noires</h3>
<p>Parfaites pour un look monochrome ou avec des couleurs neutres (gris, beige, blanc).</p>

<h3>Avec des {subject} colorées</h3>
<p>Gardez le reste de la tenue sobre pour laisser les sneakers être le point focal.</p>

{product_links}

<h2>Conseils de style</h2>
<ul>
<li><strong>Équilibrez les proportions</strong> : Sneakers chunky avec pantalon plus ajusté</li>
<li><strong>Jouez avec les textures</strong> : Cuir, denim, coton... Variez les matières</li>
<li><strong>Accessoirisez</strong> : Montre, casquette, sac assorti</li>
</ul>

<p><strong>Retrouvez la {subject} sur KP SHOES. 100% authentique, livraison rapide.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'style, outfit, {subject}, look, mode, streetwear',
        'handle': f'comment-porter-{subject.lower().replace(" ", "-")}',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }


def generate_custom_article(subject, keywords, product_links, collection_link, tone, web_info_html='', research=None):
    """Génère un article personnalisé"""
    title = f"{subject} : Tout ce que vous devez savoir en 2026"
    meta_title = f"{subject} : Guide complet 2026 | KP SHOES"[:70]
    meta_description = f"Découvrez tout ce qu'il faut savoir sur {subject}. Guide complet, conseils d'achat et sélection des meilleures paires sur KP SHOES."[:160]
    summary = f"Tout ce qu'il faut savoir sur {subject}. Guide complet et conseils d'achat par les experts KP SHOES."
    
    body = f"""
<p>Découvrez tout ce qu'il faut savoir sur <strong>{subject}</strong>. Chez <strong>KP SHOES</strong>, nous vous proposons les meilleures paires 100% authentiques.</p>

{web_info_html}

<h2>Où acheter {subject} authentique ?</h2>
<p>Pour être sûr d'obtenir une paire authentique, privilégiez les revendeurs de confiance comme <strong>KP SHOES</strong>. Nous vérifions chaque paire avant expédition.</p>

{collection_link}

{product_links}

<h2>Notre engagement qualité</h2>
<ul>
<li>✅ Authenticité garantie à 100%</li>
<li>✅ Vérification par nos experts</li>
<li>✅ Livraison rapide et sécurisée</li>
<li>✅ Service client réactif</li>
</ul>

<p><strong>Faites confiance à KP SHOES pour vos sneakers authentiques.</strong></p>
"""
    
    return {
        'title': title,
        'body_html': body,
        'tags': f'{subject}, sneakers, authentique, kp shoes',
        'handle': f'{subject.lower().replace(" ", "-")}-guide-2026',
        'meta_title': meta_title,
        'meta_description': meta_description,
        'summary_html': summary,
        'needs_image': True,
        'image_search_term': subject
    }




