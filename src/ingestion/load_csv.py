"""Chargement des CSV DVF Etalab dans staging.dvf via Supabase."""

import csv
import gzip
import io
from pathlib import Path

from sqlalchemy import text

from src.config import LANDING_DIR, DVF_YEARS, DVF_DEPARTEMENTS, SQL_DIR
from src.db import get_engine, get_raw_connection

# Colonnes du CSV Etalab a charger dans staging.dvf
# On ne prend que les colonnes utiles (le CSV en a ~40+)
ETALAB_COLUMNS_MAP = {
    "id_mutation": "id_mutation",
    "date_mutation": "date_mutation",
    "numero_disposition": "numero_disposition",
    "nature_mutation": "nature_mutation",
    "valeur_fonciere": "valeur_fonciere",
    "adresse_numero": "adresse_numero",
    "adresse_nom_voie": "adresse_nom_voie",
    "code_postal": "code_postal",
    "code_commune": "code_commune",
    "nom_commune": "nom_commune",
    "code_departement": "code_departement",
    "id_parcelle": "id_parcelle",
    "type_local": "type_local",
    "code_type_local": "code_type_local",
    "surface_reelle_bati": "surface_reelle_bati",
    "nombre_pieces_principales": "nombre_pieces_principales",
    "surface_terrain": "surface_terrain",
    "longitude": "longitude",
    "latitude": "latitude",
    "lot1_surface_carrez": "lot1_surface_carrez",
    "lot2_surface_carrez": "lot2_surface_carrez",
}

STAGING_COLUMNS = list(ETALAB_COLUMNS_MAP.values()) + ["annee_fichier"]


def create_staging_table():
    """Cree la table staging.dvf si elle n'existe pas."""
    engine = get_engine()
    sql_path = SQL_DIR / "staging" / "create_staging_dvf.sql"
    sql = sql_path.read_text(encoding="utf-8")
    with engine.begin() as conn:
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    print("[DDL] staging.dvf cree")


