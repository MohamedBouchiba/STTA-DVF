"""Connexion SQLAlchemy a PostgreSQL/PostGIS."""

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.config import DATABASE_URL


_engine = None


def get_engine():
    """Retourne un engine SQLAlchemy (singleton)."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


@contextmanager
def get_session():
    """Context manager pour une session SQLAlchemy."""
    Session = sessionmaker(bind=get_engine())
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def execute_sql_file(path: str | Path):
    """Execute un fichier SQL complet contre la base."""
    sql_path = Path(path)
    sql_content = sql_path.read_text(encoding="utf-8")
    engine = get_engine()
    with engine.begin() as conn:
        for statement in sql_content.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))


def check_connection() -> bool:
    """Verifie que la connexion a la base fonctionne."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT PostGIS_Version()"))
            version = result.scalar()
            print(f"PostGIS version: {version}")
            return True
    except Exception as e:
        print(f"Erreur de connexion: {e}")
        return False
