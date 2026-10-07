"""Application Qt locale : vues légères, tâches bornées et session explicite."""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QFont, QGuiApplication, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QApplication, QProgressBar, QStackedWidget, QLayout, QLineEdit,
    QPlainTextEdit, QSizeGrip, QStyle, QStyleOption, QVBoxLayout, QWidget,
)
from vaultsafe.config import obtenir_chemin_base, obtenir_dossier_donnees
from vaultsafe.ui.composants import BarreTitre, Infobulles, demander, etiquette, fichier, message
from vaultsafe.ui.placement import ecran_cible, placer, rendre_visible
from vaultsafe.ui.style import feuille_style, obtenir_couleurs, palette_theme
from vaultsafe.ui.taches import Taches
from vaultsafe.ui.projections import lire_vue_preparee


class Application(QWidget):
    demande_navigateur = Signal(object)

    def __init__(self, connexion=None, identifiants=None, parametres=None, *, chemin=None, integrations_windows=True, masquee=False, debut_demarrage=None, developpement=False, auto_appareil=True):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName('racine')
        self.debut_demarrage = time.perf_counter() if debut_demarrage is None else debut_demarrage
        self.setWindowTitle('VaultSafe — Gestionnaire d’identifiants')
        self.base = connexion.base if connexion else None
        self.developpement = developpement
        self.auto_appareil = auto_appareil
        self.appareil = None
        self.confiance_expire = None
        self.capture_navigateur_en_cours = False
        self.captures_browser = None
        if self.base:
            from vaultsafe.appareil_confiance import AppareilConfiance
            self.appareil = AppareilConfiance(self.base)
        self.fermeture_coffre = None
        self.connexion, self.identifiants, self.parametres = connexion, identifiants, parametres
        self.integrations_windows = integrations_windows
        self.ouvert, self.fermee = False, False
        self.vue = None
        self.preferences = {}
        self.analyse = None
        self.revision_analyse = None
        self.analyse_numero = 0
        self.analyse_en_cours = None
        self.analyse_erreur = self.fuites_erreur = ''
        self.analyse_perimee = False
        self.derniere_analyse = self.derniere_fuites = None
        self.liaison = None
        self.sauvegardes = None
        self.page = 'identifiants'
        self.geometrie_tray = None
        self.taches = Taches(self)
        self.theme, self.echelle = 'light', 100
        try:
            chemin_interface = obtenir_dossier_donnees() / 'interface.json'
            if chemin_interface.stat().st_size > 4096:
                raise ValueError('Préférences publiques invalides.')
            donnees = json.loads(chemin_interface.read_text(encoding='utf-8'))
            self.theme = 'dark' if donnees.get('theme') == 'dark' else 'light'
            self.echelle = max(100, min(200, int(donnees.get('echelle', 100))))
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        self.appliquer_theme()
        qt = QApplication.instance()
        if not hasattr(qt, 'vaultsafe_infobulles'):
            qt.vaultsafe_infobulles = Infobulles(qt)
        self.style_selection = QStyle.StateFlag.State_Selected
        self.disposition = QVBoxLayout(self)
        self.disposition.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.disposition.setContentsMargins(0, 0, 0, 0)
        self.pile = QStackedWidget()
        self.disposition.addWidget(self.pile)
        self.barre = QProgressBar()
        self.barre.setRange(0, 0)
        self.barre.hide()
        self.disposition.addWidget(self.barre)
        self.statut = etiquette('', 'secondaire')
        self.statut.setContentsMargins(16, 0, 16, 4)
        self.disposition.addWidget(self.statut)
        self.poignee = QSizeGrip(self)
        self.poignee.setFixedSize(16, 16)
        self.activite = time.monotonic()
        self.inactivite = QTimer(self)
        self.inactivite.setSingleShot(True)
        self.inactivite.timeout.connect(self.verifier_inactivite)
        self.copie_timer = QTimer(self)
        self.copie_timer.setSingleShot(True)
        self.copie_timer.timeout.connect(self.effacer_copie)
        self.texte_copie = None
        self.backup_timer = QTimer(self)
        self.backup_timer.setSingleShot(True)
        self.backup_timer.timeout.connect(self.sauvegarde_due)
        self.rappel_timer = QTimer(self)
        self.rappel_timer.setSingleShot(True)
        self.rappel_timer.timeout.connect(self.rappels)
        self.dernier_rappel = None
        self.ecran_initial = ecran_cible()
        self.login(pret=False)
        placer(self, self.taille_connexion(), screen=self.ecran_initial)
        self.windowHandle().screenChanged.connect(lambda _: self.ecran_change())
        if not masquee:
            self.show()
        from vaultsafe.ui.windows import IntegrationWindows
        self.windows = IntegrationWindows(self, integrations_windows)
        self.demande_navigateur.connect(self.traiter_navigateur)
        QApplication.instance().installEventFilter(self)
        for touche, action in (('Ctrl+N', self.nouvelle_fiche), ('Ctrl+F', self.focus_recherche), ('Ctrl+K', self.focus_recherche),
                               ('Ctrl+Shift+L', self.verrouiller), ('Ctrl+Shift+G', self.generateur)):
            raccourci = QShortcut(QKeySequence(touche), self)
            raccourci.activated.connect(action)
        if self.base is not None:
            self.executer(lambda: self.base.est_initialise(), lambda existe: self.login(existe=existe))
        else:
            self.charger_base(chemin)
        QGuiApplication.instance().screenRemoved.connect(lambda _: self.ecran_change())
        QGuiApplication.instance().screenAdded.connect(self.brancher_ecran)
        for screen in QGuiApplication.screens():
            self.brancher_ecran(screen)

    def hasHeightForWidth(self):
        # Le contenu défile ; sa hauteur calculée ne contraint pas la fenêtre
        # native, notamment quand des libellés passent sur plusieurs lignes.
        return False

    def heightForWidth(self, largeur):
        return -1

    def paintEvent(self, evenement):
        option = QStyleOption()
        option.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option, painter, self)
        painter.end()

    def appliquer_theme(self):
        self.couleurs = obtenir_couleurs(self.theme)
        qt = QApplication.instance()
        qt.setProperty('vaultsafeTheme', self.theme)
        qt.setProperty('vaultsafeEchelle', self.echelle)
        if hasattr(qt, 'vaultsafe_infobulles'):
            qt.vaultsafe_infobulles.hide()
        css = feuille_style(self.theme)
        if self.echelle != 100:
            import re
            css = re.sub(r'(\d+(?:\.\d+)?)(px|pt)', lambda m: f'{float(m[1]) * self.echelle / 100:g}{m[2]}', css)
        qt.setPalette(palette_theme(self.theme))
        QApplication.instance().setStyleSheet(css)
        police = QFont('Segoe UI Variable')
        police.setPointSizeF(10 * self.echelle / 100)
        QApplication.instance().setFont(police)
        if hasattr(self, 'sidebar'):
            self.adapter_navigation()

    def remplacer(self, widget):
        while self.pile.count():
            ancien = self.pile.widget(0)
            self.pile.removeWidget(ancien)
            ancien.deleteLater()
        self.pile.addWidget(widget)
        self.pile.setCurrentWidget(widget)

    def memoriser_interface(self):
        from vaultsafe.operations_fichiers import ecrire_atomique
        valeurs = json.dumps({'theme': self.theme, 'echelle': self.echelle}).encode('utf-8')
        self.taches.soumettre(lambda: ecrire_atomique(obtenir_dossier_donnees() / 'interface.json', valeurs))

    def commandes(self):
        return BarreTitre(self, complete=True)

    def taille_connexion(self):
        facteur = self.echelle / 100
        return round(440 * facteur), round(570 * facteur)

    def login(self, existe=True, pret=True, automatique=False):
        from vaultsafe.ui.connexion import construire_connexion
        construire_connexion(self, existe, pret, automatique)

    def verifier_appareil(self, automatique=False):
        appareil, base = self.appareil, self.base
        def fini(expire):
            if self.base is not base or self.ouvert or self.fermee:
                return
            self.confiance_expire = expire
            self.bouton_appareil.setVisible(expire is not None)
            self.case_appareil.setVisible(expire is None)
            if expire is not None and automatique:
                self.connecter_appareil()
        self.taches.soumettre(appareil.etat, fini)

    def charger_base(self, chemin):
        def travail():
            from vaultsafe.database import BaseDeDonnees
            from vaultsafe.connexion import Connexion
            from vaultsafe.identifiants import Identifiants
            from vaultsafe.parametres import Parametres
            from vaultsafe.appareil_confiance import AppareilConfiance
            # Le lancement habituel n'a pas d'argument --coffre. Résoudre le
            # coffre mémorisé (ou celui par défaut) dans le travailleur.
            base = BaseDeDonnees(obtenir_chemin_base() if chemin is None else chemin)
            connexion = Connexion(base)
            appareil = AppareilConfiance(base)
            if self.developpement:
                from vaultsafe.developpement import initialiser
                initialiser(base, connexion, appareil)
            return base, connexion, Identifiants(base, connexion), Parametres(base, connexion), base.est_initialise(), appareil
        def fini(resultat):
            self.base, self.connexion, self.identifiants, self.parametres, existe, self.appareil = resultat
            self.login(existe=existe, automatique=self.auto_appareil)
            logging.getLogger('vaultsafe').info('demarrage:pret %.1fms', (time.perf_counter() - self.debut_demarrage) * 1000)
            if self.integrations_windows and self.liaison is None:
                from vaultsafe.liaison_navigateur import ids_hote_associe, LiaisonLocale
                def associe(ids):
                    if ids and self.liaison is None:
                        try:
                            self.liaison = LiaisonLocale(ids, notifier=self.demande_navigateur.emit)
                        except (OSError, ValueError):
                            pass
                self.taches.soumettre(ids_hote_associe, associe)
        self.executer(travail, fini, erreur=lambda texte: self.erreur_login.setText(texte + ' Sélectionnez un autre coffre.'))

    def executer(self, action, succes=None, erreur=None, texte='Traitement en cours…', *, analyse=False):
        if self.fermee:
            return
        self.statut.setText(texte)
        self.barre.setVisible(not self.isMinimized() and self.isVisible())
        def fini(valeur):
            self.barre.hide()
            self.statut.setText('')
            if succes:
                succes(valeur)
        def echouer(valeur):
            self.barre.hide()
            self.statut.setText(valeur or '')
            if self.ouvert and self.base and not self.base.coffre_ouvert:
                self.verrouiller()
            if erreur:
                erreur(valeur)
        return self.taches.soumettre(action, fini, echouer, analyse=analyse)

    def connecter(self):
        if not self.base or not self.bouton_login.isEnabled():
            return
        mot = self.mot_maitre.text()
        memoriser = self.case_appareil.isChecked()
        if not self.login_existe and mot != self.confirmation_maitre.text():
            self.erreur_login.setText('Les mots de passe ne correspondent pas.')
            return
        self.mot_maitre.clear()
        self.confirmation_maitre.clear()
        self.bouton_login.setEnabled(False)
        connexion, base, existe = self.connexion, self.base, self.login_existe
        appareil, fermeture = self.appareil, self.fermeture_coffre
        generation = self.taches.generation
        def ouvrir():
            if fermeture:
                fermeture.result()
            (connexion.se_connecter if existe else connexion.creer_mot_de_passe_maitre)(mot)
            if generation != self.taches.generation:
                base.verrouiller()
                raise ValueError('La connexion a été annulée.')
            avertissement = ''
            if memoriser:
                try:
                    appareil.autoriser()
                except (ValueError, OSError):
                    avertissement = 'Connexion réussie ; l’appareil n’a pas pu être autorisé.'
            if generation != self.taches.generation:
                base.verrouiller()
                raise ValueError('La connexion a été annulée.')
            return lire_vue_preparee(base), avertissement, appareil.etat()
        def echec(texte):
            self.erreur_login.setText(texte)
            self.bouton_login.setEnabled(True)
            self.mot_maitre.setFocus()
        def fini(resultat):
            self.confiance_expire = resultat[2]
            self.session_ouverte(resultat[0])
            if resultat[1]:
                self.statut.setText(resultat[1])
        self.executer(ouvrir, fini, echec, 'Déverrouillage du coffre…')

    def connecter_appareil(self, succes=None, erreur=None):
        if not self.base or not self.bouton_login.isEnabled() or self.fermee:
            return False
        appareil, base, generation = self.appareil, self.base, self.taches.generation
        fermeture = self.fermeture_coffre
        self.bouton_login.setEnabled(False)
        self.bouton_appareil.setEnabled(False)
        def travail():
            if fermeture:
                fermeture.result()
            appareil.ouvrir()
            if generation != self.taches.generation:
                base.verrouiller()
                raise ValueError('La connexion a été annulée.')
            return lire_vue_preparee(base), appareil.etat()
        def echec(_):
            self.erreur_login.setText('L’autorisation n’est plus disponible. Utilisez votre mot de passe maître.')
            self.bouton_login.setEnabled(True)
            self.bouton_appareil.hide()
            self.case_appareil.show()
            self.case_appareil.setChecked(False)
            self.mot_maitre.setFocus()
            if erreur:
                erreur()
        def fini(vue):
            self.confiance_expire = vue[1]
            self.session_ouverte(vue[0])
            if succes:
                succes()
        self.executer(travail, fini, echec, 'Ouverture avec cet appareil…')
        return True

    def session_ouverte(self, vue):
        self.ecran_initial = ecran_cible(self)
        self.setUpdatesEnabled(False)
        self.ouvert = True
        self.vue = vue
        self.preferences = self.parametres.pour_interface(vue['preferences'])
        self.theme = self.preferences.get('theme', self.theme)
        self.echelle = int(self.preferences.get('echelle', self.echelle))
        self.appliquer_theme()
        self.memoriser_interface()
        self.windows.etat(True)
        self.construire_coffre()
        placer(self, (1050, 680), screen=self.ecran_initial)
        if self.geometrie_tray is not None:
            self.setGeometry(self.geometrie_tray)
            rendre_visible(self)
            self.geometrie_tray = None
        self.setUpdatesEnabled(True)
        self.relancer_minuteur()
        self.demarrer_services()
        self.rappels()

    def construire_coffre(self):
        from vaultsafe.ui.coffre import construire_coffre
        construire_coffre(self)

    def afficher_page(self, nom):
        if not self.ouvert:
            return
        self.page = nom
        if nom == 'identifiants':
            page = self.liste
        else:
            if nom not in self.autres_pages:
                page = self.creer_securite() if nom == 'securite' else self.creer_parametres()
                self.autres_pages[nom] = page
                self.pages.addWidget(page)
            page = self.autres_pages[nom]
        if nom == 'parametres':
            page.actualiser_capture()
        self.pages.setCurrentWidget(page)
        for cle, b in self.navigation.items():
            b.setChecked(cle == nom)
        if nom in ('identifiants', 'securite'):
            if self.recherches_focus.indexOf(page.recherche) == -1:
                self.recherches_focus.addWidget(page.recherche)
            self.recherches_focus.setCurrentWidget(page.recherche)
        self.recherches_focus.setVisible(nom in ('identifiants', 'securite'))
        self.relancer_minuteur()

    def actualiser(self, apres=None, mutation=False):
        if not self.ouvert:
            return
        if mutation:
            self.invalider_analyse()
        base = self.base
        def fini(vue):
            if vue['revision'] != base.revision_courante:
                self.actualiser(apres=apres)
                return
            if self.revision_analyse is not None and self.revision_analyse != vue['revision']:
                self.invalider_analyse()
            self.vue, self.preferences = vue, self.parametres.pour_interface(vue['preferences'])
            self.liste.actualiser(vue)
            if 'parametres' in self.autres_pages:
                self.autres_pages['parametres'].actualiser_capture()
            self.actualiser_securite()
            self.planifier_backup()
            if apres:
                apres()
        noms = dict(self.icones_sites.moteur.noms) if hasattr(self, 'icones_sites') else {}
        self.executer(lambda: lire_vue_preparee(base, noms), fini, texte='Actualisation…')

    def mutation(self, action, succes=None, parent=None, erreur=None):
        def fini(valeur):
            if self.ouvert:
                self.actualiser(mutation=True)
            if succes and (parent is None or getattr(parent, 'actif', True)):
                succes(valeur)
        return self.executer(action, fini, erreur=erreur or ((lambda texte: parent.erreur.setText(texte)) if parent else None),
                             texte='Enregistrement…')

    def creer_securite(self):
        from vaultsafe.ui.securite import PageSecurite
        return PageSecurite(self)

    def analyse_courante(self):
        if self.ouvert and self.analyse and self.vue and self.revision_analyse == self.vue['revision'] == self.base.revision_courante:
            return self.analyse
        return None

    def invalider_analyse(self):
        self.analyse_perimee = bool(self.derniere_analyse or self.analyse_en_cours)
        self.analyse_numero += 1
        self.analyse = self.revision_analyse = self.analyse_en_cours = None
        self.analyse_erreur = self.fuites_erreur = ''
        if hasattr(self, 'liste'):
            self.liste.actualiser_analyse()
        self.actualiser_securite()

    def score_analyse(self):
        r = self.analyse_courante()
        if not r:
            return None
        from vaultsafe.score import calculer_score
        return calculer_score(r['total'], len(r['faibles']), len(r['reutilises']),
                              len(r['exposes']) if 'exposes' in r else None)

    def actualiser_securite(self):
        if not self.ouvert or not hasattr(self, 'autres_pages'):
            return
        from shiboken6 import isValid
        page = self.autres_pages.get('securite')
        if page is not None and isValid(page):
            page.actualiser()

    def analyser(self, en_ligne=False):
        if not self.ouvert or self.analyse_en_cours:
            return
        if en_ligne and not message(self, 'Vérification en ligne', 'Seuls les cinq premiers caractères de l’empreinte de chaque mot de passe sont envoyés au service de vérification. Continuer ?', True):
            return
        gestion, base = self.identifiants, self.base
        precedente = self.analyse_courante()
        exposes = set(precedente['exposes']) if precedente and 'exposes' in precedente else None
        revision_precedente = self.revision_analyse
        generation = self.taches.generation
        self.analyse_numero += 1
        numero = self.analyse_numero
        self.analyse_en_cours = 'fuites' if en_ligne else 'locale'
        self.analyse_erreur = ''
        if en_ligne:
            self.fuites_erreur = ''
        self.actualiser_securite()
        def annule():
            return generation != self.taches.generation or numero != self.analyse_numero
        def travail():
            from vaultsafe.score import analyser_mots_de_passe
            donnees, revision = base.lire_analyse()
            fiches = [gestion.dictionnaire_vers_identifiant(d) for d in donnees]
            faibles, reutilises = analyser_mots_de_passe(fiches, annule=annule)
            resultat = {'total': sum(bool(f.mot_de_passe) for f in fiches), 'faibles': faibles, 'reutilises': reutilises}
            date_analyse, date_fuites, erreur_fuites = datetime.now().astimezone(), None, ''
            if en_ligne:
                from vaultsafe.fuites import verifier_comptes_exposes
                try:
                    resultat['exposes'] = set(verifier_comptes_exposes([(f.id, f.mot_de_passe) for f in fiches if f.mot_de_passe], annule=annule))
                    date_fuites = datetime.now().astimezone()
                except (ValueError, OSError):
                    erreur_fuites = 'Vérification des fuites indisponible.'
            elif exposes is not None and revision == revision_precedente:
                resultat['exposes'] = exposes
            return revision, resultat, date_analyse, date_fuites, erreur_fuites
        def fini(valeur):
            revision, resultat, date_analyse, date_fuites, erreur_fuites = valeur
            if annule():
                return
            if revision != self.vue['revision'] or revision != base.revision_courante:
                self.invalider_analyse()
                self.actualiser()
                return
            self.analyse, self.revision_analyse = resultat, revision
            self.analyse_en_cours, self.analyse_perimee = None, False
            self.derniere_analyse = date_analyse
            if en_ligne:
                self.fuites_erreur = erreur_fuites
                self.derniere_fuites = date_fuites
            self.liste.actualiser_analyse()
            self.actualiser_securite()
        def echec(_):
            if not annule():
                self.analyse_en_cours = None
                self.analyse_erreur = 'Analyse indisponible. Réessayez.'
                if en_ligne:
                    self.fuites_erreur = 'Vérification indisponible.'
                self.actualiser_securite()
        self.taches.soumettre(travail, fini, echec, analyse=True)

    def filtre_securite(self, filtre):
        self.afficher_page('identifiants')
        self.liste.recherche.clear()
        self.liste.types.setCurrentIndex(0)
        self.liste.dossiers.setCurrentIndex(0)
        self.liste.options.show()
        self.liste.etats.setCurrentIndex(self.liste.etats.findData(filtre))

    def creer_parametres(self):
        from vaultsafe.ui.parametres import PageParametres
        return PageParametres(self)

    def nouvelle_fiche(self):
        if self.ouvert:
            from vaultsafe.ui.fiches import ChoisirType
            ChoisirType(self).ouvrir()

    def details(self, identifiant):
        if self.ouvert:
            from vaultsafe.ui.outils import DetailsFiche
            popup = DetailsFiche(self, identifiant)
            popup.charger()

    def copier_fiche(self, identifiant):
        self.copier_champ_fiche(identifiant, 'mot_de_passe')

    def copier_champ_fiche(self, identifiant, cle):
        if self.ouvert:
            gestion = self.identifiants
            def travail():
                fiche = gestion.afficher_identifiant(identifiant)
                if isinstance(cle, tuple):
                    return next((c['valeur'] for c in fiche.champs if c['nom'] == cle[1]), '')
                return getattr(fiche, cle)
            self.executer(travail, self.copier_texte)

    def copier_texte(self, texte):
        if not self.ouvert:
            return
        from vaultsafe.protections_windows import copier_confidentiel
        try:
            copier_confidentiel(int(self.winId()), texte)
        except (OSError, ValueError):
            self.statut.setText('Le presse-papiers Windows est indisponible. Réessayez.')
            return
        self.texte_copie = texte
        self.copie_timer.start(int(self.preferences.get('presse_papiers_secondes', '30')) * 1000)
        self.statut.setText('Copié. Effacement automatique du presse-papiers activé.')

    def effacer_copie(self):
        clipboard = QApplication.clipboard()
        if self.texte_copie is not None and clipboard.text() == self.texte_copie:
            clipboard.clear()
        self.texte_copie = None
        self.copie_timer.stop()

    def dossiers(self):
        if self.ouvert:
            from vaultsafe.ui.outils import Dossiers
            Dossiers(self).ouvrir()

    def corbeille(self):
        if self.ouvert:
            from vaultsafe.ui.outils import Corbeille
            popup = Corbeille(self)
            popup.ouvrir()
            popup.charger()

    def generateur(self):
        if self.ouvert:
            from vaultsafe.ui.outils import Generateur
            Generateur(self).ouvrir()

    def recuperation(self):
        if self.base:
            from vaultsafe.ui.outils import Recuperation
            Recuperation(self).ouvrir()

    def choisir_coffre(self, creer=False):
        chemin = fichier(self, 'Créer un autre coffre' if creer else 'Ouvrir un coffre',
                         'Coffre VaultSafe (*.db *.vaultsafe)', creer, 'Mon-coffre.db' if creer else '')
        if not chemin:
            return
        chemin = Path(chemin)
        if creer and chemin.exists():
            message(self, 'Nouveau coffre', 'Choisissez un nouveau fichier. Le fichier existant est conservé.')
            return
        if chemin.suffix.lower() == '.vaultsafe':
            mot = demander(self, 'Ouvrir la sauvegarde', 'Mot de passe de cette sauvegarde :', True)
            if mot is None:
                return
            destination = fichier(self, 'Copie du coffre', 'Coffre VaultSafe (*.db)', True, chemin.stem + '-ouvert.db')
            if not destination:
                return
            from vaultsafe.coffres import cloner_sauvegarde
            self.executer(lambda: cloner_sauvegarde(chemin, destination, mot), self.changer_coffre)
        else:
            self.changer_coffre(chemin)

    def changer_coffre(self, chemin):
        self.verrouiller()
        self.base = None
        self.appareil = None
        self.developpement = False
        self.ecran_initial = ecran_cible(self)
        self.login(pret=False)
        from vaultsafe.coffres import memoriser_coffre
        self.charger_base(chemin)
        self.taches.soumettre(lambda: memoriser_coffre(chemin))

    def focus_recherche(self):
        if self.ouvert:
            if self.page not in ('identifiants', 'securite'):
                self.afficher_page('identifiants')
            self.recherches_focus.currentWidget().setFocus()

    def eventFilter(self, objet, evenement):
        if objet is self and evenement.type() == QEvent.Type.WinIdChange and hasattr(self, 'windows'):
            self.windows.actualiser()
        if objet is self and evenement.type() in (QEvent.Type.Hide, QEvent.Type.WindowStateChange):
            if self.isHidden() or self.isMinimized():
                self.analyse_numero += 1
                if self.analyse_en_cours:
                    if self.analyse_en_cours == 'fuites':
                        self.fuites_erreur = 'Vérification interrompue.'
                    else:
                        self.analyse_erreur = 'Analyse interrompue. Relancez-la.'
                    self.analyse_en_cours = None
                    self.actualiser_securite()
                self.barre.hide()
        if not self.ouvert and evenement.type() == QEvent.Type.KeyPress and objet.property('confidentiel'):
            if evenement.matches(QKeySequence.StandardKey.Copy) or evenement.matches(QKeySequence.StandardKey.Cut):
                return True
        if self.ouvert and evenement.type() == QEvent.Type.KeyPress and objet.property('confidentiel'):
            if evenement.key() in (Qt.Key.Key_C, Qt.Key.Key_X) and evenement.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if isinstance(objet, QLineEdit):
                    selection = objet.selectedText()
                    if objet.echoMode() == QLineEdit.EchoMode.Password:
                        return True
                elif isinstance(objet, QPlainTextEdit):
                    selection = objet.textCursor().selectedText().replace('\u2029', '\n')
                else:
                    selection = ''
                if selection:
                    self.copier_texte(selection)
                    if evenement.key() == Qt.Key.Key_X and not objet.isReadOnly():
                        if isinstance(objet, QLineEdit):
                            objet.insert('')
                        else:
                            objet.textCursor().removeSelectedText()
                return True
        if self.ouvert and evenement.type() in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.Wheel):
            self.relancer_minuteur()
        return False

    def cle_inactivite(self):
        return 'inactivite_confiance' if self.confiance_expire is not None and self.confiance_expire > time.time() else 'inactivite'

    def delai_inactivite(self):
        cle = self.cle_inactivite()
        return int(self.preferences.get(cle, '0' if cle == 'inactivite_confiance' else '5'))

    def definir_confiance(self, expire):
        self.confiance_expire = expire
        self.inactivite.stop()
        self.relancer_minuteur()
        page = getattr(self, 'autres_pages', {}).get('parametres')
        if page:
            page.actualiser_delai()

    def relancer_minuteur(self):
        if self.ouvert:
            self.activite = time.monotonic()
            minutes = self.delai_inactivite()
            if minutes == 0:
                # Aucun réveil périodique. Seule l'expiration du droit local est utile.
                if self.cle_inactivite() == 'inactivite_confiance':
                    if not self.inactivite.isActive():
                        self.inactivite.start(min(2_147_483_647, max(1, int((self.confiance_expire - time.time()) * 1000))))
                else:
                    self.inactivite.stop()
                return
            if not self.inactivite.isActive():
                self.inactivite.start(minutes * 60_000)

    def verifier_inactivite(self):
        minutes = self.delai_inactivite()
        if not minutes:
            self.relancer_minuteur()
            return
        restant = minutes * 60 - (time.monotonic() - self.activite)
        if restant <= 0:
            self.verrouiller()
        elif self.ouvert:
            self.inactivite.start(max(1, int(restant * 1000)))

    def demarrer_services(self):
        from vaultsafe.sauvegardes import SauvegardesAutomatiques
        self.sauvegardes = SauvegardesAutomatiques(self.base)
        ids = self.preferences.get('extension_ids', '')
        if self.liaison and self.liaison.origines != {'chrome-extension://' + n.strip() + '/' for n in ids.split(',') if n.strip()}:
            ancienne = self.liaison
            ancienne.invalider()
            self.taches.securite.submit(ancienne.arreter)
            self.liaison = None
        if ids and self.integrations_windows and not self.liaison:
            from vaultsafe.liaison_navigateur import LiaisonLocale
            try:
                self.liaison = LiaisonLocale(ids, notifier=self.demande_navigateur.emit)
            except (ValueError, OSError):
                self.statut.setText('La liaison navigateur est indisponible.')
        self.planifier_backup()

    def planifier_backup(self):
        self.backup_timer.stop()
        if self.ouvert and self.sauvegardes and self.preferences.get('backup_dossier'):
            if self.sauvegardes.derniere_signature != self.vue['revision']:
                intervalle = int(self.preferences.get('backup_minutes', '60')) * 60
                delai = max(1, intervalle - (time.monotonic() - self.sauvegardes.derniere_execution))
                self.backup_timer.start(int(delai * 1000))

    def sauvegarde_due(self):
        gestionnaire = self.sauvegardes
        if self.ouvert and gestionnaire:
            self.executer(gestionnaire.effectuer, lambda _: self.planifier_backup(), texte='Sauvegarde chiffrée…')

    def rappels(self):
        if not self.ouvert:
            return
        aujourd_hui = date.today()
        if self.preferences.get('rappels', 'oui') == 'oui' and self.dernier_rappel != aujourd_hui:
            self.dernier_rappel = aujourd_hui
            nombre = sum(bool(f['expiration']) and f['expiration'] <= (aujourd_hui + timedelta(days=7)).isoformat() for f in self.vue['fiches'])
            if nombre:
                self.windows.notifier(f'{nombre} échéance(s) à revoir dans votre coffre.')
        demain = datetime.combine(aujourd_hui + timedelta(days=1), datetime.min.time())
        self.rappel_timer.start(max(1000, int((demain - datetime.now()).total_seconds() * 1000)))

    def traiter_navigateur(self, evenement):
        from vaultsafe.ui.navigateur import traiter
        traiter(self, evenement)

    def reduire(self):
        if self.preferences.get('reduire_zone', 'non') == 'oui' and self.windows.icone:
            self.geometrie_tray = self.geometry()
            self.hide()
            # Masquer conserve la session ; inactivité et événements Windows
            # continuent à verrouiller, comme le bouton Verrouiller.
        else:
            self.showMinimized()

    def reafficher(self):
        rendre_visible(self)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def verrouiller(self):
        if self.fermee:
            return
        if self.base is None and not self.ouvert:
            return
        screen = ecran_cible(self)
        self.ouvert = False
        self.capture_navigateur_en_cours = False
        if self.captures_browser:
            self.captures_browser.vider()
        if hasattr(self, 'icones_sites'):
            self.icones_sites.annuler()
        if hasattr(self, 'liste'):
            self.liste.nettoyer()
        self.taches.invalider()
        if self.base:
            base = self.base
            self.fermeture_coffre = self.taches.securite.submit(base.verrouiller)
        self.inactivite.stop()
        self.backup_timer.stop()
        self.rappel_timer.stop()
        self.effacer_copie()
        if self.liaison:
            self.liaison.annuler_attentes()
        self.sauvegardes = None
        for popup in list(self.findChildren(QWidget)):
            if getattr(popup, 'sensible', False):
                popup.close()
        self.vue = None
        self.analyse = None
        self.revision_analyse = None
        self.analyse_en_cours = None
        self.analyse_erreur = self.fuites_erreur = ''
        self.analyse_perimee = False
        self.derniere_analyse = self.derniere_fuites = None
        self.preferences = {}
        if hasattr(self, 'liste'):
            self.liste.modele.remplacer([])
            self.liste.actualiser_analyse()
            self.autres_pages.clear()
            self.navigation.clear()
            del self.liste
            del self.sidebar
            del self.pages
        self.barre.hide()
        self.statut.clear()
        self.windows.etat(False)
        self.login()
        placer(self, self.taille_connexion(), screen=screen)

    def ecran_change(self):
        rendre_visible(self)
        for popup in self.findChildren(QWidget):
            if popup.isWindow() and popup.isVisible():
                placer(popup, (popup.width(), popup.height()), popup.parentWidget() or self)

    def brancher_ecran(self, screen):
        screen.availableGeometryChanged.connect(lambda _: self.ecran_change())

    def resizeEvent(self, evenement):
        super().resizeEvent(evenement)
        if hasattr(self, 'poignee'):
            self.poignee.move(self.width() - 18, self.height() - 18)
            self.poignee.raise_()
        if getattr(self, 'ouvert', False) and hasattr(self, 'sidebar'):
            self.adapter_navigation()

    def adapter_navigation(self):
        facteur = self.echelle / 100
        self.sidebar.setFixedWidth(round((56 if self.width() < 500 * facteur else 64) * facteur))
        self.marque_focus.setVisible(self.width() >= 640 * facteur)
        self.recherches_focus.setMaximumWidth(round(460 * facteur))
        for b in self.navigation.values():
            b.setMinimumHeight(round(40 * facteur))
        self.liste.adapter_table()

    def mousePressEvent(self, evenement):
        self._origine_deplacement = evenement.globalPosition().toPoint() - self.frameGeometry().topLeft() if evenement.position().y() < 72 else None

    def mouseMoveEvent(self, evenement):
        if evenement.buttons() & Qt.MouseButton.LeftButton and getattr(self, '_origine_deplacement', None) is not None:
            self.move(evenement.globalPosition().toPoint() - self._origine_deplacement)

    def fermer(self):
        self.close()

    def closeEvent(self, evenement):
        if not self.fermee:
            self.verrouiller()
            self.fermee = True
            if self.liaison:
                liaison = self.liaison
                liaison.invalider()
                self.taches.securite.submit(liaison.arreter)
                self.liaison = None
            self.windows.arreter()
            if hasattr(self, 'icones_sites'):
                self.icones_sites.arreter()
            self.taches.arreter(self.base.verrouiller if self.base else None)
            QApplication.instance().removeEventFilter(self)
        evenement.accept()
        QApplication.instance().quit()
