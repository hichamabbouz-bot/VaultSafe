"""Projection de présentation : service, regroupement et identité graphique."""
from vaultsafe.domaines import domaine_site, suffixes as suffixes
from vaultsafe.services import MARQUES as MARQUES, MoteurServices, normaliser


def identifier_site(valeur):
    service = normaliser(valeur)
    return service.cle, service.nom, service.hote


def presenter(fiche, moteur=None):
    moteur = moteur or MoteurServices()
    source = normaliser(fiche.get('site', ''))
    service = moteur.pour_fiche(fiche)
    cle, nom, hote = service.cle, service.nom, source.hote
    choix = fiche.get('presentation', {})
    local = service.genre == 'reseau'
    if choix.get('equipement') and local:
        nom = choix['equipement'] + ' · ' + cle.split('://', 1)[1]
    titre = fiche.get('titre', '').strip()
    automatiques = {nom.casefold(), hote.casefold(), domaine_site(hote).casefold() if hote else ''}
    if source.application:
        automatiques.update({source.application.casefold(), 'android.' + source.candidat,
                             source.candidat, normaliser('https://' + source.candidat).nom.casefold()})
    # Un titre personnalisé reste un choix explicite ; aucun secret ni URL réécrit.
    libelle = choix.get('nom', '').strip() or (titre if titre and titre.casefold() not in automatiques else nom)
    if not cle:
        libelle = choix.get('nom', '').strip() or titre or 'Sans site'
    groupe = choix.get('groupe', '').strip()
    if groupe:
        cle, nom = 'manuel:' + groupe.casefold(), groupe
    if choix.get('separe'):
        cle = 'fiche:' + fiche['id']
    manuel = moteur.icones.get(service.logo, '')
    if choix.get('separe'):
        manuel = choix.get('icone', '') or manuel
    # Pour les appels unitaires hors projection complète, respecter l'image choisie.
    if not moteur.appris and choix.get('icone'):
        manuel = choix['icone']
    symbole = service.symbole if service.cle else {
        'note': 'note', 'carte': 'carte', 'identite': 'personne', 'licence': 'cle',
        'wifi': 'reglages', 'serveur': 'serveur'}.get(fiche.get('type'), 'cle')
    return {'_site_cle': cle, '_site_nom': nom, '_hote': hote, '_libelle': libelle,
            '_reseau': local, '_service_cle': service.cle, '_service_confiance': service.confiance,
            '_application': service.application, '_icone_cle': service.logo or cle,
            '_icone_origines': service.origines, '_icone_symbole': symbole,
            '_icone_manuelle': manuel}
