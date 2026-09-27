"""Executes the persistence layer against a real PostgreSQL, which nothing else does.

Every other test in this suite runs with an empty ``DATABASE_URL``, so ``store_analysis``,
``cached_analysis`` and the retention prune have never been executed - only the shape of
the rows they build has been asserted. That is the blind spot UAT-02 survived: the link
insert violated ``uq_link``, the transaction rolled back whole, every request still
returned 200, and ``/api/health`` still reported a healthy database. Nothing could notice,
because no test in the repository ever opened a connection.

Skipped unless ``TEST_DATABASE_URL`` names a database whose name contains ``test``. These
tests are destructive: each one truncates all three tables.
"""

from __future__ import annotations

import logging
import os
import pathlib
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine, func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app import db
from app.config import Settings
from app.models import AnalysisRun, Article, ArticleLink
from app.repository import cached_analysis, store_analysis
from app.schemas import AnalysisResult
from app.services.analysis import analyze_article
from tests.fake_wikipedia import ADA, FakeWikipediaClient

_URL_ENV = "TEST_DATABASE_URL"
_INIT_SQL = pathlib.Path(__file__).parents[2] / "database" / "init.sql"

_URL = os.environ.get(_URL_ENV, "").strip()
if not _URL:
    pytest.skip(
        f"{_URL_ENV} is not set, so no database is exercised and every test here is skipped",
        allow_module_level=True,
    )
if "test" not in _URL.split("?", 1)[0].rsplit("/", 1)[-1].lower():
    # These tests truncate. A typo pointing at the real cache would empty it silently.
    pytest.fail(
        f"{_URL_ENV} names a database that does not look like a test database. Every test "
        "in this file truncates articles, article_links and analysis_runs.",
        pytrace=False,
    )


async def _analysis() -> AnalysisResult:
    """A real analysis of the fixture wiki, computed without a network call."""

    return await analyze_article(FakeWikipediaClient(), Settings(database_url=""), ADA)


def _settings(**overrides: object) -> Settings:
    return Settings(database_url=_URL, **overrides)  # type: ignore[arg-type]


def _index_names(engine: Engine, table: str) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = :table"),
            {"table": table},
        )
        return {row[0] for row in rows}


