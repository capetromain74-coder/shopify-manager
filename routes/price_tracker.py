"""
KP SHOES - Price Drop Tracker
Compare les prix avec un snapshot stocké en shop metafield.
Si baisse → set compare_at_price (prix barré).
Si égal/hausse → clear compare_at_price (pas de promo).
"""

import os
import json
import time
import logging
from datetime import datetime
from collections import defaultdict
from flask import Blueprint, jsonify, request

from services.shopify import shopify_request, shopify_graphql

log = logging.getLogger("kpshoes.price_tracker")
price_bp = Blueprint("price", __name__)

NAMESPACE = "kp_pricetracker"
KEY = "snapshot"

# Token de sécurité pour la route cron (pour éviter qu'un random ping la déclenche)
CRON_TOKEN = os.environ.get("CRON_TOKEN", "")


def _get_shop_id():
    """Récupère l'ID du shop pour ownerId du metafield."""
    res = shopify_graphql("{ shop { id } }")
    if not res or not res.get('data'):
        raise Exception("Impossible de récupérer shop ID")
    return res['data']['shop']['id']


def _fetch_all_variants():
    """Bulk query → {variant_id_short: {product_id_short, price, compare_at}}
    Utilise des IDs courts (juste les numéros) pour rester sous 2MB de metafield."""
    # Lancer le bulk operation
    start = shopify_graphql("""
    mutation {
      bulkOperationRunQuery(query: \"\"\"
        { products { edges { node { id variants { edges { node {
          id price compareAtPrice
        } } } } } } }
      \"\"\") {
        bulkOperation { id status }
        userErrors { message }
      }
    }
    """)

    if not start or start.get('errors'):
        log.error(f"[PriceTracker] Bulk start failed: {start}")
        return {}

    user_errs = start.get('data', {}).get('bulkOperationRunQuery', {}).get('userErrors', [])
    if user_errs:
        log.error(f"[PriceTracker] Bulk userErrors: {user_errs}")
        return {}

    # Poll
    log.info("[PriceTracker] Polling bulk operation...")
    op = None
    for attempt in range(120):  # max 10 min
        time.sleep(5)
        res = shopify_graphql("{ currentBulkOperation { status url errorCode objectCount } }")
        op = res.get('data', {}).get('currentBulkOperation') if res else None
        if not op:
            continue
        if op['status'] == 'COMPLETED':
            log.info(f"[PriceTracker] Bulk completed: {op.get('objectCount')} objects")
            break
        if op['status'] in ('FAILED', 'CANCELED'):
            log.error(f"[PriceTracker] Bulk failed: {op}")
            return {}
        log.info(f"[PriceTracker] Bulk status: {op['status']} ({op.get('objectCount', 0)} obj so far)")

    if not op or op.get('status') != 'COMPLETED' or not op.get('url'):
        log.error("[PriceTracker] Bulk timed out or no URL")
        return {}

    # Télécharger le JSONL
    import urllib.request
    log.info("[PriceTracker] Downloading bulk results...")
    with urllib.request.urlopen(op['url'], timeout=120) as r:
        text = r.read().decode('utf-8')

    variants = {}
    for line in text.strip().split("\n"):
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        oid = obj.get("id", "")
        if "ProductVariant" in oid:
            # Extraire juste les IDs numériques pour compresser
            variant_short = oid.rsplit('/', 1)[-1]
            parent_short = obj.get("__parentId", "").rsplit('/', 1)[-1]
            variants[variant_short] = {
                "product_id": parent_short,
                "price": float(obj["price"]),
                "compare_at": float(obj["compareAtPrice"]) if obj.get("compareAtPrice") else None,
            }
    return variants


def _load_snapshot():
    """Charge le snapshot depuis shop metafield."""
    res = shopify_graphql(f"""
    {{
      shop {{
        metafield(namespace: "{NAMESPACE}", key: "{KEY}") {{ value }}
      }}
    }}
    """)
    if not res or not res.get('data'):
        return None
    mf = res['data']['shop'].get('metafield')
    if not mf:
        return None
    try:
        return json.loads(mf['value'])
    except:
        return None


