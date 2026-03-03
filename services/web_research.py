"""
KP SHOES - Recherche web pour articles de blog
"""

import re
import ssl
import json
import logging
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

log = logging.getLogger("kpshoes.research")


# ══════════════════════════════════════════════════════════════
# RECHERCHE WEB POUR LE BLOG (scraping direct des sites sneakers)
# ══════════════════════════════════════════════════════════════

def fetch_url(url, timeout=10):
    """Fetch une URL avec gestion d'erreurs"""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
        })
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        log.error(f"[Fetch] {url[:60]}: {e}")
        return None


def extract_text_from_html(html, min_length=50, max_paragraphs=15):
    """Extrait les paragraphes de texte utile d'une page HTML"""
    if not html:
        return []
    
    paragraphs = []
    
    # Extraire les <p>
    p_tags = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
    for p in p_tags:
        text = re.sub(r'<[^>]+>', '', p).strip()
        text = re.sub(r'\s+', ' ', text)
        if len(text) >= min_length and len(text) < 2000:
            lower = text.lower()
            skip = False
            # Liste étendue de bruit à filtrer
            junk_list = [
                'cookie', 'privacy policy', 'subscribe', 'newsletter', 'sign up', 
                'log in', 'accept all', 'javascript', 'copyright', 'terms of service',
                'politique de confidentialite', 'kicksfinder is an online database',
                'fashionfootwear', 'artdesignmusic', 'brand ranking', 'brand directory',
                'scan the qr', 'download the app', 'app stores', 'stay ahead of the curve',
                'get the latest', 'follow us', 'all rights reserved', 'terms of use',
                'accuracy may vary', 'some languages may be', 'don\'t show again',
                'turn on code', 'cmd', 'www.kicksfinder.com', 'online database of the most popular',
                'complete list of retailers'
            ]
            for junk in junk_list:
                if junk in lower:
                    skip = True
                    break
            # Aussi filtrer les textes qui ressemblent à des menus de navigation (mots collés sans espaces)
            if not skip and len(text) > 80:
                # Ratio espaces/texte trop bas = menu de navigation
                space_ratio = text.count(' ') / len(text)
                if space_ratio < 0.05:
                    skip = True
            if not skip:
                paragraphs.append(text)
    
    # Aussi extraire les <meta description>
    meta = re.findall(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.DOTALL)
    if not meta:
        meta = re.findall(r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']', html, re.DOTALL)
    for m in meta:
        m_clean = m.strip()
        m_lower = m_clean.lower()
        if len(m_clean) > 40 and 'kicksfinder' not in m_lower and 'online database' not in m_lower:
            paragraphs.insert(0, m_clean)
    
    return paragraphs[:max_paragraphs]


def search_wikipedia(query):
    """Recherche Wikipedia FR puis EN via l'API"""
    for lang in ['fr', 'en']:
        try:
            import urllib.parse
            search_url = f"https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit=3&format=json"
            html = fetch_url(search_url, timeout=8)
            if html:
                data = json.loads(html)
                if data and len(data) >= 4 and data[1]:
                    title = data[1][0]
                    summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
                    summary_html = fetch_url(summary_url, timeout=8)
                    if summary_html:
                        summary_data = json.loads(summary_html)
                        if summary_data.get('extract'):
                            log.info(f"[Wikipedia] Found '{title}' ({lang})")
                            return {
                                'title': summary_data.get('title', ''),
                                'extract': summary_data['extract'],
                                'lang': lang
                            }
        except Exception as e:
            log.error(f"[Wikipedia] Error ({lang}): {e}")
    return None


