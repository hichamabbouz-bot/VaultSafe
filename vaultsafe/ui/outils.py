"""Outils Qt chargés à leur ouverture, avec services de coffre partagés."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QGridLayout, QListWidget, QListWidgetItem, QWidget
from vaultsafe.ui.composants import Dialogue, Nombre, bouton, champ, demander, etiquette, fichier, message
from vaultsafe.ui.fiches import FormulaireFiche as FormulaireFiche, DetailsFiche as DetailsFiche, choix, ligne


class Generateur(Dialogue):
    def __init__(self, app, parent=None, inserer=None):
        super().__init__(parent or app, 'Générateur', (500, 530))
        self.app, self.inserer = app, inserer
        self.mode = choix([('Mot de passe', 'caracteres'), ('Phrase de passe EFF', 'phrase')], 'caracteres')
        self.corps.addWidget(self.mode)
        self.longueur = Nombre()
        self.longueur.setRange(12, 128)
        self.longueur.setValue(24)
        self.label_longueur = etiquette('Longueur du mot de passe', 'secondaire')
        self.corps.addWidget(self.label_longueur)
        self.corps.addWidget(self.longueur)
        self.categories = {}
        self.cadre_categories = QWidget()
        grille = QGridLayout(self.cadre_categories)
        grille.setContentsMargins(0, 0, 0, 0)
        for cle, texte, actif in (('minuscules', 'Minuscules', True), ('majuscules', 'Majuscules', True),
                                  ('chiffres', 'Chiffres', True), ('symboles', 'Symboles', True),
                                  ('ambigus', 'Inclure les caractères ambigus (I, l, 1, O, 0…)', False)):
            case = QCheckBox(texte)
            case.setChecked(actif)
            self.categories[cle] = case
            numero = len(self.categories) - 1
            grille.addWidget(case, numero // 2, numero % 2, 1, 2 if cle == 'ambigus' else 1)
        self.corps.addWidget(self.cadre_categories)
        self.nombre = Nombre()
        self.nombre.setRange(6, 12)
        self.nombre.setValue(6)
        self.label_nombre = etiquette('Nombre de mots', 'secondaire')
        self.corps.addWidget(self.label_nombre)
        self.corps.addWidget(self.nombre)
        self.separateur = choix([('Tiret', '-'), ('Espace', ' '), ('Point', '.'), ('Souligné', '_')], '-')
        self.corps.addWidget(self.separateur)
        self.resultat = champ(secret=True)
        self.resultat.setReadOnly(True)
        voir = bouton('Afficher')
        voir.setCheckable(True)
        def afficher_resultat(actif):
            self.resultat.setEchoMode(self.resultat.EchoMode.Normal if actif else self.resultat.EchoMode.Password)
            voir.setText('Masquer' if actif else 'Afficher')
        voir.toggled.connect(afficher_resultat)
        self.corps.addWidget(ligne(self.resultat, voir))
        self.information = etiquette('', 'secondaire')
        self.corps.addWidget(self.information)
        self.corps.addWidget(ligne(bouton('Générer', self.generer, 'principal'),
                                  bouton('Copier', lambda: app.copier_texte(self.resultat.text()), symbole='copier')))
        self.actions.addWidget(bouton('Fermer', self.reject))
        if inserer:
            self.actions.addWidget(bouton('Utiliser', self.utiliser, 'principal'))
        self.mode.currentIndexChanged.connect(self.actualiser_mode)
        self.actualiser_mode()
        self.generer()

    def actualiser_mode(self):
        phrase = self.mode.currentData() == 'phrase'
        self.longueur.setVisible(not phrase)
        self.label_longueur.setVisible(not phrase)
        self.cadre_categories.setVisible(not phrase)
        for case in self.categories.values():
            case.setEnabled(not phrase)
        self.nombre.setVisible(phrase)
        self.label_nombre.setVisible(phrase)
        self.separateur.setVisible(phrase)

    def generer(self):
        from vaultsafe.generateur_avance import entropie_phrase, generer_configurable, generer_phrase
        mode = self.mode.currentData()
        longueur, nombre, separateur = self.longueur.value(), self.nombre.value(), self.separateur.currentData()
        categories = {k: c.isChecked() for k, c in self.categories.items()}
        def travail():
            if mode == 'phrase':
                return generer_phrase(nombre, separateur), f'{nombre} mots tirés au hasard · {entropie_phrase(nombre)} bits'
            return generer_configurable(longueur, **categories), f'{longueur} caractères tirés au hasard'
        def fini(valeur):
            if self.actif:
                self.resultat.setText(valeur[0])
                self.information.setText(valeur[1])
                self.erreur.clear()
        self.app.executer(travail, fini, self.erreur.setText)

    def utiliser(self):
        if self.resultat.text() and self.app.ouvert:
            self.inserer(self.resultat.text())
            self.accept()

    def nettoyer(self):
        self.inserer = None
        super().nettoyer()


class Dossiers(Dialogue):
    def __init__(self, app):
        super().__init__(app, 'Dossiers', (600, 500))
        self.app = app
        self.dossiers = list(app.vue['dossiers'])
        self.liste = QListWidget()
        self.utiliser_liste(self.liste)
        self.disposition.insertWidget(2, ligne(bouton('Créer', self.creer), bouton('Renommer / déplacer', self.modifier), bouton('Supprimer', self.supprimer, 'danger')))
        self.actions.addWidget(bouton('Fermer', self.reject))
        self.afficher(self.dossiers)

    def afficher(self, dossiers):
        if not self.actif:
            return
        self.dossiers = dossiers
        self.liste.clear()
        noms = {d['id']: d['nom'] for d in dossiers}
        for d in dossiers:
            texte = (noms.get(d['parent'], '') + ' / ' if d['parent'] else '') + d['nom']
            entree = QListWidgetItem(texte)
            entree.setData(Qt.ItemDataRole.UserRole, d)
            self.liste.addItem(entree)

    def charger(self):
        self.app.executer(self.app.base.lire_dossiers, self.afficher, self.erreur.setText)

    def selection(self):
        entree = self.liste.currentItem()
        return entree.data(Qt.ItemDataRole.UserRole) if entree else None

    def editer(self, dossier=None):
        popup = Dialogue(self, 'Modifier le dossier' if dossier else 'Créer un dossier', (500, 380))
        nom = champ(dossier['nom'] if dossier else '')
        parent = choix([('À la racine', '')] + [(d['nom'], d['id']) for d in self.dossiers if not dossier or d['id'] != dossier['id']], dossier['parent'] if dossier else '')
        popup.corps.addWidget(etiquette('Nom'))
        popup.corps.addWidget(nom)
        popup.corps.addWidget(etiquette('Dossier parent'))
        popup.corps.addWidget(parent)
        def enregistrer():
            base, valeur, cible = self.app.base, nom.text(), parent.currentData()
            def travail():
                if dossier:
                    return base.modifier_dossier(dossier['id'], valeur, cible)
                return base.creer_dossier(valeur, cible)
            def fini(_):
                popup.accept()
                self.charger()
            self.app.mutation(travail, fini, popup)
        popup.actions.addWidget(bouton('Annuler', popup.reject))
        popup.actions.addWidget(bouton('Enregistrer', enregistrer, 'principal'))
        popup.ouvrir()

    def creer(self):
        self.editer()

    def modifier(self):
        dossier = self.selection()
        if dossier:
            self.editer(dossier)

    def supprimer(self):
        dossier = self.selection()
        if dossier and message(self, 'Supprimer le dossier', 'Les fiches seront conservées sans ce dossier. Les sous-dossiers doivent être déplacés avant la suppression. Continuer ?', True):
            base = self.app.base
            self.app.mutation(lambda: base.supprimer_dossier(dossier['id']), lambda _: self.charger(), self)


class Corbeille(Dialogue):
    def __init__(self, app):
        super().__init__(app, 'Corbeille', (620, 540))
        self.app = app
        self.liste = QListWidget()
        self.utiliser_liste(self.liste)
        self.disposition.insertWidget(1, etiquette('Conservées chiffrées jusqu’à la suppression définitive.', 'secondaire'))
        self.disposition.insertWidget(3, ligne(bouton('Restaurer', self.restaurer, 'principal'), bouton('Supprimer', self.purger, 'danger'), bouton('Vider', lambda: self.purger(True), 'danger')))
        self.actions.addWidget(bouton('Fermer', self.reject))

    def charger(self):
        base = self.app.base
        def travail():
            return [(r['fiche']['id'], r['fiche']['titre'], r['date_suppression']) for r in base.lire_corbeille()]
        def fini(valeurs):
            if self.actif:
                self.liste.clear()
                for identifiant, titre, date_suppression in valeurs:
                    entree = QListWidgetItem(titre + ' · ' + date_suppression)
                    entree.setData(Qt.ItemDataRole.UserRole, identifiant)
                    self.liste.addItem(entree)
                self.erreur.setText('La corbeille est vide.' if not valeurs else '')
        self.app.executer(travail, fini, self.erreur.setText)

    def selection(self):
        entree = self.liste.currentItem()
        return entree.data(Qt.ItemDataRole.UserRole) if entree else None

    def restaurer(self):
        identifiant = self.selection()
        if identifiant:
            base = self.app.base
            self.app.mutation(lambda: base.restaurer_fiche(identifiant), lambda _: self.charger(), self)

    def purger(self, tout=False):
        identifiant = None if tout else self.selection()
        if not tout and not identifiant:
            return
        confirmation = demander(self, 'Suppression définitive', 'Saisissez SUPPRIMER. Les fiches concernées, leur historique et leurs pièces seront définitivement supprimés :')
        if confirmation == 'SUPPRIMER':
            base = self.app.base
            self.app.mutation(lambda: base.purger_corbeille(identifiant, confirmation), lambda _: self.charger(), self)


def afficher_secours(app, cle):
    popup = Dialogue(app, 'Votre clé de secours', (650, 440))
    popup.corps.addWidget(etiquette('Conservez cette clé maintenant', 'titre'))
    popup.corps.addWidget(etiquette('Cette clé récupère ce coffre sans son mot de passe. Elle ne sera plus affichée après fermeture. Gardez-la séparément du coffre.', 'secondaire'))
    entree = champ(cle, True)
    entree.setReadOnly(True)
    popup.corps.addWidget(entree)
    voir = QCheckBox('Afficher la clé')
    voir.toggled.connect(lambda actif: entree.setEchoMode(entree.EchoMode.Normal if actif else entree.EchoMode.Password))
    popup.corps.addWidget(voir)
    popup.corps.addWidget(bouton('Copier la clé', lambda: app.copier_texte(entree.text())))
    def sauvegarder():
        destination = fichier(popup, 'Enregistrer la clé en clair', 'Texte (*.txt)', True, 'VaultSafe-cle-secours.txt')
        if destination:
            from vaultsafe.operations_fichiers import ecrire_atomique
            base, valeur = app.base, entree.text()
            def travail():
                if Path(destination).resolve() == base.chemin:
                    raise ValueError('La clé ne peut pas remplacer le coffre.')
                ecrire_atomique(destination, ('VaultSafe — clé de secours\n\n' + valeur + '\n').encode('utf-8'))
            app.executer(travail, lambda _: popup.erreur.setText('Clé enregistrée en clair ; conservez-la séparément du coffre.'), popup.erreur.setText)
    popup.corps.addWidget(bouton('Enregistrer la clé', sauvegarder))
    popup.actions.addWidget(bouton('J’ai conservé la clé', popup.accept, 'principal'))
    popup.ouvrir()


def creer_secours(app):
    if not app.ouvert:
        return
    if not message(app, 'Créer / renouveler la clé', 'Une ancienne clé ne récupérera plus cette version du coffre. Elle reste liée aux anciennes sauvegardes. Continuer ?', True):
        return
    mot = demander(app, 'Créer la clé de secours', 'Votre mot de passe maître :', True)
    if mot is not None and app.ouvert:
        base = app.base
        app.mutation(lambda: base.creer_cle_recuperation(mot), lambda cle: afficher_secours(app, cle))


class Recuperation(Dialogue):
    def __init__(self, app):
        super().__init__(app, 'Récupérer le coffre', (560, 540))
        self.app = app
        self.corps.addWidget(etiquette('Utilisez la clé VS2 créée pour ce coffre. Une nouvelle clé remplacera l’ancienne.', 'secondaire'))
        self.cle = champ(secret=True, indication='Clé de secours VS2-…')
        self.nouveau = champ(secret=True, indication='Nouveau mot de passe · 12 caractères minimum')
        self.confirmation = champ(secret=True, indication='Confirmer le nouveau mot de passe')
        for entree in (self.cle, self.nouveau, self.confirmation):
            self.corps.addWidget(entree)
        self.sauver = bouton('Récupérer', self.recuperer, 'principal')
        self.actions.addWidget(bouton('Annuler', self.reject))
        self.actions.addWidget(self.sauver)

    def recuperer(self):
        if not self.sauver.isEnabled():
            return
        nouveau, cle = self.nouveau.text(), self.cle.text()
        if nouveau != self.confirmation.text():
            self.erreur.setText('Les mots de passe ne correspondent pas.')
            return
        try:
            self.app.connexion.verifier_longueur(nouveau)
        except ValueError as probleme:
            self.erreur.setText(str(probleme))
            return
        self.sauver.setEnabled(False)
        base, generation = self.app.base, self.app.taches.generation
        def travail():
            if generation != self.app.taches.generation or not self.actif:
                raise ValueError('Récupération annulée avant traitement.')
            cle_neuve = base.recuperer_coffre(cle, nouveau)
            if generation != self.app.taches.generation or not self.actif:
                base.verrouiller()
                raise ValueError('Récupération annulée.')
            return base.lire_vue(), cle_neuve
        def fini(valeur):
            self.accept()
            self.app.session_ouverte(valeur[0])
            afficher_secours(self.app, valeur[1])
        def echec(texte):
            self.sauver.setEnabled(True)
            self.erreur.setText(texte)
        self.app.executer(travail, fini, echec)


def changer_maitre(app):
    popup = Dialogue(app, 'Modifier le mot de passe maître', (570, 510))
    ancien = champ(secret=True, indication='Mot de passe actuel')
    nouveau = champ(secret=True, indication='Nouveau mot de passe · 12 caractères minimum')
    confirmation = champ(secret=True, indication='Confirmer le nouveau mot de passe')
    for entree in (ancien, nouveau, confirmation):
        popup.corps.addWidget(entree)
    def enregistrer():
        if nouveau.text() != confirmation.text():
            popup.erreur.setText('Les mots de passe ne correspondent pas.')
            return
        connexion, actuel, futur = app.connexion, ancien.text(), nouveau.text()
        app.mutation(lambda: connexion.changer_mot_de_passe(actuel, futur), lambda _: popup.accept(), popup)
    popup.actions.addWidget(bouton('Annuler', popup.reject))
    popup.actions.addWidget(bouton('Enregistrer', enregistrer, 'principal'))
    popup.ouvrir()


def importer(app):
    from vaultsafe.ui.transferts import importer as action
    action(app)


def exporter(app, format_='json'):
    from vaultsafe.ui.transferts import exporter as action
    action(app, format_)


def migration(app):
    from vaultsafe.ui.transferts import migration as action
    action(app)


def sauvegarder(app):
    destination = fichier(app, 'Sauvegarde chiffrée', 'Coffre chiffré (*.vaultsafe)', True, 'VaultSafe-sauvegarde.vaultsafe')
    if destination and app.ouvert:
        base = app.base
        app.executer(lambda: base.exporter_sauvegarde(destination),
            lambda _: message(app, 'Sauvegarde', 'Le coffre complet a été sauvegardé avec son chiffrement.'))


def restaurer(app):
    source = fichier(app, 'Restaurer une sauvegarde', 'Coffre chiffré (*.vaultsafe *.db)')
    if not source:
        return
    if not message(app, 'Restaurer le coffre actif', 'La sauvegarde remplacera le coffre ouvert. Conservez une sauvegarde des données actuelles avant de continuer.', True):
        return
    mot = demander(app, 'Restaurer la sauvegarde', 'Mot de passe maître de la sauvegarde :', True)
    if mot is not None and app.ouvert:
        base = app.base
        app.executer(lambda: base.restaurer_sauvegarde(source, mot), lambda _: app.verrouiller())


def reinitialiser(app):
    mot = demander(app, 'Réinitialiser le coffre actif', 'Votre mot de passe maître :', True)
    if mot is None or not app.ouvert:
        return
    confirmation = demander(app, 'Effacement du coffre actif', 'Saisissez REINITIALISER pour effacer définitivement toutes ses fiches, pièces et paramètres :')
    if confirmation == 'REINITIALISER' and app.ouvert:
        base = app.base
        def travail():
            base.authentifier_action(mot)
            base.reinitialiser(confirmation)
        def fini(_):
            app.verrouiller()
            app.login(existe=False)
        app.executer(travail, fini)
