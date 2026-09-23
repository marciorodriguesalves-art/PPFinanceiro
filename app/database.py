from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base declarativa compartilhada por todos os modelos."""


def _make_engine(url: str):
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args, future=True)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator:
    """Dependency do FastAPI: fornece uma sessão por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
