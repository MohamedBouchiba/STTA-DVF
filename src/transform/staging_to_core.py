"""Transformation staging -> core."""

from pathlib import Path

from sqlalchemy import text

from src.config import SQL_DIR
from src.db import get_engine


def create_core_tables():
    """Cree les tables core si elles n'existent pas."""
    engine = get_engine()
    for sql_file in ["create_core_transactions.sql", "create_core_geo.sql"]:
        path = SQL_DIR / "core" / sql_file
        sql = path.read_text(encoding="utf-8")
        with engine.begin() as conn:
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(text(stmt))
        print(f"[DDL] {sql_file} execute")


def run_transform():
    """Execute la transformation staging -> core."""
    create_core_tables()

    engine = get_engine()
    sql_path = SQL_DIR / "core" / "transform_staging_to_core.sql"
    sql = sql_path.read_text(encoding="utf-8")

    # Executer chaque statement separement
    with engine.begin() as conn:
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                print(f"  Executing: {stmt[:80]}...")
                conn.execute(text(stmt))

    # Afficher les comptages
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM core.transactions")).scalar()
        clean = conn.execute(
            text("SELECT COUNT(*) FROM core.transactions WHERE quality_score & 1 = 0")
        ).scalar()
        geo = conn.execute(text("SELECT COUNT(*) FROM core.geo")).scalar()
        outliers = total - clean

    print(f"\n=== Transformation terminee ===")
    print(f"  Transactions totales : {total:,}")
    print(f"  Transactions propres : {clean:,}")
    print(f"  Outliers detectes    : {outliers:,} ({100*outliers/max(total,1):.1f}%)")
    print(f"  Geolocalisees        : {geo:,}")


if __name__ == "__main__":
    run_transform()
