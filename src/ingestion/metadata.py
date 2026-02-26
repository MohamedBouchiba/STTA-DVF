"""Suivi des executions du pipeline d'ingestion."""

from datetime import datetime, timezone

from sqlalchemy import text

from src.db import get_engine


INGESTION_LOG_DDL = """
CREATE TABLE IF NOT EXISTS staging.ingestion_log (
    id              SERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          TEXT DEFAULT 'running',
    step            TEXT,
    departements    TEXT[],
    row_count       INTEGER,
    notes           TEXT
);
"""


def init_ingestion_log():
    """Cree la table de log si elle n'existe pas."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(INGESTION_LOG_DDL))


def log_start(run_id: str, step: str, departements: list[str] | None = None) -> int:
    """Enregistre le debut d'une execution. Retourne l'id du log."""
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO staging.ingestion_log (run_id, started_at, step, departements, status)
                VALUES (:run_id, :started_at, :step, :departements, 'running')
                RETURNING id
            """),
            {
                "run_id": run_id,
                "started_at": datetime.now(timezone.utc),
                "step": step,
                "departements": departements,
            },
        )
        return result.scalar()


def log_finish(log_id: int, status: str = "success", row_count: int | None = None, notes: str | None = None):
    """Met a jour le log apres execution."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE staging.ingestion_log
                SET finished_at = :finished_at, status = :status,
                    row_count = :row_count, notes = :notes
                WHERE id = :id
            """),
            {
                "finished_at": datetime.now(timezone.utc),
                "status": status,
                "row_count": row_count,
                "notes": notes,
                "id": log_id,
            },
        )
