from PySide6.QtCore import Qt

from vaultsafe.ui.liste import FiltreFiches, ModeleFiches


def test_modele_tri_filtre_sans_secrets(coffre, qt):
    base, _, gestion, _ = coffre
    a = gestion.ajouter_identifiant(titre='Alpha fictif', mot_de_passe='Secret-fictif', favori=True)
    gestion.ajouter_identifiant(titre='Beta fictif', mot_de_passe='Secret-fictif')
    modele = ModeleFiches()
    filtre = FiltreFiches()
    filtre.setSourceModel(modele)
    modele.remplacer(base.lire_vue()['fiches'])
    assert modele.rowCount() == 2 and modele.columnCount() == 7
    assert modele.index(0, 0).data(Qt.ItemDataRole.UserRole)['id'] == a.id
    filtre.mots = ['beta']
    filtre.invalidateFilter()
    assert filtre.rowCount() == 1
    assert 'mot_de_passe' not in filtre.index(0, 0).data(Qt.ItemDataRole.UserRole)
    filtre.mots, filtre.etat = [], 'favoris'
    filtre.invalidateFilter()
    assert filtre.rowCount() == 1


def test_projection_preparee_equivalente_et_noms_appris(coffre, qt):
    from vaultsafe.ui.projections import lire_vue_preparee
    base, _, gestion, _ = coffre
    gestion.ajouter_identifiant(titre='app.example.test', site='https://app.example.test',
        mot_de_passe='Secret-fictif', nom_utilisateur='personne@example.test')
    vue = lire_vue_preparee(base)
    normal, prepare = ModeleFiches(), ModeleFiches()
    normal.remplacer(vue['fiches'], vue['dossiers'])
    prepare.remplacer(vue['fiches'], vue['dossiers'], table=vue['table'])
    assert normal.fiches == prepare.fiches
    assert not {'mot_de_passe', 'notes', 'totp'} & prepare.fiches[0].keys()
