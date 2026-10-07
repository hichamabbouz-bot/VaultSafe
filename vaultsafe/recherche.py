"""Recherche et tri des comptes déjà lus dans la base, sans nouvelle lecture."""

from __future__ import annotations

# TYPE_CHECKING sert seulement à expliquer le type d'un compte à l'éditeur.
# Ce fichier n'a donc pas besoin de charger identifiants.py à l'exécution.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vaultsafe.identifiants import Identifiant


def filtrer_et_trier(
    comptes: list[Identifiant], recherche: str = "", tri: str = "recent"
) -> list[Identifiant]:
    """Retourne une copie filtrée et triée, sans nouvelle requête SQLite."""
    # list crée une copie : trier ici ne change pas l'ordre reçu par l'appelant.
    liste = list(comptes)
    # casefold ignore les différences de majuscules, y compris en français.
    texte = recherche.strip().casefold()
    if texte:
        # On parcourt chaque compte et on garde ceux dont au moins un champ
        # contient les mots saisis. Tout reste en mémoire : pas de requête SQL.
        liste = [
            compte for compte in liste
            if texte in " ".join((
                compte.titre, compte.nom_utilisateur, compte.site, compte.notes, " ".join(compte.tags)
            )).casefold()
        ]
    if tri == "favoris":
        liste.sort(key=lambda compte: (not compte.favori, compte.titre.casefold()))
    elif tri == "nom":
        # lambda reçoit un compte et fournit sa clé de classement à sort.
        # Ici, on classe sur le titre sans tenir compte des majuscules.
        liste.sort(key=lambda compte: compte.titre.casefold())
    elif tri == "creation":
        # reverse=True met les dates les plus récentes en premier.
        liste.sort(key=lambda compte: compte.date_creation, reverse=True)
    else:
        # Par défaut, le dernier compte modifié apparaît en tête.
        liste.sort(key=lambda compte: compte.date_modification, reverse=True)
    return liste
