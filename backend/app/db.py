"""Database engine / session management.

The database is optional. When ``DATABASE_URL`` is empty the app still answers
requests, it just does not cache anything. A failing commit is logged and
swallowed, so a database problem can never take the API down.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import Base

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_engine(settings: Settings) -> None:
    global _engine, _session_factory
    shutdown()
    if not settings.database_enabled:
        logger.info("DATABASE_URL is empty, running without persistence")
        return
    _engine = create_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
    )
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)


def get_engine() -> Engine | None:
    return _engine


@contextmanager
def session_scope() -> Iterator[Session | None]:
    """Yield a session, or ``None`` when persistence is disabled.

    Failures while committing are logged and ignored: the caller has already
    built its response and the cache is only an optimisation.
    """

    if _session_factory is None:
        yield None
        return

    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:  # noqa: BLE001 - persistence must never break a request
        logger.exception("Database write failed, continuing without cache")
        session.rollback()
    finally:
        session.close()


def create_all() -> None:
    if _engine is None:
        return
    Base.metadata.create_all(_engine)


def ping() -> bool:
    if _engine is None:
        return False
    try:
        with _engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - health check must never raise
        logger.exception("Database ping failed")
        return False
    return True


def shutdown() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
