"""Capture Chromium : secret temporaire en RAM, validation et écriture chiffrée."""
import re
import secrets
import threading
import time
from urllib.parse import unquote, urlsplit, urlunsplit

from vaultsafe.liaison_navigateur import origine_web, sites_identiques
from vaultsafe.parametres import Parametres


def url_connexion(adresse):
    scheme, hote, port = origine_web(adresse)
    netloc = '[' + hote + ']' if ':' in hote else hote
    if port != (443 if scheme == 'https' else 80):
        netloc += ':' + str(port)
    morceaux, precedent = [], ''
    for segment in urlsplit(adresse).path.split('/'):
        clair = unquote(segment).split(';', 1)[0]
        if (len('/'.join(morceaux)) > 512 or '@' in clair or re.search(r'[\x00-\x20<>\\]', clair)
                or re.fullmatch(r'[0-9a-fA-F]{24,}|[A-Za-z0-9_=-]{40,}', clair)
                or clair.startswith('eyJ') or precedent in ('token', 'code', 'ticket', 'session', 'assertion')):
            break
        morceaux.append(segment.split(';', 1)[0])
        precedent = clair.lower()
    return urlunsplit((scheme, netloc, '/'.join(morceaux) or '/', '', '')), scheme + '://' + netloc, hote


class CapturesComptes:
    DUREE, MAXIMUM = 120, 8

    def __init__(self, horloge=time.monotonic):
        self.horloge, self.mutex, self.attentes = horloge, threading.RLock(), {}
        self.politique = {'mode': 'proposition', 'exclus': []}

    def _effacer(self, token):
        r = self.attentes.pop(token, None)
        if r:
            r['mot_de_passe'] = r['utilisateur'] = ''

    def purger(self):
        with self.mutex:
            for token in list(self.attentes):
                if self.attentes[token]['expiration'] <= self.horloge():
                    self._effacer(token)

    def vider(self):
        with self.mutex:
            for token in list(self.attentes):
                self._effacer(token)

    def options(self, base=None):
        with self.mutex:
            if base and base.coffre_ouvert:
                p = Parametres.pour_interface(base.lire_preferences())
                self.politique = {'mode': p.get('capture_mode', 'proposition'), 'exclus': p.get('capture_exclus', '').splitlines()}
            return dict(self.politique, exclus=list(self.politique['exclus']))

    def _record(self, base, appelant, token):
        self.purger()
        r = self.attentes.get(token)
        if not r or r['appelant'] != appelant or base is None or r['coffre'] != str(base.chemin):
            raise ValueError('Proposition expirée. Soumettez de nouveau le formulaire.')
        return r

    def creer(self, base, appelant, contenu):
        attendus = {'action', 'url', 'utilisateur', 'mot_de_passe', 'type'}
        if set(contenu) != attendus or any(not isinstance(contenu[k], str) for k in attendus):
            raise ValueError('Compte soumis invalide.')
        if (len(contenu['utilisateur']) > 200 or not 1 <= len(contenu['mot_de_passe']) <= 4096
                or contenu['type'] not in ('connexion', 'inscription', 'changement')):
            raise ValueError('Compte soumis invalide.')
        url, origine, domaine = url_connexion(contenu['url'])
        with self.mutex:
            self.purger()
            options = self.options(base)
            if options['mode'] == 'desactive' or origine in options['exclus']:
                return {'ok': True, 'etat': 'ignore', 'options': options}
            if base is None:
                raise ValueError('VaultSafe démarre. Réessayez après son ouverture.')
            if len(self.attentes) >= self.MAXIMUM:
                self._effacer(next(iter(self.attentes)))
            token = secrets.token_urlsafe(24)
            self.attentes[token] = {'appelant': appelant, 'coffre': str(base.chemin), 'url': url, 'origine': origine,
                'domaine': domaine, 'type': contenu['type'], 'utilisateur': contenu['utilisateur'].strip(),
                'mot_de_passe': contenu['mot_de_passe'], 'expiration': self.horloge() + self.DUREE, 'resultat': 'incertain'}
            try:
                return dict(self.decrire(base, appelant, token), token=token, options=options)
            except Exception:
                self._effacer(token)
                raise

    @staticmethod
    def _candidats(base, r, nom):
        # Autorisation humaine explicite du 5/10 : comparaison LOCALE pour éviter les doublons.
        # Une lecture au travailleur ; les anciens mots de passe ne quittent jamais le coffre local.
        return [f for f in base._lire()['identifiants'] if f['type'] == 'connexion'
                and sites_identiques(f['site'], r['origine']) and (f['nom_utilisateur'] == nom
                    or r['type'] == 'changement' and not r['utilisateur'] and not nom)][:100]

    @staticmethod
    def _egal(a, b):
        return secrets.compare_digest(a.encode('utf-8'), b.encode('utf-8'))

    def decrire(self, base, appelant, token, secret=False):
        with self.mutex:
            r = self._record(base, appelant, token)
            if not base.coffre_ouvert:
                return {'ok': True, 'etat': 'verrouille', 'origine': r['origine'], 'url': r['url']}
            p = self.options(base)
            if p['mode'] == 'desactive' or r['origine'] in p['exclus']:
                self._effacer(token)
                return {'ok': True, 'etat': 'ignore'}
            with base._mutex:
                candidats = self._candidats(base, r, r['utilisateur'])
                if (r['utilisateur'] or len(candidats) == 1) and any(self._egal(f['mot_de_passe'], r['mot_de_passe']) for f in candidats):
                    self._effacer(token)
                    return {'ok': True, 'etat': 'identique', 'texte': 'Compte déjà présent dans VaultSafe.'}
                vue = base.lire_vue()
                retour = {'ok': True, 'etat': 'proposition', 'origine': r['origine'], 'url': r['url'],
                    'utilisateur': r['utilisateur'] or (candidats[0]['nom_utilisateur'] if len(candidats) == 1 else ''), 'type': r['type'], 'resultat': r['resultat'],
                    'automatique': p['mode'] == 'automatique' and not candidats and bool(r['utilisateur']) and r['type'] != 'changement',
                    'candidats': [{'id': f['id'], 'titre': f['titre'], 'utilisateur': f['nom_utilisateur']} for f in candidats],
                    'dossier': candidats[0]['dossier'] if len(candidats) == 1 else '',
                    'dossiers': [{'id': d['id'], 'nom': d['nom']} for d in vue['dossiers']]}
                if secret:
                    retour['mot_de_passe'] = r['mot_de_passe']
                return retour

    def resultat(self, base, gestion, appelant, token, resultat):
        if resultat not in ('incertain', 'echec'):
            raise ValueError('Résultat invalide.')
        with self.mutex:
            r = self._record(base, appelant, token)
            r['resultat'] = resultat
            retour = self.decrire(base, appelant, token)
            if retour.get('automatique') and resultat != 'echec':
                return self.enregistrer(base, gestion, appelant, token,
                    {'utilisateur': r['utilisateur'], 'mot_de_passe': r['mot_de_passe'], 'dossier': '', 'id': ''}, automatique=True)
            return retour

    def enregistrer(self, base, gestion, appelant, token, valeurs, automatique=False):
        if (set(valeurs) != {'utilisateur', 'mot_de_passe', 'dossier', 'id'} or any(not isinstance(v, str) for v in valeurs.values())
                or len(valeurs['utilisateur']) > 200 or not 1 <= len(valeurs['mot_de_passe']) <= 4096
                or len(valeurs['dossier']) > 36 or len(valeurs['id']) > 36):
            raise ValueError('Compte invalide.')
        with self.mutex:
            r = self._record(base, appelant, token)
            base.exiger_ouverture()
            p = self.options(base)
            if p['mode'] == 'desactive' or r['origine'] in p['exclus']:
                raise ValueError('Détection désactivée pour ce site.')
            with base._mutex:
                nom, mot = valeurs['utilisateur'].strip(), valeurs['mot_de_passe']
                if r['type'] == 'changement' and not nom:
                    possibles = self._candidats(base, r, '')
                    choisi = next((f for f in possibles if f['id'] == valeurs['id']), None) if valeurs['id'] else (possibles[0] if len(possibles) == 1 else None)
                    if choisi is None:
                        raise ValueError('Choisissez le compte à mettre à jour ou renseignez son identifiant.')
                    nom = choisi['nom_utilisateur']
                candidats = self._candidats(base, r, nom)
                if any(self._egal(f['mot_de_passe'], mot) for f in candidats):
                    self._effacer(token)
                    return {'ok': True, 'etat': 'identique', 'texte': 'Compte déjà présent dans VaultSafe.'}
                # Aucun écrasement automatique, même si le site paraît accepter la connexion.
                if automatique and (p['mode'] != 'automatique' or candidats or not nom
                        or r['type'] == 'changement' or r['resultat'] == 'echec'):
                    return self.decrire(base, appelant, token)
                cible = None
                if valeurs['id']:
                    cible = next((f for f in self._candidats(base, r, r['utilisateur']) if f['id'] == valeurs['id']), None)
                    if cible is None:
                        raise ValueError('Le compte à mettre à jour a changé.')
                    if any(f['id'] != cible['id'] for f in candidats):
                        raise ValueError('Cet identifiant appartient déjà à un autre compte de cette origine.')
                elif len(candidats) == 1:
                    cible = candidats[0]
                elif candidats:
                    raise ValueError('Choisissez le compte à mettre à jour.')
                dossier = valeurs['dossier']
                if dossier and not any(d['id'] == dossier for d in base.lire_vue()['dossiers']):
                    raise ValueError('Dossier introuvable.')
                if cible:
                    gestion.modifier_identifiant(cible['id'], nom_utilisateur=nom, mot_de_passe=mot,
                        dossier=dossier if dossier else cible['dossier'])
                    etat, texte = 'mis_a_jour', 'Compte mis à jour dans VaultSafe.'
                else:
                    from vaultsafe.services import normaliser
                    gestion.ajouter_identifiant(titre=normaliser(r['origine']).nom, site=r['url'],
                        nom_utilisateur=nom, mot_de_passe=mot, dossier=dossier)
                    etat, texte = 'enregistre', 'Compte enregistré dans VaultSafe.'
                self._effacer(token)
                return {'ok': True, 'etat': etat, 'texte': texte}

    def ignorer(self, appelant, token):
        with self.mutex:
            r = self.attentes.get(token)
            if r and r['appelant'] == appelant:
                self._effacer(token)
            return {'ok': True, 'etat': 'ignore'}
