"""Rapport de qualite des donnees."""

import pandas as pd
from sqlalchemy import text

from src.config import SQL_DIR
from src.db import get_engine


def run_quality_checks() -> dict[str, pd.DataFrame]:
    """
    Execute les controles qualite et retourne les resultats.

    Returns:
        Dictionnaire de DataFrames avec les resultats par controle.
    """
    engine = get_engine()
    sql_path = SQL_DIR / "quality" / "quality_checks.sql"
    sql_content = sql_path.read_text(encoding="utf-8")

    # Separer les requetes (chaque SELECT est un controle)
    queries = []
    current = []
    for line in sql_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("--") and not current:
            continue
        if stripped.startswith("--") and current:
            # Nouveau bloc de commentaire = fin du precedent
            query = "\n".join(current).strip().rstrip(";")
            if query:
                queries.append(query)
            current = []
            continue
        current.append(line)
    # Dernier bloc
    query = "\n".join(current).strip().rstrip(";")
    if query:
        queries.append(query)

    check_names = [
        "comptages",
        "surfaces_nulles",
        "distribution_prix",
        "transactions_annee",
        "couverture_geo",
        "taux_outliers",
    ]

    results = {}
    for name, query in zip(check_names, queries):
        try:
            df = pd.read_sql(query, engine)
            results[name] = df
            print(f"\n=== {name.upper()} ===")
            print(df.to_string(index=False))
        except Exception as e:
            print(f"\n=== {name.upper()} === ERREUR: {e}")

    return results


if __name__ == "__main__":
    run_quality_checks()
