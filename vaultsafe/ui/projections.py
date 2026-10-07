"""Pure presentation work, run in the bounded worker before updating Qt models."""
from vaultsafe.services import MoteurServices
from vaultsafe.sites import presenter


def preparer_table(fiches, dossiers=(), moteur=None):
    moteur = moteur or MoteurServices()
    moteur.apprendre(fiches)
    noms = {d['id']: d['nom'] for d in dossiers}
    publics = []
    for f in fiches:
        public = dict(f)
        public.update(presenter(f, moteur))
        public['dossier_nom'] = noms.get(f['dossier'], 'Sans dossier')
        public['_recherche'] = ' '.join((f['titre'], public['_libelle'], f['nom_utilisateur'], f['site'],
            public['_site_nom'], public['dossier_nom'], ' '.join(f['tags']))).casefold()
        public['_nom'] = f['titre'].casefold()
        public['_identifiant'] = f['nom_utilisateur'].casefold()
        public['_dossier'] = public['dossier_nom'].casefold()
        publics.append(public)
    return {'fiches': publics, 'aliases': moteur.aliases, 'icones': moteur.icones,
            'noms_manuels': moteur.noms_manuels}


def lire_vue_preparee(base, noms=None):
    vue = base.lire_vue()
    moteur = MoteurServices()
    moteur.noms = dict(noms or {})
    vue['table'] = preparer_table(vue['fiches'], vue['dossiers'], moteur)
    return vue
