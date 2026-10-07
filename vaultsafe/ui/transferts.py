"""Imports avec aperçu et exports authentifiés ; aucune copie locale cachée."""
from vaultsafe.ui.composants import Dialogue, bouton, demander, etiquette, fichier, message
from vaultsafe.ui.fiches import choix
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QStyleOptionViewItem, QStyledItemDelegate, QTableView
from vaultsafe.ui.style import echelle_active, obtenir_couleurs, theme_actif


class LigneImport(QStyledItemDelegate):
    def paint(self, painter, option, index):
        cadre = QStyleOptionViewItem(option)
        cadre.rect.adjust(round(8 * echelle_active()), 0, -round(8 * echelle_active()), 0)
        super().paint(painter, cadre, index)
        painter.save()
        painter.setPen(QColor(obtenir_couleurs(theme_actif())['border']))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.restore()


class ModeleImport(QAbstractTableModel):
    """Projection publique de toutes les lignes ; aucun secret dans la liste."""
    def __init__(self, comptes, parent):
        super().__init__(parent)
        self.lignes = [(c['titre'][:200], c.get('nom_utilisateur', '')[:200]) for c in comptes]

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.lignes)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 2

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return self.lignes[index.row()][index.column()]

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ('Titre', 'Identifiant')[section]


class ApercuImport(Dialogue):
    def __init__(self, app, apercu, ancien=False):
        super().__init__(app, 'Aperçu de l’import', (560, 480))
        self.app, self.apercu, self.ancien = app, apercu, ancien
        resume = etiquette(f"{len(apercu['comptes'])} fiches valides · {apercu['doublons']} doublons · {apercu.get('invalides', 0)} lignes invalides", 'secondaire')
        self.liste = QTableView()
        self.liste.setObjectName('table_import')
        self.liste.setAccessibleName('Fiches à importer, sans mots de passe')
        self.modele = ModeleImport(apercu['comptes'], self.liste)
        self.liste.setModel(self.modele)
        self.liste.setItemDelegate(LigneImport(self.liste))
        self.liste.setShowGrid(False)
        self.liste.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.liste.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.liste.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.liste.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.liste.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.liste.verticalHeader().hide()
        self.liste.verticalHeader().setDefaultSectionSize(round(32 * echelle_active()))
        self.liste.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.liste.horizontalHeader().setSectionsClickable(False)
        self.liste.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.utiliser_liste(self.liste)
        self.disposition.insertWidget(1, resume)
        self.politique = choix([('Ignorer les doublons', 'ignorer'), ('Conserver les deux', 'ajouter'), ('Remplacer les fiches', 'remplacer')], 'ignorer')
        self.politique.setVisible(not ancien)
        self.politique.setAccessibleName('Gestion des doublons')
        self.disposition.insertWidget(3, self.politique)
        self.valider = bouton('Importer', self.importer, 'principal', 'importer')
        self.valider.setEnabled(bool(apercu['comptes']))
        self.actions.addWidget(bouton('Annuler', self.reject))
        self.actions.addWidget(self.valider)

    def importer(self):
        politique = self.politique.currentData()
        if politique == 'remplacer' and not message(self, 'Remplacer les doublons', 'Les versions actuelles seront conservées dans l’historique. Continuer ?', True):
            return
        gestion, apercu, ancien = self.app.identifiants, self.apercu, self.ancien
        self.valider.setEnabled(False)
        def travail():
            if ancien:
                from vaultsafe.migration import appliquer_migration
                return {'ajoutes': appliquer_migration(gestion, apercu), 'remplaces': 0, 'ignores': apercu['doublons']}
            from vaultsafe.operations_fichiers import appliquer_import
            return appliquer_import(gestion, apercu, politique)
        def fini(r):
            self.accept()
            self.app.afficher_page('identifiants')
            message(self.app, 'Import terminé', f"{r['ajoutes']} ajouts · {r['remplaces']} remplacements · {r['ignores']} doublons ignorés.")
        def echec(texte):
            self.valider.setEnabled(True)
            self.erreur.setText(texte)
        self.app.mutation(travail, fini, self, erreur=echec)

    def nettoyer(self):
        self.apercu = None
        super().nettoyer()


def importer(app):
    source = fichier(app, 'Importer dans le coffre', 'CSV / JSON (*.csv *.json)')
    if source and app.ouvert:
        from vaultsafe.operations_fichiers import preparer_import
        gestion = app.identifiants
        app.executer(lambda: preparer_import(gestion, source), lambda apercu: ApercuImport(app, apercu).ouvrir())


def migration(app):
    source = fichier(app, 'Ancienne base VaultSafe', 'Coffre (*.db *.vaultsafe)')
    if not source:
        return
    mot = demander(app, 'Ancien coffre', 'Son mot de passe maître :', True)
    if mot is not None and app.ouvert:
        from vaultsafe.migration import preparer_migration
        gestion = app.identifiants
        app.executer(lambda: preparer_migration(gestion, source, mot), lambda apercu: ApercuImport(app, apercu, True).ouvrir())


def exporter(app, format_='json'):
    if not message(app, 'Exporter en clair', 'Les mots de passe seront lisibles dans le fichier. L’export ne contient ni les pièces ni l’historique. Continuer ?', True):
        return
    mot = demander(app, 'Confirmer l’export', 'Votre mot de passe maître :', True)
    if mot is None:
        return
    destination = fichier(app, 'Export en clair', format_.upper() + ' (*.' + format_ + ')', True, 'VaultSafe-export.' + format_)
    if destination and app.ouvert:
        from vaultsafe.operations_fichiers import exporter_clair
        gestion = app.identifiants
        app.executer(lambda: exporter_clair(gestion, destination, mot, format_),
            lambda _: message(app, 'Export terminé', 'Le fichier est en clair. Utilisez une sauvegarde .vaultsafe pour conserver le chiffrement.'))
