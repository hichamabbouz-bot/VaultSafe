"""Local installation guide; never edits browser profiles or captures secrets."""
import os

from vaultsafe.ui.composants import Dialogue, bouton, champ, etiquette
from vaultsafe.windows_local import executable_courant


def ouvrir(app):
    dialogue = Dialogue(app, 'Extension Chrome / Edge', (540, 470), sensible=False)
    dossier = executable_courant().parent / 'extension'
    dialogue.corps.addWidget(etiquette(
        '1. Ouvrez chrome://extensions ou edge://extensions.\n'
        '2. Activez Mode développeur.\n'
        '3. Choisissez Charger l’extension non empaquetée.\n'
        '4. Sélectionnez le dossier ci-dessous.\n'
        '5. Revenez dans Paramètres > Avancé et cliquez Associer.\n'
        '6. L’extension affiche Connecté quand le coffre est ouvert.'))
    chemin = champ(str(dossier))
    chemin.setReadOnly(True)
    dialogue.corps.addWidget(chemin)
    ouvrir_dossier = bouton('Ouvrir le dossier', lambda: os.startfile(dossier))
    ouvrir_dossier.setEnabled(dossier.is_dir())
    dialogue.corps.addWidget(ouvrir_dossier)
    dialogue.corps.addWidget(bouton('Copier le chemin', lambda: app.copier_texte(str(dossier))))
    dialogue.corps.addWidget(etiquette(
        'Après une mise à niveau, rechargez l’extension et actualisez les pages ouvertes. '
        'Si vous déplacez VaultSafe, cliquez de nouveau Associer.', 'secondaire'))
    if not dossier.is_dir():
        dialogue.erreur.setText('Le dossier extension doit accompagner l’exécutable installé.')
    dialogue.actions.addWidget(bouton('Fermer', dialogue.reject, 'primaire'))
    dialogue.ouvrir()
    return dialogue