def truncate_staging():
    """Vide la table staging.dvf."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE staging.dvf"))
    print("[TRUNCATE] staging.dvf vide")


def _clean_value(val: str) -> str | None:
    """Nettoie une valeur CSV (vide -> None)."""
    if val == "" or val is None:
        return None
    return val


def load_single_csv(csv_path: Path, year: int) -> int:
    """
    Charge un fichier CSV (possiblement .gz) dans staging.dvf.

    Utilise un INSERT par batch pour compatibilite Supabase
    (COPY n'est pas toujours disponible via connexion poolee).

    Args:
        csv_path: Chemin vers le fichier .csv ou .csv.gz.
        year: Annee du fichier (pour la colonne annee_fichier).

    Returns:
        Nombre de lignes chargees.
    """
    # Ouvrir le fichier (gzip ou plain)
    if csv_path.suffix == ".gz":
        f = gzip.open(csv_path, "rt", encoding="utf-8")
    else:
        f = open(csv_path, "r", encoding="utf-8")

    try:
        reader = csv.DictReader(f)

        # Verifier que les colonnes attendues existent
        csv_columns = set(reader.fieldnames or [])
        missing = set(ETALAB_COLUMNS_MAP.keys()) - csv_columns
        if missing:
            print(f"  [WARN] Colonnes manquantes dans {csv_path.name}: {missing}")

        # Construire les INSERT par batch
        engine = get_engine()
        cols_sql = ", ".join(STAGING_COLUMNS)
        placeholders = ", ".join(f":{c}" for c in STAGING_COLUMNS)
        insert_sql = text(
            f"INSERT INTO staging.dvf ({cols_sql}) VALUES ({placeholders})"
        )

        batch = []
        batch_size = 5000
        total_rows = 0

        for row in reader:
            record = {}
            for csv_col, db_col in ETALAB_COLUMNS_MAP.items():
                record[db_col] = _clean_value(row.get(csv_col, ""))
            record["annee_fichier"] = year

            batch.append(record)

            if len(batch) >= batch_size:
                with engine.begin() as conn:
                    conn.execute(insert_sql, batch)
                total_rows += len(batch)
                batch = []

        # Dernier batch
        if batch:
            with engine.begin() as conn:
                conn.execute(insert_sql, batch)
            total_rows += len(batch)

        return total_rows

    finally:
        f.close()


def load_and_transform(
    years: list[int] | None = None,
    departements: list[str] | None = None,
):
    """
    Charge les CSV dans staging puis transforme vers core, un fichier a la fois.

    Strategie pour respecter la limite 500 MB de Supabase :
    1. TRUNCATE staging
    2. COPY un CSV dans staging
    3. INSERT INTO core.transactions (depuis staging)
    4. TRUNCATE staging
    5. Repeter pour chaque fichier

    Args:
        years: Annees a charger (defaut: DVF_YEARS).
        departements: Departements a charger (defaut: DVF_DEPARTEMENTS).
    """
    if years is None:
        years = DVF_YEARS
    if departements is None:
        departements = DVF_DEPARTEMENTS

    # S'assurer que staging existe
    create_staging_table()

    # Lire le SQL de transformation
    transform_sql_path = SQL_DIR / "core" / "transform_staging_to_core.sql"
    transform_sql = transform_sql_path.read_text(encoding="utf-8")

    engine = get_engine()
    total_loaded = 0
    total_transformed = 0

    for year in years:
        for dep in departements:
            csv_path = LANDING_DIR / str(year) / f"{dep}.csv.gz"

            if not csv_path.exists():
                print(f"[SKIP] {csv_path} non trouve")
                continue

            # Verifier si deja charge dans core
            with engine.connect() as conn:
                already = conn.execute(
                    text("SELECT COUNT(*) FROM core.transactions WHERE code_departement = :dep AND annee = :year"),
                    {"dep": dep, "year": year}
                ).scalar()
            if already > 0:
                print(f"[SKIP] {year}/{dep} deja charge ({already:,} rows)")
                continue

            print(f"\n--- {year}/{dep} ---")

            # 1. Truncate staging
            truncate_staging()

            # 2. Load CSV dans staging
            print(f"  [LOAD] {csv_path.name}...")
            rows = load_single_csv(csv_path, year)
            total_loaded += rows
            print(f"  [LOAD] {rows:,} lignes chargees dans staging")

            # 3. Transform staging -> core
            print(f"  [TRANSFORM] staging -> core...")
            count_before = 0
            with engine.connect() as conn:
                count_before = conn.execute(
                    text("SELECT COUNT(*) FROM core.transactions")
                ).scalar()

            with engine.begin() as conn:
                conn.execute(text("SET statement_timeout = '300s'"))
                for stmt in transform_sql.split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        conn.execute(text(stmt))

            with engine.connect() as conn:
                count_after = conn.execute(
                    text("SELECT COUNT(*) FROM core.transactions")
                ).scalar()

            inserted = count_after - count_before
            total_transformed += inserted
            print(f"  [TRANSFORM] {inserted:,} transactions inserees dans core")

            # 4. Truncate staging (liberer espace)
            truncate_staging()

    print(f"\n=== Chargement termine ===")
    print(f"  Lignes staging totales : {total_loaded:,}")
    print(f"  Transactions core      : {total_transformed:,}")


def detect_outliers():
    """Detecte les outliers dans core.transactions via IQR par dept x type x annee."""
    engine = get_engine()
    print("[OUTLIERS] Detection des outliers par IQR...")

    with engine.begin() as conn:
        # Reset
        conn.execute(text("UPDATE core.transactions SET is_outlier = FALSE"))

        # Marquer les outliers par departement x type_bien x annee
        conn.execute(text("""
            WITH stats AS (
                SELECT
                    code_departement,
                    type_bien,
                    annee,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY prix_m2) AS q1,
                    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY prix_m2) AS q3
                FROM core.transactions
                GROUP BY code_departement, type_bien, annee
            )
            UPDATE core.transactions t
            SET is_outlier = TRUE
            FROM stats s
            WHERE t.code_departement = s.code_departement
              AND t.type_bien = s.type_bien
              AND t.annee = s.annee
              AND (t.prix_m2 < s.q1 - 1.5 * (s.q3 - s.q1)
                   OR t.prix_m2 > s.q3 + 1.5 * (s.q3 - s.q1))
        """))

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM core.transactions")).scalar()
        outliers = conn.execute(
            text("SELECT COUNT(*) FROM core.transactions WHERE is_outlier")
        ).scalar()

    pct = 100 * outliers / max(total, 1)
    print(f"[OUTLIERS] {outliers:,} outliers sur {total:,} transactions ({pct:.1f}%)")
