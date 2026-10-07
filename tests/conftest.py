"""Every test uses disposable data; Qt never touches the desktop clipboard."""
import os
import tempfile

import pytest

_isolation = tempfile.TemporaryDirectory(prefix='vaultsafe-pytest-')
os.environ['VAULTSAFE_DATA_DIR'] = _isolation.name
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

MASTER = 'Reference-fictive-2026!'


def pytest_configure(config):
    # Avoid any existing pytest directory or another user's temporary profile.
    config.option.basetemp = os.path.join(_isolation.name, 'cases')


@pytest.fixture
def coffre(tmp_path):
    from vaultsafe.connexion import Connexion
    from vaultsafe.database import BaseDeDonnees
    from vaultsafe.identifiants import Identifiants
    from vaultsafe.parametres import Parametres
    base = BaseDeDonnees(tmp_path / 'fictif.db')
    connexion = Connexion(base)
    connexion.creer_mot_de_passe_maitre(MASTER)
    try:
        yield base, connexion, Identifiants(base, connexion), Parametres(base, connexion)
    finally:
        base.verrouiller()


@pytest.fixture(scope='session')
def qt():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    return app


def pytest_sessionfinish(session, exitstatus):
    _isolation.cleanup()
