"""KP SHOES - Routes API SEO"""
import time
from threading import Thread
from flask import Blueprint, jsonify, request
from services.shopify import shopify_request, get_collections, get_task_progress, set_task_progress
from services.seo_engine import generate_meta_title, generate_meta_description, generate_body_html, update_seo_field
from services.image_manager import fix_product_images
seo_bp = Blueprint("seo", __name__)
@seo_bp.route("/api/seo/apply", methods=["POST"])
def api_apply_seo():
    pid = request.json.get("product_id")
    goat_slug = request.json.get("goat_slug", "")
    r = shopify_request(f"products/{pid}.json")
    if not r: return jsonify({"error": "err"}), 404
    p = r["product"]
    cols = get_collections()
    update_seo_field(pid, "meta_title", generate_meta_title(p))
    time.sleep(0.3)
    update_seo_field(pid, "meta_description", generate_meta_description(p, goat_slug=goat_slug))
    time.sleep(0.3)
    update_seo_field(pid, "body_html", generate_body_html(p, cols, goat_slug=goat_slug))
    time.sleep(0.3)
    fix_product_images(pid)
    return jsonify({"success": True})
@seo_bp.route("/api/seo/update", methods=["POST"])
def api_update_seo():
    pid = request.json.get("product_id")
    fields = request.json.get("fields", [])
    goat_slug = request.json.get("goat_slug", "")
    if not fields: return jsonify({"error": "No fields"}), 400
    r = shopify_request(f"products/{pid}.json")
    if not r: return jsonify({"error": "err"}), 404
    p = r["product"]
    cols = get_collections()
    for field in fields:
        if field == "meta_title": update_seo_field(pid, "meta_title", generate_meta_title(p))
        elif field == "meta_description": update_seo_field(pid, "meta_description", generate_meta_description(p, goat_slug=goat_slug))
        elif field == "body_html": update_seo_field(pid, "body_html", generate_body_html(p, cols, goat_slug=goat_slug))
        elif field == "images_seo": fix_product_images(pid)
        time.sleep(0.3)
    return jsonify({"success": True, "updated": fields})
@seo_bp.route("/api/seo/batch", methods=["POST"])
def api_batch_seo():
    pids = request.json.get("product_ids", [])
    def run():
        set_task_progress(running=True, current=0, total=len(pids), message="Demarrage...")
        cols = get_collections()
        for i, pid in enumerate(pids):
            set_task_progress(current=i + 1)
            r = shopify_request(f"products/{pid}.json")
            if r and "product" in r:
                p = r["product"]
                set_task_progress(message=p.get("title", "")[:30])
                update_seo_field(pid, "meta_title", generate_meta_title(p))
                time.sleep(0.3)
                update_seo_field(pid, "meta_description", generate_meta_description(p))
                time.sleep(0.3)
                update_seo_field(pid, "body_html", generate_body_html(p, cols))
            time.sleep(0.5)
        set_task_progress(running=False, current=len(pids), total=len(pids), message="Termine!")
    Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})
@seo_bp.route("/api/seo/fix-titles", methods=["POST"])
def api_fix_titles():
    """Met a jour UNIQUEMENT les meta titles de tous les produits.
    Rapide, pas d'appel API Anthropic, juste Shopify.
    Utilise since_id pour paginer sans timeout."""
    def run():
        set_task_progress(running=True, current=0, total=0, message="Chargement des produits...")
        since_id = 0
        all_products = []
        # Charger tous les produits par pagination since_id
        while True:
            r = shopify_request(f"products.json?limit=250&since_id={since_id}&fields=id,title,variants")
            if not r or not r.get("products"):
                break
            batch = r["products"]
            all_products.extend(batch)
            since_id = batch[-1]["id"]
            set_task_progress(message=f"Chargement... {len(all_products)} produits")
            time.sleep(0.3)
            if len(batch) < 250:
                break
        set_task_progress(total=len(all_products), message=f"{len(all_products)} produits a traiter")
        updated = 0
        skipped = 0
        for i, p in enumerate(all_products):
            set_task_progress(current=i + 1, message=p.get("title", "")[:40])
            new_title = generate_meta_title(p)
            # Toujours appliquer pour ecraser l'ancien format avec | KP SHOES
            try:
                update_seo_field(p["id"], "meta_title", new_title)
                updated += 1
            except Exception:
                skipped += 1
            time.sleep(0.4)
        set_task_progress(running=False, current=len(all_products), total=len(all_products),
                          message=f"Termine! {updated} mis a jour, {skipped} erreurs")
    Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "message": "Fix titles demarre en arriere-plan"})
