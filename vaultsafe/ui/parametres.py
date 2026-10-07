"""Réglages Focus : lignes compactes, préférences et brouillon de sauvegarde."""
from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from vaultsafe.ui.composants import Choix, Interrupteur, LigneSouple, Nombre, Segments, Symbole, bouton, champ, defilement, etiquette, fichier, message
from shiboken6 import isValid


class PageParametres(QWidget):
    def __init__(self, app):
        super().__init__()
        self.setObjectName('page_reglages')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.app, self.en_cours = app, False
        self.controles = {}
        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(24, 16, 20, 12)
        disposition.setSpacing(10)
        entete = QHBoxLayout()
        entete.addWidget(etiquette('Paramètres', 'titre'), 1)
        self.statut = etiquette('', 'secondaire')
        entete.addWidget(self.statut)
        disposition.addLayout(entete)
        noms = [('Apparence', 'apparence'), ('Protection', 'protection'), ('Sauvegardes', 'sauvegardes'), ('Avancé', 'avance')]
        self.onglets = QFrame()
        self.onglets.setObjectName('onglets_reglages')
        onglets = QHBoxLayout(self.onglets)
        onglets.setContentsMargins(0, 0, 0, 0)
        onglets.setSpacing(8)
        groupe = QButtonGroup(self)
        self.boutons_onglets = {}
        for i, (libelle, cle) in enumerate(noms):
            b = bouton(libelle, role='onglet_reglages')
            b.setMinimumHeight(34)
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.clicked.connect(lambda _=False, index=i: self.pile.setCurrentIndex(index))
            groupe.addButton(b)
            self.boutons_onglets[cle] = b
            onglets.addWidget(b)
        onglets.addStretch()
        disposition.addWidget(self.onglets)
        self.pile = QStackedWidget()
        disposition.addWidget(self.pile, 1)
        self.pages = {}
        for _, cle in noms:
            contenu = QWidget()
            layout = QVBoxLayout(contenu)
            layout.setContentsMargins(0, 0, 6, 0)
            layout.setSpacing(0)
            self.pages[cle] = layout
            self.pile.addWidget(defilement(contenu))
        self.erreur = etiquette('', 'erreur')
        disposition.addWidget(self.erreur)
        p = app.preferences

        apparence = self.section('apparence', 'AFFICHAGE')
        self.theme = Segments([('Clair', 'light'), ('Sombre', 'dark')], p.get('theme', 'light'), replier=False)
        self.theme.setObjectName('themes_preference')
        from vaultsafe.ui.icones import icone
        for cle, b in self.theme.boutons.items():
            b.setProperty('role', 'theme_preference')
            b.setMinimumHeight(32)
            b.setIcon(icone('soleil' if cle == 'light' else 'lune'))
        self.ligne(apparence, 'Thème', 'Le même style sur tous les écrans.', self.theme, 'reglages')
        self.controles['theme'] = self.theme
        self.theme.changed.connect(lambda valeur: self.enregistrer({'theme': valeur}))
        taille = Nombre()
        taille.setRange(100, 200)
        taille.setSingleStep(25)
        taille.setSuffix(' %')
        taille.setValue(int(p.get('echelle', '100')))
        self.ligne(apparence, 'Taille de l’interface', 'Adaptée au zoom Windows.', taille, 'agrandir')
        self.preference('echelle', taille)
        confort = self.section('apparence', 'COMPORTEMENT')
        for cle, titre, description, defaut, symbole in (
                ('reduire_zone', 'Zone de notification', 'Garder VaultSafe accessible après réduction.', 'non', 'ecran'),
                ('notifications', 'Notifications', 'Afficher les confirmations utiles et les échéances.', 'oui', 'cloche')):
            case = Interrupteur(titre)
            case.setChecked(p.get(cle, defaut) == 'oui')
            self.ligne(confort, titre, description, case, symbole)
            self.preference(cle, case)
        icones = Interrupteur('Icônes en ligne')
        icones.setChecked(p.get('icones_reseau', 'non') == 'oui')
        self.ligne(confort, 'Icônes en ligne', 'Contacte les sites publics uniquement, sans identifiant ni mot de passe.', icones, 'globe')
        self.preference('icones_reseau', icones)
        confort.addWidget(etiquette('Les préférences sont enregistrées automatiquement.', 'secondaire'))

        protection = self.section('protection', 'Verrouillage et copies')
        self.delai = self.choix([(f'{n} min', str(n)) for n in (1, 5, 10, 15, 30, 60)] + [('Jamais', '0')], str(app.delai_inactivite()))
        self.ligne(protection, 'Verrouillage automatique', 'Appareil de confiance : désactivé par défaut. Vous choisissez le délai.', self.delai, 'verrou')
        self.actualiser_delai()
        self.delai.currentIndexChanged.connect(lambda _: self.enregistrer({app.cle_inactivite(): self.delai.currentData()}))
        copie = self.choix([(f'{n} s', str(n)) for n in (5, 15, 30, 60, 120)], p.get('presse_papiers_secondes', '30'))
        self.ligne(protection, 'Effacer les copies après', '', copie, 'copier')
        self.preference('presse_papiers_secondes', copie)
        acces = self.section('protection', 'Accès')
        self.appareil = Interrupteur('Appareil de confiance')
        self.appareil.setEnabled(False)
        self.ligne(acces, 'Appareil de confiance', 'Ouverture automatique avec ce compte Windows · 30 jours.', self.appareil, 'bouclier')
        self.appareil.toggled.connect(self.modifier_appareil)
        self.actualiser_appareil()
        self.ligne(acces, 'Mot de passe maître', '', self.action_bouton('Modifier', lambda: self.action('changer_maitre')), 'cle')
        self.ligne(acces, 'Clé de secours', 'Pour récupérer l’accès à vos données.', self.action_bouton('Créer / renouveler', lambda: self.action('creer_secours')), 'bouclier')
        self.ligne(acces, 'Générateur', '', self.action_bouton('Ouvrir', app.generateur), 'cle')

        sauvegardes = self.section('sauvegardes', 'Sauvegardes automatiques')
        self.backup_active = Interrupteur('Sauvegarde automatique')
        self.backup_active.setChecked(bool(p.get('backup_dossier')))
        self.ligne(sauvegardes, 'Sauvegarde automatique', 'Copies chiffrées après modification.', self.backup_active, 'bouclier')
        self.dossier_backup = champ(p.get('backup_dossier', ''), indication='Choisir un dossier')
        self.dossier_backup.setMinimumHeight(34)
        self.dossier_backup.setReadOnly(True)
        self.dossier_backup.setAccessibleName('Dossier de sauvegarde')
        dossier = QWidget()
        chemin = QHBoxLayout(dossier)
        chemin.setContentsMargins(0, 0, 0, 0)
        chemin.setSpacing(6)
        chemin.addWidget(self.dossier_backup, 1)
        chemin.addWidget(self.action_bouton('Parcourir', self.choisir_dossier))
        self.ligne(sauvegardes, 'Dossier', '', dossier, 'dossier', large=True)
        self.minutes, self.retention = Nombre(), Nombre()
        self.minutes.setRange(1, 1440)
        self.minutes.setValue(int(p.get('backup_minutes', '60')))
        self.minutes.setSuffix(' min')
        self.retention.setRange(1, 50)
        self.retention.setValue(int(p.get('backup_retention', '7')))
        self.ligne(sauvegardes, 'Intervalle', '', self.minutes, 'reglages')
        self.ligne(sauvegardes, 'Copies à conserver', '', self.retention, 'copier')
        self.backup_controles = [self.backup_active, dossier, self.minutes, self.retention]
        pied = QHBoxLayout()
        pied.setContentsMargins(0, 8, 0, 4)
        self.backup_etat = etiquette('', 'secondaire')
        pied.addWidget(self.backup_etat, 1)
        self.appliquer = self.action_bouton('Appliquer', self.appliquer_backup)
        pied.addWidget(self.appliquer)
        sauvegardes.addLayout(pied)
        self.backup_enregistre = self.valeurs_backup()
        self.backup_active.toggled.connect(self.backup_modifie)
        self.dossier_backup.textChanged.connect(self.backup_modifie)
        self.minutes.valueChanged.connect(self.backup_modifie)
        self.retention.valueChanged.connect(self.backup_modifie)
        self.backup_modifie()
        manuelles = self.section('sauvegardes', 'Copie complète')
        self.ligne(manuelles, 'Sauvegarder ou restaurer', 'Inclut les fiches, les pièces et l’historique.',
                   self.actions(('Sauvegarder', lambda: self.action('sauvegarder')), ('Restaurer', lambda: self.action('restaurer'))), 'dossier')
        transferts = self.section('sauvegardes', 'Import et export')
        self.ligne(transferts, 'Importer des fiches', 'CSV ou JSON, avec aperçu.', self.action_bouton('Importer', lambda: self.action('importer')), 'importer')
        self.format_export = self.choix([('JSON', 'json'), ('CSV', 'csv')], 'json')
        export = QWidget()
        actions_export = QHBoxLayout(export)
        actions_export.setContentsMargins(0, 0, 0, 0)
        actions_export.setSpacing(6)
        actions_export.addWidget(self.format_export)
        actions_export.addWidget(self.action_bouton('Exporter', lambda: self.action('exporter', self.format_export.currentData())))
        self.ligne(transferts, 'Exporter en clair', 'Les mots de passe seront lisibles.', export, 'ouvrir')

        extension = self.section('avance', 'Extension Chrome / Edge')
        self.extension_ids = champ(p.get('extension_ids') or 'egbpodcdijmeibnmfabhiignfppmclbl', indication='Identifiant de l’extension')
        self.extension_ids.setMinimumHeight(34)
        self.ligne(extension, 'Associer l’extension', 'Chaque remplissage demande une confirmation.', self.extension_ids, 'globe', large=True)
        self.extension_statut = etiquette('Liaison active' if app.liaison else 'Liaison désactivée', 'secondaire')
        extension.addWidget(self.extension_statut)
        extension.addWidget(self.actions(('Dossier', self.ouvrir_extension), ('Associer', self.associer), ('Déconnecter', self.dissocier)), alignment=Qt.AlignmentFlag.AlignRight)
        extension.addWidget(bouton('Guide de l’extension', self.guide_extension))
        mode_capture = self.choix([('Proposer un enregistrement', 'proposition'),
            ('Enregistrer les nouveaux comptes', 'automatique'), ('Détection désactivée', 'desactive')],
            p.get('capture_mode', 'proposition'))
        self.ligne(extension, 'Enregistrement des comptes', 'Automatique : nouveaux comptes uniquement ; modifications à vérifier.', mode_capture, 'enregistrer')
        self.preference('capture_mode', mode_capture)
        self.capture_exclus = champ(p.get('capture_exclus', '').replace('\n', ', '), indication='exemple.com, https://connexion.exemple.com')
        self.ligne(extension, 'Sites exclus', 'Origines exactes, séparées par une virgule.', self.capture_exclus, 'globe', large=True)
        extension.addWidget(self.actions(('Appliquer les exclusions', lambda: self.enregistrer({'capture_exclus': self.capture_exclus.text()}))), alignment=Qt.AlignmentFlag.AlignRight)
        gestion = self.section('avance', 'Gestion des données')
        demarrage = Interrupteur('Ouvrir au démarrage de Windows')
        demarrage.setChecked(p.get('demarrage_windows', 'non') == 'oui')
        self.ligne(gestion, 'Ouvrir au démarrage de Windows', '', demarrage, 'ouvrir')
        self.preference('demarrage_windows', demarrage)
        rappels = Interrupteur('Rappeler les échéances')
        rappels.setChecked(p.get('rappels', 'oui') == 'oui')
        self.ligne(gestion, 'Rappeler les échéances', '', rappels, 'note')
        self.preference('rappels', rappels)
        self.ligne(gestion, 'Autre fichier', '', self.actions(('Ouvrir', app.choisir_coffre), ('Créer', lambda: app.choisir_coffre(True))), 'dossier')
        self.ligne(gestion, 'Ancienne version', '', self.action_bouton('Importer', lambda: self.action('migration')), 'importer')
        self.ligne(gestion, 'Intégrité des données', '', self.action_bouton('Vérifier', lambda: app.executer(app.base.verifier_integrite,
            lambda _: message(app, 'Intégrité', 'Les données et les pièces ont été vérifiées.'))), 'bouclier')
        self.ligne(gestion, 'Réinitialiser', 'Effacement des données après confirmation.', self.action_bouton('Réinitialiser', lambda: self.action('reinitialiser'), 'danger'), 'corbeille')
        for layout in self.pages.values():
            layout.addStretch()

    def section(self, onglet, titre):
        label = etiquette(titre, 'section_preference')
        label.setContentsMargins(0, 16, 0, 6)
        self.pages[onglet].addWidget(label)
        return self.pages[onglet]

    def ligne(self, layout, titre, description, controle, symbole, large=False):
        cadre = QFrame()
        cadre.setObjectName('ligne_preference')
        disposition = QVBoxLayout(cadre)
        disposition.setContentsMargins(0, 0, 0, 0)
        ligne = LigneSouple(570)
        ligne.ligne.setSpacing(12)
        texte = QWidget()
        entete = QHBoxLayout(texte)
        entete.setContentsMargins(0, 0, 0, 0)
        entete.setSpacing(12)
        entete.addWidget(Symbole(symbole, taille=20))
        libelles = QVBoxLayout()
        libelles.setSpacing(2)
        libelles.addWidget(etiquette(titre, 'preference'))
        if description:
            libelles.addWidget(etiquette(description, 'secondaire'))
        entete.addLayout(libelles, 1)
        ligne.ligne.addWidget(texte, 1)
        ligne.ligne.addWidget(controle, 1 if large else 0)
        disposition.addWidget(ligne)
        layout.addWidget(cadre)

    def action_bouton(self, libelle, action, role='preference_action'):
        b = bouton(libelle, action, role)
        b.setMinimumHeight(32)
        return b

    def actions(self, *elements):
        widget = QWidget()
        ligne = QHBoxLayout(widget)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(6)
        for texte, action in elements:
            ligne.addWidget(self.action_bouton(texte, action))
        return widget

    def choix(self, valeurs, selection):
        control = Choix()
        control.setMinimumHeight(34)
        for texte, valeur in valeurs:
            control.addItem(texte, valeur)
        if control.findData(selection) < 0:
            control.addItem(str(selection), selection)
        control.setCurrentIndex(control.findData(selection))
        return control

    def preference(self, cle, controle):
        self.controles[cle] = controle
        if isinstance(controle, Interrupteur):
            controle.toggled.connect(lambda valeur: self.enregistrer({cle: 'oui' if valeur else 'non'}))
        elif isinstance(controle, Nombre):
            controle.valueChanged.connect(lambda valeur: self.enregistrer({cle: str(valeur)}))
        else:
            controle.currentIndexChanged.connect(lambda: self.enregistrer({cle: controle.currentData()}))

    def restaurer_controle(self, cle, valeur):
        controle = self.controles[cle]
        with QSignalBlocker(controle):
            if isinstance(controle, Interrupteur):
                controle.setChecked(valeur == 'oui')
            elif isinstance(controle, Segments):
                controle.boutons[valeur].setChecked(True)
            elif isinstance(controle, Nombre):
                controle.setValue(int(valeur))
            else:
                controle.setCurrentIndex(controle.findData(valeur))

    def valeurs_backup(self):
        return {'backup_dossier': self.dossier_backup.text().strip() if self.backup_active.isChecked() else '',
                'backup_minutes': str(self.minutes.value()), 'backup_retention': str(self.retention.value())}

    def backup_modifie(self, *_):
        en_attente = self.valeurs_backup() != self.backup_enregistre or self.backup_active.isChecked() != bool(self.backup_enregistre['backup_dossier'])
        self.backup_etat.setText('À appliquer' if en_attente else 'Activée' if self.backup_active.isChecked() else 'Désactivée')
        self.appliquer.setEnabled(en_attente and not self.en_cours)
        if en_attente and not self.en_cours:
            self.statut.clear()

    def appliquer_backup(self):
        if self.backup_active.isChecked() and not self.dossier_backup.text().strip():
            self.erreur.setText('Choisissez un dossier avant d’activer les sauvegardes.')
            return
        def fini():
            self.backup_enregistre = {k: self.app.preferences[k] for k in self.valeurs_backup()}
            self.backup_modifie()
        self.enregistrer(self.valeurs_backup(), apres=fini)

    def enregistrer(self, valeurs, apres=None):
        if self.en_cours:
            return
        app, parametres = self.app, self.app.parametres
        defauts = {'theme': app.theme, 'echelle': str(app.echelle), 'inactivite': '5', 'inactivite_confiance': '0', 'presse_papiers_secondes': '30',
                   'reduire_zone': 'non', 'rappels': 'oui', 'notifications': 'oui', 'demarrage_windows': 'non', 'icones_reseau': 'non', 'capture_mode': 'proposition', 'capture_exclus': ''}
        anciens = {k: app.preferences.get(k, defauts.get(k, '')) for k in valeurs}
        self.en_cours = True
        self.statut.setText('Enregistrement…')
        self.erreur.clear()
        for controle in list(self.controles.values()) + self.backup_controles:
            controle.setEnabled(False)
        self.appliquer.setEnabled(False)
        def travail():
            if 'demarrage_windows' in valeurs and app.integrations_windows:
                from vaultsafe.windows_local import demarrage_windows
                demarrage_windows(valeurs['demarrage_windows'] == 'oui')
            try:
                parametres.enregistrer_lot(valeurs)
            except Exception:
                if 'demarrage_windows' in valeurs and app.integrations_windows:
                    demarrage_windows(anciens['demarrage_windows'] == 'oui')
                raise
            return {k: parametres.valider(k, v) for k, v in valeurs.items()}
        def liberer():
            self.en_cours = False
            for controle in list(self.controles.values()) + self.backup_controles:
                controle.setEnabled(True)
            self.backup_modifie()
        def fini(enregistres):
            if not isValid(self):
                return
            app.preferences.update(enregistres)
            if 'capture_exclus' in enregistres:
                self.capture_exclus.setModified(False)
            if ('capture_mode' in valeurs or 'capture_exclus' in valeurs) and app.captures_browser:
                app.captures_browser.vider()
            if 'theme' in valeurs or 'echelle' in valeurs:
                app.theme = app.preferences.get('theme', 'light')
                app.echelle = int(app.preferences.get('echelle', '100'))
                app.appliquer_theme()
                app.memoriser_interface()
            if 'icones_reseau' in valeurs:
                app.icones_sites.annuler()
            if 'inactivite' in valeurs or 'inactivite_confiance' in valeurs:
                app.inactivite.stop()
                app.relancer_minuteur()
            liberer()
            self.statut.setText('Enregistré')
            if apres:
                apres()
            app.actualiser()
        def echec(texte):
            if not isValid(self):
                return
            for cle, valeur in anciens.items():
                if cle in self.controles:
                    self.restaurer_controle(cle, valeur)
            liberer()
            self.statut.setText('Non enregistré')
            self.erreur.setText(texte)
        app.executer(travail, fini, echec)

    def choisir_dossier(self):
        dossier = fichier(self.app, 'Dossier des sauvegardes', repertoire=True)
        if dossier and isValid(self):
            self.dossier_backup.setText(dossier)

    def action(self, nom, *args):
        from vaultsafe.ui import outils
        getattr(outils, nom)(self.app, *args)

    def actualiser_capture(self):
        if self.en_cours:
            return
        mode = self.app.preferences.get('capture_mode', 'proposition')
        if self.controles['capture_mode'].currentData() != mode:
            self.restaurer_controle('capture_mode', mode)
        if not self.capture_exclus.hasFocus() and not self.capture_exclus.isModified():
            texte = self.app.preferences.get('capture_exclus', '').replace('\n', ', ')
            if self.capture_exclus.text() != texte:
                self.capture_exclus.setText(texte)

    def actualiser_delai(self):
        self.controles.pop('inactivite', None)
        self.controles.pop('inactivite_confiance', None)
        self.controles[self.app.cle_inactivite()] = self.delai
        with QSignalBlocker(self.delai):
            self.delai.setCurrentIndex(max(0, self.delai.findData(str(self.app.delai_inactivite()))))

    def actualiser_appareil(self):
        def fini(expire):
            if isValid(self):
                self.app.definir_confiance(expire)
                with QSignalBlocker(self.appareil):
                    self.appareil.setChecked(expire is not None)
                self.appareil.setEnabled(True)
        self.app.taches.soumettre(self.app.appareil.etat, fini)

    def modifier_appareil(self, actif):
        self.appareil.setEnabled(False)
        self.statut.setText('Enregistrement…')
        appareil = self.app.appareil
        def travail():
            if actif:
                return appareil.autoriser()
            appareil.revoquer()
            return None
        def fini(expire):
            if isValid(self):
                self.app.definir_confiance(expire)
                with QSignalBlocker(self.appareil):
                    self.appareil.setChecked(expire is not None)
                self.appareil.setEnabled(True)
                self.erreur.clear()
                self.statut.setText('Enregistré')
        def echec(texte):
            if isValid(self):
                self.statut.setText('Non enregistré')
                self.erreur.setText(texte)
                self.actualiser_appareil()
        self.app.executer(travail, fini, echec)


    def associer(self):
        ids = self.extension_ids.text().strip()
        app = self.app
        from vaultsafe.liaison_navigateur import installer_hote, LiaisonLocale
        def travail():
            installer_hote(ids)
            app.parametres.enregistrer_parametre('extension_ids', ids)
        def fini(_):
            if app.liaison:
                app.liaison.arreter()
            app.liaison = LiaisonLocale(ids, notifier=app.demande_navigateur.emit)
            app.preferences['extension_ids'] = ids
            self.extension_statut.setText('Liaison active')
        app.mutation(travail, fini, self)

    def dissocier(self):
        app = self.app
        from vaultsafe.liaison_navigateur import desinstaller_hote
        def travail():
            desinstaller_hote()
            app.parametres.enregistrer_parametre('extension_ids', '')
        def fini(_):
            if app.liaison:
                app.liaison.arreter()
                app.liaison = None
            self.extension_ids.clear()
            app.preferences['extension_ids'] = ''
            self.extension_statut.setText('Liaison désactivée')
        app.mutation(travail, fini, self)

    def ouvrir_extension(self):
        import os
        from vaultsafe.windows_local import executable_courant
        dossier = executable_courant().parent / 'extension'
        if dossier.is_dir():
            os.startfile(dossier)
        else:
            message(self, 'Extension', 'Le dossier extension doit accompagner l’exécutable.')

    def guide_extension(self):
        from vaultsafe.ui.guide_extension import ouvrir
        ouvrir(self.app)
