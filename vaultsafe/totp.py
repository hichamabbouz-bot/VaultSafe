"""TOTP RFC 6238, import otpauth et paramètres strictement validés."""
from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import time
from urllib.parse import parse_qs, unquote, urlparse


def secret_octets(secret):
    if not isinstance(secret, str) or not 16 <= len(secret) <= 256:
        raise ValueError('Secret TOTP invalide.')
    nettoye = secret.replace(' ', '').upper().rstrip('=')
    try:
        resultat = base64.b32decode(nettoye + '=' * (-len(nettoye) % 8))
    except (ValueError, TypeError) as erreur:
        raise ValueError('Le secret TOTP doit être en Base32.') from erreur
    if not 10 <= len(resultat) <= 128:
        raise ValueError('Longueur de secret TOTP invalide.')
    return resultat


def verifier_configuration(config):
    if not isinstance(config, dict) or set(config) != {'secret', 'algorithm', 'digits', 'period', 'label'}:
        raise ValueError('Configuration TOTP invalide.')
    secret_octets(config['secret'])
    if (config['algorithm'] not in ('SHA1', 'SHA256', 'SHA512')
            or type(config['digits']) is not int or config['digits'] not in (6, 8)
            or type(config['period']) is not int or not 15 <= config['period'] <= 120
            or not isinstance(config['label'], str) or len(config['label']) > 200):
        raise ValueError('Paramètres TOTP non pris en charge.')


def importer_totp(valeur):
    valeur = valeur.strip()
    if not valeur:
        return {}
    config = {'secret': valeur.replace(' ', '').upper(), 'algorithm': 'SHA1',
              'digits': 6, 'period': 30, 'label': ''}
    if valeur.startswith('otpauth:'):
        url = urlparse(valeur)
        if url.scheme != 'otpauth' or url.netloc != 'totp' or url.fragment:
            raise ValueError('Seules les adresses otpauth://totp sont prises en charge.')
        params = parse_qs(url.query, keep_blank_values=True)
        if any(len(v) != 1 for v in params.values()) or 'secret' not in params:
            raise ValueError('Adresse TOTP invalide.')
        try:
            config = {'secret': params['secret'][0].replace(' ', '').upper(),
                      'algorithm': params.get('algorithm', ['SHA1'])[0].upper(),
                      'digits': int(params.get('digits', ['6'])[0]),
                      'period': int(params.get('period', ['30'])[0]),
                      'label': unquote(url.path.lstrip('/'))}
        except (ValueError, TypeError) as erreur:
            raise ValueError('Adresse TOTP invalide.') from erreur
    verifier_configuration(config)
    return config


def code_totp(config, instant=None):
    verifier_configuration(config)
    instant = time.time() if instant is None else instant
    if not isinstance(instant, (int, float)) or instant < 0:
        raise ValueError('Horloge TOTP invalide.')
    compteur = int(instant // config['period'])
    digest = hmac.new(secret_octets(config['secret']), struct.pack('>Q', compteur),
                      getattr(hashlib, config['algorithm'].lower())).digest()
    offset = digest[-1] & 15
    valeur = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff
    return str(valeur % (10 ** config['digits'])).zfill(config['digits'])


def secondes_restantes(config, instant=None):
    verifier_configuration(config)
    instant = time.time() if instant is None else instant
    return config['period'] - int(instant) % config['period']
