"""Opérations transactionnelles des fiches, dossiers, révisions et pièces jointes."""
from __future__ import annotations

import copy
import hashlib
import hmac
import os
from pathlib import Path
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from vaultsafe.modele import MAX_PIECE, TAILLE_BLOC, maintenant, normaliser_fiche
from vaultsafe.securite_coffre import encoder_json, verifier_entete


def _chercher(document, identifiant):
    return next((f for f in document['identifiants'] if f['id'] == identifiant), None)


def _revision(document, fiche):
    document['historique'].append({'fiche': copy.deepcopy(fiche), 'date': maintenant()})
    revisions = [i for i, h in enumerate(document['historique']) if h['fiche']['id'] == fiche['id']]
    for indice in reversed(revisions[:-20]):
        del document['historique'][indice]


def _aad_piece(coffre_id, piece_id, numero):
    return encoder_json({'format': 'VaultSafe-piece-1', 'coffre_id': coffre_id,
                         'piece_id': piece_id, 'bloc': numero})


def _nettoyer_pieces(document, sql):
    fiches = (document['identifiants'] + [h['fiche'] for h in document['historique']]
              + [h['fiche'] for h in document['corbeille']])
    references = {p['id'] for f in fiches for p in f['pieces_jointes']}
    for (identifiant,) in sql.execute('SELECT DISTINCT id FROM pieces').fetchall():
        if identifiant not in references:
            sql.execute('DELETE FROM pieces WHERE id=?', (identifiant,))


