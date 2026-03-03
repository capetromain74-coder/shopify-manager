"""
KP SHOES - Moteur SEO
Analyse, generation de meta tags, descriptions produits, scoring.
"""

import re
import time
import unicodedata
import logging

from config import SITE_NAME, SITE_DOMAIN
from data.descriptions import MODEL_DESCRIPTIONS, ICONIC_COLORWAYS, COLOR_KEYWORDS
from data.mappings import MODEL_COLLECTIONS, BRAND_COLLECTIONS, EXCLUDED
from services.shopify import shopify_request

log = logging.getLogger('kpshoes.seo')


def title_to_filename(title):
    """Convertit un titre produit en nom de fichier safe: 'Air Jordan 4 Rétro (2025)' -> 'Air_Jordan_4_Retro_2025'"""
    # Enlever les accents : è→e, é→e, à→a, etc.
    fn = unicodedata.normalize('NFD', title)
    fn = ''.join(c for c in fn if unicodedata.category(c) != 'Mn')
    fn = fn.replace(' ', '_')
    fn = re.sub(r'[^\w\-]', '_', fn)
    fn = re.sub(r'_+', '_', fn)
    return fn.strip('_')


def find_collection(title, collections):
    if not title or not collections: return None
    t = title.lower()
    available = [c['handle'] for c in collections if c['handle'] not in EXCLUDED]
    for handle, keywords in MODEL_COLLECTIONS.items():
        if handle in available:
            for kw in keywords:
                if kw in t:
                    col = next((c for c in collections if c['handle'] == handle), None)
                    if col: return {'handle': col['handle'], 'title': col['title'], 'url': f"https://{SITE_DOMAIN}/collections/{col['handle']}", 'type': 'model'}
    for handle, keywords in BRAND_COLLECTIONS.items():
        if handle in available:
            for kw in keywords:
                if kw in t:
                    col = next((c for c in collections if c['handle'] == handle), None)
                    if col: return {'handle': col['handle'], 'title': col['title'], 'url': f"https://{SITE_DOMAIN}/collections/{col['handle']}", 'type': 'brand'}
    return None


def extract_brand(title):
    t = title.lower()
    if 'fear of god' in t or 'essentials' in t: return 'Fear of God'
    if 'jordan' in t: return 'Jordan'
    if 'yeezy' in t: return 'Yeezy'
    if 'travis scott' in t: return 'Nike x Travis Scott'
    if 'off-white' in t.replace(' ', '-'): return 'Nike x Off-White'
    if 'dior' in t: return 'Dior'
    if 'mschf' in t: return 'MSCHF'
    brands = [
        ('Nike', ['nike', 'dunk', 'air force', 'air max', 'nocta', 'blazer', 'vomero', 'p-6000']),
        ('Adidas', ['adidas', 'samba', 'campus', 'gazelle', 'spezial', 'forum', 'sl 72', 'adilette']),
        ('New Balance', ['new balance']),
        ('Asics', ['asics', 'gel-']),
        ('UGG', ['ugg', 'tasman', 'tazz']),
        ('Puma', ['puma']),
        ('Crocs', ['crocs']),
        ('Birkenstock', ['birkenstock']),
        ('Salomon', ['salomon']),
        ('Timberland', ['timberland']),
        ('Converse', ['converse', 'chuck taylor']),
        ('Vans', ['vans', 'old skool', 'sk8-hi']),
        ('Reebok', ['reebok']),
        ('On Running', ['on cloud', 'cloudmonster', 'cloudnova']),
    ]
    for brand, kws in brands:
        for kw in kws:
            if kw in t: return brand
    return 'Sneakers'


def analyze_seo(product, meta_title, meta_description):
    body_html = product.get('body_html', '') or ''
    results = {'score': 0, 'max_score': 100, 'checks': []}
    
    check1 = {'name': 'Meta Title', 'points': 0, 'max': 20, 'status': 'error', 'message': 'Absent'}
    if meta_title:
        if SITE_NAME in meta_title and len(meta_title) <= 60:
            check1 = {'name': 'Meta Title', 'points': 20, 'max': 20, 'status': 'success', 'message': 'OK (' + str(len(meta_title)) + ' car.)'}
        elif len(meta_title) > 60:
            check1 = {'name': 'Meta Title', 'points': 8, 'max': 20, 'status': 'warning', 'message': 'Trop long'}
        else:
            check1 = {'name': 'Meta Title', 'points': 12, 'max': 20, 'status': 'warning', 'message': 'Manque KP SHOES'}
    results['checks'].append(check1)
    results['score'] += check1['points']
    
    check2 = {'name': 'Meta Description', 'points': 0, 'max': 20, 'status': 'error', 'message': 'Absente'}
    if meta_description:
        has_auth = '100%' in meta_description or 'authentique' in meta_description.lower()
        good_len = 100 <= len(meta_description) <= 155
        if has_auth and good_len:
            check2 = {'name': 'Meta Description', 'points': 20, 'max': 20, 'status': 'success', 'message': 'OK'}
        elif good_len:
            check2 = {'name': 'Meta Description', 'points': 12, 'max': 20, 'status': 'warning', 'message': 'Manque authenticite'}
        else:
            check2 = {'name': 'Meta Description', 'points': 8, 'max': 20, 'status': 'warning', 'message': 'Longueur incorrecte'}
    results['checks'].append(check2)
    results['score'] += check2['points']
    
    check3 = {'name': 'Description + Lien', 'points': 0, 'max': 30, 'status': 'error', 'message': 'Manquante'}
    has_desc = len(body_html) > 100
    has_link = 'kpshoes.fr/collections/' in body_html.lower()
    if has_desc and has_link:
        check3 = {'name': 'Description + Lien', 'points': 30, 'max': 30, 'status': 'success', 'message': 'Complete avec lien'}
    elif has_desc:
        check3 = {'name': 'Description + Lien', 'points': 12, 'max': 30, 'status': 'warning', 'message': 'Sans lien'}
    results['checks'].append(check3)
    results['score'] += check3['points']
    
    check4 = {'name': 'SKU', 'points': 0, 'max': 10, 'status': 'error', 'message': 'Manquant'}
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    if sku:
        check4 = {'name': 'SKU', 'points': 10, 'max': 10, 'status': 'success', 'message': sku}
    results['checks'].append(check4)
    results['score'] += check4['points']
    
    # Check Images : alt text + filename
    images = product.get('images', [])
    title = product.get('title', '')
    title_for_filename = title_to_filename(title)
    check5 = {'name': 'Images SEO', 'points': 0, 'max': 20, 'status': 'error', 'message': 'Aucune image'}
    if images:
        all_alt_ok = True
        all_filename_ok = True
        bad_alt = 0
        bad_filename = 0
        for img in images:
            alt = img.get('alt', '') or ''
            src = img.get('src', '') or ''
            filename = src.split('/')[-1].split('?')[0] if src else ''
            if alt != title:
                all_alt_ok = False
                bad_alt += 1
            if title_for_filename not in filename:
                all_filename_ok = False
                bad_filename += 1
        
        if all_alt_ok and all_filename_ok:
            check5 = {'name': 'Images SEO', 'points': 20, 'max': 20, 'status': 'success', 'message': f'{len(images)} images OK'}
        elif all_alt_ok:
            check5 = {'name': 'Images SEO', 'points': 10, 'max': 20, 'status': 'warning', 'message': f'Alt OK, {bad_filename} noms a corriger'}
        elif all_filename_ok:
            check5 = {'name': 'Images SEO', 'points': 10, 'max': 20, 'status': 'warning', 'message': f'Noms OK, {bad_alt} alt a corriger'}
        else:
            check5 = {'name': 'Images SEO', 'points': 0, 'max': 20, 'status': 'error', 'message': f'{bad_alt} alt + {bad_filename} noms a corriger'}
    results['checks'].append(check5)
    results['score'] += check5['points']
    
    if results['score'] >= 85: results['status'] = 'excellent'
    elif results['score'] >= 70: results['status'] = 'good'
    elif results['score'] >= 50: results['status'] = 'warning'
    else: results['status'] = 'poor'
    
    return results