def _save_snapshot(shop_id, prices):
    """Sauvegarde le snapshot dans shop metafield (JSON compact)."""
    value = json.dumps(prices, separators=(",", ":"))
    size_mb = len(value) / 1024 / 1024
    log.info(f"[PriceTracker] Saving snapshot: {len(prices)} variants, {size_mb:.2f} MB")

    res = shopify_graphql("""
    mutation save($metafields: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $metafields) {
        metafields { id key namespace }
        userErrors { field message code }
      }
    }
    """, {
        "metafields": [{
            "ownerId": shop_id,
            "namespace": NAMESPACE,
            "key": KEY,
            "type": "json",
            "value": value,
        }]
    })
    log.info(f"[PriceTracker] Save snapshot raw response: {res}")
    if not res:
        log.error("[PriceTracker] No response from GraphQL")
        return False
    if res.get('errors'):
        log.error(f"[PriceTracker] GraphQL errors: {res['errors']}")
        return False
    if res.get('data'):
        errs = res['data'].get('metafieldsSet', {}).get('userErrors', [])
        if errs:
            log.error(f"[PriceTracker] Snapshot save userErrors: {errs}")
            return False
        saved = res['data'].get('metafieldsSet', {}).get('metafields', [])
        log.info(f"[PriceTracker] Saved metafields: {saved}")
    return True


def _update_variants(updates):
    """updates: list de (product_id_short, variant_id_short, new_compare_at | None)
    Reconstruit les gids avant d'envoyer à Shopify."""
    by_product = defaultdict(list)
    for pid, vid, cap in updates:
        # Si c'est déjà un gid, garde-le, sinon construis-le
        pid_gid = pid if pid.startswith('gid://') else f"gid://shopify/Product/{pid}"
        vid_gid = vid if vid.startswith('gid://') else f"gid://shopify/ProductVariant/{vid}"
        by_product[pid_gid].append({
            "id": vid_gid,
            "compareAtPrice": str(cap) if cap is not None else None,
        })

    total_errors = 0
    total_done = 0
    for pid, variants in by_product.items():
        # Max 100 variants par mutation
        for i in range(0, len(variants), 100):
            batch = variants[i:i + 100]
            res = shopify_graphql("""
            mutation upd($pid: ID!, $variants: [ProductVariantsBulkInput!]!) {
              productVariantsBulkUpdate(productId: $pid, variants: $variants) {
                userErrors { field message }
              }
            }
            """, {"pid": pid, "variants": batch})
            if res and res.get('data'):
                errs = res['data'].get('productVariantsBulkUpdate', {}).get('userErrors', [])
                if errs:
                    total_errors += len(errs)
                    log.error(f"[PriceTracker] {pid}: {errs}")
                else:
                    total_done += len(batch)
            time.sleep(0.3)  # rate limit
    return total_done, total_errors


def run_price_check():
    """Job principal : compare prix, update compare_at_price, save snapshot."""
    started = datetime.now()
    log.info(f"[PriceTracker] === START at {started:%Y-%m-%d %H:%M} ===")
    result = {
        "started_at": started.isoformat(),
        "drops": 0,
        "clears": 0,
        "already_ok": 0,
        "new_variants": 0,
        "updates_ok": 0,
        "updates_err": 0,
        "total_variants": 0,
        "first_run": False,
    }

    try:
        shop_id = _get_shop_id()

        log.info("[PriceTracker] Fetching today's prices...")
        today = _fetch_all_variants()
        result["total_variants"] = len(today)

        if not today:
            log.error("[PriceTracker] No variants fetched, aborting")
            result["error"] = "No variants fetched"
            return result

        yesterday = _load_snapshot()

        if yesterday:
            updates = []
            for vid, info in today.items():
                today_price = info["price"]
                current_cap = info["compare_at"]
                yest_price = yesterday.get(vid)

                if yest_price is None:
                    result["new_variants"] += 1
                    # Si nouveau variant avec un compare_at déjà set, on le laisse
                    continue

                if today_price < yest_price:
                    # Baisse de prix → afficher prix barré
                    target_cap = yest_price
                    if current_cap != target_cap:
                        updates.append((info["product_id"], vid, target_cap))
                        result["drops"] += 1
                    else:
                        result["already_ok"] += 1
                else:
                    # Prix égal ou en hausse → clear compare_at
                    if current_cap is not None:
                        updates.append((info["product_id"], vid, None))
                        result["clears"] += 1

            log.info(f"[PriceTracker] {result['drops']} drops | {result['clears']} clears | {result['already_ok']} already OK | {result['new_variants']} new")

            if updates:
                log.info(f"[PriceTracker] Updating {len(updates)} variants...")
                ok, errs = _update_variants(updates)
                result["updates_ok"] = ok
                result["updates_err"] = errs
        else:
            log.info("[PriceTracker] First run, no previous snapshot")
            result["first_run"] = True

        log.info("[PriceTracker] Saving today's snapshot...")
        snapshot = {vid: info["price"] for vid, info in today.items()}
        if not _save_snapshot(shop_id, snapshot):
            result["snapshot_error"] = True

        ended = datetime.now()
        duration = (ended - started).total_seconds()
        result["ended_at"] = ended.isoformat()
        result["duration_sec"] = duration
        log.info(f"[PriceTracker] === DONE in {duration:.0f}s ===")
        return result

    except Exception as e:
        log.error(f"[PriceTracker] Error: {e}")
        import traceback
        log.error(traceback.format_exc())
        result["error"] = str(e)
        return result


