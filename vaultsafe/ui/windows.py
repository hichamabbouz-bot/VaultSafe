"""Événements Windows et icône Qt, sans pompe périodique."""
import ctypes
import sys
from ctypes import wintypes
from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal, Qt
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from vaultsafe.ui.composants import Menu


class IntegrationWindows(QObject, QAbstractNativeEventFilter):
    verrouillage = Signal()
    changement_theme = Signal()
    def __init__(self, app, actif=True):
        QObject.__init__(self, app)
        QAbstractNativeEventFilter.__init__(self)
        self.app = app
        self.actif = actif and sys.platform == 'win32'
        self.hwnd = None
        self.erreur = ''
        self.icone = None
        self.verrouillage.connect(app.verrouiller, Qt.ConnectionType.QueuedConnection)
        self.changement_theme.connect(self.actualiser_icone, Qt.ConnectionType.QueuedConnection)
        from vaultsafe.ui.icones import icone_application
        app.setWindowIcon(icone_application())
        if not self.actif:
            return
        QApplication.instance().installNativeEventFilter(self)
        self.wts = ctypes.WinDLL('wtsapi32', use_last_error=True)
        self.wts.WTSRegisterSessionNotification.argtypes = [wintypes.HWND, wintypes.DWORD]
        self.wts.WTSRegisterSessionNotification.restype = wintypes.BOOL
        self.wts.WTSUnRegisterSessionNotification.argtypes = [wintypes.HWND]
        self.actualiser()
        self.icone = QSystemTrayIcon(self)
        self.actualiser_icone()
        self.actualiser()
        self.menu = Menu()
        self.menu.addAction('Afficher', app.reafficher)
        self.action_verrou = self.menu.addAction('Verrouiller', app.verrouiller)
        self.menu.addSeparator()
        self.menu.addAction('Quitter', app.fermer)
        self.icone.setContextMenu(self.menu)
        self.icone.activated.connect(lambda raison: app.reafficher() if raison in
            (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        self.icone.setToolTip('VaultSafe · coffre verrouillé')
        self.icone.show()

    @staticmethod
    def barre_sombre():
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as cle:
                return winreg.QueryValueEx(cle, 'SystemUsesLightTheme')[0] == 0
        except OSError:
            return False

    def actualiser_icone(self):
        if self.icone:
            from vaultsafe.ui.icones import icone_notification
            self.icone.setIcon(icone_notification(self.barre_sombre()))

    def actualiser(self):
        if not self.actif:
            return
        hwnd = int(self.app.winId())
        if hwnd == self.hwnd:
            return
        if self.hwnd is not None:
            self.wts.WTSUnRegisterSessionNotification(self.hwnd)
        self.hwnd = hwnd
        if not self.wts.WTSRegisterSessionNotification(hwnd, 0):
            self.erreur = 'Surveillance de session Windows indisponible.'

    def nativeEventFilter(self, type_evenement, message):
        if self.actif:
            msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if msg.hWnd == self.hwnd and ((msg.message == 0x2B1 and msg.wParam in (3, 4, 6, 7))
                                        or (msg.message == 0x218 and msg.wParam == 4)):
                self.verrouillage.emit()
            if msg.hWnd == self.hwnd and msg.message in (0x1A, 0x31A):
                self.changement_theme.emit()
        return False, 0

    def etat(self, ouvert):
        if self.icone:
            self.action_verrou.setEnabled(ouvert)
            self.icone.setToolTip('VaultSafe · coffre ' + ('ouvert' if ouvert else 'verrouillé'))

    def notifier(self, texte):
        if self.icone and self.app.preferences.get('notifications', 'oui') == 'oui':
            self.icone.showMessage('VaultSafe', texte)

    def arreter(self):
        if self.actif:
            QApplication.instance().removeNativeEventFilter(self)
            if self.hwnd:
                self.wts.WTSUnRegisterSessionNotification(self.hwnd)
            self.hwnd = None
            self.actif = False
        if self.icone:
            self.icone.hide()
