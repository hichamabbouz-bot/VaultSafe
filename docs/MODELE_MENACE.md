# Modèle de menace de VaultSafe local

6 octobre 2026 — 3.3.2-alpha.1. Évaluation de conception et contrôles de développement ; aucun audit indépendant.

## Actifs et adversaires

Mots de passe, notes, champs, TOTP, pièces, noms, sites, dates et préférences sont sensibles. Un adversaire peut copier une base/sauvegarde, altérer des octets ou paramètres publics, proposer un fichier hostile ou provoquer une erreur disque. Une autre instance légitime peut écrire en parallèle. Un site hostile peut présenter plusieurs formulaires, une action externe ou changer de page pendant une confirmation.

## Mesures implémentées

| Menace | Réponse |
| --- | --- |
| Copie du fichier au repos | Document et pièces AES-256-GCM ; en-tête public et tailles visibles |
| Essais hors ligne du mot de passe | Argon2id 64 MiB/3/4, sel aléatoire, limites avant dérivation |
| Altération du contenu/en-tête/blocs | AAD, tags GCM, manifeste chiffré, ordre et SHA-256 vérifiés |
| Récupération contournant le mot de passe | Clé aléatoire explicite, enveloppe distincte, renouvellement après utilisation |
| Fichier hostile | Formats/coûts/tailles validés, schémas stricts, métadonnées SQLite contrôlées |
| Lecture verrouillée | Absence de clé et contrôles au niveau service et dépôt |
| Autorisation d’appareil copiée | DPAPI du compte Windows, empreinte de machine, chemin canonique du coffre et contexte de son enveloppe ; durée de 30 jours |
| Ancienne autorisation après changement d’accès | Enveloppe maître incluse dans le contexte ; changement maître/récupération invalident l’autorisation ; révocation locale explicite |
| Écriture d’une session ancienne | Empreinte de ligne, verrouillage de l’instance périmée |
| Import/écriture interrompus | Transactions de lot ou remplacement atomique, copies vérifiées |
| Sauvegarde altérée | Vérification complète sur copie avant remplacement ; source conservée |
| Suppression accidentelle | Corbeille, historique limité et confirmations de purge ; sauvegarde recommandée |
| Divulgation par tableur | Neutralisation de formules CSV avec marqueur pour le retour des caractères d’origine |
| Secret du coffre encore visible après verrouillage | Popups Windows fermés, projections et copies oubliées, demandes IPC invalidées par génération ; la capture de champs du site peut proposer une réouverture explicite sans lire les secrets du coffre |
| Historique/cloud du presse-papiers Windows | Formats d’exclusion DWORD zéro avant texte ; pas de garantie envers les logiciels tiers |
| Divulgation par icônes | Réseau désactivé par défaut, activation explicite ; origine publique seule, sans chemin/paramètres/identifiant/secret ; IP et équipements locaux exclus |
| Image ou redirection hostile | HTTPS vérifié, DNS public épinglé et revalidé à chaque redirection, taille et délais bornés, raster réencodé en PNG sans contenu actif |
| Résultat arrivé après verrouillage/modification | Génération de session et révision du coffre vérifiées avant livraison ; tâches bornées et analyses annulables |
| Extension non associée/rejeu IPC | Origines autorisées exactes, clé de session DPAPI/AES-GCM, expiration et anti-rejeu |
| Mauvais site de remplissage | Origine exacte, confirmation Windows, relecture de l’onglet, cadre principal/formulaire visible/action de même origine |
| Popup fermé pendant confirmation | Service worker conserve le canal ; retours temporaires liés à l’origine, sans identifiant ni mot de passe ; secrets de saisie/génération uniquement en mémoire |
| Regroupement confondu avec autorisation | Marques et groupes servent à la présentation ; comptes comparés par origine exacte et identifiant, mises à jour explicites uniquement |
| Capture de formulaire hostile | Script isolé du cadre principal, geste utilisateur, contrôles HTTPS/origine/action/ambiguïté ; champs masqués/2FA exclus, iframe d’origine extension dans une racine DOM fermée ; nonce de proposition et visibilité contrôlés avant lecture/enregistrement |
| Capture après verrouillage ou délai | Propositions liées à l’extension et au coffre, huit maximum, expiration de deux minutes ; verrouillage manuel invalide les anciennes propositions, lecture de secret et écriture exigent une session valide |
| Écrasement après connexion refusée | Aucun remplacement automatique d’un compte existant ; erreurs visibles signalées et vérification proposée ; comparaison locale des doublons sans transmettre l’ancien secret |
| Écriture automatique non consentie | Proposition par défaut ; activation explicite du mode automatique, réservée aux nouveaux comptes identifiés ; préférence chiffrée et revérifiée avant écriture |
| Application Android confondue avec site web | Certificat et paquet définissent l’identité source ; domaine inféré réservé à la présentation, affiliation manuelle explicite ; aucun remplissage web pour une URI Android |
| SVG actif ou externe | Sous-ensemble graphique limité en taille, nœuds, profondeur et dimensions ; scripts et ressources externes refusés avant rasterisation |

## Limites

