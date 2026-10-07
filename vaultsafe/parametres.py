"""Préférences validées et enregistrées atomiquement dans le coffre chiffré."""
from pathlib import Path

from vaultsafe.connexion import Connexion
from vaultsafe.database import BaseDeDonnees


class Parametres:
    def __init__(self, base: BaseDeDonnees, connexion: Connexion):
        self.base, self.connexion = base, connexion

    def lire_parametre(self, nom, valeur_defaut):
        return self.base.lire_parametre(nom, valeur_defaut)

    def lire_lot(self):
        return self.base.lire_preferences()

    @staticmethod
    def pour_interface(preferences):
        """Ignore les anciens réglages invalides sans les effacer du coffre."""
        resultat = dict(preferences)
        for nom in ('theme', 'echelle', 'inactivite', 'inactivite_confiance', 'presse_papiers_secondes',
                    'backup_minutes', 'backup_retention', 'rappels', 'reduire_zone',
                    'demarrage_windows', 'notifications', 'icones_reseau', 'extension_ids', 'capture_mode', 'capture_exclus'):
            if nom in resultat:
                try:
                    resultat[nom] = Parametres.valider(nom, resultat[nom])
                except ValueError:
                    resultat.pop(nom)
        return resultat

    @staticmethod
    def valider(nom, valeur):
        if not isinstance(nom, str) or not isinstance(valeur, str) or len(nom) > 100 or len(valeur) > 4096:
            raise ValueError('Préférence invalide.')
        if nom == 'theme' and valeur not in ('light', 'dark'):
            raise ValueError('Thème non pris en charge.')
        if nom == 'capture_mode' and valeur not in ('proposition', 'automatique', 'desactive'):
            raise ValueError('Mode de capture invalide.')
        if nom == 'capture_exclus':
            from vaultsafe.liaison_navigateur import origine_web
            origines = []
            for adresse in valeur.replace(',', '\n').splitlines():
                adresse = adresse.strip()
                if not adresse:
                    continue
                if '://' not in adresse:
                    adresse = 'https://' + adresse
                scheme, hote, port = origine_web(adresse)
                origine = scheme + '://' + ('[' + hote + ']' if ':' in hote else hote)
                if port != (443 if scheme == 'https' else 80):
                    origine += ':' + str(port)
                if origine not in origines:
                    origines.append(origine)
            if len(origines) > 32:
                raise ValueError('Au maximum 32 origines exclues.')
            valeur = '\n'.join(origines)
        if nom in ('icones_reseau', 'reduire_zone', 'rappels', 'notifications', 'demarrage_windows') and valeur not in ('oui', 'non'):
            raise ValueError('Préférence invalide.')
        bornes = {'inactivite': (0, 60), 'inactivite_confiance': (0, 60), 'backup_minutes': (1, 1440), 'backup_retention': (1, 50),
                  'presse_papiers_secondes': (5, 120), 'echelle': (100, 200)}
        if nom in bornes:
            try:
                nombre = int(valeur)
            except ValueError as erreur:
                raise ValueError('Cette préférence doit être un nombre.') from erreur
            minimum, maximum = bornes[nom]
            if not minimum <= nombre <= maximum:
                raise ValueError(f'La valeur doit être comprise entre {minimum} et {maximum}.')
            valeur = str(nombre)
        if nom == 'backup_dossier' and valeur:
            chemin = Path(valeur).expanduser()
            if not chemin.is_absolute():
                raise ValueError('Choisissez un dossier de sauvegarde avec un chemin complet.')
            valeur = str(chemin.resolve())
        if nom == 'extension_ids' and valeur:
            from vaultsafe.liaison_navigateur import valider_ids
            valeur = ','.join(valider_ids(valeur))
        return valeur

    def enregistrer_parametre(self, nom, valeur):
        self.enregistrer_lot({nom: valeur})

    def enregistrer_lot(self, preferences):
        self.connexion.exiger_connexion()
        valeurs = {k: self.valider(k, v) for k, v in preferences.items()}
        self.base._modifier(lambda d: d['parametres'].update(valeurs))
