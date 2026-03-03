"""KP SHOES - Routes API SEO"""
import time
import logging
from threading import Thread
from flask import Blueprint, jsonify, request
from services.shopify import shopify_request, get_collections, get_task_progress, set_task_progress
from services.seo_engine import generate_meta_title, generate_meta_description, generate_body_html, update_seo_field
from services.image_manager import fix_product_images

log = logging.getLogger('kpshoes.seo_routes')
seo_bp = Blueprint("seo", __name__)

@seo_bp.route("/api/seo/apply", methods=["POST"])
def api_apply_seo():
    pid = request.json.get("product_id")
    r = shopify_request(f"products/{pid}.json")
    if not r: return jsonify({"error": "err"}), 404
    p = r["product"]
    cols = get_collections()
    
    new_title = generate_meta_title(p)
    update_seo_field(pid, "meta_title", new_title)
    time.sleep(0.3)
    
    new_desc = generate_meta_description(p)
    update_seo_field(pid, "meta_description", new_desc)
    time.sleep(0.3)
    
    new_body = generate_body_html(p, cols)
    update_seo_field(pid, "body_html", new_body)
    time.sleep(0.3)
    
    fix_product_images(pid)
    
    # Detecter la source utilisee pour la description
    body_lower = new_body.lower()
    source = "goat" if ("tige en" in body_lower or "tons " in body_lower or "outsole" in body_lower) else "fallback"
    
    return jsonify({
        "success": True,
        "source": source,
        "preview": new_body[:300] + "..." if len(new_body) > 300 else new_body
    })

@seo_bp.route("/api/seo/update", methods=["POST"])
def api_update_seo():
    pid = request.json.get("product_id")
    fields = request.json.get("fields", [])
    if not fields: return jsonify({"error": "No fields"}), 400
    r = shopify_request(f"products/{pid}.json")
    if not r: return jsonify({"error": "err"}), 404
    p = r["product"]
    cols = get_collections()
    results = {}
    for field in fields:
        if field == "meta_title":
            val = generate_meta_title(p)
            update_seo_field(pid, "meta_title", val)
            results["meta_title"] = val
        elif field == "meta_description":
            val = generate_meta_description(p)
            update_seo_field(pid, "meta_description", val)
            results["meta_description"] = val
        elif field == "body_html":
            val = generate_body_html(p, cols)
            update_seo_field(pid, "body_html", val)
            results["body_html_preview"] = val[:300]
        elif field == "images_seo":
            fix_product_images(pid)
            results["images_seo"] = "done"
        time.sleep(0.3)
    return jsonify({"success": True, "updated": fields, "results": results})

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

@seo_bp.route("/api/seo/test-goat")
def api_test_goat():
    """Endpoint de test : verifie si GOAT retourne des donnees pour un SKU."""
    sku = request.args.get("sku", "")
    if not sku:
        return jsonify({"error": "Parametre ?sku= requis"}), 400
    
    try:
        from services.goat_client import search as goat_search, get_product_details as goat_get_details
        from services.seo_engine import build_goat_description, extract_colorway
        
        # 1. Chercher le produit
        product = goat_search(sku)
        if not product or not product.get('slug'):
            return jsonify({"found": False, "step": "search", "message": f"Produit non trouve sur GOAT pour SKU {sku}"})
        
        # 2. Recuperer les details
        details = goat_get_details(product['slug'])
        if not details:
            return jsonify({
                "found": True, "details_found": False, "step": "details",
                "product": {"name": product.get("name"), "slug": product.get("slug")},
                "message": "Produit trouve mais details non disponibles (Cloudflare?)"
            })
        
        # 3. Generer la description
        colorway = extract_colorway(product.get('name', ''))
        desc, desc_type = build_goat_description(details, product.get('name', ''), colorway)
        
        return jsonify({
            "found": True, "details_found": True,
            "product": {"name": product.get("name"), "slug": product.get("slug")},
            "goat_data": {
                "color": details.get("color", ""),
                "upper_material": details.get("upper_material", ""),
                "midsole": details.get("midsole", ""),
                "story": (details.get("story", "") or "")[:300],
                "details": (details.get("details", "") or "")[:300],
                "nickname": details.get("nickname", ""),
            },
            "generated_description": desc,
            "description_type": desc_type
        })
    except Exception as e:
        log.error(f"[Test GOAT] Error: {e}")
        return jsonify({"error": str(e)}), 500
