"""Liaison native Chromium : canal local AES-GCM, secret DPAPI et validation des origines."""
from __future__ import annotations

import ctypes
import os
import re
import secrets
import select
import socket
import socketserver
import struct
import sys
import threading
import time
from pathlib import Path
from queue import Queue
from urllib.parse import urlsplit
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from vaultsafe.config import obtenir_dossier_donnees
from vaultsafe.operations_fichiers import ecrire_atomique
from vaultsafe.protections_windows import dpapi
from vaultsafe.securite_coffre import decoder_json, effacer_cle, encoder_json
from vaultsafe.windows_local import executable_courant

HOTE = 'org.vaultsafe.local'
MAX_MESSAGE = 512 * 1024
AAD_REQUETE = b'VaultSafe-liaison-requete-v1'
AAD_REPONSE = b'VaultSafe-liaison-reponse-v1'


def origine_web(adresse):
    if not isinstance(adresse, str) or len(adresse) > 8192 or re.search(r'[\x00-\x20\\]', adresse):
        raise ValueError('Adresse du navigateur invalide.')
    url = urlsplit(adresse)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username is not None or url.password is not None:
        raise ValueError('Adresse du navigateur invalide.')
    # Un point final crée une origine navigateur distincte, même si DNS résout le même serveur.
    hote = url.hostname.encode('idna').decode('ascii').lower()
    if url.scheme == 'http' and hote not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Le remplissage navigateur exige HTTPS.')
    port = url.port or (443 if url.scheme == 'https' else 80)
    return url.scheme, hote, port


def sites_identiques(site, adresse):
    try:
        site = site if '://' in site else 'https://' + site
        return origine_web(site) == origine_web(adresse)
    except (ValueError, UnicodeError):
        return False


def valider_ids(texte):
    ids = list(dict.fromkeys(p.strip() for p in texte.split(',') if p.strip()))
    if not 1 <= len(ids) <= 10 or any(re.fullmatch('[a-p]{32}', p) is None for p in ids):
        raise ValueError('Saisissez l’identifiant de l’extension (32 lettres a à p). Plusieurs identifiants : virgules.')
    return ids


def ids_hote_associe():
    manifest = obtenir_dossier_donnees() / 'native-host.json'
    try:
        if manifest.is_symlink() or manifest.stat().st_size > 4096:
            return ''
        data = decoder_json(manifest.read_bytes())
        if data['name'] != HOTE or data['type'] != 'stdio' or Path(data['path']).resolve() != executable_courant().resolve():
            return ''
        origines = data['allowed_origins']
        if not isinstance(origines, list) or any(not isinstance(o, str) or re.fullmatch('chrome-extension://[a-p]{32}/', o) is None for o in origines):
            return ''
        return ','.join(valider_ids(','.join(o[19:-1] for o in origines)))
    except (OSError, ValueError, KeyError, TypeError):
        return ''


def installer_hote(texte, dossier=None, executable=None, registre=True):
    ids = valider_ids(texte)
    executable = executable_courant() if executable is None else Path(executable).resolve()
    if not executable.is_file() or executable.suffix.lower() != '.exe':
        raise ValueError('Construisez l’exécutable VaultSafe avant d’associer le navigateur.')
    dossier = obtenir_dossier_donnees() if dossier is None else Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    manifest = dossier / 'native-host.json'
    data = {'name': HOTE, 'description': 'VaultSafe · coffre Windows local', 'path': str(executable),
            'type': 'stdio', 'allowed_origins': ['chrome-extension://' + id_ + '/' for id_ in ids]}
    ecrire_atomique(manifest, encoder_json(data))
    if registre:
        import winreg
        for navigateur in (r'Software\Google\Chrome', r'Software\Microsoft\Edge'):
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, navigateur + '\\NativeMessagingHosts\\' + HOTE) as cle:
                winreg.SetValueEx(cle, '', 0, winreg.REG_SZ, str(manifest))
    return data


def desinstaller_hote():
    import winreg
    for navigateur in (r'Software\Google\Chrome', r'Software\Microsoft\Edge'):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, navigateur + '\\NativeMessagingHosts\\' + HOTE)
        except FileNotFoundError:
            pass
    (obtenir_dossier_donnees() / 'native-host.json').unlink(missing_ok=True)


