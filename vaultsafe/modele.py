"""Schéma des fiches, dossiers, historique et corbeille, entièrement chiffré."""
from __future__ import annotations

import copy
import re
from datetime import date, datetime, timezone
from uuid import UUID

TYPES = {
    'connexion': 'Identifiant', 'note': 'Note sécurisée', 'carte': 'Carte bancaire',
    'identite': 'Identité', 'licence': 'Licence', 'wifi': 'Wi-Fi', 'serveur': 'Serveur',
}
MODELES = {
    'carte': ['Titulaire', 'Numéro', 'Expiration', 'Code de sécurité'],
    'identite': ['Nom complet', 'Adresse', 'Document', 'Numéro du document'],
    'licence': ['Produit', 'Clé de licence', 'Éditeur'],
    'wifi': ['SSID', 'Type de sécurité'],
    'serveur': ['Hôte', 'Port', 'Protocole'],
}
BASE = {'id', 'titre', 'nom_utilisateur', 'mot_de_passe', 'site', 'notes',
        'date_creation', 'date_modification'}
EXTRA = {'type', 'dossier', 'tags', 'favori', 'champs', 'totp', 'expiration', 'pieces_jointes', 'presentation'}
MAX_PIECE = 16 * 1024 * 1024
TAILLE_BLOC = 64 * 1024


def maintenant():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def normaliser_fiche(fiche):
    resultat = copy.deepcopy(fiche)
    for cle, valeur in {'type': 'connexion', 'dossier': '', 'tags': [], 'favori': False,
                       'champs': [], 'totp': {}, 'expiration': '', 'pieces_jointes': [], 'presentation': {}}.items():
        resultat.setdefault(cle, valeur)
    return resultat


def document_vide():
    return {'schema': 2, 'identifiants': [], 'parametres': {'theme': 'light', 'inactivite': '5'},
            'dossiers': [], 'historique': [], 'corbeille': []}


def mettre_a_niveau(document):
    if document['schema'] == 2:
        return document
    resultat = document_vide()
    resultat['identifiants'] = [normaliser_fiche(f) for f in document['identifiants']]
    resultat['parametres'] = dict(document['parametres'])
    return resultat


def _uuid(valeur):
    if not isinstance(valeur, str) or str(UUID(valeur)) != valeur:
        raise ValueError('Identifiant de fiche ou de dossier invalide.')


def _texte(valeur, maximum=100_000):
    if not isinstance(valeur, str) or len(valeur) > maximum:
        raise ValueError('Champ trop long ou invalide.')