def search_sneaker_sites(subject):
    """Scrape les sites sneakers : URLs directes + pages de recherche -> articles -> contenu"""
    import urllib.parse
    all_results = []
    slug = subject.lower().replace(' ', '-')
    query_encoded = urllib.parse.quote(subject)
    
    subject_lower = subject.lower()
    generic = ['retro', 'high', 'low', 'mid', 'og', 'sp', 'se', 'premium', 'men', 'women', 'mens', 'womens', 'the', 'a', 'x']
    keywords = [w for w in subject_lower.split() if w not in generic and len(w) > 1]
    
    # ── ÉTAPE 1 : Construire des URLs directes intelligentes ──
    direct_urls = []
    
    # Variantes de slug pour about.nike.com
    slug_parts = slug.split('-')
    
    # Slug complet et variantes
    direct_urls.append(f"https://about.nike.com/en/newsroom/releases/{slug}-official-images")
    
    # Slug simplifié (enlever les termes génériques)
    simple_words = [w for w in subject_lower.split() if w not in generic]
    simple_slug = '-'.join(simple_words)
    direct_urls.append(f"https://about.nike.com/en/newsroom/releases/{simple_slug}-official-images")
    
    # Variantes courtes
    if len(slug_parts) >= 2:
        for length in [3, 2]:
            short = '-'.join(slug_parts[:length])
            direct_urls.append(f"https://about.nike.com/en/newsroom/releases/{short}-official-images")
    
    # SneakerNews
    direct_urls.append(f"https://sneakernews.com/{slug}-release-date/")
    
    # Dédupliquer les URLs
    direct_urls = list(dict.fromkeys(direct_urls))
    
    for url in direct_urls:
        try:
            html = fetch_url(url, timeout=10)
            if html and len(html) > 5000:
                paragraphs = extract_text_from_html(html, min_length=60)
                relevant = [p for p in paragraphs if any(kw in p.lower() for kw in keywords[:5])]
                
                if relevant:
                    log.info(f"[Direct] {url[:60]} -> {len(relevant)} relevant paragraphs")
                    all_results.extend(relevant)
                    if len(all_results) >= 5:
                        break
        except Exception as e:
            log.error(f"[Direct] {url[:60]}: {e}")
    
    # ── ÉTAPE 2 : Pages de recherche -> liens d'articles -> scraper ──
    if len(all_results) < 3:
        search_pages = [
            f"https://sneakernews.com/?s={query_encoded}",
            f"https://hypebeast.com/search?s={query_encoded}",
        ]
        
        for search_url in search_pages:
            try:
                html = fetch_url(search_url, timeout=10)
                if not html:
                    continue
                
                article_urls = []
                all_links = re.findall(r'href="(https?://(?:sneakernews\.com|hypebeast\.com)/[^"]{20,})"', html)
                
                for link in all_links:
                    link_lower = link.lower()
                    match_count = sum(1 for kw in keywords if kw in link_lower)
                    if match_count >= 2 and '/search' not in link_lower and '/tag/' not in link_lower and '/author/' not in link_lower:
                        article_urls.append((match_count, link))
                
                article_urls.sort(key=lambda x: x[0], reverse=True)
                unique_urls = list(dict.fromkeys([u[1] for u in article_urls]))
                
                for article_url in unique_urls[:2]:
                    try:
                        article_html = fetch_url(article_url, timeout=10)
                        if article_html and len(article_html) > 5000:
                            paragraphs = extract_text_from_html(article_html, min_length=60)
                            relevant = [p for p in paragraphs if any(kw in p.lower() for kw in keywords[:5])]
                            if relevant:
                                log.info(f"[Article] {article_url[:60]} -> {len(relevant)} relevant paragraphs")
                                all_results.extend(relevant)
                    except Exception as e:
                        log.error(f"[Article] {article_url[:60]}: {e}")
                
                if len(all_results) >= 5:
                    break
            except Exception as e:
                log.error(f"[Search] {search_url[:60]}: {e}")
    
    # ── ÉTAPE 3 : JSON-LD et meta depuis nike.com ──
    if len(all_results) < 3:
        try:
            nike_search_url = f"https://www.nike.com/w?q={query_encoded}"
            html = fetch_url(nike_search_url, timeout=10)
            if html:
                json_ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
                for jld in json_ld:
                    try:
                        data = json.loads(jld)
                        desc = data.get('description', '')
                        if desc and len(desc) > 40 and any(kw in desc.lower() for kw in keywords[:3]):
                            all_results.append(desc)
                    except:
                        pass
        except Exception as e:
            log.error(f"[Nike search] {e}")
    
    return all_results


