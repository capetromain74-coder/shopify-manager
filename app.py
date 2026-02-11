"""
Shopify Manager V4 - Version Pagination
"""

from flask import Flask, jsonify, request
import json, os, time, re, ssl
from urllib.request import Request, urlopen
from threading import Thread

app = Flask(__name__)

SHOP = os.environ.get('SHOPIFY_SHOP', 'capet-shop.myshopify.com')
ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
API_VERSION = '2024-01'
SITE_NAME = os.environ.get('SITE_NAME', 'KP SHOES')
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'kpshoes.fr')

task_progress = {'running': False, 'current': 0, 'total': 0, 'message': ''}
_collections_cache = None


def shopify_request(endpoint, method='GET', data=None):
    url = f"https://{SHOP}/admin/api/{API_VERSION}/{endpoint}"
    headers = {'X-Shopify-Access-Token': ACCESS_TOKEN, 'Content-Type': 'application/json'}
    try:
        req = Request(url, data=json.dumps(data).encode('utf-8') if data else None, headers=headers, method=method)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urlopen(req, context=ctx, timeout=30) as r:
            return True if method == 'DELETE' else json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f"[Err] {e}")
        return None


def get_collections():
    global _collections_cache
    if _collections_cache: return _collections_cache
    cols = []
    for t in ['custom_collections', 'smart_collections']:
        r = shopify_request(f'{t}.json?limit=250')
        if r and t in r:
            cols.extend([{'id': c['id'], 'handle': c['handle'], 'title': c['title']} for c in r[t]])
    _collections_cache = cols
    return cols


def find_col(title, cols):
    if not title: return None
    t = title.lower()
    MODEL_PATTERNS = [('jordan-4', ['jordan 4']), ('jordan-1-high', ['jordan 1 high']), ('jordan-1-low', ['jordan 1 low']), ('adidas-samba', ['samba']), ('adidas-campus', ['campus']), ('adidas-gazelle', ['gazelle']), ('asics-gel-1130', ['gel-1130']), ('ugg-tasman', ['tasman']), ('ugg-tazz', ['tazz']), ('nike-dunk-low', ['dunk low']), ('air-force-1', ['air force 1'])]
    BRAND_PATTERNS = [('jordan-1', ['jordan']), ('adidas-1', ['adidas']), ('asics-1', ['asics']), ('nike', ['nike']), ('ugg', ['ugg']), ('new-balance', ['new balance'])]
    for h, ps in MODEL_PATTERNS:
        c = next((x for x in cols if x['handle'] == h), None)
        if c:
            for p in ps:
                if p in t: return {'handle': h, 'title': c['title'], 'type': 'model'}
    for h, ps in BRAND_PATTERNS:
        c = next((x for x in cols if x['handle'] == h), None)
        if c:
            for p in ps:
                if p in t: return {'handle': h, 'title': c['title'], 'type': 'brand'}
    return None


def gen_title(p): return (p.get('title','')[:50] + ' | ' + SITE_NAME)[:60]
def gen_desc(p): return f"Achetez {p.get('title','')} - 100% Authentique - Livraison rapide | {SITE_NAME}"[:155]
def gen_body(p, col):
    title = p.get('title','')
    brand = p.get('vendor','Sneakers')
    sku = p['variants'][0].get('sku','') if p.get('variants') else ''
    if col:
        link = f'<a href="https://{SITE_DOMAIN}/collections/{col["handle"]}">{col["title"]}</a>'
        intro = f'<p>Decouvrez la <strong>{title}</strong>, de notre collection {link}.</p>'
    else:
        intro = f'<p>Decouvrez la <strong>{title}</strong> par <strong>{brand}</strong>.</p>'
    tech = f'<p><strong>SKU</strong>: {sku}<br><strong>Marque</strong>: {brand}</p>' if sku else f'<p><strong>Marque</strong>: {brand}</p>'
    return intro + '<p>Design iconique, finitions premium.</p>' + tech + f'<p>Chez <strong>{SITE_NAME}</strong>, 100% authentique.</p>'


