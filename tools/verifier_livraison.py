"""Bounded build checks: source versions, required assets, extension and hashes."""
import argparse
import ast
import hashlib
import json
from pathlib import Path


def version(root):
    module = ast.parse((root / 'vaultsafe/config.py').read_text(encoding='utf-8-sig'))
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(n, ast.Name) and n.id == 'APP_VERSION' for n in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('Version application absente.')


def ressource_windows(root, destination):
    v = version(root)
    chiffres = tuple(int(n) for n in v.split('-')[0].split('.')) + (0,)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # PyInstaller lit cette syntaxe de ressource, sans importer le code applicatif.
    prerelease = 0x2 if '-' in v else 0
    destination.write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={chiffres!r}, prodvers={chiffres!r},
    mask=0x3f, flags={prerelease}, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040c04b0', [
    StringStruct('CompanyName', 'VaultSafe'),
    StringStruct('FileDescription', 'VaultSafe — gestionnaire local'),
    StringStruct('FileVersion', {v!r}),
    StringStruct('InternalName', 'VaultSafe'),
    StringStruct('OriginalFilename', 'VaultSafe.exe'),
    StringStruct('ProductName', 'VaultSafe'),
    StringStruct('ProductVersion', {v!r})])]),
    VarFileInfo([VarStruct('Translation', [1036, 1200])])])
''', encoding='utf-8')


def verifier(root, livraison=None):
    v = version(root)
    manifeste = json.loads((root / 'extension/manifest.json').read_text(encoding='utf-8'))
    assert v.split('-')[0] == manifeste['version'], 'Versions application/extension divergentes.'
    for nom in ('assets/vaultsafe.ico', 'assets/licences/Qt-LGPL-3.0.txt', 'assets/licences/GNU-GPL-3.0.txt',
                'assets/EFF_dictionary_NOTICE.txt', 'assets/public_suffix_list.dat', 'LICENSE', 'THIRD_PARTY_NOTICES.md'):
        assert (root / nom).is_file(), 'Ressource ou licence absente : ' + nom
    if livraison:
        assert (livraison / 'VaultSafe.exe').is_file()
        for nom in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'GUIDE_EXTENSION.txt', '_internal/licences/Python/LICENSE.txt'):
            assert (livraison / nom).is_file(), 'Notice livrée absente : ' + nom
        for distribution in ('cffi', 'pycparser', 'cryptography', 'zxcvbn', 'pyside6_essentials', 'shiboken6'):
            assert list((livraison / '_internal').glob(distribution + '-*.dist-info')), 'Métadonnées absentes : ' + distribution
        sources = {p.relative_to(root / 'extension').as_posix(): p for p in (root / 'extension').rglob('*') if p.is_file()}
        livrees = {p.relative_to(livraison / 'extension').as_posix(): p for p in (livraison / 'extension').rglob('*') if p.is_file()}
        assert sources.keys() == livrees.keys(), 'Fichiers extension divergents.'
        for nom, source in sources.items():
            assert source.read_bytes() == livrees[nom].read_bytes(), 'Extension divergente : ' + nom
        assert (root / 'assets/vaultsafe.ico').read_bytes() == (livraison / '_internal/assets/vaultsafe.ico').read_bytes()
        interdits = {'.db', '.sqlite', '.sqlite3', '.csv', '.vaultsafe', '.pfx', '.key'}
        assert not any(p.suffix.lower() in interdits for p in livraison.rglob('*') if p.is_file())
        assert len(list(livraison.rglob('*.exe'))) == 1, 'Un seul exécutable application attendu.'
        empreintes = {p.relative_to(livraison).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in livraison.rglob('*') if p.is_file() and p.name != 'BUILDINFO.json'}
        (livraison / 'BUILDINFO.json').write_text(json.dumps({'application': v, 'extension': manifeste['version'],
            'signature': 'non signee', 'sha256': empreintes}, indent=2), encoding='utf-8')
    return v


def main():
    parseur = argparse.ArgumentParser()
    parseur.add_argument('--source', type=Path, required=True)
    parseur.add_argument('--livraison', type=Path)
    parseur.add_argument('--version', action='store_true')
    parseur.add_argument('--version-windows', type=Path)
    args = parseur.parse_args()
    if args.version_windows:
        ressource_windows(args.source, args.version_windows)
        return
    print(version(args.source) if args.version else verifier(args.source, args.livraison))


if __name__ == '__main__':
    main()
