"""Identité de présentation commune ; aucune autorisation de remplissage ici."""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from urllib.parse import urlsplit

from vaultsafe.domaines import domaine_site, suffixes

# Catalogue d'affiliations existantes : données, sans branche par marque.
# Les services absents suivent les mêmes règles générales de domaines/apps.
MARQUES = {
    'ankama.com': 'Ankama', 'cihbank.ma': 'CIH Bank', 'live.com': 'Microsoft', 'microsoft.com': 'Microsoft',
    'microsoftonline.com': 'Microsoft', 'office.com': 'Microsoft',
    'outlook.com': 'Microsoft', 'google.com': 'Google', 'gmail.com': 'Google',
    'github.com': 'GitHub', 'adobe.com': 'Adobe', 'apple.com': 'Apple',
    'icloud.com': 'Apple', 'amazon.com': 'Amazon', 'amazon.fr': 'Amazon',
    'facebook.com': 'Facebook', 'instagram.com': 'Instagram',
    'linkedin.com': 'LinkedIn', 'paypal.com': 'PayPal', 'steamcommunity.com': 'Steam',
    'steampowered.com': 'Steam', 'discord.com': 'Discord', 'spotify.com': 'Spotify',
}

LOCAUX = ('.local', '.lan', '.internal', '.home', '.localhost', '.test', '.invalid', '.example')
PAQUET = re.compile(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+')
HOTE = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?')


@dataclass(frozen=True)
class Service:
    cle: str = ''
    nom: str = 'Sans site'
    hote: str = ''
    genre: str = 'inconnu'
    confiance: str = 'indetermine'
    origines: tuple[str, ...] = ()
    logo: str = ''
    symbole: str = 'globe'
    application: str = ''
    candidat: str = ''


def _hote(valeur):
    hote = valeur.rstrip('.').encode('idna').decode('ascii').lower()
    if len(hote) > 253 or not all(HOTE.fullmatch(p) for p in hote.split('.')):
        raise ValueError('Hôte invalide.')
    return hote


def est_public(hote):
    try:
        return ipaddress.ip_address(hote).is_global
    except ValueError:
        return '.' in hote and not hote.endswith(LOCAUX) and hote != 'localhost'


@lru_cache(maxsize=4096)
def _web(hote, scheme, port):
    try:
        ip = ipaddress.ip_address(hote)
        hote = str(ip)
        cible = '[' + hote + ']' if ip.version == 6 else hote
        cle = f'{scheme}://{cible}:{port}'
        nom = 'Appareil réseau local' if not ip.is_global else 'Serveur'
        return Service(cle, nom + ' · ' + cible + ':' + str(port), hote, 'reseau', 'adresse', symbole='serveur')
    except ValueError:
        pass
    if hote == 'localhost' or hote.endswith(LOCAUX[:5]):
        cle = f'{scheme}://{hote}:{port}'
        return Service(cle, 'Appareil réseau local · ' + hote + ':' + str(port), hote, 'reseau', 'adresse', symbole='serveur')
    domaine = domaine_site(hote)
    nom = MARQUES.get(domaine, domaine)
    famille = tuple(d for d, n in MARQUES.items() if n == nom) or (domaine,)
    etiquette = re.sub(r'[^a-z0-9]', '', nom.casefold())
    domaines = sorted(famille, key=lambda d: (d.split('.')[0] != etiquette, len(d), d))
    origines = tuple('https://' + d for d in domaines if est_public(d))
    # Une page de connexion peut proposer l'icône lorsque la racine la refuse.
    # La clé commune reste stable ; cette source ne change aucune autorisation.
    if est_public(hote) and 'https://' + hote not in origines:
        origines += ('https://' + hote,)
    cle = 'marque:' + nom.casefold() if domaine in MARQUES else 'domaine:' + domaine
    return Service(cle, nom, hote, 'web', 'catalogue' if domaine in MARQUES else 'domaine',
                   origines, cle)


def _candidat_application(paquet):
    parties = paquet.lower().split('.')
    listes = suffixes()
    if listes is None:
        return ''
    regles, jokers, exceptions = listes
    # Le nom de paquet propose seulement une piste, jamais une affiliation.
    for n in range(2, min(4, len(parties)) + 1):
        candidat = '.'.join(reversed(parties[:n]))
        if candidat in regles or domaine_site(candidat) != candidat:
            continue
        if any(candidat.endswith('.' + j) for j in jokers) and candidat not in exceptions:
            continue
        try:
            if est_public(candidat) and parties[0] in regles:
                return _hote(candidat)
        except (ValueError, UnicodeError):
            pass
    return ''


def normaliser(adresse):
    if not isinstance(adresse, str):
        return Service()
    texte = adresse.strip()
    if not texte or len(texte) > 8192 or any(c.isspace() or ord(c) < 32 for c in texte) or '\\' in texte:
        return Service()
    if texte.lower().startswith('android://'):
        m = re.fullmatch(r'android://([A-Za-z0-9_=-]{8,128})@([^/?#:@]+)/?', texte, re.IGNORECASE)
        if not m or not PAQUET.fullmatch(m[2]) or len(m[2]) > 200:
            return Service()
        try:
            certificat = base64.b64decode(m[1] + '=' * (-len(m[1]) % 4), altchars=b'-_', validate=True)
            if len(certificat) not in (20, 32, 64):
                return Service()
        except ValueError:
            return Service()
        paquet = m[2]  # Les noms Android sont sensibles à la casse.
        cle = 'android:' + hashlib.sha256(paquet.encode() + b'\0' + certificat).hexdigest()
        candidat = _candidat_application(paquet)
        piste = _web(candidat, 'https', 443) if candidat else Service()
        nom = piste.nom if candidat else paquet
        return Service(cle, nom + ' · Android', paquet, 'android', 'probable',
                       piste.origines, piste.logo or cle, 'personne', paquet, candidat)
    try:
        url = urlsplit(texte if '://' in texte else 'https://' + texte)
        if url.scheme.lower() not in ('http', 'https') or url.username is not None or url.password is not None or not url.hostname:
            return Service()
        port = url.port
        if port is not None and not 1 <= port <= 65535:
            return Service()
        try:
            hote = str(ipaddress.ip_address(url.hostname))
        except ValueError:
            hote = _hote(url.hostname)
        if '.' not in hote and ':' not in hote and hote != 'localhost':
            return Service()
        resultat = _web(hote, url.scheme.lower(), port or (443 if url.scheme.lower() == 'https' else 80))
        # Un port inhabituel garde sa propre identité ; pas de collecte distante.
        if resultat.genre == 'web' and port not in (None, 80, 443):
            return replace(resultat, cle=f'origine:{url.scheme.lower()}://{hote}:{port}',
                           logo=f'origine:{url.scheme.lower()}://{hote}:{port}', origines=(), confiance='adresse')
        return resultat
    except (ValueError, UnicodeError):
        return Service()


class MoteurServices:
    """Affiliations explicites apprises du coffre, sans modifier ses données."""
    def __init__(self):
        self.aliases, self.icones, self.noms, self.noms_manuels = {}, {}, {}, {}
        self.appris = False

    def resoudre(self, adresse):
        source = normaliser(adresse)
        resultat = self.aliases.get(source.cle, source)
        return self.avec_nom(resultat)

    def avec_nom(self, resultat):
        if resultat.cle in self.noms_manuels:
            resultat = replace(resultat, nom=self.noms_manuels[resultat.cle])
        elif resultat.cle in self.noms:
            resultat = replace(resultat, nom=self.noms[resultat.cle])
        elif resultat.genre == 'android' and resultat.logo in self.noms:
            resultat = replace(resultat, nom=self.noms[resultat.logo] + ' · Android')
        return resultat

    def apprendre(self, fiches):
        self.appris = True
        associations = {}
        for f in fiches:
            choix = f.get('presentation', {})
            correction = choix.get('service', '').strip()
            if not correction:
                continue
            source, cible = normaliser(f.get('site', '')), normaliser(correction)
            if source.cle and source.genre != 'reseau' and cible.genre == 'web' and cible.origines:
                associations.setdefault(source.cle, {})[cible.cle] = cible
        # Deux corrections incompatibles ne produisent pas de choix arbitraire.
        self.aliases = {k: replace(next(iter(v.values())), confiance='manuel')
                        for k, v in associations.items() if len(v) == 1}
        images, noms = {}, {}
        for f in fiches:
            choix = f.get('presentation', {})
            service = self.pour_fiche(f)
            manuel = choix.get('icone', '')
            if service.logo and not choix.get('separe') and re.fullmatch('[0-9a-f]{64}', manuel):
                images.setdefault(service.logo, set()).add(manuel)
            nom = choix.get('nom', '').strip()
            if service.cle and nom and not choix.get('separe'):
                noms.setdefault(service.cle, set()).add(nom)
        self.icones = {k: next(iter(v)) for k, v in images.items() if len(v) == 1}
        self.noms_manuels = {k: next(iter(v)) for k, v in noms.items() if len(v) == 1}

    def pour_fiche(self, fiche):
        correction = fiche.get('presentation', {}).get('service', '').strip()
        cible = normaliser(correction)
        if correction and cible.genre == 'web' and cible.origines:
            return self.avec_nom(replace(cible, confiance='manuel'))
        return self.resoudre(fiche.get('site', ''))

    def nom_appris(self, cle, valeur):
        if (isinstance(valeur, str) and 1 <= len(valeur.strip()) <= 80
                and not any(ord(c) < 32 for c in valeur) and not any(c in valeur for c in '<>@/\\_')):
            valeur = valeur.strip()
            if self.noms.get(cle) != valeur:
                self.noms[cle] = valeur
                if len(self.noms) > 256:
                    self.noms.pop(next(iter(self.noms)))
                return True
        return False

    def oublier(self):
        self.aliases.clear()
        self.icones.clear()
        self.noms.clear()
        self.noms_manuels.clear()
        self.appris = False
