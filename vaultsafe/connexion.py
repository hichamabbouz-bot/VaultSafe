"""Session locale : son état découle de la présence effective de la clé du coffre."""
import time

from vaultsafe.config import MIN_MASTER_PASSWORD_LENGTH
from vaultsafe.database import BaseDeDonnees


class Connexion:
    def __init__(self, base: BaseDeDonnees):
        self.base = base
        self._echecs = 0
        self._attendre = 0.0

    @property
    def est_connecte(self) -> bool:
        return self.base.coffre_ouvert

    def premier_lancement(self) -> bool:
        return not self.base.est_initialise()

    def verifier_longueur(self, mot_de_passe: str) -> None:
        if not isinstance(mot_de_passe, str) or len(mot_de_passe) < MIN_MASTER_PASSWORD_LENGTH:
            raise ValueError(f"Le mot de passe doit contenir au moins {MIN_MASTER_PASSWORD_LENGTH} caractères.")
        if len(mot_de_passe.encode("utf-8")) > 4096:
            raise ValueError("Le mot de passe maître est trop long.")

    def creer_mot_de_passe_maitre(self, mot_de_passe: str) -> None:
        self.verifier_longueur(mot_de_passe)
        if not self.premier_lancement():
            raise ValueError("Un coffre existe déjà.")
        self.base.creer_coffre(mot_de_passe)

    def se_connecter(self, mot_de_passe: str) -> None:
        if time.monotonic() < self._attendre:
            raise ValueError("Attendez quelques secondes avant une nouvelle tentative.")
        try:
            self.base.ouvrir_coffre(mot_de_passe)
        except ValueError:
            self._echecs += 1
            if self._echecs >= 5:
                self._attendre = time.monotonic() + min(30, 2 ** min(self._echecs - 4, 5))
            raise
        self._echecs = 0
        self._attendre = 0.0

    def se_deconnecter(self) -> None:
        self.base.verrouiller()

    def exiger_connexion(self) -> None:
        self.base.exiger_ouverture()

    def changer_mot_de_passe(self, ancien: str, nouveau: str) -> None:
        self.exiger_connexion()
        self.verifier_longueur(nouveau)
        self.base.changer_mot_de_passe(ancien, nouveau)
