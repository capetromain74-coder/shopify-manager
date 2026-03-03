# KP SHOES - Plateforme de Gestion Shopify V9

## Architecture Modulaire

Le monolithe de 5456 lignes a ete decoupe en modules thematiques.

### Structure
- **app.py** - Point d entree Flask (factory pattern + blueprints)
- **config.py** - Configuration centralisee (env vars, constantes)
- **services/** - Logique metier (shopify, goat, seo, images, blog, research)
- **routes/** - Endpoints API (blueprints Flask)
- **data/** - Donnees statiques (descriptions, SEO collections, mappings)
- **templates/** - HTML separe du Python

## Changements vs V8

### Securite
- SSL active sur toutes les requetes Shopify (plus de CERT_NONE)
- Cles GOAT en variables d environnement
- Bare except remplaces par except specifiques
- threading.Lock sur les variables globales

### Architecture
- 5456 lignes -> ~20 fichiers modulaires
- HTML extrait dans /templates/
- Factory pattern Flask
- Blueprints par domaine

### Fiabilite
- Cache collections avec TTL (5 min, configurable)
- Gestion d erreurs HTTP specifique
- Logging structure

## Installation