def _save_last_run(result):
    """Sauvegarde le résultat du dernier run dans un metafield pour pouvoir le consulter."""
    try:
        shop_id = _get_shop_id()
        shopify_graphql("""
        mutation save($metafields: [MetafieldsSetInput!]!) {
          metafieldsSet(metafields: $metafields) {
            userErrors { field message }
          }
        }
        """, {
            "metafields": [{
                "ownerId": shop_id,
                "namespace": NAMESPACE,
                "key": "last_run",
                "type": "json",
                "value": json.dumps(result, separators=(",", ":")),
            }]
        })
    except Exception as e:
        log.error(f"[PriceTracker] Could not save last_run: {e}")


def _load_last_run():
    """Charge le résultat du dernier run."""
    res = shopify_graphql(f"""
    {{
      shop {{
        metafield(namespace: "{NAMESPACE}", key: "last_run") {{ value }}
      }}
    }}
    """)
    if not res or not res.get('data'):
        return None
    mf = res['data']['shop'].get('metafield')
    if not mf:
        return None
    try:
        return json.loads(mf['value'])
    except:
        return None


# État en mémoire pour savoir si un job tourne
_job_running = {"running": False, "started_at": None}


def _run_async():
    """Wrapper pour lancer le job en background et stocker le résultat."""
    import threading
    if _job_running["running"]:
        return False
    _job_running["running"] = True
    _job_running["started_at"] = datetime.now().isoformat()

    def worker():
        try:
            result = run_price_check()
            _save_last_run(result)
        except Exception as e:
            log.error(f"[PriceTracker] Async worker error: {e}")
        finally:
            _job_running["running"] = False

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return True


@price_bp.route('/api/price/run', methods=['POST', 'GET'])
def api_run_price_check():
    """Trigger le job en background. Retourne immédiatement 200.
    Pour voir le résultat, ping /api/price/last-run après quelques minutes."""
    token = request.args.get('token', '') or request.headers.get('X-Cron-Token', '')
    if CRON_TOKEN and token != CRON_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401

    # Mode synchrone (ancien) si ?sync=1
    if request.args.get('sync') == '1':
        result = run_price_check()
        _save_last_run(result)
        return jsonify(result)

    # Mode async par défaut (pour éviter timeout gunicorn)
    started = _run_async()
    if not started:
        return jsonify({
            'status': 'already_running',
            'started_at': _job_running.get("started_at"),
            'message': 'Un job est déjà en cours. Réessaie dans quelques minutes.'
        }), 202

    return jsonify({
        'status': 'started',
        'started_at': _job_running["started_at"],
        'message': 'Job lancé en arrière-plan. Consulte /api/price/last-run dans 1-3 minutes pour voir le résultat.'
    }), 202


@price_bp.route('/api/price/last-run')
def api_last_run():
    """Retourne le résultat du dernier run terminé."""
    result = _load_last_run()
    if not result:
        return jsonify({
            'has_last_run': False,
            'job_running': _job_running["running"],
            'message': 'Aucun run terminé pour le moment.'
        })
    return jsonify({
        'has_last_run': True,
        'job_running': _job_running["running"],
        'last_run': result
    })


@price_bp.route('/api/price/status')
def api_price_status():
    """Affiche le snapshot actuel (combien de variants, taille)."""
    snapshot = _load_snapshot()
    if not snapshot:
        return jsonify({'has_snapshot': False, 'variants': 0})
    value = json.dumps(snapshot, separators=(",", ":"))
    return jsonify({
        'has_snapshot': True,
        'variants': len(snapshot),
        'size_kb': round(len(value) / 1024, 1),
        'size_mb': round(len(value) / 1024 / 1024, 3),
    })


