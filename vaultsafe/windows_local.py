"""Zone de notification, autostart volontaire et verrouillage de session Windows."""
from __future__ import annotations

import sys
from pathlib import Path


def executable_courant():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve()
    racine = Path(__file__).resolve().parents[1]
    return racine / 'dist' / 'VaultSafe' / 'VaultSafe.exe'


def demarrage_windows(actif):
    import winreg
    chemin = executable_courant()
    if actif and not chemin.is_file():
        raise ValueError('Construisez l’exécutable avant d’activer le démarrage Windows.')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                         r'Software\Microsoft\Windows\CurrentVersion\Run') as cle:
        if actif:
            winreg.SetValueEx(cle, 'VaultSafe', 0, winreg.REG_SZ, '"' + str(chemin) + '" --reduire')
        else:
            try:
                winreg.DeleteValue(cle, 'VaultSafe')
            except FileNotFoundError:
                pass