def _column_names(engine: Engine, table: str) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :table"
            ),
            {"table": table},
        )
        return {row[0] for row in rows}


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    """A live engine, built the way the application builds it at startup."""

    db.init_engine(Settings(database_url=_URL))
    db.create_all()
    connected = db.get_engine()
    assert connected is not None, "init_engine did not produce an engine"
    try:
        yield connected
    finally:
        # `app.db` keeps the engine in a module global, and the rest of this suite asserts
        # that an unconfigured application caches nothing. Leaving it behind would make
        # `test_repository.py` depend on the order this file happened to run in.
        db.shutdown()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Reads the database as it is, and raises when a query fails.

    Neither of the app's own two paths will do. `db.session_scope` logs and swallows, which
    is right for a request and wrong for a test: a query that failed here would come back
    as an empty result and be reported as a missing row rather than as the error it is. And
    a bare `Connection` executing an ORM `select()` returns column values, not objects.
    """

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as open_session:
        yield open_session


@pytest.fixture(autouse=True)
def empty_tables(engine: Engine) -> Iterator[None]:
    with engine.begin() as connection:
        connection.execute(
            text("TRUNCATE analysis_runs, article_links, articles RESTART IDENTITY")
        )
    yield


def _article_row(page_id: int, title: str) -> dict[str, object]:
    return {
        "page_id": page_id,
        "title": title,
        "normalized_title": title.lower(),
        "fetched_at": datetime.now(timezone.utc),
    }


def _stale_run_row(days_old: int) -> dict[str, object]:
    return {
        "seed_page_id": 1,
        "seed_title": f"A run from {days_old} days ago",
        "total_links": 1,
        "total_missing": 0,
        "total_one_way": 0,
        "created_at": datetime.now(timezone.utc) - timedelta(days=days_old),
    }


# --- the write path -------------------------------------------------------------


async def test_a_stored_analysis_lands_as_the_rows_it_describes(session: Session) -> None:
    """Every value the response carries has to survive the round trip into a row."""

    result = await _analysis()
    store_analysis(result, settings=_settings())

    article = session.execute(select(Article)).scalars().one()
    assert article.page_id == result.article.page_id
    assert article.title == result.article.title == ADA
    assert article.description == result.article.description
    assert article.extract == result.article.extract
    assert article.url == result.article.url
    assert article.length == result.article.length
    assert article.analysis_payload is not None
    assert article.fetched_at is not None

    links = (
        session.execute(select(ArticleLink).order_by(ArticleLink.id)).scalars().all()
    )
    assert [link.target_title for link in links] == [link.title for link in result.links]
    assert [link.exists for link in links] == [link.exists for link in result.links]
    assert [link.target_page_id for link in links] == [link.page_id for link in result.links]
    assert {link.source_page_id for link in links} == {result.article.page_id}

    run = session.execute(select(AnalysisRun)).scalars().one()
    assert (run.seed_page_id, run.seed_title) == (
        result.article.page_id,
        result.article.title,
    )
    assert (run.total_links, run.total_missing, run.total_one_way) == (
        result.summary.total_links,
        result.summary.total_missing,
        result.summary.total_one_way,
    )
    assert run.created_at is not None


async def test_an_article_without_a_page_id_is_not_stored(session: Session) -> None:
    """There is no primary key to hang the links off, so there is nothing to write."""

    result = await _analysis()
    orphan = result.model_copy(
        update={"article": result.article.model_copy(update={"page_id": None})}
    )
    store_analysis(orphan, settings=_settings())

    for model in (Article, ArticleLink, AnalysisRun):
        assert session.execute(select(func.count()).select_from(model)).scalar_one() == 0


# --- the duplicate that UAT-02 lived on ----------------------------------------


async def test_a_target_reached_through_a_redirect_lands_once_and_nothing_is_lost(
    session: Session,
) -> None:
    """The executed form of UAT-02, which no assertion about row shape could have caught.

    `Ada Lovelace` links both `Allan G. Bromley` and a title that redirects there, so
    `resolve_titles` returns the same resolved title twice. Both rows used to be inserted,
    `uq_link` rejected the statement, and the whole transaction was lost - the article, its
    links and its run, all of it, on every request, silently.
    """

    result = await _analysis()
    first = result.links[0]
    duplicated = result.model_copy(
        update={"links": [*result.links, first.model_copy(update={"redirected": True})]}
    )
    store_analysis(duplicated, settings=_settings())

    titles = list(
        session.execute(
            select(ArticleLink.target_title).order_by(ArticleLink.id)
        ).scalars()
    )
    assert titles.count(first.title) == 1, "the redirect and the canonical title are one row"
    assert len(titles) == len(duplicated.links) - 1
    # The write is atomic, so the rest of the transaction is there too. Before the fix all
    # three of these counts were zero.
    assert session.execute(select(func.count()).select_from(Article)).scalar_one() == 1
    assert (
        session.execute(select(func.count()).select_from(ArticleLink)).scalar_one()
        == len(titles)
    )
    assert session.execute(select(func.count()).select_from(AnalysisRun)).scalar_one() == 1


def test_the_database_rejects_the_duplicate_the_dedupe_prevents(
    engine: Engine, session: Session
) -> None:
    """Proves the collapse above is load-bearing rather than defensive.

    If `uq_link` were not really in the database, the fix that removed the crash would be
    hiding a constraint nobody has, and the next duplicate would quietly be stored twice.
    """

    session.execute(insert(Article).values(**_article_row(1, ADA)))
    session.commit()

    row = {
        "source_page_id": 1,
        "target_title": "Allan G. Bromley",
        "target_normalized_title": "Allan G. Bromley",
        "target_page_id": 4341343,
        "exists": True,
    }
    with pytest.raises(IntegrityError):
        session.execute(insert(ArticleLink).values([row, dict(row)]))
    session.rollback()

    assert (
        session.execute(select(func.count()).select_from(ArticleLink)).scalar_one() == 0
    ), "the rejected statement must leave nothing behind"


# --- re-analysing ---------------------------------------------------------------


async def test_re_analysing_an_article_replaces_its_links_rather_than_adding_to_them(
    session: Session,
) -> None:
    result = await _analysis()
    store_analysis(result, settings=_settings())

    store_analysis(
        result.model_copy(update={"links": result.links[:1]}), settings=_settings()
    )

    titles = list(session.execute(select(ArticleLink.target_title)).scalars())
    assert titles == [result.links[0].title]
    assert session.execute(select(func.count()).select_from(Article)).scalar_one() == 1
    # One row per analysis, so both runs are kept - that table is the request history.
    assert session.execute(select(func.count()).select_from(AnalysisRun)).scalar_one() == 2


# --- the read path --------------------------------------------------------------


async def test_a_stored_analysis_is_served_back_from_the_database() -> None:
    """A write that cannot be read is not a cache, it is a log.

    This is the round trip that decides whether the database is a cache at all: the
    analysis is written, and then asked for again by the key a repeat request would use.
    """

    result = await _analysis()
    store_analysis(result, settings=_settings())

    assert cached_analysis(ADA, ttl_seconds=3600) == result


async def test_a_repeat_request_finds_the_cache_however_the_title_is_spelled() -> None:
    """The user types the name; MediaWiki answers with the canonical spelling.

    So the cache is asked for with `ada lovelace` while the row was written with
    `Ada Lovelace`, and a case-sensitive `VARCHAR` comparison finds nothing. That is not a
    near miss. It means the read path never answers, `X-Cache` is always `miss`, and every
    request pays for a full crawl of Wikipedia.
    """

    result = await _analysis()
    store_analysis(result, settings=_settings())

    for spelling in (ADA, ADA.lower(), "ada_lovelace", f"  {ADA}  "):
        assert cached_analysis(spelling, ttl_seconds=3600) == result, spelling


async def test_an_expired_analysis_is_not_served() -> None:
    result = await _analysis()
    store_analysis(result, settings=_settings())

    later = datetime.now(timezone.utc) + timedelta(seconds=3601)
    assert cached_analysis(ADA, ttl_seconds=3600, now=later) is None
    # A ttl of zero disables the read path rather than expiring everything at once.
    assert cached_analysis(ADA, ttl_seconds=0) is None


# --- retention ------------------------------------------------------------------


async def test_the_prune_deletes_runs_past_the_window_and_keeps_the_rest(
    engine: Engine, session: Session
) -> None:
    result = await _analysis()
    with engine.begin() as connection:
        connection.execute(insert(AnalysisRun).values(**_stale_run_row(40)))

    store_analysis(
        result,
        settings=_settings(analysis_run_prune_every=1, analysis_run_retention_days=30),
    )

    titles = list(session.execute(select(AnalysisRun.seed_title)).scalars())
    assert titles == [result.article.title], "the stale run survived the prune"


async def test_the_prune_does_not_run_on_a_write_below_its_threshold(
    engine: Engine, session: Session
) -> None:
    """`prune_every` defaults to 100, so a busy table must not pay for a count and a
    delete on every single request."""

    result = await _analysis()
    with engine.begin() as connection:
        connection.execute(insert(AnalysisRun).values(**_stale_run_row(40)))

    store_analysis(result, settings=_settings(analysis_run_retention_days=30))

    titles = sorted(session.execute(select(AnalysisRun.seed_title)).scalars())
    assert titles == sorted(["A run from 40 days ago", result.article.title])


# --- a failing write ------------------------------------------------------------


async def test_a_write_that_violates_a_constraint_is_swallowed_and_leaves_nothing(
    engine: Engine, session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """The invariant that makes persistence safe, executed rather than assumed.

    A database problem must never fail a request, so the failure is caught. What must not
    happen is the other half: catching it and leaving the transaction half-applied, or
    swallowing it silently enough that nobody ever learns the cache is dead.
    """

    result = await _analysis()
    # `articles.title` is UNIQUE and `_upsert_article` conflicts on `page_id`, so a
    # different page id already holding this title aborts the whole insert.
    with engine.begin() as connection:
        connection.execute(insert(Article).values(**_article_row(999, ADA)))

    with caplog.at_level(logging.ERROR, logger="app.db"):
        store_analysis(result, settings=_settings())

    assert session.execute(select(func.count()).select_from(Article)).scalar_one() == 1
    assert session.execute(select(func.count()).select_from(ArticleLink)).scalar_one() == 0
    assert session.execute(select(func.count()).select_from(AnalysisRun)).scalar_one() == 0
    assert "Database write failed" in caplog.text, (
        "a silently failed cache is the failure mode this whole module exists to prevent"
    )


# --- the schema the writes go into ----------------------------------------------


def test_every_column_the_models_declare_exists_in_the_database(engine: Engine) -> None:
    """`create_all()` only ever creates missing tables, never missing columns.

    A column added to `models.py` after the first deploy therefore reaches a brand new
    database and no existing one, and nothing reports the difference. This compares the
    declared columns against the live database rather than comparing two files of text.
    """

    for model in (Article, ArticleLink, AnalysisRun):
        declared = set(model.__table__.c.keys())
        present = _column_names(engine, model.__tablename__)
        assert declared <= present, (
            f"{model.__tablename__} is missing {sorted(declared - present)}"
        )


def test_applying_init_sql_upgrades_a_database_the_app_already_created(
    engine: Engine,
) -> None:
    """The upgrade path a deployed volume takes, which is the one path never tested.

    A database created by `create_all()` at 0.1.0 has no `analysis_payload` column and no
    `ix_article_links_missing` index. Re-applying `init.sql` is the only thing that brings
    it to the current schema, and it has to do that to tables that already hold rows.
    """

    sql = _INIT_SQL.read_text(encoding="utf-8")
    with engine.begin() as connection:
        # Establish the precondition rather than assume it: a database someone has already
        # applied `init.sql` to by hand would otherwise make this test pass for the wrong
        # reason.
        connection.execute(text("DROP INDEX IF EXISTS ix_article_links_missing"))
        connection.execute(text("ALTER TABLE articles DROP COLUMN IF EXISTS analysis_payload"))
        connection.execute(insert(Article).values(**_article_row(1, ADA)))
        connection.execute(
            insert(ArticleLink).values(
                source_page_id=1,
                target_title="London",
                target_normalized_title="London",
                target_page_id=3,
                exists=True,
            )
        )
    assert "ix_article_links_missing" not in _index_names(engine, "article_links")
    assert "analysis_payload" not in _column_names(engine, "articles")

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as raw:
        raw.exec_driver_sql(sql)

    assert "ix_article_links_missing" in _index_names(engine, "article_links")
    assert "analysis_payload" in _column_names(engine, "articles")
    # The statements ran against populated tables, so the rows that were there survived.
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(Article)).scalar_one() == 1
        assert (
            connection.execute(select(func.count()).select_from(ArticleLink)).scalar_one()
            == 1
        )

    # Idempotent: the file is `IF NOT EXISTS` throughout and contains no `DROP`, which is
    # the property docs/ROLLBACK.md section 1 depends on. Applying it twice changes nothing.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as raw:
        raw.exec_driver_sql(sql)

    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(Article)).scalar_one() == 1
        assert (
            connection.execute(select(func.count()).select_from(ArticleLink)).scalar_one()
            == 1
        )
