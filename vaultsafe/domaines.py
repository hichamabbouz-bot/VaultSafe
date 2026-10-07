"""Domaines enregistrés : suffixes publics et privés, sans accès réseau."""
import sys
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def suffixes():
    racine = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    regles, jokers, exceptions = set(), set(), set()
    try:
        contenu = (racine / 'assets' / 'public_suffix_list.dat').read_text(encoding='utf-8')
        for ligne in contenu.splitlines():
            ligne = ligne.strip()
            if not ligne or ligne.startswith('//'):
                continue
            collection = exceptions if ligne.startswith('!') else jokers if ligne.startswith('*.') else regles
            regle = ligne[1:] if ligne.startswith('!') else ligne[2:] if ligne.startswith('*.') else ligne
            collection.add(regle.encode('idna').decode('ascii').lower())
        if not regles:
            raise ValueError
    except (OSError, UnicodeError, ValueError):
        return None
    return regles, jokers, exceptions


@lru_cache(maxsize=4096)
def domaine_site(hote):
    listes = suffixes()
    if listes is None:
        return hote.removeprefix('www.')  # Repli prudent si la ressource manque.
    regles, jokers, exceptions = listes
    parties = hote.split('.')
    taille = 1
    for i in range(len(parties)):
        fin = '.'.join(parties[i:])
        if fin in exceptions:
            taille = len(parties) - i - 1
            break
        if fin in regles:
            taille = max(taille, len(parties) - i)
        if i > 0 and fin in jokers:
            taille = max(taille, len(parties) - i + 1)
    return '.'.join(parties[-(taille + 1):])
