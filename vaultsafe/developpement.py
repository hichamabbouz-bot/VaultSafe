"""Profil de développement explicite, distinct des coffres personnels."""
import os
from vaultsafe.config import obtenir_dossier_donnees

# Ce mot de passe connu ne sert qu'au profil isolé --developpement.
MOT_DE_PASSE_INITIAL = 'hichamabbouz'


def choisir_profil():
    dossier = obtenir_dossier_donnees().parent / 'VaultSafeDeveloppement'
    os.environ['VAULTSAFE_DATA_DIR'] = str(dossier)
    return dossier / 'vaultsafe-dev.db'


def initialiser(base, connexion, appareil):
    if base.chemin.name != 'vaultsafe-dev.db':
        raise ValueError('Le développement exige son profil isolé.')
    from vaultsafe.coffres import memoriser_coffre
    memoriser_coffre(base.chemin)
    if not base.est_initialise():
        connexion.creer_mot_de_passe_maitre(MOT_DE_PASSE_INITIAL)
    elif appareil.etat() is not None:
        return
    else:
        try:
            connexion.se_connecter(MOT_DE_PASSE_INITIAL)
        except ValueError:
            return  # Un mot de passe personnalisé garde son fonctionnement normal.
    try:
        appareil.autoriser()
    finally:
        base.verrouiller()
