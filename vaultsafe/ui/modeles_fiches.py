"""Public table model and filters; no storage reads or secret-bearing rows."""
from datetime import datetime
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from vaultsafe.modele import TYPES
from vaultsafe.ui.projections import preparer_table


class ModeleFiches(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fiches, self.lignes = [], {}
        self.app = getattr(parent, 'app', None)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.fiches)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 7

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.fiches):
            return None
        f, col = self.fiches[index.row()], index.column()
        if role == Qt.ItemDataRole.UserRole:
            return f
        valeurs = (f['_libelle'], f['dossier_nom'], date_affichee(f['date_modification']),
                   'Favori' if f['favori'] else '', 'Copier l’identifiant', 'Déplier / replier', 'Actions')
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            return valeurs[col]
        if role == Qt.ItemDataRole.ToolTipRole:
            return (' · '.join((f['titre'], TYPES[f['type']], f['_hote'])), f['dossier_nom'], f['date_modification'],
                    'Retirer des favoris' if f['favori'] else 'Ajouter aux favoris',
                    'Copier l’identifiant' if f['nom_utilisateur'] else 'Aucun identifiant à copier',
                    'Déplier / replier la fiche', 'Actions de la fiche')[col]
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ('Compte', 'Dossier', 'Modifié', '', '', '', '')[section]
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.AccessibleTextRole:
            return ('Compte', 'Dossier', 'Modifié', 'Favori', 'Copier l’identifiant', 'Déplier', 'Actions')[section]
        return None

    def remplacer(self, fiches, dossiers=(), tri='_nom', inverse=False, *, table=None):
        moteur = getattr(getattr(self.app, 'icones_sites', None), 'moteur', None)
        table = table if table is not None else preparer_table(fiches, dossiers, moteur)
        if moteur is not None:
            moteur.aliases, moteur.icones, moteur.noms_manuels = table['aliases'], table['icones'], table['noms_manuels']
            moteur.appris = True
        self.beginResetModel()
        self.fiches = list(table['fiches'])
        self.fiches.sort(key=lambda f: (f[tri], f['id']), reverse=inverse)
        self.lignes = {f['id']: i for i, f in enumerate(self.fiches)}
        self.endResetModel()

    def ordonner(self, cle, inverse=False):
        self.beginResetModel()
        self.fiches.sort(key=lambda f: (f[cle], f['id']), reverse=inverse)
        self.lignes = {f['id']: i for i, f in enumerate(self.fiches)}
        self.endResetModel()


class FiltreFiches(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.texte, self.mots, self.type_fiche, self.dossier, self.etat = '', [], '', None, ''
        self.tri = '_nom'
        self.faibles, self.reutilises, self.exposes = set(), set(), set()
        self.echeance = ''

    def filterAcceptsRow(self, ligne, parent):
        f = self.sourceModel().fiches[ligne]
        if not all(mot in f['_recherche'] for mot in self.mots):
            return False
        if self.type_fiche and f['type'] != self.type_fiche:
            return False
        if self.dossier is not None and f['dossier'] != self.dossier:
            return False
        if self.etat == 'favoris' and not f['favori']:
            return False
        if self.etat in ('faibles', 'reutilises', 'exposes') and f['id'] not in getattr(self, self.etat):
            return False
        if self.etat == 'echeances' and (not f['expiration'] or f['expiration'] > self.echeance):
            return False
        return True


def date_affichee(valeur):
    try:
        date = datetime.fromisoformat(valeur).astimezone()
        jours = (datetime.now().astimezone().date() - date.date()).days
        if jours == 0:
            return 'Aujourd’hui'
        if jours == 1:
            return 'Hier'
        return date.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return '—'

