"""Configuration gunicorn — chargée automatiquement si la commande de démarrage
est simplement `gunicorn app:app`.

But: éviter que Render coupe les requêtes longues (remplacement d'images sur des
produits à 8 photos) au bout de 30s, ce qui renvoyait une page HTML d'erreur
au lieu du JSON -> "Unexpected token '<'... is not valid JSON" côté navigateur.
"""

# Timeout worker généreux : un apply 8 images + renommage SEO peut prendre >30s
timeout = 120
graceful_timeout = 120

# Garder la conso mémoire raisonnable sur Render
workers = 2
threads = 2
worker_class = "gthread"

# Recycler les workers pour éviter les fuites mémoire sur les longs runs
max_requests = 200
max_requests_jitter = 50

keepalive = 5
