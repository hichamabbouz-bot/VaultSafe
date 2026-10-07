import threading
import time

from PySide6.QtCore import QRect, QSize
from PySide6.QtTest import QTest

from vaultsafe.ui.placement import rectangle_centre
from vaultsafe.ui.taches import Taches


def attendre(qt, condition, secondes=3):
    fin = time.monotonic() + secondes
    while not condition() and time.monotonic() < fin:
        qt.processEvents()
        QTest.qWait(5)
    assert condition()


def test_ecrans_negatifs_et_petit_ecran():
    for zone in (QRect(-1920, 0, 1920, 1040), QRect(1920, -300, 1280, 700), QRect(0, 0, 640, 400)):
        rect = rectangle_centre(zone, QSize(1050, 680))
        assert zone.contains(rect)
        assert abs(rect.center().x() - zone.center().x()) <= 1


def test_travail_hors_gui_et_resultats_perimes(qt):
    taches = Taches()
    entree, sortie = threading.Event(), threading.Event()
    resultats = []
    identite_gui = threading.get_ident()
    def action():
        entree.set()
        sortie.wait(2)
        return threading.get_ident()
    try:
        futur = taches.soumettre(action, resultats.append)
        assert entree.wait(1)
        taches.invalider()
        sortie.set()
        assert futur.result(timeout=2)[1] != identite_gui
        qt.processEvents()
        assert not resultats
    finally:
        sortie.set()
        taches.arreter()


def test_erreurs_et_file_bornee(qt):
    taches = Taches()
    sortie = threading.Event()
    erreurs = []
    try:
        for _ in range(16):
            taches.soumettre(lambda: sortie.wait(2))
        assert taches.soumettre(lambda: None, erreur=erreurs.append) is None
        assert erreurs and len(taches.attentes) == 16
    finally:
        sortie.set()
        taches.arreter()


def test_fermeture_pendant_travail(qt):
    taches = Taches()
    entree, sortie, nettoye = threading.Event(), threading.Event(), threading.Event()
    resultats = []
    def action():
        entree.set()
        sortie.wait(2)
    futur = taches.soumettre(action, resultats.append)
    assert entree.wait(1)
    taches.arreter(nettoye.set)
    sortie.set()
    futur.result(timeout=2)
    attendre(qt, nettoye.is_set)
    assert not resultats