def update_seo(pid, updates):
    if 'body_html' in updates:
        shopify_request(f'products/{pid}.json', 'PUT', {'product': {'id': pid, 'body_html': updates['body_html']}})
        time.sleep(0.4)
    for k, m in [('meta_title', 'title_tag'), ('meta_description', 'description_tag')]:
        if k in updates:
            shopify_request(f'products/{pid}/metafields.json', 'POST', {'metafield': {'namespace': 'global', 'key': m, 'value': updates[k], 'type': 'single_line_text_field'}})
            time.sleep(0.3)
    return True


@app.route('/')
def home():
    return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>V4</title>
<style>body{font-family:system-ui;background:#0a0a0f;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}a{background:#00ff88;color:#000;padding:15px 40px;border-radius:8px;text-decoration:none;font-weight:bold}</style></head>
<body><div style="text-align:center"><h1 style="color:#00ff88">Shopify Manager V4</h1><br><a href="/seo">Gestion SEO</a></div></body></html>'''


@app.route('/seo')
def seo():
    return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SEO</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#0a0a0f;color:#fff}
.hd{padding:10px 15px;background:#111;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #222}
.hd a{color:#666;text-decoration:none}
.hd b{color:#00ff88}
.stats{display:flex;gap:8px;padding:10px 15px;background:#0d0d14;flex-wrap:wrap}
.st{background:#1a1a2e;padding:8px 14px;border-radius:6px;text-align:center}
.st .v{font-size:18px;font-weight:bold}
.st .v.g{color:#0f8}
.st .v.o{color:#fa0}
.st .v.r{color:#f55}
.st .l{font-size:8px;color:#555}
.pct{background:#0f8;color:#000;padding:8px 16px;border-radius:6px;font-size:20px;font-weight:bold}
.ctrl{padding:10px 15px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;border-bottom:1px solid #222}
input,select{padding:7px 10px;background:#1a1a2e;border:1px solid #333;border-radius:4px;color:#fff;font-size:12px}
button{padding:7px 14px;border:none;border-radius:4px;cursor:pointer;font-weight:600;font-size:11px}
.bg{background:#0f8;color:#000}
.br{background:#f55;color:#fff}
.bs{background:#333;color:#fff}
.info{margin-left:auto;font-size:11px;color:#555}
.msg{padding:10px 15px;font-size:11px;color:#0f8;background:#0f81a;display:none}
.msg.on{display:block}
#list{padding:10px 15px}
.pr{background:#111;border:1px solid #222;border-radius:6px;padding:8px 10px;margin-bottom:5px;display:grid;grid-template-columns:22px 45px 1fr 90px 50px 60px;gap:8px;align-items:center;font-size:11px}
.ck{width:16px;height:16px;border:2px solid #444;border-radius:3px;cursor:pointer}
.ck.on{background:#0f8;border-color:#0f8}
.im{width:45px;height:45px;border-radius:4px;object-fit:cover;background:#222}
.ti{overflow:hidden}
.ti h4{font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:2px}
.ti .sk{font-size:8px;color:#444}
.ti .co{font-size:8px;margin-top:1px}
.ti .co.g{color:#0f8}
.ti .co.p{color:#a5f}
.ti .co.n{color:#f55}
.se{font-size:8px}
.se .ok{color:#0f8}
.se .no{color:#f55}
.sc{font-size:9px;padding:3px 7px;border-radius:8px}
.sc.h{background:#0f82;color:#0f8}
.sc.m{background:#fa02;color:#fa0}
.sc.l{background:#f552;color:#f55}
.pr button{padding:3px 7px;font-size:9px}
.ld{text-align:center;padding:40px;color:#555}
.sp{width:30px;height:30px;border:3px solid #222;border-top-color:#0f8;border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 10px}
@keyframes spin{to{transform:rotate(360deg)}}
.bar{position:fixed;top:0;left:0;right:0;background:#111;padding:10px 15px;border-bottom:2px solid #0f8;display:none;z-index:99;font-size:11px}
.bar.on{display:block}
.bar .tr{height:5px;background:#222;border-radius:3px;margin-top:6px}
.bar .fl{height:100%;background:#0f8;border-radius:3px}
.toast{position:fixed;bottom:15px;right:15px;padding:8px 14px;border-radius:5px;font-size:11px;z-index:100}
.toast.s{background:#0f8;color:#000}
.toast.e{background:#f55}
</style></head><body>
<div class="bar" id="bar"><div style="display:flex;justify-content:space-between"><span id="bm">...</span><span id="bc">0/0</span></div><div class="tr"><div class="fl" id="bf"></div></div></div>
<div class="hd"><a href="/">Retour</a><b>SEO V4</b><span></span></div>
<div class="stats"><div class="st"><div class="v g" id="s1">-</div><div class="l">OK</div></div><div class="st"><div class="v o" id="s2">-</div><div class="l">PARTIEL</div></div><div class="st"><div class="v r" id="s3">-</div><div class="l">MANQUE</div></div><div class="st"><div class="v" id="s4">-</div><div class="l">TOTAL</div></div><div class="pct" id="pct">-</div></div>
<div class="ctrl"><input id="q" placeholder="Rechercher..."><select id="f"><option value="">Tous</option><option value="missing">Sans lien</option><option value="partial">Partiel</option><option value="complete">Complet</option></select><button class="bs" onclick="reload()">Actualiser</button><button class="bg" onclick="doSel()">Selection</button><button class="br" onclick="doAll()">TOUT</button><div class="info"><b id="sc">0</b> sel.</div></div>
<div class="msg" id="msg"></div>
<div id="list"><div class="ld"><div class="sp"></div>Chargement...</div></div>
<script>
var P=[];
var C=[];
var sel=new Set();
var sinceId=0;
var loading=false;

function loadMore(){
    if(loading) return;
    loading=true;
    showMsg("Chargement... "+P.length+" produits");
    fetch("/api/products?since_id="+sinceId+"&limit=50")
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.collections) C=d.collections;
            if(d.products && d.products.length>0){
                for(var i=0;i<d.products.length;i++){
                    var p=d.products[i];
                    var b=(p.body_html||"").toLowerCase();
                    p._lk=b.indexOf("kpshoes.fr/collections/")>=0;
                    p._ds=(p.body_html||"").length>100;
                    p._sc=(p._ds?30:0)+(p._lk?70:0);
                    p._st=p._sc>=70?"complete":p._sc>=30?"partial":"missing";
                    p._co=findC(p.title);
                    P.push(p);
                }
                sinceId=d.products[d.products.length-1].id;
                updateStats();
                filter();
                loading=false;
                if(d.products.length>=50){
                    setTimeout(loadMore,300);
                }else{
                    showMsg("");
                }
            }else{
                showMsg("");
                loading=false;
                filter();
            }
        })
        .catch(function(e){
            showMsg("Erreur: "+e.message);
            loading=false;
        });
}

function findC(t){
    if(!t||!C.length) return null;
    t=t.toLowerCase();
    var M=[["jordan-4",["jordan 4"]],["jordan-1-high",["jordan 1 high"]],["jordan-1-low",["jordan 1 low"]],["adidas-samba",["samba"]],["adidas-campus",["campus"]],["adidas-gazelle",["gazelle"]],["asics-gel-1130",["gel-1130"]],["ugg-tasman",["tasman"]],["ugg-tazz",["tazz"]],["nike-dunk-low",["dunk low"]],["air-force-1",["air force 1"]]];
    var B=[["jordan-1",["jordan"]],["adidas-1",["adidas"]],["asics-1",["asics"]],["nike",["nike"]],["ugg",["ugg"]],["new-balance",["new balance"]]];
    for(var i=0;i<M.length;i++){
        var h=M[i][0];
        var ps=M[i][1];
        var c=null;
        for(var j=0;j<C.length;j++){if(C[j].handle===h){c=C[j];break;}}
        if(c){
            for(var k=0;k<ps.length;k++){
                if(t.indexOf(ps[k])>=0) return {h:h,n:c.title,t:"m"};
            }
        }
    }
    for(var i=0;i<B.length;i++){
        var h=B[i][0];
        var ps=B[i][1];
        var c=null;
        for(var j=0;j<C.length;j++){if(C[j].handle===h){c=C[j];break;}}
        if(c){
            for(var k=0;k<ps.length;k++){
                if(t.indexOf(ps[k])>=0) return {h:h,n:c.title,t:"b"};
            }
        }
    }
    return null;
}

function updateStats(){
    var c1=0,c2=0,c3=0;
    for(var i=0;i<P.length;i++){
        if(P[i]._st==="complete") c1++;
        else if(P[i]._st==="partial") c2++;
        else c3++;
    }
    document.getElementById("s1").textContent=c1;
    document.getElementById("s2").textContent=c2;
    document.getElementById("s3").textContent=c3;
    document.getElementById("s4").textContent=P.length;
    document.getElementById("pct").textContent=P.length?Math.round(c1/P.length*100)+"%":"0%";
}

function showMsg(t){
    var m=document.getElementById("msg");
    m.textContent=t;
    if(t){m.classList.add("on");}else{m.classList.remove("on");}
}

function filter(){
    var q=document.getElementById("q").value.toLowerCase();
    var f=document.getElementById("f").value;
    var L=[];
    for(var i=0;i<P.length;i++){
        var p=P[i];
        if(q && p.title.toLowerCase().indexOf(q)<0) continue;
        if(f && p._st!==f) continue;
        L.push(p);
    }
    render(L);
}

function render(L){
    if(!L.length && !loading){
        document.getElementById("list").innerHTML="<div class='ld'>Aucun produit</div>";
        return;
    }
    var html="";
    var max=Math.min(L.length,200);
    for(var i=0;i<max;i++){
        var p=L[i];
        var ck=sel.has(p.id)?"on":"";
        var sc=p._sc>=70?"h":p._sc>=30?"m":"l";
        var co="<span class='co n'>-</span>";
        if(p._co){
            co="<span class='co "+(p._co.t==="m"?"g":"p")+"'>"+(p._co.t==="m"?"V":"O")+" "+esc(p._co.n)+"</span>";
        }
        var img=(p.image && p.image.src)?p.image.src:"";
        var sku=(p.variants && p.variants[0] && p.variants[0].sku)?p.variants[0].sku:"-";
        html+="<div class='pr'>";
        html+="<div class='ck "+ck+"' onclick='tog("+p.id+")'></div>";
        html+="<img class='im' src='"+img+"' onerror=\"this.src=''\">";
        html+="<div class='ti'><h4>"+esc(p.title)+"</h4><div class='sk'>"+sku+"</div>"+co+"</div>";
        html+="<div class='se'><div class='"+(p._ds?"ok":"no")+"'>"+(p._ds?"V":"X")+" Desc</div><div class='"+(p._lk?"ok":"no")+"'>"+(p._lk?"V":"X")+" Lien</div></div>";
        html+="<div class='sc "+sc+"'>"+p._sc+"%</div>";
        html+="<div><button class='bg' onclick='doOne("+p.id+")'>GO</button></div>";
        html+="</div>";
    }
    if(L.length>200){
        html+="<div class='ld'>200 affiches. Utilisez recherche.</div>";
    }
    document.getElementById("list").innerHTML=html;
}

function esc(s){
    if(!s) return "";
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function tog(id){
    if(sel.has(id)){sel.delete(id);}else{sel.add(id);}
    document.getElementById("sc").textContent=sel.size;
    filter();
}

function reload(){
    P=[];
    C=[];
    sinceId=0;
    sel.clear();
    document.getElementById("sc").textContent="0";
    document.getElementById("list").innerHTML="<div class='ld'><div class='sp'></div>Chargement...</div>";
    loadMore();
}

function doOne(id){
    toast("...","s");
    fetch("/api/seo/apply",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:id})})
        .then(function(r){return r.json();})
        .then(function(d){
            if(d.success){
                toast("OK!","s");
                for(var i=0;i<P.length;i++){
                    if(P[i].id===id){
                        P[i]._lk=true;
                        P[i]._ds=true;
                        P[i]._sc=100;
                        P[i]._st="complete";
                        break;
                    }
                }
                updateStats();
                filter();
            }else{
                toast("Erreur","e");
            }
        })
        .catch(function(e){toast("Erreur","e");});
}

function doSel(){
    if(!sel.size){toast("Selectionnez","e");return;}
    var ids=Array.from(sel);
    batch(ids);
}

function doAll(){
    if(!confirm("Appliquer a "+P.length+" produits?")) return;
    var ids=[];
    for(var i=0;i<P.length;i++){ids.push(P[i].id);}
    batch(ids);
}

function batch(ids){
    document.getElementById("bar").classList.add("on");
    fetch("/api/seo/batch",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_ids:ids})})
        .then(function(){
            var iv=setInterval(function(){
                fetch("/api/progress")
                    .then(function(r){return r.json();})
                    .then(function(r){
                        var pct=r.total?Math.round(r.current/r.total*100):0;
                        document.getElementById("bf").style.width=pct+"%";
                        document.getElementById("bc").textContent=r.current+"/"+r.total;
                        document.getElementById("bm").textContent=r.message||"...";
                        if(!r.running){
                            clearInterval(iv);
                            document.getElementById("bar").classList.remove("on");
                            toast("Termine!","s");
                            sel.clear();
                            document.getElementById("sc").textContent="0";
                            reload();
                        }
                    });
            },1000);
        });
}

function toast(m,t){
    var e=document.createElement("div");
    e.className="toast "+t;
    e.textContent=m;
    document.body.appendChild(e);
    setTimeout(function(){e.remove();},2000);
}

document.getElementById("q").addEventListener("input",filter);
document.getElementById("f").addEventListener("change",filter);
loadMore();
</script></body></html>'''


@app.route('/api/products')
def api_products():
    since_id = request.args.get('since_id', '0')
    limit = request.args.get('limit', '50')
    r = shopify_request(f'products.json?limit={limit}&since_id={since_id}')
    products = r.get('products', []) if r else []
    return jsonify({'products': products, 'collections': get_collections()})


@app.route('/api/progress')
def api_progress():
    return jsonify(task_progress)


@app.route('/api/seo/apply', methods=['POST'])
def api_apply():
    pid = request.json.get('product_id')
    r = shopify_request(f'products/{pid}.json')
    if not r: return jsonify({'error': 'err'}), 404
    p = r['product']
    col = find_col(p.get('title', ''), get_collections())
    update_seo(pid, {'meta_title': gen_title(p), 'meta_description': gen_desc(p), 'body_html': gen_body(p, col)})
    return jsonify({'success': True})


@app.route('/api/seo/batch', methods=['POST'])
def api_batch():
    global task_progress
    pids = request.json.get('product_ids', [])
    def run():
        global task_progress
        task_progress = {'running': True, 'current': 0, 'total': len(pids), 'message': 'Demarrage...'}
        cols = get_collections()
        for i, pid in enumerate(pids):
            task_progress['current'] = i + 1
            r = shopify_request(f'products/{pid}.json')
            if r and 'product' in r:
                p = r['product']
                task_progress['message'] = p.get('title','')[:25]
                col = find_col(p.get('title', ''), cols)
                update_seo(pid, {'meta_title': gen_title(p), 'meta_description': gen_desc(p), 'body_html': gen_body(p, col)})
            time.sleep(1)
        task_progress = {'running': False, 'current': len(pids), 'total': len(pids), 'message': 'OK '+str(len(pids))+'!'}
    Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
