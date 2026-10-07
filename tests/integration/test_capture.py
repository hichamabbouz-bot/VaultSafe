import pytest

from vaultsafe.capture_comptes import CapturesComptes

APPELANT = 'chrome-extension://egbpodcdijmeibnmfabhiignfppmclbl/'
SECRET = 'Compte-fictif-uniquement!'


def contenu(mot=SECRET, url='https://app.example.test/login?token=secret', type_='connexion'):
    return dict(action='capture_begin', url=url, utilisateur='test@example.test', mot_de_passe=mot, type=type_)


def valeurs(mot=SECRET):
    return dict(utilisateur='test@example.test', mot_de_passe=mot, dossier='', id='')


def test_proposition_doublon_origine_stricte(coffre):
    base, _, gestion, _ = coffre
    captures = CapturesComptes()
    r = captures.creer(base, APPELANT, contenu())
    assert r['etat'] == 'proposition' and 'mot_de_passe' not in r
    assert captures.enregistrer(base, gestion, APPELANT, r['token'], valeurs())['etat'] == 'enregistre'
    assert captures.creer(base, APPELANT, contenu())['etat'] == 'identique'
    r = captures.creer(base, APPELANT, contenu(url='https://other.example.test/login'))
    assert not r['candidats']
    with pytest.raises(ValueError):
        captures.decrire(base, 'autre-appelant', r['token'], secret=True)


@pytest.mark.parametrize('nombre', [1, 2])
def test_changement_sans_identifiant_ne_fusionne_pas_comptes(coffre, nombre):
    base, _, gestion, _ = coffre
    fiches = [gestion.ajouter_identifiant(titre='Fictif', site='https://app.example.test/login',
        nom_utilisateur=f'test{i}@example.test', mot_de_passe=SECRET) for i in range(nombre)]
    captures = CapturesComptes()
    r = captures.creer(base, APPELANT, dict(contenu('Nouveau-fictif!', type_='changement'), utilisateur=''))
    assert len(r['candidats']) == nombre and not r['automatique']
    v = dict(utilisateur='', mot_de_passe='Nouveau-fictif!', dossier='', id='')
    if nombre > 1:
        with pytest.raises(ValueError):
            captures.enregistrer(base, gestion, APPELANT, r['token'], v)
        v['id'] = fiches[0].id
    assert captures.enregistrer(base, gestion, APPELANT, r['token'], v)['etat'] == 'mis_a_jour'
    assert gestion.afficher_identifiant(fiches[0].id).nom_utilisateur == 'test0@example.test'
    assert len(base.lire_vue()['fiches']) == nombre
    assert base.lire_historique(fiches[0].id)[0]['fiche']['mot_de_passe'] == SECRET
    if nombre > 1:
        assert gestion.afficher_identifiant(fiches[1].id).mot_de_passe == SECRET


def test_automatique_et_refus_ne_remplacent_pas(coffre):
    base, _, gestion, parametres = coffre
    parametres.enregistrer_lot({'capture_mode': 'automatique'})
    captures = CapturesComptes()
    r = captures.creer(base, APPELANT, contenu())
    assert captures.resultat(base, gestion, APPELANT, r['token'], 'incertain')['etat'] == 'enregistre'
    r = captures.creer(base, APPELANT, contenu('Tentative-refusee!'))
    assert not r['automatique']
    captures.resultat(base, gestion, APPELANT, r['token'], 'echec')
    assert base.afficher_identifiants()[0]['mot_de_passe'] == SECRET
    nouveau = captures.creer(base, APPELANT, dict(contenu(), utilisateur='nouveau@example.test'))
    captures.resultat(base, gestion, APPELANT, nouveau['token'], 'echec')
    assert len(base.lire_vue()['fiches']) == 1


def test_mise_a_jour_conserve_metadonnees(coffre):
    base, _, gestion, _ = coffre
    f = gestion.ajouter_identifiant(titre='Fictif', site='https://app.example.test/login',
        nom_utilisateur='test@example.test', mot_de_passe=SECRET, notes='Notes conservées', tags=['test'])
    captures = CapturesComptes()
    r = captures.creer(base, APPELANT, contenu('Nouveau-fictif!'))
    assert captures.enregistrer(base, gestion, APPELANT, r['token'], valeurs('Nouveau-fictif!'))['etat'] == 'mis_a_jour'
    fiche = gestion.afficher_identifiant(f.id)
    assert fiche.notes == 'Notes conservées' and fiche.tags == ['test']
    assert base.lire_historique(f.id)[0]['fiche']['mot_de_passe'] == SECRET


def test_verrou_expiration_exclusion(coffre):
    base, connexion, _, parametres = coffre
    horloge = [0]
    captures = CapturesComptes(lambda: horloge[0])
    r = captures.creer(base, APPELANT, contenu())
    connexion.se_deconnecter()
    assert captures.decrire(base, APPELANT, r['token'], secret=True)['etat'] == 'verrouille'
    horloge[0] = 121
    captures.purger()
    assert not captures.attentes
    connexion.se_connecter('Reference-fictive-2026!')
    parametres.enregistrer_lot({'capture_exclus': 'https://app.example.test'})
    assert captures.creer(base, APPELANT, contenu())['etat'] == 'ignore'
