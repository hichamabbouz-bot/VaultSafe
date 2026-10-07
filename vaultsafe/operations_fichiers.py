"""Imports avec aperçu et écritures atomiques ; exports explicitement en clair."""
from __future__ import annotations

import copy
import csv
import io
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from vaultsafe.import_csv import ImportateurCSV
from vaultsafe.modele import normaliser_fiche, verifier_fiche, maintenant
from vaultsafe.securite_coffre import decoder_json, encoder_json


def repere(fiche):
    return (fiche['type'], (fiche['site'].strip().casefold().rstrip('/') or fiche['titre'].casefold()),
            fiche['nom_utilisateur'].casefold())


def preparer_import(gestion, source):
    gestion.connexion.exiger_connexion()
    source = Path(source)
    if not source.is_file() or source.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('Fichier d’import introuvable ou trop volumineux (maximum 20 Mo).')
    if source.suffix.lower() == '.json':
        data = decoder_json(source.read_bytes())
        if set(data) != {'format', 'fiches'} or data['format'] != 'VaultSafe-export-1' or not isinstance(data['fiches'], list):
            raise ValueError('Format JSON non reconnu. Choisissez un export VaultSafe.')
        if len(data['fiches']) > 50_000:
            raise ValueError('Trop de fiches dans l’import.')
        fiches = []
        for valeur in data['fiches']:
            valeur = normaliser_fiche(valeur)
            verifier_fiche(valeur)
            if valeur['pieces_jointes']:
                raise ValueError('Les pièces jointes se restaurent avec une sauvegarde chiffrée.')
            fiches.append(valeur)
        invalides = 0
        format_import = 'JSON VaultSafe'
    else:
        fiches, invalides, format_import = ImportateurCSV(gestion).lire_csv_navigateur(source)
    comptes = [asdict(gestion.preparer_fiche(f)) for f in fiches]
    existants = {repere(asdict(f)) for f in gestion.afficher_identifiants()}
    connus = set(existants)
    doublons = 0
    for fiche in comptes:
        cle = repere(fiche)
        doublons += cle in connus
        connus.add(cle)
    return {'format': format_import, 'comptes': comptes, 'total': len(comptes) + invalides,
            'invalides': invalides, 'doublons': doublons, 'nouveaux': len(comptes) - doublons}


def appliquer_import(gestion, apercu, politique='ignorer'):
    gestion.connexion.exiger_connexion()
    if politique not in ('ignorer', 'ajouter', 'remplacer'):
        raise ValueError('Choix de doublons invalide.')
    source = copy.deepcopy(apercu['comptes'])

    def importer(document, sql):
        from vaultsafe.fonctions_coffre import _revision, _nettoyer_pieces
        existants = {repere(f): f for f in document['identifiants']}
        ajoutes = remplaces = ignores = 0
        for fiche in source:
            cle = repere(fiche)
            ancien = existants.get(cle)
            if ancien is not None and politique == 'ignorer':
                ignores += 1
                continue
            if ancien is not None and politique == 'remplacer':
                _revision(document, ancien)
                fiche['id'] = ancien['id']
                fiche['date_creation'] = ancien['date_creation']
                fiche['date_modification'] = maintenant()
                fiche['pieces_jointes'] = copy.deepcopy(ancien['pieces_jointes'])
                fiche['dossier'] = ancien['dossier']
                document['identifiants'][document['identifiants'].index(ancien)] = fiche
                remplaces += 1
            else:
                # Un dossier importé n'existe pas nécessairement dans le coffre cible.
                fiche['dossier'] = ''
                document['identifiants'].append(fiche)
                ajoutes += 1
            existants[cle] = fiche
        _nettoyer_pieces(document, sql)
        return {'ajoutes': ajoutes, 'remplaces': remplaces, 'ignores': ignores,
                'invalides': apercu['invalides']}
    return gestion.base._modifier(importer, avec_sql=True)


def ecrire_atomique(destination, donnees):
    destination = Path(destination).resolve()
    temporaire = None
    try:
        descripteur, nom = tempfile.mkstemp(prefix='.vaultsafe-export-', suffix='.tmp', dir=destination.parent)
        temporaire = Path(nom)
        with os.fdopen(descripteur, 'wb') as fichier:
            fichier.write(donnees)
            fichier.flush()
            os.fsync(fichier.fileno())
        os.replace(temporaire, destination)
        return destination
    finally:
        if temporaire is not None:
            temporaire.unlink(missing_ok=True)


def _csv_sans_formule(valeur):
    if valeur and valeur[0] in "'=+-@\t\r\n":
        return "'" + valeur
    return valeur


def exporter_clair(gestion, destination, mot_de_passe, format_export='json'):
    gestion.base.authentifier_action(mot_de_passe)
    if format_export not in ('json', 'csv'):
        raise ValueError('Format d’export invalide.')
    destination = Path(destination).with_suffix('.' + format_export).resolve()
    if destination == gestion.base.chemin:
        raise ValueError('Choisissez une destination distincte du coffre.')
    fiches = [asdict(f) for f in gestion.afficher_identifiants()]
    if format_export == 'json':
        for fiche in fiches:
            fiche['pieces_jointes'] = []
        donnees = encoder_json({'format': 'VaultSafe-export-1', 'fiches': fiches})
    else:
        sortie = io.StringIO(newline='')
        writer = csv.DictWriter(sortie, fieldnames=['name', 'url', 'username', 'password', 'note', 'vaultsafe_csv'],
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for fiche in fiches:
            if fiche['type'] != 'connexion':
                continue
            ligne = {'name': fiche['titre'], 'url': fiche['site'], 'username': fiche['nom_utilisateur'],
                     'password': fiche['mot_de_passe'], 'note': fiche['notes']}
            ligne = {k: _csv_sans_formule(v) for k, v in ligne.items()}
            ligne['vaultsafe_csv'] = '1'
            writer.writerow(ligne)
        donnees = sortie.getvalue().encode('utf-8-sig')
    return ecrire_atomique(destination, donnees)


def exporter_piece(base, fiche_id, piece_id, destination):
    destination = Path(destination).resolve()
    if destination == base.chemin or (destination.exists() and os.path.samefile(destination, base.chemin)):
        raise ValueError('La pièce ne peut pas remplacer le coffre actif.')
    return ecrire_atomique(destination, base.lire_piece(fiche_id, piece_id))
