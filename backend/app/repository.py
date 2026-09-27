"""Optional persistence of analysis results.

Everything here is best effort. When no database is configured, or a write fails, the API
keeps working and simply does not cache the result.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import Delete, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import session_scope
from app.models import AnalysisRun, Article, ArticleLink
from app.schemas import AnalysisResult, ArticleDetail, ExtractedLink
from app.services.mediawiki import normalize_title, title_key

logger = logging.getLogger(__name__)


def retention_cutoff(now: datetime, *, days: int) -> datetime:
    """Runs older than this are no longer kept.

    Age rather than a row count, because the count needs a ``SELECT count(*)`` on every
    write to be a real bound and the age does not: the table's growth rate is the request
    rate, and that is already capped by the nginx limiter in front of the app and by
    Wikimedia's published ceiling behind it. ``ix_analysis_runs_created_at`` covers this
    delete, so it stays an index range scan rather than a sequential one.
    """

    if days <= 0:
        raise ValueError("analysis_run_retention_days must be greater than 0")
    return now - timedelta(days=days)


def prune_statement(cutoff: datetime) -> Delete:
    """The delete itself, built without touching a connection.

    Split out from the execute so the statement can be compiled and asserted in a test.
    There is no database in the test suite - every fixture runs with an empty
    ``DATABASE_URL`` - so this is the only layer of the prune that can be checked here.
    """

    return delete(AnalysisRun).where(AnalysisRun.created_at < cutoff)


def _should_prune(runs_since_last_prune: int, *, every: int) -> bool:
    if every <= 0:
        return False
    return runs_since_last_prune >= every


def is_fresh(fetched_at: datetime | None, *, now: datetime, ttl_seconds: int) -> bool:
    """Whether a stored analysis is still recent enough to serve.

    Split out as a pure function because the whole freshness policy is here and nothing
    else is: no database in this suite means the query cannot be exercised, but this can.

    A missing or unreadable timestamp is treated as stale. Assuming fresh on a missing
    value is how a cache silently serves something nobody knows the age of.
    """

    if fetched_at is None or ttl_seconds <= 0:
        return False
    if fetched_at.tzinfo is None:
        # Postgres hands back a naive datetime for a timestamptz when the driver is not
        # told otherwise, and comparing the two raises rather than answering.
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return (now - fetched_at).total_seconds() < ttl_seconds


def _payload_json(result: AnalysisResult) -> str:
    return result.model_dump_json()


def cached_analysis(
    title: str, *, ttl_seconds: int, now: datetime | None = None
) -> AnalysisResult | None:
    """A previously computed analysis for this article, if it is still fresh.

    Returns ``None`` on a miss, on a stale entry, or on any database problem. A cache that
    raises is a cache that breaks requests, and persistence is best effort everywhere else
    in this module for the same reason.
    """

    key = title_key(title)
    if not key or ttl_seconds <= 0:
        return None

    moment = now or datetime.now(timezone.utc)
    try:
        with session_scope(read_only=True) as session:
            if session is None:
                return None
            row = session.execute(
                select(Article.analysis_payload, Article.fetched_at).where(
                    Article.normalized_title == key
                )
            ).first()
    except Exception:  # noqa: BLE001 - a cache miss must never fail a request
        logger.warning("Could not read the analysis cache", exc_info=True)
        return None

    if row is None or not row.analysis_payload:
        return None
    if not is_fresh(row.fetched_at, now=moment, ttl_seconds=ttl_seconds):
        return None

    try:
        return AnalysisResult.model_validate_json(row.analysis_payload)
    except Exception:  # noqa: BLE001 - a corrupt payload is a miss, not a failure
        logger.warning(
            "Discarding an unreadable cached analysis for %s", title, exc_info=True
        )
        return None


def store_analysis(result: AnalysisResult, *, settings: Settings | None = None) -> None:
    """Cache the article, its outgoing links and the run summary.

    ``settings`` is optional so an embedder or a test can call this without one; without
    it the retention prune simply does not run, which is a table that grows rather than a
    write that fails.
    """

    article = result.article
    if article.page_id is None:
        return

    with session_scope() as session:
        if session is None:
            return

        row = _upsert_article(session, article, payload=_payload_json(result))
        if row is None:
            return

        _replace_links(session, row.page_id, result.links)
        session.add(
            AnalysisRun(
                seed_page_id=row.page_id,
                seed_title=row.title,
                total_links=result.summary.total_links,
                total_missing=result.summary.total_missing,
                total_one_way=result.summary.total_one_way,
            )
        )
        if settings is not None:
            _prune_old_runs(session, settings)
        logger.info(
            "Stored analysis for %s: %s links, %s missing, %s one-way",
            row.title,
            result.summary.total_links,
            result.summary.total_missing,
            result.summary.total_one_way,
        )


def _prune_old_runs(session: Session, settings: Settings) -> None:
    """Delete runs past the retention window, at most once per `prune_every` writes.

    Deliberately best effort: if the prune fails, the write still lands and the table keeps
    a few more rows than it should. Losing an analysis row is a smaller problem than losing
    the analysis, so this never propagates.
    """

    every = settings.analysis_run_prune_every
    if every <= 0:
        return

    try:
        stored = session.scalar(select(func.count()).select_from(AnalysisRun))
    except Exception:  # noqa: BLE001 - retention must never fail a write
        logger.warning("Could not count analysis runs, skipping retention", exc_info=True)
        return

    if not stored or not _should_prune(int(stored), every=every):
        return

    try:
        cutoff = retention_cutoff(
            datetime.now(timezone.utc), days=settings.analysis_run_retention_days
        )
        deleted = session.execute(prune_statement(cutoff)).rowcount
    except Exception:  # noqa: BLE001 - retention must never fail a write
        logger.warning("Could not prune old analysis runs", exc_info=True)
        return

    if deleted:
        logger.info("Pruned %s analysis runs older than %s", deleted, cutoff)


def _upsert_article(
    session: Session, article: ArticleDetail, *, payload: str | None = None
) -> Article | None:
    values = {
        "page_id": article.page_id,
        "title": article.title,
        # The lookup key, not the display title. `cached_analysis` searches this column
        # with `title_key`, and PostgreSQL compares VARCHAR case-sensitively, so storing
        # the display spelling here means the read path never matches its own write.
        # `database/init.sql` says the same thing: its example query compares this column
        # to `lower('ada lovelace')`.
        "normalized_title": title_key(article.title),
        "description": article.description,
        "extract": article.extract,
        "url": article.url,
        "length": article.length,
        "analysis_payload": payload,
        "fetched_at": datetime.now(timezone.utc),
    }
    statement = pg_insert(Article).values(**values)
    statement = statement.on_conflict_do_update(
        index_elements=[Article.page_id],
        set_={
            column: statement.excluded[column]
            for column in (
                "title",
                "normalized_title",
                "description",
                "extract",
                "url",
                "length",
                "analysis_payload",
                "fetched_at",
            )
        },
    )
    session.execute(statement)
    return session.get(Article, article.page_id)



def _link_rows(source_page_id: int, links: list[ExtractedLink]) -> list[dict[str, object]]:
    """One row per (source, target), which is what `uq_link` allows.

    Two link occurrences in the article can resolve to the same article - one links the
    canonical title directly, the other reaches it through a redirect, so
    `resolve_titles` hands back the same page_id and the same canonical title twice.
    `uq_link` is (source_page_id, target_normalized_title), so passing both through
    aborts the whole transaction and the analysis is silently not cached at all. The
    duplicates carry identical data, so keeping the first loses nothing.
    """

    rows: dict[str, dict[str, object]] = {}
    for link in links:
        key = normalize_title(link.title)
        rows.setdefault(
            key,
            {
                "source_page_id": source_page_id,
                "target_title": link.title,
                "target_normalized_title": key,
                "target_page_id": link.page_id,
                "exists": link.exists,
            },
        )
    return list(rows.values())


def _replace_links(
    session: Session, source_page_id: int, links: list[ExtractedLink]
) -> None:
    session.execute(
        delete(ArticleLink).where(ArticleLink.source_page_id == source_page_id)
    )
    rows = _link_rows(source_page_id, links)
    if rows:
        session.execute(pg_insert(ArticleLink).values(rows))



