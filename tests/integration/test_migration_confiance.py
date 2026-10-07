import hashlib
import os
import sqlite3
from contextlib import closing

import pytest

from vaultsafe.migration import appliquer_migration, preparer_migration


def test_migration_historique_authentifiee_sans_alteration(coffre, tmp_path):
    base, _, gestion, _ = coffre
    ancien = tmp_path / 'ancien-fictif.db'
    salt = os.urandom(16)
    empreinte = hashlib.pbkdf2_hmac('sha256', b'Ancien-fictif-2026!', salt, 100000)
    with closing(sqlite3.connect(ancien)) as sql, sql:
        sql.execute('CREATE TABLE acces (id INTEGER, sel BLOB, empreinte BLOB, repetitions INTEGER)')
        sql.execute('INSERT INTO acces VALUES (1, ?, ?, 100000)', (salt, empreinte))
        sql.execute('CREATE TABLE identifiants (id TEXT, titre TEXT, nom_utilisateur TEXT, mot_de_passe TEXT, site TEXT, notes TEXT, date_creation TEXT, date_modification TEXT)')
        sql.execute('INSERT INTO identifiants VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            ('ancien-id', 'Historique fictif', 'test@example.test', 'Ancien-secret-fictif!',
             'https://example.test/login', 'Note historique', '2025-01-01T00:00:00', '2025-01-02T00:00:00'))
        sql.execute('CREATE TABLE parametres (nom TEXT, valeur TEXT)')
    original = ancien.read_bytes()
    with pytest.raises(ValueError):
        preparer_migration(gestion, ancien, 'Erreur-fictive!')
    assert not base.lire_vue()['fiches']
    apercu = preparer_migration(gestion, ancien, 'Ancien-fictif-2026!')
    appliquer_migration(gestion, apercu)
    fiche = gestion.afficher_identifiant(base.lire_vue()['fiches'][0]['id'])
    assert fiche.mot_de_passe == 'Ancien-secret-fictif!'
    assert fiche.notes == 'Note historique'
    assert fiche.date_creation.startswith('2025-01-01')
    assert preparer_migration(gestion, ancien, 'Ancien-fictif-2026!')['doublons'] == 1
    assert ancien.read_bytes() == original


@pytest.mark.skipif(os.name != 'nt', reason='DPAPI Windows')
def test_confiance_dpapi_revoquee_et_contexte_change(coffre, tmp_path, monkeypatch):
    from vaultsafe.appareil_confiance import AppareilConfiance
    monkeypatch.setenv('VAULTSAFE_DATA_DIR', str(tmp_path / 'profil-fictif'))
    base, connexion, gestion, _ = coffre
    fiche = gestion.ajouter_identifiant(titre='DPAPI fictif', mot_de_passe='Secret-fictif!')
    appareil = AppareilConfiance(base)
    appareil.autoriser()
    connexion.se_deconnecter()
    appareil.ouvrir()
    assert gestion.afficher_identifiant(fiche.id).mot_de_passe == 'Secret-fictif!'
    appareil.revoquer()
    connexion.se_deconnecter()
    with pytest.raises(ValueError):
        appareil.ouvrir()
    assert not base.coffre_ouvert
    connexion.se_connecter('Reference-fictive-2026!')
    appareil.autoriser()
    base.changer_mot_de_passe('Reference-fictive-2026!', 'Reference-renouvelee-2026!')
    assert appareil.etat() is None
    assert not appareil.chemin.exists()


def test_restauration_authentifiee_et_echec_preserve_coffre(coffre, tmp_path):
    base, connexion, gestion, _ = coffre
    f = gestion.ajouter_identifiant(titre='Avant sauvegarde', mot_de_passe='Premier-fictif!')
    copie = base.exporter_sauvegarde(tmp_path / 'copie.vaultsafe')
    gestion.modifier_identifiant(f.id, mot_de_passe='Apres-fictif!')
    avant = base.chemin.read_bytes()
    with pytest.raises(ValueError):
        base.restaurer_sauvegarde(copie, 'Tentative-invalide!')
    assert base.chemin.read_bytes() == avant
    base.restaurer_sauvegarde(copie, 'Reference-fictive-2026!')
    assert not base.coffre_ouvert
    connexion.se_connecter('Reference-fictive-2026!')
    assert gestion.afficher_identifiant(f.id).mot_de_passe == 'Premier-fictif!'
    assert not list(tmp_path.glob('.vaultsafe-restauration-*'))
