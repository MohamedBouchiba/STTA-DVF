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
        # Executer chaque sous-statement du bloc
        for stmt in block.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                with engine.begin() as conn:
                    print(f"  Executing: {stmt[:80]}...")
                    conn.execute(text(stmt))

    # Comptages
    with engine.connect() as conn:
        commune = conn.execute(text("SELECT COUNT(*) FROM mart.prix_m2_commune")).scalar()
        dep = conn.execute(text("SELECT COUNT(*) FROM mart.prix_m2_departement")).scalar()
        zones = conn.execute(text("SELECT COUNT(*) FROM mart.zone_stats")).scalar()
        indices = conn.execute(text("SELECT COUNT(*) FROM mart.indices_temporels")).scalar()

    print(f"\n=== Marts rafraichis ===")
    print(f"  prix_m2_commune     : {commune:,} lignes")
    print(f"  prix_m2_departement : {dep:,} lignes")
    print(f"  zone_stats          : {zones:,} lignes")
    print(f"  indices_temporels   : {indices:,} lignes")


if __name__ == "__main__":
    refresh_marts()
