"""Vérification volontaire des mots de passe dans les fuites connues."""

from __future__ import annotations

# hashlib calcule SHA-1 uniquement pour interroger Pwned Passwords.
# Ce SHA-1 n'est pas le mécanisme de connexion ni un stockage de secret.
import hashlib
# string.hexdigits aide à vérifier que la réponse ne contient que de l'hexadécimal.
import string
# Le réseau attend parfois plusieurs secondes : quatre tâches parallèles
# évitent de bloquer la fenêtre et accélèrent les comptes distincts.
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
# urllib fait la requête HTTPS sans ajouter de nouvelle dépendance au projet.
from urllib.request import Request, urlopen


class ControleFuites:
    """Garde seulement le dernier contrôle en mémoire, jamais dans SQLite."""

    def __init__(self) -> None:
        self.resultats: dict[str, int] | None = None
        # Un contrôle lancé avant une modification ne doit pas réapparaître
        # après cette modification ou après une déconnexion.
        self.generation = 0

    def oublier(self) -> None:
        """Une modification ou déconnexion rend l'ancien résultat périmé."""
        self.resultats = None
        self.generation += 1


def verifier_mot_de_passe_expose(mot_de_passe: str) -> int:
    """Cherche un mot dans Pwned Passwords sans envoyer le mot ni son hash entier.

    SHA-1 sert uniquement à cette recherche compatible avec le service ; il
    ne sert jamais à protéger ou à enregistrer un mot de passe dans le coffre.
    """
    empreinte = hashlib.sha1(mot_de_passe.encode("utf-8")).hexdigest().upper()
    # Le service reçoit seulement les cinq premiers caractères. Le reste
    # demeure sur l'ordinateur et sert à trouver la bonne ligne dans la réponse.
    debut, fin = empreinte[:5], empreinte[5:]
    demande = Request(
        f"https://api.pwnedpasswords.com/range/{debut}",
        headers={"User-Agent": "VaultSafe/2.1", "Add-Padding": "true"},
    )
    try:
        with urlopen(demande, timeout=5) as reponse:
            # Une réponse anormalement grande ne doit pas saturer la mémoire.
            donnees = reponse.read(1_000_001)
        if len(donnees) > 1_000_000:
            raise ValueError("Réponse du service trop volumineuse.")
        lignes = donnees.decode("ascii").splitlines()
        if not lignes:
            raise ValueError("Réponse vide.")
        # Chaque ligne de la réponse contient une fin d'empreinte et son nombre
        # d'apparitions dans les fuites. On compare la fin avec la nôtre.
        for ligne in lignes:
            suffixe, separateur, nombre = ligne.partition(":")
            if (not separateur or len(suffixe) != 35
                    or any(caractere not in string.hexdigits for caractere in suffixe)
                    or not nombre.isdecimal()):
                raise ValueError("Réponse du service invalide.")
            if separateur and suffixe.upper() == fin:
                return int(nombre)
        # Aucune ligne correspondante : le service n'a pas trouvé ce mot.
        return 0
    except (OSError, UnicodeError, ValueError) as erreur:
        raise ValueError("Contrôle des fuites indisponible. Réessayez plus tard.") from erreur


def verifier_comptes_exposes(
    comptes: list[tuple[str, str]], progression=None, annule=None
) -> dict[str, int]:
    """Vérifie chaque mot distinct une seule fois, sur quatre tâches de fond.

    Le résultat associe un numéro de compte au nombre d'apparitions trouvées.
    Rien n'est enregistré dans SQLite ni dans un fichier de rapport.
    """
    # Un même mot peut servir à plusieurs comptes. On le vérifie une seule
    # fois sur Internet, puis on rattache le résultat à chaque compte concerné.
    groupes = {}
    for identifiant, mot_de_passe in comptes:
        groupes.setdefault(mot_de_passe, []).append(identifiant)

    resultat = {}
    with ThreadPoolExecutor(max_workers=4) as travailleurs:
        # submit lance une vérification par mot distinct. Le dictionnaire
        # conserve le lien entre chaque travail et le mot qu'il vérifie.
        attentes = {}
        mots, numero = iter(groupes), 0
        def completer():
            while len(attentes) < 4:
                if annule and annule():
                    raise ValueError('Contrôle annulé.')
                mot = next(mots, None)
                if mot is None:
                    break
                attentes[travailleurs.submit(verifier_mot_de_passe_expose, mot)] = mot
        completer()
        while attentes:
            if annule and annule():
                raise ValueError('Contrôle annulé.')
            pretes, _ = wait(attentes, timeout=0.2, return_when=FIRST_COMPLETED)
            for attente in pretes:
                mot = attentes.pop(attente)
                nombre = attente.result()
                if nombre > 0:
                    for identifiant in groupes[mot]:
                        resultat[identifiant] = nombre
                numero += 1
                if progression is not None:
                    progression(numero, len(groupes))
            completer()
    return resultat
