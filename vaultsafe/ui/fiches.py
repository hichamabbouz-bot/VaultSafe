"""Fiche unique : saisie, détails, historique et pièces du même service."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox, QGridLayout, QHBoxLayout, QListWidget, QLineEdit,
    QVBoxLayout, QWidget,
)
from vaultsafe.modele import MODELES, TYPES
from vaultsafe.ui.composants import Choix, Depliable, Dialogue, Nombre, apercu_note, bouton, champ, demander, editer_note, etiquette, fichier, message, texte


def choix(valeurs, selection):
    entree = Choix()
    for libelle, valeur in valeurs:
        entree.addItem(libelle, valeur)
    entree.setCurrentIndex(max(0, entree.findData(selection)))
    return entree


def ligne(*elements):
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    for element in elements:
        layout.addWidget(element)
    return widget


def ouvrir_site(parent, valeur):
    valeur = valeur.strip()
    url = QUrl(valeur if '://' in valeur else 'https://' + valeur)
    if url.scheme() not in ('https', 'http') or not url.host() or url.userInfo():
        parent.erreur.setText('Seules les adresses web http/https sans identifiants sont ouvertes.')
        return
    QDesktopServices.openUrl(url)


class ChoisirType(Dialogue):
    def __init__(self, app, appliquer=None, parent=None):
        super().__init__(parent or app, 'Nouvelle fiche' if appliquer is None else 'Type de fiche', (520, 390))
        self.app, self.appliquer = app, appliquer
        self.corps.addWidget(etiquette('Quel type de fiche souhaitez-vous créer ?', 'secondaire'))
        grille = QGridLayout()
        grille.setSpacing(10)
        for i, (cle, libelle) in enumerate(TYPES.items()):
            symbole = {'connexion': 'cle', 'note': 'note', 'carte': 'carte', 'identite': 'personne',
                       'licence': 'cle', 'wifi': 'reglages', 'serveur': 'reglages'}[cle]
            b = bouton(libelle, lambda _=False, k=cle: self.choisir(k), 'type_fiche', symbole)
            b.setMinimumHeight(48)
            grille.addWidget(b, i // 2, i % 2)
        self.corps.addLayout(grille)
        self.actions.addWidget(bouton('Annuler', self.reject))

    def choisir(self, type_fiche):
        self.accept()
        if self.appliquer:
            self.appliquer(type_fiche)
        else:
            FormulaireFiche(self.app, type_initial=type_fiche).ouvrir()


class FormulaireFiche(Dialogue):
    def __init__(self, app, fiche=None, *, dupliquer=False, parent=None, type_initial='connexion'):
        super().__init__(parent or app, 'Modifier la fiche' if fiche and not dupliquer else 'Nouvelle fiche', (520, 570))
        self.ajuster_contenu = True
        self.app = app
        self.identifiant = fiche.id if fiche and not dupliquer else None
        valeurs = asdict(fiche) if fiche else {}
        self.entrees = {}
        self.entrees['type'] = choix([(v, k) for k, v in TYPES.items()], valeurs.get('type', type_initial))
        self.entrees['type'].setParent(self)
        self.entrees['type'].hide()
        entete = QHBoxLayout()
        self.type_libelle = etiquette('', 'secondaire')
        entete.addWidget(self.type_libelle, 1)
        entete.addWidget(bouton('Changer le type', self.choisir_type, 'discret'))
        self.corps.addLayout(entete)
        self.entrees['titre'] = champ(valeurs.get('titre', '') + (' · copie' if dupliquer else ''))
        self.essentiels = QGridLayout()
        self.essentiels.setContentsMargins(0, 0, 0, 0)
        self.essentiels.setVerticalSpacing(10)
        self.essentiels.setColumnStretch(1, 1)
        self.corps.addLayout(self.essentiels)
        label_titre = etiquette('Titre *', 'secondaire')
        label_titre.setFixedWidth(104)
        self.essentiels.setHorizontalSpacing(6)
        self.essentiels.addWidget(label_titre, 0, 0)
        self.essentiels.addWidget(self.entrees['titre'], 0, 1)
        self.generaux = QWidget()
        generaux = QVBoxLayout(self.generaux)
        generaux.setContentsMargins(0, 0, 0, 0)
        generaux.setSpacing(8)
        self.blocs_generaux = {}
        for nom, libelle in (('nom_utilisateur', 'Identifiant'), ('mot_de_passe', 'Mot de passe'), ('site', 'Site web')):
            self.entrees[nom] = champ(valeurs.get(nom, ''), secret=nom == 'mot_de_passe')
            bloc = QWidget()
            bloc_layout = QHBoxLayout(bloc)
            bloc_layout.setContentsMargins(0, 0, 0, 0)
            bloc_layout.setSpacing(6)
            controle = ligne(self.entrees[nom], bouton('Générer', self.generer, symbole='cle')) if nom == 'mot_de_passe' else self.entrees[nom]
            label = etiquette(libelle, 'secondaire')
            label.setFixedWidth(104)
            bloc_layout.addWidget(label)
            bloc_layout.addWidget(controle, 1)
            generaux.addWidget(bloc)
            self.blocs_generaux[nom] = bloc
        self.corps.addWidget(self.generaux)
        self.force = etiquette('', 'secondaire')
        self.corps.addWidget(self.force)
        self.force_numero = 0
        self.force_timer = QTimer(self)
        self.force_timer.setSingleShot(True)
        self.force_timer.timeout.connect(self.evaluer_force)
        self.entrees['mot_de_passe'].textChanged.connect(self.force_modifiee)
        self.modeles = QWidget()
        self.modeles_layout = QVBoxLayout(self.modeles)
        self.modeles_layout.setContentsMargins(0, 0, 0, 0)
        self.modeles_layout.setSpacing(10)
        self.corps.addWidget(self.modeles)
        self.note_bascule = Depliable('Note')
        self.corps.addWidget(self.note_bascule)
        self.note_bloc = QWidget()
        note_layout = QVBoxLayout(self.note_bloc)
        note_layout.setContentsMargins(0, 0, 0, 0)
        note_layout.setSpacing(6)
        note_entete = QHBoxLayout()
        note_entete.addStretch()
        note_entete.addWidget(bouton('Agrandir', self.agrandir_note, 'discret'))
        note_layout.addLayout(note_entete)
        self.entrees['notes'] = texte(valeurs.get('notes', ''))
        note_layout.addWidget(self.entrees['notes'])
        self.note_bascule.toggled.connect(self.note_bloc.setVisible)
        self.corps.addWidget(self.note_bloc)
        self.avances = QWidget()
        self.avances_layout = QVBoxLayout(self.avances)
        self.avances_layout.setContentsMargins(0, 0, 0, 0)
        self.avances_layout.setSpacing(10)
        self.bascule_avances = Depliable('Options supplémentaires')
        self.bascule_avances.toggled.connect(self.avances.setVisible)
        self.corps.addWidget(self.bascule_avances)
        self.corps.addWidget(self.avances)
        self.entrees['dossier'] = choix([('Sans dossier', '')] + [(d['nom'], d['id']) for d in app.vue['dossiers']], valeurs.get('dossier', ''))
        dossier = ligne(etiquette('Dossier', 'secondaire'), self.entrees['dossier'])
        dossier.layout().itemAt(0).widget().setFixedWidth(104)
        dossier.layout().setStretch(1, 1)
        self.corps.insertWidget(self.corps.indexOf(self.note_bascule), dossier)
        presentation = valeurs.get('presentation', {})
        self.service_associe = champ(presentation.get('service', ''), indication='exemple.com · facultatif')
        self.service_associe.setMaxLength(253)
        self.nom_service = champ(presentation.get('nom', ''), indication='Détection automatique ; titre actuel conservé')
        self.groupe_service = champ(presentation.get('groupe', ''), indication='Automatique, ou nom de groupe choisi')
        self.ajouter('Service associé', self.service_associe, self.avances_layout)
        self.service_associe.setToolTip('Corrige la détection pour les fiches de la même adresse ou application. Le site original reste conservé.')
        self.ajouter('Nom du service', self.nom_service, self.avances_layout)
        self.ajouter('Regroupement', self.groupe_service, self.avances_layout)
        self.equipement = choix([(n or 'Détection automatique', n) for n in ('', 'Appareil réseau local', 'Routeur', 'NAS', 'Serveur', 'Imprimante')], presentation.get('equipement', ''))
        self.ajouter('Type d’équipement local', self.equipement, self.avances_layout)
        self.separe = QCheckBox('Garder cette fiche séparée')
        self.separe.setChecked(presentation.get('separe', False))
        self.avances_layout.addWidget(self.separe)
        self.icone_id = presentation.get('icone', '')
        self.avances_layout.addWidget(ligne(bouton('Choisir une icône', self.choisir_icone, 'discret'),
            bouton('Icône automatique', lambda: setattr(self, 'icone_id', ''), 'discret')))
        self.entrees['tags'] = champ(', '.join(valeurs.get('tags', [])), indication='Séparer les tags par des virgules')
        self.ajouter('Tags', self.entrees['tags'], self.avances_layout)
        self.entrees['expiration'] = champ(valeurs.get('expiration', ''), indication='AAAA-MM-JJ, ou laisser vide')
        self.ajouter('Échéance', self.entrees['expiration'], self.avances_layout)
        self.entrees['favori'] = QCheckBox('Ajouter aux favoris')
        self.entrees['favori'].setChecked(valeurs.get('favori', False))
        self.avances_layout.addWidget(self.entrees['favori'])
        self.champs = []
        self.champs_layout = QVBoxLayout()
        self.avances_layout.addWidget(etiquette('Champs personnalisés', 'secondaire'))
        self.avances_layout.addLayout(self.champs_layout)
        for contenu in valeurs.get('champs', []):
            self.ajouter_champ(contenu)
        self.avances_layout.addWidget(bouton('Ajouter un champ', lambda: self.ajouter_champ()))
        totp = valeurs.get('totp', {})
        self.entrees['totp'] = champ(totp.get('secret', ''), True, 'Secret Base32 ou otpauth://totp')
        self.ajouter('Code TOTP', self.entrees['totp'], self.avances_layout)
        self.totp_algorithm = choix([(n, n) for n in ('SHA1', 'SHA256', 'SHA512')], totp.get('algorithm', 'SHA1'))
        self.totp_digits = choix([('6 chiffres', 6), ('8 chiffres', 8)], totp.get('digits', 6))
        self.totp_period = Nombre()
        self.totp_period.setRange(15, 120)
        self.totp_period.setValue(totp.get('period', 30))
        self.avances_layout.addWidget(ligne(self.totp_algorithm, self.totp_digits, self.totp_period))
        self.totp_label = champ(totp.get('label', ''), indication='Libellé TOTP facultatif')
        self.avances_layout.addWidget(self.totp_label)
        self.sauver = bouton('Enregistrer', self.enregistrer, 'principal')
        self.actions.addWidget(bouton('Annuler', self.reject))
        self.actions.addWidget(self.sauver)
        self.entrees['type'].currentIndexChanged.connect(self.adapter_type)
        self.adapter_type()
        montrer_options = False
        self.bascule_avances.setChecked(montrer_options)
        self.avances.setVisible(montrer_options)
        self.entrees['titre'].setFocus()

    def choisir_type(self):
        ChoisirType(self.app, appliquer=lambda cle: self.entrees['type'].setCurrentIndex(self.entrees['type'].findData(cle)), parent=self).ouvrir()

    def choisir_icone(self):
        source = fichier(self, 'Choisir une icône', 'Images (*.svg *.png *.jpg *.jpeg *.ico *.webp)')
        if source:
            from vaultsafe.icones_sites import installer_icone
            def fini(identifiant):
                self.icone_id = identifiant
            self.app.executer(lambda: installer_icone(source), fini, self.erreur.setText)

    def agrandir_note(self):
        editer_note(self, self.entrees['notes'].toPlainText(), appliquer=self.entrees['notes'].setPlainText)

    def adapter_type(self):
        cle = self.entrees['type'].currentData()
        self.type_libelle.setText(TYPES[cle])
        actifs = {'connexion': ('nom_utilisateur', 'mot_de_passe', 'site'), 'note': (), 'carte': (),
                  'identite': (), 'licence': ('site',), 'wifi': ('mot_de_passe',),
                  'serveur': ('nom_utilisateur', 'mot_de_passe', 'site')}[cle]
        for nom, bloc in self.blocs_generaux.items():
            bloc.setVisible(nom in actifs or bool(self.entrees[nom].text()))
        self.generaux.setVisible(any(nom in actifs or self.entrees[nom].text() for nom in self.blocs_generaux))
        self.force.setVisible(bool(self.force.text()) and ('mot_de_passe' in actifs or bool(self.entrees['mot_de_passe'].text())))
        noms = {m.casefold() for m in MODELES.get(cle, [])}
        self.ajouter_modele()
        for nom, contenu, secret, widget in self.champs:
            modele = nom.text().casefold() in noms
            self.champs_layout.removeWidget(widget)
            self.modeles_layout.removeWidget(widget)
            (self.modeles_layout if modele else self.champs_layout).addWidget(widget)
            nom.setVisible(not modele)
            secret.setVisible(not modele)
            widget.label_modele.setText(nom.text())
            widget.label_modele.setVisible(modele)
            widget.retirer.setVisible(not modele)
            widget.voir.setVisible(modele and secret.isChecked())
        self.modeles.setVisible(bool(noms))
        note = cle == 'note' or self.note_bascule.isChecked()
        self.note_bascule.setVisible(cle != 'note')
        self.note_bascule.setChecked(note)
        self.note_bloc.setVisible(note)

    def force_modifiee(self):
        self.force_numero += 1
        self.force_timer.start(300)

    def evaluer_force(self):
        mot, numero = self.entrees['mot_de_passe'].text()[:72], self.force_numero
        def travail():
            if not self.actif or numero != self.force_numero:
                return None
            from vaultsafe.generateur import evaluer_force_mot_de_passe
            return evaluer_force_mot_de_passe(mot)
        def fini(resultat):
            if self.actif and numero == self.force_numero and resultat:
                self.force.setText('Force indicative : ' + resultat)
                self.force.setVisible(bool(self.entrees['mot_de_passe'].text()))
        self.app.taches.soumettre(travail, fini, analyse=True)

    def ajouter_modele(self):
        existants = {nom.text().strip().casefold() for nom, *_ in self.champs}
        for nom in MODELES.get(self.entrees['type'].currentData(), []):
            if nom.casefold() not in existants and len(self.champs) < 40:
                self.ajouter_champ({'nom': nom, 'valeur': '', 'secret': nom in ('Numéro', 'Code de sécurité', 'Clé de licence', 'Numéro du document')})

    def ajouter(self, libelle, widget, layout=None):
        cible = layout or self.corps
        bloc = QWidget()
        disposition = QVBoxLayout(bloc)
        disposition.setContentsMargins(0, 0, 0, 0)
        disposition.setSpacing(4)
        disposition.addWidget(etiquette(libelle, 'secondaire'))
        disposition.addWidget(widget)
        cible.addWidget(bloc)

    def ajouter_champ(self, valeur=None):
        if len(self.champs) >= 40:
            self.erreur.setText('Maximum : 40 champs par fiche.')
            return
        valeur = valeur or {}
        nom = champ(valeur.get('nom', ''), indication='Nom du champ')
        secret = QCheckBox('Secret')
        secret.setChecked(valeur.get('secret', False))
        contenu = champ(valeur.get('valeur', ''), secret.isChecked(), 'Valeur')
        # Toutes les valeurs libres peuvent contenir des secrets : copies protégées.
        contenu.setProperty('confidentiel', True)
        contenu.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        secret.toggled.connect(lambda actif: contenu.setEchoMode(QLineEdit.EchoMode.Password if actif else QLineEdit.EchoMode.Normal))
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        widget.label_modele = etiquette(nom.text(), 'secondaire')
        widget.label_modele.hide()
        layout.addWidget(widget.label_modele)
        rangee = ligne(nom, contenu, secret)
        layout.addWidget(rangee)
        widget.voir = bouton('Afficher')
        widget.voir.setCheckable(True)
        def reveler(actif):
            contenu.setEchoMode(QLineEdit.EchoMode.Normal if actif else QLineEdit.EchoMode.Password)
            widget.voir.setText('Masquer' if actif else 'Afficher')
        widget.voir.toggled.connect(reveler)
        widget.voir.hide()
        rangee.layout().addWidget(widget.voir)
        entree = (nom, contenu, secret, widget)
        def retirer():
            self.champs.remove(entree)
            contenu.clear()
            widget.deleteLater()
        widget.retirer = bouton('Retirer', retirer)
        rangee.layout().addWidget(widget.retirer)
        self.champs.append(entree)
        self.champs_layout.addWidget(widget)

    def generer(self):
        from vaultsafe.ui.outils import Generateur
        Generateur(self.app, parent=self, inserer=self.entrees['mot_de_passe'].setText).ouvrir()

    def valeurs(self):
        from vaultsafe.totp import importer_totp, verifier_configuration
        resultat = {nom: self.entrees[nom].text() for nom in ('titre', 'nom_utilisateur', 'mot_de_passe', 'site', 'expiration')}
        if resultat['expiration']:
            date.fromisoformat(resultat['expiration'])
        resultat.update(type=self.entrees['type'].currentData(), dossier=self.entrees['dossier'].currentData(),
            tags=[t.strip() for t in self.entrees['tags'].text().split(',') if t.strip()],
            notes=self.entrees['notes'].toPlainText(), favori=self.entrees['favori'].isChecked(),
            champs=[{'nom': n.text(), 'valeur': v.text(), 'secret': s.isChecked()} for n, v, s, _ in self.champs])
        valeur_totp = self.entrees['totp'].text().strip()
        configuration = importer_totp(valeur_totp)
        if configuration and not valeur_totp.startswith('otpauth:'):
            configuration.update(algorithm=self.totp_algorithm.currentData(), digits=self.totp_digits.currentData(),
                                 period=self.totp_period.value(), label=self.totp_label.text())
            verifier_configuration(configuration)
        resultat['totp'] = configuration
        service = self.service_associe.text().strip()
        if service:
            from vaultsafe.services import normaliser
            cible = normaliser(service)
            if cible.genre != 'web' or not cible.origines:
                raise ValueError('Indiquez un domaine web public pour le service associé.')
            service = cible.hote
        presentation = {'service': service, 'nom': self.nom_service.text().strip(), 'groupe': self.groupe_service.text().strip(),
                        'equipement': self.equipement.currentData(), 'icone': self.icone_id, 'separe': self.separe.isChecked()}
        resultat['presentation'] = {k: v for k, v in presentation.items() if v}
        return resultat

    def enregistrer(self):
        if not self.app.ouvert or not self.sauver.isEnabled():
            return
        try:
            valeurs = self.valeurs()
        except ValueError as probleme:
            self.erreur.setText(str(probleme))
            return
        gestion, identifiant = self.app.identifiants, self.identifiant
        self.sauver.setEnabled(False)
        def travail():
            return gestion.modifier_identifiant(identifiant, **valeurs) if identifiant else gestion.ajouter_identifiant(**valeurs)
        def echec(texte):
            self.erreur.setText(texte)
            self.sauver.setEnabled(True)
        self.app.mutation(travail, lambda _: self.accept(), self, erreur=echec)

    def nettoyer(self):
        self.force_timer.stop()
        self.force_numero += 1
        super().nettoyer()
        self.champs.clear()


class DetailsFiche(Dialogue):
    def __init__(self, app, identifiant):
        super().__init__(app, 'Détails', (540, 500))
        self.ajuster_contenu = True
        self.app, self.identifiant = app, identifiant
        self.fiche = None
        self.corps.addWidget(etiquette('Chargement…', 'secondaire'))
        self.actions.addWidget(bouton('Fermer', self.reject))
        self.modifier_action = bouton('Modifier', self.modifier, 'principal')
        self.modifier_action.setEnabled(False)
        self.actions.addWidget(self.modifier_action)
        self.totp_timer = QTimer(self)
        self.totp_timer.timeout.connect(self.actualiser_totp)
        self.installEventFilter(self)
        app.installEventFilter(self)

    def charger(self):
        gestion = self.app.identifiants
        def fini(fiche):
            if self.actif:
                self.afficher(fiche)
                if not self.isVisible():
                    self.ouvrir()
        def echec(erreur):
            if self.actif:
                self.erreur.setText(erreur)
                if not self.isVisible():
                    self.ouvrir()
        self.app.executer(lambda: gestion.afficher_identifiant(self.identifiant), fini, echec)

    def afficher(self, fiche):
        if not self.actif:
            return
        self.fiche = fiche
        self.modifier_action.setEnabled(True)
        self.totp_timer.stop()
        while self.corps.count():
            element = self.corps.takeAt(0)
            if element.widget():
                element.widget().hide()
                element.widget().deleteLater()
        self.barre_titre.titre.setText(fiche.titre)
        if fiche.type != 'connexion':
            self.corps.addWidget(etiquette(TYPES[fiche.type], 'secondaire'))
        if fiche.nom_utilisateur:
            self.valeur('Identifiant', fiche.nom_utilisateur, cle='nom_utilisateur')
        if fiche.mot_de_passe:
            self.valeur('Mot de passe / secret', fiche.mot_de_passe, secret=True, cle='mot_de_passe')
        if fiche.site:
            self.valeur('Site web', fiche.site, cle='site', ouvrir=True)
        if fiche.notes:
            self.corps.addWidget(etiquette('Notes sécurisées', 'secondaire'))
            self.corps.addWidget(apercu_note(self, fiche.notes))
        for c in fiche.champs:
            self.valeur(c['nom'], c['valeur'], c['secret'], cle=('champs', c['nom']))
        if fiche.expiration:
            self.corps.addWidget(etiquette('Échéance : ' + fiche.expiration, 'secondaire'))
        if fiche.totp:
            self.code = etiquette('', 'titre')
            self.corps.addWidget(self.code)
            self.corps.addWidget(bouton('Copier le code TOTP', self.copier_totp))
            self.actualiser_totp()
            self.synchroniser_totp()
        avances = QWidget()
        options = QVBoxLayout(avances)
        options.setContentsMargins(0, 0, 0, 0)
        options.setSpacing(10)
        if fiche.tags:
            options.addWidget(etiquette('Tags : ' + ', '.join(fiche.tags), 'secondaire'))
        options.addWidget(etiquette('Pièces jointes', 'secondaire'))
        for piece in fiche.pieces_jointes:
            options.addWidget(etiquette(f"{piece['nom']} · {piece['taille']:,} octets", 'secondaire'))
            options.addWidget(ligne(bouton('Exporter', lambda _=False, p=piece: self.exporter_piece(p)),
                bouton('Retirer', lambda _=False, p=piece: self.retirer_piece(p))))
        options.addWidget(bouton('Ajouter une pièce', self.ajouter_piece))
        options.addWidget(etiquette('Créée : ' + fiche.date_creation + '\nModifiée : ' + fiche.date_modification, 'secondaire'))
        options.addWidget(bouton('Dupliquer', self.dupliquer))
        options.addWidget(ligne(bouton('Retirer des favoris' if fiche.favori else 'Ajouter aux favoris', self.favori),
            bouton('Historique', self.historique)))
        options.addWidget(bouton('Mettre à la corbeille', self.supprimer, 'danger'))
        bascule = Depliable('Autres options')
        bascule.toggled.connect(avances.setVisible)
        avances.hide()
        self.corps.addWidget(bascule)
        self.corps.addWidget(avances)

    def valeur(self, libelle, valeur, secret=False, cle=None, ouvrir=False):
        self.corps.addWidget(etiquette(libelle, 'secondaire'))
        entree = champ(valeur, secret)
        entree.setReadOnly(True)
        entree.setProperty('confidentiel', True)
        entree.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        copier = bouton('', lambda: self.app.copier_champ_fiche(self.identifiant, cle), 'icone', 'copier')
        copier.setFixedWidth(40)
        copier.setAccessibleName('Copier ' + libelle)
        copier.setToolTip('Copier ' + libelle)
        elements = [entree, copier]
        if ouvrir:
            elements.append(bouton('Ouvrir', self.ouvrir_site, 'discret'))
        if secret:
            minuterie = QTimer(entree)
            minuterie.setSingleShot(True)
            voir = bouton('Afficher')
            def cacher():
                entree.setEchoMode(QLineEdit.EchoMode.Password)
                voir.setText('Afficher')
            def basculer():
                if entree.echoMode() == QLineEdit.EchoMode.Normal:
                    cacher()
                    minuterie.stop()
                else:
                    entree.setEchoMode(QLineEdit.EchoMode.Normal)
                    voir.setText('Masquer')
                    minuterie.start(10_000)
            minuterie.timeout.connect(cacher)
            voir.clicked.connect(basculer)
            elements.append(voir)
        self.corps.addWidget(ligne(*elements))

    def ouvrir_site(self):
        ouvrir_site(self, self.fiche.site)

    def actualiser_totp(self):
        if self.actif and self.app.ouvert and self.fiche and self.fiche.totp:
            from vaultsafe.totp import code_totp, secondes_restantes
            self.code.setText(code_totp(self.fiche.totp) + f' · {secondes_restantes(self.fiche.totp)} s')

    def synchroniser_totp(self):
        if not self.actif:
            return
        actif = self.actif and self.isVisible() and not self.app.isMinimized() and self.app.isVisible()
        if actif and self.fiche and self.fiche.totp:
            self.actualiser_totp()
            self.totp_timer.start(1000)
        else:
            self.totp_timer.stop()

    def eventFilter(self, objet, evenement):
        if evenement.type() in (QEvent.Type.Hide, QEvent.Type.Show, QEvent.Type.WindowStateChange):
            QTimer.singleShot(0, self.synchroniser_totp)
        return False

    def copier_totp(self):
        from vaultsafe.totp import code_totp
        gestion = self.app.identifiants
        self.app.executer(lambda: code_totp(gestion.afficher_identifiant(self.identifiant).totp), self.app.copier_texte)

    def modifier(self):
        FormulaireFiche(self.app, self.fiche).ouvrir()
        self.reject()

    def dupliquer(self):
        FormulaireFiche(self.app, self.fiche, dupliquer=True).ouvrir()
        self.reject()

    def favori(self):
        gestion = self.app.identifiants
        self.app.mutation(lambda: gestion.basculer_favori(self.identifiant), lambda _: self.charger(), self)

    def historique(self):
        popup = Historique(self.app, self.identifiant, self)
        popup.ouvrir()
        popup.charger()

    def supprimer(self):
        if message(self, 'Corbeille', 'La fiche et ses pièces seront conservées dans la corbeille. Continuer ?', True):
            gestion = self.app.identifiants
            self.app.mutation(lambda: gestion.supprimer_identifiant(self.identifiant), lambda _: self.accept(), self)

    def ajouter_piece(self):
        source = fichier(self, 'Ajouter une pièce', 'Tous les fichiers (*)')
        if source:
            base = self.app.base
            self.app.mutation(lambda: base.ajouter_piece(self.identifiant, source), lambda _: self.charger(), self)

    def retirer_piece(self, piece):
        if message(self, 'Retirer la pièce', 'Supprimer cette pièce de la fiche courante ?', True):
            base = self.app.base
            self.app.mutation(lambda: base.retirer_piece(self.identifiant, piece['id']), lambda _: self.charger(), self)

    def exporter_piece(self, piece):
        mot = demander(self, 'Exporter la pièce en clair', 'Votre mot de passe maître :', True)
        if mot is None:
            return
        destination = fichier(self, 'Exporter la pièce en clair', 'Tous les fichiers (*)', True, piece['nom'])
        if destination:
            from vaultsafe.operations_fichiers import exporter_piece
            base = self.app.base
            def travail():
                base.authentifier_action(mot)
                return exporter_piece(base, self.identifiant, piece['id'], destination)
            self.app.executer(travail, lambda _: self.erreur.setText('Pièce exportée en clair.'), self.erreur.setText)

    def nettoyer(self):
        self.totp_timer.stop()
        self.app.removeEventFilter(self)
        self.fiche = None
        super().nettoyer()


class Historique(Dialogue):
    def __init__(self, app, identifiant, parent):
        super().__init__(parent, 'Historique de la fiche', (600, 500))
        self.app, self.identifiant = app, identifiant
        self.revisions = []
        self.liste = QListWidget()
        self.utiliser_liste(self.liste)
        self.disposition.insertWidget(2, ligne(bouton('Voir', self.apercu), bouton('Restaurer', self.restaurer, 'principal'), bouton('Effacer l’historique', self.effacer, 'danger')))
        self.actions.addWidget(bouton('Fermer', self.reject))

    def charger(self):
        base = self.app.base
        self.app.executer(lambda: base.lire_historique(self.identifiant), self.afficher, self.erreur.setText)

    def afficher(self, revisions):
        if self.actif:
            # L'interface ne conserve que le numéro et les métadonnées des versions.
            self.revisions = [(r['date'], r['fiche']['titre']) for r in revisions]
            self.liste.clear()
            self.liste.addItems([d + ' · ' + t for d, t in self.revisions])
            self.erreur.setText('Aucune version précédente.' if not revisions else '')

    def restaurer(self):
        index = self.liste.currentRow()
        if index < 0:
            return
        if message(self, 'Restaurer la version', 'La version actuelle sera conservée dans l’historique. Continuer ?', True):
            base = self.app.base
            def fini(_):
                self.parentWidget().charger()
                self.accept()
            self.app.mutation(lambda: base.restaurer_revision(self.identifiant, index), fini, self)

    def apercu(self):
        index = self.liste.currentRow()
        if index < 0:
            return
        base = self.app.base
        def travail():
            revisions = base.lire_historique(self.identifiant)
            if index >= len(revisions):
                raise ValueError('Version introuvable.')
            return revisions[index]
        def fini(revision):
            if not self.actif:
                return
            popup = Dialogue(self, 'Version antérieure', (620, 580))
            fiche = revision['fiche']
            popup.corps.addWidget(etiquette(revision['date'] + ' · ' + fiche['titre'], 'titre'))
            secrets = []
            for libelle, valeur, sensible in [('Identifiant', fiche['nom_utilisateur'], False),
                ('Mot de passe / secret', fiche['mot_de_passe'], True), ('Site', fiche['site'], False)] + [
                (c['nom'], c['valeur'], c['secret']) for c in fiche['champs']]:
                if valeur:
                    entree = champ(valeur, sensible)
                    entree.setReadOnly(True)
                    entree.setProperty('confidentiel', True)
                    entree.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
                    popup.corps.addWidget(etiquette(libelle, 'secondaire'))
                    popup.corps.addWidget(entree)
                    if sensible:
                        secrets.append(entree)
            if fiche['notes']:
                popup.corps.addWidget(apercu_note(popup, fiche['notes']))
            if fiche['totp']:
                popup.corps.addWidget(etiquette('Configuration TOTP conservée dans cette version.', 'secondaire'))
            voir = QCheckBox('Afficher les secrets de cette version')
            voir.toggled.connect(lambda actif: [e.setEchoMode(QLineEdit.EchoMode.Normal if actif else QLineEdit.EchoMode.Password) for e in secrets])
            popup.corps.addWidget(voir)
            popup.actions.addWidget(bouton('Fermer', popup.reject))
            popup.ouvrir()
        self.app.executer(travail, fini, self.erreur.setText)

    def effacer(self):
        confirmation = demander(self, 'Effacer l’historique', 'Saisissez SUPPRIMER pour effacer définitivement les versions :')
        if confirmation == 'SUPPRIMER':
            base = self.app.base
            self.app.mutation(lambda: base.vider_historique(self.identifiant, confirmation), lambda _: self.charger(), self)

    def nettoyer(self):
        self.revisions.clear()
        super().nettoyer()
