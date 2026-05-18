"""
KP SHOES - Price Drop Tracker (Chunked Queue Version)
Compare les prix avec un snapshot stocké en shop metafield.
Si baisse → set compare_at_price (prix barré).
Si égal/hausse → clear compare_at_price.

Architecture en queue chunked :
- /api/price/run : démarre un nouveau cycle (ou continue le précédent)
- Chaque appel traite max CHUNK_SIZE updates (~3 min)
- Si queue non vide à la fin, retourne pour qu'un cron rappelle
- Robuste aux redémarrages Render
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Blueprint, jsonify, request

from services.shopify import shopify_request, shopify_graphql

log = logging.getLogger("kpshoes.price_tracker")
price_bp = Blueprint("price", __name__)

NAMESPACE = "kp_pricetracker"
SNAPSHOT_KEY = "snapshot"
QUEUE_KEY = "queue"
LASTRUN_KEY = "last_run"
PROMO_DATES_KEY = "promo_dates"  # {variant_id: date_iso} pour tracker l'âge des promos

CHUNK_SIZE = 500  # nombre max d'updates par exécution
PROMO_MAX_DAYS = 30  # après 30 jours, on clear automatiquement (loi française)
MAX_DISCOUNT_PCT = 0.30  # si réduction depuis compare_at > 30%, on rebase sur yesterday_price
CRON_TOKEN = os.environ.get("CRON_TOKEN", "")


def _get_shop_id():
    res = shopify_graphql("{ shop { id } }")
    if not res or not res.get('data'):
        raise Exception("Impossible de récupérer shop ID")
    return res['data']['shop']['id']


def _save_metafield(shop_id, key, value_dict, mf_type="json"):
    """Helper pour sauvegarder un metafield JSON."""
    value = json.dumps(value_dict, separators=(",", ":"))
    res = shopify_graphql("""
    mutation save($metafields: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $metafields) {
        userErrors { field message code }
      }
    }
    """, {
        "metafields": [{
            "ownerId": shop_id,
            "namespace": NAMESPACE,
            "key": key,
            "type": mf_type,
            "value": value,
        }]
    })
    if not res or res.get('errors'):
        log.error(f"[PriceTracker] Save {key} failed: {res}")
        return False
    errs = res.get('data', {}).get('metafieldsSet', {}).get('userErrors', [])
    if errs:
        log.error(f"[PriceTracker] Save {key} userErrors: {errs}")
        return False
    return True


def _load_metafield(key):
    """Helper pour charger un metafield JSON."""
    res = shopify_graphql(f"""
    {{
      shop {{
        metafield(namespace: "{NAMESPACE}", key: "{key}") {{ value }}
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


def _fetch_all_variants():
    """Bulk query → {variant_id_short: {product_id_short, price, compare_at}}"""
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

    log.info("[PriceTracker] Polling bulk operation...")
    op = None
    for attempt in range(120):
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
        log.info(f"[PriceTracker] Bulk status: {op['status']} ({op.get('objectCount', 0)})")

    if not op or op.get('status') != 'COMPLETED' or not op.get('url'):
        log.error("[PriceTracker] Bulk timed out or no URL")
        return {}

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
            variant_short = oid.rsplit('/', 1)[-1]
            parent_short = obj.get("__parentId", "").rsplit('/', 1)[-1]
            variants[variant_short] = {
                "product_id": parent_short,
                "price": float(obj["price"]),
                "compare_at": float(obj["compareAtPrice"]) if obj.get("compareAtPrice") else None,
            }
    return variants


def _apply_updates(updates):
    """updates: list de [product_id, variant_id, compare_at] (IDs courts).
    Retourne (ok_count, error_count)."""
    by_product = defaultdict(list)
    for pid, vid, cap in updates:
        pid_gid = f"gid://shopify/Product/{pid}" if not str(pid).startswith('gid://') else pid
        vid_gid = f"gid://shopify/ProductVariant/{vid}" if not str(vid).startswith('gid://') else vid
        by_product[pid_gid].append({
            "id": vid_gid,
            "compareAtPrice": str(cap) if cap is not None else None,
        })

    total_errors = 0
    total_done = 0
    for pid, variants in by_product.items():
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
            time.sleep(0.2)  # rate limit
    return total_done, total_errors


def _start_new_cycle():
    """Démarre un nouveau cycle : fetch, compare, save queue + snapshot.
    
    Logique :
    - Today < Yesterday → set compare_at = max(yesterday, current_cap) [promo]
    - Today == Yesterday → ne rien clear, garder l'état (loi 30j)
    - Today > Yesterday → clear le compare_at (plus de promo)
    - Promos > 30 jours → auto-clear (conformité légale FR)
    """
    started = datetime.now()
    log.info(f"[PriceTracker] === NEW CYCLE START at {started:%H:%M:%S} ===")

    shop_id = _get_shop_id()
    today = _fetch_all_variants()
    if not today:
        return {"error": "No variants fetched", "started_at": started.isoformat()}

    yesterday = _load_metafield(SNAPSHOT_KEY)
    promo_dates = _load_metafield(PROMO_DATES_KEY) or {}

    drops = 0
    rebased = 0
    clears = 0
    expired_clears = 0
    already_ok = 0
    stable_kept = 0
    new_variants = 0
    updates = []

    from datetime import datetime as dt
    now_iso = started.isoformat()
    cutoff_date = (started - timedelta(days=PROMO_MAX_DAYS)).isoformat()

    if yesterday:
        for vid, info in today.items():
            today_price = info["price"]
            current_cap = info["compare_at"]
            yest_price = yesterday.get(vid)

            if yest_price is None:
                new_variants += 1
                continue

            if today_price < yest_price:
                # BAISSE → définir target_cap
                if current_cap and current_cap > yest_price:
                    # Une promo plus haute existe déjà → vérifier si on la garde
                    potential_discount = (current_cap - today_price) / current_cap
                    if potential_discount > MAX_DISCOUNT_PCT:
                        # Réduction trop grosse → on rebase sur yesterday_price
                        target_cap = yest_price
                        rebased += 1
                        promo_dates[vid] = now_iso  # nouvelle base = nouvelle date
                    else:
                        # Garde le compare_at original (réduction raisonnable)
                        target_cap = current_cap
                        if vid not in promo_dates:
                            promo_dates[vid] = now_iso
                else:
                    # Pas de promo existante (ou compare_at <= yesterday) → yesterday
                    target_cap = yest_price
                    promo_dates[vid] = now_iso

                if current_cap != target_cap:
                    updates.append([info["product_id"], vid, target_cap])
                    drops += 1
                else:
                    already_ok += 1
            elif today_price == yest_price:
                # STABLE → ne rien faire (garder la promo existante)
                if current_cap is not None and current_cap > today_price:
                    # Vérifier si promo trop ancienne (>30j) → expirer
                    promo_date = promo_dates.get(vid)
                    if promo_date and promo_date < cutoff_date:
                        updates.append([info["product_id"], vid, None])
                        expired_clears += 1
                        promo_dates.pop(vid, None)
                    else:
                        stable_kept += 1
                # else: pas de promo en cours, rien à faire
            else:
                # HAUSSE → clear le compare_at
                if current_cap is not None:
                    updates.append([info["product_id"], vid, None])
                    clears += 1
                    promo_dates.pop(vid, None)

        log.info(f"[PriceTracker] Computed: {drops} drops ({rebased} rebased), {clears} clears (price up), {expired_clears} expired clears (>30j), {stable_kept} stable kept, {already_ok} already ok, {new_variants} new")

    # Sauvegarder queue
    queue_data = {
        "updates": updates,
        "started_at": started.isoformat(),
        "stats": {
            "drops": drops,
            "rebased": rebased,
            "clears": clears,
            "expired_clears": expired_clears,
            "stable_kept": stable_kept,
            "already_ok": already_ok,
            "new_variants": new_variants,
            "total_variants": len(today),
            "first_run": yesterday is None,
            "max_discount_pct": MAX_DISCOUNT_PCT,
        }
    }
    _save_metafield(shop_id, QUEUE_KEY, queue_data)

    # Sauvegarder snapshot d'aujourd'hui
    snapshot = {vid: info["price"] for vid, info in today.items()}
    _save_metafield(shop_id, SNAPSHOT_KEY, snapshot)

    # Sauvegarder promo_dates (nettoyer les variants qui n'existent plus)
    promo_dates_cleaned = {k: v for k, v in promo_dates.items() if k in today}
    _save_metafield(shop_id, PROMO_DATES_KEY, promo_dates_cleaned)

    return queue_data


def _process_chunk():
    """Traite le prochain chunk de la queue."""
    queue = _load_metafield(QUEUE_KEY)
    if not queue or not queue.get('updates'):
        return {'status': 'queue_empty', 'processed': 0, 'remaining': 0}

    pending = queue.get('updates', [])
    chunk = pending[:CHUNK_SIZE]
    remaining = pending[CHUNK_SIZE:]

    log.info(f"[PriceTracker] Processing chunk: {len(chunk)} updates ({len(remaining)} remaining)")
    ok, errs = _apply_updates(chunk)

    # Mettre à jour la queue avec les restants
    queue['updates'] = remaining
    queue['last_chunk_at'] = datetime.now().isoformat()
    queue['last_chunk_ok'] = queue.get('last_chunk_ok', 0) + ok
    queue['last_chunk_errs'] = queue.get('last_chunk_errs', 0) + errs

    shop_id = _get_shop_id()
    _save_metafield(shop_id, QUEUE_KEY, queue)

    if not remaining:
        # Queue vide → finaliser et sauver last_run
        log.info(f"[PriceTracker] === QUEUE COMPLETE === Total OK: {queue['last_chunk_ok']}, Errors: {queue['last_chunk_errs']}")
        last_run = {
            "completed_at": datetime.now().isoformat(),
            "started_at": queue.get('started_at'),
            "stats": queue.get('stats', {}),
            "updates_ok": queue['last_chunk_ok'],
            "updates_err": queue['last_chunk_errs'],
        }
        _save_metafield(shop_id, LASTRUN_KEY, last_run)

    return {
        'status': 'chunk_done' if remaining else 'cycle_complete',
        'processed': ok,
        'errors': errs,
        'remaining': len(remaining),
        'total_ok_so_far': queue['last_chunk_ok'],
    }


# État en mémoire pour éviter de lancer plusieurs threads en parallèle
_thread_running = {"running": False, "started_at": None}


def _do_run_work():
    """Le vrai travail : démarre un cycle ou continue la queue."""
    try:
        queue = _load_metafield(QUEUE_KEY)
        pending_count = len(queue.get('updates', [])) if queue else 0

        if pending_count == 0:
            log.info("[PriceTracker] No queue, starting new cycle")
            cycle_data = _start_new_cycle()
            if 'error' in cycle_data:
                log.error(f"[PriceTracker] Cycle start error: {cycle_data}")
                return

            if cycle_data.get('updates'):
                # Traiter chunks en boucle jusqu'à plus rien ou ~3 min écoulées
                start_time = time.time()
                while time.time() - start_time < 180:  # max 3 min
                    result = _process_chunk()
                    if result.get('status') in ('queue_empty', 'cycle_complete'):
                        break
            else:
                # Aucun update à faire
                shop_id = _get_shop_id()
                last_run = {
                    "completed_at": datetime.now().isoformat(),
                    "started_at": cycle_data.get('started_at'),
                    "stats": cycle_data.get('stats', {}),
                    "updates_ok": 0,
                    "updates_err": 0,
                }
                _save_metafield(shop_id, LASTRUN_KEY, last_run)
        else:
            log.info(f"[PriceTracker] Queue has {pending_count} pending, processing chunks")
            start_time = time.time()
            while time.time() - start_time < 180:  # max 3 min par appel
                result = _process_chunk()
                if result.get('status') in ('queue_empty', 'cycle_complete'):
                    break
    except Exception as e:
        import traceback
        log.error(f"[PriceTracker] Run error: {e}\n{traceback.format_exc()}")
    finally:
        _thread_running["running"] = False


@price_bp.route('/api/price/run', methods=['POST', 'GET'])
def api_run():
    """Endpoint principal en mode async :
    - Lance le travail en arrière-plan, retourne immédiatement
    - Pour voir le progrès, ping /api/price/status
    - À pinger toutes les 5 min jusqu'à queue vide."""
    token = request.args.get('token', '') or request.headers.get('X-Cron-Token', '')
    if CRON_TOKEN and token != CRON_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401

    # Si un thread tourne déjà depuis moins de 5 min → renvoie ça
    if _thread_running["running"]:
        try:
            from datetime import datetime as dt
            started = dt.fromisoformat(_thread_running["started_at"])
            elapsed = (dt.now() - started).total_seconds()
            if elapsed < 300:
                return jsonify({
                    'status': 'already_running',
                    'started_at': _thread_running["started_at"],
                    'message': f'Job en cours depuis {int(elapsed)}s. Réessaie plus tard.'
                }), 202
        except:
            pass

    # Démarrer le thread
    import threading
    _thread_running["running"] = True
    _thread_running["started_at"] = datetime.now().isoformat()

    t = threading.Thread(target=_do_run_work, daemon=True)
    t.start()

    # Snapshot de l'état actuel pour info
    queue = _load_metafield(QUEUE_KEY)
    pending = len(queue.get('updates', [])) if queue else 0

    return jsonify({
        'status': 'started',
        'started_at': _thread_running["started_at"],
        'queue_pending_before': pending,
        'message': 'Job lancé en arrière-plan. Check /api/price/status pour le progrès.'
    }), 202


@price_bp.route('/api/price/status')
def api_status():
    """Affiche le statut : snapshot, queue, last_run."""
    snapshot = _load_metafield(SNAPSHOT_KEY)
    queue = _load_metafield(QUEUE_KEY)
    last_run = _load_metafield(LASTRUN_KEY)

    snapshot_info = {'has_snapshot': False}
    if snapshot:
        value = json.dumps(snapshot, separators=(",", ":"))
        snapshot_info = {
            'has_snapshot': True,
            'variants': len(snapshot),
            'size_kb': round(len(value) / 1024, 1),
        }

    queue_info = {'has_queue': False, 'pending': 0}
    if queue:
        queue_info = {
            'has_queue': True,
            'pending': len(queue.get('updates', [])),
            'started_at': queue.get('started_at'),
            'stats': queue.get('stats', {}),
            'last_chunk_at': queue.get('last_chunk_at'),
            'updates_done_so_far': queue.get('last_chunk_ok', 0),
        }

    return jsonify({
        'snapshot': snapshot_info,
        'queue': queue_info,
        'last_run': last_run,
    })


@price_bp.route('/api/price/last-run')
def api_last_run():
    """Retourne le résultat du dernier cycle terminé."""
    last_run = _load_metafield(LASTRUN_KEY)
    queue = _load_metafield(QUEUE_KEY)
    pending = len(queue.get('updates', [])) if queue else 0

    return jsonify({
        'has_last_run': last_run is not None,
        'queue_pending': pending,
        'last_run': last_run,
    })


@price_bp.route('/api/price/reset', methods=['POST'])
def api_reset():
    """Vide complètement le snapshot et la queue."""
    token = request.args.get('token', '') or request.headers.get('X-Cron-Token', '')
    if CRON_TOKEN and token != CRON_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        shop_id = _get_shop_id()
        _save_metafield(shop_id, SNAPSHOT_KEY, {})
        _save_metafield(shop_id, QUEUE_KEY, {'updates': []})
        return jsonify({'success': True, 'message': 'Snapshot et queue réinitialisés'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@price_bp.route('/api/price/clear-queue', methods=['POST', 'GET'])
def api_clear_queue():
    """Vide juste la queue (pas le snapshot)."""
    token = request.args.get('token', '') or request.headers.get('X-Cron-Token', '')
    if CRON_TOKEN and token != CRON_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        shop_id = _get_shop_id()
        _save_metafield(shop_id, QUEUE_KEY, {'updates': []})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@price_bp.route('/api/price/test-product', methods=['POST', 'GET'])
def api_test_product():
    """Test sur UN produit. Usage: ?product_id=123&fake_old_price=200"""
    pid = request.args.get('product_id', '').strip()
    fake_old = request.args.get('fake_old_price', '').strip()
    if not pid:
        return jsonify({'error': 'product_id requis'}), 400

    try:
        r = shopify_request(f'products/{pid}.json')
        if not r or 'product' not in r:
            return jsonify({'error': 'Produit non trouvé'}), 404
        product = r['product']
        yesterday = _load_metafield(SNAPSHOT_KEY) or {}

        results = []
        updates = []
        for v in product.get('variants', []):
            vid_short = str(v['id'])
            today_price = float(v['price'])
            current_cap = float(v['compare_at_price']) if v.get('compare_at_price') else None
            yest_price = float(fake_old) if fake_old else yesterday.get(vid_short)

            action = "no_change"
            target_cap = current_cap

            if yest_price is None:
                action = "no_snapshot"
            elif today_price < yest_price:
                target_cap = yest_price
                if current_cap != target_cap:
                    action = "set_compare_at"
                    updates.append([str(pid), vid_short, target_cap])
                else:
                    action = "already_correct"
            else:
                if current_cap is not None:
                    target_cap = None
                    action = "clear_compare_at"
                    updates.append([str(pid), vid_short, None])

            results.append({
                'variant_id': v['id'],
                'title': v.get('title', ''),
                'today_price': today_price,
                'yesterday_price': yest_price,
                'current_compare_at': current_cap,
                'target_compare_at': target_cap,
                'action': action,
            })

        ok, errs = _apply_updates(updates) if updates else (0, 0)

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
