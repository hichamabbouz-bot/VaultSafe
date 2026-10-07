# Composants tiers

La licence non commerciale du code VaultSafe ne modifie pas les droits sur les
bibliothèques tierces. Les licences et notices livrées avec les distributions
Python/Qt sont conservées dans `_internal` et `assets/licences`.

| Composant | Version maîtrisée | Licence / provenance |
| --- | --- | --- |
| Python | 3.13.x (construction locale 3.13.14) | PSF, https://www.python.org/psf/license/ |
| Qt / PySide6 Essentials / Shiboken6 | 6.11.2 | LGPLv3, https://doc.qt.io/qtforpython-6/licenses.html |
| cryptography | 50.0.2 | Apache-2.0 / BSD, notices incluses par la distribution |
| cffi / pycparser | 2.1.1 / 3.0 | MIT-0 / BSD-3-Clause, métadonnées et textes conservés dans `_internal` |
| zxcvbn | 4.5.0 | MIT, distribution Python utilisée |
| PyInstaller (construction) | 6.22.3 | GPL avec exception pour les applications générées |
| pytest / Ruff (développement) | 9.1.1 / 0.16.10 | MIT |
| Inno Setup (construction du setup) | 6.7.3 | Licence du compilateur, https://jrsoftware.org/isinfo.php |
| Liste des suffixes publics | copie dans assets | Mozilla Public License 2.0, https://publicsuffix.org/list/ |
| Liste de mots EFF | copie dans assets | notice `assets/EFF_dictionary_NOTICE.txt` |

Qt est livré sous forme de DLL remplaçables, sans liaison statique. Les textes
LGPLv3 et GPLv3 sont inclus. Les modifications des bibliothèques et l'ingénierie
inverse nécessaire à leur débogage restent permises, y compris lorsque le code
original de VaultSafe est sous licence non commerciale. Voir la notice Qt pour
les sources correspondant à la version livrée.

Les icônes de sites téléchargées à l'utilisation restent dans le cache local de
l'utilisateur. Elles ne font pas partie des ressources redistribuées du setup.
Les marques appartiennent à leurs propriétaires. Ne pas inclure de cache personnel
dans une livraison ou dans le futur dépôt.

Le texte de licence du runtime Python est livré dans
`_internal/licences/Python/LICENSE.txt`. Les notices des roues Python se trouvent
dans les répertoires `*.dist-info`. Inno Setup et les outils de tests ne sont pas
installés sur le poste du client.
