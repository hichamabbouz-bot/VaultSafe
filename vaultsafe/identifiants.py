"""Service des fiches du coffre, compatible avec les écrans existants."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from vaultsafe.connexion import Connexion
from vaultsafe.database import BaseDeDonnees
from vaultsafe.modele import maintenant, normaliser_fiche, verifier_fiche
from vaultsafe.recherche import filtrer_et_trier

date_actuelle = maintenant


@dataclass(slots=True)
class Identifiant:
    id: str
    titre: str
    nom_utilisateur: str = ''
    mot_de_passe: str = ''
    site: str = ''
    notes: str = ''
    date_creation: str = field(default_factory=date_actuelle)
    date_modification: str = field(default_factory=date_actuelle)
    type: str = 'connexion'
    dossier: str = ''
    tags: list[str] = field(default_factory=list)
    favori: bool = False
    champs: list[dict] = field(default_factory=list)
    totp: dict = field(default_factory=dict)
    expiration: str = ''
    pieces_jointes: list[dict] = field(default_factory=list)
    presentation: dict = field(default_factory=dict)


class Identifiants:
    def __init__(self, base: BaseDeDonnees, connexion: Connexion):
        self.base = base
        self.connexion = connexion

    def verifier_identifiant(self, identifiant):
        identifiant.titre = identifiant.titre.strip()
        identifiant.nom_utilisateur = identifiant.nom_utilisateur.strip()
        identifiant.site = identifiant.site.strip()
        verifier_fiche(asdict(identifiant))

    def dictionnaire_vers_identifiant(self, valeurs):
        return Identifiant(**normaliser_fiche(valeurs))

    def identifiant_vers_dictionnaire(self, identifiant):
        return asdict(identifiant)

    def preparer_fiche(self, champs):
        valeurs = {'id': str(uuid4()), 'titre': '', 'date_creation': date_actuelle(),
                   'date_modification': date_actuelle()}
        valeurs.update({k: v for k, v in champs.items() if k != 'id'})
        fiche = Identifiant(**valeurs)
        self.verifier_identifiant(fiche)
        return fiche

    def ajouter_identifiant(self, **champs: Any):
        self.connexion.exiger_connexion()
        fiche = self.preparer_fiche(champs)
        self.base.ajouter_identifiant(asdict(fiche))
        return fiche

    def ajouter_lot(self, fiches):
        self.connexion.exiger_connexion()
        valeurs = [asdict(self.preparer_fiche(f)) for f in fiches]
        return self.base.ajouter_lot(valeurs)

    def afficher_identifiant(self, identifiant_id):
        self.connexion.exiger_connexion()
        valeurs = self.base.afficher_identifiant(identifiant_id)
        if valeurs is None:
            raise ValueError('Fiche introuvable.')
        return self.dictionnaire_vers_identifiant(valeurs)

    def afficher_identifiants(self, recherche='', tri='recent', *, type_fiche='', dossier=None,
                             tag='', favoris=False):
        self.connexion.exiger_connexion()
        fiches = [self.dictionnaire_vers_identifiant(v) for v in self.base.afficher_identifiants()]
        fiches = [f for f in fiches if (not type_fiche or f.type == type_fiche)
                  and (dossier is None or f.dossier == dossier)
                  and (not tag or tag.casefold() in [t.casefold() for t in f.tags])
                  and (not favoris or f.favori)]
        return filtrer_et_trier(fiches, recherche, tri)

    def modifier_identifiant(self, identifiant_id, **champs: Any):
        fiche = self.afficher_identifiant(identifiant_id)
        for nom, valeur in champs.items():
            if nom not in ('id', 'date_creation', 'date_modification', 'pieces_jointes') and hasattr(fiche, nom):
                setattr(fiche, nom, valeur)
        fiche.date_modification = date_actuelle()
        self.verifier_identifiant(fiche)
        self.base.modifier_identifiant(asdict(fiche))
        return fiche

    def supprimer_identifiant(self, identifiant_id):
        self.connexion.exiger_connexion()
        self.base.supprimer_identifiant(identifiant_id)

    def basculer_favori(self, identifiant_id):
        fiche = self.afficher_identifiant(identifiant_id)
        return self.modifier_identifiant(identifiant_id, favori=not fiche.favori)
