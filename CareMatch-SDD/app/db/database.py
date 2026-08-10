from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(url: str | None = None):
    url = url or get_settings().database_url
    connect_args = {}
    kwargs = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if url in ("sqlite://", "sqlite:///:memory:"):
            # Share one connection so an in-memory DB survives across sessions.
            kwargs["poolclass"] = StaticPool
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True, **kwargs)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Generator[Session, None, None]:
    db = SessionLocal()
    request.state.db = db
    try:
        yield db
    finally:
        db.close()


def init_db(force: bool = False) -> None:
    from app.db import models  # noqa: F401  (register models with Base metadata)

    if force:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
