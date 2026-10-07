# Recette navigateur réelle

Windows, Edge, Node.js et application compilée nécessaires. `npm install` puis
`npm test` dans ce dossier. Playwright est fixé à 1.62.1.
Variables facultatives : `VAULTSAFE_TEST_EXE`, `VAULTSAFE_TEST_PYTHON`,
`VAULTSAFE_TEST_BROWSER`, `PLAYWRIGHT_MODULE` (module existant).

Profil jetable, site `recette.example` intercepté localement, données fictives.
La recette crée puis retire seulement HKCU `org.vaultsafe.recette` et refuse de
remplacer une clé existante. Le presse-papiers est remplacé en mémoire.
La confirmation de remplissage est acceptée dans le fixture fictif uniquement ;
elle reste requise dans le produit livré. Les enregistrements ne la requièrent pas.
