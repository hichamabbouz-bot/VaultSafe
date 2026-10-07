"""Stockage SQLite d'un document entièrement chiffré, sans cache en clair.

Les lectures et écritures sensibles exigent une clé déverrouillée. Une empreinte
de la version lue empêche d'écraser les changements d'une autre instance.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path
from threading import RLock

from vaultsafe.enveloppe import ajouter_recuperation, nouvelle_enveloppe, ouvrir_cle, ouvrir_recuperation
from vaultsafe.fonctions_coffre import FonctionsCoffre
from vaultsafe.modele import document_vide, mettre_a_niveau
from vaultsafe.securite_coffre import (
    MAX_PAYLOAD_BYTES, ErreurCoffre, chiffrer, dechiffrer,
    effacer_cle, encoder_json, verifier_entete,
)

APPLICATION_ID = 0x56534_631
MAX_DATABASE_BYTES = 256 * 1024 * 1024
COLONNES = ["id", "entete", "nonce", "contenu"]


class ErreurBase(ValueError):
    """Erreur de stockage ne contenant pas de données sensibles."""


class BaseDeDonnees(FonctionsCoffre):
    """Dépôt local : document chiffré et blocs de pièces authentifiés."""

    def __init__(self, chemin: str | Path):
        self.chemin = Path(chemin).expanduser().resolve()
        self._cle: bytearray | None = None
        self._signature: bytes | None = None
        self._mutex = RLock()
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        if not self.chemin.exists():
            # Création exclusive : ne jamais tronquer un fichier existant.
            try:
                descripteur = os.open(self.chemin, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descripteur)
                with self._sql(ecriture=True) as sql:
                    sql.execute("CREATE TABLE coffre (id INTEGER PRIMARY KEY CHECK(id=1), "
                                "entete BLOB NOT NULL, nonce BLOB NOT NULL, contenu BLOB NOT NULL)")
                    sql.execute(f"PRAGMA application_id={APPLICATION_ID}")
                    sql.execute("PRAGMA user_version=1")
            except OSError as erreur:
                raise ErreurBase("Impossible de créer le coffre local.") from erreur
        with self._sql() as sql:
            self._verifier_format(sql)
            self._lire_ligne(sql)

    @contextmanager
    def _sql(self, ecriture: bool = False):
        sql = None
        try:
            if self.chemin.stat().st_size > MAX_DATABASE_BYTES:
                raise ErreurBase("Fichier de coffre trop volumineux.")
            # L'URI échappe correctement espaces, accents, # et ? du chemin.
            sql = sqlite3.connect(self.chemin.as_uri() + ("?mode=rw" if ecriture else "?mode=ro"),
                                  uri=True, timeout=5)
            sql.row_factory = sqlite3.Row
            sql.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_PAYLOAD_BYTES + 8192)
            sql.execute("PRAGMA trusted_schema=OFF")
            if ecriture:
                sql.execute("PRAGMA synchronous=FULL")
                sql.execute("BEGIN IMMEDIATE")
            yield sql
            if ecriture:
                sql.commit()
        except (sqlite3.Error, OSError) as erreur:
            if sql is not None:
                sql.rollback()
            raise ErreurBase("Impossible de lire ou d'enregistrer le coffre. "
                             "Vérifiez le fichier, l'espace disque et les permissions.") from erreur
        except BaseException:
            if sql is not None:
                sql.rollback()
            raise
        finally:
            if sql is not None:
                sql.close()

    @staticmethod
    def _verifier_format(sql):
        objets = {(ligne[0], ligne[1]) for ligne in sql.execute(
            "SELECT name,type FROM sqlite_master WHERE type IN ('table','view','trigger')")}
        tables = {nom for nom, type_ in objets}
        if {"acces", "identifiants"}.intersection(tables):
            raise ErreurBase("Ancien coffre en clair : migration explicite nécessaire. "
                             "Le fichier d'origine est conservé.")
        version = sql.execute("PRAGMA user_version").fetchone()[0]
        attendus = {("coffre", "table"), ("pieces", "table")} if version == 3 else {("coffre", "table")}
        if objets != attendus or sql.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            raise ErreurBase("Ce fichier n'est pas un coffre chiffré VaultSafe.")
        if [ligne[1] for ligne in sql.execute("PRAGMA table_info(coffre)")] != COLONNES:
            raise ErreurBase("Structure du coffre invalide.")
        if sql.execute("PRAGMA user_version").fetchone()[0] not in (1, 2, 3):
            raise ErreurBase("Version du fichier non prise en charge.")
        if version == 3:
            structure = [(r[1], r[2], r[5]) for r in sql.execute("PRAGMA table_info(pieces)")]
            if structure != [("id", "TEXT", 1), ("numero", "INTEGER", 2),
                             ("nonce", "BLOB", 0), ("contenu", "BLOB", 0)]:
                raise ErreurBase("Structure des pièces jointes invalide.")
        if sql.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ErreurBase("Le fichier du coffre est endommagé.")

    @staticmethod
    def _lire_ligne(sql):
        lignes = sql.execute("SELECT id,entete,nonce,contenu FROM coffre LIMIT 2").fetchall()
        if not lignes:
            if sql.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ErreurBase("Les données du coffre ont disparu.")
            return None
        if len(lignes) != 1 or lignes[0]["id"] != 1:
            raise ErreurBase("Structure du coffre invalide.")
        ligne = lignes[0]
        if any(not isinstance(ligne[colonne], bytes) for colonne in COLONNES[1:]):
            raise ErreurBase("Données du coffre invalides.")
        verifier_entete(ligne["entete"])
        if len(ligne["nonce"]) != 12 or not 16 <= len(ligne["contenu"]) <= MAX_PAYLOAD_BYTES + 16:
            raise ErreurBase("Données chiffrées invalides.")
        return ligne

    @staticmethod
    def _empreinte(ligne):
        resume = hashlib.sha256()
        for colonne in COLONNES[1:]:
            resume.update(len(ligne[colonne]).to_bytes(8, "big"))
            resume.update(ligne[colonne])
        return resume.digest()

    @property
    def coffre_ouvert(self) -> bool:
        return self._cle is not None

    @property
    def revision_courante(self) -> bytes | None:
        """Last in-memory fingerprint for freshness checks, never a disk read.

        This deliberately takes no storage mutex: the GUI must not wait for a
        worker decrypting a large vault. Authenticated reads/writes still validate
        under their mutex; this immutable snapshot is not an authorization.
        """
        return self._signature

    def est_initialise(self) -> bool:
        with self._mutex, self._sql() as sql:
            return self._lire_ligne(sql) is not None

    def exiger_ouverture(self) -> None:
        if self._cle is None:
            raise ErreurBase("Déverrouillez le coffre avant cette action.")

    @staticmethod
    def _contexte_appareil(ligne):
        entete = verifier_entete(ligne['entete'])
        if entete['version'] != 2:
            raise ErreurBase('Ouvrez d’abord ce coffre avec son mot de passe maître.')
        # Une modification de l'enveloppe maître révoque les anciens jetons.
        entete.pop('recovery_wrap', None)
        return hashlib.sha256(encoder_json(entete)).hexdigest()

    def contexte_appareil(self):
        with self._mutex, self._sql() as sql:
            ligne = self._lire_ligne(sql)
            if ligne is None:
                raise ErreurBase('Créez d’abord votre coffre.')
            return self._contexte_appareil(ligne)

    def exporter_cle_appareil(self):
        with self._mutex, self._sql() as sql:
            ligne, _ = self._contenu(sql)
            return self._contexte_appareil(ligne), bytearray(self._cle)

    def ouvrir_appareil(self, cle, contexte):
        with self._mutex:
            self.verrouiller()
            if not isinstance(cle, bytearray) or len(cle) != 32 or not isinstance(contexte, str):
                raise ErreurBase('Autorisation de cet appareil invalide.')
            with self._sql() as sql:
                self._verifier_format(sql)
                ligne = self._lire_ligne(sql)
            if ligne is None or not hmac.compare_digest(self._contexte_appareil(ligne), contexte):
                raise ErreurBase('L’autorisation a expiré. Utilisez votre mot de passe maître.')
            dechiffrer(cle, ligne['entete'], ligne['nonce'], ligne['contenu'])
            self._cle = bytearray(cle)
            self._signature = self._empreinte(ligne)

    def verrouiller(self) -> None:
        with self._mutex:
            effacer_cle(self._cle)
            self._cle = None
            self._signature = None

    @staticmethod
    def _creer_table_pieces(sql):
        sql.execute("CREATE TABLE IF NOT EXISTS pieces (id TEXT NOT NULL, numero INTEGER NOT NULL, "
                    "nonce BLOB NOT NULL, contenu BLOB NOT NULL, PRIMARY KEY(id,numero))")

    def creer_coffre(self, mot_de_passe: str) -> None:
        self._verifier_nouveau_mot_de_passe(mot_de_passe)
        with self._mutex:
            self.verrouiller()
            entete, cle = nouvelle_enveloppe(mot_de_passe)
            try:
                nonce, chiffre = chiffrer(cle, entete, document_vide())
                with self._sql(ecriture=True) as sql:
                    if self._lire_ligne(sql) is not None:
                        raise ErreurBase("Un coffre existe déjà.")
                    self._creer_table_pieces(sql)
                    sql.execute("INSERT INTO coffre VALUES(1,?,?,?)", (entete, nonce, chiffre))
                    sql.execute("PRAGMA user_version=3")
                self._cle = cle
                self._signature = self._empreinte({"entete": entete, "nonce": nonce, "contenu": chiffre})
            except BaseException:
                effacer_cle(cle)
                raise

    def ouvrir_coffre(self, mot_de_passe: str) -> None:
        with self._mutex:
            self.verrouiller()
            with self._sql() as sql:
                self._verifier_format(sql)
                ligne = self._lire_ligne(sql)
            if ligne is None:
                raise ErreurBase("Créez d’abord votre coffre.")
            cle = ouvrir_cle(mot_de_passe, ligne["entete"])
            nouvelle_cle = None
            try:
                contenu = dechiffrer(cle, ligne["entete"], ligne["nonce"], ligne["contenu"])
                if verifier_entete(ligne["entete"])["version"] == 1:
                    entete, nouvelle_cle = nouvelle_enveloppe(
                        mot_de_passe, verifier_entete(ligne["entete"])["coffre_id"])
                    nonce, chiffre = chiffrer(nouvelle_cle, entete, mettre_a_niveau(contenu))
                    with self._sql(ecriture=True) as sql:
                        actuelle = self._lire_ligne(sql)
                        if actuelle is None or not hmac.compare_digest(self._empreinte(actuelle), self._empreinte(ligne)):
                            raise ErreurBase("Le coffre a changé. Déverrouillez-le à nouveau.")
                        self._creer_table_pieces(sql)
                        sql.execute("UPDATE coffre SET entete=?,nonce=?,contenu=? WHERE id=1", (entete, nonce, chiffre))
                        sql.execute("PRAGMA user_version=3")
                    effacer_cle(cle)
                    cle, nouvelle_cle = nouvelle_cle, None
                    ligne = {"entete": entete, "nonce": nonce, "contenu": chiffre}
                self._cle = cle
                self._signature = self._empreinte(ligne)
            except BaseException:
                effacer_cle(cle)
                effacer_cle(nouvelle_cle)
                raise

    def _contenu(self, sql):
        self.exiger_ouverture()
        try:
            ligne = self._lire_ligne(sql)
            if ligne is None or not hmac.compare_digest(self._empreinte(ligne), self._signature):
                raise ErreurBase("Le coffre a changé dans une autre instance ou a été altéré. "
                                 "Déverrouillez-le à nouveau.")
            return ligne, mettre_a_niveau(dechiffrer(self._cle, ligne["entete"], ligne["nonce"], ligne["contenu"]))
        except (ErreurCoffre, ErreurBase):
            self.verrouiller()
            raise

    def _lire(self):
        with self._mutex:
            self.exiger_ouverture()
            with self._sql() as sql:
                return self._contenu(sql)[1]

    def _modifier(self, action, avec_sql=False):
        with self._mutex:
            self.exiger_ouverture()
            with self._sql(ecriture=True) as sql:
                ligne, contenu = self._contenu(sql)
                resultat = action(contenu, sql) if avec_sql else action(contenu)
                nonce, chiffre = chiffrer(self._cle, ligne["entete"], contenu)
                sql.execute("UPDATE coffre SET nonce=?,contenu=? WHERE id=1", (nonce, chiffre))
            # Ne changer la version en mémoire qu'après commit réussi.
            self._signature = self._empreinte({"entete": ligne["entete"], "nonce": nonce, "contenu": chiffre})
            return resultat

    def afficher_identifiants(self) -> list[dict]:
        return sorted(self._lire()["identifiants"], key=lambda c: c["date_modification"], reverse=True)

    def afficher_identifiant(self, identifiant_id: str) -> dict | None:
        return next((c for c in self._lire()["identifiants"] if c["id"] == identifiant_id), None)

    def lire_parametre(self, nom: str, valeur_defaut: str) -> str:
        # Avant déverrouillage, seul le défaut du demandeur est disponible.
        with self._mutex:
            if not self.coffre_ouvert:
                return valeur_defaut
            return self._lire()["parametres"].get(nom, valeur_defaut)

    def enregistrer_parametre(self, nom: str, valeur: str) -> None:
        self._modifier(lambda contenu: contenu["parametres"].__setitem__(nom, valeur))

    def lire_preferences(self) -> dict:
        """Lecture groupée ; aucun document clair conservé dans le dépôt."""
        return dict(self._lire()['parametres'])

    def lire_analyse(self):
        """Instantané complet réservé au travailleur, jamais au modèle de liste."""
        with self._mutex:
            document = self._lire()
            return document['identifiants'], self._signature

    def lire_vue(self) -> dict:
        """Projection de liste : aucun mot de passe, note ou secret TOTP."""
        with self._mutex:
            document = self._lire()
            colonnes = ('id', 'titre', 'nom_utilisateur', 'site', 'date_creation',
                        'date_modification', 'type', 'dossier', 'expiration', 'favori')
            fiches = [{**{k: f[k] for k in colonnes}, 'tags': list(f['tags']),
                       'presentation': dict(f.get('presentation', {})),
                       'secret_present': bool(f['mot_de_passe']), 'totp_present': bool(f['totp'])}
                      for f in document['identifiants']]
            return {'fiches': fiches, 'preferences': dict(document['parametres']),
                    'dossiers': document['dossiers'], 'corbeille': len(document['corbeille']),
                    'revision': self._signature}

    def changer_mot_de_passe(self, ancien: str, nouveau: str) -> None:
        self._verifier_nouveau_mot_de_passe(nouveau)
        with self._mutex:
            self.exiger_ouverture()
            ancienne_cle = nouvelle_cle = None
            try:
                with self._sql(ecriture=True) as sql:
                    ligne, contenu = self._contenu(sql)
                    ancienne_cle = ouvrir_cle(ancien, ligne["entete"])
                    dechiffrer(ancienne_cle, ligne["entete"], ligne["nonce"], ligne["contenu"])
                    ancien_entete = verifier_entete(ligne["entete"])
                    entete, nouvelle_cle = nouvelle_enveloppe(
                        nouveau, ancien_entete["coffre_id"], cle=self._cle,
                        recuperation=ancien_entete.get("recovery_wrap"))
                    nonce, chiffre = chiffrer(nouvelle_cle, entete, contenu)
                    sql.execute("UPDATE coffre SET entete=?,nonce=?,contenu=? WHERE id=1", (entete, nonce, chiffre))
                effacer_cle(self._cle)
                self._cle = nouvelle_cle
                nouvelle_cle = None
                self._signature = self._empreinte({"entete": entete, "nonce": nonce, "contenu": chiffre})
            finally:
                effacer_cle(ancienne_cle)
                effacer_cle(nouvelle_cle)

    def exporter_sauvegarde(self, destination: str | Path) -> Path:
        destination = Path(destination).with_suffix(".vaultsafe").resolve()
        if destination == self.chemin or (destination.exists() and os.path.samefile(destination, self.chemin)):
            raise ErreurBase("La sauvegarde doit être distincte du coffre actif.")
        temporaire = None
        try:
            with self._mutex:
                self.exiger_ouverture()
                with self._sql() as sql:
                    self._contenu(sql)
                    descripteur, nom = tempfile.mkstemp(prefix=".vaultsafe-", suffix=".tmp", dir=destination.parent)
                    os.close(descripteur)
                    temporaire = Path(nom)
                    with closing(sqlite3.connect(temporaire)) as copie:
                        sql.backup(copie)
                        copie.commit()
                essai = BaseDeDonnees(temporaire)
                try:
                    essai._cle = bytearray(self._cle)
                    with essai._sql() as lecture:
                        essai._signature = essai._empreinte(essai._lire_ligne(lecture))
                    essai.verifier_integrite()
                finally:
                    essai.verrouiller()
                os.replace(temporaire, destination)
            return destination
        except (sqlite3.Error, OSError) as erreur:
            raise ErreurBase("Impossible de créer la sauvegarde chiffrée.") from erreur
        finally:
            if temporaire is not None:
                temporaire.unlink(missing_ok=True)

    def restaurer_sauvegarde(self, source: str | Path, mot_de_passe: str) -> None:
        source = Path(source).resolve()
        if not source.is_file() or source.stat().st_size > MAX_DATABASE_BYTES:
            raise ErreurBase("Sauvegarde introuvable ou trop volumineuse.")
        if source == self.chemin or os.path.samefile(source, self.chemin):
            raise ErreurBase("Choisissez une sauvegarde distincte du coffre actif.")
        temporaire = None
        essai = None
        try:
            with self._mutex:
                # Snapshot cohérent avant validation : aucune course source/copie.
                descripteur, nom = tempfile.mkstemp(prefix=".vaultsafe-restauration-", suffix=".tmp", dir=self.chemin.parent)
                os.close(descripteur)
                temporaire = Path(nom)
                with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as lecture:
                    lecture.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_PAYLOAD_BYTES + 8192)
                    self._verifier_format(lecture)
                    with closing(sqlite3.connect(temporaire)) as copie:
                        lecture.backup(copie)
                        copie.commit()
                essai = BaseDeDonnees(temporaire)
                essai.ouvrir_coffre(mot_de_passe)
                essai.verifier_integrite()
                essai.verrouiller()
                self._refuser_journal_actif()
                os.replace(temporaire, self.chemin)
                self.verrouiller()
        except (sqlite3.Error, OSError) as erreur:
            raise ErreurBase("Impossible de restaurer la sauvegarde. Le coffre actuel est conservé.") from erreur
        finally:
            if essai is not None:
                essai.verrouiller()
            if temporaire is not None:
                temporaire.unlink(missing_ok=True)

    def _refuser_journal_actif(self):
        if any(Path(str(self.chemin) + suffixe).exists() for suffixe in ("-wal", "-shm", "-journal")):
            raise ErreurBase("Une écriture est en cours. Fermez les autres instances avant de remplacer le coffre.")

    @staticmethod
    def _verifier_nouveau_mot_de_passe(mot_de_passe):
        if not isinstance(mot_de_passe, str) or len(mot_de_passe) < 12:
            raise ErreurBase("Le mot de passe maître doit contenir au moins 12 caractères.")
        if len(mot_de_passe.encode("utf-8")) > 4096:
            raise ErreurBase("Le mot de passe maître est trop long.")

    def reinitialiser(self, confirmation: str = "") -> None:
        if confirmation != "REINITIALISER":
            raise ErreurBase("La suppression du coffre exige une confirmation explicite.")
        temporaire = None
        try:
            with self._mutex:
                self._refuser_journal_actif()
                temporaire = self.chemin.parent / (".vaultsafe-vide-" + os.urandom(8).hex() + ".tmp")
                BaseDeDonnees(temporaire)
                os.replace(temporaire, self.chemin)
                self.verrouiller()
        except OSError as erreur:
            raise ErreurBase("Impossible de réinitialiser le coffre.") from erreur
        finally:
            if temporaire is not None:
                temporaire.unlink(missing_ok=True)

    def recuperation_active(self):
        with self._mutex, self._sql() as sql:
            ligne = self._lire_ligne(sql)
            return bool(ligne and verifier_entete(ligne["entete"]).get("recovery_wrap"))

    def creer_cle_recuperation(self, mot_de_passe):
        with self._mutex:
            self.exiger_ouverture()
            protection = None
            try:
                with self._sql(ecriture=True) as sql:
                    ligne, contenu = self._contenu(sql)
                    protection = ouvrir_cle(mot_de_passe, ligne["entete"])
                    if not hmac.compare_digest(protection, self._cle):
                        raise ErreurBase("Mot de passe incorrect.")
                    entete, secret = ajouter_recuperation(ligne["entete"], self._cle)
                    nonce, chiffre = chiffrer(self._cle, entete, contenu)
                    sql.execute("UPDATE coffre SET entete=?,nonce=?,contenu=? WHERE id=1", (entete, nonce, chiffre))
                self._signature = self._empreinte({"entete": entete, "nonce": nonce, "contenu": chiffre})
                return secret
            finally:
                effacer_cle(protection)

    def recuperer_coffre(self, secret, nouveau_mot_de_passe):
        self._verifier_nouveau_mot_de_passe(nouveau_mot_de_passe)
        with self._mutex:
            cle = nouvelle_cle = None
            try:
                with self._sql(ecriture=True) as sql:
                    ligne = self._lire_ligne(sql)
                    if ligne is None:
                        raise ErreurBase("Aucun coffre à récupérer.")
                    cle = ouvrir_recuperation(secret, ligne["entete"])
                    contenu = mettre_a_niveau(dechiffrer(cle, ligne["entete"], ligne["nonce"], ligne["contenu"]))
                    entete, nouvelle_cle = nouvelle_enveloppe(
                        nouveau_mot_de_passe, verifier_entete(ligne["entete"])["coffre_id"], cle=cle)
                    entete, nouveau_secret = ajouter_recuperation(entete, nouvelle_cle)
                    nonce, chiffre = chiffrer(nouvelle_cle, entete, contenu)
                    sql.execute("UPDATE coffre SET entete=?,nonce=?,contenu=? WHERE id=1", (entete, nonce, chiffre))
                self.verrouiller()
                self._cle, nouvelle_cle = nouvelle_cle, None
                self._signature = self._empreinte({"entete": entete, "nonce": nonce, "contenu": chiffre})
                return nouveau_secret
            finally:
                effacer_cle(cle)
                effacer_cle(nouvelle_cle)
