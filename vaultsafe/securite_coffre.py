"""Format v1 : Argon2id et AES-256-GCM, via la bibliothèque cryptography.

Seul l'en-tête public est hors du chiffrement. Il est authentifié comme AAD.
Les nonces sont renouvelés à chaque écriture. Aucun algorithme fait maison.
"""
from __future__ import annotations

import json
import secrets
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

FORMAT_VERSION = 1
PAYLOAD_VERSION = 1
MAX_PAYLOAD_BYTES = 32 * 1024 * 1024
MAX_HEADER_BYTES = 2048
MAX_RECORDS = 50_000
MAX_FIELD_CHARS = 100_000
ARGON_MEMORY_KIB = 64 * 1024
ARGON_ITERATIONS = 3
ARGON_LANES = 4
CHAMPS_IDENTIFIANT = {
    "id", "titre", "nom_utilisateur", "mot_de_passe", "site", "notes",
    "date_creation", "date_modification",
}


class ErreurCoffre(ValueError):
    """Erreur présentable à l'utilisateur, sans contenu du coffre."""


def _sans_doublon(paires):
    resultat = {}
    for cle, valeur in paires:
        if cle in resultat:
            raise ErreurCoffre("Format du coffre invalide.")
        resultat[cle] = valeur
    return resultat


