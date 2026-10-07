import threading
import time


def test_revision_non_bloquante_pendant_ecriture(coffre):
    base, _, gestion, _ = coffre
    avant = base.revision_courante
    gestion.ajouter_identifiant(titre='Révision fictive', mot_de_passe='Secret-fictif')
    assert base.revision_courante != avant
    entree, sortie = threading.Event(), threading.Event()
    def tenir_verrou():
        with base._mutex:
            entree.set()
            sortie.wait(3)
    thread = threading.Thread(target=tenir_verrou)
    thread.start()
    try:
        assert entree.wait(1)
        debut = time.perf_counter()
        assert base.revision_courante is not None
        assert time.perf_counter() - debut < .1
    finally:
        sortie.set()
        thread.join(3)
