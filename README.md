<p align="center"><img src="assets/signature/symbol-blue.svg" width="64" alt="Logo VaultSafe"></p>

# VaultSafe

**Vos identifiants, dans un coffre local sur Windows.**

VaultSafe est une application gratuite pour usage non commercial, avec un coffre
chiffré local et une extension Chrome / Edge. Organisez vos comptes, générez des
mots de passe et enregistrez les identifiants détectés dans le navigateur en un clic.
Aucun compte distant ni abonnement n'est nécessaire.

**Préversion : 3.3.3-alpha.1 · Windows x64 · Python / PySide6**

[Voir la démonstration vidéo — 45 secondes](docs/media/VaultSafe-45s-review.mp4)

## Fonctionnalités

- Identifiants, notes sécurisées, cartes, identités, licences, Wi-Fi et serveurs.
- Recherche, dossiers, tags, favoris, regroupement par service et corbeille.
- Générateur de mots de passe et phrases de passe, TOTP et analyse locale.
- Imports CSV / JSON, exports explicites et sauvegardes chiffrées avec restauration.
- Historique des mots de passe et pièces jointes chiffrées.
- Thèmes clair / sombre, zone de notification et verrouillage configurable.
- Appareil de confiance : ouverture avec une autorisation liée au compte Windows.
- Extension : détection, proposition d'enregistrement, remplissage et générateur.
  Le mode d'enregistrement automatique est facultatif.

## Installer

Télécharger l'installateur Windows depuis la
[préversion 3.3.3-alpha.1](https://github.com/hichamabbouz-bot/VaultSafe/releases/tag/v3.3.3-alpha.1) :
`VaultSafe-Setup-3.3.3-alpha.1-x64.exe`.

1. Lancer l'installateur. Python n'est pas nécessaire sur le poste utilisateur.
2. Ouvrir VaultSafe et créer un mot de passe maître de 12 caractères minimum.
3. Créer une clé de secours dans **Paramètres → Protection** et la conserver
   séparément. Préparer également une sauvegarde chiffrée.

L'installation s'effectue pour le compte Windows courant, sans administrateur,
dans `%LOCALAPPDATA%\Programs\VaultSafe`. Le coffre par défaut se trouve dans
`%LOCALAPPDATA%\VaultSafe\vaultsafe.db`, séparément du programme.

**Mise à jour :** fermer l'application et lancer le nouvel installateur.
La désinstallation conserve les coffres et sauvegardes par défaut.
Sans mot de passe maître ni clé de secours créée auparavant, le coffre reste inaccessible.

## Extension Chrome / Edge

L'installateur fournit l'extension dans
`%LOCALAPPDATA%\Programs\VaultSafe\extension`. Le ZIP de la Release contient
la même version, pour une installation séparée.

1. Ouvrir `chrome://extensions` ou `edge://extensions` et activer le mode développeur.
2. Choisir **Charger l'extension non empaquetée**, puis le dossier installé
   ou extrait du ZIP. Le fichier `manifest.json` doit se trouver à sa racine.
3. Copier l'identifiant affiché. Dans VaultSafe déverrouillé, ouvrir
   **Paramètres → Avancé → Extension**, renseigner cet identifiant et choisir **Associer**.
4. Autoriser l'accès aux sites souhaités et actualiser les pages déjà ouvertes.

L'application doit être lancée et le coffre accessible pour enregistrer un compte.
Par défaut, la détection se fait en arrière-plan et un petit panneau propose
**Enregistrer** ou **Ignorer**. Une mise à jour conserve les autres informations
de la fiche et l'ancien mot de passe dans l'historique.

Le popup contient **Remplissage** et **Générateur**. Le remplissage nécessite
une confirmation dans l'application ; le formulaire n'est pas soumis à votre place.
Après une mise à jour : recharger l'extension, réautoriser les permissions si demandé,
puis actualiser les pages ouvertes.

## Données et confidentialité

Le coffre reste sur votre ordinateur. La confiance accordée à un appareil utilise
DPAPI ; sa révocation et le verrouillage manuel restent respectés.
Les exports CSV / JSON sont en clair. Pour transférer ou restaurer le coffre complet,
utiliser une sauvegarde chiffrée.

La récupération des icônes en ligne est facultative. Elle contacte les sites publics
concernés sans identifiant, mot de passe ni URL personnelle complète.
Les vérifications de fuites en ligne sont également volontaires.
Les groupes visuels n'élargissent jamais les origines autorisées pour le remplissage.
Voir le [modèle de menace](docs/MODELE_MENACE.md).

## Limites de la préversion

- Installateur non signé : Windows peut afficher un avertissement de réputation.
- Détection testée sur des formulaires fictifs ; tous les sites ne sont pas garantis.
  Les formulaires ambigus, iframes et parcours entre origines restent limités.
- Extension en mode développeur ; aucune publication Chrome Web Store.
- Icônes génériques lorsque les sites bloquent ou ne fournissent pas d'image utilisable.
- Tests locaux Windows 11 ; Windows vierge, moniteurs réels et endurance prolongée
  encore à qualifier. Aucun audit indépendant ni certification de sécurité annoncé.

Les résultats et leurs limites figurent dans la [qualification](docs/QUALIFICATION.md).
Pour signaler un problème, utiliser les Issues du dépôt avec des données fictives.
Ne joindre aucun coffre, mot de passe, clé de secours ou export personnel.

## Vérifier un téléchargement

La Release fournit `SHA256SUMS.txt`. Après téléchargement, comparer l'empreinte :

```powershell
Get-FileHash .\VaultSafe-Setup-3.3.3-alpha.1-x64.exe -Algorithm SHA256
```

L'empreinte vérifie l'intégrité et la correspondance avec le fichier publié ;
elle ne constitue pas une signature de l'éditeur.

## Développer

Python 3.13 et Windows sont nécessaires. Depuis le dossier des sources :

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -B main.py
.\.venv\Scripts\python.exe -B -m pytest -q
.\.venv\Scripts\ruff.exe check --no-cache vaultsafe tests tools main.py
```

`Lancer.ps1 -Developpement` utilise un profil distinct des coffres personnels.
Ne jamais utiliser ce profil pour de vrais secrets.
Pour construire : `Construire.ps1`. Pour l'installateur, utiliser Inno Setup 6.7.3
avec `Construire.ps1 -Setup -CompilateurInno chemin\ISCC.exe`.
Voir l'[architecture](docs/ARCHITECTURE.md) et les
[commandes de qualification](docs/QUALIFICATION.md).

Les dossiers `.venv/`, `dist/`, `release/`, archives, caches et données de coffres
sont exclus du dépôt. Les fichiers compilés sont destinés aux Releases.

## Licence et crédits

Code original sous [PolyForm Noncommercial 1.0.0](LICENSE) : gratuit pour les
usages autorisés non commerciaux, avec code accessible. Le projet est présenté
comme **source disponible avec restriction commerciale**.
Les composants tiers conservent leurs propres licences :
[notices et attributions](THIRD_PARTY_NOTICES.md).

Développé par :

- [Hicham Abbouz](https://www.linkedin.com/in/hichamabbouz/)
- [Sanae Omari Alaoui](https://www.linkedin.com/in/sanaa-omari-alaoui-/)

Les retours, signalements et suggestions sont bienvenus.
