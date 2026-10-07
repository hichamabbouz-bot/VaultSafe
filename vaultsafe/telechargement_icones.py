"""Téléchargement d'icônes autorisé : origine seule, HTTPS public, DNS épinglé."""
import http.client
import ipaddress
import json
import time
import socket
import ssl
import threading
from queue import Queue, Empty
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from vaultsafe.icones_sites import MAX_IMAGE, MIN_ICONE, image_validee
from vaultsafe.services import normaliser

RESOLUTIONS = threading.BoundedSemaphore(2)


def origine_icone(site):
    service = normaliser(site)
    return service.origines[0] if service.origines else ''


def adresse_publique(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443) or any(ord(c) <= 32 or c == '\\' for c in url):
        raise ValueError('Source d’icône non autorisée.')
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        if '.' not in parsed.hostname or parsed.hostname.endswith(('.local', '.lan', '.internal', '.home', '.localhost', '.test', '.invalid', '.example')):
            raise ValueError('Source locale refusée.')
    resultat = Queue(maxsize=1)
    if not RESOLUTIONS.acquire(timeout=2):
        raise ValueError('Résolution indisponible.')
    def resoudre():
        try:
            resultat.put(socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM))
        except OSError as erreur:
            resultat.put(erreur)
        finally:
            RESOLUTIONS.release()
    threading.Thread(target=resoudre, daemon=True, name='VaultSafeDNS').start()
    try:
        adresses = resultat.get(timeout=2)
    except Empty:
        raise ValueError('Résolution trop lente.') from None
    if isinstance(adresses, OSError):
        raise adresses
    if not adresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in adresses):
        raise ValueError('Adresse non publique.')
    return parsed, adresses[0][4][0]


def telecharger(url, actif=lambda: True):
    for _ in range(4):
        if not actif():
            raise ValueError('Téléchargement annulé.')
        parsed, adresse = adresse_publique(url)
        if not actif():
            raise ValueError('Téléchargement annulé.')
        connexion = http.client.HTTPSConnection(parsed.hostname, timeout=2)
        limite = None
        try:
            transport = socket.create_connection((adresse, 443), timeout=2)
            try:
                connexion.sock = ssl.create_default_context().wrap_socket(transport, server_hostname=parsed.hostname)
            except BaseException:
                transport.close()
                raise
            transport_tls = connexion.sock
            def interrompre():
                try:
                    transport_tls.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            limite = threading.Timer(3, interrompre)
            limite.daemon = True
            limite.start()
            connexion.request('GET', parsed.path or '/', headers={'User-Agent': 'VaultSafe/3.2', 'Accept': 'image/*,text/html;q=0.5', 'Connection': 'close'})
            reponse = connexion.getresponse()
            if reponse.status in (301, 302, 303, 307, 308):
                cible = reponse.getheader('Location')
                if not cible:
                    raise ValueError('Redirection invalide.')
                p = urlsplit(urljoin(url, cible))
                url = urlunsplit((p.scheme, p.netloc, p.path, '', ''))
                continue
            if reponse.status != 200 or reponse.getheader('Content-Encoding', 'identity') not in ('identity', ''):
                raise ValueError('Icône indisponible.')
            longueur = reponse.getheader('Content-Length')
            typ = reponse.getheader('Content-Type', '').split(';')[0].lower()
            html = typ == 'text/html'
            if longueur and (not longueur.isdecimal() or (not html and int(longueur) > MAX_IMAGE)):
                raise ValueError('Icône trop volumineuse.')
            # Le début d'une grande page suffit pour son head ; les images restent strictement bornées.
            limite_lecture = 128 * 1024 if html else MAX_IMAGE
            donnees = reponse.read(limite_lecture + 1)
            if not html and len(donnees) > MAX_IMAGE:
                raise ValueError('Icône trop volumineuse.')
            return donnees[:limite_lecture], typ, url
        finally:
            if limite:
                limite.cancel()
            connexion.close()
    raise ValueError('Trop de redirections.')


