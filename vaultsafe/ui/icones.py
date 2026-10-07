"""Icônes Signature locales, vectorielles et adaptées au zoom Qt."""
from functools import lru_cache
from pathlib import Path
import sys
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QIconEngine, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

DOSSIER = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2])) / 'assets'
PICTOGRAMMES = {'info':'info','fermer':'close','soleil':'sun','lune':'moon','ecran':'screen','cloche':'notification','reduire':'minimize','agrandir':'maximize','restaurer':'restore-window','plus':'add','moins':'minus','plus_options':'more','ouvrir':'open','modifier':'edit','wifi':'wifi','serveur':'server','globe':'globe','coche':'success','note':'note','carte':'card','personne':'account','recherche':'search','copier':'copy','suivant':'chevron-right','bas':'chevron-down','haut':'chevron-up','verrou':'lock','oeil':'eye','oeil_ferme':'eye-off','cle':'key','bouclier':'security','reglages':'settings','analyser':'analysis','importer':'import','dossier':'folder','corbeille':'delete','etoile':'star','etoile_pleine':'star-filled'}


PICTOGRAMMES['linkedin'] = 'linkedin'


@lru_cache(maxsize=48)
def donnees_icone(nom):
    chemin = DOSSIER / 'signature' / ('symbol-blue.svg' if nom == 'logo' else 'ui/' + PICTOGRAMMES[nom] + '.svg')
    return chemin.read_bytes()


@lru_cache(maxsize=128)
def rendu_icone(nom, couleur):
    donnees = donnees_icone(nom)
    if nom != 'logo':
        donnees = donnees.replace(b'currentColor', couleur.encode('ascii'))
    return QSvgRenderer(QByteArray(donnees))


def dessiner_icone(painter, rectangle, nom, couleur=None):
    if nom != 'logo' and nom not in PICTOGRAMMES:
        return
    couleur = QColor(couleur or QApplication.palette().color(QPalette.ColorRole.ButtonText)).name()
    rendu = rendu_icone(nom, '#0071e3' if nom == 'logo' else couleur)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    cote = min(rectangle.width(), rectangle.height())
    cible = QRectF(rectangle.center().x() - cote / 2, rectangle.center().y() - cote / 2, cote, cote)
    rendu.render(painter, cible)
    painter.restore()


def icone_application():
    return QIcon(str(DOSSIER / 'vaultsafe.ico'))


def icone_notification(sombre):
    icone = QIcon()
    variante = 'white' if sombre else 'graphite'
    for taille in (16, 20, 24, 32, 48, 64):
        icone.addFile(str(DOSSIER / 'signature' / 'tray' / variante / f'{taille}.png'))
    return icone


class Icone(QIconEngine):
    def __init__(self, nom, couleur=None):
        super().__init__()
        self.nom, self.couleur = nom, couleur

    def clone(self):
        return Icone(self.nom, self.couleur)

    def paint(self, painter, rect, mode, state):
        couleur = self.couleur
        if mode == QIcon.Mode.Disabled:
            couleur = QApplication.palette().color(QPalette.ColorRole.PlaceholderText)
        elif couleur is None and state == QIcon.State.On:
            couleur = QApplication.palette().color(QPalette.ColorRole.Highlight)
        dessiner_icone(painter, QRectF(rect), self.nom, couleur)

    def pixmap(self, size, mode, state):
        image = QPixmap(size)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.paint(painter, image.rect(), mode, state)
        painter.end()
        return image


def icone(nom, couleur=None):
    return QIcon(Icone(nom, couleur))
