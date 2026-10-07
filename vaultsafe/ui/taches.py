"""Un travailleur borné et des résultats isolés par génération de session."""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal


class Taches(QObject):
    fini = Signal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.generation = 0
        self.fermee = False
        self.verrou = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='VaultSafeTravail')
        self.analyseur = ThreadPoolExecutor(max_workers=1, thread_name_prefix='VaultSafeAnalyse')
        self.securite = ThreadPoolExecutor(max_workers=1, thread_name_prefix='VaultSafeFermeture')
        self.attentes = {}
        self.numero = 0
        self.fini.connect(self.livrer)

    def soumettre(self, action, succes=None, erreur=None, *, analyse=False):
        if self.fermee or len(self.attentes) >= 16:
            if erreur:
                erreur('Trop d’actions en attente. Réessayez après le traitement courant.')
            return None
        self.numero += 1
        numero, generation = self.numero, self.generation
        def travail():
            if generation != self.generation:
                return False, None
            try:
                valeur = action()
                return True, valeur
            except (ValueError, OSError) as probleme:
                return False, str(probleme)
            except Exception as probleme:
                # Ne jamais journaliser la valeur d'une exception ni des variables locales.
                cadres = []
                trace = probleme.__traceback__
                while trace is not None:
                    cadres.append(f'{trace.tb_frame.f_code.co_name}:{trace.tb_lineno}')
                    trace = trace.tb_next
                logging.getLogger('vaultsafe').error('operation:%s cadres:%s',
                                                    type(probleme).__name__, ','.join(cadres[-8:]))
                return False, 'L’action a échoué. Le coffre et les données sont conservés.'
        futur = (self.analyseur if analyse else self.executor).submit(travail)
        self.attentes[numero] = (futur, succes, erreur, generation)
        def terminer(future):
            try:
                ok, valeur = future.result()
            except Exception:
                ok, valeur = False, None
            if not self.fermee:
                self.fini.emit((numero, generation, ok, valeur))
        futur.add_done_callback(terminer)
        return futur

    def livrer(self, resultat):
        numero, generation, ok, valeur = resultat
        entree = self.attentes.pop(numero, None)
        if entree is None or self.fermee or generation != self.generation:
            return
        callback = entree[1] if ok else entree[2]
        if callback is not None:
            try:
                callback(valeur)
            except RuntimeError:
                # Un dialogue fermé pendant un traitement ne reçoit plus ses résultats.
                pass

    def invalider(self):
        self.generation += 1
        for futur, *_ in list(self.attentes.values()):
            futur.cancel()
        self.attentes.clear()

    def arreter(self, nettoyage=None):
        self.fermee = True
        self.invalider()
        # Après l'action en cours, le nettoyage ferme la clé et les intégrations.
        if nettoyage:
            self.securite.submit(nettoyage)
        self.executor.shutdown(wait=False, cancel_futures=False)
        self.analyseur.shutdown(wait=False, cancel_futures=True)
        self.securite.shutdown(wait=False, cancel_futures=False)
