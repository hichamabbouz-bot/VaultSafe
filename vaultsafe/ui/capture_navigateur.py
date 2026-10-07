"""API de capture pour les cadres d'extension ; aucune seconde confirmation Windows."""
import re
import time
from PySide6.QtCore import QTimer
from vaultsafe.capture_comptes import CapturesComptes
from vaultsafe.parametres import Parametres


def traiter(app, demande, livrer):
    contenu, appelant = demande['contenu'], demande['appelant']
    action = contenu.get('action')
    if app.captures_browser is None:
        app.captures_browser = CapturesComptes()
        app.capture_timer = QTimer(app)
        app.capture_timer.setSingleShot(True)
        def nettoyer():
            app.captures_browser.purger()
            programmer()
        app.capture_timer.timeout.connect(nettoyer)
    moteur, base, generation = app.captures_browser, app.base, app.taches.generation
    def programmer():
        with moteur.mutex:
            echeance = min((r['expiration'] for r in moteur.attentes.values()), default=None)
        app.capture_timer.stop()
        if echeance is not None:
            app.capture_timer.start(max(1, int((echeance - moteur.horloge()) * 1000)))
    def valide(ouvert=False):
        if demande['expiration'] <= time.time() or app.base is not base or generation != app.taches.generation:
            raise ValueError('La session a changé.')
        if ouvert and not app.ouvert:
            raise ValueError('Déverrouiller VaultSafe pour enregistrer.')
    def fini(r):
        programmer()
        r['theme'] = app.theme
        if r.get('origine'):
            from vaultsafe.services import normaliser
            r['service'] = normaliser(r['origine']).nom
            if app.ouvert and hasattr(app, 'icones_sites'):
                from vaultsafe.sites import presenter
                service = presenter({'site': r['origine'], 'titre': ''}, app.icones_sites.moteur)
                r['service'] = service['_site_nom']
                r['icone'] = app.icones_sites.pour_extension(dict(site=r['origine'], **service),
                    app.preferences.get('icones_reseau', 'non') == 'oui')
        livrer(r, secret='mot_de_passe' in r)
    def echec(_):
        contenu['mot_de_passe'] = ''
        programmer()
        livrer({'ok': False, 'erreur': 'Déverrouiller VaultSafe pour enregistrer.' if not app.ouvert
                else 'Proposition expirée, compte ambigu ou enregistrement refusé.'}, False)
    try:
        if action == 'capture_options' and set(contenu) == {'action'}:
            app.executer(lambda: moteur.options(base), lambda options: fini({'ok': True, 'options': options}), echec)
            return
        if action == 'capture_config' and set(contenu) == {'action', 'mode', 'exclus'}:
            if not isinstance(contenu['mode'], str) or not isinstance(contenu['exclus'], str):
                raise ValueError('Préférence invalide.')
            valeurs = {'capture_mode': Parametres.valider('capture_mode', contenu['mode']),
                       'capture_exclus': Parametres.valider('capture_exclus', contenu['exclus'])}
            def configurer():
                valide(True)
                app.parametres.enregistrer_lot(valeurs)
                moteur.vider()
                return {'ok': True, 'options': moteur.options(base)}
            app.mutation(configurer, fini, erreur=echec)
            return
        if action == 'capture_begin':
            def commencer():
                try:
                    valide()
                    return moteur.creer(base, appelant, contenu)
                finally:
                    contenu['mot_de_passe'] = ''
            app.executer(commencer, fini, echec)
            return
        token = contenu.get('token')
        if not isinstance(token, str) or re.fullmatch(r'[A-Za-z0-9_-]{32}', token) is None:
            raise ValueError('Proposition invalide.')
        if action in ('capture_read', 'capture_ignore') and set(contenu) == {'action', 'token'}:
            def lire():
                valide()
                return moteur.ignorer(appelant, token) if action == 'capture_ignore' else moteur.decrire(base, appelant, token, secret=True)
            app.executer(lire, fini, echec)
            return
        if action == 'capture_resolve' and set(contenu) == {'action', 'token', 'resultat'}:
            def resoudre():
                valide()
                return moteur.resultat(base, app.identifiants, appelant, token, contenu['resultat'])
            app.mutation(resoudre, fini, erreur=echec)
            return
        if action == 'capture_commit' and set(contenu) == {'action', 'token', 'utilisateur', 'mot_de_passe', 'dossier', 'id'}:
            def enregistrer():
                try:
                    valide(True)
                    valeurs = {k: contenu[k] for k in ('utilisateur', 'mot_de_passe', 'dossier', 'id')}
                    return moteur.enregistrer(base, app.identifiants, appelant, token, valeurs)
                finally:
                    contenu['mot_de_passe'] = ''
            app.mutation(enregistrer, fini, erreur=echec)
            return
        raise ValueError('Action de capture invalide.')
    except (ValueError, TypeError):
        echec(None)
