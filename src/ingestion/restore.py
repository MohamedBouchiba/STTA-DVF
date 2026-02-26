"""Restauration des dumps DVF+ dans PostgreSQL."""

import subprocess
from pathlib import Path

from src.config import (
    LANDING_DIR,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
)


def restore_backup(filepath: Path, schema: str = "staging") -> bool:
    """
    Restaure un fichier .backup via pg_restore.

    Args:
        filepath: Chemin vers le fichier .backup.
        schema: Schema cible (par defaut 'staging').

    Returns:
        True si la restauration a reussi.
    """
    env = {
        "PGPASSWORD": POSTGRES_PASSWORD,
        "PATH": subprocess.os.environ.get("PATH", ""),
    }

    cmd = [
        "pg_restore",
        f"--host={POSTGRES_HOST}",
        f"--port={POSTGRES_PORT}",
        f"--username={POSTGRES_USER}",
        f"--dbname={POSTGRES_DB}",
        "--no-owner",
        "--no-acl",
        "--if-exists",
        "--clean",
        str(filepath),
    ]

    print(f"[RESTORE] {filepath.name} -> {schema}")
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=3600,
        )
        if result.returncode != 0:
            # pg_restore retourne souvent des warnings non-bloquants
            if "ERROR" in result.stderr:
                print(f"  Erreurs: {result.stderr[:500]}")
                return False
            else:
                print(f"  Warnings (non-bloquant): {result.stderr[:200]}")
        print(f"  OK")
        return True
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT apres 3600s")
        return False
    except FileNotFoundError:
        print("  pg_restore non trouve. Verifier que PostgreSQL client est installe.")
        return False


def restore_sql_gz(filepath: Path) -> bool:
    """
    Restaure un fichier .sql.gz via psql.

    Args:
        filepath: Chemin vers le fichier .sql.gz.

    Returns:
        True si la restauration a reussi.
    """
    env = {
        "PGPASSWORD": POSTGRES_PASSWORD,
        "PATH": subprocess.os.environ.get("PATH", ""),
    }

    # gunzip | psql
    print(f"[RESTORE] {filepath.name}")
    try:
        gunzip = subprocess.Popen(
            ["gunzip", "-c", str(filepath)],
            stdout=subprocess.PIPE,
            env=env,
        )
        psql = subprocess.Popen(
            [
                "psql",
                f"--host={POSTGRES_HOST}",
                f"--port={POSTGRES_PORT}",
                f"--username={POSTGRES_USER}",
                f"--dbname={POSTGRES_DB}",
            ],
            stdin=gunzip.stdout,
            capture_output=True,
            text=True,
            env=env,
        )
        gunzip.stdout.close()
        stdout, stderr = psql.communicate(timeout=3600)

        if psql.returncode != 0:
            print(f"  Erreur: {stderr[:500]}")
            return False
        print(f"  OK")
        return True
    except Exception as e:
        print(f"  Erreur: {e}")
        return False


def restore_department(dep_code: str) -> bool:
    """Restaure les donnees d'un departement."""
    # Chercher le fichier dans le landing
    for ext in [".backup", ".sql.gz"]:
        filepath = LANDING_DIR / f"dvfplus_{dep_code}{ext}"
        if filepath.exists():
            if ext == ".backup":
                return restore_backup(filepath)
            else:
                return restore_sql_gz(filepath)

    print(f"[NOT_FOUND] Aucun fichier pour le departement {dep_code}")
    return False


def restore_all(departements: list[str] | None = None) -> dict[str, bool]:
    """
    Restaure tous les departements disponibles.

    Args:
        departements: Liste des codes departements a restaurer.
                     Si None, restaure tous les fichiers du landing.

    Returns:
        {dep_code: success}
    """
    from src.ingestion.download import DEPARTEMENTS

    if departements is None:
        # Detecter les departements disponibles dans le landing
        files = list(LANDING_DIR.glob("dvfplus_*"))
        departements = []
        for f in files:
            # Extraire le code departement du nom de fichier
            name = f.stem  # dvfplus_75 ou dvfplus_75.sql
            if name.startswith("dvfplus_"):
                dep = name.replace("dvfplus_", "").replace(".sql", "")
                if dep in DEPARTEMENTS:
                    departements.append(dep)
        departements = sorted(set(departements))

    results = {}
    total = len(departements)
    for i, dep in enumerate(departements, 1):
        print(f"\n--- Departement {dep} ({i}/{total}) ---")
        results[dep] = restore_department(dep)

    ok = sum(results.values())
    print(f"\n=== Restauration terminee: {ok}/{total} departements ===")
    return results