MODEL_DESCRIPTIONS = {
    'jordan 4': "Conçue par Tinker Hatfield en 1989, la Air Jordan 4 allie mesh respirant, œillets en TPU et amorti Air visible au talon. Portée par MJ pour son premier titre de meilleur marqueur NBA, elle reste l'une des silhouettes les plus convoitées.",
    'jordan 3': "Première collaboration entre Michael Jordan et Tinker Hatfield en 1988, la Air Jordan 3 a introduit l'elephant print iconique et le logo Jumpman. Son amorti Air visible au talon et sa tige en cuir en font un classique intemporel.",
    'jordan 2': "Sortie en 1986, la Air Jordan 2 se distingue par son design épuré inspiré de la mode italienne, sans logo Swoosh. Son upper en cuir premium lui confère une allure luxueuse unique dans la lignée Jordan.",
    'jordan 5': "Dessinée par Tinker Hatfield en 1990, la Air Jordan 5 s'inspire des avions de chasse P-51 Mustang avec sa semelle translucide, ses empiècements en mesh et ses dents de requin sur la midsole. Un design agressif devenu culte.",
    'jordan 6': "Portée par MJ lors de son premier titre NBA en 1991 contre les Lakers, la Air Jordan 6 se reconnaît à son spoiler arrière, ses trous de ventilation et son système de laçage innovant. Une sneaker chargée d'histoire.",
    'jordan 7': "Chaussure des JO de Barcelone 1992 et du Dream Team, la Air Jordan 7 arbore un design coloré inspiré par l'art afro-pop. Première Jordan sans Nike Air visible, elle mise tout sur le style et la performance.",
    'jordan 11': "Chef-d'œuvre de Tinker Hatfield sorti en 1995, la Air Jordan 11 révolutionne le design sneaker avec son upper en cuir verni et sa semelle en fibre de carbone translucide. MJ la portait lors de son retour triomphal en NBA.",
    'jordan 12': "Inspirée du drapeau japonais et des chaussures habillées, la Air Jordan 12 accompagna MJ lors de la saison 72-10 en 1996-97 et du fameux Flu Game. Son cuir premium et ses coutures distinctives en font un modèle élégant.",
    'jordan 13': "Inspirée de la panthère noire, la Air Jordan 13 dispose d'un œil de chat holographique, d'une patte de panthère en semelle et de la technologie Zoom Air. La dernière Jordan portée par MJ en saison régulière.",
    'jordan 1 high': "Créée par Peter Moore en 1985, la Air Jordan 1 High est la sneaker qui a tout commencé. Bannie par la NBA pour infraction au code couleur, elle a généré 5 000 dollars d'amende par match, propulsant Nike et MJ dans la légende.",
    'jordan 1 low': "Version basse de la légendaire Air Jordan 1, la Low conserve le design iconique de 1985 avec un col plus bas pour un confort quotidien. Même cuir premium, même semelle Air, avec un profil plus discret et polyvalent.",
    'jordan 1 mid': "La Air Jordan 1 Mid offre le parfait équilibre entre la High et la Low avec un col intermédiaire. Sortie dans des centaines de coloris, elle reste l'entrée idéale dans l'univers Jordan.",
    'dunk low': "Créée en 1985 pour le programme basketball Be True To Your School, la Nike Dunk Low est l'une des silhouettes les plus populaires au monde. Sa tige en cuir, sa semelle cupsole et ses déclinaisons infinies en font un pilier du streetwear.",
    'dunk high': "La Nike Dunk High conserve le design original de 1985 avec sa tige montante et son col rembourré. Du basketball universitaire au skateboarding, elle a traversé les époques sans perdre son attrait.",
    'dunk': "Créée en 1985 pour le basketball universitaire, la Nike Dunk est devenue une icône grâce à son design épuré, ses matériaux premium et ses innombrables collaborations.",
    'air force 1': "Première sneaker à intégrer la technologie Air en 1982, la Nike Air Force 1 dessinée par Bruce Kilgore est le modèle le plus vendu de Nike. Son cuir premium, sa semelle Air et sa silhouette épaisse en font un classique absolu.",
    'air max 1': "Conçue par Tinker Hatfield en 1987 après une visite au Centre Pompidou, la Air Max 1 a révélé pour la première fois la bulle Air au monde. Son design et son window visible ont changé l'industrie du sneaker.",
    'air max 90': "Baptisée Air Max III en 1990, la Air Max 90 de Tinker Hatfield se distingue par ses couches superposées de mesh et daim, et son unité Air visible imposante. Un pilier de la culture urbaine.",
    'air max 95': "Conçue par Sergio Lozano en 1995, la Air Max 95 s'inspire de l'anatomie humaine : la semelle est la colonne vertébrale, les couches les muscles, le mesh la peau. Première Nike avec Air avant-pied et talon.",
    'air max 97': "Dessinée par Christian Tresser en 1997, la Air Max 97 s'inspire des trains Shinkansen japonais. Première sneaker avec une unité Air pleine longueur, ses lignes fluides et réfléchissantes sont devenues iconiques.",
    'air max plus': "Née en 1998, la Air Max Plus TN de Sean McDowell s'inspire des couchers de soleil de Floride. Ses lignes ondulées et son système Tuned Air en ont fait un phénomène mondial, particulièrement culte en France.",
    'air max dn': "La Nike Air Max Dn représente la nouvelle génération Air avec son système Dynamic Air composé de quatre unités Air Tube réactives. Design futuriste et amorti révolutionnaire.",
    'air max': "La gamme Air Max de Nike révolutionne le confort depuis 1987 avec sa bulle d'air visible, alliant innovation technologique et design audacieux, génération après génération.",
    'vomero': "La Nike Vomero 5, modèle running de 2000, fait son retour en streetwear. Ses superpositions cuir/mesh, sa technologie Zoom Air et son look chunky rétro-technique séduisent les amateurs de dad shoes.",
    'p-6000': "La Nike P-6000, inspirée des Pegasus du début des années 2000, combine cuir, mesh et détails réfléchissants dans une silhouette chunky. Sa technologie Air Zoom au talon assure un confort optimal.",
    'blazer': "Née sur les terrains de basket en 1973, la Nike Blazer est la première basketball Nike. Son upper en cuir, son Swoosh oversize et sa semelle vulcanisée en font une icône du style décontracté.",
    'samba': "Née en 1950 pour le football sur terrain gelé, l'Adidas Samba est l'une des chaussures les plus vendues de l'histoire. Son upper en cuir, sa semelle en gomme et son toe cap en T sont reconnaissables entre mille.",
    'campus': "Apparue dans les années 80, l'Adidas Campus se distingue par son upper en daim premium et ses trois bandes contrastées. Adoptée par le hip-hop new-yorkais puis le skate, elle incarne le style universitaire.",
    'gazelle': "Créée en 1966 comme chaussure d'entraînement polyvalente, l'Adidas Gazelle a conquis les terrains de foot, les scènes musicales et les rues. Son daim et son profil épuré en font un classique intemporel.",
    'spezial': "L'Adidas Spezial, née dans les années 70 pour le handball, incarne l'esprit terrace culture britannique. Son daim, sa semelle en gomme translucide et sa silhouette basse symbolisent le style casual européen.",
    'forum': "Sortie en 1984, l'Adidas Forum était la basketball la plus chère de l'époque. Son strap à boucle, son upper en cuir et sa silhouette imposante en ont fait un favori du hip-hop et du streetwear.",
    'sl 72': "Créée pour les JO de Munich en 1972, l'Adidas SL 72 était la compétition la plus légère de son époque. Son design running vintage en nylon et daim incarne le style sportif rétro.",
    'adilette': "Née en 1972, l'Adidas Adilette est la claquette la plus iconique de l'histoire. Conçue pour les vestiaires sportifs, son bandeau à trois bandes en a fait un accessoire de mode incontournable.",
    'yeezy slide': "La Yeezy Slide, conçue par Kanye West, est une sandale monobloc en mousse EVA injectée. Son design minimaliste, son confort exceptionnel et sa rareté en ont fait l'un des slides les plus désirées.",
    'yeezy 350': "La Yeezy Boost 350 V2, fruit de la collaboration Kanye West x Adidas, a révolutionné le marché sneaker en 2016. Son upper Primeknit, son boost pleine longueur et sa bande SPLY-350 sont reconnaissables.",
    'yeezy 700': "La Yeezy 700 Wave Runner, sortie en 2017, a relancé la tendance chunky. Ses couches de daim, mesh et cuir avec un amorti Boost encapsulé en font une pièce aussi confortable que visuellement audacieuse.",
    'foam runner': "La Yeezy Foam Runner est en mousse EVA et algues récoltées, dans une forme futuriste moulée d'une seule pièce. Son design organique perforé est devenu un phénomène culturel.",
    'new balance 550': "Ressortie des archives en 2020, la New Balance 550 de 1989 est une basketball au cuir premium et logo N en relief. Propulsée par la collaboration Aimé Leon Dore, elle incarne le revival vintage.",
    'new balance 530': "La New Balance 530, modèle running des années 90, séduit par son design chunky avec technologie ABZORB et tige en mesh/synthétique. Son esthétique Y2K et son confort en font une silhouette très demandée.",
    'new balance 2002r': "La New Balance 2002R combine les technologies N-ERGY et ABZORB SBS pour un confort premium. Son upper en daim et mesh avec silhouette arrondie est devenue un favori du streetwear contemporain.",
    'new balance 9060': "Sortie en 2022, la New Balance 9060 fusionne des éléments de la 990, 860 et 2002R. Ses lignes exagérées, ses superpositions daim/mesh et son amorti FuelCell en font un modèle d'avant-garde.",
    'new balance 1906': "La New Balance 1906R revisite un runner des années 2000 avec les technologies N-ERGY et ABZORB DTS. Son design rétro-futuriste en mesh et empiècements synthétiques plaît aux amateurs de silhouettes techniques.",
    'new balance 990': "Sortie en 1982, la New Balance 990 fut la première running à 100 dollars. Fabriquée aux USA, elle est devenue un symbole de qualité premium portée aussi bien par Steve Jobs que par des présidents américains.",
    'gel-1130': "Sortie en 2008, l'Asics Gel-1130 a resurgi en streetwear grâce à sa silhouette technique Y2K. Sa technologie Gel au talon, son upper en mesh/synthétique et son look rétro-technique sont irrésistibles.",
    'gel-kayano 14': "L'Asics Gel-Kayano 14, sortie en 2008, impressionne par son design ultra-technique avec gel visible et technologie IGS. Le modèle le plus prisé des amateurs de gorpcore et de silhouettes techniques.",
    'gel-kayano': "Lancée en 1993 par Toshikazu Kayano, l'Asics Gel-Kayano est la référence des running stabilisantes. Sa technologie Gel et son design technique en font une icône du running devenue pièce streetwear.",
    'gel-nyc': "Sortie en 2023, l'Asics Gel-NYC fusionne le Gel-Nimbus 3 et le MC Plus V. Son design hybride avec gel apparent, daim et mesh en fait l'une des sorties les plus remarquées de la marque japonaise.",
    'tasman': "La UGG Tasman combine la peau de mouton iconique avec un design slip-on inspiré du mocassin. Sa doublure en laine mérinos de 17mm, sa semelle Treadlite et ses coutures tressées offrent un confort exceptionnel.",
    'tazz': "La UGG Tazz revisite le classique Tasman avec une semelle plateforme en EVA qui ajoute 3cm de hauteur. Même confort en peau de mouton, même facilité d'enfilage, avec un twist contemporain.",
    'ultra mini': "La UGG Ultra Mini est la version compacte du classique boot UGG. Sa tige ultra-courte, sa doublure en peau de mouton recyclée et sa semelle Treadlite légère sont parfaites pour un style décontracté.",
    'crocs': "Inventées en 2002 avec le matériau breveté Croslite, les Crocs offrent une légèreté et un confort uniques. Des blocs opératoires aux podiums de mode, elles sont un phénomène mondial grâce aux Jibbitz personnalisables.",
    'birkenstock': "Fabriquées en Allemagne depuis 1774, les Birkenstock sont célèbres pour leur semelle anatomique en liège et latex naturel. Un confort orthopédique devenu symbole de style normcore.",
    'salomon': "Marque française d'Annecy depuis 1947, les Salomon ont conquis le streetwear avec la XT-6 et l'ACS Pro. Technologie Contagrip, design technique et résistance aux éléments.",
    'converse': "Les Converse Chuck Taylor, créées en 1917, sont les sneakers les plus vendues de tous les temps. Toile de coton, semelle vulcanisée et patch étoile All-Star : un symbole universel de la culture jeune.",
    'vans': "Nées en 1966 à Anaheim, les Vans sont indissociables de la culture skate. Leur semelle waffle, leur construction robuste et leur style décontracté incarnent l'esprit créatif de la côte ouest.",
    'timberland': "Les Timberland 6-Inch, surnommées Timbs, sont un symbole du hip-hop et de la culture urbaine depuis les années 90. Cuir nubuck imperméable, semelle anti-fatigue et durabilité légendaire.",
    'travis scott': "Les collaborations Travis Scott x Nike, lancées en 2019, se distinguent par leur Swoosh inversé, leurs coloris terreux et leurs détails cachés. Des pièces de collection qui prennent de la valeur.",
    'off-white': "Les collaborations Off-White x Nike de Virgil Abloh ont redéfini le concept de sneaker en 2017 avec The Ten. Esthétique déconstructiviste, zip-ties et inscriptions entre guillemets : un mouvement.",
    'bermuda': "L'Adidas Bermuda, modèle terrace des années 70, se distingue par son daim premium, sa semelle en gomme et son profil épuré. Symbole de la culture casual britannique et du style décontracté européen.",
    'superstar': "L'Adidas Superstar, née en 1969 sur les terrains de basketball, est devenue un pilier du hip-hop grâce à Run-DMC. Son shell toe en caoutchouc et ses trois bandes latérales en font l'une des sneakers les plus reconnaissables au monde.",
    'stan smith': "L'Adidas Stan Smith, lancée en 1971, est la sneaker minimaliste par excellence. Son cuir blanc épuré, son logo vert et sa silhouette intemporelle en ont fait le modèle le plus vendu d'Adidas et un symbole du style clean.",
    'nocta glide': "La Nike NOCTA Glide, fruit de la collaboration entre Nike et Drake (NOCTA), marie une base en mesh technique avec des overlays en texture carbone. Un design futuriste qui reflète l'esthétique premium de la ligne NOCTA.",
    'nocta': "La ligne NOCTA, collaboration entre Nike et Drake, propose des pièces premium alliant performance sportive et style urbain nocturne. Un design distinctif qui repousse les limites du streetwear.",
    'ae 1': "L'Adidas AE 1, signature shoe d'Anthony Edwards, est la chaussure de basketball de nouvelle génération. Son design audacieux et sa technologie Lightstrike Pro offrent performance et style sur et en dehors du terrain.",
    'yeezy 500': "La Yeezy 500, avec son design inspiré des dad shoes et sa semelle épaisse adiPRENE+, offre un look chunky rétro avec des empiècements en daim, mesh et cuir de vache. Un modèle phare de la gamme Yeezy.",
    'sb dunk low': "La Nike SB Dunk Low adapte le classique de 1985 aux besoins du skateboarding avec un col rembourré Zoom Air et une languette épaisse. Ses collaborations légendaires en ont fait un graal des collectionneurs.",
    'sb dunk high': "La Nike SB Dunk High combine l'ADN basketball de 1985 avec les exigences du skate : col rembourré, semelle Zoom Air et grip optimisé. Un modèle culte de la culture skateboard.",
    'bad bunny': "Les collaborations Bad Bunny x Adidas allient l'univers créatif du superstar portoricain avec le savoir-faire sportif d'Adidas. Des pièces audacieuses aux détails uniques qui reflètent l'esthétique avant-gardiste de l'artiste.",
    'pharrell': "Les collaborations Pharrell Williams x Adidas repoussent les limites du design avec des silhouettes innovantes et des coloris audacieux. L'expression de la vision créative sans frontières du producteur et entrepreneur.",
    # ── NIKE (modèles additionnels) ──
    'shox': "La Nike Shox, lancée en 2000, a révolutionné l'amorti avec ses colonnes mécaniques en mousse au talon. Son design futuriste et son système de ressort visible en ont fait un symbole du Y2K et de l'innovation Nike.",
    'kobe 4': "La Nike Kobe 4 Protro, signature shoe de Kobe Bryant sortie en 2009, a inauguré l'ère des chaussures de basketball basses. Son upper léger et son profil bas ont changé le jeu pour toujours.",
    'kobe 5': "La Nike Kobe 5, sortie en 2009, poursuit la révolution low-top de Kobe Bryant avec une tige en Flywire ultra-légère et un amorti Zoom Air. Un modèle technique au design agressif inspiré par la Mamba Mentality.",
    'kobe 6': "La Nike Kobe 6 Protro de 2010 pousse encore plus loin le concept low-top avec un profil ultra-bas et un upper en mesh 3D. Portée par Kobe lors de sa cinquième bague NBA, c'est une pièce chargée de légende.",
    'kobe 8': "La Nike Kobe 8 System, sortie en 2012, est la première Kobe signature en Engineered Mesh, offrant un upper ultra-léger et respirant. Un modèle qui incarne la quête d'innovation permanente de la Black Mamba.",
    'kobe': "Les Nike Kobe, ligne signature de Kobe Bryant, ont révolutionné la chaussure de basketball avec leur profil bas et leur légèreté. Chaque modèle incarne la Mamba Mentality : performance, précision et excellence.",
    'ld waffle': "La Nike LD Waffle, née de la collaboration avec Sacai, superpose deux sneakers en une avec sa double semelle, double languette et double Swoosh. Un design déconstructiviste devenu culte du streetwear.",
    'vaporwaffle': "La Nike VaporWaffle Sacai fusionne la Pegasus VaporFly et la LD 1000 dans un design hybride à double épaisseur signature de Sacai. Légèreté, transparence et superposition définissent cette collaboration iconique.",
    'killshot': "La Nike Killshot, modèle court de tennis vintage des années 80, est devenue un classique du style casual grâce à sa silhouette épurée en cuir et daim avec semelle en gomme.",
    'mac attack': "La Nike Mac Attack, chaussure de tennis de John McEnroe des années 80, fait son comeback avec son design rétro court en cuir et son Swoosh bold distinctif. Un classique du tennis devenu pièce streetwear.",
    'field general': "La Nike Field General, modèle d'entraînement football américain, a été réinventée par les collaborations Union LA avec des matériaux premium et un style vintage universitaire.",
    'cortez': "La Nike Cortez, première chaussure de running Nike créée par Bill Bowerman en 1972, est un symbole de la culture californienne et du style décontracté américain depuis plus de 50 ans.",
    'kd 4': "La Nike KD 4, signature shoe de Kevin Durant, combine Zoom Air au talon et semelle Phylon pour un amorti réactif. Son upper en Hyperfuse et son strap au médio-pied offrent maintien et légèreté.",
    'kd': "Les Nike KD, ligne signature de Kevin Durant, allient technologie de pointe et design épuré. Chaque modèle reflète le jeu fluide et polyvalent du Slim Reaper.",
    'air foamposite': "La Nike Air Foamposite One, sortie en 1997, est la première sneaker avec un upper moulé d'une seule pièce. Son design futuriste en mousse Foamposite et son look unique en font un graal des collectionneurs.",
    'air penny': "La Nike Air Penny, ligne signature d'Anfernee Penny Hardaway, se distingue par son design élégant et ses lignes fluides. Le logo 1 Cent et la technologie Air Zoom en font une icône du basketball des années 90.",
    'mind 001': "La Nike Mind 001, slide premium de nouvelle génération, propose un design minimaliste et futuriste avec un confort optimal. Une sandale qui redéfinit le segment du footwear décontracté.",
    'calm slide': "La Nike Calm Slide offre un confort enveloppant avec sa mousse texturée et son profil épuré. Un design minimaliste pensé pour la récupération et la détente après le sport.",
    'air zoom courtposite': "La Nike Air Zoom Courtposite fusionne la technologie Foamposite avec le design tennis pour une silhouette unique. Portée par les collaborations Supreme, elle est devenue un objet de collection rare.",
    'sb darwin': "La Nike SB Darwin Low, modèle skateboard au profil épuré, combine cuir premium et semelle vulcanisée pour un style décontracté. Ses collaborations Supreme en ont fait une pièce très recherchée.",
    'total 90': "La Nike Total 90, chaussure de football iconique du début des années 2000, revient en version lifestyle. Son design technique agressif et ses empiècements en TPU sont devenus cultes dans la culture street.",
    'air dt max': "La Nike Air DT Max '96, chaussure d'entraînement de Deion Sanders, se distingue par son strap imposant et son design audacieux des années 90. Un modèle cross-training devenu pièce de collection.",
    'nikecraft': "Les Nike NikeCraft, collaboration avec l'artiste Tom Sachs, proposent des chaussures utilitaires au design brut et fonctionnel. La General Purpose Shoe incarne une philosophie de simplicité et d'usure assumée.",
    'astro grabber': "La Nike Astro Grabber, modèle vintage de football américain, a été réinventée par la collaboration Bode avec des matériaux artisanaux et un esprit rétro-bohème unique.",
    'air humara': "La Nike Air Humara, modèle trail des années 2000, fait son retour avec son design outdoor technique. Sa semelle crantée et son upper en mesh/cuir séduisent les amateurs de gorpcore.",
    # ── ADIDAS (modèles additionnels) ──
    'bw army': "L'Adidas BW Army (Bundeswehr Army), issue de l'armée allemande, est un modèle militaire réapproprié par le streetwear. Son cuir épuré, sa semelle en gomme et son profil bas en font un classique discret et élégant.",
    # ── NEW BALANCE (modèles additionnels) ──
    'new balance 991': "La New Balance 991, fabriquée en Angleterre (Made in UK), combine technologies ABZORB et Encap pour un confort premium. Son upper en daim et mesh avec des finitions artisanales en fait un modèle haut de gamme.",
    'new balance 993': "La New Balance 993, dernière de la lignée 99X Made in USA, est devenue un symbole de l'élite discrète. Son amorti ABZORB DTS et son cuir premium en font la sneaker de ceux qui savent.",
    'new balance 574': "La New Balance 574, sortie en 1988, est le modèle le plus populaire de New Balance. Son design running rétro en daim et mesh avec technologie Encap offre un confort quotidien intemporel.",
    'new balance 860': "La New Balance 860, modèle running stabilisant, combine technologies ABZORB et Trufuse pour un maintien optimal. Son design technique et ses lignes dynamiques séduisent les amateurs de silhouettes sportives.",
    'new balance 1000': "La New Balance 1000, runner technique des années 2000, fait son retour grâce aux collaborations comme Aimé Leon Dore. Son design chunky rétro et ses technologies d'amorti en font un modèle prisé.",
    'new balance 992': "La New Balance 992, Made in USA et portée par Steve Jobs, est un pilier de la gamme premium NB. Son amorti ABZORB SBS et son upper en daim/mesh gris en font le symbole du confort discret et raffiné.",
    'new balance 740': "La New Balance 740, modèle running rétro-technique, revient sur le devant de la scène avec un design Y2K et des technologies d'amorti modernes. Une silhouette qui séduit la nouvelle génération.",
    'new balance 204': "La New Balance 204L est un modèle technique qui allie innovation et esthétique contemporaine. Son design distinctif et ses matériaux premium en font une pièce remarquée du catalogue New Balance.",
    'abzorb 2000': "La New Balance Abzorb 2000 tire son nom de la technologie d'amorti ABZORB signature de la marque. Son design technique des années 2000 et son profil chunky en font un modèle streetwear recherché.",
    # ── ASICS (modèles additionnels) ──
    'gel-cumulus': "L'Asics Gel-Cumulus, modèle running neutre depuis 1997, offre un amorti Gel confortable et un upper respirant. Sa silhouette technique retro séduit aussi bien les coureurs que les amateurs de streetwear.",
    'gel-lyte iii': "L'Asics Gel-Lyte III, conçue par Shigeyuki Mitsui en 1990, a introduit la languette fendue split-tongue devenue iconique. Son amorti Gel et son design coloré en font un classique du running rétro.",
    'gel-lyte': "L'Asics Gel-Lyte, lancée en 1987, a été la première chaussure à intégrer la technologie d'amorti Gel. Son design running vintage et ses lignes épurées en font un pilier du streetwear japonais.",
    'gt-2160': "L'Asics GT-2160, modèle running stabilisant sorti en 2009, impressionne par son design ultra-technique. Sa technologie Gel et son upper structuré en font un favori du style gorpcore et technique.",
    'gel-nimbus': "L'Asics Gel-Nimbus, référence de l'amorti neutre depuis 1999, offre un confort maximal grâce à ses unités Gel avant-pied et talon. Son design technique et moderne en fait un modèle polyvalent.",
    'gel-quantum': "L'Asics Gel-Quantum 360 enveloppe le pied dans une semelle Gel à 360 degrés pour un amorti intégral. Son design futuriste et son confort maximal en font un modèle unique dans la gamme Asics.",
    # ── UGG (modèles additionnels) ──
    'classic mini': "La UGG Classic Mini, version courte du classique boot UGG, offre la même doublure en peau de mouton et la même semelle Treadlite dans un format compact et polyvalent, parfait pour toutes les saisons.",
    'disquette': "La UGG Disquette, slipper plateforme au design audacieux, combine la peau de mouton UGG avec une semelle surélevée en sucre canne. Un modèle statement qui a conquis les réseaux sociaux.",
    'goldenstar': "La UGG Goldenstar Clog revisite le sabot classique avec la peau de mouton signature UGG et une semelle plateforme. Un modèle confort-first devenu incontournable du style casual.",
    'lowmel': "La UGG Lowmel est une mule plateforme moderne qui combine la doublure en peau de mouton UGG avec un design contemporain. Un modèle facile à enfiler pour un confort instantané.",
    # ── PUMA ──
    'speedcat': "La Puma Speedcat, inspirée des chaussures de pilotes de Formule 1, se distingue par son profil ultra-bas et sa semelle fine. Son design racing minimaliste en fait un modèle tendance du moment.",
    'puma suede': "La Puma Suede, née en 1968 sur les podiums olympiques de Mexico, est un classique du streetwear et du hip-hop. Son upper en daim, sa forme basse et ses coloris variés traversent les décennies.",
    'lamelo': "Les Puma LaMelo Ball, signature shoe du prodige NBA, combinent design avant-gardiste et technologies de performance. L'expression du style flamboyant et du jeu spectaculaire de Melo.",
    # ── AUTRES ──
    'fear of god': "Fear of God, marque fondée par Jerry Lorenzo en 2013, fusionne luxe et streetwear dans des pièces essentielles. La ligne Essentials propose des basiques premium au design minimaliste et intemporel.",
    'dior b23': "La Dior B23, sneaker haute couture de la maison Dior, arbore le motif Oblique signature sur une toile technique. Un modèle de luxe qui incarne la fusion entre mode et culture sneaker.",
    'mschf': "MSCHF, collectif artistique new-yorkais, crée des sneakers provocatrices qui remettent en question les codes du marché. La Big Red Boot, devenue virale, illustre leur approche disruptive du design.",
    'adifom': "L'Adidas adiFOM réinvente des silhouettes classiques avec un matériau mousse monobloc futuriste. Un design minimaliste et organique qui transforme les icônes Adidas en pièces d'art contemporain.",

}

