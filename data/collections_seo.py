"""
KP SHOES - SEO des collections
Format WetTheNew: H2 titre + intro + H2 histoire + paragraphe
Contenu visible, pas de display:none
"""

# Style wrapper appliqué à chaque description
_S = '<div class="collection-seo" style="max-width:900px;margin:40px auto 20px;padding:0 20px;line-height:1.8;color:#555;font-size:14px">'
_E = '</div>'
_H1 = '<h2 style="font-size:20px;color:#222;margin:0 0 14px 0;font-weight:600">'
_H2 = '<h2 style="font-size:17px;color:#222;margin:32px 0 10px 0;font-weight:600">'
_P = '<p style="margin:0 0 16px 0">'

COLLECTION_SEO = {

    # ══════════════════════════════════════════
    # JORDAN
    # ══════════════════════════════════════════

    'jordan-1': {
        'meta_title': 'Air Jordan - Sneakers Jordan pour Homme et Femme',
        'meta_description': "Toutes les Air Jordan sur KP SHOES. Jordan 1, 3, 4, 5, 11... Authentiques et livrées rapidement en France.",
        'description': f'{_S}{_H1}Air Jordan</h2>'
            f'{_P}Symbole ultime de la culture sneakers, la gamme <strong>Air Jordan</strong> dépasse largement le cadre du basketball. Née de la collaboration entre <strong>Michael Jordan</strong> et Nike en 1984, elle a donné naissance à des silhouettes devenues des objets de collection. Retrouvez tous les modèles Air Jordan sur <strong>KP SHOES</strong> : <a href="/collections/jordan-1-high">Jordan 1 High</a>, <a href="/collections/jordan-1-mid">Mid</a>, <a href="/collections/jordan-1-low">Low</a>, <a href="/collections/jordan-4">Jordan 4</a> et <a href="/collections/autres-jordan">bien d\'autres</a>.</p>'
            f'{_H2}L\'histoire de la Air Jordan</h2>'
            f'{_P}Tout commence en 1984, quand Nike signe un jeune rookie nommé Michael Jordan. La première <strong>Air Jordan 1</strong>, dessinée par Peter Moore, est bannie par la NBA pour avoir enfreint le code vestimentaire — une amende de 5 000 dollars par match que Nike s\'empresse de payer, transformant l\'interdiction en coup marketing légendaire. En 1988, Tinker Hatfield prend les rênes du design avec la <strong>Air Jordan 3</strong>, introduisant l\'imprimé éléphant et le logo Jumpman. Suivront la Jordan 4 immortalisée par « The Shot » en 1989, la Jordan 11 portée lors du retour de MJ en 1995, et des dizaines d\'autres modèles qui ont chacun marqué leur époque.</p>{_E}',
    },

    'jordan-1-high': {
        'meta_title': 'Air Jordan 1 High - Sneakers Jordan pour Homme et Femme',
        'meta_description': "Achetez votre Air Jordan 1 High sur KP SHOES. Chicago, Bred, Royal, Travis Scott... 100% authentiques.",
        'description': f'{_S}{_H1}Air Jordan 1 High</h2>'
            f'{_P}La <strong>Air Jordan 1 High</strong> est la sneaker qui a tout lancé. Avec sa tige montante en cuir, son col rembourré et son Swoosh latéral, elle reste la silhouette la plus emblématique du streetwear. Des coloris légendaires comme les <strong>Chicago</strong>, <strong>Bred</strong>, <strong>Royal</strong> et <strong>Shadow</strong> aux collaborations modernes avec <a href="/collections/travis-scott">Travis Scott</a> et <a href="/collections/off-white">Off-White</a>, chaque édition est un événement.</p>'
            f'{_H2}L\'histoire de la Air Jordan 1 High</h2>'
            f'{_P}Sortie en 1985, la Air Jordan 1 High a été conçue par Peter Moore pour accompagner Michael Jordan lors de sa première saison en NBA avec les Chicago Bulls. La NBA la bannit immédiatement pour non-respect du code couleur — une polémique qui fait exploser les ventes. Le coloris <strong>Chicago</strong> (rouge, blanc, noir) devient un symbole culturel. Après des années de rééditions, la Jordan 1 High connaît un second souffle spectaculaire avec la collaboration <strong>Travis Scott</strong> et son Swoosh inversé en 2019, puis le coloris <strong>Lost and Found</strong> en 2022 qui reproduit l\'effet d\'une paire vintage retrouvée dans un entrepôt.</p>{_E}',
    },

    'jordan-1-low': {
        'meta_title': 'Air Jordan 1 Low - Sneakers Jordan pour Homme et Femme',
        'meta_description': "Toutes les Air Jordan 1 Low sur KP SHOES. Mocha, UNC, Travis Scott Reverse... 100% authentiques.",
        'description': f'{_S}{_H1}Air Jordan 1 Low</h2>'
            f'{_P}La <strong>Air Jordan 1 Low</strong> reprend l\'ADN de la mythique <a href="/collections/jordan-1-high">Jordan 1 High</a> dans une version basse plus polyvalente et moderne. Les coloris <strong>Mocha</strong>, <strong>UNC</strong>, <strong>Bred Toe</strong> et <strong>Travis Scott Reverse</strong> en font l\'une des <a href="/collections/jordan-1">sneakers Jordan</a> les plus recherchées du marché.</p>'
            f'{_H2}L\'histoire de la Air Jordan 1 Low</h2>'
            f'{_P}Apparue peu après la version High en 1985, la Jordan 1 Low est longtemps restée dans l\'ombre de sa grande sœur. C\'est à partir de 2019 que le modèle explose, porté par la tendance des silhouettes basses et la collaboration <strong>Travis Scott x Fragment</strong> avec son Swoosh inversé et ses tons olive. La <strong>Reverse Mocha</strong> de 2022 devient l\'une des paires les plus attendues de l\'année, tandis que les éditions OG comme la UNC et la Bred Toe continuent de s\'arracher.</p>{_E}',
    },

    'jordan-1-mid': {
        'meta_title': 'Air Jordan 1 Mid - Sneakers Jordan pour Homme et Femme',
        'meta_description': "Achetez votre Air Jordan 1 Mid sur KP SHOES. Tous les coloris disponibles, 100% authentiques.",
        'description': f'{_S}{_H1}Air Jordan 1 Mid</h2>'
            f'{_P}La <strong>Air Jordan 1 Mid</strong> offre une silhouette intermédiaire entre la <a href="/collections/jordan-1-high">version High</a> et <a href="/collections/jordan-1-low">Low</a>, alliant style et accessibilité. Avec son col mi-montant et sa construction en cuir, elle conserve l\'esprit de la <a href="/collections/jordan-1">Jordan 1</a> originale tout en proposant une coupe confortable et des coloris audacieux.</p>'
            f'{_H2}L\'histoire de la Air Jordan 1 Mid</h2>'
            f'{_P}La Jordan 1 Mid apparaît dans les années 90 comme alternative plus accessible à la version High. Si les puristes lui préfèrent les OG, la Mid se démarque par la variété de ses coloris — souvent des combinaisons exclusives qu\'on ne retrouve ni sur la High ni sur la Low. Avec des prix plus abordables et un catalogue immense, elle est devenue la porte d\'entrée pour des millions de fans de sneakers à travers le monde.</p>{_E}',
    },

    'jordan-4': {
        'meta_title': 'Air Jordan 4 - Sneakers Jordan pour Homme et Femme',
        'meta_description': "Toutes les Air Jordan 4 sur KP SHOES. White Cement, Bred, Military Black, Black Cat... 100% authentiques.",
        'description': f'{_S}{_H1}Air Jordan 4</h2>'
            f'{_P}La <strong>Air Jordan 4</strong>, dessinée par Tinker Hatfield en 1989, est l\'une des silhouettes les plus iconiques de <a href="/collections/jordan-1">Jordan Brand</a>. Reconnaissable à ses ailes en mesh, ses œillets latéraux et sa languette à tirette, elle a été immortalisée par Michael Jordan lors du tir légendaire « The Shot ». Des coloris mythiques comme les <strong>White Cement</strong>, <strong>Bred</strong>, <strong>Military Black</strong> et <strong>Black Cat</strong> restent parmi les plus convoités au monde.</p>'
            f'{_H2}L\'histoire de la Air Jordan 4</h2>'
            f'{_P}Tinker Hatfield dessine la Jordan 4 en s\'inspirant de l\'aviation militaire. Les ailes en mesh sur les flancs et les œillets latéraux créent un design inédit. Le 7 mai 1989, Michael Jordan inscrit un tir au buzzer face aux Cavaliers — « The Shot » — chaussé de Jordan 4 Cement. En 2023, les collaborations avec <a href="/collections/travis-scott">Travis Scott</a> et les retours des coloris OG confirment que la Jordan 4 reste l\'une des sneakers les plus désirables, plus de 35 ans après sa création.</p>{_E}',
    },

    'autres-jordan': {
        'meta_title': 'Autres Jordan - Sneakers Jordan pour Homme et Femme',
        'meta_description': "Toutes les Air Jordan sur KP SHOES. Jordan 2, 3, 5, 6, 11, 12, 13 et plus. 100% authentiques.",
        'description': f'{_S}{_H1}Autres modèles Air Jordan</h2>'
            f'{_P}Au-delà des <a href="/collections/jordan-1-high">Jordan 1</a> et <a href="/collections/jordan-4">Jordan 4</a>, <strong>Jordan Brand</strong> compte des silhouettes devenues cultes. La <strong>Air Jordan 3</strong> et son imprimé éléphant, la <strong>Jordan 5</strong> avec sa semelle translucide, la <strong>Jordan 6</strong> du premier titre NBA, la <strong>Jordan 11</strong> et sa coque en patent leather, et la <strong>Jordan 13</strong> inspirée de la panthère noire.</p>'
            f'{_H2}L\'héritage de chaque modèle</h2>'
            f'{_P}Chaque numéro de Jordan correspond à une saison de Michael Jordan en NBA. La Jordan 3 (1988) introduit le logo Jumpman et sauve la collaboration Nike-Jordan. La Jordan 11 (1995) accompagne le retour de MJ après sa retraite, portée dans Space Jam. La Jordan 6 (1991) est celle du premier titre des Bulls. Ces modèles continuent de sortir en rééditions et collaborations sur <strong><a href="/collections/jordan-1">KP SHOES</a></strong>.</p>{_E}',
    },

    # ══════════════════════════════════════════
    # NIKE
    # ══════════════════════════════════════════

    'nike-1': {
        'meta_title': 'Nike - Sneakers & Baskets pour Homme et Femme',
        'meta_description': "Toutes les sneakers Nike sur KP SHOES. Dunk, Air Force 1, Air Max, Vomero, NOCTA... 100% authentiques.",
        'description': f'{_S}{_H1}Nike</h2>'
            f'{_P}<strong>Nike</strong>, fondée en 1971 par Bill Bowerman et Phil Knight, est la marque de sneakers la plus influente au monde. Retrouvez tous les modèles Nike sur <strong>KP SHOES</strong> : <a href="/collections/nike-dunk">Dunk</a>, <a href="/collections/air-force-1">Air Force 1</a>, <a href="/collections/air-max">Air Max</a>, <a href="/collections/nike-vomero">Vomero</a>, <a href="/collections/nike-sb">SB</a> et <a href="/collections/autres-nike">bien d\'autres</a>.</p>'
            f'{_H2}L\'histoire de Nike</h2>'
            f'{_P}Tout commence sous le nom Blue Ribbon Sports en 1964. En 1971, ils lancent Nike — du nom de la déesse grecque de la victoire — avec le Swoosh dessiné par Carolyn Davidson pour 35 dollars. La révolution arrive en 1979 avec la technologie <strong>Air</strong>, puis en 1984 avec la signature de Michael Jordan. Depuis, Nike a signé les plus grands athlètes et artistes, de LeBron James à <a href="/collections/travis-scott">Travis Scott</a>, créant une culture sneakers sans égale.</p>{_E}',
    },

    'nike-dunk': {
        'meta_title': 'Nike Dunk - Sneakers Nike pour Homme et Femme',
        'meta_description': "Achetez votre Nike Dunk sur KP SHOES. Dunk Low, High, SB... Panda, Off-White, Travis Scott. 100% authentiques.",
        'description': f'{_S}{_H1}Nike Dunk</h2>'
            f'{_P}La <strong>Nike Dunk</strong>, créée en 1985 pour le basketball universitaire, est devenue l\'une des sneakers les plus populaires de la planète. Des éditions OG aux collaborations avec <a href="/collections/off-white">Off-White</a>, <a href="/collections/travis-scott">Travis Scott</a> et <a href="/collections/supreme">Supreme</a>, la Dunk reste au cœur de la culture sneakers. Retrouvez aussi les <a href="/collections/nike-sb">Nike SB</a> pour les éditions skateboarding.</p>'
            f'{_H2}L\'histoire de la Nike Dunk</h2>'
            f'{_P}En 1985, Nike lance le programme « Be True To Your School » : des Dunk High aux couleurs des universités américaines — Syracuse, Kentucky, Michigan. La Dunk renaît en 2002 quand Nike crée la division <strong>SB</strong>, adaptant le modèle avec un amorti Zoom Air. Les collaborations avec Jeff Staple (Pigeon, 2005) et Supreme font exploser la cote. En 2020, le retour des coloris OG et la collection « The 50 » de Virgil Abloh propulsent la Dunk au sommet des tendances mondiales.</p>{_E}',
    },

    'air-force-1': {
        'meta_title': 'Nike Air Force 1 - Sneakers Nike pour Homme et Femme',
        'meta_description': "Toutes les Nike Air Force 1 sur KP SHOES. Triple White, Off-White, Travis Scott... 100% authentiques.",
        'description': f'{_S}{_H1}Nike Air Force 1</h2>'
            f'{_P}La <strong>Nike Air Force 1</strong>, sortie en 1982, est la première chaussure de basketball à intégrer la technologie Air. Du classique <strong>Triple White</strong> aux collaborations avec <a href="/collections/off-white">Off-White</a> et <a href="/collections/travis-scott">Travis Scott</a>, c\'est la sneaker la plus vendue de l\'histoire. Découvrez aussi les autres modèles <a href="/collections/nike-1">Nike</a>.</p>'
            f'{_H2}L\'histoire de la Nike Air Force 1</h2>'
            f'{_P}Bruce Kilgore conçoit la Air Force 1 en 1982, intégrant pour la première fois la capsule Air dans une chaussure de basketball. D\'abord discontinuée en 1984, elle est ressuscitée par la demande des boutiques de Baltimore, New York et Philadelphie. La communauté hip-hop de Harlem l\'adopte massivement dans les années 90, lui donnant le surnom d\'« Uptowns ». Depuis, la Air Force 1 n\'a jamais quitté le catalogue Nike, devenant la sneaker la plus vendue de tous les temps.</p>{_E}',
    },

    'air-max': {
        'meta_title': 'Nike Air Max - Sneakers Nike pour Homme et Femme',
        'meta_description': "Toutes les Nike Air Max sur KP SHOES. Air Max 1, 90, 95, 97, Plus TN, Dn... 100% authentiques.",
        'description': f'{_S}{_H1}Nike Air Max</h2>'
            f'{_P}La gamme <strong>Nike Air Max</strong> a révolutionné la sneaker en rendant visible la bulle d\'air Nike. De la <strong>Air Max 1</strong> à la <strong>Air Max 95</strong>, en passant par la <strong>97</strong>, <strong>Plus TN</strong> et <strong>Dn</strong>, chaque modèle incarne l\'innovation. Découvrez aussi nos <a href="/collections/nike-dunk">Nike Dunk</a> et <a href="/collections/air-force-1">Air Force 1</a>.</p>'
            f'{_H2}L\'histoire de la Nike Air Max</h2>'
            f'{_P}En 1987, Tinker Hatfield s\'inspire du Centre Pompidou à Paris pour créer la <strong>Air Max 1</strong>, première sneaker à rendre visible la bulle d\'air. Suivent la Air Max 90 (1990) avec ses couleurs Infrared, la Air Max 95 de Sergio Lozano inspirée de l\'anatomie humaine, et la Air Max 97 au design du Shinkansen japonais. La Air Max Plus TN, lancée en 1998, devient un phénomène culturel en France et en Australie.</p>{_E}',
    },

    'nike-vomero': {
        'meta_title': 'Nike Vomero 5 - Sneakers Nike pour Homme et Femme',
        'meta_description': "Achetez votre Nike Vomero 5 sur KP SHOES. Tous les coloris, 100% authentiques. Livraison rapide.",
        'description': f'{_S}{_H1}Nike Vomero 5</h2>'
            f'{_P}La <strong>Nike Vomero 5</strong>, conçue comme chaussure de running en 2004, est devenue une icône du style Y2K. Son design technique futuriste, ses superpositions en mesh et son amorti Zoom Air séduisent autant les runners que les amateurs de mode. Retrouvez aussi nos autres modèles <a href="/collections/nike-1">Nike</a>.</p>'
            f'{_H2}L\'histoire de la Nike Vomero 5</h2>'
            f'{_P}Lancée en 2004, la Vomero 5 passe inaperçue pendant plus de 15 ans. C\'est le retour du rétro-running et de l\'esthétique Y2K qui la propulsent vers 2022-2023. Son look technique, entre mesh respirant et superpositions argentées, correspond parfaitement à la vague gorpcore. Des coloris comme <strong>Photon Dust</strong> et <strong>Light Bone</strong> deviennent des best-sellers.</p>{_E}',
    },

    'nike-sacai': {
        'meta_title': 'Nike x Sacai - Sneakers Nike pour Homme et Femme',
        'meta_description': "Toutes les Nike x Sacai sur KP SHOES. LDWaffle, Vaporwaffle, Blazer... 100% authentiques.",
        'description': f'{_S}{_H1}Nike x Sacai</h2>'
            f'{_P}La collaboration entre <strong>Nike et Sacai</strong>, la maison japonaise fondée par Chitose Abe, a donné naissance à certaines des sneakers les plus innovantes de ces dernières années. Le concept : fusionner deux modèles en un seul, avec des doubles semelles, doubles Swoosh et doubles languettes.</p>'
            f'{_H2}L\'histoire de la collaboration Nike x Sacai</h2>'
            f'{_P}Chitose Abe collabore pour la première fois avec <a href="/collections/nike-1">Nike</a> en 2019 avec la <strong>LDWaffle</strong>, fusionnant la LDV et la Waffle Daybreak. Le résultat — deux Swoosh superposés, double semelle, double languette — est élu sneaker de l\'année 2019. Suivent la Vaporwaffle et les Blazer déstructurés, chacun poussant plus loin le concept de déconstruction.</p>{_E}',
    },

    'nike-sb': {
        'meta_title': 'Nike SB - Sneakers Nike SB Dunk pour Homme et Femme',
        'meta_description': "Toutes les Nike SB sur KP SHOES. Dunk Low SB, High SB, Travis Scott, Supreme... 100% authentiques.",
        'description': f'{_S}{_H1}Nike SB</h2>'
            f'{_P}Lancée en 2002, la ligne <strong>Nike SB</strong> (Skateboarding) est née de la volonté de <a href="/collections/nike-1">Nike</a> de conquérir la culture skate. Ses <a href="/collections/nike-dunk">Dunk</a> dotées d\'un amorti Zoom Air et d\'une languette épaisse ont séduit les skateurs et les collectionneurs avec des éditions mythiques.</p>'
            f'{_H2}L\'histoire de Nike SB</h2>'
            f'{_P}En 2002, Nike crée sa division Skateboarding après avoir observé que les skateurs détournaient les Dunk classiques. Les collaborations avec <a href="/collections/supreme">Supreme</a> (2002), Jeff Staple (Pigeon, 2005 — qui provoque des émeutes à New York) et Concepts (Lobster) créent une frénésie collector. Plus récemment, <a href="/collections/travis-scott">Travis Scott</a> a relancé l\'intérêt pour les SB.</p>{_E}',
    },

    'autres-nike': {
        'meta_title': 'Autres Nike - Sneakers Nike pour Homme et Femme',
        'meta_description': "Tous les modèles Nike sur KP SHOES. Blazer, Cortez, NOCTA, Mind, ACG... 100% authentiques.",
        'description': f'{_S}{_H1}Autres modèles Nike</h2>'
            f'{_P}Au-delà des <a href="/collections/nike-dunk">Dunk</a>, <a href="/collections/air-force-1">Air Force 1</a> et <a href="/collections/air-max">Air Max</a>, <strong>Nike</strong> propose des silhouettes incontournables : <strong>Blazer</strong>, <strong>Cortez</strong>, <strong>NOCTA</strong> de Drake, <strong>Nike Mind</strong> et <strong>ACG</strong> outdoor.</p>'
            f'{_H2}Des silhouettes variées</h2>'
            f'{_P}Le Blazer, créé en 1973 pour le basketball, est devenu un classique du streetwear. La Cortez, première chaussure de running Nike (1972), a été immortalisée dans Forrest Gump. La ligne NOCTA, créée avec Drake, mêle performance et style nocturne. Les Nike Mind 001, slides au design minimaliste, et la gamme ACG pour l\'outdoor complètent un catalogue qui couvre tous les styles.</p>{_E}',
    },

    # ══════════════════════════════════════════
    # ADIDAS
    # ══════════════════════════════════════════

    'adidas-1': {
        'meta_title': 'Adidas - Sneakers Adidas pour Homme et Femme',
        'meta_description': "Toutes les sneakers Adidas sur KP SHOES. Samba, Campus, Gazelle, Spezial, Forum, Superstar... 100% authentiques.",
        'description': f'{_S}{_H1}Adidas</h2>'
            f'{_P}<strong>Adidas</strong>, fondée en 1949 par Adi Dassler en Bavière, est un pilier de la culture sneakers mondiale. Des terrains de sport aux podiums, les trois bandes sont synonymes de style. Retrouvez sur KP SHOES : <a href="/collections/adidas-samba">Samba</a>, <a href="/collections/adidas-campus">Campus</a>, <a href="/collections/adidas-gazelle">Gazelle</a>, <a href="/collections/adidas-spezial">Spezial</a>, <a href="/collections/adidas-forum">Forum</a>, <a href="/collections/adidas-superstar">Superstar</a> et <a href="/collections/autres-adidas">bien d\'autres</a>.</p>'
            f'{_H2}L\'histoire d\'Adidas</h2>'
            f'{_P}Adolf « Adi » Dassler fabrique ses premières chaussures dans la buanderie familiale en 1920. Après la séparation avec son frère Rudolf (qui fondera <a href="/collections/puma-1">Puma</a>), il crée Adidas en 1949. Les trois bandes deviennent le logo le plus reconnaissable du sport. Dans les années 80, le hip-hop new-yorkais adopte les Superstar et les Stan Smith, tandis que les casuals anglais s\'approprient les Gazelle et Samba. Aujourd\'hui, Adidas domine les tendances avec le revival de ses classiques.</p>{_E}',
    },

    'adidas-samba': {
        'meta_title': 'Adidas Samba - Sneakers Adidas pour Homme et Femme',
        'meta_description': "Achetez votre Adidas Samba sur KP SHOES. OG, Decon, éditions limitées... Tous les coloris, 100% authentiques.",
        'description': f'{_S}{_H1}Adidas Samba</h2>'
            f'{_P}Née en 1950 pour le football en salle, l\'<strong>Adidas Samba</strong> est l\'une des sneakers les plus iconiques de tous les temps. Sa tige en cuir lisse, son T-toe en daim et sa semelle en gomme lui confèrent un look rétro intemporel. Déclinée en <strong>OG</strong>, <strong>Decon</strong> et collaborations exclusives. Découvrez aussi les <a href="/collections/adidas-gazelle">Gazelle</a> et <a href="/collections/adidas-spezial">Spezial</a>.</p>'
            f'{_H2}L\'histoire de la Adidas Samba</h2>'
            f'{_P}<a href="/collections/adidas-1">Adidas</a> crée la Samba en 1950 pour permettre aux footballeurs de s\'entraîner sur des terrains gelés. Son T-toe en daim protège des abrasions lors des frappes. Dans les années 80, les supporters de football anglais — les « casuals » — l\'adoptent comme pièce signature. Après des décennies de présence discrète, la Samba connaît un revival spectaculaire à partir de 2022, portée par les tendances « quiet luxury » et « terrace style ». Elle est aujourd\'hui l\'une des sneakers les plus vendues au monde.</p>{_E}',
    },

    'adidas-campus': {
        'meta_title': 'Adidas Campus - Sneakers Adidas pour Homme et Femme',
        'meta_description': "Toutes les Adidas Campus sur KP SHOES. Campus 00s, Core Black, Grey... 100% authentiques.",
        'description': f'{_S}{_H1}Adidas Campus</h2>'
            f'{_P}L\'<strong>Adidas Campus</strong>, apparue dans les années 70, est une icône du style décontracté. Sa tige en daim souple et ses trois bandes contrastées en font une pièce incontournable. Remise au goût du jour avec la <strong>Campus 00s</strong>. Retrouvez aussi les <a href="/collections/adidas-samba">Samba</a> et les <a href="/collections/adidas-gazelle">Gazelle</a>.</p>'
            f'{_H2}L\'histoire de la Adidas Campus</h2>'
            f'{_P}Conçue dans les années 70 pour les terrains de basket universitaires américains, la Campus est adoptée par la scène hip-hop new-yorkaise — les Beastie Boys la portent sur scène. En 2023, <a href="/collections/adidas-1">Adidas</a> lance la <strong>Campus 00s</strong>, version modernisée avec une semelle légèrement vieillie. Le succès est immédiat : les coloris Core Black et Grey s\'arrachent en quelques heures.</p>{_E}',
    },

    'adidas-gazelle': {
        'meta_title': 'Adidas Gazelle - Sneakers Adidas pour Homme et Femme',
        'meta_description': "Achetez votre Adidas Gazelle sur KP SHOES. OG, Bold, Indoor... Tous les coloris, 100% authentiques.",
        'description': f'{_S}{_H1}Adidas Gazelle</h2>'
            f'{_P}L\'<strong>Adidas Gazelle</strong>, lancée en 1966, est l\'une des sneakers les plus anciennes du catalogue <a href="/collections/adidas-1">Adidas</a>. Son upper en daim, son profil fin et ses trois bandes en zigzag incarnent l\'élégance. Déclinée en <strong>Bold</strong> (plateforme), <strong>Indoor</strong> et OG. Découvrez aussi les <a href="/collections/adidas-samba">Samba</a> et <a href="/collections/adidas-spezial">Spezial</a>.</p>'
            f'{_H2}L\'histoire de la Adidas Gazelle</h2>'
            f'{_P}Créée en 1966 pour le football, la Gazelle traverse les sous-cultures : le britpop des années 90 (Oasis, Blur), le skate, le terrace style. En 2023, la <strong>Gazelle Bold</strong> avec sa semelle plateforme conquiert le marché féminin, tandis que la <strong>Gazelle Indoor</strong> au look rétro sport cartonne chez les amateurs de vintage.</p>{_E}',
    },

    'adidas-spezial': {
        'meta_title': 'Adidas Spezial - Sneakers Adidas pour Homme et Femme',
        'meta_description': "Toutes les Adidas Spezial sur KP SHOES. Handball Spezial, terrace style... 100% authentiques.",
        'description': f'{_S}{_H1}Adidas Spezial</h2>'
            f'{_P}L\'<strong>Adidas Handball Spezial</strong>, née sur les terrains de handball dans les années 70, est un symbole de la culture terrace. Son daim premium, sa semelle en gomme translucide et son profil épuré en font l\'une des paires les plus demandées. Découvrez aussi les <a href="/collections/adidas-samba">Samba</a> et <a href="/collections/adidas-gazelle">Gazelle</a>.</p>'
            f'{_H2}L\'histoire de la Adidas Spezial</h2>'
            f'{_P}Conçue dans les années 70 pour le handball, la Spezial est adoptée par les supporters de football anglais dans les années 80 — la culture « casual ». Sa silhouette basse et son daim qualitatif deviennent les codes du style terrace. Après des décennies de culte confidentiel, la Spezial explose auprès du grand public en 2023-2024. Les coloris Light Blue, Shadow Brown et Night Indigo s\'écoulent en quelques minutes.</p>{_E}',
    },

    'adidas-forum': {
        'meta_title': 'Adidas Forum - Sneakers Adidas pour Homme et Femme',
        'meta_description': "Achetez votre Adidas Forum sur KP SHOES. Forum Low, Mid, 84... 100% authentiques.",
        'description': f'{_S}{_H1}Adidas Forum</h2>'
            f'{_P}L\'<strong>Adidas Forum</strong>, sortie en 1984, se distingue par sa sangle en X sur la cheville. Passée des parquets NBA à la rue, elle a été adoptée par la culture hip-hop. Déclinée en <strong>Low</strong>, <strong>Mid</strong> et <strong>84</strong>. Retrouvez tous les modèles <a href="/collections/adidas-1">Adidas</a>.</p>'
            f'{_H2}L\'histoire de la Adidas Forum</h2>'
            f'{_P}En 1984, Adidas lance la Forum comme sa chaussure de basketball premium — la plus chère du marché. Sa sangle distinctive assure un maintien parfait. Run-DMC et d\'autres artistes new-yorkais la portent hors des terrains, lançant la tendance sneakers dans le hip-hop. Elle revient régulièrement avec des collaborations et coloris contemporains.</p>{_E}',
    },

    'adidas-superstar': {
        'meta_title': 'Adidas Superstar - Sneakers Adidas pour Homme et Femme',
        'meta_description': "Achetez votre Adidas Superstar sur KP SHOES. OG, XLG, BAPE... 100% authentiques.",
        'description': f'{_S}{_H1}Adidas Superstar</h2>'
            f'{_P}L\'<strong>Adidas Superstar</strong>, avec sa coque en caoutchouc emblématique (shell toe) et ses trois bandes, est l\'une des silhouettes les plus reconnaissables au monde. Déclinée en <strong>OG</strong>, <strong>XLG</strong> et collaborations avec <a href="/collections/bape">BAPE</a> et Pharrell. Découvrez aussi les <a href="/collections/adidas-samba">Samba</a> et <a href="/collections/adidas-forum">Forum</a>.</p>'
            f'{_H2}L\'histoire de la Adidas Superstar</h2>'
            f'{_P}Lancée en 1969 pour le basketball, la Superstar est la première chaussure de basket entièrement en cuir. En 1986, <strong>Run-DMC</strong> sort « My Adidas » et porte les Superstar sans lacets — créant le premier partenariat sneaker-musique de l\'histoire. <a href="/collections/adidas-1">Adidas</a> signe un contrat d\'un million de dollars avec le groupe. Plus de 50 ans après, la Superstar reste l\'une des sneakers les plus vendues.</p>{_E}',
    },

    'autres-adidas': {
        'meta_title': 'Autres Adidas - Sneakers Adidas pour Homme et Femme',
        'meta_description': "Tous les modèles Adidas sur KP SHOES. SL 72, Stan Smith, Adilette... 100% authentiques.",
        'description': f'{_S}{_H1}Autres modèles Adidas</h2>'
            f'{_P}Au-delà des <a href="/collections/adidas-samba">Samba</a>, <a href="/collections/adidas-campus">Campus</a>, <a href="/collections/adidas-gazelle">Gazelle</a> et <a href="/collections/adidas-spezial">Spezial</a>, <strong>Adidas</strong> propose des silhouettes variées : <strong>SL 72</strong>, <strong>Stan Smith</strong>, <strong>Adilette</strong> et bien d\'autres.</p>'
            f'{_H2}Un catalogue riche</h2>'
            f'{_P}La Stan Smith, créée en 1963, est la sneaker blanche minimaliste par excellence — plus de 50 millions de paires vendues. La SL 72, sortie pour les JO de Munich en 1972, revient avec la tendance rétro-running. Les Adilette, créées en 1972, sont les slides les plus iconiques. Tout est disponible sur <a href="/collections/adidas-1">KP SHOES</a>.</p>{_E}',
    },

    # ══════════════════════════════════════════
    # YEEZY
    # ══════════════════════════════════════════

    'yeezy-1': {
        'meta_title': 'Yeezy - Sneakers & Slides Yeezy pour Homme et Femme',
        'meta_description': "Toutes les Yeezy sur KP SHOES. 350, 500, 700, Slide, Foam Runner... 100% authentiques.",
        'description': f'{_S}{_H1}Yeezy</h2>'
            f'{_P}Née de la collaboration entre <strong>Kanye West</strong> et Adidas en 2015, la gamme <strong>Yeezy</strong> a bouleversé l\'industrie de la sneaker. Retrouvez sur KP SHOES : <a href="/collections/yeezy-350">Yeezy 350</a>, <a href="/collections/yeezy-700">700</a>, <a href="/collections/yeezy-slide">Slide</a> et <a href="/collections/autres-yeezy">tous les autres modèles</a>.</p>'
            f'{_H2}L\'histoire de Yeezy</h2>'
            f'{_P}Après une première collaboration avec Nike (Air Yeezy 1 et 2), Kanye West signe avec Adidas en 2013. La Yeezy Boost 750 sort en février 2015, suivie de la Yeezy Boost 350 qui s\'écoule en quelques minutes et redéfinit le concept de « hype ». Le modèle 350 V2 avec sa bande SPLY-350 devient le sneaker le plus convoité au monde. Kanye pousse ensuite le design avec la 700 Wave Runner, la Foam Runner en mousse et la Yeezy Slide minimaliste.</p>{_E}',
    },

    'yeezy-slide': {
        'meta_title': 'Yeezy Slide - Slides Yeezy pour Homme et Femme',
        'meta_description': "Achetez votre Yeezy Slide sur KP SHOES. Onyx, Bone, Granite... 100% authentiques.",
        'description': f'{_S}{_H1}Yeezy Slide</h2>'
            f'{_P}La <strong>Yeezy Slide</strong>, avec son design minimaliste monobloc en mousse EVA, est l\'une des slides les plus recherchées au monde. Ultra légère et confortable, elle se décline dans des coloris neutres comme <strong>Onyx</strong>, <strong>Bone</strong>, <strong>Granite</strong> et <strong>Pure</strong>. Retrouvez aussi les <a href="/collections/yeezy-350">Yeezy 350</a> et <a href="/collections/yeezy-700">700</a>.</p>'
            f'{_H2}L\'histoire de la Yeezy Slide</h2>'
            f'{_P}Lancée en 2019, la <a href="/collections/yeezy-1">Yeezy</a> Slide pousse le minimalisme à l\'extrême : une seule pièce de mousse EVA injectée, sans couture, sans logo visible. D\'abord moquée pour sa simplicité, elle devient l\'une des pièces les plus convoitées de la gamme. Les coloris s\'écoulent en quelques secondes à chaque drop et le marché de la revente explose.</p>{_E}',
    },

    'yeezy-350': {
        'meta_title': 'Yeezy 350 V2 - Sneakers Yeezy pour Homme et Femme',
        'meta_description': "Achetez votre Yeezy 350 V2 sur KP SHOES. Zebra, Beluga, Bred... 100% authentiques.",
        'description': f'{_S}{_H1}Yeezy Boost 350 V2</h2>'
            f'{_P}La <strong>Yeezy Boost 350 V2</strong> est le modèle le plus emblématique de <a href="/collections/yeezy-1">Yeezy</a>. Sa tige en Primeknit, sa semelle Boost et sa bande SPLY-350 ont défini le style sneaker des années 2010. Les coloris <strong>Zebra</strong>, <strong>Beluga</strong>, <strong>Bred</strong> et <strong>Cream White</strong> restent parmi les plus convoités. Découvrez aussi les <a href="/collections/yeezy-700">Yeezy 700</a> et <a href="/collections/yeezy-slide">Slide</a>.</p>'
            f'{_H2}L\'histoire de la Yeezy 350</h2>'
            f'{_P}La première Yeezy 350 sort en juin 2015 en coloris « Turtle Dove » et crée une hystérie mondiale. En 2016, la V2 arrive avec la bande SPLY-350. Le Beluga (gris/orange), le Zebra (blanc/rouge) et le Bred (noir/rouge) deviennent des grails absolus. La technologie Boost d\'Adidas assure un confort exceptionnel, tandis que le Primeknit offre un maintien souple comme une chaussette.</p>{_E}',
    },

    'yeezy-700': {
        'meta_title': 'Yeezy 700 - Sneakers Yeezy pour Homme et Femme',
        'meta_description': "Toutes les Yeezy 700 sur KP SHOES. Wave Runner, V2, V3... 100% authentiques.",
        'description': f'{_S}{_H1}Yeezy 700</h2>'
            f'{_P}La <strong>Yeezy 700</strong>, surnommée « Wave Runner », a popularisé la tendance dad shoe avec son design chunky. Dotée d\'un amorti Boost et d\'une tige mêlant cuir, daim et mesh, elle existe en <strong>V1</strong>, <strong>V2</strong> et <strong>V3</strong>. Retrouvez aussi les <a href="/collections/yeezy-350">350</a> et <a href="/collections/yeezy-slide">Slide</a>.</p>'
            f'{_H2}L\'histoire de la Yeezy 700</h2>'
            f'{_P}Présentée au défilé <a href="/collections/yeezy-1">Yeezy</a> Season 5 en 2017, la 700 « Wave Runner » choque par son design chunky et multicolore. Kanye West anticipe la tendance dad shoe. Le coloris OG avec ses touches de bleu, orange et gris devient un classique instantané. La V2 (2018) simplifie le design, la V3 (2019) abandonne le Boost pour un look plus futuriste, et la MNVN propose une version en nylon épuré.</p>{_E}',
    },

    'autres-yeezy': {
        'meta_title': 'Autres Yeezy - Sneakers Yeezy pour Homme et Femme',
        'meta_description': "Tous les modèles Yeezy sur KP SHOES. 500, Foam Runner... 100% authentiques.",
        'description': f'{_S}{_H1}Autres modèles Yeezy</h2>'
            f'{_P}Au-delà des <a href="/collections/yeezy-350">350</a>, <a href="/collections/yeezy-700">700</a> et <a href="/collections/yeezy-slide">Slide</a>, la gamme <a href="/collections/yeezy-1">Yeezy</a> propose la <strong>Yeezy 500</strong>, la <strong>Foam Runner</strong> et la <strong>Yeezy Knit Runner</strong>.</p>'
            f'{_H2}Des modèles avant-gardistes</h2>'
            f'{_P}La Yeezy 500 (2017) avec son amorti adiPRENE et son design organique. La Foam Runner (2020), entièrement moulée en mousse d\'algue, avec son design qui divise autant qu\'il fascine — avant de devenir un must-have. La Knit Runner au look alien et les 450 avec leur semelle tentaculaire complètent une gamme qui ne ressemble à aucune autre.</p>{_E}',
    },

    # ══════════════════════════════════════════
    # NEW BALANCE
    # ══════════════════════════════════════════

    'new-balance-1': {
        'meta_title': 'New Balance - Sneakers pour Homme et Femme',
        'meta_description': "Toutes les New Balance sur KP SHOES. 550, 530, 2002R, 9060, 990... 100% authentiques.",
        'description': f'{_S}{_H1}New Balance</h2>'
            f'{_P}<strong>New Balance</strong>, fondée en 1906 à Boston, est réputée pour son savoir-faire artisanal et son confort inégalé. Retrouvez sur KP SHOES : <a href="/collections/new-balance-550">550</a>, <a href="/collections/new-balance-530">530</a>, <a href="/collections/new-balance-2002r">2002R</a>, <a href="/collections/new-balance-9060">9060</a>, <a href="/collections/new-balance-740">740</a> et <a href="/collections/autres-new-balance">bien d\'autres</a>.</p>'
            f'{_H2}L\'histoire de New Balance</h2>'
            f'{_P}Fondée en 1906 par William J. Riley, New Balance commence par fabriquer des semelles orthopédiques. En 1982, la 990 devient la première sneaker vendue à 100 dollars, positionnant New Balance dans le segment premium. Le choix de maintenir une fabrication Made in USA et Made in England forge la réputation qui attire aujourd\'hui des collaborateurs comme <strong>Aimé Leon Dore</strong>, <strong>Joe Freshgoods</strong> et <strong>JJJJound</strong>.</p>{_E}',
    },

    'new-balance-550': {
        'meta_title': 'New Balance 550 - Sneakers New Balance pour Homme et Femme',
        'meta_description': "Achetez votre New Balance 550 sur KP SHOES. Tous coloris, 100% authentiques.",
        'description': f'{_S}{_H1}New Balance 550</h2>'
            f'{_P}La <strong>New Balance 550</strong>, sortie en 1989 pour le basketball, a connu un retour fracassant grâce à <strong>Aimé Leon Dore</strong>. Sa tige en cuir, son logo N proéminent et son look rétro sport en font l\'une des sneakers les plus tendances. Retrouvez aussi les <a href="/collections/new-balance-530">530</a> et <a href="/collections/new-balance-2002r">2002R</a>.</p>'
            f'{_H2}L\'histoire de la New Balance 550</h2>'
            f'{_P}Lancée en 1989 sous le nom P550, cette chaussure de basketball disparaît rapidement. En 2020, Teddy Santis d\'Aimé Leon Dore la ressuscite avec une collaboration qui fait sensation. Le look rétro-basketball correspond parfaitement à l\'esthétique « quiet luxury ». Le succès est tel que <a href="/collections/new-balance-1">New Balance</a> lance des dizaines de coloris et que la 550 devient l\'une de ses meilleures ventes.</p>{_E}',
    },

    'new-balance-530': {
        'meta_title': 'New Balance 530 - Sneakers New Balance pour Homme et Femme',
        'meta_description': "Toutes les New Balance 530 sur KP SHOES. 100% authentiques, livraison rapide.",
        'description': f'{_S}{_H1}New Balance 530</h2>'
            f'{_P}La <strong>New Balance 530</strong>, issue du running des années 90, séduit par son design technique et son amorti ABZORB. Ses lignes fluides et son allure chunky incarnent la tendance rétro-running. Découvrez aussi les <a href="/collections/new-balance-550">550</a> et <a href="/collections/new-balance-9060">9060</a>.</p>'
            f'{_H2}L\'histoire de la New Balance 530</h2>'
            f'{_P}Sortie dans les années 90 comme chaussure de running, la 530 combine la technologie ABZORB avec un design fluide et technique. Revenue avec la vague rétro-running des années 2020, son profil chunky et ses matériaux mixtes en font une paire idéale pour le quotidien. Les coloris Silver et White sont devenus des classiques de <a href="/collections/new-balance-1">New Balance</a>.</p>{_E}',
    },

    'new-balance-2002r': {
        'meta_title': 'New Balance 2002R - Sneakers New Balance pour Homme et Femme',
        'meta_description': "Achetez votre New Balance 2002R sur KP SHOES. Protection Pack... 100% authentiques.",
        'description': f'{_S}{_H1}New Balance 2002R</h2>'
            f'{_P}La <strong>New Balance 2002R</strong> combine l\'héritage running avec un confort moderne grâce à sa semelle N-ERGY. Les éditions <strong>Protection Pack</strong> avec leur aspect vieilli sont parmi les plus demandées. Retrouvez aussi les <a href="/collections/new-balance-550">550</a> et <a href="/collections/new-balance-9060">9060</a>.</p>'
            f'{_H2}L\'histoire de la New Balance 2002R</h2>'
            f'{_P}La 2002 originale sort en 2010 comme chaussure de running premium. La version 2002R (R pour Refined) arrive en 2020 avec la technologie N-ERGY. C\'est le <strong>Protection Pack</strong> de 2022 — avec ses finitions volontairement usées — qui fait exploser la popularité du modèle. La 2002R s\'impose comme le modèle <a href="/collections/new-balance-1">New Balance</a> préféré des amateurs de streetwear.</p>{_E}',
    },

    'new-balance-9060': {
        'meta_title': 'New Balance 9060 - Sneakers New Balance pour Homme et Femme',
        'meta_description': "Toutes les New Balance 9060 sur KP SHOES. Joe Freshgoods... 100% authentiques.",
        'description': f'{_S}{_H1}New Balance 9060</h2>'
            f'{_P}La <strong>New Balance 9060</strong>, née de la collaboration avec <strong>Joe Freshgoods</strong>, réinterprète les silhouettes running des années 2000. Son design organique et son amorti SBS en font l\'un des modèles les plus innovants de <a href="/collections/new-balance-1">New Balance</a>.</p>'
            f'{_H2}L\'histoire de la New Balance 9060</h2>'
            f'{_P}Joe Freshgoods, designer de Chicago, imagine la 9060 en fusionnant des éléments de plusieurs modèles vintage. Le premier coloris « Inside Voices » (2022) crée un buzz immédiat avec ses tons lavande. La silhouette se distingue par ses pods SBS en semelle et son design qui semble venir du futur tout en rappelant le passé. Retrouvez aussi les <a href="/collections/new-balance-550">550</a> et <a href="/collections/new-balance-2002r">2002R</a>.</p>{_E}',
    },

    'new-balance-740': {
        'meta_title': 'New Balance 740 - Sneakers New Balance pour Homme et Femme',
        'meta_description': "Toutes les New Balance 740 sur KP SHOES. 100% authentiques.",
        'description': f'{_S}{_H1}New Balance 740</h2>'
            f'{_P}La <strong>New Balance 740</strong> est un modèle running rétro qui incarne le savoir-faire technique de <a href="/collections/new-balance-1">New Balance</a>. Sa construction robuste et son amorti performant séduisent les amateurs de silhouettes chunky et de style vintage.</p>'
            f'{_H2}L\'histoire de la New Balance 740</h2>'
            f'{_P}Issue de la gamme running, la 740 fait partie de ces modèles techniques redécouverts par le streetwear. Sa silhouette chunky et ses matériaux premium — mesh, daim et cuir — lui donnent un look Y2K très recherché. Comme les <a href="/collections/new-balance-530">530</a> et <a href="/collections/new-balance-2002r">2002R</a>, elle bénéficie de l\'engouement pour les sneakers rétro-running.</p>{_E}',
    },

    'autres-new-balance': {
        'meta_title': 'Autres New Balance - Sneakers NB pour Homme et Femme',
        'meta_description': "Tous les modèles New Balance sur KP SHOES. 990, 992, 993, 1906R... 100% authentiques.",
        'description': f'{_S}{_H1}Autres modèles New Balance</h2>'
            f'{_P}Au-delà des <a href="/collections/new-balance-550">550</a>, <a href="/collections/new-balance-530">530</a>, <a href="/collections/new-balance-2002r">2002R</a> et <a href="/collections/new-balance-9060">9060</a>, <strong>New Balance</strong> propose les <strong>990</strong>, <strong>992</strong>, <strong>993</strong> Made in USA et les <strong>1906R</strong>.</p>'
            f'{_H2}Des modèles d\'exception</h2>'
            f'{_P}La gamme 990 est le fleuron de <a href="/collections/new-balance-1">New Balance</a> — fabriquée aux USA depuis 1982, c\'est la sneaker préférée de Steve Jobs. Les 992 et 993, également Made in USA, offrent un confort inégalé. La 1906R revisite la 1906 avec des matériaux modernes et un look technique.</p>{_E}',
    },

    # ══════════════════════════════════════════
    # ASICS
    # ══════════════════════════════════════════

    'asics-1': {
        'meta_title': 'ASICS - Sneakers & Running pour Homme et Femme',
        'meta_description': "Toutes les ASICS sur KP SHOES. Gel-1130, Gel-Kayano 14, Gel-NYC... 100% authentiques.",
        'description': f'{_S}{_H1}ASICS</h2>'
            f'{_P}<strong>ASICS</strong>, fondée au Japon en 1949, signifie « Anima Sana In Corpore Sano ». Reconnue pour son amorti GEL légendaire, la marque s\'est imposée dans le streetwear. Retrouvez sur KP SHOES : <a href="/collections/asics-gel-1130">Gel-1130</a>, <a href="/collections/asics-gel-kayano">Gel-Kayano 14</a>, <a href="/collections/asics-gel-nyc">Gel-NYC</a> et <a href="/collections/autres-asics">bien d\'autres</a>.</p>'
            f'{_H2}L\'histoire d\'ASICS</h2>'
            f'{_P}En 1949, Kihachiro Onitsuka fabrique des chaussures de basketball à Kobe. Sa marque Onitsuka Tiger gagne en notoriété aux Olympiques de 1964. En 1977, la fusion donne naissance à ASICS. La technologie GEL, introduite en 1986, révolutionne l\'amorti running. Aujourd\'hui, les modèles rétro des années 2000 connaissent un revival spectaculaire dans le streetwear.</p>{_E}',
    },

    'asics-gel-1130': {
        'meta_title': 'ASICS Gel-1130 - Sneakers ASICS pour Homme et Femme',
        'meta_description': "Achetez votre ASICS Gel-1130 sur KP SHOES. White/Clay Canyon, Black/Pure Silver... 100% authentiques.",
        'description': f'{_S}{_H1}ASICS Gel-1130</h2>'
            f'{_P}La <strong>ASICS Gel-1130</strong>, héritière de la gamme running des années 2000, est devenue la sneaker tendance du moment. Son design technique, ses superpositions en mesh et cuir synthétique et son amorti GEL en font une paire idéale. Retrouvez aussi les <a href="/collections/asics-gel-kayano">Gel-Kayano 14</a> et <a href="/collections/asics-gel-nyc">Gel-NYC</a>.</p>'
            f'{_H2}L\'histoire de la ASICS Gel-1130</h2>'
            f'{_P}Sortie au début des années 2000 comme chaussure de running, la Gel-1130 passe inaperçue pendant près de 20 ans. C\'est la tendance rétro-running et l\'esthétique Y2K qui la propulsent. Son look technique — mesh respirant, superpositions argentées, amorti GEL visible — correspond parfaitement aux codes du moment. Les coloris White/Clay Canyon et Black/Pure Silver deviennent des best-sellers d\'<a href="/collections/asics-1">ASICS</a>.</p>{_E}',
    },

    'asics-gel-kayano': {
        'meta_title': 'ASICS Gel-Kayano 14 - Sneakers ASICS pour Homme et Femme',
        'meta_description': "Toutes les ASICS Gel-Kayano 14 sur KP SHOES. 100% authentiques, livraison rapide.",
        'description': f'{_S}{_H1}ASICS Gel-Kayano 14</h2>'
            f'{_P}Classique de chez <strong><a href="/collections/asics-1">ASICS</a></strong>, la <strong>Gel-Kayano 14</strong> est une sneaker iconique qui allie confort, performance et style rétro. Conçue initialement pour la course à pied, elle se distingue par son amorti GEL emblématique et sa structure robuste. Avec son design inspiré des modèles running des années 2000, elle séduit autant les amateurs de sneakers que les sportifs.</p>'
            f'{_H2}L\'histoire de la ASICS Gel-Kayano 14</h2>'
            f'{_P}Lancée en 2008, la Gel-Kayano 14 marque une évolution majeure dans la gamme Kayano, avec un design revisité qui améliore la légèreté et la flexibilité du modèle. Conçue pour offrir un maximum de stabilité aux coureurs longue distance, cette version introduit des innovations comme la semelle intermédiaire en <strong>Solyte</strong> et le système <strong>TRUSSTIC</strong> pour un meilleur contrôle du mouvement. Après avoir conquis les athlètes, elle revient aujourd\'hui sur le devant de la scène grâce aux collaborations avec <strong>JJJJound</strong> et aux coloris lifestyle comme White/Midnight et Cream/Pure Silver. Retrouvez aussi les <a href="/collections/asics-gel-1130">Gel-1130</a> et <a href="/collections/asics-gel-nyc">Gel-NYC</a>.</p>{_E}',
    },

    'asics-gel-nyc': {
        'meta_title': 'ASICS Gel-NYC - Sneakers ASICS pour Homme et Femme',
        'meta_description': "Achetez votre ASICS Gel-NYC sur KP SHOES. 100% authentiques.",
        'description': f'{_S}{_H1}ASICS Gel-NYC</h2>'
            f'{_P}La <strong>ASICS Gel-NYC</strong> fusionne deux modèles classiques — la Gel-Nimbus 3 et la MC Plus V — pour créer une silhouette hybride moderne. Sa tige en mesh et daim, son amorti GEL et son design chunky représentent la nouvelle vague <a href="/collections/asics-1">ASICS</a>.</p>'
            f'{_H2}L\'histoire de la ASICS Gel-NYC</h2>'
            f'{_P}Lancée en 2023, la Gel-NYC est le premier modèle hybride d\'ASICS. Inspirée par New York, elle incarne l\'énergie de la ville avec ses superpositions de textures et ses coloris sophistiqués. Le succès est immédiat : le coloris Cream/Steel Grey s\'écoule en quelques jours. Retrouvez aussi les <a href="/collections/asics-gel-1130">Gel-1130</a> et <a href="/collections/asics-gel-kayano">Gel-Kayano 14</a>.</p>{_E}',
    },

    'autres-asics': {
        'meta_title': 'Autres ASICS - Sneakers ASICS pour Homme et Femme',
        'meta_description': "Tous les modèles ASICS sur KP SHOES. Gel-Lyte III, Gel-Venture... 100% authentiques.",
        'description': f'{_S}{_H1}Autres modèles ASICS</h2>'
            f'{_P}Au-delà des <a href="/collections/asics-gel-1130">Gel-1130</a>, <a href="/collections/asics-gel-kayano">Gel-Kayano</a> et <a href="/collections/asics-gel-nyc">Gel-NYC</a>, <strong>ASICS</strong> propose les <strong>Gel-Lyte III</strong>, <strong>Gel-Venture</strong>, <strong>Gel-Nimbus</strong> et les collaborations avec Story mfg et Kiko Kostadinov.</p>'
            f'{_H2}Un catalogue riche</h2>'
            f'{_P}La Gel-Lyte III, créée en 1990 par Shigeyuki Mitsui, introduit la tongue split. Les Gel-Venture apportent un look trail outdoor très recherché. Les collaborations positionnent <a href="/collections/asics-1">ASICS</a> dans la mode avant-gardiste. Chaque paire bénéficie du savoir-faire japonais et de l\'amorti GEL signature.</p>{_E}',
    },

    # ══════════════════════════════════════════
    # UGG
    # ══════════════════════════════════════════

    'ugg-1': {
        'meta_title': 'UGG - Chaussons et Bottes pour Homme et Femme',
        'meta_description': "Tous les modèles UGG sur KP SHOES. Tasman, Tazz, Ultra Mini... 100% authentiques.",
        'description': f'{_S}{_H1}UGG</h2>'
            f'{_P}<strong>UGG</strong>, née en Californie en 1978, est synonyme de confort. Retrouvez sur KP SHOES : <a href="/collections/ugg-tasman">Tasman</a>, <a href="/collections/ugg-tazz">Tazz</a>, <a href="/collections/ugg-ultra-mini">Ultra Mini</a>, <a href="/collections/ugg-classic-mini">Classic Mini</a>, <a href="/collections/ugg-lowmel">Lowmel</a> et <a href="/collections/autres-ugg">bien d\'autres</a>.</p>'
            f'{_H2}L\'histoire de UGG</h2>'
            f'{_P}Brian Smith, surfeur australien en Californie, lance UGG en 1978 en important des bottes en peau de mouton. Les surfeurs les adoptent pour se réchauffer après les sessions. Dans les années 2000, les UGG deviennent un phénomène mondial. Depuis 2022, le retour de la tendance « comfort first » a propulsé les Tasman et Tazz au rang de must-have streetwear.</p>{_E}',
    },

    'ugg-tasman': {
        'meta_title': 'UGG Tasman - Chaussons UGG pour Homme et Femme',
        'meta_description': "Achetez votre UGG Tasman sur KP SHOES. Chestnut, Black, Sand... 100% authentiques.",
        'description': f'{_S}{_H1}UGG Tasman</h2>'
            f'{_P}La <strong>UGG Tasman</strong>, avec sa tige en daim doublée de laine et son bandeau tressé signature, est devenue le chausson le plus tendance. Portée en intérieur comme en extérieur. Les coloris <strong>Chestnut</strong>, <strong>Black</strong> et <strong>Sand</strong> sont les plus recherchés. Retrouvez aussi la <a href="/collections/ugg-tazz">Tazz</a> en version plateforme.</p>'
            f'{_H2}L\'histoire de la UGG Tasman</h2>'
            f'{_P}La Tasman existe depuis les années 90 comme chausson d\'intérieur de <a href="/collections/ugg-1">UGG</a>. Le tournant arrive en 2022 quand les réseaux sociaux s\'en emparent comme pièce streetwear — portée avec des jeans, des survêtements ou des robes. Les coloris Chestnut, Black et Sand s\'écoulent à chaque restock.</p>{_E}',
    },

    'ugg-tazz': {
        'meta_title': 'UGG Tazz - Chaussons UGG Plateforme pour Homme et Femme',
        'meta_description': "Achetez votre UGG Tazz sur KP SHOES. 100% authentiques.",
        'description': f'{_S}{_H1}UGG Tazz</h2>'
            f'{_P}La <strong>UGG Tazz</strong> reprend le design de la <a href="/collections/ugg-tasman">Tasman</a> avec une semelle plateforme qui lui donne une allure moderne. Doublée de laine de mouton et ornée du bandeau tressé, elle offre le confort <a href="/collections/ugg-1">UGG</a> avec un twist streetwear.</p>'
            f'{_H2}L\'histoire de la UGG Tazz</h2>'
            f'{_P}Lancée pour répondre à la demande de silhouettes plateforme, la Tazz reprend le design iconique de la Tasman en ajoutant une semelle surélevée de 3 cm. Ce simple changement transforme un chausson cosy en pièce mode. Portée par des influenceuses et des célébrités, la Tazz est devenue l\'un des modèles les plus convoités, avec des coloris Chestnut, Sand et Black qui s\'écoulent en quelques heures.</p>{_E}',
    },

    'ugg-ultra-mini': {
        'meta_title': 'UGG Ultra Mini - Bottes UGG pour Homme et Femme',
        'meta_description': "Achetez votre UGG Ultra Mini sur KP SHOES. 100% authentiques.",
        'description': f'{_S}{_H1}UGG Classic Ultra Mini</h2>'
            f'{_P}La <strong>UGG Classic Ultra Mini</strong> est la version raccourcie de la botte <a href="/collections/ugg-1">UGG</a> classique. Sa tige basse en daim, sa doublure en laine de mouton et sa semelle Treadlite légère offrent chaleur et confort dans un format compact. Découvrez aussi la <a href="/collections/ugg-classic-mini">Classic Mini</a>.</p>'
            f'{_H2}L\'histoire de la UGG Ultra Mini</h2>'
            f'{_P}Née de la volonté de moderniser la botte UGG classique, la Ultra Mini raccourcit la tige au maximum et utilise la semelle Treadlite plus légère. Le format mini séduit une clientèle plus jeune et urbaine. Les coloris Chestnut, Black et Mustard Seed sont les plus populaires.</p>{_E}',
    },

    'ugg-classic-mini': {
        'meta_title': 'UGG Classic Mini - Bottes UGG pour Homme et Femme',
        'meta_description': "Achetez votre UGG Classic Mini sur KP SHOES. 100% authentiques.",
        'description': f'{_S}{_H1}UGG Classic Mini</h2>'
            f'{_P}La <strong>UGG Classic Mini</strong>, version basse de la botte <a href="/collections/ugg-1">UGG</a> originale, est un classique intemporel. Sa tige en daim Twin-face, sa doublure en laine naturelle et sa semelle EVA légère en font la paire parfaite pour les saisons fraîches.</p>'
            f'{_H2}L\'histoire de la UGG Classic Mini</h2>'
            f'{_P}Déclinaison raccourcie de la Classic Short, la Classic Mini conserve le savoir-faire UGG dans un format plus urbain. La tige mi-haute en peau de mouton Twin-face assure chaleur et respirabilité. Elle est restée un best-seller constant depuis les années 2000. Découvrez aussi la <a href="/collections/ugg-ultra-mini">Ultra Mini</a> et la <a href="/collections/ugg-tasman">Tasman</a>.</p>{_E}',
    },

    'ugg-lowmel': {
        'meta_title': 'UGG Lowmel - Mocassins UGG pour Homme et Femme',
        'meta_description': "Achetez votre UGG Lowmel sur KP SHOES. 100% authentiques.",
        'description': f'{_S}{_H1}UGG Lowmel</h2>'
            f'{_P}La <strong>UGG Lowmel</strong> est un mocassin moderne qui mêle l\'ADN confort de <a href="/collections/ugg-1">UGG</a> à une silhouette basse et épurée. Sa tige en daim premium et sa doublure douillette apportent une touche de raffinement décontracté.</p>'
            f'{_H2}Un nouveau classique UGG</h2>'
            f'{_P}Le Lowmel représente l\'évolution de UGG vers des modèles plus lifestyle. Avec son design de mocassin bas, il s\'intègre facilement dans une garde-robe quotidienne tout en conservant le confort qui a fait la réputation de la marque. Retrouvez aussi la <a href="/collections/ugg-tasman">Tasman</a> et la <a href="/collections/ugg-tazz">Tazz</a>.</p>{_E}',
    },

    'autres-ugg': {
        'meta_title': 'Autres UGG - Chaussons et Bottes UGG pour Homme et Femme',
        'meta_description': "Tous les modèles UGG sur KP SHOES. Classic Short, Neumel... 100% authentiques.",
        'description': f'{_S}{_H1}Autres modèles UGG</h2>'
            f'{_P}Au-delà des <a href="/collections/ugg-tasman">Tasman</a>, <a href="/collections/ugg-tazz">Tazz</a> et <a href="/collections/ugg-ultra-mini">Ultra Mini</a>, <strong>UGG</strong> propose les <strong>Classic Short</strong>, <strong>Neumel</strong>, <strong>Disquette</strong> et de nombreuses collaborations.</p>'
            f'{_H2}Le confort UGG dans tous les styles</h2>'
            f'{_P}La Classic Short est la botte <a href="/collections/ugg-1">UGG</a> originale. Le Neumel est un chukka boot en peau de mouton. La Disquette est une slide plateforme au look audacieux. Chaque modèle offre la doublure en laine de mouton qui a fait la renommée de UGG depuis plus de 45 ans.</p>{_E}',
    },

    # ══════════════════════════════════════════
    # AUTRES MARQUES
    # ══════════════════════════════════════════

    'puma-1': {
        'meta_title': 'Puma - Sneakers Puma pour Homme et Femme',
        'meta_description': "Toutes les Puma sur KP SHOES. Speedcat, Suede... 100% authentiques.",
        'description': f'{_S}{_H1}Puma</h2>'
            f'{_P}<strong>Puma</strong>, fondée en 1948 par Rudolf Dassler (frère du fondateur d\'<a href="/collections/adidas-1">Adidas</a>), mêle héritage sportif et innovation. Des Suede classiques aux Speedcat inspirées du motorsport, Puma apporte une touche audacieuse au streetwear.</p>'
            f'{_H2}L\'histoire de Puma</h2>'
            f'{_P}Rudolf Dassler crée Puma après sa séparation avec son frère Adi en 1948. Pelé porte des Puma King en Coupe du monde 1970, Usain Bolt bat des records en Puma. La Suede (1968) devient un symbole du hip-hop. La Speedcat, inspirée des chaussures de pilotes F1, connaît un revival spectaculaire en 2024.</p>{_E}',
    },

    'birkenstock-1': {
        'meta_title': 'Birkenstock - Sandales et Mules pour Homme et Femme',
        'meta_description': "Toutes les Birkenstock sur KP SHOES. Boston, Arizona... 100% authentiques.",
        'description': f'{_S}{_H1}Birkenstock</h2>'
            f'{_P}<strong>Birkenstock</strong>, marque allemande fondée en 1774, est reconnue pour ses sandales au pied anatomique en liège et latex. De la <strong>Boston</strong> au <strong>Arizona</strong>, chaque modèle offre un confort inégalé et un style devenu symbole du luxe décontracté.</p>'
            f'{_H2}L\'histoire de Birkenstock</h2>'
            f'{_P}La famille Birkenstock fabrique des chaussures depuis 1774. En 1896, Konrad Birkenstock invente la première semelle de soutien de voûte. Le modèle Arizona naît en 1973, suivi du Boston. Longtemps associées à un style « granola », les Birkenstock sont propulsées dans le luxe par des collaborations avec Dior et l\'acquisition par LVMH en 2021.</p>{_E}',
    },

    'crocs': {
        'meta_title': 'Crocs - Chaussures & Sandales pour Homme et Femme',
        'meta_description': "Toutes les Crocs sur KP SHOES. Classic Clog, Echo... 100% authentiques.",
        'description': f'{_S}{_H1}Crocs</h2>'
            f'{_P}<strong>Crocs</strong>, née en 2002, a transformé un simple sabot en mousse Croslite en phénomène mondial. Personnalisables grâce aux Jibbitz et déclinées en collaborations avec <strong>Salehe Bembury</strong> et <strong>Balenciaga</strong>, les Crocs sont passées de chaussure utilitaire à icône de mode.</p>'
            f'{_H2}L\'histoire de Crocs</h2>'
            f'{_P}Créées en 2002 au Colorado comme chaussures nautiques, les Crocs sont moquées pendant des années. Le designer Salehe Bembury crée la Pollex Clog en 2020, version organique qui fait sensation. La collaboration Balenciaga avec des Crocs à plateforme de 10 cm parachève la transformation en objet de mode. Aujourd\'hui, Crocs vend plus de 100 millions de paires par an.</p>{_E}',
    },

    'converse': {
        'meta_title': 'Converse - Sneakers Converse pour Homme et Femme',
        'meta_description': "Toutes les Converse sur KP SHOES. Chuck 70, CDG... 100% authentiques.",
        'description': f'{_S}{_H1}Converse</h2>'
            f'{_P}<strong>Converse</strong>, fondée en 1908, est l\'une des marques les plus iconiques. La <strong>Chuck Taylor All Star</strong>, créée en 1917, est un symbole de la culture rock, punk et streetwear. Les collaborations avec <strong>Comme des Garçons</strong> et <strong>Rick Owens</strong> renforcent son statut culte.</p>'
            f'{_H2}L\'histoire de Converse</h2>'
            f'{_P}Marquis Mills Converse fonde la marque en 1908. En 1917, la All Star est créée pour le basketball. Chuck Taylor y appose son nom en 1932. La Chuck Taylor devient la chaussure du rock (Ramones), du punk (Kurt Cobain) et du streetwear. Rachetée par <a href="/collections/nike-1">Nike</a> en 2003, Converse continue d\'innover avec la Chuck 70 et les collaborations CDG et Off-White.</p>{_E}',
    },

    'salomon': {
        'meta_title': 'Salomon - Chaussures Trail & Running pour Homme et Femme',
        'meta_description': "Toutes les Salomon sur KP SHOES. XT-6, XT-4, ACS Pro... 100% authentiques.",
        'description': f'{_S}{_H1}Salomon</h2>'
            f'{_P}<strong>Salomon</strong>, marque française fondée en 1947 à Annecy, est spécialisée dans les chaussures outdoor et trail. Les <strong>XT-6</strong>, <strong>XT-4</strong> et <strong>ACS Pro</strong> ont conquis le streetwear par leur esthétique technique et fonctionnelle.</p>'
            f'{_H2}L\'histoire de Salomon dans le streetwear</h2>'
            f'{_P}Salomon fabrique des équipements de ski et trail depuis 1947 dans les Alpes françaises. Le tournant arrive quand des designers comme Boris Bidjan Saberi et Comme des Garçons collaborent avec la marque. La XT-6, conçue pour les ultra-trails, séduit par son look technique. La tendance « gorpcore » propulse Salomon au rang de marque de mode à part entière.</p>{_E}',
    },

    'timberland': {
        'meta_title': 'Timberland - Chaussures et Boots pour Homme et Femme',
        'meta_description': "Toutes les Timberland sur KP SHOES. 6-Inch, collaborations... 100% authentiques.",
        'description': f'{_S}{_H1}Timberland</h2>'
            f'{_P}<strong>Timberland</strong>, fondée en 1973, est célèbre pour sa <strong>6-Inch Premium Boot</strong> jaune miel devenue un symbole du hip-hop et du streetwear new-yorkais. Robuste et imperméable, la « Timb » traverse les saisons et les modes.</p>'
            f'{_H2}L\'histoire de Timberland</h2>'
            f'{_P}Sidney Swartz lance Timberland en 1973 avec une botte imperméable innovante. La 6-Inch Boot jaune est adoptée dans les années 90 par Notorious B.I.G., Nas et Jay-Z dans les rues de Brooklyn et du Queens. La « Timb » devient un symbole de résilience urbaine et un classique intemporel.</p>{_E}',
    },

    'maison-mihara': {
        'meta_title': 'Maison Mihara Yasuhiro - Sneakers pour Homme et Femme',
        'meta_description': "Achetez vos Maison Mihara Yasuhiro sur KP SHOES. Peterson, Wayne, Blakey... 100% authentiques.",
        'description': f'{_S}{_H1}Maison Mihara Yasuhiro</h2>'
            f'{_P}<strong>Maison Mihara Yasuhiro (MMY)</strong>, fondée en 1997 par le designer japonais éponyme, repousse les limites du design sneaker. Chaque paire est pensée comme une œuvre d\'art, mêlant déconstruction, matériaux inattendus et silhouettes sculpturales.</p>'
            f'{_H2}L\'histoire de Maison Mihara Yasuhiro</h2>'
            f'{_P}Mihara Yasuhiro étudie le design de chaussures à l\'université de Tama à Tokyo avant de lancer sa marque en 1997. La <strong>Peterson</strong>, avec sa semelle qui semble fondre, devient sa signature. Les modèles Wayne, Hank et Blakey explorent d\'autres déformations — semelles ondulées, structures déconstruites. Fabriquées au Japon avec un soin artisanal, les MMY séduisent les amateurs de pièces uniques.</p>{_E}',
    },

    # ══════════════════════════════════════════
    # COLLABORATIONS
    # ══════════════════════════════════════════

    'travis-scott': {
        'meta_title': 'Travis Scott - Sneakers Jordan & Nike pour Homme et Femme',
        'meta_description': "Toutes les Travis Scott sur KP SHOES. Jordan 1, Jordan 4, Dunk, Air Max... 100% authentiques.",
        'description': f'{_S}{_H1}Travis Scott x Nike</h2>'
            f'{_P}Les sneakers <strong>Travis Scott</strong> sont parmi les plus convoitées au monde. Le rappeur de Houston et fondateur de <strong>Cactus Jack</strong> collabore avec <a href="/collections/nike-1">Nike</a> et <a href="/collections/jordan-1">Jordan Brand</a> pour créer des éditions qui se vendent en quelques secondes. Son <strong>Swoosh inversé</strong> est devenu un signe distinctif reconnaissable entre tous.</p>'
            f'{_H2}L\'histoire des collaborations Travis Scott</h2>'
            f'{_P}La première collaboration majeure, la <a href="/collections/jordan-4">Air Jordan 4</a> « Cactus Jack » (2018), fait sensation. Mais c\'est la <a href="/collections/jordan-1-high">Jordan 1 High</a> avec son Swoosh inversé (2019) qui change la donne. Suivent les <a href="/collections/nike-dunk">Dunk Low</a>, les <a href="/collections/air-max">Air Max 1</a> « Baroque Brown », la Jordan 1 Low « Reverse Mocha » et la Jordan 4 « Olive ». Chaque sortie provoque une frénésie mondiale.</p>{_E}',
    },

    'off-white': {
        'meta_title': 'Off-White - Sneakers Nike & Jordan pour Homme et Femme',
        'meta_description': "Toutes les Off-White x Nike sur KP SHOES. Jordan 1, Dunk, Air Max, Presto... 100% authentiques.",
        'description': f'{_S}{_H1}Off-White x Nike</h2>'
            f'{_P}Les collaborations <strong>Off-White x <a href="/collections/nike-1">Nike</a></strong>, initiées par Virgil Abloh avec « The Ten » en 2017, ont redéfini la sneaker contemporaine. Le style déconstruit, les zip-ties, les guillemets et le texte imprimé sont devenus la signature d\'Off-White.</p>'
            f'{_H2}L\'histoire de Off-White x Nike</h2>'
            f'{_P}En 2017, Virgil Abloh présente « The Ten » : dix modèles Nike iconiques réinterprétés — coutures visibles, texte imprimé, Swoosh déplacé. La <a href="/collections/jordan-1-high">Jordan 1 Chicago</a> et la Presto deviennent des grails. La collection est divisée en « Revealed » et « Ghosted ». Après le décès de Virgil Abloh en 2021, les dernières sorties comme les <a href="/collections/nike-dunk">Dunk</a> « Dear Summer » deviennent des hommages collector.</p>{_E}',
    },

    'supreme': {
        'meta_title': 'Supreme - Sneakers & Collaborations pour Homme et Femme',
        'meta_description': "Toutes les Supreme sur KP SHOES. Dunk, Air Force 1, Jordan... 100% authentiques.",
        'description': f'{_S}{_H1}Supreme</h2>'
            f'{_P}<strong>Supreme</strong>, fondée à New York en 1994, est la marque de streetwear la plus influente de sa génération. Ses collaborations avec <a href="/collections/nike-1">Nike</a>, <a href="/collections/jordan-1">Jordan Brand</a> et Vans créent des pièces ultra limitées qui s\'arrachent instantanément.</p>'
            f'{_H2}L\'histoire de Supreme</h2>'
            f'{_P}James Jebbia ouvre le premier Supreme sur Lafayette Street à Manhattan en 1994. Le modèle du drop hebdomadaire crée une culture de la rareté. Les collaborations sneakers commencent avec les <a href="/collections/nike-sb">Dunk SB</a> en 2002, suivies des <a href="/collections/air-force-1">Air Force 1</a> et des Jordan 5. Le box logo rouge et blanc devient l\'un des symboles les plus reconnaissables de la mode urbaine.</p>{_E}',
    },

    'bape': {
        'meta_title': 'BAPE - Sneakers Bape Sta pour Homme et Femme',
        'meta_description': "Toutes les BAPE sur KP SHOES. BAPE Sta, collaborations Adidas... 100% authentiques.",
        'description': f'{_S}{_H1}BAPE</h2>'
            f'{_P}<strong>A Bathing Ape (BAPE)</strong>, fondée à Tokyo en 1993 par Nigo, est pionnière du streetwear japonais. Son camouflage distinctif et les <strong>BAPE Sta</strong> sont très recherchées. Les collaborations avec <a href="/collections/adidas-1">Adidas</a> (<a href="/collections/adidas-superstar">Superstar</a>, Campus) perpétuent l\'héritage.</p>'
            f'{_H2}L\'histoire de BAPE</h2>'
            f'{_P}Nigo lance BAPE en 1993 à Harajuku, Tokyo, avec une philosophie de rareté absolue. Le camouflage BAPE et la BAPE Sta — sneaker avec une étoile filante — deviennent des icônes. Pharrell Williams et Kanye West popularisent la marque aux États-Unis dans les années 2000.</p>{_E}',
    },

    'dior': {
        'meta_title': 'Dior - Sneakers Dior x Jordan pour Homme et Femme',
        'meta_description': "Sneakers Dior sur KP SHOES. B23, Jordan x Dior... 100% authentiques.",
        'description': f'{_S}{_H1}Dior</h2>'
            f'{_P}Les sneakers <strong>Dior</strong> incarnent la fusion entre haute couture et culture sneakers. La collaboration <strong>Dior x <a href="/collections/jordan-1-high">Air Jordan 1</a></strong> reste l\'une des sneakers les plus exclusives jamais produites. La <strong>B23</strong> avec son monogramme Oblique est devenue un symbole du luxe streetwear.</p>'
            f'{_H2}L\'histoire des sneakers Dior</h2>'
            f'{_P}Kim Jones orchestre la collaboration Dior x Air Jordan 1 en 2020 : 13 000 paires pour 5 millions de demandes. La Jordan 1 en cuir italien avec le monogramme Oblique sur le Swoosh devient instantanément l\'une des sneakers les plus chères. La B23, high-top en toile Oblique, s\'impose comme le modèle phare de la maison.</p>{_E}',
    },

    'patta': {
        'meta_title': 'Patta - Sneakers Nike & New Balance pour Homme et Femme',
        'meta_description': "Toutes les Patta sur KP SHOES. Air Max 1, Dunk... 100% authentiques.",
        'description': f'{_S}{_H1}Patta</h2>'
            f'{_P}<strong>Patta</strong>, fondée à Amsterdam en 2004, est l\'un des magasins de sneakers les plus respectés d\'Europe. Ses collaborations avec <a href="/collections/nike-1">Nike</a>, <a href="/collections/new-balance-1">New Balance</a> et <a href="/collections/asics-1">ASICS</a> se distinguent par des coloris audacieux et un sens du détail remarquable.</p>'
            f'{_H2}L\'histoire de Patta</h2>'
            f'{_P}Edson Sabajo et Guillaume Schmidt ouvrent Patta en 2004 dans un sous-sol d\'Amsterdam. Leur première collaboration Nike — une <a href="/collections/air-max">Air Max 1</a> « Lucky Green » — établit leur réputation. Les Air Max 1 Patta avec leurs vagues latérales deviennent emblématiques, déclinées en Monarch, Aqua et Chlorophyll.</p>{_E}',
    },

    'autre-marques': {
        'meta_title': 'Autres Marques - Sneakers pour Homme et Femme',
        'meta_description': "Découvrez d\'autres marques de sneakers sur KP SHOES. 100% authentiques.",
        'description': f'{_S}{_H1}Autres marques</h2>'
            f'{_P}Réunissant des labels au style unique, cette sélection met en avant des sneakers qui se distinguent par leur originalité et leur design innovant. Des marques émergentes aux labels établis, découvrez des paires qui sortent des sentiers battus sur <strong>KP SHOES</strong>.</p>{_E}',
    },

    # ══════════════════════════════════════════
    # COLLECTIONS GLOBALES
    # ══════════════════════════════════════════

    'sneakers': {
        'meta_title': 'Sneakers - Baskets Tendances pour Homme et Femme',
        'meta_description': "Toutes les sneakers sur KP SHOES. Nike, Jordan, Adidas, New Balance, ASICS, Yeezy... 100% authentiques.",
        'description': f'{_S}{_H1}Sneakers</h2>'
            f'{_P}Retrouvez toutes les sneakers disponibles sur <strong>KP SHOES</strong>. Des classiques intemporels aux éditions limitées les plus convoitées : <a href="/collections/nike-1">Nike</a>, <a href="/collections/jordan-1">Jordan</a>, <a href="/collections/adidas-1">Adidas</a>, <a href="/collections/new-balance-1">New Balance</a>, <a href="/collections/asics-1">ASICS</a>, <a href="/collections/yeezy-1">Yeezy</a>, <a href="/collections/ugg-1">UGG</a> et bien d\'autres. Chaque paire est vérifiée et 100% authentique.</p>'
            f'{_H2}L\'univers sneakers sur KP SHOES</h2>'
            f'{_P}La sneaker est bien plus qu\'une chaussure — c\'est un objet culturel. De la Air Jordan 1 qui a lancé la révolution en 1985 aux Adidas Samba qui dominent les tendances actuelles, en passant par les Yeezy qui ont redéfini la hype, le monde de la sneaker ne cesse de se réinventer. Sur KP SHOES, nous sélectionnons les modèles les plus recherchés et garantissons leur authenticité.</p>{_E}',
    },

    'streetwear': {
        'meta_title': 'Streetwear - T-Shirts, Hoodies pour Homme et Femme',
        'meta_description': "Vêtements streetwear sur KP SHOES. Essentials, Stüssy, Supreme, hoodies, t-shirts... 100% authentiques.",
        'description': f'{_S}{_H1}Streetwear</h2>'
            f'{_P}Complétez votre look avec notre sélection de vêtements streetwear premium. <strong>Fear of God Essentials</strong>, <strong>Denim Tears</strong>, <strong>Stüssy</strong>, <a href="/collections/supreme">Supreme</a>, <a href="/collections/bape">BAPE</a> et bien d\'autres — hoodies, t-shirts, joggers et vestes des marques les plus convoitées. Tous 100% authentiques et vérifiés sur <strong>KP SHOES</strong>.</p>'
            f'{_H2}Le streetwear sur KP SHOES</h2>'
            f'{_P}Le streetwear est né dans les rues de New York et Tokyo dans les années 80-90. De Supreme à BAPE, de Stüssy à Fear of God, ces marques ont transformé des vêtements du quotidien en pièces de collection. Sur KP SHOES, nous proposons les drops les plus recherchés, tous vérifiés et authentiques.</p>{_E}',
    },

    # ══════════════════════════════════════════
    # COLLECTIONS UTILITAIRES
    # ══════════════════════════════════════════

    'meilleures-ventes': {
        'meta_title': 'Meilleures Ventes - Sneakers Populaires pour Homme et Femme',
        'meta_description': "Les sneakers les plus populaires sur KP SHOES. Nos best-sellers du moment, 100% authentiques.",
        'description': f'{_S}{_H1}Nos meilleures ventes</h2>'
            f'{_P}Découvrez les sneakers les plus populaires du moment sur <strong>KP SHOES</strong>. Cette sélection regroupe les paires les plus demandées — des classiques intemporels aux dernières sorties. Toutes 100% authentiques et vérifiées par nos experts.</p>{_E}',
    },

    'moins-de-150': {
        'meta_title': 'Sneakers à Moins de 150€ pour Homme et Femme',
        'meta_description': "Des sneakers tendance à moins de 150€ sur KP SHOES. 100% authentiques.",
        'description': f'{_S}{_H1}Sneakers à moins de 150€</h2>'
            f'{_P}Des sneakers authentiques et tendance sans se ruiner. <a href="/collections/nike-dunk">Nike Dunk</a>, <a href="/collections/adidas-samba">Adidas Samba</a>, <a href="/collections/new-balance-1">New Balance</a>, <a href="/collections/asics-1">ASICS</a>... Les modèles les plus populaires à prix accessibles, tous vérifiés et authentiques sur <strong>KP SHOES</strong>.</p>{_E}',
    },

    'livraison-48h': {
        'meta_title': 'Livraison 48h - Sneakers Express pour Homme et Femme',
        'meta_description': "Recevez vos sneakers en 48h avec KP SHOES. Sélection en stock, 100% authentiques.",
        'description': f'{_S}{_H1}Livraison en 48h</h2>'
            f'{_P}Besoin de vos sneakers rapidement ? Cette sélection regroupe les paires en stock et expédiées sous 48h. <strong>KP SHOES</strong> vous garantit une livraison rapide sans compromis sur l\'authenticité.</p>{_E}',
    },

    'nouveautes': {
        'meta_title': 'Nouveautés - Sneakers & Streetwear pour Homme et Femme',
        'meta_description': "Les dernières nouveautés sneakers sur KP SHOES. Sorties récentes, éditions limitées. 100% authentiques.",
        'description': f'{_S}{_H1}Nouveautés</h2>'
            f'{_P}Les dernières sorties et nouveautés sneakers sur <strong>KP SHOES</strong>. Éditions limitées, collaborations exclusives et coloris fraîchement sortis — soyez parmi les premiers à porter les paires du moment.</p>{_E}',
    },

    'sport': {
        'meta_title': 'Sneakers Sport - Performance et Running pour Homme et Femme',
        'meta_description': "Sneakers sport sur KP SHOES. Performance, confort et style réunis. 100% authentiques.",
        'description': f'{_S}{_H1}Sneakers sport</h2>'
            f'{_P}Performance, confort et style réunis. Cette sélection regroupe des sneakers adaptées à l\'entraînement et au sport, avec les technologies les plus avancées de <a href="/collections/nike-1">Nike</a>, <a href="/collections/adidas-1">Adidas</a>, <a href="/collections/asics-1">ASICS</a> et <a href="/collections/new-balance-1">New Balance</a>.</p>{_E}',
    },

    'pour-enfants': {
        'meta_title': 'Sneakers Enfant - Baskets Nike, Jordan, Adidas',
        'meta_description': "Sneakers pour enfants sur KP SHOES. Jordan, Nike, Adidas, UGG... 100% authentiques.",
        'description': f'{_S}{_H1}Sneakers pour enfants</h2>'
            f'{_P}Les plus belles sneakers existent aussi en tailles enfant. <a href="/collections/jordan-1">Air Jordan</a>, <a href="/collections/nike-dunk">Nike Dunk</a>, <a href="/collections/adidas-campus">Adidas Campus</a>, <a href="/collections/ugg-tazz">UGG Tazz</a>... En versions PS (Preschool), GS (Grade School) et TD (Toddler). Toutes 100% authentiques sur <strong>KP SHOES</strong>.</p>{_E}',
    },

    'stock-x-sneakers': {
        'meta_title': 'StockX Sneakers - Alternative Française Authentifiée',
        'meta_description': "Vous cherchez des sneakers StockX ? Découvrez KP SHOES, alternative française avec authentification et livraison rapide.",
        'description': f'{_S}{_H1}Alternative à StockX en France</h2>'
            f'{_P}Vous cherchez des sneakers authentiques comme sur StockX ? <strong>KP SHOES</strong> est votre alternative française. Nous proposons plus de 2 800 modèles authentifiés par nos experts, avec une livraison rapide en France. <a href="/collections/nike-1">Nike</a>, <a href="/collections/jordan-1">Jordan</a>, <a href="/collections/adidas-1">Adidas</a>, <a href="/collections/yeezy-1">Yeezy</a>, <a href="/collections/new-balance-1">New Balance</a> — tous vérifiés et garantis 100% authentiques.</p>{_E}',
    },

}
