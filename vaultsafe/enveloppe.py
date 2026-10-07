"""Enveloppes AES-GCM de la clé de données ; lecture du format historique v1."""
from __future__ import annotations

import base64
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from vaultsafe.securite_coffre import (
    ErreurCoffre, deriver_cle, effacer_cle, encoder_json, nouvel_entete, verifier_entete,
)


def _aad(entete, role):
    base = {k: v for k, v in entete.items() if k not in ('master_wrap', 'recovery_wrap')}
    if role == 'recuperation':
        base = {'format': 'VaultSafe', 'version': 2, 'coffre_id': entete['coffre_id']}
    base['role'] = role
    return encoder_json(base)


def _emballer(cle, protection, aad):
    nonce = secrets.token_bytes(12)
    return {'nonce': nonce.hex(), 'contenu': AESGCM(protection).encrypt(nonce, bytes(cle), aad).hex()}


def _deballe(paquet, protection, aad):
    try:
        return bytearray(AESGCM(protection).decrypt(bytes.fromhex(paquet['nonce']),
                                                   bytes.fromhex(paquet['contenu']), aad))
    except InvalidTag as erreur:
        raise ErreurCoffre('Secret incorrect ou coffre altéré.') from erreur


def nouvelle_enveloppe(mot_de_passe, coffre_id=None, cle=None, recuperation=None):
    entete = verifier_entete(nouvel_entete(coffre_id))
    entete.update(version=2, master_wrap={'nonce': '00' * 12, 'contenu': '00' * 48},
                  recovery_wrap=recuperation)
    cle = bytearray(secrets.token_bytes(32)) if cle is None else bytearray(cle)
    protection = deriver_cle(mot_de_passe, encoder_json(entete))
    try:
        entete['master_wrap'] = _emballer(cle, protection, _aad(entete, 'maitre'))
        return encoder_json(entete), cle
    finally:
        effacer_cle(protection)


def ouvrir_cle(mot_de_passe, entete_octets):
    entete = verifier_entete(entete_octets)
    protection = deriver_cle(mot_de_passe, entete_octets)
    if entete['version'] == 1:
        return protection
    try:
        return _deballe(entete['master_wrap'], protection, _aad(entete, 'maitre'))
    finally:
        effacer_cle(protection)


def ajouter_recuperation(entete_octets, cle):
    entete = verifier_entete(entete_octets)
    if entete['version'] != 2:
        raise ErreurCoffre('Ouvrez le coffre avec son mot de passe avant de créer une clé de secours.')
    protection = bytearray(secrets.token_bytes(32))
    try:
        secret = base64.b32encode(protection).decode('ascii').rstrip('=')
        entete['recovery_wrap'] = _emballer(cle, protection, _aad(entete, 'recuperation'))
        groupes = '-'.join(secret[i:i + 4] for i in range(0, len(secret), 4))
        return encoder_json(entete), 'VS2-' + groupes
    finally:
        effacer_cle(protection)


def ouvrir_recuperation(secret, entete_octets):
    entete = verifier_entete(entete_octets)
    if entete['version'] != 2 or entete['recovery_wrap'] is None:
        raise ErreurCoffre('Aucune clé de secours n’a été créée pour ce coffre.')
    if not isinstance(secret, str) or not secret.upper().startswith('VS2-') or len(secret) > 100:
        raise ErreurCoffre('Clé de secours invalide.')
    try:
        texte = secret.upper()[4:].replace('-', '').replace(' ', '')
        if len(texte) != 52:
            raise ValueError
        protection = bytearray(base64.b32decode(texte + '=' * (-len(texte) % 8)))
    except ValueError as erreur:
        raise ErreurCoffre('Clé de secours invalide.') from erreur
    try:
        if base64.b32encode(protection).decode('ascii').rstrip('=') != texte:
            raise ErreurCoffre('Clé de secours invalide.')
        return _deballe(entete['recovery_wrap'], protection, _aad(entete, 'recuperation'))
    finally:
        effacer_cle(protection)
