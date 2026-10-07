"""Analyse locale des comptes et calcul d'une note indicative."""

from __future__ import annotations

# TYPE_CHECKING décrit le type Identifiant sans créer d'import circulaire.
from typing import TYPE_CHECKING
import hmac
import secrets
import time

# Le générateur contient aussi la règle pédagogique Faible/Moyen/Fort.
from vaultsafe.generateur import evaluer_force_mot_de_passe

if TYPE_CHECKING:
    from vaultsafe.identifiants import Identifiant


def analyser_mots_de_passe(comptes: list[Identifiant], annule=None) -> tuple[set[str], set[str]]:
    """Retourne les numéros des comptes faibles et réutilisés."""
    # Jetons HMAC éphémères : pas de secret en clé d'un cache de résultats.
    cle = secrets.token_bytes(32)
    comptes = [(c, hmac.digest(cle, c.mot_de_passe.encode('utf-8'), 'sha256')) for c in comptes if c.mot_de_passe]
    occurrences = {}
    for compte, jeton in comptes:
        occurrences[jeton] = occurrences.get(jeton, 0) + 1
    # Un ensemble (set) garde uniquement les identifiants des comptes faibles.
    # On compare le résultat de la règle de force au texte « Faible ».
    evaluations = {}
    faibles = set()
    echeance = time.monotonic() + .006
    for compte, jeton in comptes:
        if annule and annule():
            raise ValueError('Analyse annulée.')
        if jeton not in evaluations:
            evaluations[jeton] = evaluer_force_mot_de_passe(compte.mot_de_passe)
        if evaluations[jeton] == 'Faible':
            faibles.add(compte.id)
        if time.monotonic() >= echeance:
            # Relâche l'exécution Python entre petits lots pour les événements Qt.
            time.sleep(.003)
            echeance = time.monotonic() + .006
    # Si un mot apparaît plus d'une fois, chacun des comptes concernés est
    # marqué, pas seulement la deuxième occurrence.
    reutilises = {
        compte.id for compte, jeton in comptes
        if occurrences[jeton] > 1
    }
    return faibles, reutilises


def calculer_score(
    total: int, faibles: int, reutilises: int, exposes: int | None = None
) -> int | None:
    """Donne une note indicative sur 100, ou rien si le coffre est vide.

    Les mots faibles retirent jusqu'à 40 points, les réutilisés jusqu'à 30.
    Après contrôle des fuites, les mots exposés retirent jusqu'à 30 points.
    """
    if total == 0:
        # Il serait trompeur de montrer 100 % quand aucun mot n'a été évalué.
        return None
    # Chaque ratio représente la part des comptes concernés dans le coffre.
    # Ce score est une indication simple, pas une garantie de sécurité.
    penalite = 40 * faibles / total + 30 * reutilises / total
    if exposes is not None:
        # None signifie « pas encore vérifié », ce qui diffère de zéro fuite.
        penalite += 30 * exposes / total
    return max(0, round(100 - penalite))
