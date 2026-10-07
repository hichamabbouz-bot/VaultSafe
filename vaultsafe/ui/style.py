"""Identité visuelle et composants Qt partagés."""
import sys
from pathlib import Path
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication
LIGHT = dict(background='#F5F5F7', surface='#FFFFFF', surface_alt='#F2F2F7',
             sidebar='#FBFBFD', text='#1D1D1F', muted='#6E6E73', border='#D2D2D7',
             field_border='#85858B', accent='#0071E3', accent_text='#0064CB', accent_soft='#EAF3FF',
             success='#18743D', warning='#8A5200', danger='#B42318')
DARK = dict(background='#111113', surface='#202023', surface_alt='#2B2B2F',
            sidebar='#19191C', text='#F5F5F7', muted='#A1A1A6', border='#37373C',
            field_border='#77777D', accent='#2997FF', accent_text='#2997FF', accent_soft='#25272D',
            success='#30D158', warning='#FFD60A', danger='#FF6A61')


def obtenir_couleurs(theme):
    return dict(DARK if theme == 'dark' else LIGHT)


def theme_actif():
    return 'dark' if QApplication.instance().property('vaultsafeTheme') == 'dark' else 'light'


def echelle_active():
    return (QApplication.instance().property('vaultsafeEchelle') or 100) / 100


def palette_theme(theme):
    c = obtenir_couleurs(theme)
    palette = QPalette()
    roles = {'Window': 'background', 'Base': 'surface', 'AlternateBase': 'surface_alt', 'Button': 'surface_alt',
             'Text': 'text', 'WindowText': 'text', 'ButtonText': 'text', 'PlaceholderText': 'muted',
             'ToolTipBase': 'surface', 'ToolTipText': 'text', 'Highlight': 'accent', 'HighlightedText': None}
    for groupe in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
        for nom, couleur in roles.items():
            valeur = '#FFFFFF' if couleur is None else c['muted'] if groupe == QPalette.ColorGroup.Disabled and nom in ('Text', 'ButtonText', 'WindowText') else c[couleur]
            palette.setColor(groupe, getattr(QPalette.ColorRole, nom), QColor(valeur))
    return palette


