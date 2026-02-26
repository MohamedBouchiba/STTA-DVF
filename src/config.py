"""Configuration centrale chargee depuis .env."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Racine du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Base de donnees
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dvf_user:dvf_secret@localhost:5433/dvf")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "dvf")
POSTGRES_USER = os.getenv("POSTGRES_USER", "dvf_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dvf_secret")

# Chemins
LANDING_DIR = PROJECT_ROOT / os.getenv("LANDING_DIR", "data/landing")
SQL_DIR = PROJECT_ROOT / "sql"

# Geocodage
GEOCODING_API_URL = os.getenv("GEOCODING_API_URL", "https://data.geopf.fr/geocodage/search")
GEOCODING_RATE_LIMIT = int(os.getenv("GEOCODING_RATE_LIMIT", "40"))

# Estimation
MIN_COMPARABLES = int(os.getenv("MIN_COMPARABLES", "5"))
OUTLIER_IQR_FACTOR = float(os.getenv("OUTLIER_IQR_FACTOR", "1.5"))
FALLBACK_RADIUS_KM = [1, 2, 5, 10]