@seo_bp.route("/api/seo/fix-single-title", methods=["POST"])
def api_fix_single_title():
    """Corrige le titre d'un seul produit + regenere tout le SEO (meta title, meta desc, body html)."""
    data = request.json or {}
    pid = data.get("product_id")
    new_title = data.get("new_title", "").strip()
    regen_seo = data.get("regen_seo", True)
    if not pid or not new_title:
        return jsonify({"error": "product_id et new_title requis"}), 400
    try:
        # 1. Update product title on Shopify
        shopify_request(f'products/{pid}.json', 'PUT', {
            'product': {'id': pid, 'title': new_title}
        })
        time.sleep(0.3)
        # 2. Update meta title (juste le nom, pas de | KP SHOES)
        new_meta = new_title if len(new_title) <= 60 else new_title[:57] + '...'
        update_seo_field(pid, "meta_title", new_meta)
        time.sleep(0.3)
        # 3. Regenerer meta description + body html avec le nouveau titre
        if regen_seo:
            r = shopify_request(f"products/{pid}.json")
            if r and "product" in r:
                p = r["product"]
                cols = get_collections()
                update_seo_field(pid, "meta_description", generate_meta_description(p))
                time.sleep(0.3)
                update_seo_field(pid, "body_html", generate_body_html(p, cols))
        return jsonify({"success": True, "new_title": new_title})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@seo_bp.route("/api/seo/fix-brand-case", methods=["POST"])
def api_fix_brand_case():
    """Corrige la casse d'une marque dans les titres produits + meta title.
    Ex: ASICS -> Asics, remplace dans le titre Shopify et re-genere le meta title.
    Body: {"find": "ASICS", "replace": "Asics", "product_ids": [123, 456, ...]}
    Si product_ids est vide, scanne tous les produits."""
    data = request.json or {}
    find_str = data.get("find", "").strip()
    replace_str = data.get("replace", "").strip()
    product_ids = data.get("product_ids", [])
    if not find_str or not replace_str:
        return jsonify({"error": "find et replace requis"}), 400
    def run():
        set_task_progress(running=True, current=0, total=0, message="Chargement des produits...")
        # Charger les produits cibles
        targets = []
        if product_ids:
            for pid in product_ids:
                r = shopify_request(f"products/{pid}.json?fields=id,title")
                if r and "product" in r:
                    p = r["product"]
                    if find_str in p.get("title", ""):
                        targets.append(p)
                time.sleep(0.2)
        else:
            since_id = 0
            while True:
                r = shopify_request(f"products.json?limit=250&since_id={since_id}&fields=id,title")
                if not r or not r.get("products"):
                    break
                for p in r["products"]:
                    if find_str in p.get("title", ""):
                        targets.append(p)
                since_id = r["products"][-1]["id"]
                set_task_progress(message=f"Scan... {len(targets)} produits avec '{find_str}'")
                time.sleep(0.3)
                if len(r["products"]) < 250:
                    break
        set_task_progress(total=len(targets), message=f"{len(targets)} produits a corriger")
        updated = 0
        errors = 0
        for i, p in enumerate(targets):
            set_task_progress(current=i + 1, message=p.get("title", "")[:40])
            old_title = p["title"]
            new_title = old_title.replace(find_str, replace_str)
            if new_title == old_title:
                continue
            try:
                # 1. Corriger le titre produit sur Shopify
                shopify_request(f'products/{p["id"]}.json', 'PUT', {
                    'product': {'id': p['id'], 'title': new_title}
                })
                time.sleep(0.3)
                # 2. Re-generer le meta title avec le nouveau titre
                new_meta = new_title if len(new_title) <= 60 else new_title[:57] + '...'
                update_seo_field(p["id"], "meta_title", new_meta)
                updated += 1
            except Exception:
                errors += 1
            time.sleep(0.4)
        set_task_progress(running=False, current=len(targets), total=len(targets),
                          message=f"Termine! {updated} corriges, {errors} erreurs")
    Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "message": f"Fix brand case demarre en arriere-plan"})
@seo_bp.route("/api/seo/preview-brand-case")
def api_preview_brand_case():
    """Preview: liste les produits qui contiennent une string dans leur titre.
    Usage: ?find=ASICS"""
    find_str = request.args.get("find", "").strip()
    if not find_str:
        return jsonify({"error": "?find= requis"}), 400
    matches = []
    since_id = 0
    while True:
        r = shopify_request(f"products.json?limit=250&since_id={since_id}&fields=id,title,images,variants")
        if not r or not r.get("products"):
            break
        for p in r["products"]:
            if find_str in p.get("title", ""):
                sku = p["variants"][0].get("sku", "") if p.get("variants") else ""
                img = p["images"][0]["src"] if p.get("images") else ""
                matches.append({"id": p["id"], "title": p["title"], "sku": sku, "image": img})
        since_id = r["products"][-1]["id"]
        if len(r["products"]) < 250:
            break
        time.sleep(0.3)
    return jsonify({"find": find_str, "count": len(matches), "products": matches})
@seo_bp.route("/api/progress")
def api_progress():
    @seo_bp.route('/api/seo/fix-handle', methods=['POST'])
def api_fix_handle():
    """Corrige le handle (URL) d'un produit pour correspondre au titre."""
    data = request.get_json()
    pid = data.get('product_id')
    new_handle = data.get('handle', '').strip()
    if not pid or not new_handle:
        return jsonify({'error': 'product_id et handle requis'}), 400
    try:
        r = shopify_request(f'products/{pid}.json', 'PUT', {
            'product': {'id': pid, 'handle': new_handle}
        })
        if r:
            return jsonify({'success': True, 'handle': new_handle})
        return jsonify({'error': 'Shopify error'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(get_task_progress())
