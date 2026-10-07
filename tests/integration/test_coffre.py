import os

import pytest

from vaultsafe.database import BaseDeDonnees
from vaultsafe.operations_fichiers import appliquer_import, exporter_clair, preparer_import

MASTER = 'Reference-fictive-2026!'
SECRET = 'Secret-fictif-jamais-personnel!'


def test_projection_chiffrement_reouverture(coffre):
    base, connexion, gestion, _ = coffre
    f = gestion.ajouter_identifiant(titre='Service fictif', nom_utilisateur='personne@example.test',
        mot_de_passe=SECRET, site='https://service.example.test/login', notes='Note fictive')
    public = base.lire_vue()['fiches'][0]
    assert not {'mot_de_passe', 'notes', 'totp'} & public.keys()
    assert public['secret_present']
    connexion.se_deconnecter()
    assert SECRET.encode() not in base.chemin.read_bytes()
    with pytest.raises(ValueError):
        base.lire_vue()
    with pytest.raises(ValueError):
        connexion.se_connecter('Tentative-invalide!')
    connexion.se_connecter(MASTER)
    assert gestion.afficher_identifiant(f.id).mot_de_passe == SECRET


def test_historique_corbeille_et_dossiers(coffre):
    base, _, gestion, _ = coffre
    dossier = base.creer_dossier('Travail fictif')
    f = gestion.ajouter_identifiant(titre='Fictif', mot_de_passe=SECRET, dossier=dossier)
    gestion.modifier_identifiant(f.id, mot_de_passe='Nouveau-fictif!')
    assert base.lire_historique(f.id)[0]['fiche']['mot_de_passe'] == SECRET
    gestion.supprimer_identifiant(f.id)
    assert len(base.lire_corbeille()) == 1
    base.restaurer_fiche(f.id)
    assert gestion.afficher_identifiant(f.id).dossier == dossier
    base.restaurer_revision(f.id, 0)
    assert gestion.afficher_identifiant(f.id).mot_de_passe == SECRET


def test_piece_sauvegarde_integrite(coffre, tmp_path):
    base, _, gestion, _ = coffre
    f = gestion.ajouter_identifiant(titre='Pièce fictive', mot_de_passe=SECRET)
    contenu = b'piece fictive confidentielle' * 1000
    source = tmp_path / 'piece.txt'
    source.write_bytes(contenu)
    piece = base.ajouter_piece(f.id, source)
    sauvegarde = base.exporter_sauvegarde(tmp_path / 'copie.vaultsafe')
    copie = BaseDeDonnees(sauvegarde)
    try:
        copie.ouvrir_coffre(MASTER)
        assert copie.lire_piece(f.id, piece) == contenu
        assert copie.verifier_integrite()['pieces'] == 1
    finally:
        copie.verrouiller()
    assert contenu not in sauvegarde.read_bytes()


def test_import_export_et_doublon(coffre, tmp_path):
    base, _, gestion, _ = coffre
    gestion.ajouter_identifiant(titre='Export fictif', mot_de_passe=SECRET,
        nom_utilisateur='test@example.test', site='https://example.test/login')
    for format_export in ('json', 'csv'):
        fichier = exporter_clair(gestion, tmp_path / ('sortie.' + format_export), MASTER, format_export)
        apercu = preparer_import(gestion, fichier)
        assert apercu['doublons'] == 1
        assert appliquer_import(gestion, apercu)['ignores'] == 1
    assert len(base.lire_vue()['fiches']) == 1


def test_recuperation_et_preferences(coffre):
    base, connexion, gestion, parametres = coffre
    f = gestion.ajouter_identifiant(titre='Récupération fictive', mot_de_passe=SECRET)
    parametres.enregistrer_lot({'theme': 'dark', 'inactivite': '0'})
    cle = base.creer_cle_recuperation(MASTER)
    connexion.se_deconnecter()
    base.recuperer_coffre(cle, 'Nouvelle-reference-2026!')
    connexion.se_connecter('Nouvelle-reference-2026!')
    assert gestion.afficher_identifiant(f.id).mot_de_passe == SECRET
    assert base.lire_preferences()['theme'] == 'dark'


def test_erreur_disque_preserve_destination(coffre, tmp_path, monkeypatch):
    from vaultsafe.operations_fichiers import ecrire_atomique
    destination = tmp_path / 'precedent.txt'
    destination.write_bytes(b'ancienne sortie fictive')
    def refuser(*args):
        raise OSError('Erreur disque fictive')
    monkeypatch.setattr(os, 'replace', refuser)
    with pytest.raises(OSError):
        ecrire_atomique(destination, b'nouvelle sortie')
    assert destination.read_bytes() == b'ancienne sortie fictive'
    assert not list(tmp_path.glob('.vaultsafe-export-*'))
