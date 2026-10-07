"""Import explicitement authentifié du coffre historique, ouvert en lecture seule."""
from __future__ import annotations

import hashlib
import hmac
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def lire_ancien_coffre(source, mot_de_passe):
    source = Path(source).resolve()
    if not source.is_file() or source.stat().st_size > 128 * 1024 * 1024:
        raise ValueError('Ancien coffre introuvable ou trop volumineux.')
    if not isinstance(mot_de_passe, str) or len(mot_de_passe.encode('utf-8')) > 4096:
        raise ValueError('Mot de passe invalide.')
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as sql:
            sql.row_factory = sqlite3.Row
            sql.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 32 * 1024 * 1024)
            sql.execute('PRAGMA trusted_schema=OFF')
            sql.execute('PRAGMA query_only=ON')
            sql.execute('BEGIN')
            objets = {(r[0], r[1]) for r in sql.execute(
                "SELECT name,type FROM sqlite_master WHERE type IN ('table','view','trigger')")}
            if objets != {('acces', 'table'), ('identifiants', 'table'), ('parametres', 'table')}:
                raise ValueError('Ce fichier ne correspond pas à l’ancien format VaultSafe.')
            if sql.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Ancien coffre endommagé.')
            if [r[1] for r in sql.execute('PRAGMA table_info(acces)')] != ['id', 'sel', 'empreinte', 'repetitions']:
                raise ValueError('Ancien accès invalide.')
            acces = sql.execute('SELECT * FROM acces LIMIT 2').fetchall()
            if len(acces) != 1 or acces[0]['id'] != 1:
                raise ValueError('Ancien accès invalide.')
            acces = acces[0]
            if (not isinstance(acces['sel'], bytes) or not 16 <= len(acces['sel']) <= 64
                    or not isinstance(acces['empreinte'], bytes) or len(acces['empreinte']) != 32
                    or type(acces['repetitions']) is not int or not 100_000 <= acces['repetitions'] <= 2_000_000):
                raise ValueError('Paramètres de l’ancien accès invalides.')
            empreinte = hashlib.pbkdf2_hmac('sha256', mot_de_passe.encode('utf-8'),
                                          acces['sel'], acces['repetitions'], dklen=32)
            if not hmac.compare_digest(empreinte, acces['empreinte']):
                raise ValueError('Mot de passe de l’ancien coffre incorrect.')
            colonnes = ['id', 'titre', 'nom_utilisateur', 'mot_de_passe', 'site', 'notes',
                        'date_creation', 'date_modification']
            if [r[1] for r in sql.execute('PRAGMA table_info(identifiants)')] != colonnes:
                raise ValueError('Anciennes fiches invalides.')
            fiches = sql.execute('SELECT * FROM identifiants LIMIT 50001').fetchall()
            if len(fiches) > 50_000:
                raise ValueError('Ancien coffre trop volumineux.')
            resultat = []
            for ligne in fiches:
                fiche = dict(ligne)
                if any(not isinstance(v, str) or len(v) > 100_000 for v in fiche.values()):
                    raise ValueError('Une ancienne fiche est invalide.')
                fiche.pop('id')
                # L'import crée des UUID propres ; les dates historiques sont conservées après validation.
                for nom in ('date_creation', 'date_modification'):
                    stamp = datetime.fromisoformat(fiche[nom])
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=timezone.utc)
                    fiche[nom] = stamp.isoformat(timespec='seconds')
                if not fiche['titre'].strip() or not fiche['mot_de_passe']:
                    raise ValueError('Une ancienne fiche est incomplète.')
                resultat.append(fiche)
            return resultat
    except (sqlite3.Error, OSError) as erreur:
        raise ValueError('Impossible de lire l’ancien coffre. Le fichier est conservé.') from erreur


def preparer_migration(gestion, source, mot_de_passe):
    gestion.connexion.exiger_connexion()
    source = Path(source).resolve()
    if source == gestion.base.chemin:
        raise ValueError('Choisissez l’ancienne base, distincte du coffre actif.')
    fiches = lire_ancien_coffre(source, mot_de_passe)
    connus = {(f.site.strip().casefold().rstrip('/'), f.nom_utilisateur.casefold(), f.titre.casefold())
              for f in gestion.afficher_identifiants()}
    nouvelles = []
    for fiche in fiches:
        repere = (fiche['site'].strip().casefold().rstrip('/'),
                  fiche['nom_utilisateur'].casefold(), fiche['titre'].casefold())
        if repere not in connus:
            connus.add(repere)
            nouvelles.append(fiche)
    return {'comptes': nouvelles, 'total': len(fiches), 'doublons': len(fiches) - len(nouvelles),
            'source': str(source)}


def appliquer_migration(gestion, apercu):
    gestion.connexion.exiger_connexion()
    # Une unique transaction chiffrée ; aucun enregistrement partiel.
    return gestion.ajouter_lot(apercu['comptes'])
