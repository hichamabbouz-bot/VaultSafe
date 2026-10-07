"""Images locales validées : import explicite et cache sans contenu actif."""
import base64
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, Signal, Qt, QTimer
from PySide6.QtGui import QImageReader
from vaultsafe.config import obtenir_dossier_donnees
from vaultsafe.operations_fichiers import ecrire_atomique

MAX_IMAGE = 512 * 1024
TAILLE_ICONE = 256
MIN_ICONE = 48
DELAI_REPRISE = 15 * 60


def identite_cache(origine):
    return hashlib.sha256(('service-3:' + origine).encode('utf-8')).hexdigest()


def image_validee(donnees):
    if not isinstance(donnees, bytes) or not 1 <= len(donnees) <= MAX_IMAGE:
        raise ValueError('Image invalide ou trop grande (512 Ko maximum).')
    if b'<svg' in donnees[:1024] or b':svg' in donnees[:1024]:
        from vaultsafe.images_svg import rasteriser_svg
        image = rasteriser_svg(donnees)
        sortie = QBuffer()
        sortie.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(sortie, 'PNG'):
            raise ValueError('Image illisible.')
        return image, bytes(sortie.data())
    tampon = QBuffer()
    tampon.setData(QByteArray(donnees))
    tampon.open(QIODevice.OpenModeFlag.ReadOnly)
    lecteur = QImageReader(tampon)
    lecteur.setAllocationLimit(16)
    format_ = bytes(lecteur.format()).lower()
    if format_ not in (b'png', b'jpeg', b'jpg', b'ico', b'webp'):
        raise ValueError('Utilisez une image PNG, JPEG, ICO ou WebP.')
    if format_ == b'ico':
        # Un ICO commence souvent par sa variante 16 px : choisir la plus
        # grande variante valide avant le décodage, sans agrandir l'original.
        meilleur, surface = 0, 0
        for i in range(min(32, max(1, lecteur.imageCount()))):
            if lecteur.jumpToImage(i):
                taille = lecteur.size()
                if 1 <= taille.width() <= 1024 and 1 <= taille.height() <= 1024:
                    if taille.width() * taille.height() > surface:
                        meilleur, surface = i, taille.width() * taille.height()
        lecteur.jumpToImage(meilleur)
    taille = lecteur.size()
    if not 1 <= taille.width() <= 1024 or not 1 <= taille.height() <= 1024:
        raise ValueError('Dimensions maximales : 1024 × 1024.')
    image = lecteur.read()
    if image.isNull():
        raise ValueError('Image illisible.')
    if max(image.width(), image.height()) > TAILLE_ICONE:
        image = image.scaled(TAILLE_ICONE, TAILLE_ICONE, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    sortie = QBuffer()
    sortie.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(sortie, 'PNG'):
        raise ValueError('Image illisible.')
    return image, bytes(sortie.data())


def installer_icone(source):
    with Path(source).open('rb') as fichier:
        _, png = image_validee(fichier.read(MAX_IMAGE + 1))
    identifiant = hashlib.sha256(png).hexdigest()
    chemin = obtenir_dossier_donnees() / 'icones-manuelles' / (identifiant + '.png')
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ecrire_atomique(chemin, png)
    return identifiant


class IconesSites(QObject):
    arrivee = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        from vaultsafe.services import MoteurServices
        self.moteur = MoteurServices()
        self.images, self.attentes = {}, {}
        self.reprises = {}
        self.actif, self.generation = True, 0
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='VaultSafeIcones')
        self.arrivee.connect(self.livrer)
        self.dossier = obtenir_dossier_donnees()
        self.identites_modifiees = False
        self.rafraichissement = QTimer(self)
        self.rafraichissement.setSingleShot(True)
        self.rafraichissement.timeout.connect(self.actualiser_identites)

    def obtenir(self, fiche, autorise=False):
        from vaultsafe.sites import presenter
        public = fiche if '_icone_cle' in fiche else dict(fiche, **presenter(fiche, self.moteur))
        manuel, origines = public.get('_icone_manuelle', ''), public.get('_icone_origines', ())
        if manuel and (len(manuel) != 64 or any(c not in '0123456789abcdef' for c in manuel)):
            return None
        identite = public.get('_icone_cle', '')
        cle = 'manuel:' + manuel if manuel else 'service:' + identite
        if not self.actif or (not manuel and (not identite or not origines)):
            return None
        if self.identites_modifiees and not self.rafraichissement.isActive():
            self.rafraichissement.start(120)
        if cle in self.images:
            if self.images[cle] is not None or not autorise or time.monotonic() < self.reprises.get(cle, 0):
                return self.images[cle]
            self.images.pop(cle, None)
            self.reprises.pop(cle, None)
        if cle in self.attentes or len(self.attentes) >= 8:
            return None
        cache = self.dossier / ('icones-manuelles' if manuel else 'icones-sites')
        fichier = cache / ((manuel or identite_cache(identite)) + '.png')
        # Migrer seulement l'ancien cache du domaine principal, de façon stable.
        origine = origines[0] if origines else ''
        anciens = [cache / (hashlib.sha256((prefixe + origine).encode()).hexdigest() + '.png')
                   for prefixe in ('qualite-2:', '')] if origine and not manuel else []
        if not autorise and not manuel and not any(p.is_file() for p in (fichier, *anciens)):
            return None
        generation = self.generation

        def travail():
            echec, etiquette = fichier.with_suffix('.absent'), fichier.with_suffix('.nom')
            ancienne_image, nom = None, ''
            try:
                if etiquette.stat().st_size <= 512:
                    data = json.loads(etiquette.read_text(encoding='utf-8'))
                    nom = data.get('nom', '') if isinstance(data, dict) else ''
            except (OSError, ValueError, RecursionError):
                pass
            for candidat in (fichier, *anciens):
                try:
                    with candidat.open('rb') as flux:
                        image = image_validee(flux.read(MAX_IMAGE + 1))[0]
                    if manuel or min(image.width(), image.height()) >= MIN_ICONE:
                        ancienne_image = image
                        if manuel or (candidat == fichier and time.time() - candidat.stat().st_mtime < 7 * 86400):
                            return ancienne_image, nom
                        break
                except (ValueError, OSError):
                    pass
            if manuel or not autorise or (echec.is_file() and time.time() - echec.stat().st_mtime < DELAI_REPRISE):
                return ancienne_image, nom
            from vaultsafe.telechargement_icones import trouver_identite
            def valide():
                return self.actif and generation == self.generation
            png, nom_lu = trouver_identite(origines, valide)
            if not valide():
                return None, ''
            cache.mkdir(parents=True, exist_ok=True)
            fichiers = []
            for p in cache.glob('*'):
                try:
                    if p.suffix in ('.png', '.absent', '.nom') and len(p.stem) == 64 and all(c in '0123456789abcdef' for c in p.stem) and p.is_file():
                        fichiers.append((p.stat().st_mtime, p))
                except OSError:
                    pass
            # 256 identités au plus ; variantes image/échec/nom restent groupées.
            identites = {}
            for date, p in fichiers:
                identites[p.stem] = max(identites.get(p.stem, 0), date)
            perimes = {k for k, _ in sorted(identites.items(), key=lambda x: x[1])[:-255]}
            for _, ancien in fichiers:
                if ancien.stem in perimes:
                    try:
                        ancien.unlink(missing_ok=True)
                    except OSError:
                        pass
            nom = nom_lu or nom
            if png:
                ecrire_atomique(fichier, png)
                echec.unlink(missing_ok=True)
                if isinstance(nom, str) and len(nom) <= 80:
                    ecrire_atomique(etiquette, json.dumps({'nom': nom}, ensure_ascii=False).encode('utf-8'))
                for ancien in anciens:
                    ancien.unlink(missing_ok=True)
                    ancien.with_suffix('.absent').unlink(missing_ok=True)
                return image_validee(png)[0], nom
            ecrire_atomique(echec, b'')
            return ancienne_image, nom

        futur = self.executor.submit(travail)
        self.attentes[cle] = futur
        def fini(f):
            try:
                image, nom = f.result()
            except Exception:
                image, nom = None, ''
            if self.actif:
                self.arrivee.emit((cle, generation, image, identite, nom))
        futur.add_done_callback(fini)
        return None

    def livrer(self, resultat):
        cle, generation, image, identite, nom = resultat
        if not self.actif or generation != self.generation:
            return
        self.attentes.pop(cle, None)
        if len(self.images) >= 128:
            ancienne_cle = next(iter(self.images))
            self.images.pop(ancienne_cle)
            self.reprises.pop(ancienne_cle, None)
        self.images[cle] = image
        if image is None:
            self.reprises[cle] = time.monotonic() + DELAI_REPRISE
        else:
            self.reprises.pop(cle, None)
        # Les noms du catalogue et les corrections explicites restent prioritaires.
        if identite.startswith('domaine:') and self.moteur.nom_appris(identite, nom):
            self.identites_modifiees = True
            self.rafraichissement.start(120)
        app = self.parent()
        if app and app.ouvert and app.isVisible() and hasattr(app, 'liste'):
            app.liste.vue.viewport().update()
            for page in app.autres_pages.values():
                if hasattr(page, 'vue'):
                    page.vue.viewport().update()

    def actualiser_identites(self):
        app = self.parent()
        if not self.identites_modifiees or not app or not app.ouvert or not app.isVisible() or not hasattr(app, 'liste'):
            return
        self.identites_modifiees = False
        # Service recognition for a large list is prepared in the worker too.
        app.actualiser()

    def annuler(self):
        self.generation += 1
        self.rafraichissement.stop()
        for futur in self.attentes.values():
            futur.cancel()
        self.attentes.clear()
        self.images.clear()
        self.reprises.clear()
        self.moteur.oublier()
        self.identites_modifiees = False

    def arreter(self):
        self.actif = False
        self.annuler()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def pour_extension(self, fiche, autorise=False):
        image = self.obtenir(fiche, autorise)
        if image is None:
            return ''
        sortie = QBuffer()
        sortie.open(QIODevice.OpenModeFlag.WriteOnly)
        image = image.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation) if max(image.width(), image.height()) > 128 else image
        image.save(sortie, 'PNG')
        return 'data:image/png;base64,' + base64.b64encode(bytes(sortie.data())).decode('ascii')
