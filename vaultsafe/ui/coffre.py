"""Construction des widgets ; orchestration conservée dans Application."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from vaultsafe.ui.composants import Symbole, bouton, defilement, etiquette


def construire_coffre(self):
    from vaultsafe.ui.liste import ListeFiches
    if not hasattr(self, 'icones_sites'):
        from vaultsafe.icones_sites import IconesSites
        self.icones_sites = IconesSites(self)
    self.poignee.show()
    contenu = QWidget()
    disposition = QHBoxLayout(contenu)
    disposition.setContentsMargins(0, 0, 0, 0)
    disposition.setSpacing(0)
    contenu_menu = QWidget()
    self.sidebar = defilement(contenu_menu)
    self.sidebar.setObjectName('sidebar')
    menu = QVBoxLayout(contenu_menu)
    menu.setContentsMargins(10, 16, 10, 14)
    menu.setSpacing(12)
    menu.addWidget(Symbole('logo', self.couleurs['accent'], 28), alignment=Qt.AlignmentFlag.AlignHCenter)
    menu.addSpacing(12)
    self.navigation = {}
    for cle, texte in (('identifiants', 'Mes identifiants'), ('securite', 'Sécurité'), ('parametres', 'Paramètres')):
        symbole = {'identifiants': 'cle', 'securite': 'bouclier', 'parametres': 'reglages'}[cle]
        b = bouton('', lambda _=False, k=cle: self.afficher_page(k), 'navigation_focus', symbole)
        b.setCheckable(True)
        b.setAccessibleName(texte)
        b.setToolTip(texte)
        menu.addWidget(b)
        self.navigation[cle] = b
    menu.addStretch()
    from vaultsafe.ui.a_propos import ouvrir
    apropos = bouton('', lambda: ouvrir(self), 'navigation_focus', 'info')
    apropos.setAccessibleName('À propos')
    apropos.setToolTip('À propos')
    menu.addWidget(apropos)
    verrou = bouton('', self.verrouiller, 'navigation_focus', 'verrou')
    verrou.setAccessibleName('Verrouiller')
    verrou.setToolTip('Verrouiller')
    menu.addWidget(verrou)
    disposition.addWidget(self.sidebar)
    principal = QWidget()
    vertical = QVBoxLayout(principal)
    vertical.setContentsMargins(0, 0, 0, 0)
    vertical.setSpacing(0)
    self.barre_fenetre = self.commandes()
    self.barre_fenetre.setObjectName('barre_focus')
    self.barre_fenetre.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    self.barre_fenetre.ligne.setContentsMargins(24, 10, 12, 4)
    self.barre_fenetre.titre.hide()
    marque = QWidget()
    marque_ligne = QHBoxLayout(marque)
    marque_ligne.setContentsMargins(0, 0, 0, 0)
    marque_ligne.setSpacing(5)
    marque_ligne.addWidget(Symbole('logo', self.couleurs['accent'], 24))
    self.marque_focus = etiquette('VaultSafe', 'marque_focus')
    self.marque_focus.setWordWrap(False)
    marque_ligne.addWidget(self.marque_focus)
    if self.developpement:
        marque_ligne.addWidget(etiquette('Développement', 'secondaire'))
    self.barre_fenetre.ligne.insertWidget(0, marque)
    vertical.addWidget(self.barre_fenetre)
    self.pages = QStackedWidget()
    self.liste = ListeFiches(self)
    self.recherches_focus = QStackedWidget()
    self.recherches_focus.addWidget(self.liste.recherche)
    self.barre_fenetre.ligne.insertStretch(1, 1)
    self.barre_fenetre.ligne.insertWidget(2, self.recherches_focus, 4)
    self.barre_fenetre.ligne.insertStretch(3, 1)
    self.pages.addWidget(self.liste)
    vertical.addWidget(self.pages, 1)
    disposition.addWidget(principal, 1)
    self.autres_pages = {}
    self.remplacer(contenu)
    self.adapter_navigation()
    self.liste.actualiser(self.vue)
    self.afficher_page('identifiants')
