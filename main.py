"""Un seul processus Qt ; le mode hôte natif n'importe aucune interface."""
from __future__ import annotations

import sys
import time


def diagnostics():
    import logging
    from logging.handlers import RotatingFileHandler
    from vaultsafe.config import obtenir_dossier_donnees
    logger = logging.getLogger('vaultsafe')
    logger.setLevel(logging.INFO)
    try:
        dossier = obtenir_dossier_donnees()
        dossier.mkdir(parents=True, exist_ok=True)
        sortie = RotatingFileHandler(dossier / 'technique.log', maxBytes=256 * 1024, backupCount=1, encoding='utf-8')
        sortie.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(sortie)
    except OSError:
        logger.addHandler(logging.NullHandler())
    def incident(classe, valeur, trace):
        # Ne conserver ni texte d'exception, ni arguments, ni variables locales.
        cadres = []
        while trace is not None:
            cadres.append(f'{trace.tb_frame.f_code.co_name}:{trace.tb_lineno}')
            trace = trace.tb_next
        logger.error('incident:%s cadres:%s', classe.__name__, ','.join(cadres[-8:]))
    sys.excepthook = incident
    return logger


def main():
    appelant = next((a for a in sys.argv[1:] if a.startswith('chrome-extension://')), None)
    if appelant is not None:
        from vaultsafe.liaison_navigateur import executer_hote
        executer_hote(appelant)
        return 0
    debut = time.perf_counter()
    import argparse
    parseur = argparse.ArgumentParser(description='VaultSafe · coffre Windows local')
    profil = parseur.add_mutually_exclusive_group()
    profil.add_argument('--coffre', help='Ouvrir un coffre local')
    profil.add_argument('--developpement', action='store_true', help='Profil de développement isolé, sans saisie répétée')
    parseur.add_argument('--reduire', action='store_true', help='Démarrer dans la zone de notification, coffre verrouillé')
    arguments = parseur.parse_args()
    if arguments.developpement:
        from vaultsafe.developpement import choisir_profil
        arguments.coffre = choisir_profil()
    logger = diagnostics()
    from PySide6.QtCore import QLibraryInfo, QTimer, QTranslator
    from PySide6.QtWidgets import QApplication
    from vaultsafe.ui.app import Application
    qt = QApplication(sys.argv[:1])
    qt.setApplicationName('VaultSafe')
    qt.setOrganizationName('VaultSafe')
    qt.setStyle('Fusion')
    traducteur = QTranslator(qt)
    if traducteur.load('qtbase_fr', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        qt.installTranslator(traducteur)
    app = Application(chemin=arguments.coffre, masquee=arguments.reduire, debut_demarrage=debut,
                      developpement=arguments.developpement, auto_appareil=not arguments.reduire)
    logger.info('demarrage:connexion %.1fms ecrans:%d', (time.perf_counter() - debut) * 1000, len(qt.screens()))
    QTimer.singleShot(0, lambda: logger.info('demarrage:affichage %.1fms', (time.perf_counter() - debut) * 1000))
    resultat = qt.exec()
    app.base.verrouiller() if app.base else None
    return resultat


if __name__ == '__main__':
    raise SystemExit(main())
