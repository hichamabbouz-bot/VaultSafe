import json
from pathlib import Path

import pytest

from vaultsafe.capture_comptes import url_connexion
from vaultsafe.liaison_navigateur import sites_identiques
from vaultsafe.parametres import Parametres


def test_url_retirer_secrets_conserver_chemin():
    url, origine, domaine = url_connexion('https://app.example.test/auth/login?token=secret#fragment')
    assert (url, origine, domaine) == ('https://app.example.test/auth/login', 'https://app.example.test', 'app.example.test')


@pytest.mark.parametrize('adresse', ['https://other.example.test', 'http://app.example.test', 'https://app.example.test:444'])
def test_origines_independantes(adresse):
    assert not sites_identiques('https://app.example.test/login', adresse)


@pytest.mark.parametrize('nom,valeur', [('theme', 'invalide'), ('inactivite', '-1'), ('capture_mode', 'libre'), ('extension_ids', 'invalid')])
def test_preferences_invalides(nom, valeur):
    with pytest.raises(ValueError):
        Parametres.valider(nom, valeur)


def test_version_app_extension_et_id():
    from vaultsafe.config import APP_VERSION
    import base64
    import hashlib
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / 'extension/manifest.json').read_text(encoding='utf-8'))
    assert APP_VERSION.split('-')[0] == manifest['version']
    digest = hashlib.sha256(base64.b64decode(manifest['key'])).hexdigest()[:32]
    assert ''.join(chr(ord('a') + int(c, 16)) for c in digest) == 'egbpodcdijmeibnmfabhiignfppmclbl'
