"""
KP SHOES - Routes pages HTML
Sert les templates avec une barre de navigation commune injectee.
"""
import os
import re
from flask import Blueprint

pages_bp = Blueprint('pages', __name__)
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')


def _read_template(filename):
    path = os.path.join(TEMPLATE_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# -- Barre de navigation commune (style + markup) --
NAV_CSS = """
.kpnav{position:sticky;top:0;z-index:6000;display:flex;align-items:center;gap:2px;
  background:rgba(14,14,22,.92);backdrop-filter:blur(8px);
  border-bottom:1px solid #20202c;padding:0 16px;min-height:56px;flex-wrap:wrap}
.kpnav .kp-brand{font-weight:800;font-size:17px;color:#00ff88;letter-spacing:.5px;
  text-decoration:none;margin-right:16px;display:flex;align-items:center;gap:6px}
.kpnav a.kl,.kpnav span.kl{color:#c7c7d1;text-decoration:none;font-size:13px;font-weight:600;
  padding:8px 13px;border-radius:8px;transition:background .15s,color .15s;white-space:nowrap}
.kpnav a.kl:hover,.kpdd:hover>.kl{background:#1b1b27;color:#fff}
.kpnav a.kl.active{background:rgba(0,255,136,.12);color:#00ff88}
.kpnav .kp-sp{flex:1}
.kpdd{position:relative}
.kpdd>.kl{cursor:pointer}
.kpdd-menu{display:none;position:absolute;top:100%;left:0;margin-top:4px;background:#15151f;
  border:1px solid #2a2a38;border-radius:12px;padding:6px;min-width:210px;
  box-shadow:0 14px 40px rgba(0,0,0,.55)}
.kpdd:hover .kpdd-menu{display:block}
.kpdd-menu a{display:block;color:#c7c7d1;text-decoration:none;font-size:13px;padding:10px 12px;border-radius:8px}
.kpdd-menu a:hover{background:rgba(0,255,136,.12);color:#00ff88}
@media(max-width:640px){.kpnav{padding:6px 10px}.kpnav a.kl,.kpnav span.kl{padding:6px 9px;font-size:12px}}
"""


def _nav(active):
    def c(key):
        return "kl active" if key == active else "kl"
    return f"""
<nav class="kpnav">
  <a class="kp-brand" href="/">&#128095; KP SHOES</a>
  <a class="{c('produits')}" href="/">&#128230; Produits</a>
  <a class="{c('collections')}" href="/collections">&#128450;&#65039; Collections</a>
  <a class="{c('scanner')}" href="/image-scanner">&#128247; Scanner images</a>
  <a class="{c('descriptions')}" href="/description-scanner">&#128221; Scanner descriptions</a>
  <div class="kpdd">
    <span class="{c('outils')}">&#128736;&#65039; Outils &#9662;</span>
    <div class="kpdd-menu">
      <a href="/product-finder">&#128269; Product Finder</a>
      <a href="/fix-handles">&#128279; Fix Handles (URLs)</a>
      <a href="/fix-brand-case">&#128481;&#65039; Casse des marques</a>
    </div>
  </div>
  <span class="kp-sp"></span>
</nav>
"""


def render_page(filename, active=None, **replacements):
    """Lit un template, applique les remplacements, et injecte la nav commune
    (en retirant l'ancien header .hd de la page pour eviter les doublons)."""
    html = _read_template(filename)
    for key, val in replacements.items():
        html = html.replace(key, val)
    html = html.replace('</head>', f'<style>{NAV_CSS}</style></head>', 1)
    html = re.sub(r'<header class="hd">.*?</header>', '', html, count=1, flags=re.DOTALL)
    html = html.replace('<body>', '<body>\n' + _nav(active), 1)
    return html


@pages_bp.route('/')
def home():
    return render_page('home.html', 'produits')


@pages_bp.route('/collections')
def collections_page():
    return render_page('collections.html', 'collections')


@pages_bp.route('/image-scanner')
def image_scanner_page():
    return render_page('image_scanner.html', 'scanner')


@pages_bp.route('/description-scanner')
def description_scanner_page():
    return render_page('description_scanner.html', 'descriptions')


@pages_bp.route('/product-finder')
def product_finder_page():
    return render_page('product_finder.html', 'outils')


@pages_bp.route('/fix-handles')
def fix_handles_page():
    return render_page('fix_handles.html', 'outils')


@pages_bp.route('/fix-brand-case')
def fix_brand_case_page():
    return render_page('fix_brand_case.html', 'outils')


@pages_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    from config import SHOP
    return render_page('product.html', 'produits',
                       PRODUCT_ID_PLACEHOLDER=str(product_id),
                       SHOP_PLACEHOLDER=SHOP)
