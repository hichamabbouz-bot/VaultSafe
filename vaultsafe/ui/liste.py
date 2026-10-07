"""Vue Focus : table virtualisée et une seule fiche dépliée à la demande."""
from PySide6.QtCore import QEvent, QPoint, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import QAbstractItemView, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLineEdit, QSizePolicy, QStyle, QStyledItemDelegate, QTableView, QVBoxLayout, QWidget
from shiboken6 import isValid
from vaultsafe.ui.composants import Choix, LigneSouple, Menu, bouton, champ, defilement, editer_note, etiquette
from vaultsafe.modele import TYPES
from vaultsafe.ui.modeles_fiches import ModeleFiches, FiltreFiches, date_affichee
from vaultsafe.ui.groupes import GroupesSites
from vaultsafe.ui.icones import dessiner_icone, icone
from vaultsafe.ui.identite_service import dessiner_service


class LignesFocus(QStyledItemDelegate):
    def __init__(self, liste):
        super().__init__(liste.vue)
        self.liste, self.app = liste, liste.app

    def sizeHint(self, option, index):
        return QSize(100, self.liste.hauteur_ligne())

    def paint(self, painter, option, index):
        f = index.data(Qt.ItemDataRole.UserRole)
        if not f:
            return
        c, facteur = self.app.couleurs, self.app.echelle / 100
        def px(n):
            return round(n * facteur)
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform)
        groupe = f.get('_groupe', False)
        ouvert = not groupe and f['id'] == self.liste.deplie_id
        selection = bool(option.state & QStyle.StateFlag.State_Selected)
        survol = bool(option.state & QStyle.StateFlag.State_MouseOver)
        fond = c['accent_soft'] if selection or ouvert else c['surface_alt'] if survol else c['surface']
        painter.fillRect(option.rect, QColor(fond))
        r = QRectF(option.rect.x(), option.rect.y(), option.rect.width(), self.liste.hauteur_ligne())
        painter.setPen(QPen(QColor(c['border']), .5))
        if not ouvert:
            painter.drawLine(r.bottomLeft(), r.bottomRight())
        police = QFont('Segoe UI Variable')
        police.setPointSizeF(9.5 * facteur)
        police.setWeight(QFont.Weight.DemiBold if ouvert else QFont.Weight.Normal)
        painter.setFont(police)
        painter.setPen(QColor(c['text']))
        col = index.column()
        if groupe:
            if col == 0:
                dessiner_icone(painter, QRectF(r.left() + px(8), r.center().y() - px(7), px(14), px(14)),
                              'bas' if f['_ouvert'] else 'suivant', c['muted'])
                pastille = QRectF(r.left() + px(32), r.center().y() - px(13), px(26), px(26))
                dessiner_service(painter, pastille, f['_icone_source'], self.app)
                police.setWeight(QFont.Weight.DemiBold)
                painter.setFont(police)
                painter.setPen(QColor(c['text']))
                debut = r.left() + px(72)
                disponible = max(1, int(r.right() - debut - px(100)))
                nom = painter.fontMetrics().elidedText(f['_site_nom'], Qt.TextElideMode.ElideRight, disponible)
                painter.drawText(QRectF(debut, r.top(), disponible, r.height()), Qt.AlignmentFlag.AlignVCenter, nom)
                x = debut + painter.fontMetrics().horizontalAdvance(nom) + px(16)
                police.setWeight(QFont.Weight.Normal)
                police.setPointSizeF(8.5 * facteur)
                painter.setFont(police)
                painter.setPen(QColor(c['muted']))
                compteur = f['_compteur'] + ' ' + f['_unite'] + ('s' if f['_nombre'] != 1 else '')
                painter.drawText(QRectF(x, r.top(), max(1, r.right() - x - px(8)), r.height()), Qt.AlignmentFlag.AlignVCenter, compteur)
        elif col == 0:
            retrait = 32 if f.get('_en_groupe') else 10
            pastille = QRectF(r.left() + px(retrait), r.center().y() - px(13), px(26), px(26))
            dessiner_service(painter, pastille, f, self.app)
            painter.setPen(QColor(c['text']))
            texte = r.adjusted(px(retrait + 34), px(5), -px(8), -px(5))
            police.setWeight(QFont.Weight.DemiBold)
            painter.setFont(police)
            premiere = QRectF(texte.left(), texte.top(), texte.width(), texte.height() / 2)
            painter.drawText(premiere, Qt.AlignmentFlag.AlignVCenter, painter.fontMetrics().elidedText(f['_libelle'], Qt.TextElideMode.ElideRight, max(1, int(texte.width()))))
            police.setWeight(QFont.Weight.Normal)
            police.setPointSizeF(8 * facteur)
            painter.setFont(police)
            painter.setPen(QColor(c['muted']))
            seconde = QRectF(texte.left(), premiere.bottom(), texte.width(), texte.height() / 2)
            valeur = f['nom_utilisateur'] or f['_hote'] or TYPES[f['type']]
            painter.drawText(seconde, Qt.AlignmentFlag.AlignVCenter, painter.fontMetrics().elidedText(valeur, Qt.TextElideMode.ElideRight, max(1, int(texte.width()))))
        elif col in (3, 4, 5, 6):
            symbole = ('etoile_pleine' if f['favori'] else 'etoile') if col == 3 else 'copier' if col == 4 else ('bas' if ouvert else 'suivant') if col == 5 else 'plus_options'
            cote = px(16)
            dessiner_icone(painter, QRectF(r.center().x() - cote / 2, r.center().y() - cote / 2, cote, cote), symbole,
                          c['accent_text'] if col == 3 and f['favori'] else c['muted'])
        else:
            painter.setPen(QColor(c['muted']))
            texte = r.adjusted(px(10), 0, -px(8), 0)
            valeur = f['dossier_nom'] if col == 1 else date_affichee(f['date_modification'])
            painter.drawText(texte, Qt.AlignmentFlag.AlignVCenter, painter.fontMetrics().elidedText(valeur or '—', Qt.TextElideMode.ElideRight, max(1, int(texte.width()))))
        painter.restore()


