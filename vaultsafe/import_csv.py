"""Import volontaire des mots de passe exportés par un navigateur."""

from __future__ import annotations

# csv lit correctement les virgules placées entre guillemets dans un export.
import csv
# Path gère les chemins de fichiers Windows de façon claire.
from pathlib import Path
from typing import TYPE_CHECKING, Any
# urlparse extrait un nom de site quand Firefox ne fournit aucun titre.
from urllib.parse import urlparse

from vaultsafe.config import MAX_CSV_SIZE

if TYPE_CHECKING:
    from vaultsafe.identifiants import Identifiants


class ImportateurCSV:
    """Lit un CSV, prépare un aperçu et ajoute les comptes confirmés."""

    def __init__(self, gestion: Identifiants) -> None:
        self.gestion = gestion

    @staticmethod
    def creer_cle_doublon(titre: str, nom_utilisateur: str, site: str) -> tuple[str, str]:
        """Crée un petit repère pour reconnaître deux comptes identiques.

        Deux lignes sont considérées identiques lorsqu'elles utilisent le
        même site et le même nom d'utilisateur. Si le site manque, le titre
        prend sa place. Les majuscules et le slash final sont ignorés.
        """
        site_nettoye = site.strip().casefold().rstrip("/")
        titre_nettoye = titre.strip().casefold()
        utilisateur_nettoye = nom_utilisateur.strip().casefold()
        return site_nettoye or f"titre:{titre_nettoye}", utilisateur_nettoye

    def lire_csv_navigateur(
        self, source: str | Path
    ) -> tuple[list[dict[str, str]], int, str]:
        """Lit un export Chrome, Edge ou Firefox sans modifier la base.

        Le navigateur doit d'abord créer le fichier après confirmation de
        l'identité de l'utilisateur. VaultSafe se contente ensuite de lire les
        colonnes utiles et de préparer les comptes trouvés.
        """
        self.gestion.connexion.exiger_connexion()
        chemin = Path(source)

        # On arrête immédiatement si le fichier n'existe pas ou semble anormal.
        if not chemin.is_file():
            raise ValueError("Le fichier CSV est introuvable.")
        if chemin.stat().st_size > MAX_CSV_SIZE:
            raise ValueError("Le fichier CSV est trop volumineux.")

        try:
            # utf-8-sig accepte aussi la petite marque ajoutée par certains exports.
            with chemin.open("r", encoding="utf-8-sig", newline="") as fichier:
                # Chrome utilise généralement une virgule. Certains Windows
                # francophones utilisent un point-virgule : on accepte les deux.
                debut = fichier.read(4096)
                fichier.seek(0)
                separateur = ";" if debut.count(";") > debut.count(",") else ","
                lecteur = csv.DictReader(fichier, delimiter=separateur)

                # Sans première ligne de titres, on ne sait pas lire les colonnes.
                if not lecteur.fieldnames:
                    raise ValueError("Le fichier CSV ne contient aucun en-tête.")

                # Le dictionnaire relie un nom simplifié au vrai nom du fichier.
                # Cette boucle parcourt les en-têtes une fois. casefold permet
                # de reconnaître « Password » comme « password ».
                colonnes = {
                    nom.strip().casefold(): nom
                    for nom in lecteur.fieldnames
                    if nom and nom.strip()
                }
                colonne_mot_de_passe = colonnes.get("password")
                colonne_site = (
                    colonnes.get("url")
                    or colonnes.get("origin")
                    or colonnes.get("hostname")
                )
                colonne_utilisateur = (
                    colonnes.get("username")
                    or colonnes.get("user")
                    or colonnes.get("login")
                )
                colonne_titre = colonnes.get("name") or colonnes.get("title")
                colonne_notes = colonnes.get("note") or colonnes.get("notes")

                # Les trois navigateurs fournissent au minimum url et password.
                if not colonne_mot_de_passe or not colonne_site:
                    raise ValueError(
                        "Format non reconnu : les colonnes url et password sont obligatoires."
                    )

                # Firefox possède des colonnes particulières. Chrome et Edge
                # ont le même format ; leur nom de fichier aide à les distinguer.
                nom_fichier = chemin.name.casefold()
                if {"guid", "httprealm", "formactionorigin"} & set(colonnes):
                    navigateur = "Firefox"
                elif "edge" in nom_fichier:
                    navigateur = "Microsoft Edge"
                elif "chrome" in nom_fichier or "google" in nom_fichier:
                    navigateur = "Google Chrome"
                else:
                    navigateur = "Chrome, Edge ou Firefox"

                comptes = []
                lignes_invalides = 0
                # Chaque tour correspond à une ligne exportée par le navigateur.
                # Les lignes incomplètes sont comptées puis ignorées.
                for ligne in lecteur:
                    export_vaultsafe = ligne.get(colonnes.get("vaultsafe_csv", "")) == "1"
                    if export_vaultsafe:
                        ligne = {k: v[1:] if isinstance(v, str) and v.startswith("'") else v
                                 for k, v in ligne.items()}
                    # Une valeur absente devient simplement un texte vide.
                    mot_de_passe = str(ligne.get(colonne_mot_de_passe) or "")
                    site = str(ligne.get(colonne_site) or "").strip()
                    nom_utilisateur = (
                        str(ligne.get(colonne_utilisateur) or "").strip()
                        if colonne_utilisateur
                        else ""
                    )
                    titre = (
                        str(ligne.get(colonne_titre) or "").strip()
                        if colonne_titre
                        else ""
                    )
                    notes = (
                        str(ligne.get(colonne_notes) or "").strip()
                        if colonne_notes
                        else ""
                    )

                    # Sans site ou sans mot de passe, le compte n'est pas exploitable.
                    if not mot_de_passe or (not site and not export_vaultsafe):
                        lignes_invalides += 1
                        continue

                    # Firefox ne fournit pas toujours un titre : le nom du site suffit.
                    if not titre:
                        titre = urlparse(site).hostname or site

                    # La liste utilise exactement les noms déjà connus par Ajouter.
                    comptes.append(
                        {
                            "titre": titre,
                            "nom_utilisateur": nom_utilisateur,
                            "mot_de_passe": mot_de_passe,
                            "site": site,
                            "notes": notes or f"Importé depuis {navigateur}.",
                        }
                    )
        except (OSError, UnicodeError, csv.Error) as probleme:
            raise ValueError("Impossible de lire ce fichier CSV.") from probleme

        return comptes, lignes_invalides, navigateur

    def analyser_csv_navigateur(self, source: str | Path) -> dict[str, Any]:
        """Compte les nouveautés, doublons et erreurs avant toute importation."""
        comptes, invalides, navigateur = self.lire_csv_navigateur(source)

        # On fabrique les repères de tous les comptes déjà dans VaultSafe.
        # Un set permet de tester rapidement si un compte est déjà présent.
        reperes_connus = {
            self.creer_cle_doublon(item.titre, item.nom_utilisateur, item.site)
            for item in self.gestion.afficher_identifiants()
        }
        comptes_nouveaux = []
        doublons = 0

        # La même liste sert aussi à repérer un doublon à l'intérieur du CSV.
        # Le même set grandit au fil de la boucle : il détecte aussi les
        # doublons entre deux lignes du fichier importé.
        for compte in comptes:
            repere = self.creer_cle_doublon(
                compte["titre"], compte["nom_utilisateur"], compte["site"]
            )
            if repere in reperes_connus:
                doublons += 1
                continue
            reperes_connus.add(repere)
            comptes_nouveaux.append(compte)

        # Les comptes sont conservés en mémoire pour l'import après confirmation.
        return {
            "navigateur": navigateur,
            "total": len(comptes) + invalides,
            "nouveaux": len(comptes_nouveaux),
            "doublons": doublons,
            "invalides": invalides,
            "comptes": comptes_nouveaux,
        }

    def importer_csv_navigateur(self, apercu: dict[str, Any]) -> dict[str, Any]:
        """Ajoute uniquement les comptes que l'aperçu a classés comme nouveaux."""
        self.gestion.connexion.exiger_connexion()
        nombre_importe = self.gestion.ajouter_lot(apercu["comptes"])

        # L'interface n'a besoin que des nombres pour afficher son résumé final.
        return {
            "importes": nombre_importe,
            "doublons": apercu["doublons"],
            "invalides": apercu["invalides"],
        }
