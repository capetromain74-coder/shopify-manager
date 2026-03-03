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
    r = shopify_request(f"products/{pid}.json")
    if not r: return jsonify({"error": "err"}), 404
    p = r["product"]
    cols = get_collections()
    update_seo_field(pid, "meta_title", generate_meta_title(p))
    time.sleep(0.3)
    update_seo_field(pid, "meta_description", generate_meta_description(p))
    time.sleep(0.3)
    update_seo_field(pid, "body_html", generate_body_html(p, cols))
    time.sleep(0.3)
    fix_product_images(pid)
    return jsonify({"success": True})

@seo_bp.route("/api/seo/update", methods=["POST"])
def api_update_seo():
    pid = request.json.get("product_id")
    fields = request.json.get("fields", [])
    if not fields: return jsonify({"error": "No fields"}), 400
    r = shopify_request(f"products/{pid}.json")
    if not r: return jsonify({"error": "err"}), 404
    p = r["product"]
    cols = get_collections()
    for field in fields:
        if field == "meta_title": update_seo_field(pid, "meta_title", generate_meta_title(p))
        elif field == "meta_description": update_seo_field(pid, "meta_description", generate_meta_description(p))
        elif field == "body_html": update_seo_field(pid, "body_html", generate_body_html(p, cols))
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

@seo_bp.route("/api/progress")
def api_progress():
    return jsonify(get_task_progress())