DEFAULT_DESC = "Un modèle premium qui allie qualité de fabrication et design soigné, pensé pour ceux qui recherchent style et confort au quotidien."




def get_model_description(title):
    t = title.lower()
    # Vérifier les clés les plus longues (spécifiques) d'abord
    sorted_keys = sorted(MODEL_DESCRIPTIONS.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in t:
            return MODEL_DESCRIPTIONS[key]
    
    # Matching avancé pour les Jordan (titres Shopify: "Air Jordan X Retro High/Low/Mid OG ...")
    if 'jordan 1' in t:
        if 'high' in t: return MODEL_DESCRIPTIONS.get('jordan 1 high', DEFAULT_DESC)
        if 'low' in t: return MODEL_DESCRIPTIONS.get('jordan 1 low', DEFAULT_DESC)
        if 'mid' in t: return MODEL_DESCRIPTIONS.get('jordan 1 mid', DEFAULT_DESC)
    if 'jordan 4' in t: return MODEL_DESCRIPTIONS.get('jordan 4', DEFAULT_DESC)
    if 'jordan 3' in t: return MODEL_DESCRIPTIONS.get('jordan 3', DEFAULT_DESC)
    if 'jordan 2' in t and 'jordan 2002' not in t: return MODEL_DESCRIPTIONS.get('jordan 2', DEFAULT_DESC)
    if 'jordan 5' in t: return MODEL_DESCRIPTIONS.get('jordan 5', DEFAULT_DESC)
    if 'jordan 6' in t: return MODEL_DESCRIPTIONS.get('jordan 6', DEFAULT_DESC)
    if 'jordan 7' in t: return MODEL_DESCRIPTIONS.get('jordan 7', DEFAULT_DESC)
    if 'jordan 11' in t: return MODEL_DESCRIPTIONS.get('jordan 11', DEFAULT_DESC)
    if 'jordan 12' in t: return MODEL_DESCRIPTIONS.get('jordan 12', DEFAULT_DESC)
    if 'jordan 13' in t: return MODEL_DESCRIPTIONS.get('jordan 13', DEFAULT_DESC)
    
    # Matching par mots-clés larges
    broad = {
        'dunk': 'dunk', 'air force': 'air force 1', 'air max': 'air max',
        'samba': 'samba', 'campus': 'campus', 'gazelle': 'gazelle',
        'forum': 'forum', 'superstar': 'superstar', 'stan smith': 'stan smith',
        'yeezy': 'yeezy 350', 'jordan': 'jordan 1 high',
        'gel 1130': 'gel-1130', 'gel kayano': 'gel-kayano', 'gel nyc': 'gel-nyc',
        'gel lyte': 'gel-lyte', 'gel nimbus': 'gel-nimbus', 'gel quantum': 'gel-quantum',
        'gel cumulus': 'gel-cumulus',
    }
    for kw, key in broad.items():
        if kw in t and key in MODEL_DESCRIPTIONS:
            return MODEL_DESCRIPTIONS[key]
    
    return DEFAULT_DESC



def generate_meta_title(product):
    title = product.get('title', '')
    meta_title = title + ' | ' + SITE_NAME
    if len(meta_title) > 60:
        meta_title = title[:47] + '... | ' + SITE_NAME
    return meta_title


def generate_meta_description(product):
    title = product.get('title', '')
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    brand = extract_brand(title)
    colorway = extract_colorway(title)
    
    # ── VÊTEMENTS ──
    if is_clothing(title):
        clothing_type = get_clothing_type(title)
        color = extract_clothing_color(title)
        if color:
            desc = f"{title} sur {SITE_NAME}. {clothing_type.capitalize()} streetwear premium, coloris {color}. 100% authentique, livraison rapide en France."
        else:
            desc = f"{title} sur {SITE_NAME}. {clothing_type.capitalize()} streetwear premium, 100% authentique. Livraison rapide en France."
        if len(desc) > 155:
            desc = desc[:152].rsplit(' ', 1)[0] + '...'
        return desc
    
    # ── SNEAKERS ──
    collabs = ['Travis Scott', 'Off-White', 'Fragment', 'Union LA', 'Undefeated', 'A Ma Maniere',
               'Sacai', 'CLOT', 'Stussy', 'Patta', 'Supreme', 'BAPE', 'Kith', 'Bad Bunny',
               'Pharrell', 'Drake', 'NOCTA', 'The Simpsons', 'Mercedes AMG', 'Jacquemus', 'Nigo']
    is_collab = any(c.lower() in title.lower() for c in collabs)
    
    if is_collab:
        desc = f"{title} sur {SITE_NAME}. Édition limitée 100% authentique, vérifiée par nos experts. Livraison rapide en France."
    elif colorway and sku:
        desc = f"{title} ({sku}) sur {SITE_NAME}. Coloris {colorway}, 100% authentique. Livraison rapide et paiement sécurisé."
    elif colorway:
        desc = f"Achetez la {title} sur {SITE_NAME}. Coloris {colorway}, authenticité garantie par nos experts. Livraison rapide."
    elif sku:
        desc = f"Achetez la {title} ({sku}) sur {SITE_NAME}. 100% authentique, vérifiée par nos experts. Livraison rapide."
    else:
        desc = f"Achetez la {title} sur {SITE_NAME}. Authenticité garantie, vérifiée par nos experts. Livraison rapide et paiement sécurisé."
    
    if len(desc) > 155:
        desc = desc[:152].rsplit(' ', 1)[0] + '...'
    return desc




def extract_colorway(title):
    """Extrait le coloris/version spécifique du titre produit"""
    t = title
    # Enlever la marque
    brands = ['Nike', 'Adidas', 'New Balance', 'Asics', 'Puma', 'Reebok', 'UGG', 'Crocs', 'Salomon', 'Birkenstock', 'Vans', 'Converse']
    for b in brands:
        if t.startswith(b + ' '):
            t = t[len(b)+1:]
            break
    
    # Enlever le modèle pour garder le coloris
    models = [
        # Jordan (du plus spécifique au moins spécifique)
        'Air Jordan 4 Retro OG SP', 'Air Jordan 4 Retro SE', 'Air Jordan 4 Retro Premium', 'Air Jordan 4 Retro',
        'Air Jordan 1 Retro High OG SP', 'Air Jordan 1 Retro High OG', 'Air Jordan 1 Retro High',
        'Air Jordan 1 Retro Low OG SP', 'Air Jordan 1 Retro Low OG', 'Air Jordan 1 Low SE', 'Air Jordan 1 Low',
        'Air Jordan 1 Mid SE', 'Air Jordan 1 Mid', 'Air Jordan 1 High',
        'Air Jordan 2 Retro', 'Air Jordan 3 Retro', 'Air Jordan 5 Retro', 'Air Jordan 6 Retro',
        'Air Jordan 7 Retro', 'Air Jordan 8 Retro', 'Air Jordan 9 Retro',
        'Air Jordan 11 Retro Low', 'Air Jordan 11 Retro', 'Air Jordan 12 Retro', 'Air Jordan 13 Retro',
        # Nike
        'Dunk Low Retro SP', 'Dunk Low Retro', 'Dunk Low SE', 'Dunk Low', 'Dunk High Retro', 'Dunk High',
        'Air Force 1 Low Retro', 'Air Force 1 Low', 'Air Force 1 High', 'Air Force 1 Mid', 'Air Force 1',
        'Air Max 1', 'Air Max 90', 'Air Max 95', 'Air Max 97', 'Air Max Plus', 'Air Max TN',
        'Vomero 5', 'Vomero', 'P-6000', 'Blazer Mid', 'Blazer Low', 'Blazer',
        # Adidas
        'Samba OG', 'Samba Decon', 'Samba', 'Campus 00s', 'Campus', 'Gazelle Bold', 'Gazelle Indoor', 'Gazelle',
        'Handball Spezial', 'Spezial', 'Forum Low', 'Forum Mid', 'Forum 84 Low', 'Forum',
        'SL 72 OG', 'SL 72', 'Adilette 22', 'Adilette',
        # Yeezy
        'Yeezy Slide', 'Yeezy Boost 350 V2', 'Yeezy 350 V2', 'Yeezy 350', 'Yeezy 700 V3', 'Yeezy 700',
        'Yeezy Foam Runner', 'Yeezy 500',
        # New Balance
        '550', '530', '2002R', '9060', '1906R', '990v6', '990v5', '990v4', '990v3', '990',
        '993', '2002', '327', '574', '480',
        # Asics
        'Gel-1130', 'Gel-Kayano 14', 'Gel-Kayano', 'Gel-NYC', 'Gel-Nimbus 9', 'GT-2160',
        # UGG
        'Tasman Slipper', 'Tasman', 'Tazz Slipper', 'Tazz Platform', 'Tazz',
        'Ultra Mini Platform', 'Ultra Mini', 'Classic Mini II Boot', 'Classic Mini II', 'Classic Mini',
        'Classic Short II Boot', 'Classic Short II', 'Classic Short',
        'Disquette Slipper', 'Disquette', 'Goldenstar Clog', 'Goldenstar',
        'Lowmel', 'Scuffette II',
        # Autres
        'SB Dunk Low', 'SB Dunk High',  # Nike SB
        'NOCTA Glide', 'NOCTA Hot Step',  # NOCTA
        'AE 1', 'AE1',  # Adidas AE
        'Bermuda', 'Superstar', 'Stan Smith',  # Adidas
        'adiFOM Superstar',  # Adidas
        'Yeezy 500', 'Yeezy Boost 380',  # Yeezy
        'Adiracer GT', 'Adistar Jellyfish',  # Adidas collab
        'Adizero SL 72',  # Adidas
        'Classic Clog', 'Classic Slide',  # Crocs
        'Old Skool', 'Sk8-Hi', 'Era', 'Authentic',  # Vans
        'Chuck Taylor', 'Chuck 70',  # Converse
        'XT-6', 'XT-4', 'ACS Pro',  # Salomon
    ]
    
    colorway = t
    for m in models:
        if t.startswith(m + ' '):
            colorway = t[len(m)+1:]
            break
        elif t.startswith(m):
            colorway = t[len(m):]
            break
    
    colorway = colorway.strip(' -')
    return colorway if colorway and colorway != t else ''


def generate_color_description_ai(title, colorway, brand, model_desc):
    """Utilise l'API Claude pour générer une description spécifique au coloris"""
    if not colorway:
        return '', 'color'
    
    try:
        prompt = f"""Tu es un expert sneakers qui rédige des descriptions produits pour un site e-commerce français (KP SHOES).

Produit : {title}
Coloris/version : {colorway}
Marque : {brand}

Écris UNE SEULE phrase (2-3 lignes max) décrivant spécifiquement ce coloris/cette version. 
- Décris les couleurs réelles de la paire (pas juste traduire le nom)
- Si c'est une collaboration, mentionne-la
- Si c'est un coloris iconique (Chicago, Bred, Panda, etc.), mentionne son histoire
- Sois précis et naturel, pas générique
- Ne commence PAS par "Le coloris" ou "Cette version"
- Réponds UNIQUEMENT avec la phrase, rien d'autre."""

        api_url = "https://api.anthropic.com/v1/messages"
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': os.environ.get('ANTHROPIC_API_KEY', ''),
            'anthropic-version': '2023-06-01'
        }
        data = {
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 150,
            'messages': [{'role': 'user', 'content': prompt}]
        }
        
        if not headers['x-api-key']:
            return generate_color_sentence_fallback(title, colorway)
        
        req = Request(api_url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urlopen(req, context=ctx, timeout=15) as r:
            result = json.loads(r.read().decode('utf-8'))
            if result.get('content') and result['content'][0].get('text'):
                sentence = result['content'][0]['text'].strip()
                # Déterminer le type via le fallback logic
                _, cw_type = generate_color_sentence_fallback(title, colorway)
                return sentence, cw_type
    except Exception as e:
        log.error(f"[AI Color] Error: {e}")
    
    return generate_color_sentence_fallback(title, colorway)


def generate_color_sentence_fallback(title, colorway):
    """Fallback sans IA pour la description coloris"""
    if not colorway:
        return '', 'color'
    
    collabs = ['Travis Scott', 'Off-White', 'Fragment', 'Union LA', 'Undefeated', 'A Ma Maniere', 
               'A Ma Maniére', 'J Balvin', 'PSG', 'Eminem', 'Fear of God', 'Sacai', 'CLOT', 'Stussy',
               'Patta', 'Concepts', 'atmos', 'Supreme', 'BAPE', 'Kith', 'JJJJound', 'Nocta',
               'Billie Eilish', 'Bad Bunny', 'Pharrell', 'Drake', 'UNDFTD', 'Cactus Jack',
               'Union', 'Ambush', 'Comme des Garcons', 'CDG', 'Social Status', 'SoleFly',
               'The Simpsons', 'Nigo', 'Mercedes AMG', 'Dodgers', 'Yankees', 'Georgia Bulldogs',
               'Manchester United', 'Gratitude', 'What The', 'Aleali May', 'Melody Ehsani',
               'Maison Chateau Rouge', 'Jacquemus']
    
    for collab in collabs:
        if collab.lower() in colorway.lower() or collab.lower() in title.lower():
            sentence = f'Fruit de la collaboration exclusive avec {collab}, cette édition se distingue par un design unique et des détails soignés qui en font une pièce très convoitée.'
            return sentence, 'collab'
    
    # Coloris iconiques avec descriptions spécifiques
    iconic = {
        'chicago': "Habillée du légendaire coloris Chicago — rouge, blanc et noir — cette paire rend hommage à la ville qui a vu naître la dynastie Jordan et la culture sneaker.",
        'bred': "Le coloris Bred (Black/Red), indissociable de Michael Jordan et de la marque Jordan, reste l'un des duos de couleurs les plus emblématiques de l'histoire des sneakers.",
        'royal': "Le coloris Royal Blue, associé à la Air Jordan depuis 1985, offre un contraste saisissant entre le bleu royal et le noir qui en fait un classique intemporel.",
        'panda': "Le coloris Panda, combinaison épurée de noir et blanc, est devenu un phénomène viral et l'un des coloris les plus demandés de ces dernières années.",
        'shadow': "Le coloris Shadow, mélange subtil de noir et gris, apporte une élégance discrète et polyvalente qui se marie avec toutes les tenues.",
        'mocha': "Le coloris Mocha associe des tons marron chocolat au noir et au blanc, créant une palette chaleureuse inspirée des teintes café très prisée des collectionneurs.",
        'university blue': "Le coloris University Blue s'inspire du bleu de l'université de Caroline du Nord (UNC), alma mater de Michael Jordan, créant un lien direct avec les racines de la marque.",
        'cool grey': "Le coloris Cool Grey, popularisé par la Air Jordan 11 en 2001, offre une palette de gris sophistiquée et passe-partout devenue un classique de la gamme.",
        'infrared': "Le coloris Infrared, associé aux Air Max 90 depuis 1990, est reconnaissable à son rouge-rose éclatant qui a défini l'identité visuelle de ce modèle iconique.",
        'triple white': "Cette version Triple White propose un look monochrome immaculé et épuré, parfait pour un style minimaliste et élégant au quotidien.",
        'triple black': "Cette version Triple Black offre un look monochrome total en noir, alliant discrétion et sophistication pour un style urbain affirmé.",
        'lost and found': "L'édition Lost and Found reproduit l'effet d'une paire vintage retrouvée dans un entrepôt, avec un cuir craquelé vieilli et une boîte jaunie par le temps.",
        'reimagined': "L'édition Reimagined revisite un coloris classique avec des finitions vintage et un cuir premium vieilli pour un look authentique dès la sortie de boîte.",
        'washed': "Cette édition Washed présente un traitement délavé sur les matériaux, donnant un aspect vintage porté qui séduit les amateurs de style rétro.",
        'reverse mocha': "Le Reverse Mocha inverse les panneaux du coloris Mocha original, plaçant le daim marron sur la base et le blanc en overlay pour un résultat distinctif.",
        'military black': "Le coloris Military Black associe des tons noirs, gris et blancs dans une palette sobre et polyvalente d'inspiration militaire.",
        'oxidized green': "Le coloris Oxidized Green s'inspire de la patine du cuivre oxydé, offrant des tons verts émeraude vieillis pour un rendu unique.",
        'cement': "Le coloris Cement rend hommage à l'elephant print iconique de la Jordan 3, avec ses motifs gris éclaboussés devenus signature de la marque.",
    }
    
    cl = colorway.lower()
    for key, desc in iconic.items():
        if key in cl:
            return desc, 'color'
    
    # Détecter si c'est un vrai nom de couleur
    color_keywords = [
        'black', 'white', 'red', 'blue', 'green', 'grey', 'gray', 'pink', 'purple',
        'orange', 'yellow', 'brown', 'beige', 'cream', 'navy', 'olive', 'gold', 'silver',
        'sail', 'bone', 'sand', 'smoke', 'royal', 'bred', 'panda', 'shadow', 'mocha',
        'cement', 'infrared', 'scarlet', 'burgundy', 'core black', 'cloud white',
        'phantom', 'mushroom', 'tan', 'cobalt', 'teal', 'coral', 'mint', 'lavender',
        'rust', 'sesame', 'slate', 'charcoal', 'chalk', 'dark', 'light', 'pure',
        'noir', 'blanc', 'rouge', 'bleu', 'vert', 'rose', 'gris',
        'indigo', 'khaki', 'ivory', 'onyx', 'ochre', 'lime', 'crimson', 'magnet',
        'stone', 'forest', 'dust', 'metallic', 'chrome', 'platinum', 'copper',
        'midnight', 'graphite', 'glow', 'alabaster', 'fossil', 'sea salt', 'rain cloud',
        'desert', 'azure', 'peach', 'plum', 'amber', 'mauve', 'cardinal', 'aqua',
    ]
    
    has_color = any(kw in cl for kw in color_keywords)
    
    if has_color:
        sentence = f'Proposée dans le coloris "{colorway}", cette paire affirme son identité avec une combinaison de teintes et de matières qui lui est propre.'
        return sentence, 'color'
    
    # Pas de couleur détectée et pas de collab → édition spéciale
    sentence = f'Cette édition "{colorway}" se démarque par son identité visuelle unique et ses finitions soignées.'
    return sentence, 'edition'



def is_clothing(title):
    """Détecte si le produit est un vêtement (pas une sneaker)"""
    clothing_kw = ['hoodie', 'sweatpant', 'sweatshort', 'tee ', 't-shirt', 'crewneck', 'jacket',
                   'pant ', 'pants', 'short ', 'shorts']
    t = title.lower()
    return any(kw in t for kw in clothing_kw)


def get_clothing_type(title):
    """Retourne le type de vêtement en français"""
    t = title.lower()
    if 'hoodie' in t: return 'hoodie'
    if 'sweatpant' in t: return 'jogging'
    if 'sweatshort' in t: return 'short'
    if 'crewneck' in t or 's/s tee' in t or 'ss tee' in t or 't-shirt' in t or 'tee ' in t: return 't-shirt'
    if 'jacket' in t: return 'veste'
    if 'pant' in t: return 'pantalon'
    if 'short' in t: return 'short'
    return 'pièce'


def extract_clothing_color(title):
    """Extrait la couleur d'un vêtement depuis le titre"""
    t = title
    # Supprimer les patterns connus pour garder la couleur à la fin
    for remove in ['Fear Of God Fear of God Essentials ', 'Fear Of God ', '(FW24)', '(SS25)', '(FW23)']:
        t = t.replace(remove, '')
    # Le dernier mot/groupe est généralement la couleur
    parts = t.strip().split()
    # Trouver où commence la couleur (après le type de vêtement)
    clothing_words = ['Classic', 'Fleece', 'Essential', 'Jersey', 'Crewneck', 'Core', 'Collection',
                      'Heavy', 'S/S', 'SS', 'NBA', 'Relaxed', 'Hoodie', 'Sweatpant', 'Sweatshort',
                      'Sweatshorts', 'Tee', 'T-Shirt']
    color_start = 0
    for i, p in enumerate(parts):
        if p in clothing_words:
            color_start = i + 1
    color = ' '.join(parts[color_start:]) if color_start < len(parts) else ''
    return color.strip()


def generate_body_html(product, collections):
    title = product.get('title', '')
    brand = extract_brand(title)
    sku = product['variants'][0].get('sku', '') if product.get('variants') else ''
    collection = find_collection(title, collections)
    
    # ── VÊTEMENTS ──
    if is_clothing(title):
        clothing_type = get_clothing_type(title)
        color = extract_clothing_color(title)
        
        lines = []
        # Paragraphe 1: Introduction
        if collection:
            lines.append(f'<p>Découvrez le <strong>{title}</strong> disponible sur {SITE_NAME}. Retrouvez cette pièce et bien d\'autres dans notre collection <a href="{collection["url"]}">{collection["title"]}</a>.</p>')
        else:
            lines.append(f'<p>Découvrez le <strong>{title}</strong> disponible sur {SITE_NAME}.</p>')
        
        # Paragraphe 2: Description de la marque/ligne
        if 'essentials' in title.lower():
            lines.append(f'<p>La ligne Essentials de Fear of God, créée par Jerry Lorenzo, propose des basiques streetwear premium au design minimaliste et intemporel. Chaque pièce se distingue par sa coupe oversize signature, ses matériaux de haute qualité et le logo Essentials discret qui est devenu un symbole du luxe décontracté.</p>')
        else:
            lines.append(f'<p>{get_model_description(title)}</p>')
        
        # Paragraphe 3: Description spécifique à la pièce
        type_descs = {
            'hoodie': f'Ce hoodie en molleton épais offre un confort enveloppant avec sa capuche doublée, sa poche kangourou et ses finitions côtelées aux poignets et à la taille. Une pièce essentielle de toute garde-robe streetwear.',
            'jogging': f'Ce jogging en molleton premium allie confort et style avec sa coupe décontractée, sa taille élastiquée à cordon et ses finitions côtelées aux chevilles. Parfait pour un look streetwear complet.',
            'short': f'Ce short en molleton combine confort et style décontracté avec sa coupe ample, sa taille élastiquée et ses finitions soignées. Idéal pour un look casual urbain.',
            't-shirt': f'Ce t-shirt en jersey de coton premium offre une coupe ample et décontractée avec des coutures renforcées et une finition douce au toucher. Un basique streetwear élevé au rang de pièce premium.',
            'veste': f'Cette veste allie fonctionnalité et esthétique streetwear avec ses matériaux premium et sa coupe contemporaine.',
        }
        desc = type_descs.get(clothing_type, f'Cette pièce incarne l\'esthétique minimaliste et premium de la collection, avec des matériaux de haute qualité et une coupe contemporaine.')
        lines.append(f'<p>{desc}</p>')
        
        # Paragraphe 4: Caractéristiques
        tech_items = []
        if sku:
            tech_items.append(f'<li><strong>Référence :</strong> {sku}</li>')
        tech_items.append(f'<li><strong>Marque :</strong> Fear of God Essentials</li>')
        tech_items.append(f'<li><strong>Type :</strong> {clothing_type.capitalize()}</li>')
        if color:
            tech_items.append(f'<li><strong>Coloris :</strong> {color}</li>')
        lines.append('<ul style="list-style:none;padding-left:0;">' + ''.join(tech_items) + '</ul>')
        
        # Paragraphe 5: Garanties
        lines.append(f'<p>Chez <strong>{SITE_NAME}</strong>, nous garantissons l\'authenticité de chaque article. Tous nos produits sont vérifiés par nos experts avant expédition. Livraison rapide et paiement sécurisé.</p>')
        
        return ''.join(lines)
    
    # ── SNEAKERS (logique existante) ──
    model_desc = get_model_description(title)
    colorway = extract_colorway(title)
    
    # Obtenir la phrase + le type (color, collab, edition)
    if colorway:
        color_sentence, cw_type = generate_color_description_ai(title, colorway, brand, model_desc)
    else:
        color_sentence, cw_type = '', 'color'
    
    lines = []
    
    # Paragraphe 1: Introduction avec lien collection
    if collection:
        lines.append(f'<p>Découvrez la <strong>{title}</strong> disponible sur {SITE_NAME}. Retrouvez ce modèle et bien d\'autres dans notre collection <a href="{collection["url"]}">{collection["title"]}</a>.</p>')
    else:
        lines.append(f'<p>Découvrez la <strong>{title}</strong> disponible sur {SITE_NAME}.</p>')
    
    # Paragraphe 2: Description du modèle
    lines.append(f'<p>{model_desc}</p>')
    
    # Paragraphe 3: Description spécifique au coloris/collab
    if color_sentence:
        lines.append(f'<p>{color_sentence}</p>')
    
    # Paragraphe 4: Caractéristiques techniques
    tech_items = []
    if sku:
        tech_items.append(f'<li><strong>Référence :</strong> {sku}</li>')
    tech_items.append(f'<li><strong>Marque :</strong> {brand}</li>')
    if colorway:
        if cw_type == 'collab':
            tech_items.append(f'<li><strong>Édition :</strong> {colorway}</li>')
        else:
            tech_items.append(f'<li><strong>Coloris :</strong> {colorway}</li>')
    lines.append('<ul style="list-style:none;padding-left:0;">' + ''.join(tech_items) + '</ul>')
    
    # Paragraphe 5: Garanties KP SHOES
    lines.append(f'<p>Chez <strong>{SITE_NAME}</strong>, nous garantissons l\'authenticité de chaque paire. Toutes nos sneakers sont vérifiées par nos experts avant expédition. Livraison rapide et paiement sécurisé.</p>')
    
    return ''.join(lines)


def update_seo_field(pid, field, value):
    if field == 'body_html':
        shopify_request(f'products/{pid}.json', 'PUT', {'product': {'id': pid, 'body_html': value}})
    elif field == 'meta_title':
        shopify_request(f'products/{pid}/metafields.json', 'POST', {'metafield': {'namespace': 'global', 'key': 'title_tag', 'value': value, 'type': 'single_line_text_field'}})
    elif field == 'meta_description':
        shopify_request(f'products/{pid}/metafields.json', 'POST', {'metafield': {'namespace': 'global', 'key': 'description_tag', 'value': value, 'type': 'single_line_text_field'}})
    return True



