"""Projection Qt publique : groupes repliables, sans widgets par fiche."""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class GroupesSites(QAbstractTableModel):
    def __init__(self, source, parent=None):
        super().__init__(parent)
        self.source = source
        self.lignes, self.positions, self.groupes = [], {}, {}
        self.fermes, self.fermes_recherche = set(), set()
        self.texte = ''
        self.nombre_fiches, self.nombre_sites = 0, 0

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.lignes)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.source.columnCount()

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        return self.source.headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.lignes):
            return None
        f = self.lignes[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return f
        if f.get('_groupe'):
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole, Qt.ItemDataRole.ToolTipRole):
                return f"{f['_site_nom']} · {f['_compteur']} compte(s) · " + ('Replier' if f['_ouvert'] else 'Déplier') if index.column() == 0 else ''
            return None
        source = self.source.sourceModel()
        ligne = source.lignes.get(f['id'])
        return source.data(source.index(ligne, index.column()), role) if ligne is not None else None

    def reconstruire(self, texte=None):
        if texte is not None and texte != self.texte:
            self.fermes_recherche.clear()
            self.texte = texte
        tous, identites = {}, {}
        for f in self.source.sourceModel().fiches:
            cle = f['_site_cle']
            tous[cle] = tous.get(cle, 0) + 1
            identites.setdefault(cle, {})[f.get('_icone_cle', '')] = f
        groupes = {}
        for ligne in range(self.source.rowCount()):
            f = self.source.index(ligne, 0).data(Qt.ItemDataRole.UserRole)
            groupes.setdefault(f['_site_cle'], []).append(f)
        lignes = []
        fermes = self.fermes_recherche if self.texte else self.fermes
        for cle, fiches in sorted(groupes.items(), key=lambda item: (not bool(item[0]), item[1][0]['_site_nom'].casefold(), item[0])):
            total, nombre = tous[cle], len(fiches)
            if total > 1:
                images = identites[cle]
                icone_source = next(iter(images.values())) if len(images) == 1 else {
                    '_icone_cle': cle, '_icone_origines': (), '_icone_symbole': 'dossier', '_icone_manuelle': ''}
                lignes.append({'_groupe': True, 'id': 'groupe:' + cle, '_site_cle': cle,
                    '_site_nom': fiches[0]['_site_nom'], '_ouvert': cle not in fermes,
                    '_compteur': str(nombre) if nombre == total else f'{nombre} / {total}', '_nombre': nombre,
                    '_unite': 'compte' if cle else 'fiche', '_icone_source': icone_source})
                if cle in fermes:
                    continue
            lignes.extend({**f, '_en_groupe': total > 1} for f in fiches)
        self.beginResetModel()
        self.lignes, self.groupes = lignes, groupes
        self.positions = {f['id']: i for i, f in enumerate(lignes)}
        self.nombre_fiches = self.source.rowCount()
        self.nombre_sites = sum(bool(cle) for cle in groupes)
        self.endResetModel()

    def index_id(self, fid):
        ligne = self.positions.get(fid)
        return self.index(ligne, 0) if ligne is not None else QModelIndex()

    def basculer(self, cle):
        fermes = self.fermes_recherche if self.texte else self.fermes
        fermes.remove(cle) if cle in fermes else fermes.add(cle)

    def rendre_visible(self, fid):
        for cle, fiches in self.groupes.items():
            if any(f['id'] == fid for f in fiches):
                fermes = self.fermes_recherche if self.texte else self.fermes
                if cle in fermes:
                    fermes.remove(cle)
                return
