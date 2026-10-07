"""Demandes Chromium : origine exacte, confirmation locale et session fraîche."""
import time
from vaultsafe.ui.composants import message


def traiter(app, evenement):
    from vaultsafe.liaison_navigateur import origine_web, sites_identiques
    from vaultsafe.sites import presenter
    demande, reponse = evenement
    generation = app.taches.generation
    contenu = demande['contenu']
    action = contenu.get('action')
    def livrer(resultat, secret=True):
        if demande['expiration'] <= time.time() or (secret and (generation != app.taches.generation or not app.ouvert)):
            resultat = {'ok': False, 'erreur': 'Coffre verrouillé ou demande expirée.'}
        try:
            reponse.put_nowait(resultat)
        except Exception:
            pass
    if demande['expiration'] <= time.time():
        livrer({'ok': False, 'erreur': 'Demande expirée.'}, False)
        return
    if isinstance(action, str) and action.startswith('capture_'):
        from vaultsafe.ui.capture_navigateur import traiter as traiter_capture
        traiter_capture(app, demande, livrer)
        return
    if action in ('status', 'open') and set(contenu) == {'action'}:
        if action == 'open':
            app.reafficher()
        def fini(expire):
            def etat():
                app.definir_confiance(expire)
                livrer({'ok': True, 'ouvert': app.ouvert, 'confiance': expire is not None, 'theme': app.theme,
                        'message': '' if app.ouvert else 'Déverrouillez VaultSafe dans la fenêtre Windows.'}, False)
            # Seul le clic explicite Ouvrir utilise l'autorisation locale.
            # Une consultation d'état ne doit jamais annuler un verrouillage.
            if (action == 'open' and expire is not None and not app.ouvert
                    and demande['expiration'] > time.time() and generation == app.taches.generation):
                if app.connecter_appareil(etat, etat):
                    return
            etat()
        app.taches.soumettre(app.appareil.etat, fini,
            lambda _: livrer({'ok': True, 'ouvert': app.ouvert, 'confiance': False}, False))
        return
    if not app.ouvert:
        livrer({'ok': False, 'erreur': 'Coffre verrouillé.'})
        return
    try:
        if action == 'trust' and set(contenu) == {'action', 'actif'} and type(contenu['actif']) is bool:
            actif = contenu['actif']
            app.reafficher()
            if actif and not message(app, 'Appareil de confiance', 'Autoriser l’ouverture de ce coffre avec ce compte Windows sur cet appareil pendant 30 jours ?', True):
                livrer({'ok': False, 'erreur': 'Autorisation refusée.'})
                return
            def travail():
                if generation != app.taches.generation or not app.ouvert or demande['expiration'] <= time.time():
                    raise ValueError('Session expirée.')
                return app.appareil.autoriser() if actif else app.appareil.revoquer()
            def fini(_):
                app.definir_confiance(_ if actif else None)
                page = app.autres_pages.get('parametres')
                if page:
                    page.actualiser_appareil()
                livrer({'ok': True, 'confiance': actif})
            app.executer(travail, fini,
                         lambda _: livrer({'ok': False, 'erreur': 'Autorisation indisponible.'}))
            return
        if action == 'import' and set(contenu) == {'action'}:
            from vaultsafe.ui.outils import importer
            app.reafficher()
            livrer({'ok': True, 'message': 'Choisissez votre fichier dans VaultSafe.'})
            importer(app)
            return
        if action not in ('list', 'fill', 'save'):
            raise ValueError('Action non prise en charge.')
        attendus = {'action', 'url'} | ({'id'} if action == 'fill' else
            {'titre', 'utilisateur', 'mot_de_passe', 'dossier', 'id'} if action == 'save' else
            set())
        if set(contenu) != attendus:
            raise ValueError('Message invalide.')
        url = contenu['url']
        scheme, hote, port = origine_web(url)
        cible = '[' + hote + ']' if ':' in hote else hote
        origine = f'{scheme}://{cible}' + (f':{port}' if port != (443 if scheme == 'https' else 80) else '')
        if action == 'list':
            base = app.base
            def travail():
                vue = base.lire_vue()
                return ([f for f in vue['fiches'] if f['type'] == 'connexion' and sites_identiques(f['site'], url)][:100], vue['dossiers'])
            def fini(resultat):
                fiches, dossiers = resultat
                noms = {d['id']: d['nom'] for d in dossiers}
                retour = []
                image = ''
                moteur = app.icones_sites.moteur
                moteur.apprendre(app.vue['fiches'])
                for fiche in fiches:
                    public = dict(fiche, **presenter(fiche, moteur))
                    retour.append({'id': fiche['id'], 'titre': public['_libelle'][:200],
                        'utilisateur': fiche['nom_utilisateur'][:150], 'dossier': fiche['dossier'],
                        'dossier_nom': noms.get(fiche['dossier'], 'Sans dossier')})
                service = presenter({'site': url, 'titre': '', 'id': ''}, moteur)
                public_icone = dict(site=url, **service)
                image = app.icones_sites.pour_extension(public_icone, app.preferences.get('icones_reseau', 'non') == 'oui')
                livrer({'ok': True, 'fiches': retour, 'dossiers': dossiers, 'service': service['_site_nom'],
                        'icone': image, 'icone_en_attente': not image and bool(app.icones_sites.attentes)})
            app.executer(travail, fini, lambda _: livrer({'ok': False, 'erreur': 'Lecture refusée.'}))
            return
        if action == 'fill':
            if not isinstance(contenu['id'], str):
                raise ValueError('Fiche invalide.')
            candidat = next((f for f in app.vue['fiches'] if f['id'] == contenu['id']), None)
            if not candidat or candidat['type'] != 'connexion' or not sites_identiques(candidat['site'], url):
                raise ValueError('La fiche ne correspond pas au site.')
            app.reafficher()
            if not message(app, 'Autoriser le remplissage', f'Envoyer « {candidat["titre"][:100]} » au site {origine} ?', True):
                livrer({'ok': False, 'erreur': 'Remplissage refusé.'})
                return
            gestion = app.identifiants
            def travail():
                if generation != app.taches.generation or demande['expiration'] <= time.time():
                    raise ValueError('Autorisation expirée.')
                fiche = gestion.afficher_identifiant(contenu['id'])
                if fiche.type != 'connexion' or not sites_identiques(fiche.site, url):
                    raise ValueError('La fiche a changé.')
                return {'ok': True, 'utilisateur': fiche.nom_utilisateur, 'mot_de_passe': fiche.mot_de_passe}
            app.executer(travail, livrer, lambda _: livrer({'ok': False, 'erreur': 'Remplissage refusé.'}))
            return
        for cle in ('titre', 'utilisateur', 'mot_de_passe', 'dossier', 'id'):
            if not isinstance(contenu[cle], str) or len(contenu[cle]) > (100_000 if cle == 'mot_de_passe' else 200):
                raise ValueError('Champ invalide.')
        if not contenu['titre'].strip() or not contenu['mot_de_passe']:
            raise ValueError('Fiche incomplète.')
        identifiant = contenu['id']
        dossier = contenu['dossier']
        if dossier and not any(d['id'] == dossier for d in app.vue['dossiers']):
            raise ValueError('Dossier absent.')
        candidat = next((f for f in app.vue['fiches'] if f['id'] == identifiant), None) if identifiant else None
        if identifiant and (not candidat or candidat['type'] != 'connexion' or not sites_identiques(candidat['site'], url)):
            raise ValueError('Mise à jour hors origine.')
        app.reafficher()
        verbe = 'Mettre à jour' if identifiant else 'Créer'
        if not message(app, 'Enregistrer', f'{verbe} « {contenu["titre"][:100]} » pour {origine} ?', True):
            livrer({'ok': False, 'erreur': 'Enregistrement refusé.'})
            return
        gestion = app.identifiants
        def travail():
            if generation != app.taches.generation or demande['expiration'] <= time.time():
                raise ValueError('Autorisation expirée.')
            valeurs = dict(titre=contenu['titre'], nom_utilisateur=contenu['utilisateur'],
                          mot_de_passe=contenu['mot_de_passe'], dossier=dossier)
            if identifiant:
                fiche = gestion.afficher_identifiant(identifiant)
                if fiche.type != 'connexion' or not sites_identiques(fiche.site, url):
                    raise ValueError('La fiche a changé.')
                gestion.modifier_identifiant(identifiant, **valeurs)
            else:
                gestion.ajouter_identifiant(**valeurs, site=url)
        app.mutation(travail, lambda _: livrer({'ok': True}),
                     erreur=lambda _: livrer({'ok': False, 'erreur': 'Enregistrement refusé.'}))
    except (ValueError, OSError, UnicodeError):
        livrer({'ok': False, 'erreur': 'Demande refusée.'})
