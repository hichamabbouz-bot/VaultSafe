"""Repeated owned executable processes, disposable vault, technical timings only."""
import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', type=Path, default=Path(__file__).resolve().parents[1] / 'dist/VaultSafe/VaultSafe.exe')
    parser.add_argument('--sortie', required=True, type=Path)
    parser.add_argument('--lancements', type=int, default=30)
    args = parser.parse_args()
    assert os.name == 'nt' and args.executable.is_file()
    assert 1 <= args.lancements <= 100
    with tempfile.TemporaryDirectory(prefix='vaultsafe-lancements-') as dossier:
        os.environ['VAULTSAFE_DATA_DIR'] = dossier
        from vaultsafe.connexion import Connexion
        from vaultsafe.database import BaseDeDonnees
        base = BaseDeDonnees(Path(dossier) / 'fictif.db')
        Connexion(base).creer_mot_de_passe_maitre('Lancements-fictifs-2026!')
        base.verrouiller()
        original = hashlib.sha256(base.chemin.read_bytes()).hexdigest()
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONHOME', 'PYTHONPATH')}
        env.update(QT_QPA_PLATFORM='offscreen', PYTHONDONTWRITEBYTECODE='1',
                   PATH=os.path.join(os.environ['SYSTEMROOT'], 'System32') + ';' + os.environ['SYSTEMROOT'])
        valeurs = []
        for numero in range(args.lancements):
            journal = Path(dossier) / 'technique.log'
            journal.unlink(missing_ok=True)
            debut = time.perf_counter()
            processus = subprocess.Popen([str(args.executable.resolve()), '--coffre', str(base.chemin), '--reduire'],
                env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                texte = ''
                while time.perf_counter()-debut < 15:
                    assert processus.poll() is None, 'Le processus fictif a quitté avant d’être prêt.'
                    texte = journal.read_text(encoding='utf-8') if journal.exists() else ''
                    if 'demarrage:pret ' in texte and 'demarrage:affichage ' in texte:
                        break
                    time.sleep(.02)
                else:
                    raise AssertionError('Démarrage fictif hors délai.')
                assert 'incident:' not in texte and 'operation:' not in texte
                interne = float(re.search(r'demarrage:pret ([0-9.]+)ms', texte)[1])
                valeurs.append({'numero': numero+1, 'externe_ms': round((time.perf_counter()-debut)*1000, 2), 'interne_ms': interne})
            finally:
                if processus.poll() is None:
                    processus.terminate()
                processus.wait(timeout=10)
        assert hashlib.sha256(base.chemin.read_bytes()).hexdigest() == original
        rapport = {'lancements': len(valeurs), 'conditions': 'EXE réel, cache Windows disponible, Qt offscreen, coffre fictif verrouillé; arrêt des seuls processus de recette',
            'executable_sha256': hashlib.sha256(args.executable.read_bytes()).hexdigest(), 'valeurs': valeurs,
            'externe_mediane_ms': round(statistics.median(v['externe_ms'] for v in valeurs), 2),
            'externe_max_ms': max(v['externe_ms'] for v in valeurs)}
        args.sortie.parent.mkdir(parents=True, exist_ok=True)
        args.sortie.write_text(json.dumps(rapport, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in rapport.items() if k != 'valeurs'}))


if __name__ == '__main__':
    main()