def feuille_style(theme):
    c = obtenir_couleurs(theme)
    racine = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    coche = (racine / 'assets' / 'coche.png').as_posix()
    return f'''
    QWidget {{ color: {c['text']}; font-family: "Segoe UI Variable", "Segoe UI"; font-size: 10pt; }}
    QWidget#racine {{ background: {c['background']}; border: 1px solid {c['border']}; border-radius: 22px; }}
    QWidget#sidebar {{ background: {c['sidebar']}; }}
    QFrame#carte {{ background: {c['surface']}; border-radius: 14px; }}
    QDialog {{ background: transparent; }}
    QFrame#dialogue {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 22px; }}
    QWidget#barre_titre {{ background: transparent; }}
    QWidget#barre_focus {{ background: {c['surface']}; border-top-right-radius: 22px; }}
    QLabel {{ background: transparent; }}
    QLabel[role="secondaire"] {{ color: {c['muted']}; font-size: 8.5pt; }}
    QLabel[role="titre"] {{ font-size: 15pt; font-weight: 600; }}
    QLabel[role="sous_titre"] {{ font-size: 10pt; font-weight: 600; }}
    QLabel[role="score"] {{ font-size: 25pt; font-weight: 600; }}
    QLabel[role="erreur"] {{ color: {c['danger']}; }}
    QLabel[role="marque"] {{ color: {c['accent']}; font-size: 20pt; font-weight: 600; }}
    QLabel[role="marque_connexion"] {{ color: {c['accent']}; font-size: 25pt; font-weight: 600; }}
    QLabel[role="marque_connexion_noire"] {{ color: {c['text']}; font-size: 25pt; font-weight: 600; }}
    QLabel[role="marque_focus"] {{ color: {c['accent']}; font-size: 15pt; font-weight: 600; }}
    QWidget#page_focus {{ background: {c['surface']}; }}
    QWidget#page_reglages {{ background: {c['surface']}; }}
    QFrame#ligne_preference {{ background: transparent; border: none; border-bottom: 1px solid {c['border']}; }}
    QLabel[role="section_preference"] {{ color: {c['muted']}; font-size: 8.5pt; font-weight: 600; }}
    QLabel[role="preference"] {{ font-size: 9.5pt; }}
    QFrame#onglets_reglages {{ background: transparent; border: none; border-bottom: 1px solid {c['border']}; }}
    QPushButton[role="onglet_reglages"] {{ background: transparent; border-radius: 0; border: none; border-bottom: 2px solid transparent; color: {c['muted']}; padding: 6px 10px; min-height: 20px; }}
    QPushButton[role="onglet_reglages"]:checked {{ background: transparent; border-bottom-color: {c['accent']}; color: {c['accent_text']}; }}
    QPushButton[role="onglet_reglages"]:hover {{ color: {c['text']}; }}
    QWidget#page_reglages QLineEdit, QWidget#page_reglages QComboBox {{ border-color: {c['border']}; padding: 4px 10px; min-height: 22px; }}
    QWidget#page_reglages QLineEdit:focus, QWidget#page_reglages QComboBox:focus {{ border-color: {c['accent']}; }}
    QWidget#page_reglages QFrame#nombre {{ border-color: {c['border']}; }}
    QPushButton[role="preference_action"] {{ padding: 5px 10px; min-height: 20px; font-size: 8.5pt; }}
    QFrame#bandeau_securite {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}
    QFrame#resume_securite {{ background: transparent; border: none; border-bottom: 1px solid {c['border']}; }}
    QLabel[role="score_securite"] {{ color: {c['accent_text']}; font-size: 22pt; font-weight: 600; }}
    QLabel[role="etat_fuites"] {{ background: {c['surface_alt']}; color: {c['muted']}; padding: 3px 8px; border-radius: 8px; font-size: 8.5pt; }}
    QProgressBar#score_compact {{ border: none; background: {c['surface_alt']}; border-radius: 3px; min-height: 6px; }}
    QProgressBar#score_compact::chunk {{ background: {c['accent']}; border-radius: 3px; }}
    QTableView#table_focus {{ background: {c['surface']}; border: none; outline: none; }}
    QTableView#table_focus QHeaderView::section {{ background: {c['surface']}; color: {c['muted']}; border: none; padding: 5px 10px; font-size: 9pt; }}
    QFrame#detail_focus {{ background: {c['accent_soft']}; border: none; border-radius: 10px; }}
    QFrame#detail_focus QLineEdit {{ background: {c['surface']}; border-color: {c['border']}; font-size: 9.5pt; }}
    QFrame#detail_focus QLineEdit#valeur_lecture {{ background: transparent; border: none; border-radius: 0; padding: 2px 0; min-height: 22px; }}
    QFrame#detail_focus QLineEdit#valeur_lecture:focus {{ border: none; border-bottom: 1px solid {c['accent']}; padding: 2px 0 1px; }}
    QPushButton[role="action_lecture"] {{ background: transparent; border: none; color: {c['muted']}; padding: 4px; min-height: 24px; }}
    QPushButton[role="action_lecture"]:hover, QPushButton[role="action_lecture"]:focus {{ background: {c['surface_alt']}; color: {c['accent_text']}; }}
    QPushButton[role="navigation_focus"] {{ background: transparent; padding: 0; border-radius: 9px; }}
    QPushButton[role="navigation_focus"]:hover {{ background: {c['surface_alt']}; }}
    QPushButton[role="navigation_focus"]:checked {{ background: {c['accent_soft']}; border-left: 2px solid {c['accent']}; }}
    QPushButton[role="filtre_focus"] {{ background: transparent; padding: 4px 12px; color: {c['muted']}; min-height: 20px; }}
    QPushButton[role="filtre_focus"]:checked {{ background: {c['accent_soft']}; color: {c['accent_text']}; }}
    QPushButton[role="score_focus"] {{ background: {c['surface']}; border: 1px solid {c['border']}; color: {c['muted']}; }}
    QPushButton[role="secondaire_securite"] {{ background: {c['surface']}; border: 1px solid {c['border']}; }}
    QLineEdit#recherche_focus {{ background: {c['surface_alt']}; border-color: {c['border']}; padding: 5px 10px; }}
    QLabel[role="titre_connexion"] {{ font-size: 16pt; font-weight: 600; }}
    QLabel[role="aide_connexion"] {{ color: {c['muted']}; font-size: 9.5pt; }}
    QLabel[role="libelle_connexion"] {{ font-size: 9.5pt; }}
    QWidget#connexion QLineEdit {{ background: {c['surface']}; border-color: {c['border']}; }}
    QWidget#connexion QLineEdit:focus {{ border-color: {c['accent']}; }}
    QFrame#separateur_connexion {{ background: {c['border']}; border: none; }}
    QPushButton[role="lien"] {{ color: {c['accent_text']}; background: transparent; border: none; padding: 4px 0; min-height: 18px; }}
    QPushButton[role="lien"]:hover {{ color: {c['accent']}; text-decoration: underline; }}
    QPushButton[role="options_connexion"] {{ color: {c['muted']}; background: transparent; padding: 4px 24px 4px 6px; min-height: 18px; }}
    QPushButton[role="options_connexion"]:hover, QPushButton[role="options_connexion"]:checked {{ color: {c['text']}; background: transparent; }}
    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {{
        background: {c['surface_alt']}; color: {c['text']}; selection-background-color: #0071E3;
        selection-color: white; border: 1px solid {c['field_border']}; border-radius: 10px;
        placeholder-text-color: {c['muted']}; padding: 7px 12px; min-height: 24px; font-size: 9.5pt;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 2px solid {c['accent']}; padding: 6px 11px; }}
    QLineEdit[invalid="true"] {{ border-color: {c['danger']}; }}
    QLineEdit[readOnly="true"], QPlainTextEdit[readOnly="true"] {{ background: {c['surface']}; }}
    QComboBox {{ padding-right: 30px; }}
    QComboBox:focus {{ padding-right: 29px; }}
    QComboBox QAbstractItemView {{ background: {c['surface']}; color: {c['text']}; border: none;
        selection-background-color: {c['accent_soft']}; selection-color: {c['accent_text']}; outline: none; }}
    QComboBox QAbstractItemView::item {{ padding: 0; min-height: 0; border-radius: 6px; }}
    QFrame#menu_choix {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; }}
    QFrame#segments {{ background: {c['surface_alt']}; border: none; border-radius: 10px; }}
    QFrame#themes_preference {{ background: transparent; border: none; }}
    QPushButton[role="theme_preference"] {{ background: {c['surface']}; border: 1px solid {c['border']}; padding: 5px 14px; }}
    QPushButton[role="theme_preference"]:checked {{ background: {c['accent_soft']}; border-color: {c['accent']}; color: {c['accent_text']}; }}
    QPushButton[role="segment"] {{ background: transparent; padding: 6px 12px; border: 1px solid transparent; min-height: 22px; }}
    QPushButton[role="segment"]:checked {{ background: {c['surface']}; border-color: {c['border']}; color: {c['text']}; }}
    QPushButton[role="segment"]:hover {{ background: {c['surface']}; }}
    QPushButton[role="type_fiche"] {{ text-align: left; border-color: {c['border']}; background: {c['surface']}; }}
    QPushButton[role="type_fiche"]:hover {{ background: {c['accent_soft']}; border-color: {c['accent']}; }}
    QFrame#nombre {{ background: {c['surface_alt']}; border: 1px solid {c['field_border']}; border-radius: 10px; }}
    QSpinBox#valeur_nombre {{ background: transparent; border: none; padding: 0; min-height: 24px; font-size: 9.5pt; }}
    QLabel[role="note"] {{ padding: 10px; border-radius: 10px; background: {c['surface_alt']}; font-size: 9.5pt; }}
    QListView#liste_choix {{ background: {c['surface']}; color: {c['text']}; border: none; outline: none; font-size: 9pt; }}
    QListView#liste_choix::item {{ padding: 0; min-height: 0; border: none; border-radius: 6px; }}
    QListView#liste_choix::item:selected {{ background: {c['accent_soft']}; color: {c['accent_text']}; }}
    QListView#liste_choix::item:hover {{ background: {c['surface_alt']}; }}
    QComboBox::drop-down {{ border: none; width: 26px; }}
    QComboBox::down-arrow {{ image: none; }}
    QPushButton {{ background: {c['surface_alt']}; border: 1px solid transparent;
        border-radius: 10px; padding: 8px 12px; min-height: 22px; font-size: 9pt; }}
    QPushButton:hover {{ background: {c['border']}; }}
    QPushButton:focus {{ border-color: {c['accent']}; }}
    QPushButton:checked {{ background: {c['accent_soft']}; color: {c['accent_text']}; }}
    QPushButton[role="principal"] {{ background: #0071E3; color: white; }}
    QPushButton[role="principal"]:hover {{ background: #0064CB; }}
    QPushButton[role="danger"] {{ background: #D92D20; color: white; }}
    QPushButton:disabled {{ color: {c['muted']}; background: {c['surface_alt']}; }}
    QPushButton[role="discret"], QPushButton[role="depliable"] {{ background: transparent; color: {c['muted']}; text-align: left; padding: 3px 6px; min-height: 20px; font-size: 8.5pt; }}
    QPushButton[role="discret"]:hover, QPushButton[role="depliable"]:hover {{ background: {c['surface_alt']}; color: {c['text']}; }}
    QPushButton[role="depliable"]:checked {{ background: transparent; color: {c['text']}; }}
    QPushButton[role="icone"], QPushButton[role="fenetre"], QPushButton[role="fermer"] {{
        background: transparent; padding: 0; min-height: 0; border-radius: 8px; }}
    QPushButton[role="icone"]:hover, QPushButton[role="fenetre"]:hover {{ background: {c['surface_alt']}; }}
    QPushButton[role="fermer"]:hover {{ background: {c['accent_soft']}; }}
    QPushButton[role="navigation"] {{ background: transparent; text-align: left; padding: 9px 12px; }}
    QPushButton[role="navigation"]:hover {{ background: {c['surface_alt']}; }}
    QPushButton[role="navigation"]:checked {{ background: {c['accent_soft']}; color: {c['accent_text']}; }}
    QCheckBox {{ spacing: 8px; background: transparent; min-height: 32px; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {c['field_border']}; border-radius: 5px; background: {c['surface_alt']}; }}
    QCheckBox::indicator:checked {{ background: transparent; border: none; image: url("{coche}"); }}
    QScrollArea, QListView {{ border: none; background: transparent; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 12px; margin: 3px; }}
    QScrollBar::handle:vertical {{ background: {c['field_border']}; border-radius: 3px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 3px; }}
    QScrollBar::handle:horizontal {{ background: {c['field_border']}; border-radius: 3px; min-width: 30px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
    QListWidget {{ border: none; background: transparent; outline: none; }}
    QListWidget::item {{ padding: 9px 10px; border-bottom: 1px solid {c['border']}; }}
    QListWidget::item:selected {{ background: {c['accent_soft']}; color: {c['accent_text']}; border-radius: 6px; }}
    QFrame#infobulle {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; }}
    QLabel[role="infobulle"] {{ color: {c['text']}; font-size: 8.5pt; }}
    QMenu {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 4px; }}
    QMenu::item {{ padding: 5px 12px; min-height: 20px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {c['accent_soft']}; color: {c['accent_text']}; }}
    QMenu::separator {{ height: 1px; background: {c['border']}; margin: 3px 6px; }}
    QTableView#table_import {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; outline: none; }}
    QTableView#table_import QHeaderView::section {{ background: {c['surface']}; color: {c['muted']}; font-size: 8.5pt; border: none; border-bottom: 1px solid {c['border']}; padding: 6px 10px; }}
    QProgressBar {{ border: none; background: {c['surface_alt']}; border-radius: 4px; max-height: 8px; }}
    QProgressBar::chunk {{ background: #0071E3; border-radius: 4px; }}
    '''
