"""DPAPI de l'utilisateur Windows et presse-papiers exclu de l'historique/cloud."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


class _Blob(ctypes.Structure):
    _fields_ = [('taille', wintypes.DWORD), ('donnees', ctypes.POINTER(ctypes.c_ubyte))]


def _blob(donnees):
    tampon = ctypes.create_string_buffer(donnees)
    return _Blob(len(donnees), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_ubyte))), tampon


def dpapi(donnees, dechiffrer=False, *, contexte=b'VaultSafe-liaison-locale-v1'):
    if os.name != 'nt' or not isinstance(donnees, bytes) or len(donnees) > 1024 * 1024:
        raise ValueError('La protection locale nécessite Windows.')
    if not isinstance(contexte, bytes) or not 1 <= len(contexte) <= 4096:
        raise ValueError('Contexte de protection invalide.')
    entree, tampon = _blob(donnees)
    entropy, tampon_contexte = _blob(contexte)
    sortie = _Blob()
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    operation = crypt32.CryptUnprotectData if dechiffrer else crypt32.CryptProtectData
    operation.restype = wintypes.BOOL
    operation.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.POINTER(_Blob),
                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    if not operation(ctypes.byref(entree), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(sortie)):
        ctypes.memset(tampon, 0, len(tampon))
        raise ValueError('Protection Windows indisponible.')
    try:
        return ctypes.string_at(sortie.donnees, sortie.taille)
    finally:
        ctypes.memset(sortie.donnees, 0, sortie.taille)
        kernel.LocalFree(ctypes.cast(sortie.donnees, ctypes.c_void_p))
        ctypes.memset(tampon, 0, len(tampon))
        # Maintenir les références des tampons jusqu'à la fin des appels natifs.
        del tampon, tampon_contexte


def copier_confidentiel(fenetre, texte):
    if os.name != 'nt' or not isinstance(texte, str) or '\x00' in texte:
        raise ValueError('Texte non compatible avec le presse-papiers Windows.')
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    kernel.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalLock.restype = ctypes.c_void_p
    kernel.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalFree.restype = wintypes.HGLOBAL
    paquets = []
    ouvert = False
    try:
        formats = [(user32.RegisterClipboardFormatW(nom), b'\0' * 4)
                   for nom in ('CanIncludeInClipboardHistory', 'CanUploadToCloudClipboard')]
        formats.append((13, texte.encode('utf-16-le') + b'\0\0'))
        for format_, donnees in formats:
            if not format_:
                raise ValueError('Protection du presse-papiers indisponible.')
            handle = kernel.GlobalAlloc(2, len(donnees))
            if not handle:
                raise ValueError('Mémoire du presse-papiers indisponible.')
            paquets.append([format_, handle])
            pointeur = kernel.GlobalLock(handle)
            if not pointeur:
                raise ValueError('Mémoire du presse-papiers indisponible.')
            ctypes.memmove(pointeur, donnees, len(donnees))
            kernel.GlobalUnlock(handle)
        if not user32.OpenClipboard(fenetre):
            raise ValueError('Le presse-papiers est occupé. Réessayez.')
        ouvert = True
        if not user32.EmptyClipboard():
            raise ValueError('Impossible de copier ce texte.')
        # Les deux exclusions sont présentes avant le texte, dans la même ouverture atomique.
        for paquet in paquets:
            if not user32.SetClipboardData(paquet[0], paquet[1]):
                raise ValueError('Impossible de copier ce texte avec sa protection.')
            paquet[1] = None  # Propriété transférée à Windows.
    finally:
        if ouvert:
            user32.CloseClipboard()
        for _, handle in paquets:
            if handle:
                kernel.GlobalFree(handle)
