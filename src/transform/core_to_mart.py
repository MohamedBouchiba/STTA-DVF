"""Construction des tables mart depuis core."""

from sqlalchemy import text

from src.config import SQL_DIR
from src.db import get_engine


def create_mart_tables():
    """Cree les tables mart si elles n'existent pas."""
    engine = get_engine()
    for sql_file in [
        "create_mart_prix_m2.sql",
        "create_mart_zone_stats.sql",
        "create_mart_indices.sql",
    ]:
        path = SQL_DIR / "mart" / sql_file
        sql = path.read_text(encoding="utf-8")
        with engine.begin() as conn:
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(text(stmt))
        print(f"[DDL] {sql_file} execute")


def refresh_marts():
    """Rafraichit toutes les tables mart."""
    create_mart_tables()

    engine = get_engine()
    sql_path = SQL_DIR / "mart" / "refresh_marts.sql"
    sql = sql_path.read_text(encoding="utf-8")

    # Separer et executer les statements
    # On split par les commentaires de section pour garder des blocs logiques
    statements = []
    current = []
    for line in sql.split("\n"):
        stripped = line.strip()
        if stripped.startswith("-- ") and stripped.endswith(" ---") and current:
            statements.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        statements.append("\n".join(current))

    for block in statements:
        for stmt in block.split(";"):
            # Retirer les lignes de commentaires avant de verifier si le statement est vide
            lines = [l for l in stmt.strip().splitlines() if not l.strip().startswith("--")]
            clean = "\n".join(lines).strip()
            if clean:
                with engine.begin() as conn:
                    conn.execute(text("SET statement_timeout = '300s'"))
                    print(f"  Executing: {clean[:80]}...")
                    conn.execute(text(clean))

    # Comptages
    with engine.connect() as conn:
        commune = conn.execute(text("SELECT COUNT(*) FROM mart.stats_commune")).scalar()
        dep = conn.execute(text("SELECT COUNT(*) FROM mart.stats_departement")).scalar()
        zones = conn.execute(text("SELECT COUNT(*) FROM mart.zone_stats")).scalar()
        indices = conn.execute(text("SELECT COUNT(*) FROM mart.indices_temporels")).scalar()

    print(f"\n=== Marts rafraichis ===")
    print(f"  stats_commune       : {commune:,} lignes")
    print(f"  stats_departement   : {dep:,} lignes")
    print(f"  zone_stats          : {zones:,} lignes")
    print(f"  indices_temporels   : {indices:,} lignes")


if __name__ == "__main__":
    refresh_marts()
