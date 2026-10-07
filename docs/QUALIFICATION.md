# Qualification et distribution — 6 octobre 2026, 3.3.2-alpha.1

**Livraison courante : 3.3.3-alpha.1 / extension 3.3.3.** Ajout ciblé de l'icône
À propos au-dessus du cadenas (signature et LinkedIn) et amélioration du changement
de mot de passe : libellés, ancien/nouveau/confirmation, compte sans identifiant
affiché et choix explicite si plusieurs comptes de la même origine.
31 tests locaux réussis, popup vérifié et 16 contrôles Edge réussis, dont un
formulaire de changement sans attribut autocomplete et conservation de l'historique.
Les rapports générés ont été supprimés lors du nettoyage du 7 octobre 2026.
Les recettes conservées dans `tests/` et `tools/` permettent de les reproduire.
Les mesures détaillées ci-dessous concernent la qualification précédente 3.3.2.

Application existante et extension 3.3.2, avec un installateur local Inno Setup.
Aucune publication GitHub ou Store, aucun coffre personnel utilisé pendant les tests.

## Référence

Application 3.3.1-alpha.1, extension 3.3.1. Copie restaurable des 136 fichiers
de code, ressources et documentation, sans coffre ni exécutable :
`reference-3.3.1-source.zip`, SHA-256
`636c4c58a55b2e1a72f822cc6449f06dabe47c50cb8a410b68ff36eae27a7e88`.
Elle reste hors du dossier de distribution.

Les recettes deviennent durables. Les tests créent uniquement des coffres fictifs
dans des dossiers temporaires ; Qt utilise offscreen et le navigateur un profil
jetable. Aucun test ne doit ouvrir les données LocalAppData/VaultSafe personnelles.

## Référence fonctionnelle

- Connexion, création de coffre, récupération, changement de mot de passe,
  appareil de confiance révocable, verrouillage manuel et automatique.
- Fiches de connexion, notes, cartes, identités, licences, Wi-Fi et serveurs ;
  dossiers, tags, favoris, recherche, tri, historique, corbeille, pièces jointes.
- Générateur, analyses locales et vérification de fuite volontaire.
- Imports CSV/JSON avec aperçu et doublons, export authentifié, sauvegarde
  chiffrée/restauration, sauvegardes automatiques avec rétention.
- Thèmes, échelle, préférences, presse-papiers temporaire, zone de notification,
  démarrage Windows, déplacement et placement des fenêtres.
- Extension : détection en arrière-plan, proposition en un clic, mode automatique
  explicite, mises à jour, exclusions, remplissage et générateur.

## Architecture retenue et appliquée

Conserver le paquet `vaultsafe` et les points de compatibilité. Ses petits modules
existants portent déjà le domaine (`modele`, `services`, `recherche`), les opérations
(`identifiants`, `parametres`, `operations_fichiers`) et l'infrastructure
(`stockage_chiffre`, `enveloppe`, `liaison_navigateur`, Windows).
Sous-modules Qt isolés : `modeles_fiches.py` pour modèle et filtre,
`connexion.py` et `coffre.py` pour construction des widgets. `app.py` conserve
l'orchestration des sessions et des opérations ; le dessin des écrans est préservé.
Ne pas déplacer tous les modules dans des couches artificielles.

Le stockage expose `revision_courante`, lecture publique **sans verrou bloquant**
pour les contrôles de fraîcheur. Les lectures authentifiées restent verrouillées.
`projections.py` prépare recherche et reconnaissance des services hors interface,
puis le modèle Qt applique la table préparée. Les travailleurs restent bornés
et les générations de session rejettent les résultats périmés. Aucun format de
coffre, algorithme cryptographique ou droit de remplissage n'est modifié.

Les dépendances sont séparées et fixées : runtime, construction, développement.
CustomTkinter, tkinter, Pillow et pystray ne sont pas dans la livraison.
Les outils de tests et le compilateur ne sont pas installés chez le client.

Arborescence de maintenance : `vaultsafe/`, `extension/`, `assets/`, `tests/unit/`,
`tests/integration/`, `tests/qt/`, `tests/browser/`, `tools/`, `packaging/`, `docs/`.
Une seule chaîne `Construire.ps1` fabrique l'application et, sur demande, le setup.

