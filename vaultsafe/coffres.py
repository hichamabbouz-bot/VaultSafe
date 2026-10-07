"""Choix de coffre : chemins publics, clés et sessions toujours distinctes."""
from __future__ import annotations

import json
from pathlib import Path

from vaultsafe.config import obtenir_dossier_donnees
from vaultsafe.operations_fichiers import ecrire_atomique


def memoriser_coffre(chemin):
    chemin = Path(chemin).resolve()
    if not chemin.is_file():
        raise ValueError('Coffre introuvable.')
    dossier = obtenir_dossier_donnees()
    dossier.mkdir(parents=True, exist_ok=True)
    ecrire_atomique(dossier / 'coffre-actif.json',
                    json.dumps({'chemin': str(chemin)}, ensure_ascii=False).encode('utf-8'))


def dernier_coffre():
    pointeur = obtenir_dossier_donnees() / 'coffre-actif.json'
    try:
        if not pointeur.is_file() or pointeur.stat().st_size > 4096:
            return None
        valeur = json.loads(pointeur.read_text(encoding='utf-8'))
        if not isinstance(valeur, dict) or set(valeur) != {'chemin'} or not isinstance(valeur['chemin'], str):
            return None
        chemin = Path(valeur['chemin'])
        if not chemin.is_absolute() or not chemin.is_file() or chemin.suffix.lower() not in ('.db', '.vaultsafe'):
            return None
        return chemin.resolve()
    except (OSError, ValueError, TypeError):
        return None


def cloner_sauvegarde(source, destination, mot_de_passe):
    """Ouvre une copie vérifiée, sans transformer le fichier de sauvegarde."""
    import os
    import shutil
    import tempfile
    from vaultsafe.database import BaseDeDonnees
    from vaultsafe.stockage_chiffre import MAX_DATABASE_BYTES
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file() or source.stat().st_size > MAX_DATABASE_BYTES:
        raise ValueError('Sauvegarde introuvable ou trop volumineuse.')
    if destination.exists() or destination == source:
        raise ValueError('Choisissez un nouveau fichier pour ouvrir cette sauvegarde.')
    with tempfile.TemporaryDirectory(prefix='vaultsafe-ouverture-') as travail:
        copie = Path(travail) / 'copie.db'
        shutil.copyfile(source, copie)
        base = BaseDeDonnees(copie)
        try:
            base.ouvrir_coffre(mot_de_passe)
            base.verifier_integrite()
            verifie = base.exporter_sauvegarde(Path(travail) / 'verifie.db')
            cree = False
            try:
                fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY, 0o600)
                cree = True
                with os.fdopen(fd, 'wb') as sortie, verifie.open('rb') as entree:
                    shutil.copyfileobj(entree, sortie, 1024 * 1024)
                    sortie.flush()
                    os.fsync(sortie.fileno())
            except BaseException:
                if cree:
                    destination.unlink(missing_ok=True)
                raise
        finally:
            base.verrouiller()
    return destination
