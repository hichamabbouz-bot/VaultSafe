"""Configuration générale de VaultSafe.

Ce fichier rassemble les valeurs qui peuvent être modifiées sans toucher à la
logique : nom, version, tailles, limites et emplacement de la base.
"""

# Path assemble les chemins sans se soucier des séparateurs Windows.
from pathlib import Path
# os lit les dossiers proposés par Windows dans ses variables d'environnement.
import os


# Informations affichées par la fenêtre.
APP_NAME = "VaultSafe"
APP_VERSION = "3.3.3-alpha.1"
# Une fenêtre un peu large laisse respirer la liste sans devenir compliquée.
WINDOW_SIZE = "1050x680"

# Cette police est fournie avec Windows 10/11 et reste proche du style Apple.
# Une seule constante suffit pour employer la même police dans tous les écrans.
FONT_FAMILY = "Segoe UI Variable"

# Règles choisies pour les mots de passe et le verrouillage.
MIN_MASTER_PASSWORD_LENGTH = 12
DEFAULT_PASSWORD_LENGTH = 18
DEFAULT_IDLE_MINUTES = 5

# Un export de navigateur est normalement petit. Cette limite de 20 Mo évite
# de charger par erreur un fichier gigantesque qui ralentirait l'application.
MAX_CSV_SIZE = 20 * 1024 * 1024

def obtenir_dossier_donnees() -> Path:
    """Trouve le dossier dans lequel VaultSafe doit garder ses données.

    La variable VAULTSAFE_DATA_DIR est utile pour les tests. Si elle n'existe
    pas, la fonction utilise le dossier LOCALAPPDATA de Windows.
    """
    # Cherche d'abord un chemin personnalisé dans les variables Windows.
    custom_folder = os.environ.get("VAULTSAFE_DATA_DIR")
    if custom_folder:
        # expanduser développe '~' et resolve produit un chemin absolu.
        return Path(custom_folder).expanduser().resolve()
    # Sinon, utilise le dossier local normal de l'utilisateur Windows.
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home()
    return base / APP_NAME


def obtenir_chemin_base() -> Path:
    """Ajoute le nom du fichier SQLite au dossier de données."""
    # Nouveau nom : ne jamais transformer implicitement le coffre personnel v2.
    from vaultsafe.coffres import dernier_coffre
    return dernier_coffre() or (obtenir_dossier_donnees() / "vaultsafe.db")