def search_brand_page(subject):
    """Scrape les pages officielles de la marque"""
    import urllib.parse
    s = subject.lower()
    results = []
    keywords = [w for w in s.split() if len(w) > 2 and w not in ['the', 'retro', 'high', 'low', 'mid', 'og', 'sp', 'se']]
    
    slug = subject.lower().replace(' ', '-')
    slug_clean = slug.replace('nike-', '').replace('adidas-', '').replace('new-balance-', '')
    query_encoded = urllib.parse.quote(subject)
    
    if 'nike' in s or 'jordan' in s or 'dunk' in s or 'force' in s or 'air max' in s or 'mind' in s:
        try:
            newsroom_url = "https://about.nike.com/en/newsroom/releases"
            html = fetch_url(newsroom_url, timeout=12)
            if html:
                all_links = re.findall(r'href="(/en/newsroom/releases/[^"]+)"', html)
                for link in all_links:
                    link_lower = link.lower()
                    match_count = sum(1 for kw in keywords if kw in link_lower)
                    if match_count >= 2:
                        full_url = f"https://about.nike.com{link}"
                        log.info(f"[Brand] Found newsroom article: {full_url}")
                        article_html = fetch_url(full_url, timeout=10)
                        if article_html and len(article_html) > 5000:
                            paragraphs = extract_text_from_html(article_html, min_length=60)
                            relevant = [p for p in paragraphs if any(kw in p.lower() for kw in keywords[:4])]
                            if relevant:
                                results.extend(relevant)
                                log.info(f"[Brand] about.nike.com article -> {len(relevant)} paragraphs")
                        if results:
                            break
        except Exception as e:
            log.error(f"[Brand] newsroom scrape: {e}")
        
        if not results:
            urls = [
                f"https://about.nike.com/en/newsroom/releases/nike-{slug_clean}-official-images",
                f"https://about.nike.com/en/newsroom/releases/{slug}-official-images",
                f"https://www.nike.com/a/nike-{slug_clean}-release-info",
                f"https://www.nike.com/a/{slug_clean}-release-info",
            ]
            for url in urls[:4]:
                try:
                    html = fetch_url(url, timeout=10)
                    if html and len(html) > 5000:
                        paragraphs = extract_text_from_html(html, min_length=60)
                        relevant = [p for p in paragraphs if any(kw in p.lower() for kw in keywords[:4])]
                        if relevant:
                            results.extend(relevant)
                            break
                except Exception as e:
                    log.error(f"[Brand] {url[:60]}: {e}")
    
    elif 'adidas' in s or 'samba' in s or 'campus' in s or 'gazelle' in s or 'yeezy' in s:
        urls = [f"https://news.adidas.com/search?q={query_encoded}"]
        for url in urls:
            try:
                html = fetch_url(url, timeout=10)
                if html and len(html) > 5000:
                    paragraphs = extract_text_from_html(html, min_length=60)
                    relevant = [p for p in paragraphs if any(kw in p.lower() for kw in keywords[:4])]
                    if relevant:
                        results.extend(relevant)
            except Exception as e:
                log.error(f"[Brand] {url[:60]}: {e}")
    
    return results


def do_web_research(subject, article_type):
    """Fait une recherche web via scraping direct des sites sneakers"""
    info = {
        'wikipedia': None,
        'search_results': [],
        'found': False
    }
    
    log.info(f"[Research] Starting for '{subject}' ({article_type})")
    
    # 1. Wikipedia
    wiki = search_wikipedia(subject)
    if wiki:
        info['wikipedia'] = wiki
        info['found'] = True
    
    # 2. Scraper les sites sneakers directement
    results = search_sneaker_sites(subject)
    
    # 3. Page officielle de la marque
    brand_results = search_brand_page(subject)
    results.extend(brand_results)
    
    # 4. Dédupliquer et nettoyer
    seen = set()
    clean_results = []
    for r in results:
        key = r[:80].lower()
        if key not in seen and len(r) > 40:
            seen.add(key)
            clean_results.append(r)
    
    if clean_results:
        info['search_results'] = clean_results[:15]
        info['found'] = True
    
    log.info(f"[Research] Done: wiki={'yes' if info['wikipedia'] else 'no'}, results={len(info['search_results'])}, found={info['found']}")
    return info
