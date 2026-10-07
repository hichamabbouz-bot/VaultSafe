"""Autorisation locale DPAPI, liée au chemin et à l'enveloppe d'un seul coffre."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from vaultsafe.config import obtenir_dossier_donnees
from vaultsafe.operations_fichiers import ecrire_atomique
from vaultsafe.protections_windows import dpapi
from vaultsafe.securite_coffre import effacer_cle

DUREE = 30 * 24 * 60 * 60
MAX_JETON = 8192


def empreinte_machine():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Cryptography',
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as registre:
            identifiant = winreg.QueryValueEx(registre, 'MachineGuid')[0]
        if not isinstance(identifiant, str) or not identifiant:
            raise ValueError
        return hashlib.sha256(identifiant.encode('utf-8')).digest()
    except (OSError, ValueError) as erreur:
        raise ValueError('Identification de cet appareil indisponible.') from erreur


class AppareilConfiance:
    def __init__(self, base):
        self.base = base
        self.identite = hashlib.sha256(os.path.normcase(str(base.chemin)).encode('utf-8')).hexdigest()
        self.chemin = obtenir_dossier_donnees() / 'appareils' / (self.identite + '.dpapi')
        self.entropie = b'VaultSafe-appareil-confiance-v1:' + self.identite.encode('ascii')

    def _proteger(self, donnees, dechiffrer=False):
        return dpapi(donnees, dechiffrer, contexte=self.entropie + empreinte_machine())

    def _lire(self):
        if not self.chemin.is_file():
            return None
        try:
            if not 1 <= self.chemin.stat().st_size <= MAX_JETON:
                raise ValueError('Autorisation invalide.')
            donnees = json.loads(self._proteger(self.chemin.read_bytes(), True))
            if (not isinstance(donnees, dict) or set(donnees) != {'version', 'identite', 'contexte', 'cle', 'cree', 'expire'}
                    or type(donnees['version']) is not int or donnees['version'] != 1 or not isinstance(donnees['identite'], str)
                    or not hmac.compare_digest(donnees['identite'], self.identite)
                    or not isinstance(donnees['contexte'], str) or len(donnees['contexte']) != 64
                    or not isinstance(donnees['cle'], str) or len(donnees['cle']) != 64
                    or type(donnees['cree']) is not int or type(donnees['expire']) is not int
                    or not donnees['cree'] <= int(time.time()) < donnees['expire'] <= donnees['cree'] + DUREE
                    or not hmac.compare_digest(donnees['contexte'], self.base.contexte_appareil())):
                raise ValueError('Autorisation expirée.')
            bytes.fromhex(donnees['cle'])
            return donnees
        except (ValueError, OSError, KeyError, TypeError, UnicodeError):
            # Une autorisation invalide ne modifie jamais le fichier du coffre.
            try:
                self.revoquer()
            except OSError:
                pass
            return None

    def etat(self):
        donnees = self._lire()
        return donnees['expire'] if donnees else None

    def autoriser(self):
        contexte, cle = self.base.exporter_cle_appareil()
        try:
            maintenant = int(time.time())
            donnees = json.dumps(dict(version=1, identite=self.identite, contexte=contexte,
                cle=cle.hex(), cree=maintenant, expire=maintenant + DUREE), separators=(',', ':')).encode('utf-8')
            protege = self._proteger(donnees)
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            ecrire_atomique(self.chemin, protege)
            return maintenant + DUREE
        finally:
            effacer_cle(cle)

    def ouvrir(self):
        donnees = self._lire()
        if donnees is None:
            raise ValueError('Utilisez votre mot de passe maître pour autoriser cet appareil.')
        cle = bytearray.fromhex(donnees['cle'])
        try:
            self.base.ouvrir_appareil(cle, donnees['contexte'])
        except ValueError:
            self.revoquer()
            raise
        finally:
            effacer_cle(cle)

    def revoquer(self):
        self.chemin.unlink(missing_ok=True)