def _lire_exact(flux, longueur):
    morceaux, lu = [], 0
    while lu < longueur:
        partie = flux.read(longueur - lu)
        if not partie:
            raise ValueError('Liaison interrompue.')
        morceaux.append(partie)
        lu += len(partie)
    return b''.join(morceaux)


def lire_message(flux):
    debut = flux.read(4)
    if not debut:
        return None
    if len(debut) < 4:
        debut += _lire_exact(flux, 4 - len(debut))
    longueur = struct.unpack('<I', debut)[0]
    if not 1 <= longueur <= MAX_MESSAGE:
        raise ValueError('Message navigateur trop volumineux.')
    return decoder_json(_lire_exact(flux, longueur))


def ecrire_message(flux, valeur):
    message = encoder_json(valeur)
    if len(message) > MAX_MESSAGE:
        raise ValueError('Message navigateur trop volumineux.')
    paquet = struct.pack('<I', len(message)) + message
    ecrits = 0
    while ecrits < len(paquet):
        nombre = flux.write(paquet[ecrits:])
        if not nombre:
            raise ValueError('Liaison interrompue.')
        ecrits += nombre
    flux.flush()


class _Serveur(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False
    block_on_close = False

    def __init__(self, liaison):
        self.liaison = liaison
        self.places = threading.BoundedSemaphore(8)
        super().__init__(('127.0.0.1', 0), _Connexion)
        self.reveil, self.signal_reveil = socket.socketpair()
        self.termine = threading.Event()

    def serve_forever(self, poll_interval=None):
        try:
            while self.liaison.actif:
                prets, _, _ = select.select([self.socket, self.reveil], [], [])
                if self.reveil in prets:
                    break
                if self.socket in prets and self.liaison.actif:
                    self._handle_request_noblock()
        finally:
            self.termine.set()

    def shutdown(self):
        self.signal_reveil.send(b'X')
        self.termine.wait(3)

    def server_close(self):
        super().server_close()
        if hasattr(self, 'reveil'):
            self.reveil.close()
            self.signal_reveil.close()

    def verify_request(self, request, client_address):
        return client_address[0] == '127.0.0.1' and self.places.acquire(blocking=False)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.places.release()

    def handle_error(self, request, client_address):
        # Aucun traceback ou message contenant des données du navigateur.
        pass


class _Connexion(socketserver.StreamRequestHandler):
    def handle(self):
        liaison = self.server.liaison
        reponse = None
        self.request.settimeout(3)
        try:
            longueur = struct.unpack('<I', _lire_exact(self.rfile, 4))[0]
            if not 28 <= longueur <= MAX_MESSAGE + 28:
                return
            paquet = _lire_exact(self.rfile, longueur)
            nonce = paquet[:12]
            with liaison.mutex:
                if not liaison.actif:
                    return
                demande = decoder_json(AESGCM(liaison.cle).decrypt(nonce, paquet[12:], AAD_REQUETE))
                if (set(demande) != {'appelant', 'id', 'expiration', 'contenu'}
                        or demande['appelant'] not in liaison.origines
                        or not isinstance(demande['id'], str) or len(demande['id']) != 36
                        or type(demande['expiration']) not in (int, float)
                        or not time.time() < demande['expiration'] <= time.time() + 65
                        or not isinstance(demande['contenu'], dict)):
                    return
                liaison.vues = {k: v for k, v in liaison.vues.items() if v > time.time()}
                if demande['id'] in liaison.vues or len(liaison.vues) >= 256:
                    return
                liaison.vues[demande['id']] = demande['expiration']
                generation = liaison.generation
            reponse = Queue(maxsize=1)
            with liaison.mutex:
                if not liaison.actif:
                    return
                liaison.attentes.add(reponse)
            if liaison.notifier is None:
                liaison.evenements.put((demande, reponse), timeout=1)
            else:
                liaison.notifier((demande, reponse))
            resultat = reponse.get(timeout=55)
            with liaison.mutex:
                if not liaison.actif or demande['expiration'] <= time.time():
                    return
                if generation != liaison.generation:
                    resultat = {'ok': False, 'erreur': 'Le coffre est verrouillé.'}
                nouveau_nonce = secrets.token_bytes(12)
                chiffre = AESGCM(liaison.cle).encrypt(nouveau_nonce, encoder_json(resultat), AAD_REPONSE + nonce)
                paquet = nouveau_nonce + chiffre
                self.wfile.write(struct.pack('<I', len(paquet)) + paquet)
                self.wfile.flush()
        except Exception:
            # Échec fermé ; les requêtes non authentifiées n'atteignent jamais l'interface.
            return
        finally:
            with liaison.mutex:
                liaison.attentes.discard(reponse)


class LiaisonLocale:
    def __init__(self, ids, dossier=None, notifier=None):
        self.origines = {'chrome-extension://' + id_ + '/' for id_ in valider_ids(ids)}
        self.cle = bytearray(secrets.token_bytes(32))
        self.actif = True
        self.generation = 0
        self.fermee = False
        self.mutex = threading.RLock()
        self.vues = {}
        self.attentes = set()
        self.evenements = Queue(maxsize=16)
        self.notifier = notifier
        self.serveur = _Serveur(self)
        dossier = obtenir_dossier_donnees() if dossier is None else Path(dossier)
        dossier.mkdir(parents=True, exist_ok=True)
        self.configuration = dossier / ('liaison-' + str(os.getpid()) + '.dat')
        config = {'port': self.serveur.server_address[1], 'cle': self.cle.hex(),
                  'origines': sorted(self.origines), 'pid': os.getpid()}
        try:
            ecrire_atomique(self.configuration, dpapi(encoder_json(config)))
            self.fil = threading.Thread(target=self.serveur.serve_forever, kwargs={'poll_interval': 0.1},
                                        daemon=True, name='VaultSafeNavigateur')
            self.fil.start()
        except BaseException:
            self.actif = False
            effacer_cle(self.cle)
            self.serveur.server_close()
            self.configuration.unlink(missing_ok=True)
            raise

    def annuler_attentes(self):
        # L'état verrouillé reste consultable, sans réponse secrète en attente.
        with self.mutex:
            self.generation += 1
            for reponse in self.attentes:
                try:
                    reponse.put_nowait({'ok': False, 'erreur': 'Le coffre est verrouillé.'})
                except Exception:
                    pass

    def invalider(self):
        with self.mutex:
            self.actif = False
            effacer_cle(self.cle)
            self.configuration.unlink(missing_ok=True)
            for reponse in self.attentes:
                try:
                    reponse.put_nowait({'ok': False, 'erreur': 'Le coffre est verrouillé.'})
                except Exception:
                    pass

    def arreter(self):
        with self.mutex:
            if self.fermee:
                return
            self.fermee = True
        self.invalider()
        self.serveur.shutdown()
        self.serveur.server_close()
        while not self.evenements.empty():
            try:
                _, reponse = self.evenements.get_nowait()
                reponse.put_nowait({'ok': False, 'erreur': 'Le coffre est verrouillé.'})
            except Exception:
                break


def dossier_hote(appelant):
    """Retrouver le profil associé, même pour le raccourci développement.

    Chromium lance le même EXE sans --developpement : le manifeste enregistré
    fournit le dossier, après contrôle de l'EXE et de l'origine appelante.
    """
    if os.environ.get('VAULTSAFE_DATA_DIR') or sys.platform != 'win32':
        return obtenir_dossier_donnees()
    import winreg
    profils = set()
    for navigateur in (r'Software\Google\Chrome', r'Software\Microsoft\Edge'):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, navigateur + '\\NativeMessagingHosts\\' + HOTE) as cle:
                chemin, type_ = winreg.QueryValueEx(cle, '')
            if type_ != winreg.REG_SZ or not isinstance(chemin, str):
                continue
            manifest = Path(chemin)
            if not manifest.is_absolute() or manifest.is_symlink() or not 1 <= manifest.stat().st_size <= 4096:
                continue
            data = decoder_json(manifest.read_bytes())
            origines = data.get('allowed_origins')
            if (data.get('name') == HOTE and data.get('type') == 'stdio'
                    and Path(data['path']).resolve() == executable_courant().resolve()
                    and isinstance(origines, list) and appelant in origines
                    and all(isinstance(o, str) and re.fullmatch(r'chrome-extension://[a-p]{32}/', o) for o in origines)):
                profils.add(manifest.resolve().parent)
        except (OSError, ValueError, TypeError, KeyError):
            continue
    if len(profils) > 1:
        raise ValueError('Plusieurs profils sont associés. Associez de nouveau l’extension au coffre souhaité.')
    return next(iter(profils)) if profils else obtenir_dossier_donnees()


