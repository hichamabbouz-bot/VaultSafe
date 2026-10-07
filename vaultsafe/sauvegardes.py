"""Sauvegardes automatiques chiffrées par coffre, rétention limitée aux fichiers créés ici."""
from __future__ import annotations

import re
import secrets
import time
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from vaultsafe.securite_coffre import verifier_entete


class SauvegardesAutomatiques:
    def __init__(self, base):
        self.base = base
        self.derniere_signature = None
        self.derniere_execution = 0.0
        self.derniere_erreur = ''
        self.dernier_fichier = None

    def effectuer(self, forcer=False):
        self.base.exiger_ouverture()
        preferences = self.base.lire_preferences()
        dossier = preferences.get('backup_dossier', '')
        if not dossier:
            return None
        try:
            minutes = int(preferences.get('backup_minutes', '60'))
            retention = int(preferences.get('backup_retention', '7'))
        except (TypeError, ValueError) as erreur:
            raise ValueError('Réglages de sauvegarde invalides.') from erreur
        if not 1 <= minutes <= 1440 or not 1 <= retention <= 50:
            raise ValueError('Réglages de sauvegarde invalides.')
        if not forcer and (time.monotonic() - self.derniere_execution < minutes * 60
                          or self.base._signature == self.derniere_signature):
            return None
        dossier = Path(dossier).expanduser().resolve()
        dossier.mkdir(parents=True, exist_ok=True)
        with self.base._mutex, self.base._sql() as sql:
            ligne, _ = self.base._contenu(sql)
            coffre_id = verifier_entete(ligne['entete'])['coffre_id']
        horodatage = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        nom = f'vaultsafe-{coffre_id}-{horodatage}-{secrets.token_hex(4)}.vaultsafe'
        # Capturer et vérifier localement sous le verrou du dépôt ; la copie
        # vers un disque lent n'a ensuite plus besoin d'une clé ouverte.
        with tempfile.TemporaryDirectory(prefix='vaultsafe-sauvegarde-') as travail:
            with self.base._mutex:
                snapshot = self.base.exporter_sauvegarde(Path(travail) / 'snapshot.vaultsafe')
                signature = self.base._signature
            temporaire = None
            try:
                descripteur, nom_temp = tempfile.mkstemp(prefix='.vaultsafe-auto-', suffix='.tmp', dir=dossier)
                temporaire = Path(nom_temp)
                with os.fdopen(descripteur, 'wb') as sortie, snapshot.open('rb') as entree:
                    shutil.copyfileobj(entree, sortie, 1024 * 1024)
                    sortie.flush()
                    os.fsync(sortie.fileno())
                destination = dossier / nom
                os.replace(temporaire, destination)
            finally:
                if temporaire is not None:
                    temporaire.unlink(missing_ok=True)
        self.derniere_execution = time.monotonic()
        self.derniere_signature = signature
        self.dernier_fichier = destination
        self.derniere_erreur = ''
        motif = re.compile(r'^vaultsafe-' + re.escape(coffre_id) + r'-\d{8}T\d{12}Z-[0-9a-f]{8}\.vaultsafe$')
        anciennes = sorted((f for f in dossier.iterdir() if f.is_file() and not f.is_symlink()
                             and motif.fullmatch(f.name)), key=lambda f: f.name, reverse=True)
        for ancienne in anciennes[retention:]:
            ancienne.unlink()
        return destination

    def essayer(self, forcer=False):
        try:
            return self.effectuer(forcer)
        except (OSError, ValueError):
            self.derniere_erreur = 'La sauvegarde automatique a échoué. Vérifiez son dossier et l’espace disponible.'
            return None
