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
@seo_bp.route("/api/progress")
def api_progress():
    return jsonify(get_task_progress())