def appeler_application(appelant, contenu, dossier=None):
    appelant = appelant.rstrip('/') + '/'
    if re.fullmatch(r'chrome-extension://[a-p]{32}/', appelant) is None:
        return {'ok': False, 'erreur': 'Extension non autorisée.'}
    try:
        dossier = dossier_hote(appelant) if dossier is None else Path(dossier)
    except ValueError as erreur:
        return {'ok': False, 'erreur': str(erreur)}
    candidats = sorted(dossier.glob('liaison-*.dat'), key=lambda p: p.stat().st_mtime, reverse=True)
    for fichier in candidats[:8]:
        try:
            if fichier.is_symlink() or fichier.stat().st_size > 8192:
                continue
            config = decoder_json(dpapi(fichier.read_bytes(), dechiffrer=True))
            if (set(config) != {'port', 'cle', 'origines', 'pid'} or appelant not in config['origines']
                    or type(config['port']) is not int or not 1 <= config['port'] <= 65535
                    or len(config['cle']) != 64):
                continue
            cle = bytearray.fromhex(config['cle'])
            try:
                demande = {'appelant': appelant, 'id': str(uuid4()), 'expiration': time.time() + 60,
                           'contenu': contenu}
                nonce = secrets.token_bytes(12)
                paquet = nonce + AESGCM(cle).encrypt(nonce, encoder_json(demande), AAD_REQUETE)
                if len(paquet) > MAX_MESSAGE + 28:
                    raise ValueError('Message trop volumineux.')
                with socket.create_connection(('127.0.0.1', config['port']), timeout=3) as connexion:
                    connexion.settimeout(58)
                    with connexion.makefile('rwb', buffering=0) as flux:
                        connexion.sendall(struct.pack('<I', len(paquet)) + paquet)
                        longueur = struct.unpack('<I', _lire_exact(flux, 4))[0]
                        if not 28 <= longueur <= MAX_MESSAGE + 28:
                            raise ValueError('Réponse invalide.')
                        resultat = _lire_exact(flux, longueur)
                        return decoder_json(AESGCM(cle).decrypt(resultat[:12], resultat[12:], AAD_REPONSE + nonce))
            finally:
                effacer_cle(cle)
        except (OSError, ValueError, InvalidTag, TypeError, KeyError):
            continue
    if contenu == {'action': 'open'}:
        # Action explicite, chemin du programme courant, aucun shell.
        import subprocess
        commande = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, str(Path(__file__).resolve().parents[1] / 'main.py')]
        environnement = dict(os.environ, VAULTSAFE_DATA_DIR=str(dossier))
        subprocess.Popen(commande, cwd=Path(commande[-1]).parent, env=environnement,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return {'ok': True, 'ouvert': False, 'message': 'VaultSafe démarre. Réessayez après son ouverture.'}
    return {'ok': False, 'erreur': 'Ouvrez le coffre dans VaultSafe et associez cette extension dans Paramètres.'}


def _flux_windows(numero, mode):
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.DuplicateHandle.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
                                      ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.DuplicateHandle.restype = wintypes.BOOL
    handle = kernel.GetStdHandle(ctypes.c_uint(numero).value)
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise ValueError('Canal natif indisponible.')
    copie = wintypes.HANDLE()
    processus = kernel.GetCurrentProcess()
    if not kernel.DuplicateHandle(processus, handle, processus, ctypes.byref(copie), 0, False, 2):
        raise ValueError('Canal natif indisponible.')
    descripteur = msvcrt.open_osfhandle(copie.value, os.O_BINARY | (os.O_RDONLY if mode == 'rb' else os.O_WRONLY))
    return os.fdopen(descripteur, mode, buffering=0)


def executer_hote(appelant):
    entree = sys.stdin.buffer if sys.stdin is not None else _flux_windows(-10, 'rb')
    sortie = sys.stdout.buffer if sys.stdout is not None else _flux_windows(-11, 'wb')
    try:
        while True:
            demande = lire_message(entree)
            if demande is None:
                return
            resultat = appeler_application(appelant, demande)
            ecrire_message(sortie, resultat)
    except (OSError, ValueError):
        return
