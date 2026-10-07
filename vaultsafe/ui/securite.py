"""Sécurité Focus : résultats publics, dédupliqués et contrôles volontaires."""
from PySide6.QtCore import QAbstractTableModel, QEvent, QModelIndex, QRectF, QSize, QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import QAbstractItemView, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QProgressBar, QSizePolicy, QStyle, QStyledItemDelegate, QTableView, QVBoxLayout, QWidget
from vaultsafe.ui.composants import Choix, LigneSouple, Symbole, bouton, champ, defilement, etiquette
from vaultsafe.ui.groupes import GroupesSites
from vaultsafe.ui.icones import dessiner_icone, icone
from vaultsafe.ui.liste import LignesFocus

LIBELLES = {'faibles': 'Faible', 'reutilises': 'Réutilisé', 'exposes': 'Exposé'}


class ModeleProblemes(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fiches, self.lignes = [], {}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.fiches)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 5

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.fiches):
            return None
        f = self.fiches[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return f
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole, Qt.ItemDataRole.ToolTipRole):
            return (f['nom_utilisateur'] or f['titre'], f['dossier_nom'], ', '.join(LIBELLES[p] for p in f['problemes']), 'Modifier la fiche', 'Ouvrir la fiche')[index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            return ('Compte', 'Dossier', 'À corriger', '', '')[section]
        return None

    def remplacer(self, fiches):
        self.beginResetModel()
        self.fiches = sorted(fiches, key=lambda f: (f['date_modification'], f['id']), reverse=True)
        self.lignes = {f['id']: i for i, f in enumerate(self.fiches)}
        self.endResetModel()


class FiltreProblemes(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mots, self.probleme = [], ''
        self.dossier = None

    def filterAcceptsRow(self, ligne, parent):
        f = self.sourceModel().fiches[ligne]
        return (not self.probleme or self.probleme in f['problemes']) and (self.dossier is None or f['dossier'] == self.dossier) and all(m in f['_recherche'] for m in self.mots)


class LignesProblemes(QStyledItemDelegate):
    def __init__(self, page):
        super().__init__(page.vue)
        self.page, self.nom = page, LignesFocus(page)

    def sizeHint(self, option, index):
        return QSize(100, self.page.hauteur_ligne())

    def paint(self, painter, option, index):
        if index.column() == 0:
            self.nom.paint(painter, option, index)
            return
        f, c = index.data(Qt.ItemDataRole.UserRole), self.page.app.couleurs
        facteur = self.page.app.echelle / 100
        r = QRectF(option.rect)
        selection = bool(option.state & QStyle.StateFlag.State_Selected)
        survol = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.fillRect(r, QColor(c['accent_soft'] if selection else c['surface_alt'] if survol else c['surface']))
        painter.setPen(QPen(QColor(c['border']), .5))
        painter.drawLine(r.bottomLeft(), r.bottomRight())
        police = QFont('Segoe UI Variable')
        police.setPointSizeF(9.5 * facteur)
        painter.setFont(police)
        if index.column() == 1:
            painter.setPen(QColor(c['muted']))
            texte = r.adjusted(10 * facteur, 0, -8 * facteur, 0)
            painter.drawText(texte, Qt.AlignmentFlag.AlignVCenter, painter.fontMetrics().elidedText(f['dossier_nom'], Qt.TextElideMode.ElideRight, max(1, int(texte.width()))))
        elif index.column() == 2:
            police.setPointSizeF(8.5 * facteur)
            painter.setFont(police)
            x, haut = r.left() + 8 * facteur, 23 * facteur
            largeur = sum(painter.fontMetrics().horizontalAdvance(LIBELLES[p]) + 18 * facteur for p in f['problemes']) + max(0, len(f['problemes']) - 1) * 5 * facteur
            compact = largeur > r.width() - 16 * facteur
            for probleme in f['problemes']:
                libelle = {'faibles': 'F', 'reutilises': 'R', 'exposes': 'E'}[probleme] if compact else LIBELLES[probleme]
                largeur = painter.fontMetrics().horizontalAdvance(libelle) + 18 * facteur
                badge = QRectF(x, r.center().y() - haut / 2, largeur, haut)
                couleur = QColor(c['danger'] if probleme == 'exposes' else c['warning'])
                fond = QColor(couleur)
                fond.setAlpha(22 if self.page.app.theme == 'light' else 40)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(fond)
                painter.drawRoundedRect(badge, haut / 2, haut / 2)
                painter.setPen(couleur)
                painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, libelle)
                x += largeur + 5 * facteur
        elif index.column() == 3:
            painter.setPen(QColor(c['accent_text']))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, 'Modifier')
        else:
            cote = 16 * facteur
            dessiner_icone(painter, QRectF(r.center().x() - cote / 2, r.center().y() - cote / 2, cote, cote), 'suivant', c['muted'])
        painter.restore()


