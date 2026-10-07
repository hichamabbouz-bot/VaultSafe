"""Comparable local timings on fake vaults; never accepts a personal vault path."""
import argparse
import ctypes
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def memoire_windows():
    if os.name != 'nt':
        return {'disponible': False}
    from ctypes import wintypes as w
    class Memoire(ctypes.Structure):
        _fields_ = [('cb', w.DWORD), ('faults', w.DWORD)] + [
            (n, ctypes.c_size_t) for n in ('peak_ws', 'ws', 'peak_pool', 'pool',
                'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private')]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD]
    processus = kernel.GetCurrentProcess()
    m = Memoire()
    m.cb = ctypes.sizeof(m)
    if not psapi.GetProcessMemoryInfo(processus, ctypes.byref(m), m.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    handles = w.DWORD()
    kernel.GetProcessHandleCount.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    kernel.GetProcessHandleCount(processus, ctypes.byref(handles))
    # Instantané Tool Help : ne compter que les threads du processus de recette.
    class Thread(ctypes.Structure):
        _fields_ = [(n, w.DWORD) for n in ('size', 'usage', 'id', 'processus')] + [
            ('priorite', w.LONG), ('delta', w.LONG), ('flags', w.DWORD)]
    kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.Thread32First.argtypes = kernel.Thread32Next.argtypes = [w.HANDLE, ctypes.POINTER(Thread)]
    instantane = kernel.CreateToolhelp32Snapshot(4, 0)
    if instantane == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    threads = 0
    try:
        entree = Thread()
        entree.size = ctypes.sizeof(entree)
        suivant = kernel.Thread32First(instantane, ctypes.byref(entree))
        while suivant:
            if entree.processus == os.getpid():
                threads += 1
            suivant = kernel.Thread32Next(instantane, ctypes.byref(entree))
    finally:
        kernel.CloseHandle(instantane)
    return {'privee_mio': round(m.private / 2**20, 2), 'residente_mio': round(m.ws / 2**20, 2),
            'handles': handles.value, 'threads': threads, 'cpu_secondes': round(time.process_time(), 3)}


def mesure(action, repetitions=3):
    valeurs = []
    for _ in range(repetitions):
        debut = time.perf_counter()
        action()
        valeurs.append((time.perf_counter() - debut) * 1000)
    return {'mediane_ms': round(statistics.median(valeurs), 2), 'max_ms': round(max(valeurs), 2), 'n': repetitions}


def main():
    parseur = argparse.ArgumentParser()
    parseur.add_argument('--sortie', required=True, type=Path)
    parseur.add_argument('--tailles', type=int, nargs='+', default=[100, 1000, 10000])
    args = parseur.parse_args()
    with tempfile.TemporaryDirectory(prefix='vaultsafe-mesure-') as temporaire:
        os.environ['VAULTSAFE_DATA_DIR'] = temporaire
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        debut = time.perf_counter()
        from PySide6.QtWidgets import QApplication
        from vaultsafe.config import APP_VERSION
        from vaultsafe.connexion import Connexion
        from vaultsafe.database import BaseDeDonnees
        from vaultsafe.identifiants import Identifiants
        from vaultsafe.ui.liste import ModeleFiches, FiltreFiches
        qt = QApplication([])
        rapport = {'version': APP_VERSION, 'date_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'conditions': {'os': platform.platform(), 'python': platform.python_version(),
                'processeurs_logiques': os.cpu_count(), 'qt': 'offscreen', 'disque': 'temp utilisateur',
                'cache': 'chaud après import, sans réseau', 'mesure': 'source, pas démarrage froid'},
            'imports_qt_et_liste_ms': round((time.perf_counter() - debut) * 1000, 2), 'coffres': []}
        for nombre in args.tailles:
            if not 1 <= nombre <= 50000:
                raise ValueError('Taille fictive hors limites.')
            base = BaseDeDonnees(Path(temporaire) / f'fictif-{nombre}.db')
            connexion = Connexion(base)
            connexion.creer_mot_de_passe_maitre('Mesure-fictive-2026!')
            gestion = Identifiants(base, connexion)
            fiches = [dict(titre=f'Service fictif {i}', site=f'https://s{i}.example.test/login',
                nom_utilisateur=f'personne{i}@example.test', mot_de_passe='Secret-fictif-2026!') for i in range(nombre)]
            ligne = {'fiches': nombre, 'import_lot': mesure(lambda: gestion.ajouter_lot(fiches), 1)}
            ligne['lecture_projection'] = mesure(base.lire_vue)
            vue = base.lire_vue()
            modele, filtre = ModeleFiches(), FiltreFiches()
            filtre.setSourceModel(modele)
            ligne['modele'] = mesure(lambda: modele.remplacer(vue['fiches']))
            from vaultsafe.ui.projections import preparer_table
            table = preparer_table(vue['fiches'])
            ligne['mise_a_jour_gui_preparee'] = mesure(lambda: modele.remplacer(vue['fiches'], table=table))
            def rechercher():
                filtre.mots = ['999']
                filtre.invalidateFilter()
                filtre.rowCount()
                qt.processEvents()
            ligne['recherche'] = mesure(rechercher)
            fiche_id = vue['fiches'][0]['id']
            ligne['mutation'] = mesure(lambda: gestion.modifier_identifiant(fiche_id, notes='Note fictive'))
            ligne['sauvegarde'] = mesure(lambda: base.exporter_sauvegarde(Path(temporaire) / 'backup.vaultsafe'))
            def ouvrir():
                base.verrouiller()
                connexion.se_connecter('Mesure-fictive-2026!')
            ligne['deverrouillage'] = mesure(ouvrir)
            ligne['ressources'] = memoire_windows()
            base.verrouiller()
            rapport['coffres'].append(ligne)
        args.sortie.parent.mkdir(parents=True, exist_ok=True)
        args.sortie.write_text(json.dumps(rapport, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(rapport, ensure_ascii=False))


if __name__ == '__main__':
    main()
