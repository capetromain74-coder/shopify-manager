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
/* ===== Theme KP SHOES — sobre, facon Apple ===== */
:root{--kp-bg:#f5f5f7;--kp-card:#fff;--kp-fill:#f2f2f7;--kp-line:#e5e5ea;--kp-line2:#d2d2d7;
  --kp-text:#1d1d1f;--kp-text2:#6e6e73;--kp-text3:#86868b;--kp-blue:#0071e3;--kp-blue-h:#0077ed;
  --kp-green:#248a3d;--kp-red:#d70015;--kp-orange:#b25000;
  --kp-r:14px;--kp-r-lg:18px;--kp-shadow:0 1px 2px rgba(0,0,0,.04),0 2px 10px rgba(0,0,0,.04);
  --kp-shadow-h:0 2px 6px rgba(0,0,0,.06),0 10px 30px rgba(0,0,0,.08)}
html{-webkit-text-size-adjust:100%}
body{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Helvetica,Arial,sans-serif!important;
  background:var(--kp-bg)!important;color:var(--kp-text)!important;-webkit-font-smoothing:antialiased;letter-spacing:-.01em}
a{color:var(--kp-blue)}
::selection{background:rgba(0,113,227,.18)}

/* --- Navigation --- */
.kpnav{position:sticky;top:0;z-index:6000;display:flex;align-items:center;gap:4px;height:52px;padding:0 24px;
  background:rgba(255,255,255,.78);backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);
  border-bottom:1px solid rgba(0,0,0,.08)}
.kpnav .kp-brand{font-weight:600;font-size:17px;color:var(--kp-text);text-decoration:none;margin-right:28px;letter-spacing:-.02em}
.kpnav .kl{color:var(--kp-text2);text-decoration:none;font-size:14px;padding:8px 12px;border-radius:8px;white-space:nowrap;cursor:pointer;transition:color .15s}
.kpnav .kl:hover{color:var(--kp-text)}
.kpnav .kl.active{color:var(--kp-text);font-weight:600}
.kpnav .kp-sp{flex:1}
.kpdd{position:relative}
.kpdd-menu{display:none;position:absolute;top:100%;left:0;padding:6px;min-width:220px;background:#fff;border-radius:12px;
  box-shadow:0 10px 40px rgba(0,0,0,.12),0 0 0 1px rgba(0,0,0,.05)}
.kpdd:hover .kpdd-menu{display:block}
.kpdd-menu a{display:block;padding:9px 12px;border-radius:8px;color:var(--kp-text);text-decoration:none;font-size:14px}
.kpdd-menu a:hover{background:var(--kp-fill)}
.kpdd-menu small{display:block;color:var(--kp-text3);font-size:12px;margin-top:1px}

/* --- Titre de page (identique sur toutes les pages) --- */
.page-head{max-width:1200px;margin:0 auto;padding:40px 24px 0}
.page-head h1{font-size:34px;font-weight:700;letter-spacing:-.03em;color:var(--kp-text)}
.page-head p{color:var(--kp-text2);font-size:15px;margin-top:6px}
.hero{background:transparent!important;box-shadow:none!important;padding:12px 0 6px!important}
.hero h1{font-size:34px!important;font-weight:700!important;letter-spacing:-.03em}
.hero p{font-size:15px!important}

/* --- Mise en page --- */
.main{max-width:1200px!important;margin:0 auto!important;padding:28px 24px 60px!important}
.stats{max-width:1200px;margin:0 auto!important;padding:28px 24px 0!important;gap:12px!important;background:transparent!important;
  display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))}
.st{background:var(--kp-card)!important;border:none!important;border-radius:var(--kp-r-lg)!important;box-shadow:var(--kp-shadow);
  padding:18px 20px!important;text-align:left!important;min-width:0!important}
.st .v{font-size:30px!important;font-weight:600!important;color:var(--kp-text)!important;letter-spacing:-.03em;line-height:1.1}
.st .l{font-size:12px!important;color:var(--kp-text2)!important;margin-top:6px!important;letter-spacing:.01em;font-weight:500}
.step,.section,.hero,.results-bar,.seo-box,.meta-box,.goat-section,.preview-box,.detail-section{background:var(--kp-card)!important;
  border:none!important;border-radius:var(--kp-r-lg)!important;box-shadow:var(--kp-shadow)}
.step,.section,.hero{padding:22px 24px!important;margin-bottom:16px!important}
.step h3,.section-title,.hero h1,h1,h2,h3{color:var(--kp-text)!important;letter-spacing:-.02em}
.hero h1{background:none!important;-webkit-text-fill-color:currentColor!important;font-weight:600!important}
.step p,.hero p{color:var(--kp-text2)!important}