class TableFocus(QTableView):
    def __init__(self, liste):
        super().__init__()
        self.liste, self.double = liste, False

    def mouseReleaseEvent(self, event):
        if self.double:
            self.double = False
            event.accept()
            return
        index = self.indexAt(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and index.isValid() and event.position().y() < self.visualRect(index).top() + self.liste.hauteur_ligne():
            self.setCurrentIndex(index.siblingAtColumn(0))
            f = index.data(Qt.ItemDataRole.UserRole)
            fid = f['id']
            if f.get('_groupe'):
                self.liste.basculer_groupe(f['_site_cle'])
            elif index.column() == 3:
                self.liste.favori(fid)
            elif index.column() == 4:
                if f['nom_utilisateur']:
                    self.liste.app.copier_champ_fiche(fid, 'nom_utilisateur')
            elif index.column() == 6:
                self.liste.menu_fiche(fid, event.globalPosition().toPoint())
            else:
                self.liste.basculer(fid)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double = True
        event.accept()

    def keyPressEvent(self, event):
        index = self.currentIndex()
        f = index.data(Qt.ItemDataRole.UserRole) if index.isValid() else None
        fid = f['id'] if f else None
        if f and f.get('_groupe'):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                self.liste.basculer_groupe(f['_site_cle'])
                event.accept()
                return
            if event.key() in (Qt.Key.Key_F, Qt.Key.Key_Menu, Qt.Key.Key_F10):
                event.accept()
                return
        if fid and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.liste.basculer(fid)
        elif event.key() == Qt.Key.Key_Escape:
            self.liste.replier()
        elif fid and event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.liste.favori(fid)
        elif fid and (event.key() == Qt.Key.Key_Menu or (event.key() == Qt.Key.Key_F10 and event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            self.liste.menu_fiche(fid, self.viewport().mapToGlobal(self.visualRect(index).center()))
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if index.isValid() and not index.data(Qt.ItemDataRole.UserRole).get('_groupe'):
            self.liste.menu_fiche(index.data(Qt.ItemDataRole.UserRole)['id'], event.globalPos())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.liste.adapter_table()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.liste.positionner_detail()


class DetailFocus(QFrame):
    def __init__(self, liste):
        super().__init__(liste.vue.viewport())
        self.setObjectName('detail_focus')
        self.sensible = True
        self.liste, self.app, self.fiche = liste, liste.app, None
        self.entrees, self.blocs, self.colonnes = [], [], 0
        self.note_texte = ''
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 8, 12, 8)
        self.layout.setSpacing(6)
        self.chargement = etiquette('Chargement…', 'secondaire')
        self.layout.addWidget(self.chargement)
        self.erreur = etiquette('', 'erreur')
        self.layout.addWidget(self.erreur)
        self.erreur.hide()

    def afficher(self, fiche):
        self.fiche = fiche
        fid = fiche.id
        self.chargement.hide()
        self.grille = QGridLayout()
        self.grille.setContentsMargins(0, 0, 0, 0)
        self.grille.setHorizontalSpacing(14)
        self.grille.setVerticalSpacing(8)
        self.layout.insertLayout(1, self.grille)
        valeurs = []
        if fiche.nom_utilisateur:
            valeurs.append(('Identifiant', fiche.nom_utilisateur, False, 'nom_utilisateur'))
        if fiche.mot_de_passe:
            valeurs.append(('Mot de passe', fiche.mot_de_passe, True, 'mot_de_passe'))
        if fiche.site:
            valeurs.append(('Site web', fiche.site, False, 'site'))
        valeurs.extend((c['nom'], c['valeur'], c['secret'], ('champs', c['nom'])) for c in fiche.champs)
        for libelle, valeur, secret, cle in valeurs[:3]:
            bloc = QWidget()
            boite = QVBoxLayout(bloc)
            boite.setContentsMargins(0, 0, 0, 0)
            boite.setSpacing(4)
            boite.addWidget(etiquette(libelle, 'secondaire'))
            entree = champ(valeur, secret, oeil=secret)
            entree.setObjectName('valeur_lecture')
            entree.setReadOnly(True)
            entree.setProperty('confidentiel', True)
            entree.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            entree.setMinimumWidth(0)
            entree.setAccessibleName(libelle)
            action = entree.addAction(icone('copier'), QLineEdit.ActionPosition.TrailingPosition)
            action.setText('Copier ' + libelle)
            action.setToolTip(action.text())
            if cle == 'site':
                from vaultsafe.ui.fiches import ouvrir_site
                ouvrir = entree.addAction(icone('ouvrir'), QLineEdit.ActionPosition.TrailingPosition)
                ouvrir.setText('Ouvrir le site')
                ouvrir.setToolTip('Ouvrir le site')
                ouvrir.triggered.connect(lambda: ouvrir_site(self, self.fiche.site) if self.fiche else None)
            action.triggered.connect(lambda _=False, c=cle: self.app.copier_champ_fiche(fid, c))
            boite.addWidget(entree)
            self.entrees.append(entree)
            self.blocs.append(bloc)
        pied = QWidget()
        ligne = QHBoxLayout(pied)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(8)
        if fiche.notes:
            self.note_texte = 'Note : ' + ' '.join(fiche.notes.split())
            self.note = etiquette('', 'secondaire')
            self.note.setProperty('confidentiel', True)
            self.note.setWordWrap(False)
            self.note.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            ligne.addWidget(self.note, 1)
            self.lire_note = bouton('Voir la note', lambda: editer_note(self.app, self.fiche.notes, True) if self.fiche else None, 'lien')
            self.lire_note.setMinimumHeight(28)
            self.lire_note.hide()
            ligne.addWidget(self.lire_note)
        else:
            ligne.addStretch()
        self.layout.addWidget(pied)
        modifier = bouton('', lambda: self.liste.modifier(fid), 'action_lecture', 'modifier')
        modifier.setAccessibleName('Modifier la fiche')
        modifier.setToolTip('Modifier la fiche')
        modifier.setFixedWidth(32)
        ligne.addWidget(modifier)
        pied.show()
        self.adapter(self.liste.vue.viewport().width() - 16)
        for widget in self.findChildren(QWidget):
            if widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
                widget.installEventFilter(self)

    def adapter(self, largeur):
        if self.blocs:
            facteur = self.app.echelle / 100
            colonnes = min(len(self.blocs), max(1, int(largeur / (230 * facteur))))
            if colonnes != self.colonnes:
                for i, bloc in enumerate(self.blocs):
                    self.grille.addWidget(bloc, i // colonnes, i % colonnes)
                    bloc.show()
                self.colonnes = colonnes
        self.layout.activate()

    def event(self, event):
        resultat = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest and getattr(self, 'liste', None) and self.liste.detail is self:
            self.liste.positionner_detail()
        return resultat

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.note_texte:
            disponible = self.note.width() + (self.lire_note.width() + 8 if self.lire_note.isVisible() else 0)
            longue = self.note.fontMetrics().horizontalAdvance(self.note_texte) > disponible
            self.lire_note.setVisible(longue)
            self.note.setText(self.note.fontMetrics().elidedText(self.note_texte, Qt.TextElideMode.ElideRight, max(1, self.note.width())))

    def eventFilter(self, objet, event):
        if event.type() == QEvent.Type.FocusIn:
            viewport = self.liste.vue.viewport()
            haut = objet.mapTo(viewport, QPoint()).y()
            bas = haut + objet.height()
            barre = self.liste.vue.verticalScrollBar()
            if haut < 0:
                barre.setValue(barre.value() + haut - 8)
            elif bas > viewport.height():
                barre.setValue(barre.value() + bas - viewport.height() + 8)
        return False

    def nettoyer(self):
        for entree in self.entrees:
            entree.clear()
        self.fiche, self.note_texte = None, ''
        if hasattr(self, 'note'):
            self.note.clear()

    def closeEvent(self, event):
        self.nettoyer()
        event.accept()


class ListeFiches(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app, self.actif = app, True
        self.setObjectName('page_focus')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.deplie_id, self.detail, self.futur = None, None, None
        self.numero, self.revision, self.actualisation = 0, None, False
        self.ordre = Qt.SortOrder.AscendingOrder
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 12, 22, 12)
        layout.setSpacing(8)
        outils = QWidget()
        boite = QVBoxLayout(outils)
        boite.setContentsMargins(0, 0, 0, 0)
        boite.setSpacing(10)
        self.outils_contenu = outils
        self.barre_outils = defilement(outils)
        self.barre_outils.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.barre_outils)
        entete = LigneSouple(560)
        titres = QHBoxLayout()
        titres.addWidget(etiquette('Mes identifiants', 'titre'))
        self.nombre = etiquette('0 fiche', 'secondaire')
        titres.addWidget(self.nombre)
        titres.addStretch()
        entete.ligne.addLayout(titres, 1)
        actions = QHBoxLayout()
        self.score = bouton('Sécurité  —', lambda: app.afficher_page('securite'), 'score_focus', 'bouclier')
        actions.addWidget(self.score)
        actions.addWidget(bouton('Ajouter', app.nouvelle_fiche, 'principal', 'plus'))
        entete.ligne.addLayout(actions)
        boite.addWidget(entete)
        self.recherche = champ(indication='Rechercher un compte ou un site · Ctrl K')
        self.recherche.setObjectName('recherche_focus')
        self.recherche.setAccessibleName('Rechercher une fiche')
        self.recherche.setMinimumWidth(0)
        self.recherche.setMinimumHeight(36)
        self.recherche.addAction(icone('recherche'), QLineEdit.ActionPosition.LeadingPosition).setEnabled(False)
        self.recherche_timer = QTimer(self)
        self.recherche_timer.setSingleShot(True)
        self.recherche_timer.timeout.connect(self.filtrer)
        self.recherche.textChanged.connect(lambda: self.recherche_timer.start(90))
        filtres = LigneSouple(500)
        filtres.ligne.setContentsMargins(0, 0, 0, 0)
        rapides = QHBoxLayout()
        rapides.setSpacing(4)
        self.rapides, self.groupe = {}, QButtonGroup(self)
        self.groupe.setExclusive(True)
        for titre, cle in (('Tous', 'tous'), ('Favoris', 'favoris'), ('Récents', 'recents')):
            b = bouton(titre, lambda _=False, k=cle: self.choisir_rapide(k), 'filtre_focus')
            b.setCheckable(True)
            b.setMinimumHeight(32)
            self.groupe.addButton(b)
            self.rapides[cle] = b
            rapides.addWidget(b)
        self.rapides['tous'].setChecked(True)
        rapides.addStretch()
        filtres.ligne.addLayout(rapides, 1)
        self.dossiers = Choix()
        self.dossiers.setMinimumHeight(32)
        self.dossiers.setAccessibleName('Filtrer par dossier')
        self.dossiers.setSizeAdjustPolicy(Choix.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.dossiers.setMinimumContentsLength(15)
        filtres.ligne.addWidget(self.dossiers)
        organisation = bouton('', role='icone', symbole='reglages')
        organisation.setCheckable(True)
        organisation.setAccessibleName('Filtres et organisation')
        organisation.setToolTip('Filtres et organisation')
        organisation.setFixedWidth(32)
        filtres.ligne.addWidget(organisation)
        boite.addWidget(filtres)
        self.options = LigneSouple(620)
        self.types, self.etats = Choix(), Choix()
        self.types.addItem('Tous les types', '')
        for cle, valeur in TYPES.items():
            self.types.addItem(valeur, cle)
        for texte, valeur in (('Toutes les fiches', ''), ('Favoris', 'favoris'), ('Échéances', 'echeances'),
                             ('Faibles', 'faibles'), ('Réutilisés', 'reutilises'), ('Exposés', 'exposes')):
            self.etats.addItem(texte, valeur)
        for control in (self.types, self.etats):
            self.options.ligne.addWidget(control)
            control.currentIndexChanged.connect(self.filtrer)
        self.dossiers.currentIndexChanged.connect(self.filtrer)
        self.options.ligne.addWidget(bouton('Dossiers', app.dossiers, symbole='dossier'))
        self.options.ligne.addWidget(bouton('Corbeille', app.corbeille, symbole='corbeille'))
        self.options.hide()
        organisation.toggled.connect(self.options.setVisible)
        boite.addWidget(self.options)
        self.modele, self.proxy = ModeleFiches(self), FiltreFiches(self)
        self.proxy.setSourceModel(self.modele)
        self.groupes = GroupesSites(self.proxy, self)
        self.vue = TableFocus(self)
        self.vue.setObjectName('table_focus')
        self.vue.setModel(self.groupes)
        self.vue.setItemDelegate(LignesFocus(self))
        self.vue.setShowGrid(False)
        self.vue.setFrameShape(QFrame.Shape.NoFrame)
        self.vue.setMouseTracking(True)
        self.vue.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.vue.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.vue.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.vue.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.vue.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.vue.setAccessibleName('Identifiants : Entrée pour déplier, Échap pour replier, F pour les favoris, Maj+F10 pour les actions')
        self.vue.verticalHeader().hide()
        self.vue.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.vue.verticalHeader().setMinimumSectionSize(1)
        self.vue.horizontalHeader().setSectionsClickable(True)
        self.vue.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.vue.horizontalHeader().setMinimumSectionSize(1)
        self.vue.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.vue.horizontalHeader().sectionClicked.connect(self.trier_colonne)
        self.vue.selectionModel().currentChanged.connect(self.selection_changee)
        layout.addWidget(self.vue, 1)
        self.vide = etiquette('Aucune fiche. Ajoutez une fiche ou importez depuis Paramètres.', 'secondaire')
        layout.addWidget(self.vide)
        self.trier('date_modification')

    def hauteur_ligne(self):
        return round(46 * self.app.echelle / 100)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.barre_outils.setMaximumHeight(max(80, min(self.outils_contenu.sizeHint().height() + 4, self.height() // 2)))
        self.adapter_table()

    def adapter_table(self):
        if not hasattr(self, 'vue'):
            return
        largeur, facteur = self.vue.viewport().width(), self.app.echelle / 100
        if largeur < 1:
            return
        self.vue.verticalHeader().setDefaultSectionSize(self.hauteur_ligne())
        self.vue.setColumnHidden(1, largeur < 610 * facteur)
        self.vue.setColumnHidden(2, largeur < 740 * facteur)
        actions = round(34 * facteur)
        for col in (3, 4, 5, 6):
            self.vue.setColumnWidth(col, actions)
        reste = max(40, largeur - 4 * actions)
        nom = reste
        if not self.vue.isColumnHidden(1):
            part = round(reste * .26)
            self.vue.setColumnWidth(1, part)
            nom -= part
        if not self.vue.isColumnHidden(2):
            part = round(reste * .22)
            self.vue.setColumnWidth(2, part)
            nom -= part
        self.vue.setColumnWidth(0, max(40, nom))
        self.positionner_detail()

    def index_id(self, fid):
        return self.groupes.index_id(fid)

    def reconstruire_groupes(self):
        self.groupes.reconstruire(self.recherche.text().strip().casefold())
        self.vue.clearSpans()
        for ligne, f in enumerate(self.groupes.lignes):
            if f.get('_groupe'):
                self.vue.setSpan(ligne, 0, 1, self.groupes.columnCount())

    def basculer_groupe(self, cle):
        position = self.vue.verticalScrollBar().value()
        self.replier()
        self.actualisation = True
        self.groupes.basculer(cle)
        self.reconstruire_groupes()
        self.vue.setCurrentIndex(self.groupes.index_id('groupe:' + cle))
        self.vue.verticalScrollBar().setValue(position)
        self.actualisation = False

    def rendre_visible(self, fid):
        self.actualisation = True
        self.groupes.rendre_visible(fid)
        self.reconstruire_groupes()
        self.actualisation = False
        return self.index_id(fid)

    def selection_changee(self, courant, ancien):
        if not self.actualisation and courant.isValid() and self.deplie_id and courant.data(Qt.ItemDataRole.UserRole)['id'] != self.deplie_id:
            self.replier()

    def choisir_rapide(self, cle):
        self.etats.setCurrentIndex(self.etats.findData('favoris' if cle == 'favoris' else ''))
        self.trier('date_modification')
        self.filtrer()

    def trier(self, cle, ordre=None):
        self.proxy.tri = {'titre': '_nom', 'nom_utilisateur': '_identifiant', 'dossier': '_dossier'}.get(cle, cle)
        if ordre is None:
            ordre = Qt.SortOrder.DescendingOrder if cle in ('date_creation', 'date_modification') else Qt.SortOrder.AscendingOrder
        self.ordre = ordre
        courant = self.vue.currentIndex().data(Qt.ItemDataRole.UserRole) if hasattr(self, 'vue') else None
        position = self.vue.verticalScrollBar().value() if hasattr(self, 'vue') else 0
        self.actualisation = True
        self.modele.ordonner(self.proxy.tri, ordre == Qt.SortOrder.DescendingOrder)
        self.reconstruire_groupes()
        if courant and self.index_id(courant['id']).isValid():
            self.vue.setCurrentIndex(self.index_id(courant['id']))
        self.actualisation = False
        if hasattr(self, 'vue'):
            colonne = {'nom_utilisateur': 0, 'dossier': 1, 'date_modification': 2}.get(cle)
            self.vue.horizontalHeader().setSortIndicatorShown(colonne is not None)
            if colonne is not None:
                self.vue.horizontalHeader().setSortIndicator(colonne, ordre)
            self.positionner_detail()
            self.vue.verticalScrollBar().setValue(position)

    def trier_colonne(self, col):
        cle = {0: 'nom_utilisateur', 1: 'dossier', 2: 'date_modification'}.get(col)
        if cle:
            actuel = self.vue.horizontalHeader().sortIndicatorSection()
            ordre = Qt.SortOrder.DescendingOrder if actuel == col and self.ordre == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
            self.trier(cle, ordre)

    def filtrer(self):
        if not hasattr(self, 'proxy'):
            return
        from datetime import date, timedelta
        self.recherche_timer.stop()
        self.proxy.texte = self.recherche.text().strip().casefold()
        self.proxy.mots = self.proxy.texte.split()
        self.proxy.type_fiche = self.types.currentData() or ''
        self.proxy.dossier, self.proxy.etat = self.dossiers.currentData(), self.etats.currentData() or ''
        if self.proxy.etat == 'favoris':
            self.rapides['favoris'].setChecked(True)
        elif self.rapides['favoris'].isChecked():
            self.rapides['tous'].setChecked(True)
        self.proxy.echeance = (date.today() + timedelta(days=7)).isoformat()
        self.proxy.invalidateFilter()
        selection = self.vue.currentIndex().data(Qt.ItemDataRole.UserRole)
        ancienne_actualisation = self.actualisation
        self.actualisation = True
        position = self.vue.verticalScrollBar().value()
        self.reconstruire_groupes()
        if selection and self.index_id(selection['id']).isValid():
            self.vue.setCurrentIndex(self.index_id(selection['id']))
        self.actualisation = ancienne_actualisation
        if self.deplie_id and not self.index_id(self.deplie_id).isValid():
            self.replier()
        self.actualiser_nombre()
        self.positionner_detail()
        self.vue.verticalScrollBar().setValue(position)

    def actualiser_nombre(self):
        total, base = self.proxy.rowCount(), len(self.modele.fiches)
        sites = self.groupes.nombre_sites
        self.nombre.setText(f'{total} fiche' + ('s' if total != 1 else '') + (f' / {base}' if total != base else '') +
                            f' · {sites} site' + ('s' if sites != 1 else ''))
        self.vide.setVisible(total == 0)
        self.vide.setText('Aucune fiche ne correspond aux filtres.' if base else 'Aucune fiche. Ajoutez une fiche ou importez depuis Paramètres.')

    def actualiser(self, vue):
        selection = self.vue.currentIndex().data(Qt.ItemDataRole.UserRole)
        fid, position = selection['id'] if selection else None, self.vue.verticalScrollBar().value()
        recharge = self.deplie_id if self.revision != vue['revision'] else None
        ouvert = self.deplie_id
        if recharge:
            self.replier()
        self.actualisation = True
        self.modele.remplacer(vue['fiches'], vue['dossiers'], self.proxy.tri, self.ordre == Qt.SortOrder.DescendingOrder, table=vue.get('table'))
        self.revision = vue['revision']
        dossier = self.dossiers.currentData()
        self.dossiers.blockSignals(True)
        self.dossiers.clear()
        self.dossiers.addItem('Tous les dossiers', None)
        self.dossiers.addItem('Sans dossier', '')
        for d in vue['dossiers']:
            self.dossiers.addItem(d['nom'], d['id'])
        self.dossiers.setCurrentIndex(max(0, self.dossiers.findData(dossier)))
        self.dossiers.blockSignals(False)
        self.actualiser_analyse(refiltrer=False)
        self.filtrer()
        if fid and self.index_id(fid).isValid():
            self.vue.setCurrentIndex(self.index_id(fid))
        self.actualisation = False
        self.adapter_table()
        if ouvert and self.index_id(ouvert).isValid() and recharge:
            self.deplier(ouvert)
        self.vue.verticalScrollBar().setValue(position)

    def actualiser_analyse(self, refiltrer=True):
        resultat = self.app.analyse_courante()
        if resultat:
            self.proxy.faibles, self.proxy.reutilises, self.proxy.exposes = resultat['faibles'], resultat['reutilises'], resultat.get('exposes', set())
        else:
            self.proxy.faibles, self.proxy.reutilises, self.proxy.exposes = set(), set(), set()
        score = self.app.score_analyse()
        self.score.setText(f'Sécurité  {score} / 100' if score is not None else 'Sécurité  —')
        self.score.setToolTip('Analyse de sécurité' if score is None else 'Résultat de la dernière analyse locale')
        if refiltrer:
            self.filtrer()

    def basculer(self, fid):
        self.replier() if fid == self.deplie_id else self.deplier(fid)

    def deplier(self, fid):
        if not self.app.ouvert or not self.index_id(fid).isValid():
            return
        self.replier()
        self.deplie_id = fid
        self.detail = DetailFocus(self)
        self.detail.show()
        self.positionner_detail()
        numero, revision, gestion = self.numero, self.revision, self.app.identifiants
        def valide():
            return isValid(self) and self.actif and self.app.ouvert and self.deplie_id == fid and self.numero == numero and self.revision == revision
        def fini(fiche):
            if valide():
                if self.app.base.revision_courante != revision:
                    self.app.actualiser()
                else:
                    self.detail.afficher(fiche)
                    self.positionner_detail()
        def echec(erreur):
            if valide():
                self.detail.chargement.setText(erreur)
                self.positionner_detail()
        self.futur = self.app.taches.soumettre(lambda: gestion.afficher_identifiant(fid), fini, echec)
        self.vue.viewport().update()

    def replier(self):
        self.numero += 1
        fid, detail = self.deplie_id, self.detail
        self.deplie_id, self.detail = None, None
        if self.futur:
            self.futur.cancel()
            self.futur = None
        if fid and hasattr(self, 'vue'):
            index = self.index_id(fid)
            if index.isValid():
                self.vue.setRowHeight(index.row(), self.hauteur_ligne())
        if detail:
            detail.nettoyer()
            detail.hide()
            detail.deleteLater()
        if hasattr(self, 'vue'):
            self.vue.viewport().update()

    def positionner_detail(self):
        if not self.detail or not self.deplie_id or not hasattr(self, 'vue'):
            return
        index = self.index_id(self.deplie_id)
        if not index.isValid():
            return
        largeur = max(1, self.vue.viewport().width() - 16)
        self.detail.adapter(largeur)
        hauteur = self.detail.sizeHint().height()
        attendue = self.hauteur_ligne() + hauteur + 8
        if self.vue.rowHeight(index.row()) != attendue:
            self.vue.setRowHeight(index.row(), attendue)
        r = self.vue.visualRect(index)
        self.detail.setGeometry(8, r.top() + self.hauteur_ligne(), largeur, hauteur)
        self.detail.raise_()

    def favori(self, fid):
        gestion = self.app.identifiants
        self.app.mutation(lambda: gestion.basculer_favori(fid))

    def modifier(self, fid, dupliquer=False):
        from vaultsafe.ui.fiches import FormulaireFiche
        gestion = self.app.identifiants
        self.app.executer(lambda: gestion.afficher_identifiant(fid), lambda fiche: FormulaireFiche(self.app, fiche, dupliquer=dupliquer).ouvrir())

    def menu_fiche(self, fid, position):
        index = self.index_id(fid)
        if not index.isValid():
            return
        f = index.data(Qt.ItemDataRole.UserRole)
        menu = Menu(self)
        menu.sensible = True
        menu.addAction('Déplier / replier', lambda: self.basculer(fid))
        menu.addAction('Modifier', lambda: self.modifier(fid))
        menu.addAction('Autres données', lambda: self.app.details(fid))
        menu.addAction('Dupliquer', lambda: self.modifier(fid, True))
        menu.addSeparator()
        menu.addAction('Retirer des favoris' if f['favori'] else 'Ajouter aux favoris', lambda: self.favori(fid))
        if f['nom_utilisateur']:
            menu.addAction('Copier l’identifiant', lambda: self.app.copier_champ_fiche(fid, 'nom_utilisateur'))
        if f['secret_present']:
            menu.addAction('Copier le mot de passe', lambda: self.app.copier_champ_fiche(fid, 'mot_de_passe'))
        menu.exec(position)
        menu.deleteLater()

    def hideEvent(self, event):
        self.replier()
        super().hideEvent(event)

    def nettoyer(self):
        self.actif = False
        self.recherche_timer.stop()
        self.replier()
