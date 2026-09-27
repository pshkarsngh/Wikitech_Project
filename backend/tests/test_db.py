"""Proves which failures ``session_scope`` absorbs and which it must not.

``session_scope`` swallows database failures so that an outage cannot take a
request down, and the database is optional, so this file deliberately never
opens a connection. It drives the scope with a stub session instead, which is
what makes the central assertion available in a plain ``pytest`` run rather than
only under ``TEST_DATABASE_URL``: a test that guards this behaviour and is
skipped by default is a test that will not run when the behaviour breaks.

The scope's ``try`` block wraps the ``yield``, so the caller's own code is
inside it. A bare ``except Exception`` therefore could not distinguish a dead
database from a ``TypeError`` three lines up in ``repository.py``, and the log
line it wrote said "Database write failed" for a database that was working.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from app import db


class _StubSession:
    """Records the lifecycle calls ``session_scope`` is responsible for making."""

    def __init__(self, *, commit_error: Exception | None = None) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self._commit_error = commit_error

    def commit(self) -> None:
        self.commits += 1
        if self._commit_error is not None:
            raise self._commit_error

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closes += 1


@pytest.fixture
def stub_session(monkeypatch: pytest.MonkeyPatch):
    """Install a session factory and hand back the session it will produce."""

    def _install(*, commit_error: Exception | None = None) -> _StubSession:
        session = _StubSession(commit_error=commit_error)
        monkeypatch.setattr(db, "_session_factory", lambda: session)
        return session

    return _install


def test_a_database_failure_is_swallowed_so_a_request_still_completes(
    stub_session,
) -> None:
    session = stub_session(commit_error=OperationalError("COMMIT", {}, Exception("dead")))
    with db.session_scope() as scope:
        assert scope is session
    assert session.rollbacks == 1, "a swallowed database failure must still roll back"
    assert session.closes == 1


def test_a_database_failure_is_logged_rather_than_silently_dropped(
    stub_session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The log line is the only evidence the cache was dropped, so it must exist."""

    stub_session(commit_error=OperationalError("COMMIT", {}, Exception("dead")))
    with caplog.at_level("ERROR"), db.session_scope():
        pass
    assert "Database write failed" in caplog.text


def test_a_programming_error_in_the_caller_propagates(stub_session) -> None:
    """The B5 regression.

    A ``TypeError`` in the caller is a bug in this codebase. It used to be
    absorbed, reported as a database outage, and the write was dropped while
    the request returned 200.
    """

    session = stub_session()
    with pytest.raises(TypeError, match="not subscriptable"):
        with db.session_scope() as scope:
            scope["missing key"]  # type: ignore[index]
    assert session.closes == 1, "the connection must be released on the way out"
    assert session.commits == 0, "a scope that raised must not go on to commit"


def test_the_session_is_closed_even_when_the_caller_raises(stub_session) -> None:
    """A propagating error must not leak a pooled connection."""

    session = stub_session()
    with pytest.raises(ValueError):
        with db.session_scope():
            raise ValueError("caller bug")
    assert session.closes == 1
    assert session.commits == 0, "a scope that raised must not go on to commit"
    assert session.rollbacks == 0, "no database error occurred, so nothing to roll back"


def test_a_read_only_scope_commits_nothing(stub_session) -> None:
    session = stub_session()
    with db.session_scope(read_only=True):
        pass
    assert session.commits == 0
    assert session.closes == 1


def test_persistence_disabled_yields_none_and_touches_no_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(db, "_session_factory", None)
    with db.session_scope() as session:
        assert session is None


def test_persistence_disabled_also_yields_none_for_a_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "_session_factory", None)
    with db.session_scope(read_only=True) as session:
        assert session is None
