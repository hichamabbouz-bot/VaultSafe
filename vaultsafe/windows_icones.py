"""Actualiser les seules icônes livrées, sans vider le cache Windows.

Le constructeur démarre ce helper avant le remplacement et écrit ACTUALISER
après. La même session COM conserve les clés et indices de l'ancienne image.
"""

import ctypes
import json
import os
import sys
import uuid
from ctypes import wintypes
from pathlib import Path


class Guid(ctypes.Structure):
    _fields_ = [("octets", ctypes.c_ubyte * 16)]

    @classmethod
    def creer(cls, valeur):
        return cls.from_buffer_copy(uuid.UUID(valeur).bytes_le)


class InfoFichier(ctypes.Structure):
    _fields_ = [
        ("icone", wintypes.HANDLE),
        ("index", ctypes.c_int),
        ("attributs", wintypes.DWORD),
        ("nom", wintypes.WCHAR * 260),
        ("type", wintypes.WCHAR * 80),
    ]


def _verifier(resultat, operation):
    if resultat < 0:
        raise OSError(f"{operation}: HRESULT 0x{resultat & 0xFFFFFFFF:08X}")


def _methode(interface, position, retour, *arguments):
    table = ctypes.cast(
        interface, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
    ).contents
    return ctypes.WINFUNCTYPE(retour, ctypes.c_void_p, *arguments)(table[position])


def _liberer(interface):
    if interface:
        _methode(interface, 2, wintypes.ULONG)(interface)


class SessionIcones:
    def __init__(self, chemins):
        self.chemins = list(dict.fromkeys(str(Path(p).resolve()) for p in chemins))
        self.references = []
        self.erreurs = []
        self.initialisee = False
        self.ole = ctypes.WinDLL("ole32")
        self.shell = ctypes.WinDLL("shell32")
        self.ole.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        self.ole.CoInitializeEx.restype = ctypes.c_long
        self.ole.CoUninitialize.argtypes = []
        self.ole.CoUninitialize.restype = None
        self.ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        self.ole.CoTaskMemFree.restype = None
        self.shell.SHParseDisplayName.argtypes = [
            wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        ]
        self.shell.SHParseDisplayName.restype = ctypes.c_long
        self.shell.SHBindToParent.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(Guid),
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ]
        self.shell.SHBindToParent.restype = ctypes.c_long
        self.shell.SHGetFileInfoW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(InfoFichier),
            wintypes.UINT, wintypes.UINT,
        ]
        self.shell.SHGetFileInfoW.restype = ctypes.c_size_t
        self.shell.SHUpdateImageW.argtypes = [
            wintypes.LPCWSTR, ctypes.c_int, wintypes.UINT, ctypes.c_int,
        ]
        self.shell.SHUpdateImageW.restype = None
        self.shell.SHChangeNotify.argtypes = [
            ctypes.c_long, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p,
        ]
        self.shell.SHChangeNotify.restype = None

    def __enter__(self):
        _verifier(self.ole.CoInitializeEx(None, 2), "CoInitializeEx")
        self.initialisee = True
        for chemin in self.chemins:
            if not Path(chemin).exists():
                continue
            try:
                self.references.extend(self._capturer(chemin))
            except OSError as erreur:
                self.erreurs.append(str(erreur))
        return self

    def __exit__(self, *_):
        if self.initialisee:
            self.ole.CoUninitialize()
            self.initialisee = False

    def _localisation(self, chemin):
        pidl = ctypes.c_void_p()
        parent = ctypes.c_void_p()
        enfant = ctypes.c_void_p()
        extracteur = ctypes.c_void_p()
        try:
            _verifier(self.shell.SHParseDisplayName(
                chemin, None, ctypes.byref(pidl), 0, None,
            ), "SHParseDisplayName")
            iid_parent = Guid.creer("000214e6-0000-0000-c000-000000000046")
            _verifier(self.shell.SHBindToParent(
                pidl, ctypes.byref(iid_parent), ctypes.byref(parent),
                ctypes.byref(enfant),
            ), "SHBindToParent")
            iid_extracteur = Guid.creer("000214fa-0000-0000-c000-000000000046")
            enfants = (ctypes.c_void_p * 1)(enfant.value)
            obtenir = _methode(
                parent, 10, ctypes.c_long, wintypes.HWND, wintypes.UINT,
                ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(Guid),
                ctypes.POINTER(wintypes.UINT), ctypes.POINTER(ctypes.c_void_p),
            )
            _verifier(obtenir(
                parent, None, 1, enfants, ctypes.byref(iid_extracteur), None,
                ctypes.byref(extracteur),
            ), "IShellFolder::GetUIObjectOf")
            texte = ctypes.create_unicode_buffer(32768)
            index = ctypes.c_int()
            drapeaux = wintypes.UINT()
            obtenir_localisation = _methode(
                extracteur, 3, ctypes.c_long, wintypes.UINT, wintypes.LPWSTR,
                wintypes.UINT, ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(wintypes.UINT),
            )
            resultat = obtenir_localisation(
                extracteur, 2, texte, len(texte), ctypes.byref(index),
                ctypes.byref(drapeaux),
            )
            _verifier(resultat, "IExtractIconW::GetIconLocation")
            if resultat != 0 or not texte.value:
                raise OSError("Le gestionnaire Windows utilise une icône de repli.")
            return texte.value, index.value, drapeaux.value
        finally:
            _liberer(extracteur)
            _liberer(parent)
            if pidl:
                self.ole.CoTaskMemFree(pidl)

    def _capturer(self, chemin):
        source, index, drapeaux = self._localisation(chemin)
        references = []
        # Les listes petite/grande peuvent partager le même indice : dédupliquer.
        indices = set()
        for taille in (1, 0):
            info = InfoFichier()
            if not self.shell.SHGetFileInfoW(
                chemin, 0, ctypes.byref(info), ctypes.sizeof(info), 0x4000 | taille,
            ):
                raise OSError("SHGetFileInfoW n'a pas fourni l'indice de l'icône.")
            if info.index not in indices:
                indices.add(info.index)
                references.append({
                    "item": chemin, "source": source, "index_source": index,
                    "drapeaux": drapeaux, "index_systeme": info.index,
                })
        return references

    def actualiser(self):
        if not self.initialisee:
            raise RuntimeError("La session COM des icônes est fermée.")
        images = set()
        for reference in self.references:
            cle = (reference["source"], reference["index_source"],
                   reference["drapeaux"], reference["index_systeme"])
            if cle not in images:
                images.add(cle)
                # GIL_NOTFILENAME peut rendre l'index source opaque : ne pas le remplacer par 0.
                self.shell.SHUpdateImageW(*cle)
        for chemin in self.chemins:
            self._notifier(0x2000, chemin)
        for parent in dict.fromkeys(str(Path(p).parent) for p in self.chemins):
            self._notifier(0x1000, parent)
        return {"etat": "ACTUALISE", "images": len(images), "erreurs": self.erreurs}

    def _notifier(self, evenement, chemin):
        texte = ctypes.c_wchar_p(chemin)
        self.shell.SHChangeNotify(
            evenement, 0x1005, ctypes.cast(texte, ctypes.c_void_p), None,
        )


def main():
    if os.name != "nt" or not sys.argv[1:]:
        return 1
    with SessionIcones(sys.argv[1:]) as session:
        print(json.dumps({"etat": "PRET", "references": session.references,
                          "erreurs": session.erreurs}), flush=True)
        if sys.stdin.readline(64).strip() != "ACTUALISER":
            return 0
        print(json.dumps(session.actualiser()), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
