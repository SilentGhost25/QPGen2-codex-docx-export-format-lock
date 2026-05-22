from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False, "timeout": 30.0} if settings.database_url.startswith("sqlite") else {}
engine_kwargs = {"connect_args": connect_args, "future": True}
if settings.database_url in {"sqlite://", "sqlite:///:memory:"}:
    engine_kwargs["poolclass"] = StaticPool
engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
