"""Composants communs : champs, dialogues et messages centrés."""
from PySide6.QtCore import QEvent, QPoint, QRectF, QSize, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget, QFileDialog, QPlainTextEdit, QLayout, QBoxLayout, QDialogButtonBox,
    QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QGridLayout, QListView, QMenu, QSizePolicy, QSpinBox, QStyledItemDelegate,
)
from vaultsafe.ui.placement import ecran_cible, placer
from vaultsafe.ui.icones import dessiner_icone, icone
from vaultsafe.ui.style import echelle_active, obtenir_couleurs, palette_theme, theme_actif
from shiboken6 import isValid


def etiquette(texte, role='', parent=None):
    widget = QLabel(str(texte), parent)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setProperty('role', role)
    return widget


def bouton(texte, action=None, role='', symbole=''):
    widget = QPushButton(texte)
    widget.setProperty('role', role)
    widget.setMinimumHeight(28 if role == 'discret' else 40)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if symbole:
        widget.setIcon(icone(symbole, '#FFFFFF' if role in ('principal', 'danger') else None))
        widget.setIconSize(QSize(16, 16))
    if action is not None:
        widget.clicked.connect(action)
    return widget


class OptionsMenu(QStyledItemDelegate):
    """Dessine les options comme les autres contrôles, sans style Windows."""
    def sizeHint(self, option, index):
        facteur = echelle_active()
        return QSize(option.fontMetrics.horizontalAdvance(str(index.data() or '')) + round(40 * facteur), max(round(30 * facteur), option.fontMetrics.height() + round(8 * facteur)))

    def paint(self, painter, option, index):
        from PySide6.QtWidgets import QStyle
        c = obtenir_couleurs(theme_actif())
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        facteur = echelle_active()
        r = QRectF(option.rect).adjusted(2 * facteur, facteur, -2 * facteur, -facteur)
        choisi = bool(option.state & QStyle.StateFlag.State_Selected)
        survol = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(c['accent_soft'] if choisi else c['surface_alt'] if survol else c['surface']))
        painter.drawRoundedRect(r, 6 * facteur, 6 * facteur)
        painter.setFont(option.font)
        painter.setPen(QColor(c['accent_text'] if choisi else c['text']))
        texte = option.fontMetrics.elidedText(str(index.data() or ''), Qt.TextElideMode.ElideRight, max(1, int(r.width() - 40 * facteur)))
        painter.drawText(r.adjusted(10 * facteur, 0, -28 * facteur, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, texte)
        if choisi:
            dessiner_icone(painter, QRectF(r.right() - 23 * facteur, r.center().y() - 7 * facteur, 14 * facteur, 14 * facteur), 'coche', c['accent_text'])
        painter.restore()


class BoutonOptions(QPushButton):
    def __init__(self, libelle):
        super().__init__(libelle)
        self.setProperty('role', 'options_connexion')
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, evenement):
        super().paintEvent(evenement)
        painter = QPainter(self)
        dessiner_icone(painter, QRectF(self.width() - 20, (self.height() - 14) / 2, 14, 14),
                      'haut' if self.isChecked() else 'bas')
        painter.end()