class FonctionsCoffre:
    def authentifier_action(self, mot_de_passe):
        from vaultsafe.enveloppe import ouvrir_cle
        from vaultsafe.securite_coffre import effacer_cle
        with self._mutex, self._sql() as sql:
            ligne, _ = self._contenu(sql)
            cle = ouvrir_cle(mot_de_passe, ligne['entete'])
            try:
                if not hmac.compare_digest(cle, self._cle):
                    raise ValueError('Mot de passe incorrect.')
            finally:
                effacer_cle(cle)

    def verifier_integrite(self):
        with self._mutex, self._sql() as sql:
            ligne, document = self._contenu(sql)
            coffre_id = verifier_entete(ligne['entete'])['coffre_id']
            fiches = (document['identifiants'] + [h['fiche'] for h in document['historique']]
                      + [h['fiche'] for h in document['corbeille']])
            pieces = {}
            for fiche in fiches:
                for piece in fiche['pieces_jointes']:
                    if piece['id'] in pieces and pieces[piece['id']] != piece:
                        raise ValueError('Manifest de pièce jointe incohérent.')
                    pieces[piece['id']] = piece
            presents = {r[0] for r in sql.execute('SELECT DISTINCT id FROM pieces')}
            if presents != set(pieces):
                raise ValueError('Pièce jointe absente ou orpheline.')
            for piece in pieces.values():
                blocs = sql.execute('SELECT numero,nonce,contenu FROM pieces WHERE id=? ORDER BY numero',
                                    (piece['id'],)).fetchall()
                if len(blocs) != piece['blocs']:
                    raise ValueError('Pièce jointe incomplète.')
                digest, taille = hashlib.sha256(), 0
                try:
                    for numero, bloc in enumerate(blocs):
                        if (bloc['numero'] != numero or not isinstance(bloc['nonce'], bytes)
                                or len(bloc['nonce']) != 12 or not isinstance(bloc['contenu'], bytes)
                                or not 16 <= len(bloc['contenu']) <= TAILLE_BLOC + 16):
                            raise ValueError('Bloc de pièce jointe invalide.')
                        clair = AESGCM(self._cle).decrypt(bloc['nonce'], bloc['contenu'],
                                                         _aad_piece(coffre_id, piece['id'], numero))
                        digest.update(clair)
                        taille += len(clair)
                except InvalidTag as erreur:
                    raise ValueError('Pièce jointe altérée.') from erreur
                if taille != piece['taille'] or not hmac.compare_digest(digest.hexdigest(), piece['sha256']):
                    raise ValueError('Pièce jointe altérée.')
            return {'fiches': len(document['identifiants']), 'pieces': len(pieces),
                    'corbeille': len(document['corbeille']), 'revisions': len(document['historique'])}

    def ajouter_identifiant(self, valeurs):
        self.ajouter_lot([valeurs])

    def ajouter_lot(self, fiches):
        fiches = [normaliser_fiche(f) for f in fiches]

        def ajouter(document):
            ids = {f['id'] for f in document['identifiants']}
            ids.update(h['fiche']['id'] for h in document['corbeille'])
            for fiche in fiches:
                if fiche['id'] in ids:
                    raise ValueError('Identifiant dupliqué.')
                ids.add(fiche['id'])
            document['identifiants'].extend(copy.deepcopy(fiches))
            return len(fiches)
        return self._modifier(ajouter)

    def modifier_identifiant(self, valeurs):
        valeurs = normaliser_fiche(valeurs)

        def modifier(document, sql):
            ancienne = _chercher(document, valeurs['id'])
            if ancienne is None:
                raise ValueError('Fiche introuvable.')
            # Les pièces sont gérées uniquement par les opérations dédiées.
            if valeurs['pieces_jointes'] != ancienne['pieces_jointes']:
                raise ValueError('Utilisez les actions de pièces jointes pour les modifier.')
            _revision(document, ancienne)
            document['identifiants'][document['identifiants'].index(ancienne)] = copy.deepcopy(valeurs)
            _nettoyer_pieces(document, sql)
        self._modifier(modifier, avec_sql=True)

    def supprimer_identifiant(self, identifiant):
        def supprimer(document):
            fiche = _chercher(document, identifiant)
            if fiche is None:
                raise ValueError('Fiche introuvable.')
            document['identifiants'].remove(fiche)
            document['corbeille'].append({'fiche': fiche, 'date_suppression': maintenant()})
        self._modifier(supprimer)

    def lire_corbeille(self):
        return list(reversed(self._lire()['corbeille']))

    def restaurer_fiche(self, identifiant):
        def restaurer(document):
            item = next((h for h in document['corbeille'] if h['fiche']['id'] == identifiant), None)
            if item is None:
                raise ValueError('Fiche introuvable dans la corbeille.')
            fiche = item['fiche']
            if fiche['dossier'] not in {d['id'] for d in document['dossiers']}:
                fiche['dossier'] = ''
            fiche['date_modification'] = maintenant()
            document['identifiants'].append(fiche)
            document['corbeille'].remove(item)
        self._modifier(restaurer)

    def purger_corbeille(self, identifiant=None, confirmation=''):
        if confirmation != 'SUPPRIMER':
            raise ValueError('La suppression définitive exige une confirmation explicite.')

        def purger(document, sql):
            ids = {h['fiche']['id'] for h in document['corbeille']
                   if identifiant is None or h['fiche']['id'] == identifiant}
            document['corbeille'] = [h for h in document['corbeille'] if h['fiche']['id'] not in ids]
            document['historique'] = [h for h in document['historique'] if h['fiche']['id'] not in ids]
            _nettoyer_pieces(document, sql)
        self._modifier(purger, avec_sql=True)

    def lire_historique(self, identifiant):
        return list(reversed([h for h in self._lire()['historique'] if h['fiche']['id'] == identifiant]))

    def restaurer_revision(self, identifiant, indice):
        if type(indice) is not int or indice < 0:
            raise ValueError('Révision invalide.')

        def restaurer(document, sql):
            fiche = _chercher(document, identifiant)
            revisions = list(reversed([h for h in document['historique'] if h['fiche']['id'] == identifiant]))
            if fiche is None or indice >= len(revisions):
                raise ValueError('Révision introuvable.')
            copie = copy.deepcopy(revisions[indice]['fiche'])
            _revision(document, fiche)
            if copie['dossier'] not in {d['id'] for d in document['dossiers']}:
                copie['dossier'] = ''
            copie['date_modification'] = maintenant()
            document['identifiants'][document['identifiants'].index(fiche)] = copie
            _nettoyer_pieces(document, sql)
        self._modifier(restaurer, avec_sql=True)

    def vider_historique(self, identifiant, confirmation=''):
        if confirmation != 'SUPPRIMER':
            raise ValueError('Confirmez la suppression de l’historique.')

        def purger(document, sql):
            document['historique'] = [h for h in document['historique'] if h['fiche']['id'] != identifiant]
            _nettoyer_pieces(document, sql)
        self._modifier(purger, avec_sql=True)

    def lire_dossiers(self):
        return sorted(self._lire()['dossiers'], key=lambda d: d['nom'].casefold())

    def creer_dossier(self, nom, parent=''):
        dossier = {'id': str(uuid4()), 'nom': nom.strip(), 'parent': parent}
        self._modifier(lambda d: d['dossiers'].append(dossier))
        return dossier['id']

    def modifier_dossier(self, identifiant, nom, parent=''):
        def modifier(document):
            dossier = next((d for d in document['dossiers'] if d['id'] == identifiant), None)
            if dossier is None:
                raise ValueError('Dossier introuvable.')
            dossier.update(nom=nom.strip(), parent=parent)
        self._modifier(modifier)

    def supprimer_dossier(self, identifiant):
        def supprimer(document):
            if any(d['parent'] == identifiant for d in document['dossiers']):
                raise ValueError('Déplacez ou supprimez les sous-dossiers avant de supprimer ce dossier.')
            document['dossiers'] = [d for d in document['dossiers'] if d['id'] != identifiant]
            fiches = (document['identifiants'] + [h['fiche'] for h in document['historique']]
                      + [h['fiche'] for h in document['corbeille']])
            for fiche in fiches:
                if fiche['dossier'] == identifiant:
                    fiche['dossier'] = ''
        self._modifier(supprimer)

    def ajouter_piece(self, identifiant, source):
        self.exiger_ouverture()
        source = Path(source)
        if not source.is_file() or source.stat().st_size > MAX_PIECE:
            raise ValueError('Pièce jointe introuvable ou trop volumineuse (maximum 16 Mo).')
        with source.open('rb') as fichier:
            donnees = fichier.read(MAX_PIECE + 1)
        if len(donnees) > MAX_PIECE:
            raise ValueError('Pièce jointe trop volumineuse.')
        piece = {'id': str(uuid4()), 'nom': source.name, 'taille': len(donnees),
                 'sha256': hashlib.sha256(donnees).hexdigest(),
                 'blocs': max(1, (len(donnees) + TAILLE_BLOC - 1) // TAILLE_BLOC)}

        def ajouter(document, sql):
            fiche = _chercher(document, identifiant)
            if fiche is None:
                raise ValueError('Fiche introuvable.')
            stocke = sql.execute('SELECT coalesce(sum(length(contenu)),0) FROM pieces').fetchone()[0]
            if stocke + len(donnees) > 96 * 1024 * 1024:
                raise ValueError('Limite des pièces jointes du coffre atteinte (96 Mo).')
            coffre_id = verifier_entete(self._lire_ligne(sql)['entete'])['coffre_id']
            _revision(document, fiche)
            for numero in range(piece['blocs']):
                nonce = os.urandom(12)
                bloc = donnees[numero * TAILLE_BLOC:(numero + 1) * TAILLE_BLOC]
                chiffre = AESGCM(self._cle).encrypt(nonce, bloc, _aad_piece(coffre_id, piece['id'], numero))
                sql.execute('INSERT INTO pieces VALUES(?,?,?,?)', (piece['id'], numero, nonce, chiffre))
            fiche['pieces_jointes'].append(piece)
            fiche['date_modification'] = maintenant()
            _nettoyer_pieces(document, sql)
        self._modifier(ajouter, avec_sql=True)
        return piece['id']

    def lire_piece(self, identifiant, piece_id):
        with self._mutex:
            self.exiger_ouverture()
            with self._sql() as sql:
                ligne, document = self._contenu(sql)
                fiche = _chercher(document, identifiant)
                piece = next((p for p in fiche['pieces_jointes'] if p['id'] == piece_id), None) if fiche else None
                if piece is None:
                    raise ValueError('Pièce jointe introuvable.')
                blocs = sql.execute('SELECT numero,nonce,contenu FROM pieces WHERE id=? ORDER BY numero',
                                    (piece_id,)).fetchall()
                if len(blocs) != piece['blocs']:
                    raise ValueError('Pièce jointe incomplète.')
                coffre_id = verifier_entete(ligne['entete'])['coffre_id']
                donnees = bytearray()
                try:
                    for numero, bloc in enumerate(blocs):
                        if bloc['numero'] != numero or len(bloc['contenu']) > TAILLE_BLOC + 16:
                            raise ValueError('Bloc de pièce jointe invalide.')
                        donnees.extend(AESGCM(self._cle).decrypt(
                            bloc['nonce'], bloc['contenu'], _aad_piece(coffre_id, piece_id, numero)))
                except (InvalidTag, TypeError) as erreur:
                    raise ValueError('Pièce jointe altérée.') from erreur
                if len(donnees) != piece['taille'] or not hmac.compare_digest(
                        hashlib.sha256(donnees).hexdigest(), piece['sha256']):
                    raise ValueError('Pièce jointe altérée.')
                return bytes(donnees)

    def retirer_piece(self, identifiant, piece_id):
        def retirer(document, sql):
            fiche = _chercher(document, identifiant)
            if fiche is None or not any(p['id'] == piece_id for p in fiche['pieces_jointes']):
                raise ValueError('Pièce jointe introuvable.')
            _revision(document, fiche)
            fiche['pieces_jointes'] = [p for p in fiche['pieces_jointes'] if p['id'] != piece_id]
            fiche['date_modification'] = maintenant()
            _nettoyer_pieces(document, sql)
        self._modifier(retirer, avec_sql=True)
