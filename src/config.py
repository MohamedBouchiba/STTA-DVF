"""Configuration centrale chargee depuis .env."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Racine du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Base de donnees (Supabase)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/postgres")

# Chemins
LANDING_DIR = PROJECT_ROOT / os.getenv("LANDING_DIR", "data/landing")
SQL_DIR = PROJECT_ROOT / "sql"

# Source DVF Etalab
ETALAB_BASE_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv"
DVF_YEARS = [2019, 2020, 2021, 2022, 2023, 2024]
DVF_DEPARTEMENTS = ["13", "75", "77", "78", "91", "92", "93", "94", "95"]

# Geocodage
GEOCODING_API_URL = os.getenv("GEOCODING_API_URL", "https://data.geopf.fr/geocodage/search")
GEOCODING_RATE_LIMIT = int(os.getenv("GEOCODING_RATE_LIMIT", "40"))

# Estimation
MIN_COMPARABLES = int(os.getenv("MIN_COMPARABLES", "5"))
OUTLIER_IQR_FACTOR = float(os.getenv("OUTLIER_IQR_FACTOR", "1.5"))
FALLBACK_RADIUS_KM = [1, 2, 5, 10]
