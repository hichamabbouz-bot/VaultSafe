"""Génération configurable et phrases aléatoires avec le dictionnaire EFF."""
from __future__ import annotations

import math
import secrets
import string
import sys
from functools import lru_cache
from pathlib import Path


def generer_configurable(longueur=24, minuscules=True, majuscules=True, chiffres=True,
                        symboles=True, ambigus=False):
    if type(longueur) is not int or not 12 <= longueur <= 128:
        raise ValueError('Choisissez une longueur entre 12 et 128 caractères.')
    categories = [alphabet for utilise, alphabet in (
        (minuscules, string.ascii_lowercase), (majuscules, string.ascii_uppercase),
        (chiffres, string.digits), (symboles, '!@#$%^&*()-_=+[]{}:,.?')) if utilise]
    if not ambigus:
        categories = [''.join(c for c in alphabet if c not in 'Il1O0o') for alphabet in categories]
    if not categories:
        raise ValueError('Sélectionnez au moins une catégorie de caractères.')
    alphabet = ''.join(categories)
    # Rejet uniforme, afin de ne pas surreprésenter les mots avec plusieurs catégories.
    while True:
        valeur = ''.join(secrets.choice(alphabet) for _ in range(longueur))
        if all(any(c in categorie for c in valeur) for categorie in categories):
            return valeur


@lru_cache(maxsize=1)
def mots_eff():
    racine = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    chemin = racine / 'assets' / 'eff_large_wordlist.txt'
    try:
        mots = tuple(ligne.split()[1] for ligne in chemin.read_text(encoding='utf-8').splitlines() if ligne.strip())
    except (OSError, IndexError) as erreur:
        raise ValueError('Le dictionnaire EFF est absent ou endommagé.') from erreur
    if len(mots) != 7776 or len(set(mots)) != 7776:
        raise ValueError('Le dictionnaire EFF est invalide.')
    return mots


def generer_phrase(nombre=6, separateur='-'):
    if type(nombre) is not int or not 6 <= nombre <= 12 or separateur not in ('-', ' ', '.', '_'):
        raise ValueError('Choisissez 6 à 12 mots et un séparateur pris en charge.')
    mots = mots_eff()
    return separateur.join(secrets.choice(mots) for _ in range(nombre))


def entropie_phrase(nombre=6):
    if type(nombre) is not int or not 6 <= nombre <= 12:
        raise ValueError('Nombre de mots invalide.')
    return round(nombre * math.log2(len(mots_eff())), 1)
