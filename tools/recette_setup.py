"""Install/upgrade/uninstall only in a disposable path, with fake vault/native IPC."""
import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import time
import winreg
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ID = 'egbpodcdijmeibnmfabhiignfppmclbl'
GUID = '{F69E558B-20F6-4916-A5C7-08A579551889}_is1'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--setup', type=Path, required=True)
    p.add_argument('--sortie', type=Path, required=True)
    args = p.parse_args()
    # Refuse to overwrite an already installed user's VaultSafe registry entry.
    for flags in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r'Software\Microsoft\Windows\CurrentVersion\Uninstall' + '\\' + GUID, 0, winreg.KEY_READ | flags):
                raise RuntimeError('Existing installation: use a clean Windows account/VM for qualification.')
        except FileNotFoundError:
            pass
    rapport, gui = {'checks': [], 'conditions': 'isolated directory on current Windows; not a clean VM'}, None
    with tempfile.TemporaryDirectory(prefix='vaultsafe-setup-') as temp:
        root = Path(temp).resolve()
        programme, donnees = root / 'programme', root / 'donnees'
        env = dict(os.environ, VAULTSAFE_DATA_DIR=str(donnees), QT_QPA_PLATFORM='offscreen',
                   PYTHONDONTWRITEBYTECODE='1', PYTHONPATH='', PYTHONHOME='')
        # Production path is never used, including trust tokens and native manifests.
        os.environ['VAULTSAFE_DATA_DIR'] = str(donnees)
        from vaultsafe.database import BaseDeDonnees
        from vaultsafe.connexion import Connexion
        from vaultsafe.identifiants import Identifiants
        from vaultsafe.parametres import Parametres
        from vaultsafe.appareil_confiance import AppareilConfiance
        from vaultsafe.liaison_navigateur import installer_hote
        base = BaseDeDonnees(donnees / 'fictif.db')
        connexion = Connexion(base)
        connexion.creer_mot_de_passe_maitre('Installation-fictive-2026!')
        gestion = Identifiants(base, connexion)
        gestion.ajouter_identifiant(titre='Avant installation', mot_de_passe='Ancien-fictif!', site='https://recette.example')
        Parametres(base, connexion).enregistrer_lot({'theme': 'dark', 'extension_ids': ID,
            'icones_reseau': 'non', 'notifications': 'non', 'inactivite_confiance': '0'})
        AppareilConfiance(base).autoriser()
        base.verrouiller()
        avant = hashlib.sha256(base.chemin.read_bytes()).hexdigest()
        def installer(numero):
            run = subprocess.run([str(args.setup.resolve()), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                '/NORESTART', '/NOICONS', '/TASKS=', '/GROUP=VaultSafe-Qualification',
                '/DIR=' + str(programme), '/LOG=' + str(root / f'installation-{numero}.log')],
                env=env, creationflags=subprocess.CREATE_NO_WINDOW, timeout=120)
            assert run.returncode == 0, f'Setup exit {run.returncode}'
            assert (programme / 'VaultSafe.exe').is_file()
            assert (programme / 'extension/manifest.json').is_file()
            assert hashlib.sha256(base.chemin.read_bytes()).hexdigest() == avant
        try:
            installer(1)
            rapport['checks'].append('installation per-user in isolated directory; vault hash unchanged')
            installer(2)
            rapport['checks'].append('upgrade same stable program/extension paths; vault hash unchanged')
            exe = programme / 'VaultSafe.exe'
            installer_hote(ID, dossier=donnees, executable=exe, registre=False)
            manifest = json.loads((donnees / 'native-host.json').read_text(encoding='utf-8'))
            assert Path(manifest['path']) == exe
            rapport['checks'].append('native manifest points to installed executable; stable extension ID')
            gui = subprocess.Popen([str(exe), '--coffre', str(base.chemin)], env=env,
                creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            def native(contenu):
                data = json.dumps(contenu).encode('utf-8')
                run = subprocess.Popen([str(exe), 'chrome-extension://' + ID + '/'], env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                try:
                    out, _ = run.communicate(struct.pack('<I', len(data)) + data, timeout=15)
                    assert len(out) >= 4, 'Native response absent'
                    return json.loads(out[4:4 + struct.unpack('<I', out[:4])[0]])
                finally:
                    if run.poll() is None:
                        run.kill()
                        run.wait(5)
            fin = time.monotonic() + 15
            while time.monotonic() < fin:
                r = native({'action': 'status'})
                if r.get('ok') and r.get('ouvert'):
                    break
                time.sleep(.1)
            assert r.get('ouvert'), 'Fake trusted vault did not open'
            begin = native({'action': 'capture_begin', 'url': 'https://recette.example/login',
                'utilisateur': 'installation@example.test', 'mot_de_passe': 'Nouveau-fictif!', 'type': 'connexion'})
            assert begin.get('ok') and begin.get('token')
            r = native({'action': 'capture_commit', 'token': begin['token'],
                'utilisateur': 'installation@example.test', 'mot_de_passe': 'Nouveau-fictif!', 'dossier': '', 'id': ''})
            assert r.get('ok') and r.get('etat') == 'enregistre'
            rapport['checks'].append('installed GUI + trust + native capture + encrypted commit')
            # Terminate only this owned offscreen process; normal Qt closure is tested separately.
            gui.terminate()
            gui.wait(10)
            gui = None
            base.ouvrir_coffre('Installation-fictive-2026!')
            assert len(base.lire_vue()['fiches']) == 2
            assert base.lire_preferences()['theme'] == 'dark'
            base.verrouiller()
            apres = hashlib.sha256(base.chemin.read_bytes()).hexdigest()
            rapport['checks'].append('reopen persists two encrypted accounts and preferences')
            uninstaller = programme / 'unins000.exe'
            assert uninstaller.is_file() and uninstaller.resolve().is_relative_to(root)
            run = subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'],
                env=env, creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
            assert run.returncode == 0
            assert not exe.exists()
            assert not (programme / 'extension/manifest.json').exists()
            assert hashlib.sha256(base.chemin.read_bytes()).hexdigest() == apres
            rapport['checks'].append('uninstall removes program/extension; personal data preserved by default')
            rapport['setup_sha256'] = hashlib.sha256(args.setup.read_bytes()).hexdigest()
            args.sortie.write_text(json.dumps(rapport, indent=2), encoding='utf-8')
            print(json.dumps(rapport))
        finally:
            if gui is not None and gui.poll() is None:
                gui.terminate()
                gui.wait(10)
            base.verrouiller()
            uninstaller = programme / 'unins000.exe'
            if uninstaller.exists():
                subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'],
                    env=env, creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)


if __name__ == '__main__':
    main()
