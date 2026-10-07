"""One real Qt application with fake data and no desktop integrations."""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sortie', type=Path, required=True)
    parser.add_argument('--cycles', type=int, default=30)
    parser.add_argument('--repos', type=float, default=10)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='vaultsafe-qt-') as dossier:
        os.environ['VAULTSAFE_DATA_DIR'] = dossier
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        debut = time.perf_counter()
        from PySide6.QtCore import QEvent, QCoreApplication
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from vaultsafe.connexion import Connexion
        from vaultsafe.database import BaseDeDonnees
        from vaultsafe.identifiants import Identifiants
        from vaultsafe.parametres import Parametres
        from vaultsafe.ui.app import Application
        from vaultsafe.ui.projections import lire_vue_preparee
        from tools.mesurer import memoire_windows
        qt = QApplication([])
        qt.setStyle('Fusion')
        base = BaseDeDonnees(Path(dossier) / 'fictif.db')
        connexion = Connexion(base)
        connexion.creer_mot_de_passe_maitre('Qt-reference-fictive!')
        gestion = Identifiants(base, connexion)
        parametres = Parametres(base, connexion)
        parametres.enregistrer_lot({'icones_reseau': 'non', 'notifications': 'non', 'inactivite': '0'})
        gestion.ajouter_lot([dict(titre=f'Service fictif {i}', mot_de_passe='Secret-fictif!',
            site=f'https://s{i}.example.test/login', nom_utilisateur=f'personne{i}@example.test') for i in range(100)])
        app = Application(connexion, gestion, parametres, integrations_windows=False,
            masquee=True, auto_appareil=False)
        def attendre(condition, secondes=5):
            fin = time.monotonic() + secondes
            while not condition() and time.monotonic() < fin:
                qt.processEvents()
                QTest.qWait(5)
            assert condition()
        attendre(lambda: not app.taches.attentes)
        rapport = {'cycles': args.cycles, 'conditions': 'source Qt offscreen, 100 fiches fictives, Windows désactivé',
            'demarrage_avec_creation_fictive_ms': round((time.perf_counter()-debut)*1000, 2), 'pages_ms': [], 'ressources': []}
        try:
            for numero in range(args.cycles):
                if not base.coffre_ouvert:
                    connexion.se_connecter('Qt-reference-fictive!')
                app.session_ouverte(lire_vue_preparee(base))
                for theme, echelle in (('light', 100), ('dark', 200)):
                    app.theme, app.echelle = theme, echelle
                    app.appliquer_theme()
                    for page in ('identifiants', 'securite', 'parametres', 'identifiants'):
                        t = time.perf_counter()
                        app.afficher_page(page)
                        qt.processEvents()
                        if numero == 0:
                            rapport['pages_ms'].append({'theme': theme, 'echelle': echelle, 'page': page,
                                'ms': round((time.perf_counter()-t)*1000, 2)})
                app.hide()
                app.verrouiller()
                attendre(lambda: app.fermeture_coffre is None or app.fermeture_coffre.done())
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                qt.processEvents()
                if numero == 0 or (numero+1) % 10 == 0 or numero == args.cycles-1:
                    rapport['ressources'].append(dict(cycle=numero+1, widgets=len(qt.allWidgets()),
                        travaux_en_attente=len(app.taches.attentes), **memoire_windows()))
            for etat in ('verrouille_masque', 'ouvert_masque'):
                if etat == 'ouvert_masque':
                    connexion.se_connecter('Qt-reference-fictive!')
                    app.session_ouverte(lire_vue_preparee(base))
                    app.hide()
                cpu, wall = time.process_time(), time.perf_counter()
                fin = time.monotonic() + args.repos
                while time.monotonic() < fin:
                    qt.processEvents()
                    QTest.qWait(50)
                pourcent = (time.process_time()-cpu)/(time.perf_counter()-wall)*100
                rapport.setdefault('repos', []).append({'etat': etat, 'duree_s': args.repos,
                    'cpu_un_coeur_pct': round(pourcent, 3), 'cpu_machine_pct': round(pourcent/(os.cpu_count() or 1), 3),
                    **memoire_windows()})
            args.sortie.write_text(json.dumps(rapport, indent=2), encoding='utf-8')
            print(json.dumps(rapport))
        finally:
            app.close()
            qt.processEvents()
            base.verrouiller()


if __name__ == '__main__':
    main()