## Commandes reproductibles

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q
.\.venv\Scripts\ruff.exe check --no-cache vaultsafe tests tools main.py
.\.venv\Scripts\python.exe -B tools\mesurer.py --sortie rapports\avant.json
.\.venv\Scripts\python.exe -B tests\qt\recette_application.py --sortie rapports\qt.json --cycles 60
.\.venv\Scripts\python.exe -B tools\recette_lancements.py --sortie rapports\lancements.json
.\.venv\Scripts\python.exe -B tools\recette_setup.py --setup release\VaultSafe-Setup-3.3.2-alpha.1-x64.exe --sortie rapports\setup.json
.\Construire.ps1 -Setup -CompilateurInno 'C:\chemin\ISCC.exe'
```

Créer `rapports/` avant les recettes qui demandent une sortie. Pour Edge :
`node tests/browser/recette.cjs rapports/browser.json` ; voir
[les prérequis navigateur](../tests/browser/README.md). Cette recette crée puis
supprime uniquement son propre hôte `org.vaultsafe.recette` et son profil jetable.
La recette du setup refuse de remplacer une installation personnelle existante.

Les rapports ne contiennent que des timings, tailles et compteurs techniques.
Ils distinguent mémoire privée, mémoire résidente et poids de distribution.
Le démarrage à froid, plusieurs écrans physiques, les zooms système 100–200 % et
une machine Windows vierge devront être vérifiés séparément des tests offscreen.

## Résultats locaux

Windows 11 build 26300, 12 processeurs logiques, Python 3.13.14, Qt 6.11.2.
Mesures source offscreen, réseau désactivé et caches disponibles ; médianes de
trois passages, sauf import en lot. Référence 3.3.1 puis code 3.3.2 sur ce poste.

| Nombre de fiches fictives | Modèle sur le thread GUI avant | Application de la table préparée après | Recherche avant / après | Projection avant / après |
| --- | --- | --- | --- | --- |
| 100 | 2,87 ms | 0,02 ms | 0,25 / 0,27 ms | 2,09 / 2,13 ms |
| 1 000 | 32,70 ms | 0,20 ms | 1,32 / 1,37 ms | 12,34 / 12,96 ms |
| 10 000 | 729,67 ms | 11,30 ms | 17,86 / 14,59 ms | 126,87 / 127,00 ms |

Le travail de préparation est **déplacé**, pas supprimé : à 10 000 fiches,
préparation + application du modèle prend 855,58 ms au total dans la recette
directe après changement. Le travailleur traite cette préparation sans créer de
widgets ni charger les secrets. La mutation et la sauvegarde à cette taille
restent au-delà de 250 ms (362,15 et 300,14 ms) et passent hors interface.
Leurs différences avec la référence (492,58 et 387,35 ms) ne prouvent pas une
amélioration du chiffrement, qui n'a pas changé.

- **29 tests pytest réussis**, contrôles Ruff réussis. Deux avertissements Qt
  de dépréciation de `invalidateFilter` dans les tests du filtre.
- **30 processus du nouvel EXE** démarrés sans incident : temps externe médian
  377,30 ms, maximum 426,56 ms. Coffre fictif verrouillé, Qt offscreen et caches
  Windows disponibles ; ce n'est pas un démarrage froid après redémarrage.
- **60 cycles Qt** connexion/coffre/pages/verrouillage, deux thèmes et zooms
  internes 100/200 %. Première page Sécurité 39,39 ms, Paramètres 105,71 ms.
  Après nettoyage Qt : 43 widgets et zéro tâche en attente à chaque échantillon.
  Mémoire privée 47,98 → 62,41 Mio, résidente 79,89 → 94,02 Mio ; handles
  258 → 261 et threads entre 7 et 10. Cette croissance doit encore être observée
  en endurance longue ; les compteurs stables ne démontrent pas l'absence de fuite.
- Repos source offscreen sur 10 s : CPU rapporté à la machine 0,117 % verrouillé
  et 0,091 % ouvert masqué (1,401 % et 1,089 % d'un cœur). Une boucle de recette
  pompe les événements ; ces valeurs ne certifient pas le repos réel dans le tray.
- **15 contrôles dans Edge isolé** avec native messaging vers le même EXE :
  connexion/redirection/zoom, doublon, SPA vidant les champs, inscription,
  dialogue modal, deux étapes, automatique, refus, mise à jour et historique,
  coffre verrouillé, storage sans mot de passe, copie en mémoire, insertion du
  générateur, remplissage d'origine exacte et persistance chiffrée après réouverture.
- **6 contrôles du setup** : installation par utilisateur dans un chemin
  temporaire, réinstallation au même chemin, manifeste visant l'EXE installé,
  ouverture par confiance DPAPI et écriture native, réouverture de deux comptes
  et préférences, désinstallation conservant le coffre fictif. Le SHA du coffre
  est identique avant/après installation et mise à jour. Pas de VM Windows vierge.

## Installation et extension

Installation par utilisateur dans `%LOCALAPPDATA%\Programs\VaultSafe`, sans
Python ou élévation administrateur requis. Coffres, préférences et autorisations
restent séparés des programmes. Raccourci Bureau facultatif, désinstallation via
Windows. Aucune installation silencieuse de l'extension dans un profil existant.

L'utilisateur active le mode développeur de Chrome/Edge, charge le dossier
`extension` installé puis clique **Associer** dans Paramètres → Avancé. Le guide
de l'application ouvre ou copie le chemin. Identifiant stable inchangé :
`egbpodcdijmeibnmfabhiignfppmclbl`. Après mise à niveau : recharger l'extension,
accepter les permissions demandées et actualiser les pages ouvertes. Si l'on passe
du portable au programme installé, refaire l'association et sélectionner le
nouveau dossier d'extension. Une désinstallation conserve l'association native
et les données utilisateur ; **Déconnecter** la retire explicitement.

## Contenu et limites de livraison

Un seul EXE application dans `dist/VaultSafe`, avec `_internal`, extension,
notices et guide. Informations de version Windows et icône Signature intégrées.
Les dix tailles Windows 16–256 px proviennent du dessin vectoriel ; aucune purge
globale du cache d'icônes. DLL Qt remplaçables, licences Python et métadonnées des
bibliothèques conservées. `BUILDINFO.json` donne les empreintes de la distribution.

Application : 3 344 722 octets, SHA-256
`dba41ab7bb7f5c18347ef14169953f2af0cf2375fd4daa426b80d7e12ea343ce`.
Le SHA-256 du setup final figure dans `release/SHA256SUMS.txt`.
Setup : `VaultSafe-Setup-3.3.2-alpha.1-x64.exe`, SHA-256
`73fb6e4e7a4c098294c72583a077263fb969c0973f3034e2cb6fbf712d0b06c6`.
Le poids disque (environ 105 Mio déployés) ne mesure pas la RAM ni le CPU.
Les anciennes archives locales ont été supprimées lors du nettoyage du 7 octobre 2026.

Nettoyage effectué : dossier `build/` retiré, archive intermédiaire 3.3.2 retirée,
aucun cache Python de recette dans les sources.
Un EXE application dans `dist`, un setup dans `release`, aucun EXE de test,
coffre fictif ou profil navigateur de recette restant dans la livraison.
Les sources et tests utiles restent dans le projet ; aucun module fonctionnel
n'a été supprimé pendant ce chantier.

Les résultats ci-dessus résument les rapports techniques historiques, retirés
lors du nettoyage. Le setup qualifié inclut la notice exacte MIT-0 de cffi ;
sa recette installation/mise à jour/désinstallation a été rejouée après cette
correction, sans reconstruire l'EXE déjà qualifié.

À qualifier sur un poste Windows vierge : assistant visible et boutons de fin,
installation réelle de Chrome/Edge, plusieurs moniteurs et zoom Windows,
redémarrage à froid, veille et fermeture de session réelles, endurance de deux
heures et signature Authenticode. Les recettes locales n'utilisent pas les
réglages Windows ni le navigateur personnel. Aucun audit indépendant ou scan
Codex Security formel n'a été exécuté pour cette livraison.

## Distribution et publication

Priorité confirmée par le propriétaire : l'installateur et sa qualification.
La publication GitHub a été autorisée le 7 octobre 2026. Usage non commercial demandé ; licence
PolyForm Noncommercial 1.0.0 pour le code original. Les bibliothèques tierces
conservent leurs licences, notamment les droits LGPL de remplacement de Qt.
Un dépôt avec restriction commerciale sera présenté comme source disponible.

La livraison reste alpha et non signée tant que qualification externe et
signature Authenticode ne sont pas acquises. Ne pas annoncer une certification.
