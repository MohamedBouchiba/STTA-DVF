"""CLI pour executer le pipeline ETL complet."""

import sys
import uuid
from pathlib import Path

import click

# Ajouter le projet au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import check_connection
from src.ingestion.metadata import init_ingestion_log, log_start, log_finish
from src.ingestion.restore import restore_all, restore_department
from src.transform.staging_to_core import run_transform
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
@click.option("--dep", default=None, help="Code departement (ex: 75). Si absent, restaure tout.")
def restore(dep):
    """Restaure les dumps DVF+ dans staging."""
    init_ingestion_log()
    run_id = str(uuid.uuid4())[:8]

    if dep:
        click.echo(f"Restauration du departement {dep}...")
        log_id = log_start(run_id, "restore", [dep])
        success = restore_department(dep)
        log_finish(log_id, "success" if success else "error")
    else:
        click.echo("Restauration de tous les departements...")
        log_id = log_start(run_id, "restore_all")
        results = restore_all()
        ok = sum(results.values())
        total = len(results)
        log_finish(log_id, "success" if ok == total else "partial", row_count=ok)


@cli.command()
def transform():
    """Transforme staging -> core."""
    click.echo("Transformation staging -> core...")
    run_transform()


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
@click.option("--dep", default=None, help="Departement pilote (ex: 75). Si absent, tout le pipeline.")
def all(dep):
    """Execute le pipeline complet : restore -> transform -> mart -> quality."""
    run_id = str(uuid.uuid4())[:8]
    init_ingestion_log()

    # Etape 1 : Restore
    click.echo("\n=== ETAPE 1 : Restauration ===")
    log_id = log_start(run_id, "full_pipeline")

    if dep:
        restore_department(dep)
    else:
        restore_all()

    # Etape 2 : Transform
    click.echo("\n=== ETAPE 2 : Transformation ===")
    run_transform()

    # Etape 3 : Mart
    click.echo("\n=== ETAPE 3 : Marts ===")
    refresh_marts()

    # Etape 4 : Quality
    click.echo("\n=== ETAPE 4 : Qualite ===")
    run_quality_checks()

    log_finish(log_id, "success")
    click.echo("\n=== Pipeline termine ===")


if __name__ == "__main__":
    cli()