class LiensIcones(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.liens, self.manifeste, self.nom = [], '', ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        rel = (attrs.get('rel') or '').lower().split()
        href = attrs.get('href', '')
        if tag == 'meta' and (attrs.get('property') or attrs.get('name') or '').lower() in ('og:site_name', 'application-name'):
            nom = (attrs.get('content') or '').strip()
            if 1 <= len(nom) <= 80 and not any(ord(c) < 32 or c in '<>@/\\\\' for c in nom):
                self.nom = self.nom or nom
        if tag != 'link' or not isinstance(href, str) or not 0 < len(href) <= 2048:
            return
        if 'manifest' in rel:
            self.manifeste = self.manifeste or href
        if ('icon' in rel or 'apple-touch-icon' in rel) and len(self.liens) < 32:
            tailles = []
            for valeur in (attrs.get('sizes') or '').lower().split():
                parties = valeur.split('x')
                if len(parties) == 2 and all(p.isdecimal() and len(p) <= 4 for p in parties):
                    w, h = map(int, parties)
                    if 1 <= w <= 1024 and 1 <= h <= 1024:
                        tailles.append(min(w, h))
            vectoriel = attrs.get('type', '').lower() == 'image/svg+xml' or urlsplit(href).path.lower().endswith('.svg')
            taille = 256 if vectoriel else max(tailles, default=180 if 'apple-touch-icon' in rel else 0)
            self.liens.append((taille, href))


def trouver_identite(origines, actif=lambda: True):
    """Pipeline borné : domaine principal, icônes déclarées, manifeste, www."""
    meilleur, qualite, nom = None, 0, ''
    visites, requetes = set(), 0
    debut = time.monotonic()
    def valide():
        return actif() and time.monotonic() - debut < 20
    def lire(url):
        nonlocal requetes
        p = urlsplit(url)
        cible = urlunsplit((p.scheme, p.netloc, p.path, '', ''))
        if cible in visites or requetes >= 8 or not valide():
            raise ValueError('Source déjà vérifiée ou budget terminé.')
        visites.add(cible)
        requetes += 1
        return telecharger(cible, valide)
    racines = list(dict.fromkeys(origines))
    if racines:
        hote = urlsplit(racines[0]).hostname or ''
        if hote and not hote.startswith('www.'):
            racines.insert(1, 'https://www.' + hote)
    for origine in racines[:3]:
        if not valide() or requetes >= 8:
            break
        liens, final = LiensIcones(), origine + '/'
        try:
            html, typ, final = lire(final)
            if typ == 'text/html':
                liens.feed(html.decode('utf-8', errors='replace'))
                if normaliser(final).cle == normaliser(origine).cle:
                    nom = nom or liens.nom
        except (OSError, ValueError, http.client.HTTPException):
            pass
        candidats = [urljoin(final, href) for _, href in sorted(liens.liens, key=lambda x: x[0], reverse=True)[:3]]
        # Une racine qui refuse le HTML peut tout de même servir son favicon.
        candidats.append(origine + '/favicon.ico')
        for cible in candidats:
            try:
                donnees, typ, _ = lire(cible)
                if typ not in ('image/png', 'image/jpeg', 'image/x-icon', 'image/vnd.microsoft.icon',
                               'image/webp', 'image/svg+xml', 'application/octet-stream'):
                    continue
                image, png = image_validee(donnees)
                resolution = min(image.width(), image.height())
                if resolution >= MIN_ICONE and resolution > qualite:
                    meilleur, qualite = png, resolution
                if qualite >= 128:
                    return (meilleur, nom) if valide() else (None, '')
            except (OSError, ValueError, http.client.HTTPException):
                continue
        if liens.manifeste and requetes < 7:
            try:
                donnees, typ, _ = lire(urljoin(final, liens.manifeste))
                if len(donnees) > 128 * 1024 or typ not in ('application/manifest+json', 'application/json', 'text/plain'):
                    continue
                data = json.loads(donnees)
                icones = data.get('icons', []) if isinstance(data, dict) else []
                choix = []
                for entree in icones[:32] if isinstance(icones, list) else []:
                    if isinstance(entree, dict) and isinstance(entree.get('src'), str) and 1 <= len(entree['src']) <= 2048:
                        taille = max((int(t.split('x')[0]) for t in str(entree.get('sizes', '')).lower().split()
                                      if re_taille(t)), default=0)
                        choix.append((taille, entree['src']))
                for _, src in sorted(choix, key=lambda x: x[0], reverse=True)[:2]:
                    donnees, typ, _ = lire(urljoin(final, src))
                    if typ not in ('image/png', 'image/jpeg', 'image/webp', 'image/svg+xml', 'application/octet-stream'):
                        continue
                    image, png = image_validee(donnees)
                    resolution = min(image.width(), image.height())
                    if resolution >= MIN_ICONE and resolution > qualite:
                        meilleur, qualite = png, resolution
                    if qualite >= 128:
                        return (meilleur, nom) if valide() else (None, '')
            except (OSError, ValueError, RecursionError, http.client.HTTPException):
                pass
    return (meilleur, nom) if actif() else (None, '')


def re_taille(texte):
    parties = texte.split('x')
    return len(parties) == 2 and all(p.isdecimal() and len(p) <= 4 and 1 <= int(p) <= 1024 for p in parties)


def trouver_icone(origine, actif=lambda: True):
    return trouver_identite((origine,), actif)[0]