- Un logiciel hostile sous le compte Windows, un keylogger, débogueur ou accès mémoire peut compromettre un coffre ouvert et la liaison DPAPI. La liaison locale n’isole pas les programmes d’un même utilisateur.
- L’appareil de confiance autorise les logiciels du même compte Windows à utiliser l’autorisation locale ; il n’exige pas de présence physique et n’utilise pas Windows Hello. Une session Windows accessible donne donc accès à ce coffre. La durée dépend de l’heure locale ; elle ne constitue pas une révocation distante. Une autorisation sauvegardée auparavant peut être réutilisée tant que son contexte et sa durée restent valides. Le mot de passe public de développement ne concerne que le profil explicitement isolé, jamais les coffres personnels.
- Python, les bibliothèques, la pagination, les captures et les crash dumps peuvent conserver des traces mémoire. L’effacement parfait n’est pas garanti.
- Les sites publics contactés pour les icônes voient la requête et l’adresse IP de connexion. Les caches non chiffrés peuvent révéler les services consultés et restent après verrouillage ; désactiver le réseau ne les supprime pas. Les images manuelles sont locales et ne sont pas contenues dans les sauvegardes du coffre.
- Une soumission observée ne démontre ni connexion ni création réussie. Le mode par défaut exige un clic dans le panneau d’origine extension ; le mode automatique explicitement activé peut enregistrer un nouveau compte après une tentative dont le résultat reste incertain. Des refus tardifs ou invisibles peuvent échapper au détecteur ; aucun ancien mot de passe valide n’est remplacé silencieusement. Aucun mot de passe dans storage, notifications ou journaux ; secrets en RAM deux minutes maximum, huit propositions. Le login d’une étape précédente et les métadonnées publiques de proposition peuvent rester deux minutes dans storage.session. Un redémarrage du worker peut perdre une capture indisponible, sans écriture ni faux succès.
- Les scripts du site ne lisent pas les champs du panneau d’origine extension. Ils peuvent néanmoins masquer ou supprimer son conteneur : la visibilité est contrôlée, sans empêcher un site hostile de perturber l’affichage ou de fabriquer sa propre imitation. Une politique CSP restrictive ou un formulaire non reconnu peut empêcher le panneau ; saisie manuelle disponible. Un secret déjà présent dans les champs du site ne peut pas être rappelé.
- Sur un appareil de confiance valide, le délai par défaut est Jamais ; l’utilisateur peut choisir un délai distinct. Une session laissée ouverte reste accessible à une personne utilisant ce compte Windows. Révocation, expiration, verrouillage manuel et événements Windows restent applicables.
- Le chiffrement ne masque pas la taille, présence, dates du fichier ou UUID/nombre de blocs des pièces. La suppression logique ne garantit pas l’effacement des anciennes pages, journaux, sauvegardes ou SSD.
- Un remplacement complet par une ancienne copie authentique peut provoquer un retour en arrière ; pas de service anti-rollback entre redémarrages. Des sauvegardes indépendantes sont nécessaires contre perte et ransomware.
- Une clé de secours exportée en texte déverrouille son coffre : la garder séparément. Les anciennes sauvegardes conservent leur ancien mot de passe/clé. Renouveler l’accès courant ne révoque pas ces fichiers.
- Les anciennes bases et les exports CSV/JSON/pièces restent en clair. La migration ne les efface pas. JSON/CSV ne sont pas des sauvegardes complètes.
- Le TOTP dans le même coffre est un confort ; il ne constitue pas une séparation physique du second facteur. L’heure Windows doit être correcte.
- Les exclusions du presse-papiers ne couvrent pas les gestionnaires tiers. Un contrôle de fuites déjà engagé peut attendre la fin des quatre requêtes en cours, bornées à cinq secondes, après annulation ; aucune nouvelle requête n’est engagée. Les résultats anciens ne reviennent pas à l’écran.
- La saisie Windows globale `Ctrl+Alt+V` a été retirée. Le remplissage utilise exclusivement la liaison dédiée, avec vérification d’origine et confirmation.
- Un site correspondant exactement à l’origine mais compromis peut lire ses champs après remplissage. VaultSafe ne protège pas un utilisateur qui autorise un site frauduleux ; iframes/formulaires ambigus sont refusés, sans soumission automatique.
- L’extension fonctionne en chargement développeur. Le setup local est désormais explicitement demandé : installation par utilisateur, programmes séparés des coffres, aucune modification de profil ou politique de navigateur, désinstallation conservant les données. La signature de l’EXE, la matrice Windows propre, la publication et la revue indépendante ne sont pas acquises. Windows Hello est exclu. Une désinstallation ne révoque pas à elle seule l'association native : déconnecter l'extension dans l'application avant désinstallation si souhaité.

Les tests utilisent exclusivement des données fictives, des dossiers temporaires et un navigateur isolé. Ils valident des comportements précis, sans démontrer une sécurité absolue ni une aptitude commerciale définitive.

Recette de capture 3.3.0 : extension réellement chargée dans Edge isolé, service worker et liaison native réels vers l’application Qt et un coffre fictif. 17 contrôles réussis : proposition isolée et clic unique, doublon, inscription, SPA vidant les champs, deux étapes, redirection, automatique, mise à jour avec historique, refus, verrouillage et réouverture explicite par confiance, persistance après réouverture, Entrée, 2FA, action externe, désactivation, exclusion et absence de mots de passe dans storage. 17 contrôles locaux couvrent métadonnées, origines distinctes, concurrence, édition de l’identifiant sans conflit, expiration et chiffrement. Aucun compte personnel ni connexion réelle à Milanote n’est utilisé.

Complément 3.3.1 : le panneau garde la vérification de visibilité avant lecture des champs et écriture. Placement hors des transformations du corps du site, compensation du zoom CSS et insertion dans le dialogue modal actif pour éviter son état inerte. Le cadre d’origine extension reste privé. Un résultat public final peut être lu sans la garde des secrets. La proposition attend la réponse native avant son premier affichage ; les erreurs de connexion sont liées à une soumission précise et attendent sa création native. L’automatique n’affiche pas de formulaire pendant l’attente. Le popup de l’icône conserve uniquement remplissage et générateur, sans parcours manuel de capture.
