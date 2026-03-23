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

# Cache WTN products for 30 min
_wtn_cache = None
_wtn_cache_time = 0
_WTN_CACHE_TTL = 1800


def _fetch_url(url, timeout=30):
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
    global _wtn_cache, _wtn_cache_time

    now = time.time()
    if _wtn_cache and (now - _wtn_cache_time) < _WTN_CACHE_TTL:
        log.info(f"[WTN] Cache hit: {len(_wtn_cache)} products")
        return _wtn_cache

    log.info("[WTN] Fetching sitemap-products.xml...")
    data = _fetch_url("https://wethenew.com/sitemap-products.xml", timeout=30)
    if not data:
        return None

    # Simple individual regex - reliable on all platforms
    urls = re.findall(r'<loc>(https://wethenew\.com/products/[^<]+)</loc>', data)
    titles = re.findall(r'<image:title>([^<]+)</image:title>', data)
    images = re.findall(r'<image:loc>([^<]+)</image:loc>', data)
    captions = re.findall(r'<image:caption>([^<]+)</image:caption>', data)

    log.info(f"[WTN] Parsed {len(urls)} URLs, {len(titles)} titles, {len(images)} images")

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
    for i, url in enumerate(urls):
        slug = url.split('/products/')[-1].lower()

        if any(ex in slug for ex in exclude_url_patterns):
            continue
        if 'gift' in slug or 'carte' in slug:
            continue

        title = html_mod.unescape(titles[i]).strip() if i < len(titles) else ''
        image = html_mod.unescape(images[i]).strip() if i < len(images) else ''
        caption = html_mod.unescape(captions[i]).strip() if i < len(captions) else ''

        # Extract SKU from caption
        sku = ''
        sku_match = re.search(r'[\s\-\u2013]([A-Z]{1,3}[0-9]{4,}-[0-9]{2,3})\s*$', caption)
        if not sku_match:
            sku_match = re.search(r'[\s\-\u2013]([A-Z]{1,3}[0-9]{5,})\s*$', caption)
        if sku_match:
            sku = sku_match.group(1)

        display_title = title or caption.rsplit(' - ', 1)[0]

        if display_title:
            sneakers.append({
                'url': url,
                'title': display_title,
                'sku': sku,
                'image': image,
            })

    log.info(f"[WTN] Filtered to {len(sneakers)} sneakers")

    _wtn_cache = sneakers
    _wtn_cache_time = time.time()
    return sneakers


@competitor_bp.route('/api/competitor/scan-wtn')
def api_scan_wtn():
    sneakers = _parse_wtn_sitemap()
    if sneakers is None:
        return jsonify({'error': 'Impossible de charger le sitemap WetTheNew'}), 500
    return jsonify({
        'products': sneakers,
        'count': len(sneakers),
        'cached': (time.time() - _wtn_cache_time) < 5,
    })
