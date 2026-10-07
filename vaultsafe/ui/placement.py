"""Placement en coordonnées logiques, indépendant de l'origine des écrans."""
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QCursor, QGuiApplication, QRegion


def ecran_cible(parent=None):
    if parent is not None and parent.windowHandle() is not None:
        screen = parent.windowHandle().screen()
        if screen in QGuiApplication.screens():
            return screen
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()


def rectangle_centre(zone, taille, centre=None):
    """Fonction pure : garde les coordonnées négatives et une marge de 16."""
    disponible = zone.adjusted(16, 16, -16, -16)
    if disponible.width() < 64 or disponible.height() < 64:
        disponible = QRect(zone)
    largeur = min(taille.width(), disponible.width())
    hauteur = min(taille.height(), disponible.height())
    centre = disponible.center() if centre is None else centre
    x = max(disponible.left(), min(centre.x() - largeur // 2, disponible.right() - largeur + 1))
    y = max(disponible.top(), min(centre.y() - hauteur // 2, disponible.bottom() - hauteur + 1))
    return QRect(x, y, largeur, hauteur)


def placer(fenetre, taille=(1050, 680), parent=None, screen=None):
    screen = screen if screen in QGuiApplication.screens() else ecran_cible(parent)
    if screen is None:
        return
    fenetre.winId()
    fenetre.windowHandle().setScreen(screen)
    marges = fenetre.windowHandle().frameMargins()
    centre = parent.frameGeometry().center() if parent is not None else None
    largeur = marges.left() + marges.right()
    hauteur = marges.top() + marges.bottom()
    rectangle = rectangle_centre(screen.availableGeometry(), QSize(taille[0] + largeur, taille[1] + hauteur), centre)
    # Le cadre reste réductible ; les zones défilantes gèrent le contenu long.
    fenetre.setMinimumSize(1, 1)
    fenetre.setGeometry(rectangle.adjusted(marges.left(), marges.top(), -marges.right(), -marges.bottom()))


def rendre_visible(fenetre):
    cadre = fenetre.frameGeometry()
    if fenetre.isMinimized() and fenetre.normalGeometry().isValid():
        marges = fenetre.windowHandle().frameMargins()
        cadre = fenetre.normalGeometry().adjusted(-marges.left(), -marges.top(), marges.right(), marges.bottom())
    ensemble = QRegion()
    for screen in QGuiApplication.screens():
        ensemble = ensemble.united(QRegion(screen.availableGeometry()))
    if ensemble.contains(cadre):
        return
    screen = QGuiApplication.screenAt(cadre.center())
    if screen is None:
        placer(fenetre, (fenetre.width(), fenetre.height()))
        return
    marges = fenetre.windowHandle().frameMargins()
    rectangle = rectangle_centre(screen.availableGeometry(), cadre.size(), cadre.center())
    fenetre.setGeometry(rectangle.adjusted(marges.left(), marges.top(), -marges.right(), -marges.bottom()))
