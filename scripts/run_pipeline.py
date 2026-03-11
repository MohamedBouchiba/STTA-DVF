"""CLI pour executer le pipeline ETL complet."""

import sys
import uuid
from pathlib import Path

import click

# Ajouter le projet au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import check_connection
from src.ingestion.metadata import init_ingestion_log, log_start, log_finish
from src.ingestion.download import download_dvf_etalab
from src.ingestion.load_csv import (
    create_staging_table,
    load_and_transform,
    detect_outliers,
)
from src.transform.staging_to_core import create_core_tables
from src.transform.core_to_mart import refresh_marts
from src.transform.quality import run_quality_checks


@click.group()
def cli():
    """STTA-DVF Pipeline ETL."""
    pass


@cli.command()
def check():
    """Verifie la connexion a la base de donnees."""
    if check_connection():
        click.echo("Connexion OK.")
    else:
        click.echo("Connexion echouee.")
        sys.exit(1)


@cli.command()
def init_db():
    """Cree les schemas et tables (staging + core + mart)."""
    from src.db import get_engine
    from sqlalchemy import text

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS mart"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    click.echo("Schemas crees.")

    create_staging_table()
    create_core_tables()
    click.echo("Tables staging + core creees.")

    from src.transform.core_to_mart import create_mart_tables
    create_mart_tables()
    click.echo("Tables mart creees.")

    init_ingestion_log()
    click.echo("Table ingestion_log creee.")


@cli.command()
@click.option("--year", type=int, default=None, help="Annee specifique (ex: 2024).")
@click.option("--dep", default=None, help="Departement specifique (ex: 75).")
@click.option("--force", is_flag=True, help="Re-telecharger meme si existant.")
def download(year, dep, force):
    """Telecharge les CSV DVF Etalab."""
    years = [year] if year else None
    departements = [dep] if dep else None
    download_dvf_etalab(years=years, departements=departements, force=force)


@cli.command()
@click.option("--year", type=int, default=None, help="Annee specifique (ex: 2024).")
@click.option("--dep", default=None, help="Departement specifique (ex: 75).")
def load(year, dep):
    """Charge les CSV dans staging puis transforme vers core."""
    years = [year] if year else None
    departements = [dep] if dep else None

    init_ingestion_log()
    run_id = str(uuid.uuid4())[:8]
    log_id = log_start(run_id, "load_and_transform")

    load_and_transform(years=years, departements=departements)

    log_finish(log_id, "success")


@cli.command()
def outliers():
    """Detecte les outliers dans core.transactions."""
    detect_outliers()


@cli.command()
def mart():
    """Rafraichit les tables mart."""
    click.echo("Rafraichissement des marts...")
    refresh_marts()


@cli.command()
def quality():
    """Execute les controles qualite."""
    click.echo("Controles qualite...")
    run_quality_checks()


@cli.command()
@click.option("--year", type=int, default=None, help="Annee specifique.")
@click.option("--dep", default=None, help="Departement specifique.")
def run_all(year, dep):
    """Execute le pipeline complet : init -> download -> load -> outliers -> mart -> quality."""
    run_id = str(uuid.uuid4())[:8]

    # Etape 0 : Init DB
    click.echo("\n=== ETAPE 0 : Initialisation DB ===")
    from src.db import get_engine
    from sqlalchemy import text
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS mart"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

    init_ingestion_log()
    log_id = log_start(run_id, "full_pipeline")

    create_staging_table()
    create_core_tables()

    # Etape 1 : Download
    click.echo("\n=== ETAPE 1 : Telechargement ===")
    years = [year] if year else None
    departements = [dep] if dep else None
    download_dvf_etalab(years=years, departements=departements)

    # Etape 2 : Load + Transform
    click.echo("\n=== ETAPE 2 : Chargement + Transformation ===")
    load_and_transform(years=years, departements=departements)

    # Etape 3 : Outliers
    click.echo("\n=== ETAPE 3 : Detection outliers ===")
    detect_outliers()

    # Etape 4 : Mart
    click.echo("\n=== ETAPE 4 : Marts ===")
    refresh_marts()

    # Etape 5 : Quality
    click.echo("\n=== ETAPE 5 : Qualite ===")
    run_quality_checks()

    log_finish(log_id, "success")
    click.echo("\n=== Pipeline termine ===")


if __name__ == "__main__":
    cli()