/* --- Boutons : une seule couleur d'accent, le reste en gris --- */
.btn,.btn-sm,.btn-scan,.btn-fix,.btn-sel,.btn-o,.btn-g,.btn-goat,.btn-filter,.filter-btn,.load-more,.btn-apply{
  background:#e8e8ed!important;color:var(--kp-text)!important;border:none!important;border-radius:980px!important;
  font-weight:500!important;font-size:14px!important;font-family:inherit!important;cursor:pointer;
  transition:background .15s,transform .1s!important;box-shadow:none!important;filter:none!important;text-shadow:none!important}
.btn:hover,.btn-sm:hover,.btn-scan:hover,.btn-fix:hover,.btn-sel:hover,.btn-o:hover,.btn-g:hover,.filter-btn:hover{background:#dcdce1!important;transform:none!important}
.btn-sm{padding:6px 14px!important;font-size:13px!important}
.btn-p,.btn-primary,#corBtn,#bulkGoatBtn,#btnLoad,#btnScan,#btnApplyAll,.btn-apply-img,.btn-apply,.btn-fix,.btn-goat{
  background:var(--kp-blue)!important;color:#fff!important}
.btn-p:hover,.btn-primary:hover,#corBtn:hover,#bulkGoatBtn:hover,#btnLoad:hover,#btnScan:hover,#btnApplyAll:hover,.btn-apply-img:hover,.btn-fix:hover{background:var(--kp-blue-h)!important}
.btn-ghost{background:transparent!important;color:var(--kp-blue)!important}
.btn-ghost:hover{background:rgba(0,113,227,.08)!important}
.btn:disabled,.btn-sm:disabled,button:disabled{opacity:.45!important;cursor:default}
.filter-btn.active,.btn-filter.active{background:var(--kp-text)!important;color:#fff!important}

/* --- Champs --- */
input[type=text],input[type=search],input[type=number],input:not([type]),select,textarea,.search,.filter{
  background:#fff!important;color:var(--kp-text)!important;border:1px solid var(--kp-line2)!important;border-radius:10px!important;
  font-family:inherit!important;font-size:14px!important}
.search,.filter{padding:10px 14px!important}
input:focus,select:focus,textarea:focus{outline:none!important;border-color:var(--kp-blue)!important;box-shadow:0 0 0 4px rgba(0,113,227,.15)!important}
input[type=checkbox],input[type=radio]{accent-color:var(--kp-blue)!important}

/* --- Cartes produit --- */
.card{background:var(--kp-card)!important;border:none!important;border-radius:var(--kp-r-lg)!important;box-shadow:var(--kp-shadow)!important;
  overflow:hidden;transition:box-shadow .2s,transform .2s!important}
.card:hover{box-shadow:var(--kp-shadow-h)!important;transform:translateY(-2px)!important}
.card img,.main-img,.thumb{background:#fff!important}
.card-title{color:var(--kp-text)!important;font-weight:500!important}
.card-sku{color:var(--kp-text3)!important}
.card.has-new,.card.selected{box-shadow:0 0 0 2px var(--kp-blue),var(--kp-shadow)!important}
.card-actions{border-top:1px solid var(--kp-line)!important}

/* --- Pastilles de statut --- */
.badge,.card-badge,.lvl{border-radius:980px!important;font-weight:500!important;font-size:11px!important;letter-spacing:0!important}
.badge.excellent,.badge.good,.badge-new,.badge-ok,.badge-done{background:#e9f6ec!important;color:var(--kp-green)!important}
.badge.warning,.badge-scan,.lvl-basique,.badge-diff{background:#fff4e5!important;color:var(--kp-orange)!important}
.badge.poor,.badge-err,.lvl-vide{background:#fdecec!important;color:var(--kp-red)!important}
.badge-wait,.badge-same{background:var(--kp-fill)!important;color:var(--kp-text2)!important}

/* --- Messages, progression, chargement --- */
.msg{background:#fff!important;color:var(--kp-text)!important;border:none!important;border-radius:12px!important;box-shadow:var(--kp-shadow)}
.msg.ok{color:var(--kp-green)!important}.msg.err{color:var(--kp-red)!important}
.prog-bar{background:#e8e8ed!important;height:6px!important;border-radius:3px!important}
.prog-fill{background:var(--kp-blue)!important}
.spinner,.spinner-sm{border-color:var(--kp-line)!important;border-top-color:var(--kp-blue)!important}
.loading{color:var(--kp-text2)!important}

/* --- Fenetres (modales) --- */
.modal-bg,.detail-modal{background:rgba(0,0,0,.28)!important;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.modal-box,.detail-box,.goat-content{background:#fff!important;color:var(--kp-text)!important;border:none!important;border-radius:20px!important;
  box-shadow:0 30px 80px rgba(0,0,0,.2)!important}
.modal-close,.detail-close,.goat-close{color:var(--kp-text3)!important}
.opt-label{color:var(--kp-text2)!important;font-weight:600!important;font-size:12px!important;letter-spacing:.02em}
.opt-radio,.opt-check,.opt-sub{background:var(--kp-fill)!important;border:none!important;border-radius:10px!important;color:var(--kp-text)!important}
#bulkGoatLog,#corLog,.log{background:var(--kp-fill)!important;border-radius:10px!important;padding:10px 12px!important;
  font-family:"SF Mono",ui-monospace,Menlo,monospace!important;font-size:12px!important}
.toast{background:var(--kp-text)!important;color:#fff!important;border-radius:12px!important}

@media(max-width:700px){.kpnav{padding:0 12px;overflow-x:auto}.kpnav .kp-brand{margin-right:12px}.main{padding:20px 14px 40px!important}
  .stats{padding:20px 14px 0!important;grid-template-columns:repeat(2,minmax(0,1fr))!important}}
"""


def _nav(active):
    def c(*keys):
        return "kl active" if active in keys else "kl"
    return f"""
<nav class="kpnav">
  <a class="kp-brand" href="/">KP SHOES</a>
  <a class="{c('produits')}" href="/">Produits</a>
  <a class="{c('collections')}" href="/collections">Collections</a>
  <div class="kpdd">
    <span class="{c('scanner', 'descriptions')}">Scanners &#9662;</span>
    <div class="kpdd-menu">
      <a href="/image-scanner">Nouvelles photos<small>Fiches qui peuvent recevoir plus de photos GOAT</small></a>
      <a href="/description-scanner">Descriptions<small>Fiches dont la description peut &ecirc;tre compl&eacute;t&eacute;e</small></a>
    </div>
  </div>
  <div class="kpdd">
    <span class="{c('outils')}">Outils &#9662;</span>
    <div class="kpdd-menu">
      <a href="/product-finder">Produits manquants<small>Comparer avec le catalogue WetTheNew</small></a>
      <a href="/fix-handles">URLs des fiches<small>Corriger les handles</small></a>
      <a href="/fix-brand-case">Casse des marques<small>Uniformiser l&rsquo;&eacute;criture des marques</small></a>
    </div>
  </div>
  <span class="kp-sp"></span>
</nav>
"""


def render_page(filename, active=None, title=None, subtitle=None, **replacements):
    """Lit un template, applique les remplacements, et injecte la nav commune
    (en retirant l'ancien header .hd de la page pour eviter les doublons)."""
    html = _read_template(filename)
    for key, val in replacements.items():
        html = html.replace(key, val)
    html = html.replace('</head>', f'<style>{NAV_CSS}</style></head>', 1)
    html = re.sub(r'<header class="hd">.*?</header>', '', html, count=1, flags=re.DOTALL)
    head = ''
    if title:
        head = f'<header class="page-head"><h1>{title}</h1>' + (f'<p>{subtitle}</p>' if subtitle else '') + '</header>'
    html = html.replace('<body>', '<body>\n' + _nav(active) + head, 1)
    return html


@pages_bp.route('/')
def home():
    return render_page('home.html', 'produits')


@pages_bp.route('/collections')
def collections_page():
    return render_page('collections.html', 'collections', 'Collections', 'Le r&eacute;f&eacute;rencement de tes collections.')


@pages_bp.route('/image-scanner')
def image_scanner_page():
    return render_page('image_scanner.html', 'scanner', 'Nouvelles photos', 'Les fiches qui peuvent recevoir plus de photos GOAT.')


@pages_bp.route('/description-scanner')
def description_scanner_page():
    return render_page('description_scanner.html', 'descriptions', 'Descriptions', 'Les fiches dont la description peut &ecirc;tre compl&eacute;t&eacute;e.')


@pages_bp.route('/product-finder')
def product_finder_page():
    return render_page('product_finder.html', 'outils')


@pages_bp.route('/fix-handles')
def fix_handles_page():
    return render_page('fix_handles.html', 'outils')


@pages_bp.route('/fix-brand-case')
def fix_brand_case_page():
    return render_page('fix_brand_case.html', 'outils', 'Casse des marques', 'Uniformiser l&rsquo;&eacute;criture des marques dans les titres.')


@pages_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    from config import SHOP
    return render_page('product.html', 'produits',
                       PRODUCT_ID_PLACEHOLDER=str(product_id),
                       SHOP_PLACEHOLDER=SHOP)