@price_bp.route('/api/price/reset', methods=['POST'])
def api_price_reset():
    """Supprime le snapshot (force un first run au prochain lancement)."""
    token = request.args.get('token', '') or request.headers.get('X-Cron-Token', '')
    if CRON_TOKEN and token != CRON_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        shop_id = _get_shop_id()
        # Save empty dict to "reset"
        _save_snapshot(shop_id, {})
        return jsonify({'success': True, 'message': 'Snapshot reset'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@price_bp.route('/api/price/test-product', methods=['POST', 'GET'])
def api_price_test_product():
    """Test sur UN produit : compare ses variants avec le snapshot et applique le fix.
    Usage: POST /api/price/test-product?product_id=123456&fake_old_price=200
    - product_id: ID Shopify (sans gid://)
    - fake_old_price (optionnel): force un ancien prix pour simuler une baisse
    """
    pid = request.args.get('product_id', '').strip()
    fake_old = request.args.get('fake_old_price', '').strip()
    if not pid:
        return jsonify({'error': 'product_id requis'}), 400

    try:
        # 1. Récupérer le produit + variants
        r = shopify_request(f'products/{pid}.json')
        if not r or 'product' not in r:
            return jsonify({'error': 'Produit non trouvé'}), 404
        product = r['product']

        product_gid = f"gid://shopify/Product/{pid}"

        # 2. Charger snapshot
        yesterday = _load_snapshot() or {}

        results = []
        updates = []
        for v in product.get('variants', []):
            vid_short = str(v['id'])
            vid_gid = f"gid://shopify/ProductVariant/{vid_short}"
            today_price = float(v['price'])
            current_cap = float(v['compare_at_price']) if v.get('compare_at_price') else None

            if fake_old:
                yest_price = float(fake_old)
            else:
                # Snapshot stocke avec IDs courts
                yest_price = yesterday.get(vid_short)

            action = "no_change"
            target_cap = current_cap

            if yest_price is None:
                action = "no_snapshot"
            elif today_price < yest_price:
                target_cap = yest_price
                if current_cap != target_cap:
                    action = "set_compare_at"
                    updates.append((product_gid, vid_gid, target_cap))
                else:
                    action = "already_correct"
            else:
                if current_cap is not None:
                    target_cap = None
                    action = "clear_compare_at"
                    updates.append((product_gid, vid_gid, None))

            results.append({
                'variant_id': v['id'],
                'title': v.get('title', ''),
                'today_price': today_price,
                'yesterday_price': yest_price,
                'current_compare_at': current_cap,
                'target_compare_at': target_cap,
                'action': action,
            })

        # 3. Appliquer
        if updates:
            ok, errs = _update_variants(updates)
        else:
            ok, errs = 0, 0

        return jsonify({
            'product': product['title'],
            'product_id': pid,
            'variants': results,
            'updates_applied': ok,
            'errors': errs,
            'fake_old_used': fake_old if fake_old else None,
        })
    except Exception as e:
        import traceback
        log.error(f"[PriceTest] Error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@price_bp.route('/api/price/dry-run')
def api_price_dry_run():
    """Simule le job complet sans rien modifier ni sauvegarder.
    Affiche combien de variants seraient affectés."""
    try:
        log.info("[PriceTracker DRY-RUN] Fetching prices...")
        today = _fetch_all_variants()
        if not today:
            return jsonify({'error': 'No variants fetched'}), 500

        yesterday = _load_snapshot()
        if not yesterday:
            return jsonify({
                'first_run': True,
                'today_variants': len(today),
                'message': 'Pas de snapshot précédent, ce serait un first run.'
            })

        drops = []
        clears = []
        already_ok = 0
        new_variants = 0

        for vid, info in today.items():
            today_price = info["price"]
            current_cap = info["compare_at"]
            yest_price = yesterday.get(vid)

            if yest_price is None:
                new_variants += 1
                continue

            if today_price < yest_price:
                if current_cap != yest_price:
                    drops.append({
                        'variant_id': vid,
                        'today': today_price,
                        'yesterday': yest_price,
                        'diff': round(yest_price - today_price, 2),
                    })
                else:
                    already_ok += 1
            else:
                if current_cap is not None:
                    clears.append({
                        'variant_id': vid,
                        'today': today_price,
                        'yesterday': yest_price,
                        'current_cap': current_cap,
                    })

        return jsonify({
            'today_variants': len(today),
            'yesterday_variants': len(yesterday),
            'new_variants': new_variants,
            'drops_count': len(drops),
            'clears_count': len(clears),
            'already_ok': already_ok,
            'drops_sample': drops[:20],
            'clears_sample': clears[:20],
            'note': 'Aucune modification appliquée (dry-run)',
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
