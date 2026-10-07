"""Rasteriser seulement un sous-ensemble SVG graphique, sans ressources externes."""
import re
from xml.etree import ElementTree
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QImage, QPainter

ELEMENTS = {'svg', 'g', 'defs', 'path', 'rect', 'circle', 'ellipse', 'line',
            'polyline', 'polygon', 'linearGradient', 'radialGradient', 'stop',
            'clipPath', 'title', 'desc'}
ATTRIBUTS = {'id', 'version', 'viewBox', 'width', 'height', 'x', 'y', 'x1', 'y1',
             'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry', 'fx', 'fy', 'd', 'points',
             'fill', 'fill-rule', 'fill-opacity', 'stroke', 'stroke-width',
             'stroke-linecap', 'stroke-linejoin', 'stroke-miterlimit', 'stroke-opacity',
             'opacity', 'transform', 'gradientTransform', 'gradientUnits',
             'offset', 'stop-color', 'stop-opacity', 'clip-path', 'clip-rule',
             'preserveAspectRatio'}
STYLES = {'fill', 'fill-rule', 'fill-opacity', 'stroke', 'stroke-width',
          'stroke-linecap', 'stroke-linejoin', 'opacity', 'stop-color', 'stop-opacity'}


def rasteriser_svg(donnees):
    if len(donnees) > 64 * 1024 or b'<!' in donnees or b'<?' in donnees.replace(b'<?xml', b''):
        raise ValueError('SVG non pris en charge.')
    try:
        racine = ElementTree.fromstring(donnees)
    except (ElementTree.ParseError, ValueError):
        raise ValueError('SVG illisible.') from None
    if racine.tag not in ('svg', '{http://www.w3.org/2000/svg}svg'):
        raise ValueError('SVG invalide.')
    noeuds = list(racine.iter())
    if len(noeuds) > 512:
        raise ValueError('SVG trop complexe.')
    pile = [(racine, 0)]
    while pile:
        element, profondeur = pile.pop()
        if profondeur > 32:
            raise ValueError('SVG trop imbriqué.')
        pile.extend((enfant, profondeur + 1) for enfant in element)
    for element in noeuds:
        nom = element.tag.split('}')[-1]
        if nom not in ELEMENTS or (element.tag.startswith('{') and not element.tag.startswith('{http://www.w3.org/2000/svg}')):
            raise ValueError('Contenu SVG actif ou externe refusé.')
        element.tag = nom
        if 'style' in element.attrib:
            style = element.attrib.pop('style')
            for declaration in style.split(';'):
                if declaration.strip():
                    cle, separateur, valeur = declaration.partition(':')
                    if not separateur or cle.strip() not in STYLES:
                        raise ValueError('Style SVG non pris en charge.')
                    element.attrib[cle.strip()] = valeur.strip()
        for cle, valeur in element.attrib.items():
            if cle not in ATTRIBUTS or len(valeur) > 16 * 1024:
                raise ValueError('Attribut SVG non pris en charge.')
            if re.search(r'url\s*\(', valeur, re.I):
                if not re.fullmatch(r'url\(#[A-Za-z_][A-Za-z0-9_.-]{0,100}\)', valeur):
                    raise ValueError('Ressource SVG externe refusée.')
            if re.search(r'(?:https?:|data:|file:|javascript:|@import|expression\s*\()', valeur, re.I):
                raise ValueError('Ressource SVG externe refusée.')
        if nom not in ('title', 'desc') and element.text and element.text.strip():
            raise ValueError('Texte SVG non pris en charge.')
    from PySide6.QtSvg import QSvgRenderer
    racine.set('xmlns', 'http://www.w3.org/2000/svg')
    rendu = QSvgRenderer(QByteArray(ElementTree.tostring(racine, encoding='utf-8')))
    taille = rendu.defaultSize()
    if not rendu.isValid() or not 1 <= taille.width() <= 1024 or not 1 <= taille.height() <= 1024:
        raise ValueError('Dimensions SVG invalides.')
    taille = taille.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio)
    image = QImage(taille, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    peintre = QPainter(image)
    try:
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        rendu.render(peintre, QRectF(0, 0, taille.width(), taille.height()))
    finally:
        peintre.end()
    return image