class Choix(QComboBox):
    """Liste déroulante Qt, avec le même dessin dans les deux thèmes."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(40)
        self.setMaxVisibleItems(6)
        self.menu = None

    def showPopup(self):
        if not self.count():
            return
        if self.menu is None:
            self.menu = QWidget(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
            self.menu.sensible = True
            self.menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            enveloppe = QVBoxLayout(self.menu)
            enveloppe.setContentsMargins(0, 0, 0, 0)
            cadre = QFrame()
            cadre.setObjectName('menu_choix')
            enveloppe.addWidget(cadre)
            layout = QVBoxLayout(cadre)
            layout.setContentsMargins(4, 4, 4, 4)
            self.liste_choix = QListView()
            self.liste_choix.setObjectName('liste_choix')
            self.liste_choix.setAccessibleName(self.accessibleName() or 'Choisir une option')
            self.liste_choix.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.liste_choix.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            self.liste_choix.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.liste_choix.setItemDelegate(OptionsMenu(self.liste_choix))
            self.liste_choix.setSpacing(0)
            self.liste_choix.setMouseTracking(True)
            self.liste_choix.installEventFilter(self)
            self.liste_choix.clicked.connect(self.choisir)
            layout.addWidget(self.liste_choix)
        self.liste_choix.setModel(self.model())
        self.liste_choix.setModelColumn(self.modelColumn())
        self.liste_choix.setRootIndex(self.rootModelIndex())
        self.liste_choix.setCurrentIndex(self.model().index(self.currentIndex(), self.modelColumn(), self.rootModelIndex()))
        self.menu.setPalette(palette_theme(theme_actif()))
        self.liste_choix.setPalette(palette_theme(theme_actif()))
        self.menu.ensurePolished()
        facteur = echelle_active()
        hauteur_ligne = max(round(30 * facteur), self.liste_choix.sizeHintForRow(0))
        screen = ecran_cible(self.window())
        zone = screen.availableGeometry().adjusted(8, 8, -8, -8)
        largeur = min(zone.width(), round(600 * facteur), max(self.width(), self.liste_choix.sizeHintForColumn(0) + round(12 * facteur)))
        hauteur = min(zone.height(), min(self.count(), self.maxVisibleItems()) * hauteur_ligne + 10)
        origine = self.mapToGlobal(QPoint(0, self.height() + 4))
        y = origine.y() if origine.y() + hauteur <= zone.bottom() else self.mapToGlobal(QPoint(0, -hauteur - 4)).y()
        self.menu.setGeometry(max(zone.left(), min(origine.x(), zone.right() - largeur + 1)),
                              max(zone.top(), min(y, zone.bottom() - hauteur + 1)), largeur, hauteur)
        self.menu.show()
        self.liste_choix.scrollTo(self.liste_choix.currentIndex())
        self.liste_choix.setFocus()

    def hidePopup(self):
        if self.menu is not None:
            self.menu.hide()
        super().hidePopup()

    def choisir(self, index):
        if index.isValid():
            self.setCurrentIndex(index.row())
            self.activated.emit(index.row())
            self.textActivated.emit(self.currentText())
        self.hidePopup()
        self.setFocus()

    def eventFilter(self, objet, evenement):
        if evenement.type() == QEvent.Type.KeyPress:
            if evenement.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                self.choisir(self.liste_choix.currentIndex())
                if evenement.key() == Qt.Key.Key_Tab:
                    self.focusNextPrevChild(not bool(evenement.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                return True
            if evenement.key() == Qt.Key.Key_Escape:
                self.hidePopup()
                self.setFocus()
                return True
        return super().eventFilter(objet, evenement)

    def paintEvent(self, evenement):
        super().paintEvent(evenement)
        painter = QPainter(self)
        dessiner_icone(painter, QRectF(self.width() - 25, (self.height() - 14) / 2, 14, 14), 'bas')
        painter.end()


class Segments(QFrame):
    changed = Signal(str)

    def __init__(self, valeurs, selection, replier=True):
        super().__init__()
        self.replier = replier
        self.setObjectName('segments')
        self.grille = QGridLayout(self)
        self.grille.setContentsMargins(4, 4, 4, 4)
        self.grille.setSpacing(2)
        self.groupe = QButtonGroup(self)
        self.boutons = {}
        for libelle, valeur in valeurs:
            b = bouton(libelle, role='segment')
            b.setCheckable(True)
            b.setChecked(valeur == selection)
            self.groupe.addButton(b)
            self.boutons[valeur] = b
            b.clicked.connect(lambda _=False, v=valeur: self.changed.emit(v))
            self.grille.addWidget(b, 0, len(self.boutons) - 1)
        self.colonnes = len(self.boutons)

    def resizeEvent(self, evenement):
        super().resizeEvent(evenement)
        if not self.replier:
            return
        largeur = max(b.minimumSizeHint().width() for b in self.boutons.values()) + 8
        colonnes = max(1, min(len(self.boutons), (self.width() - 8) // max(1, largeur)))
        if colonnes != self.colonnes:
            for i, b in enumerate(self.boutons.values()):
                self.grille.addWidget(b, i // colonnes, i % colonnes)
            self.colonnes = colonnes


class Nombre(QFrame):
    """Saisie numérique et boutons − / + partagés dans tous les écrans."""
    valueChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('nombre')
        self.setMinimumHeight(40)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(0)
        self.entree = QSpinBox()
        self.entree.setObjectName('valeur_nombre')
        self.entree.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.entree.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.moins = bouton('', lambda: self.entree.stepDown(), 'icone', 'moins')
        self.plus = bouton('', lambda: self.entree.stepUp(), 'icone', 'plus')
        for b, libelle in ((self.moins, 'Diminuer'), (self.plus, 'Augmenter')):
            b.setFixedWidth(32)
            b.setAccessibleName(libelle)
            b.setToolTip(libelle)
            b.setAutoRepeat(True)
        layout.addWidget(self.moins)
        layout.addWidget(self.entree, 1)
        layout.addWidget(self.plus)
        self.entree.valueChanged.connect(self.actualiser)
        self.setMaximumWidth(190)
        self.actualiser(self.value())

    def actualiser(self, valeur):
        self.moins.setEnabled(valeur > self.entree.minimum())
        self.plus.setEnabled(valeur < self.entree.maximum())
        self.valueChanged.emit(valeur)

    def setRange(self, minimum, maximum):
        self.entree.setRange(minimum, maximum)
        self.actualiser(self.value())

    def setValue(self, valeur):
        self.entree.setValue(valeur)

    def value(self):
        return self.entree.value()

    def setSuffix(self, suffixe):
        self.entree.setSuffix(suffixe)

    def setSingleStep(self, valeur):
        self.entree.setSingleStep(valeur)


class Interrupteur(QCheckBox):
    """Bascule locale, avec les mêmes couleurs et une zone de clic confortable."""
    def __init__(self, libelle):
        super().__init__()
        self.setAccessibleName(libelle)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self):
        return QSize(round(48 * echelle_active()), round(36 * echelle_active()))

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        c, facteur = obtenir_couleurs(theme_actif()), echelle_active()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect().center().x() - 20 * facteur, self.rect().center().y() - 11 * facteur, 40 * facteur, 22 * facteur)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(c['accent'] if self.isChecked() and self.isEnabled() else c['border']))
        painter.drawRoundedRect(r, 11 * facteur, 11 * facteur)
        painter.setBrush(QColor('#FFFFFF'))
        x = r.right() - 19 * facteur if self.isChecked() else r.left() + 3 * facteur
        painter.drawEllipse(QRectF(x, r.top() + 3 * facteur, 16 * facteur, 16 * facteur))
        if self.hasFocus():
            painter.setPen(QColor(c['accent_text']))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(r.adjusted(-2, -2, 2, 2), 13 * facteur, 13 * facteur)
        painter.end()


class Depliable(QPushButton):
    def __init__(self, libelle):
        super().__init__(libelle)
        self.setProperty('role', 'depliable')
        self.setCheckable(True)
        self.setMinimumHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self.actualiser)
        self.actualiser(False)

    def actualiser(self, actif):
        self.setIcon(icone('bas' if actif else 'suivant'))
        self.setIconSize(QSize(14, 14))


def uniformiser_menu(menu):
    menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    menu.setPalette(palette_theme(theme_actif()))
    return menu


class Menu(QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)
        uniformiser_menu(self)
        self.aboutToShow.connect(lambda: self.setPalette(palette_theme(theme_actif())))


class Infobulles(QWidget):
    """Une seule petite infobulle thémée ; aucune fenêtre native carrée."""
    def __init__(self, qt):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.cible = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        cadre = QFrame()
        cadre.setObjectName('infobulle')
        corps = QVBoxLayout(cadre)
        corps.setContentsMargins(8, 5, 8, 5)
        self.libelle = etiquette('', 'infobulle')
        corps.addWidget(self.libelle)
        layout.addWidget(cadre)
        self.delai = QTimer(self)
        self.delai.setSingleShot(True)
        self.delai.timeout.connect(self.hide)
        qt.installEventFilter(self)
        qt.aboutToQuit.connect(self.hide)

    def eventFilter(self, objet, event):
        if event.type() == QEvent.Type.ToolTip:
            if not isinstance(objet, QWidget) or not objet.toolTip() or objet.property('role') in ('fenetre', 'fermer'):
                return True
            self.cible = objet
            facteur = echelle_active()
            self.libelle.setText(objet.toolTip()[:180])
            self.libelle.setMaximumWidth(round(240 * facteur))
            self.setPalette(palette_theme(theme_actif()))
            self.adjustSize()
            screen = ecran_cible(objet.window())
            zone = screen.availableGeometry().adjusted(8, 8, -8, -8)
            point = event.globalPos() + QPoint(10, 14)
            self.move(max(zone.left(), min(point.x(), zone.right() - self.width() + 1)), max(zone.top(), min(point.y(), zone.bottom() - self.height() + 1)))
            self.show()
            self.delai.start(4000)
            return True
        if self.isVisible() and (event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress, QEvent.Type.WindowStateChange, QEvent.Type.ApplicationDeactivate) or objet is self.cible and event.type() in (QEvent.Type.Leave, QEvent.Type.Hide, QEvent.Type.StyleChange)):
            self.hide()
        return False


class BarreTitre(QWidget):
    """Zone de déplacement et commandes à droite, commune aux fenêtres."""
    def __init__(self, fenetre, titre='', complete=False):
        super().__init__()
        self.setObjectName('barre_titre')
        self.fenetre, self.complete = fenetre, complete
        self.ligne = QHBoxLayout(self)
        self.ligne.setContentsMargins(0, 0, 0, 0)
        self.ligne.setSpacing(2)
        label = etiquette(titre, 'sous_titre' if complete else 'titre')
        self.titre = label
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.ligne.addWidget(label, 1)
        if complete:
            self.ligne.addWidget(self.commande('reduire', 'Réduire', fenetre.reduire))
            self.maximum = self.commande('agrandir', 'Agrandir / restaurer', self.agrandir)
            self.ligne.addWidget(self.maximum)
            fenetre.installEventFilter(self)
        fermer = fenetre.fermer if complete else fenetre.reject
        self.ligne.addWidget(self.commande('fermer', 'Fermer', fermer, 'fermer'))

    def commande(self, symbole, libelle, action, role='fenetre'):
        controle = bouton('', action, role, symbole)
        controle.setFixedSize(40, 36)
        controle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        controle.setAccessibleName(libelle)
        return controle

    def agrandir(self):
        if self.fenetre.isMaximized():
            self.fenetre.showNormal()
        else:
            self.fenetre.showMaximized()

    def eventFilter(self, objet, evenement):
        if evenement.type() == QEvent.Type.WindowStateChange:
            self.maximum.setIcon(icone('restaurer' if self.fenetre.isMaximized() else 'agrandir'))
        return False

    def mousePressEvent(self, evenement):
        if evenement.button() == Qt.MouseButton.LeftButton:
            handle = self.fenetre.windowHandle()
            if handle and handle.startSystemMove():
                return
            self._origine = evenement.globalPosition().toPoint() - self.fenetre.pos()

    def mouseMoveEvent(self, evenement):
        if evenement.buttons() & Qt.MouseButton.LeftButton and getattr(self, '_origine', None) is not None:
            self.fenetre.move(evenement.globalPosition().toPoint() - self._origine)

    def mouseReleaseEvent(self, evenement):
        self._origine = None

    def mouseDoubleClickEvent(self, evenement):
        if self.complete and evenement.button() == Qt.MouseButton.LeftButton:
            self.agrandir()


class Symbole(QWidget):
    """Icône vectorielle sans interaction, nette aux différents zooms."""
    def __init__(self, nom, couleur=None, taille=36):
        super().__init__()
        self.nom, self.couleur, self.taille = nom, couleur, taille
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def sizeHint(self):
        cote = round(self.taille * max(1, self.font().pointSizeF() / 10))
        return QSize(cote, cote)

    def paintEvent(self, evenement):
        painter = QPainter(self)
        dessiner_icone(painter, QRectF(self.rect()), self.nom, self.couleur)
        painter.end()


def champ(texte='', secret=False, indication='', oeil=False):
    widget = QLineEdit()
    # Qt compte en unités UTF-16 : deux unités pour certains caractères.
    widget.setMaxLength(200_000)
    widget.setText(texte)
    widget.setMinimumHeight(40)
    widget.setPlaceholderText(indication)
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    def contexte(point):
        menu = uniformiser_menu(widget.createStandardContextMenu())
        menu.exec(widget.mapToGlobal(point))
        menu.deleteLater()
    widget.customContextMenuRequested.connect(contexte)
    if secret:
        widget.setProperty('confidentiel', True)
        widget.setEchoMode(QLineEdit.EchoMode.Password)
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        if oeil:
            action = widget.addAction(icone('oeil'), QLineEdit.ActionPosition.TrailingPosition)
            action.setCheckable(True)
            minuterie = QTimer(widget)
            minuterie.setSingleShot(True)
            def basculer(visible):
                if not all(isValid(objet) for objet in (widget, action, minuterie)):
                    return
                widget.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
                action.setIcon(icone('oeil_ferme' if visible else 'oeil'))
                libelle = 'Masquer le mot de passe' if visible else 'Afficher le mot de passe'
                action.setText(libelle)
                action.setToolTip(libelle)
                if visible:
                    minuterie.start(10_000)
                else:
                    minuterie.stop()
            def masquer():
                if not isValid(action):
                    return
                action.setChecked(False)
                basculer(False)
            action.toggled.connect(basculer)
            minuterie.timeout.connect(masquer)
            widget.textChanged.connect(lambda valeur: masquer() if not valeur else None)
            basculer(False)
    return widget


def texte(valeur='', lecture_seule=False):
    widget = QPlainTextEdit(valeur)
    widget.setProperty('confidentiel', True)
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    widget.setReadOnly(lecture_seule)
    widget.setMinimumHeight(64)
    widget.setMaximumHeight(96)
    widget.setTabChangesFocus(True)
    return widget


def editer_note(parent, valeur, lecture_seule=False, appliquer=None):
    dialogue = Dialogue(parent, 'Note', (540, 440))
    dialogue.ajuster_contenu = False
    entree = texte(valeur, lecture_seule)
    entree.setMinimumHeight(0)
    entree.setMaximumHeight(16777215)
    dialogue.zone_contenu.hide()
    dialogue.disposition.insertWidget(1, entree, 1)
    dialogue.actions.addWidget(bouton('Fermer' if lecture_seule else 'Annuler', dialogue.reject))
    if not lecture_seule:
        def valider():
            if appliquer:
                appliquer(entree.toPlainText())
            dialogue.accept()
        dialogue.actions.addWidget(bouton('Appliquer', valider, 'principal'))
    dialogue.ouvrir()
    entree.setFocus()
    return dialogue


def apercu_note(parent, valeur):
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    extrait = '\n'.join(valeur.splitlines()[:3])[:160]
    label = etiquette(extrait + ('…' if extrait != valeur else ''))
    label.setProperty('role', 'note')
    label.setProperty('confidentiel', True)
    layout.addWidget(label)
    if extrait != valeur:
        ouvrir = bouton('Lire la note', lambda: editer_note(parent, valeur, True), 'discret')
        layout.addWidget(ouvrir, alignment=Qt.AlignmentFlag.AlignLeft)
    return widget


def defilement(contenu):
    zone = QScrollArea()
    zone.setWidgetResizable(True)
    zone.setFrameShape(QFrame.Shape.NoFrame)
    zone.setWidget(contenu)
    zone.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return zone


def carte():
    cadre = QFrame()
    cadre.setObjectName('carte')
    layout = QVBoxLayout(cadre)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(8)
    return cadre, layout


class LigneSouple(QWidget):
    """Les contrôles passent sous leur libellé quand la largeur manque."""
    def __init__(self, seuil=570):
        super().__init__()
        self.seuil = seuil
        self.ligne = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.ligne.setContentsMargins(0, 6, 0, 6)

    def resizeEvent(self, evenement):
        super().resizeEvent(evenement)
        # Utilise les dimensions réelles des polices, y compris le zoom choisi.
        facteur = max(1, self.font().pointSizeF() / 10)
        direction = QBoxLayout.Direction.TopToBottom if self.width() < self.seuil * facteur else QBoxLayout.Direction.LeftToRight
        if self.ligne.direction() != direction:
            self.ligne.setDirection(direction)
            self.updateGeometry()


class Dialogue(QDialog):
    def __init__(self, parent, titre, taille=(520, 480), sensible=True):
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle(titre)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setModal(True)
        self.sensible = sensible
        self.actif = True
        self.finished.connect(self._terminer)
        self.taille = taille
        self.ajuster_contenu = True
        enveloppe = QVBoxLayout(self)
        enveloppe.setContentsMargins(0, 0, 0, 0)
        enveloppe.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        cadre = QFrame()
        cadre.setObjectName('dialogue')
        enveloppe.addWidget(cadre)
        self.disposition = QVBoxLayout(cadre)
        self.disposition.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.disposition.setContentsMargins(18, 12, 18, 14)
        self.disposition.setSpacing(8)
        self.barre_titre = BarreTitre(self, titre)
        self.disposition.addWidget(self.barre_titre)
        self.contenu = QWidget()
        self.corps = QVBoxLayout(self.contenu)
        self.corps.setContentsMargins(0, 0, 0, 0)
        self.corps.setSpacing(10)
        self.zone_contenu = defilement(self.contenu)
        self.disposition.addWidget(self.zone_contenu, 1)
        self.erreur = etiquette('', 'erreur')
        self.disposition.addWidget(self.erreur)
        self.actions = QHBoxLayout()
        self.actions.addStretch()
        self.disposition.addLayout(self.actions)

    def preparer(self):
        facteur = echelle_active()
        screen = ecran_cible(self.parentWidget())
        largeur = min(round(self.taille[0] * facteur), screen.availableGeometry().width() - 32)
        hauteur = round(self.taille[1] * facteur)
        if getattr(self, 'ajuster_contenu', False):
            corps = self.corps.totalHeightForWidth(max(1, largeur - 40))
            hauteur = max(corps, self.corps.sizeHint().height() if corps < 0 else 0) + self.barre_titre.sizeHint().height() + self.actions.sizeHint().height() + self.erreur.sizeHint().height() + 70
        placer(self, (largeur, min(round(self.taille[1] * facteur), max(round(210 * facteur), hauteur))), self.parentWidget())

    def ouvrir(self):
        self.preparer()
        self.open()
        self.raise_()

    def utiliser_liste(self, liste):
        """Une seule surface défilante, avec le titre et les actions fixes."""
        self.ajuster_contenu = False
        self.zone_contenu.hide()
        self.disposition.insertWidget(1, liste, 1)

    def _terminer(self, _):
        self.actif = False
        self.nettoyer()

    def nettoyer(self):
        for entree in self.findChildren(QLineEdit):
            if entree.property('confidentiel'):
                entree.clear()
        for entree in self.findChildren(QPlainTextEdit):
            entree.clear()
        for label in self.findChildren(QLabel):
            if label.property('confidentiel'):
                label.clear()


def demander(parent, titre, texte, secret=False, valeur=''):
    dialogue = Dialogue(parent, titre, (440, 280), sensible=secret)
    dialogue.ajuster_contenu = True
    dialogue.corps.addWidget(etiquette(texte))
    entree = champ(valeur, secret)
    dialogue.corps.addWidget(entree)
    resultat = [None]
    def accepter():
        resultat[0] = entree.text()
        entree.clear()
        dialogue.accept()
    dialogue.actions.addWidget(bouton('Annuler', dialogue.reject))
    dialogue.actions.addWidget(bouton('Valider', accepter, 'principal'))
    entree.returnPressed.connect(accepter)
    dialogue.preparer()
    entree.setFocus()
    dialogue.exec()
    return resultat[0]


def message(parent, titre, texte, confirmation=False):
    dialogue = Dialogue(parent, titre, (440, 280), sensible=False)
    dialogue.ajuster_contenu = True
    dialogue.corps.addWidget(etiquette(texte))
    if confirmation:
        dialogue.actions.addWidget(bouton('Annuler', dialogue.reject))
    dialogue.actions.addWidget(bouton('Continuer' if confirmation else 'Fermer', dialogue.accept, 'principal'))
    dialogue.preparer()
    return dialogue.exec() == QDialog.DialogCode.Accepted


def fichier(parent, titre, filtre='', sauver=False, initial='', repertoire=False):
    dialogue = QFileDialog(parent, titre, initial, filtre)
    dialogue.sensible = True
    dialogue.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialogue.setWindowFlag(Qt.WindowType.FramelessWindowHint)
    dialogue.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    contenu = QWidget()
    contenu.setLayout(dialogue.layout())
    contenu.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
    enveloppe = QVBoxLayout(dialogue)
    enveloppe.setContentsMargins(0, 0, 0, 0)
    enveloppe.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
    cadre = QFrame()
    cadre.setObjectName('dialogue')
    enveloppe.addWidget(cadre)
    disposition = QVBoxLayout(cadre)
    disposition.setContentsMargins(16, 12, 16, 16)
    disposition.addWidget(BarreTitre(dialogue, titre))
    disposition.addWidget(contenu, 1)
    dialogue.setAcceptMode(QFileDialog.AcceptMode.AcceptSave if sauver else QFileDialog.AcceptMode.AcceptOpen)
    dialogue.setFileMode(QFileDialog.FileMode.Directory if repertoire else
                         QFileDialog.FileMode.AnyFile if sauver else QFileDialog.FileMode.ExistingFile)
    if repertoire:
        dialogue.setOption(QFileDialog.Option.ShowDirsOnly)
    actions = dialogue.findChild(QDialogButtonBox)
    if actions:
        for action in actions.buttons():
            if actions.buttonRole(action) == QDialogButtonBox.ButtonRole.AcceptRole:
                action.setProperty('role', 'principal')
    placer(dialogue, (700, 460), parent)
    accepte = dialogue.exec()
    resultat = dialogue.selectedFiles()[0] if accepte and isValid(dialogue) else ''
    if isValid(dialogue):
        dialogue.deleteLater()
    return resultat