class TableProblemes(QTableView):
    def __init__(self, page):
        super().__init__()
        self.page = page

    def mouseReleaseEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        f = index.data(Qt.ItemDataRole.UserRole) if index.isValid() else None
        if event.button() == Qt.MouseButton.LeftButton and f and f.get('_groupe'):
            self.page.basculer_groupe(f['_site_cle'])
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and index.isValid() and index.column() in (3, 4):
            self.setCurrentIndex(index.siblingAtColumn(0))
            fid = index.data(Qt.ItemDataRole.UserRole)['id']
            self.page.app.liste.modifier(fid) if index.column() == 3 else self.page.ouvrir_fiche(fid)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        index = self.currentIndex()
        if index.isValid() and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_M):
            f = index.data(Qt.ItemDataRole.UserRole)
            if f.get('_groupe'):
                if event.key() != Qt.Key.Key_M:
                    self.page.basculer_groupe(f['_site_cle'])
                event.accept()
                return
            fid = f['id']
            self.page.app.liste.modifier(fid) if event.key() == Qt.Key.Key_M else self.page.ouvrir_fiche(fid)
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.page.adapter()


class PageSecurite(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app, self.deplie_id, self.critere = app, None, ''
        self.ajustement = QTimer(self)
        self.ajustement.setSingleShot(True)
        self.ajustement.timeout.connect(self.adapter)
        self.setObjectName('page_focus')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 12, 22, 12)
        layout.setSpacing(10)
        outils = QWidget()
        self.outils_contenu = outils
        outils.installEventFilter(self)
        contenu = QVBoxLayout(outils)
        contenu.setContentsMargins(0, 0, 0, 0)
        contenu.setSpacing(10)
        self.outils = defilement(outils)
        self.outils.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.outils)
        titre = QHBoxLayout()
        titre.addWidget(etiquette('Sécurité', 'titre'))
        self.nombre = etiquette('', 'secondaire')
        titre.addWidget(self.nombre)
        titre.addStretch()
        contenu.addLayout(titre)
        cadre = QFrame()
        cadre.setObjectName('resume_securite')
        bandeau = QVBoxLayout(cadre)
        bandeau.setContentsMargins(14, 10, 14, 10)
        bandeau.setSpacing(0)
        ligne = LigneSouple(690)
        score = QHBoxLayout()
        score.setSpacing(10)
        self.score_icone = Symbole('bouclier', taille=34)
        score.addWidget(self.score_icone)
        libelles = QVBoxLayout()
        libelles.setSpacing(2)
        libelles.addWidget(etiquette('Score de sécurité', 'secondaire'))
        self.score = etiquette('—', 'score_securite')
        libelles.addWidget(self.score)
        score.addLayout(libelles)
        ligne.ligne.addLayout(score, 1)
        bilan = QVBoxLayout()
        bilan.setSpacing(5)
        self.revoir = etiquette('À analyser', 'sous_titre')
        bilan.addWidget(self.revoir)
        self.barre_score = QProgressBar()
        self.barre_score.setObjectName('score_compact')
        self.barre_score.setRange(0, 100)
        self.barre_score.setTextVisible(False)
        self.barre_score.setAccessibleName('Score de sécurité sur 100')
        bilan.addWidget(self.barre_score)
        self.etat = etiquette('', 'secondaire')
        bilan.addWidget(self.etat)
        ligne.ligne.addLayout(bilan, 2)
        commandes = QVBoxLayout()
        commandes.setSpacing(4)
        self.analyser = bouton('Analyser', app.analyser, 'principal', 'analyser')
        commandes.addWidget(self.analyser)
        self.derniere = etiquette('Aucune analyse effectuée', 'secondaire')
        commandes.addWidget(self.derniere)
        ligne.ligne.addLayout(commandes, 1)
        bandeau.addWidget(ligne)
        contenu.addWidget(cadre)
        contenu.addWidget(etiquette('Comptes à corriger', 'sous_titre'))
        self.zone_filtres = QWidget()
        self.ligne_filtres = QGridLayout(self.zone_filtres)
        self.ligne_filtres.setContentsMargins(0, 0, 0, 0)
        self.ligne_filtres.setSpacing(4)
        self.ligne_filtres.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.disposition_filtres = None
        self.filtres, self.groupe = {}, QButtonGroup(self)
        self.groupe.setExclusive(True)
        for cle, libelle in (('', 'Tous'), ('faibles', 'Faibles'), ('reutilises', 'Réutilisés'), ('exposes', 'Exposés')):
            b = bouton(libelle + '  —', lambda _=False, p=cle: self.choisir(p), 'filtre_focus')
            b.setCheckable(True)
            b.setMinimumHeight(32)
            self.groupe.addButton(b)
            self.filtres[cle] = b
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self.ligne_filtres.addWidget(b, 0, len(self.filtres) - 1)
        self.filtres[''].setChecked(True)
        filtres = LigneSouple(590)
        filtres.ligne.addWidget(self.zone_filtres, 1)
        self.dossiers = Choix()
        self.dossiers.addItem('Tous les dossiers', None)
        self.dossiers.setMinimumHeight(32)
        self.dossiers.setMinimumContentsLength(15)
        self.dossiers.setSizeAdjustPolicy(Choix.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.dossiers.setAccessibleName('Filtrer les comptes à corriger par dossier')
        self.dossiers.currentIndexChanged.connect(self.filtrer)
        filtres.ligne.addWidget(self.dossiers)
        contenu.addWidget(filtres)
        self.recherche = champ(indication='Rechercher un compte ou un site · Ctrl K')
        self.recherche.setObjectName('recherche_focus')
        self.recherche.setMinimumWidth(0)
        self.recherche.setMinimumHeight(36)
        self.recherche.setAccessibleName('Rechercher dans les fiches à revoir')
        self.recherche.addAction(icone('recherche'), self.recherche.ActionPosition.LeadingPosition).setEnabled(False)
        self.minuterie = QTimer(self)
        self.minuterie.setSingleShot(True)
        self.minuterie.timeout.connect(self.filtrer)
        self.recherche.textChanged.connect(lambda: self.minuterie.start(90))
        self.modele, self.proxy = ModeleProblemes(self), FiltreProblemes(self)
        self.proxy.setSourceModel(self.modele)
        self.groupes = GroupesSites(self.proxy, self)
        self.vue = TableProblemes(self)
        self.vue.setObjectName('table_focus')
        self.vue.setModel(self.groupes)
        self.vue.setItemDelegate(LignesProblemes(self))
        self.vue.setShowGrid(False)
        self.vue.setFrameShape(QFrame.Shape.NoFrame)
        self.vue.setMouseTracking(True)
        self.vue.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.vue.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.vue.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.vue.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.vue.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.vue.setAccessibleName('Fiches à revoir : Entrée pour ouvrir, M pour modifier. F = faible, R = réutilisé, E = exposé.')
        self.vue.verticalHeader().hide()
        self.vue.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        entete = self.vue.horizontalHeader()
        entete.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        entete.setMinimumSectionSize(1)
        entete.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.vue.doubleClicked.connect(self.double_clic)
        layout.addWidget(self.vue, 1)
        self.vide = etiquette('', 'secondaire')
        layout.addWidget(self.vide)
        pied = QWidget()
        self.pied_contenu = pied
        pied.installEventFilter(self)
        self.pied = defilement(pied)
        self.pied.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        pied_layout = QVBoxLayout(pied)
        pied_layout.setContentsMargins(0, 0, 0, 0)
        secondaire = QFrame()
        secondaire.setObjectName('bandeau_securite')
        interieur = QVBoxLayout(secondaire)
        interieur.setContentsMargins(14, 8, 14, 8)
        fuites = LigneSouple(610)
        texte_fuites = QVBoxLayout()
        texte_fuites.setSpacing(3)
        titres = QHBoxLayout()
        titres.addWidget(etiquette('Fuites de données', 'sous_titre'))
        self.etat_fuites = etiquette('Non vérifiées', 'etat_fuites')
        titres.addWidget(self.etat_fuites)
        titres.addStretch()
        texte_fuites.addLayout(titres)
        self.aide_fuites = etiquette('Vérification en ligne à votre demande.', 'secondaire')
        texte_fuites.addWidget(self.aide_fuites)
        fuites.ligne.addLayout(texte_fuites, 1)
        self.verifier = bouton('Vérifier en ligne', lambda: app.analyser(True), 'secondaire_securite', 'globe')
        fuites.ligne.addWidget(self.verifier)
        interieur.addWidget(fuites)
        pied_layout.addWidget(secondaire)
        layout.addWidget(self.pied)
        for widget in (*outils.findChildren(QWidget), *pied.findChildren(QWidget)):
            if widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
                widget.installEventFilter(self)
        self.actualiser()

    def hauteur_ligne(self):
        return round(46 * self.app.echelle / 100)

    def double_clic(self, index):
        f = index.data(Qt.ItemDataRole.UserRole)
        if f and not f.get('_groupe') and index.column() < 3:
            self.ouvrir_fiche(f['id'])

    def reconstruire_groupes(self):
        self.groupes.reconstruire(self.recherche.text().strip().casefold())
        self.vue.clearSpans()
        for ligne, f in enumerate(self.groupes.lignes):
            if f.get('_groupe'):
                self.vue.setSpan(ligne, 0, 1, self.groupes.columnCount())

    def basculer_groupe(self, cle):
        position = self.vue.verticalScrollBar().value()
        self.groupes.basculer(cle)
        self.reconstruire_groupes()
        self.vue.setCurrentIndex(self.groupes.index_id('groupe:' + cle))
        self.vue.verticalScrollBar().setValue(position)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adapter()

    def eventFilter(self, objet, event):
        if event.type() == QEvent.Type.FocusIn:
            for zone in (self.outils, self.pied):
                if zone.widget().isAncestorOf(objet):
                    zone.ensureWidgetVisible(objet, 8, 8)
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self.ajustement.start(0)
        return False

    def adapter(self):
        if not hasattr(self, 'vue'):
            return
        facteur = self.app.echelle / 100
        visibles = [b for b in self.filtres.values() if not b.isHidden()]
        disponible = max(1, self.outils.viewport().width())
        colonnes = len(visibles) if sum(b.sizeHint().width() + 4 for b in visibles) <= disponible else max(1, int(disponible / max(b.sizeHint().width() + 4 for b in visibles)))
        disposition = (tuple(visibles), colonnes)
        if disposition != self.disposition_filtres:
            for b in self.filtres.values():
                self.ligne_filtres.removeWidget(b)
            for i, b in enumerate(visibles):
                self.ligne_filtres.addWidget(b, i // colonnes, i % colonnes)
            self.disposition_filtres = disposition
        def hauteur(contenu, zone):
            mesure = contenu.layout().totalHeightForWidth(max(1, zone.viewport().width()))
            return mesure if mesure >= 0 else contenu.sizeHint().height()
        self.outils.setMaximumHeight(max(90, min(hauteur(self.outils_contenu, self.outils) + 4, self.height() // 2)))
        self.pied.setMaximumHeight(max(64, min(hauteur(self.pied_contenu, self.pied) + 4, self.height() // 4)))
        self.score_icone.couleur = self.app.couleurs['accent']
        self.score_icone.update()
        self.barre_score.setFixedHeight(round(6 * facteur))
        self.vue.verticalHeader().setDefaultSectionSize(self.hauteur_ligne())
        largeur = self.vue.viewport().width()
        self.vue.setColumnHidden(1, largeur < 620 * facteur)
        self.vue.setColumnHidden(3, largeur < 600 * facteur)
        fleche = round(36 * facteur)
        action = 0 if self.vue.isColumnHidden(3) else round(78 * facteur)
        problemes = min(round(240 * facteur), round(largeur * .38))
        identifiant = 0 if self.vue.isColumnHidden(1) else round(largeur * .28)
        for col, taille in ((0, max(20, largeur - fleche - action - problemes - identifiant)), (1, identifiant), (2, problemes), (3, action), (4, fleche)):
            if not self.vue.isColumnHidden(col):
                self.vue.setColumnWidth(col, taille)

    def choisir(self, probleme):
        self.critere = probleme
        self.filtrer()

    def filtrer(self):
        if not hasattr(self, 'groupes'):
            return
        self.minuterie.stop()
        courant = self.vue.currentIndex().data(Qt.ItemDataRole.UserRole)
        position = self.vue.verticalScrollBar().value()
        self.proxy.mots, self.proxy.probleme = self.recherche.text().strip().casefold().split(), self.critere
        self.proxy.dossier = self.dossiers.currentData()
        self.proxy.invalidateFilter()
        self.reconstruire_groupes()
        if courant and self.groupes.index_id(courant['id']).isValid():
            self.vue.setCurrentIndex(self.groupes.index_id(courant['id']))
        self.vue.verticalScrollBar().setValue(position)
        eligibles = [f for f in self.modele.fiches if (self.proxy.dossier is None or f['dossier'] == self.proxy.dossier)
                     and all(m in f['_recherche'] for m in self.proxy.mots)]
        for cle, b in self.filtres.items():
            libelle = {'': 'Tous', 'faibles': 'Faibles', 'reutilises': 'Réutilisés', 'exposes': 'Exposés'}[cle]
            nombre = sum(not cle or cle in f['problemes'] for f in eligibles)
            b.setText(libelle + '  ' + (str(nombre) if self.app.analyse_courante() else '—'))
        self.afficher_vide()

    def afficher_vide(self):
        self.vide.setVisible(self.proxy.rowCount() == 0)
        if not self.app.analyse_courante():
            texte = 'Analyse en cours…' if self.app.analyse_en_cours else 'Relancez une analyse après vos modifications.' if self.app.analyse_perimee else 'Analysez vos mots de passe pour voir les fiches à revoir.'
        elif not self.app.analyse['total']:
            texte = 'Aucun mot de passe à analyser.'
        elif not self.modele.fiches:
            texte = 'Aucun problème détecté par les contrôles effectués.'
        else:
            texte = 'Aucune fiche ne correspond à ces filtres.'
        self.vide.setText(texte)

    def actualiser(self):
        r = self.app.analyse_courante()
        nombre = sum(f['secret_present'] for f in self.app.vue['fiches']) if self.app.vue else 0
        self.nombre.setText(f'{nombre} mot' + ('s' if nombre != 1 else '') + ' de passe')
        union = set().union(*(r.get(k, set()) for k in LIBELLES)) if r else set()
        score = self.app.score_analyse()
        self.score.setText(f'{score} / 100' if score is not None else '—')
        self.barre_score.setVisible(score is not None)
        if score is not None:
            self.barre_score.setValue(score)
        self.revoir.setText((f'{len(union)} compte' + ('s' if len(union) != 1 else '') + ' à corriger') if r else 'À analyser')
        self.etat.setText('Analyse locale en cours…' if self.app.analyse_en_cours == 'locale' else
                          self.app.analyse_erreur or ('Résultats périmés · relancez l’analyse.' if self.app.analyse_perimee else
                          ('Aucun mot de passe à analyser.' if r and not r['total'] else 'Analyse locale.' if r else 'Analyse locale à votre demande.')))
        date = self.app.derniere_analyse
        self.derniere.setText('Dernière analyse : ' + date.strftime('%d/%m à %H:%M') + (' · périmée' if self.app.analyse_perimee else '') if date else 'Aucune analyse effectuée')
        self.analyser.setEnabled(bool(nombre) and not self.app.analyse_en_cours)
        self.analyser.setText('Analyse…' if self.app.analyse_en_cours == 'locale' else 'Analyser')
        for cle, b in self.filtres.items():
            libelle = {'': 'Tous', 'faibles': 'Faibles', 'reutilises': 'Réutilisés', 'exposes': 'Exposés'}[cle]
            compteur = len(r[cle]) if r and cle in r else len(union) if r and not cle else None
            if cle == 'exposes':
                connu = r is not None and 'exposes' in r
                b.setVisible(connu)
                compteur = len(r['exposes']) if connu else None
            b.setText(libelle + '  ' + (str(compteur) if compteur is not None else '—'))
            b.setEnabled(r is not None)
        if self.critere == 'exposes' and (not r or 'exposes' not in r):
            self.critere = ''
            self.filtres[''].setChecked(True)
        courant = self.vue.currentIndex().data(Qt.ItemDataRole.UserRole)
        position = self.vue.verticalScrollBar().value()
        fiches = [{**f, 'problemes': tuple(k for k in LIBELLES if f['id'] in r.get(k, set()))} for f in self.app.liste.modele.fiches if f['id'] in union] if r else []
        self.modele.remplacer(fiches)
        dossier = self.dossiers.currentData()
        self.dossiers.blockSignals(True)
        self.dossiers.clear()
        self.dossiers.addItem('Tous les dossiers', None)
        self.dossiers.addItem('Sans dossier', '')
        for d in self.app.vue['dossiers'] if self.app.vue else ():
            self.dossiers.addItem(d['nom'], d['id'])
        self.dossiers.setCurrentIndex(max(0, self.dossiers.findData(dossier)))
        self.dossiers.blockSignals(False)
        self.filtrer()
        if courant and courant['id'] in self.modele.lignes:
            index = self.groupes.index_id(courant['id'])
            if index.isValid():
                self.vue.setCurrentIndex(index)
        self.vue.verticalScrollBar().setValue(position)
        if self.app.analyse_en_cours == 'fuites':
            fuites = 'Vérification…'
        elif self.app.fuites_erreur:
            fuites = 'Interrompue' if 'interrompue' in self.app.fuites_erreur else 'Vérification échouée'
        elif r and 'exposes' in r:
            n = len(r['exposes'])
            fuites = f'{n} exposé' + ('s' if n != 1 else '')
        else:
            fuites = 'Non vérifiées'
        self.etat_fuites.setText(fuites)
        self.aide_fuites.setText('Vérification en ligne à votre demande.' + (' Réessayez plus tard.' if self.app.fuites_erreur else ''))
        self.verifier.setEnabled(bool(nombre) and not self.app.analyse_en_cours)
        self.adapter()

    def ouvrir_fiche(self, fid):
        # Conserver les filtres Focus ; une fiche filtrée reste accessible en dialogue.
        liste = self.app.liste
        index = liste.rendre_visible(fid)
        if index.isValid():
            self.app.afficher_page('identifiants')
            liste.vue.setCurrentIndex(index)
            liste.deplier(fid)
            liste.vue.scrollTo(index)
        else:
            self.app.details(fid)
