"""Un seul rendu de logo pour fiches, groupes et page Sécurité."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from vaultsafe.ui.icones import dessiner_icone


def dessiner_service(peintre, rectangle, fiche, app):
    peintre.save()
    try:
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        peintre.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        image = app.icones_sites.obtenir(fiche, app.preferences.get('icones_reseau', 'non') == 'oui')
        rayon = rectangle.width() * 6 / 26
        contour = QPainterPath()
        contour.addRoundedRect(rectangle, rayon, rayon)
        peintre.setClipPath(contour, Qt.ClipOperation.IntersectClip)
        if image is not None:
            # Aucune teinte bleue ajoutée au groupe ou à la sélection.
            peintre.fillPath(contour, QColor(app.couleurs['surface']))
            marge = rectangle.width() * 2 / 26
            contenu = rectangle.adjusted(marge, marge, -marge, -marge)
            taille = image.size().scaled(contenu.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
            cible = QRectF(0, 0, taille.width(), taille.height())
            cible.moveCenter(rectangle.center())
            peintre.drawImage(cible, image)
        else:
            peintre.fillPath(contour, QColor(app.couleurs['surface_alt']))
            marge = rectangle.width() * 5 / 26
            symbole = fiche.get('_icone_symbole') or ('serveur' if fiche.get('_reseau') else 'globe')
            dessiner_icone(peintre, rectangle.adjusted(marge, marge, -marge, -marge), symbole, app.couleurs['muted'])
    finally:
        peintre.restore()
