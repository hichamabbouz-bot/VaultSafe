"""Génération et évaluation simple des mots de passe."""

# secrets fournit des tirages adaptés aux mots de passe (contrairement à random).
# string regroupe les lettres et les chiffres sans les recopier à la main.

from vaultsafe.config import DEFAULT_PASSWORD_LENGTH


def generer_mot_de_passe(longueur: int = DEFAULT_PASSWORD_LENGTH) -> str:
    """Crée un mot aléatoire de 12 à 32 caractères avec quatre types."""
    if not 12 <= longueur <= 32:
        raise ValueError("La longueur doit être comprise entre 12 et 32.")
    from vaultsafe.generateur_avance import generer_configurable
    return generer_configurable(longueur)


def evaluer_force_mot_de_passe(mot_de_passe: str) -> str:
    """Estimation zxcvbn locale et conservative, bornée aux 72 premiers caractères."""
    if not mot_de_passe:
        return "Faible"
    from zxcvbn import zxcvbn
    score = zxcvbn(mot_de_passe[:72])["score"]
    return "Fort" if score >= 3 else "Moyen" if score == 2 else "Faible"
