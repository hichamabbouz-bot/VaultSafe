"""Informations publiques et soutien volontaire, sans accès au coffre."""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout
from vaultsafe.config import APP_VERSION
from vaultsafe.ui.composants import Dialogue, Symbole, bouton, etiquette


def ouvrir(app):
    dialogue = Dialogue(app, 'À propos', (480, 440), sensible=False)
    identite = QHBoxLayout()
    identite.setSpacing(18)
    identite.addWidget(Symbole('logo', app.couleurs['accent'], 56),
                       alignment=Qt.AlignmentFlag.AlignTop)
    textes = QVBoxLayout()
    textes.setSpacing(6)
    for texte, style in (('VaultSafe', 'titre'), (APP_VERSION, 'secondaire'),
                         ('Développé par', 'secondaire')):
        textes.addWidget(etiquette(texte, style))
    for nom, url in (
        ('Hicham Abbouz', 'https://www.linkedin.com/in/hichamabbouz/'),
        ('Sanae Omari Alaoui', 'https://www.linkedin.com/in/sanaa-omari-alaoui-/'),
    ):
        ligne = QHBoxLayout()
        ligne.setSpacing(6)
        ligne.addWidget(etiquette(nom))
        linkedin = bouton('', lambda checked=False, cible=url:
            QDesktopServices.openUrl(QUrl(cible)), 'discret', 'linkedin')
        linkedin.setFixedSize(28, 28)
        linkedin.setAccessibleName('LinkedIn — ' + nom)
        linkedin.setToolTip('Voir le profil LinkedIn de ' + nom)
        linkedin.setStyleSheet('QPushButton { padding: 4px; border: none; background: transparent; }'
                              'QPushButton:hover, QPushButton:focus { background: '
                              + app.couleurs['surface_alt'] + '; border-radius: 6px; }')
        ligne.addWidget(linkedin)
        ligne.addStretch()
        textes.addLayout(ligne)
    textes.addWidget(etiquette('Application gratuite', 'secondaire'))
    identite.addLayout(textes, 1)
    dialogue.corps.addLayout(identite)
    separateur = QFrame(objectName='separateur_connexion')
    separateur.setFixedHeight(1)
    dialogue.disposition.insertWidget(dialogue.disposition.count() - 1, separateur)
    dialogue.actions.addWidget(bouton('Fermer', dialogue.reject))
    dialogue.ouvrir()
    return dialogue
