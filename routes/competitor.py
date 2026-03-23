"""KP SHOES - Routes API Competitor Scanning"""
import re
import time
import logging
import ssl
from urllib.request import Request, urlopen
from flask import Blueprint, jsonify, request
import html as html_mod

log = logging.getLogger("kpshoes.competitor")
competitor_bp = Blueprint("competitor", __name__)

# Cache WTN products for 30 min to avoid re-scraping
_wtn_cache = None
_wtn_cache_time = 0
_WTN_CACHE_TTL = 1800  # 30 min


def _fetch_url(url, timeout=20):
    """Fetch URL with headers"""
    try:
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/xml,application/xml,*/*',
        })
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urlopen(req, context=ctx, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        log.error(f"[Competitor] Fetch error: {e}")
        return None


def _parse_wtn_sitemap():
    """Parse WetTheNew product sitemap and return sneakers only."""
    global _wtn_cache, _wtn_cache_time

    now = time.time()
    if _wtn_cache and (now - _wtn_cache_time) < _WTN_CACHE_TTL:
        log.info(f"[WTN] Cache hit: {len(_wtn_cache)} products")
        return _wtn_cache

    log.info("[WTN] Fetching sitemap-products.xml...")
    data = _fetch_url("https://wethenew.com/sitemap-products.xml", timeout=30)
    if not data:
        return None

    # Parse all products from sitemap
    products = re.findall(
        r'<url><loc>(.*?)</loc>.*?(?:<image:image><image:loc>(.*?)</image:loc>)?.*?'
        r'(?:<image:caption>(.*?)</image:caption>)?.*?(?:<image:title>(.*?)</image:title>)?.*?</url>',
        data, re.DOTALL
    )

    if not products:
        # Fallback: simpler regex
        urls = re.findall(r'<loc>(https://wethenew\.com/products/[^<]+)</loc>', data)
        titles = re.findall(r'<image:title>([^<]+)</image:title>', data)
        images = re.findall(r'<image:loc>([^<]+)</image:loc>', data)
        captions = re.findall(r'<image:caption>([^<]+)</image:caption>', data)
        products = list(zip(
            urls,
            images + [''] * (len(urls) - len(images)),
            captions + [''] * (len(urls) - len(captions)),
            titles + [''] * (len(urls) - len(titles))
        ))

    log.info(f"[WTN] Parsed {len(products)} total products from sitemap")

    # Filter: exclude clothing, accessories, gift cards
    exclude_url_patterns = [
        'hoodie', 'sweatshirt', 'sweatpant', 't-shirt', 'tee-', '-tee-',
        'crewneck', 'jacket-', 'pants', 'jogger', 'polo-', 'shorts',
        'beanie', 'cap-', '-cap-', 'hat-', '-hat-', 'bag-', 'backpack', 'socks',
        'boxers', 'necklace', 'wallet', 'belt-', 'gift-card', 'carte-cadeau',
        'jersey-', 'vest-', '-vest-', 'skirt', 'dress', 'legging',
        'trouser', 'cardigan', 'sweater-', 'knit-', 'fleece-',
        'puffer-', 'anorak', 'workshirt', 'work-shirt', 'overshirt',
    ]

    sneakers = []
    for item in products:
        url = item[0] if len(item) > 0 else ''
        image = item[1] if len(item) > 1 else ''
        caption = item[2] if len(item) > 2 else ''
        title = item[3] if len(item) > 3 else ''

        if not url or '/products/' not in url:
            continue

        slug = url.split('/products/')[-1].lower()

        # Skip non-sneaker URLs
        if any(ex in slug for ex in exclude_url_patterns):
            continue

        # Skip gift cards
        if 'gift' in slug or 'carte' in slug:
            continue

        title_clean = html_mod.unescape(title).strip() if title else ''
        caption_clean = html_mod.unescape(caption).strip() if caption else ''
        image_clean = html_mod.unescape(image).strip() if image else ''

        # Try extract SKU from caption (pattern: - XX1234-567 at the end)
        sku = ''
        sku_match = re.search(r'[\s\-–]([A-Z]{1,3}[0-9]{4,}-[0-9]{2,3})\s*$', caption_clean)
        if not sku_match:
            sku_match = re.search(r'[\s\-–]([A-Z]{1,3}[0-9]{5,})\s*$', caption_clean)
        if sku_match:
            sku = sku_match.group(1)

        # Use caption as title fallback (often more complete)
        display_title = title_clean or caption_clean.rsplit(' - ', 1)[0].rsplit(' &#45; ', 1)[0]

        if display_title:
            sneakers.append({
                'url': url,
                'title': display_title,
                'sku': sku,
                'image': image_clean,
            })

    log.info(f"[WTN] Filtered to {len(sneakers)} sneakers (excluded {len(products) - len(sneakers)} non-sneakers)")

    # Cache results
    _wtn_cache = sneakers
    _wtn_cache_time = time.time()

    return sneakers


@competitor_bp.route('/api/competitor/scan-wtn')
def api_scan_wtn():
    """Charge et retourne le catalogue sneakers WetTheNew depuis leur sitemap."""
    sneakers = _parse_wtn_sitemap()
    if sneakers is None:
        return jsonify({'error': 'Impossible de charger le sitemap WetTheNew'}), 500
    return jsonify({
        'products': sneakers,
        'count': len(sneakers),
        'cached': (time.time() - _wtn_cache_time) < 5,  # True if served from cache
    })
