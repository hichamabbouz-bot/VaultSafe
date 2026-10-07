"""Private native-messaging fixture, never a personal vault or desktop clipboard."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repertoire', required=True, type=Path)
    parser.add_argument('--executable', required=True, type=Path)
    args = parser.parse_args()
    dossier = args.repertoire.resolve()
    assert (dossier / 'fixture-owned.json').is_file()
    os.environ['VAULTSAFE_DATA_DIR'] = str(dossier / 'donnees')
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from vaultsafe.connexion import Connexion
    from vaultsafe.database import BaseDeDonnees
    from vaultsafe.identifiants import Identifiants
    from vaultsafe.parametres import Parametres
    from vaultsafe.liaison_navigateur import installer_hote, LiaisonLocale
    from vaultsafe.ui.app import Application
    from vaultsafe.ui.projections import lire_vue_preparee
    import vaultsafe.ui.navigateur as navigateur
    from vaultsafe.capture_comptes import CapturesComptes
    erreurs = []
    def diagnostic(original):
        def appeler(*a, **kw):
            try:
                return original(*a, **kw)
            except Exception as probleme:
                cadres, trace = [], probleme.__traceback__
                while trace is not None:
                    cadres.append(trace.tb_frame.f_code.co_name + ':' + str(trace.tb_lineno))
                    trace = trace.tb_next
                erreurs.append({'operation': original.__name__, 'classe': type(probleme).__name__, 'cadres': cadres})
                raise
        return appeler
    for nom in ('creer', 'decrire', 'resultat', 'enregistrer'):
        setattr(CapturesComptes, nom, diagnostic(getattr(CapturesComptes, nom)))
    qt = QApplication([])
    qt.setStyle('Fusion')
    base = BaseDeDonnees(dossier / 'donnees' / 'fictif.db')
    connexion = Connexion(base)
    connexion.creer_mot_de_passe_maitre('Navigateur-fictif-2026!')
    gestion, parametres = Identifiants(base, connexion), Parametres(base, connexion)
    ids = 'egbpodcdijmeibnmfabhiignfppmclbl'
    parametres.enregistrer_lot({'extension_ids': ids, 'icones_reseau': 'non', 'notifications': 'non', 'inactivite': '0'})
    installer_hote(ids, executable=args.executable, registre=False)
    app = Application(connexion, gestion, parametres, integrations_windows=False, masquee=True, auto_appareil=False)
    app.reafficher = lambda: None
    confirmations = []
    navigateur.message = lambda *a, **k: confirmations.append(a[1]) or True
    app.copier_texte = lambda texte: None
    sequence = -1
    timer = QTimer()
    timer.setInterval(40)
    def publier(numero=0):
        comptes = base.afficher_identifiants() if base.coffre_ouvert else []
        data = {'sequence': numero, 'ouvert': base.coffre_ouvert, 'nombre': len(comptes),
            'historique': sum(len(base.lire_historique(f['id'])) for f in comptes),
            'confirmations_windows': len(confirmations), 'ids': [f['id'] for f in comptes]}
        data['capture_mode'] = base.lire_preferences().get('capture_mode') if base.coffre_ouvert else None
        data['capture_attentes'] = len(app.captures_browser.attentes) if app.captures_browser else 0
        data['erreurs_techniques'] = list(erreurs)
        tmp = dossier / 'etat.tmp'
        tmp.write_text(json.dumps(data), encoding='utf-8')
        tmp.replace(dossier / 'etat.json')
    def commande():
        nonlocal sequence
        try:
            p = dossier / 'commande.json'
            if not p.exists():
                return
            c = json.loads(p.read_text(encoding='utf-8'))
            if c['sequence'] == sequence:
                return
            sequence = c['sequence']
            action = c['action']
            if action == 'stop':
                app.close()
                return
            if action == 'mode':
                parametres.enregistrer_lot({'capture_mode': c['mode']})
                app.preferences['capture_mode'] = c['mode']
            if action == 'lock':
                app.verrouiller()
            if action == 'unlock':
                connexion.se_connecter('Navigateur-fictif-2026!')
                app.session_ouverte(lire_vue_preparee(base))
            if action == 'reopen':
                base.verrouiller()
                connexion.se_connecter('Navigateur-fictif-2026!')
            publier(sequence)
        except (OSError, ValueError):
            (dossier / 'fixture-error.txt').write_text('Fixture command failed', encoding='utf-8')
    def ouvrir():
        if app.taches.attentes:
            QTimer.singleShot(20, ouvrir)
            return
        app.session_ouverte(lire_vue_preparee(base))
        app.hide()
        app.liaison = LiaisonLocale(ids, dossier=dossier / 'donnees', notifier=app.demande_navigateur.emit)
        publier()
        timer.timeout.connect(commande)
        timer.start()
    QTimer.singleShot(20, ouvrir)
    try:
        qt.exec()
    finally:
        timer.stop()
        app.close()
        base.verrouiller()


if __name__ == '__main__':
    main()