def encoder_json(valeur: dict) -> bytes:
    return json.dumps(
        valeur, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def decoder_json(donnees: bytes) -> dict:
    try:
        resultat = json.loads(donnees, object_pairs_hook=_sans_doublon)
    except (ValueError, UnicodeError, RecursionError) as erreur:
        raise ErreurCoffre("Format du coffre invalide.") from erreur
    if not isinstance(resultat, dict):
        raise ErreurCoffre("Format du coffre invalide.")
    return resultat


def nouvel_entete(coffre_id: str | None = None) -> bytes:
    return encoder_json({
        "format": "VaultSafe", "version": FORMAT_VERSION,
        "coffre_id": coffre_id or str(uuid4()), "kdf": "argon2id",
        "sel": secrets.token_bytes(16).hex(), "memory_kib": ARGON_MEMORY_KIB,
        "iterations": ARGON_ITERATIONS, "lanes": ARGON_LANES,
        "cipher": "aes-256-gcm",
    })


def verifier_entete(entete: bytes) -> dict:
    if not isinstance(entete, bytes) or not 1 <= len(entete) <= MAX_HEADER_BYTES:
        raise ErreurCoffre("En-tête du coffre invalide.")
    valeur = decoder_json(entete)
    attendus = {
        "format", "version", "coffre_id", "kdf", "sel", "memory_kib",
        "iterations", "lanes", "cipher",
    }
    if valeur.get("version") == 2:
        attendus |= {"master_wrap", "recovery_wrap"}
    if set(valeur) != attendus:
        raise ErreurCoffre("En-tête du coffre invalide.")
    if type(valeur["version"]) is not int or valeur["version"] not in (1, 2):
        raise ErreurCoffre("Version du coffre non prise en charge.")
    if (valeur["format"] != "VaultSafe" or valeur["kdf"] != "argon2id"
            or valeur["cipher"] != "aes-256-gcm"):
        raise ErreurCoffre("Format cryptographique non pris en charge.")
    # Borner avant la dérivation empêche un fichier hostile d'épuiser la mémoire.
    bornes = {"memory_kib": (ARGON_MEMORY_KIB, 256 * 1024),
              "iterations": (3, 8), "lanes": (1, 4)}
    for cle, (minimum, maximum) in bornes.items():
        if type(valeur[cle]) is not int or not minimum <= valeur[cle] <= maximum:
            raise ErreurCoffre("Paramètres de sécurité non pris en charge.")
    if valeur["memory_kib"] * valeur["iterations"] > 768 * 1024:
        raise ErreurCoffre("Paramètres de sécurité trop coûteux.")
    try:
        if not isinstance(valeur["sel"], str) or len(valeur["sel"]) != 32:
            raise ValueError
        bytes.fromhex(valeur["sel"])
        if not isinstance(valeur["coffre_id"], str):
            raise ValueError
        UUID(valeur["coffre_id"])
    except (ValueError, TypeError) as erreur:
        raise ErreurCoffre("En-tête du coffre invalide.") from erreur
    if valeur["version"] == 2:
        for nom in ("master_wrap", "recovery_wrap"):
            paquet = valeur[nom]
            if nom == "recovery_wrap" and paquet is None:
                continue
            if not isinstance(paquet, dict) or set(paquet) != {"nonce", "contenu"}:
                raise ErreurCoffre("Enveloppe de clé invalide.")
            try:
                if (not isinstance(paquet["nonce"], str) or len(paquet["nonce"]) != 24
                        or not isinstance(paquet["contenu"], str) or len(paquet["contenu"]) != 96
                        or len(bytes.fromhex(paquet["nonce"])) != 12
                        or len(bytes.fromhex(paquet["contenu"])) != 48):
                    raise ValueError
            except ValueError as erreur:
                raise ErreurCoffre("Enveloppe de clé invalide.") from erreur
    if encoder_json(valeur) != entete:
        raise ErreurCoffre("En-tête du coffre non canonique.")
    return valeur


def deriver_cle(mot_de_passe: str, entete: bytes) -> bytearray:
    valeur = verifier_entete(entete)
    if not isinstance(mot_de_passe, str) or len(mot_de_passe.encode("utf-8")) > 4096:
        raise ErreurCoffre("Mot de passe maître invalide ou trop long.")
    kdf = Argon2id(salt=bytes.fromhex(valeur["sel"]), length=32,
                  iterations=valeur["iterations"], lanes=valeur["lanes"],
                  memory_cost=valeur["memory_kib"])
    return bytearray(kdf.derive(mot_de_passe.encode("utf-8")))


def effacer_cle(cle: bytearray | None) -> None:
    if cle is not None:
        cle[:] = b"\x00" * len(cle)


def verifier_contenu(contenu: dict) -> None:
    if contenu.get("schema") == 2:
        from vaultsafe.modele import verifier_document
        try:
            verifier_document(contenu)
        except (ValueError, TypeError, KeyError, RecursionError) as erreur:
            raise ErreurCoffre("Structure du coffre invalide.") from erreur
        return
    if set(contenu) != {"schema", "identifiants", "parametres"}:
        raise ErreurCoffre("Structure du coffre invalide.")
    if type(contenu["schema"]) is not int or contenu["schema"] != PAYLOAD_VERSION:
        raise ErreurCoffre("Version des données non prise en charge.")
    comptes, preferences = contenu["identifiants"], contenu["parametres"]
    if not isinstance(comptes, list) or len(comptes) > MAX_RECORDS:
        raise ErreurCoffre("Taille du coffre non prise en charge.")
    if (not isinstance(preferences, dict) or len(preferences) > 100
            or any(not isinstance(k, str) or not isinstance(v, str)
                   or len(k) > 100 or len(v) > 1000 for k, v in preferences.items())):
        raise ErreurCoffre("Paramètres du coffre invalides.")
    ids = set()
    for compte in comptes:
        if (not isinstance(compte, dict) or set(compte) != CHAMPS_IDENTIFIANT
                or any(not isinstance(v, str) or len(v) > MAX_FIELD_CHARS
                       for v in compte.values())):
            raise ErreurCoffre("Fiche du coffre invalide.")
        if not compte["titre"].strip() or not compte["mot_de_passe"]:
            raise ErreurCoffre("Fiche du coffre incomplète.")
        try:
            UUID(compte["id"])
        except ValueError as erreur:
            raise ErreurCoffre("Identifiant de fiche invalide.") from erreur
        if compte["id"] in ids:
            raise ErreurCoffre("Identifiant de fiche dupliqué.")
        ids.add(compte["id"])


def chiffrer(cle: bytearray, entete: bytes, contenu: dict) -> tuple[bytes, bytes]:
    verifier_entete(entete)
    verifier_contenu(contenu)
    donnees = encoder_json(contenu)
    if len(donnees) > MAX_PAYLOAD_BYTES:
        raise ErreurCoffre("Le coffre dépasse la taille maximale de 32 Mo.")
    nonce = secrets.token_bytes(12)
    return nonce, AESGCM(cle).encrypt(nonce, donnees, entete)


def dechiffrer(cle: bytearray, entete: bytes, nonce: bytes, chiffre: bytes) -> dict:
    verifier_entete(entete)
    if (not isinstance(nonce, bytes) or len(nonce) != 12
            or not isinstance(chiffre, bytes) or not 16 <= len(chiffre) <= MAX_PAYLOAD_BYTES + 16):
        raise ErreurCoffre("Données chiffrées invalides.")
    try:
        donnees = AESGCM(cle).decrypt(nonce, chiffre, entete)
    except InvalidTag as erreur:
        raise ErreurCoffre("Mot de passe incorrect ou coffre altéré.") from erreur
    contenu = decoder_json(donnees)
    verifier_contenu(contenu)
    return contenu