def verifier_fiche(fiche):
    if not isinstance(fiche, dict) or set(fiche) not in (BASE | EXTRA, BASE | (EXTRA - {'presentation'})):
        raise ValueError('Structure de fiche invalide.')
    presentation = fiche.get('presentation', {})
    if (not isinstance(presentation, dict) or not set(presentation) <= {'nom', 'groupe', 'icone', 'equipement', 'separe', 'service'}
            or any(not isinstance(v, str) or len(v) > (253 if k == 'service' else 200) for k, v in presentation.items() if k != 'separe')
            or ('separe' in presentation and type(presentation['separe']) is not bool)
            or presentation.get('equipement', '') not in ('', 'Routeur', 'NAS', 'Serveur', 'Imprimante', 'Appareil réseau local')
            or (presentation.get('icone') and re.fullmatch('[0-9a-f]{64}', presentation['icone']) is None)):
        raise ValueError('Présentation de fiche invalide.')
    if presentation.get('service'):
        from vaultsafe.services import normaliser
        service = normaliser(presentation['service'])
        if service.genre != 'web' or not service.origines:
            raise ValueError('Le service associé doit être un domaine web public.')
    for nom in BASE:
        _texte(fiche[nom])
    for nom in ('type', 'dossier', 'expiration'):
        _texte(fiche[nom], 100)
    _uuid(fiche['id'])
    if not fiche['titre'].strip() or fiche['type'] not in TYPES:
        raise ValueError('Titre ou type de fiche invalide.')
    if fiche['type'] == 'connexion' and not fiche['mot_de_passe']:
        raise ValueError('Le mot de passe est obligatoire pour un identifiant.')
    for nom in ('date_creation', 'date_modification'):
        timestamp = datetime.fromisoformat(fiche[nom])
        if timestamp.tzinfo is None:
            raise ValueError('Date sans fuseau horaire.')
    if fiche['dossier']:
        _uuid(fiche['dossier'])
    if type(fiche['favori']) is not bool:
        raise ValueError('Favori invalide.')
    if (not isinstance(fiche['tags'], list) or len(fiche['tags']) > 30
            or any(not isinstance(t, str) for t in fiche['tags'])
            or len(set(fiche['tags'])) != len(fiche['tags'])):
        raise ValueError('Étiquettes invalides.')
    for tag in fiche['tags']:
        _texte(tag, 50)
        if not tag.strip():
            raise ValueError('Étiquette vide.')
    champs = fiche['champs']
    if not isinstance(champs, list) or len(champs) > 40:
        raise ValueError('Champs personnalisés invalides.')
    noms = set()
    for champ in champs:
        if not isinstance(champ, dict) or set(champ) != {'nom', 'valeur', 'secret'}:
            raise ValueError('Champ personnalisé invalide.')
        _texte(champ['nom'], 100)
        _texte(champ['valeur'])
        if not champ['nom'].strip() or champ['nom'].casefold() in noms or type(champ['secret']) is not bool:
            raise ValueError('Nom de champ dupliqué ou invalide.')
        noms.add(champ['nom'].casefold())
    if fiche['expiration']:
        date.fromisoformat(fiche['expiration'])
    totp = fiche['totp']
    if not isinstance(totp, dict):
        raise ValueError('Configuration TOTP invalide.')
    if totp:
        from vaultsafe.totp import verifier_configuration
        verifier_configuration(totp)
    pieces = fiche['pieces_jointes']
    if not isinstance(pieces, list) or len(pieces) > 20:
        raise ValueError('Trop de pièces jointes (maximum 20 par fiche).')
    piece_ids = set()
    for piece in pieces:
        if not isinstance(piece, dict) or set(piece) != {'id', 'nom', 'taille', 'sha256', 'blocs'}:
            raise ValueError('Manifest de pièce jointe invalide.')
        _uuid(piece['id'])
        _texte(piece['nom'], 255)
        if (not piece['nom'] or re.search(r'[\\/\x00-\x1f]', piece['nom'])
                or piece['nom'] in ('.', '..') or piece['id'] in piece_ids):
            raise ValueError('Nom de pièce jointe invalide.')
        piece_ids.add(piece['id'])
        if type(piece['taille']) is not int or not 0 <= piece['taille'] <= MAX_PIECE:
            raise ValueError('Pièce jointe trop volumineuse (maximum 16 Mo).')
        if (type(piece['blocs']) is not int
                or piece['blocs'] != max(1, (piece['taille'] + TAILLE_BLOC - 1) // TAILLE_BLOC)
                or not isinstance(piece['sha256'], str)
                or re.fullmatch('[0-9a-f]{64}', piece['sha256']) is None):
            raise ValueError('Manifest de pièce jointe invalide.')


def verifier_document(document):
    if (set(document) != {'schema', 'identifiants', 'parametres', 'dossiers', 'historique', 'corbeille'}
            or type(document['schema']) is not int or document['schema'] != 2):
        raise ValueError('Version des données non prise en charge.')
    prefs = document['parametres']
    if (not isinstance(prefs, dict) or len(prefs) > 100
            or any(not isinstance(k, str) or not isinstance(v, str) or len(k) > 100 or len(v) > 4096
                   for k, v in prefs.items())):
        raise ValueError('Préférences invalides.')
    dossiers = document['dossiers']
    if not isinstance(dossiers, list) or len(dossiers) > 1000:
        raise ValueError('Trop de dossiers.')
    parents = {}
    for dossier in dossiers:
        if not isinstance(dossier, dict) or set(dossier) != {'id', 'nom', 'parent'}:
            raise ValueError('Dossier invalide.')
        _uuid(dossier['id'])
        _texte(dossier['nom'], 100)
        _texte(dossier['parent'], 36)
        if not dossier['nom'].strip() or dossier['id'] in parents:
            raise ValueError('Nom de dossier vide ou dossier dupliqué.')
        parents[dossier['id']] = dossier['parent']
    for identifiant in parents:
        visites = {identifiant}
        parent = parents[identifiant]
        while parent:
            if parent not in parents or parent in visites:
                raise ValueError('Hiérarchie de dossiers invalide.')
            visites.add(parent)
            parent = parents[parent]
    actifs, corbeille, historique = (document[n] for n in ('identifiants', 'corbeille', 'historique'))
    if (not isinstance(actifs, list) or not isinstance(corbeille, list) or not isinstance(historique, list)
            or len(actifs) + len(corbeille) > 50_000 or len(historique) > 50_000):
        raise ValueError('Taille du coffre non prise en charge.')
    ids = set()
    for fiche in actifs:
        verifier_fiche(fiche)
        if fiche['id'] in ids or (fiche['dossier'] and fiche['dossier'] not in parents):
            raise ValueError('Fiche dupliquée ou dossier introuvable.')
        ids.add(fiche['id'])
    for item in corbeille:
        if not isinstance(item, dict) or set(item) != {'fiche', 'date_suppression'}:
            raise ValueError('Corbeille invalide.')
        verifier_fiche(item['fiche'])
        datetime.fromisoformat(item['date_suppression'])
        if item['fiche']['id'] in ids:
            raise ValueError('Fiche dupliquée dans la corbeille.')
        ids.add(item['fiche']['id'])
    revisions = {}
    for item in historique:
        if not isinstance(item, dict) or set(item) != {'fiche', 'date'}:
            raise ValueError('Historique invalide.')
        verifier_fiche(item['fiche'])
        datetime.fromisoformat(item['date'])
        fiche_id = item['fiche']['id']
        if fiche_id not in ids:
            raise ValueError('Révision orpheline.')
        revisions[fiche_id] = revisions.get(fiche_id, 0) + 1
        if revisions[fiche_id] > 20:
            raise ValueError('Trop de révisions pour une fiche.')
