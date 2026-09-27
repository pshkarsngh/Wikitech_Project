"""Database engine / session management.

The database is optional. When ``DATABASE_URL`` is empty the app still answers
requests, it just does not cache anything. A failing commit is logged and
swallowed, so a database problem can never take the API down. "A database
problem" is meant literally: a bug in our own code is not swallowed, because
swallowing it hides the bug behind a log line that blames the database.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
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
def session_scope(*, read_only: bool = False) -> Iterator[Session | None]:
    """Yield a session, or ``None`` when persistence is disabled.

    Database failures are logged and ignored: the caller has already built its
    response and the cache is only an optimisation. The catch is deliberately
    narrowed to :class:`SQLAlchemyError` for that reason, because the ``yield``
    sits inside the ``try`` and so the caller's own code is inside it too. A
    ``TypeError`` raised by a repository is a bug, not an outage, and swallowing
    it here logged "Database write failed" for a database that was working
    perfectly - the log pointed the investigation at the wrong component and the
    caller carried on with a silently dropped write. Programming errors now
    propagate; ``finally`` still closes the session, so nothing leaks.

    ``read_only`` yields the same session but never commits, for the cache lookup. The
    read path has nothing to write, and a read-only scope must not be able to leave a
    half-finished unit of work behind in the autocommit-less session it was handed.
    """

    if _session_factory is None:
        yield None
        return

    session = _session_factory()
    try:
        yield session
        if not read_only:
            session.commit()
    except SQLAlchemyError:
        logger.exception("Database write failed, continuing without cache")
        session.rollback()
    finally:
        session.close()


def create_all() -> None:
    if _engine is None:
        return
    Base.metadata.create_all(_engine)


def ping() -> bool:
    # The broad catch here is not the one narrowed in session_scope, and the
    # difference is deliberate: no caller code runs inside this try, so there is
    # no caller's bug to mislabel. The guarantee that matters is that this never
    # raises, because the container HEALTHCHECK reads /api/health and an
    # exception here would surface as a crash rather than as an unhealthy
    # container with a diagnosis.
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
