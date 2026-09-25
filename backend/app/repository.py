"""Optional persistence of analysis results.

Everything here is best effort. When no database is configured, or a write
fails, the API keeps working and simply does not cache the result.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import session_scope
from app.models import AnalysisRun, Article, ArticleLink
from app.schemas import AnalysisResult, ArticleDetail, ExtractedLink
from app.services.mediawiki import normalize_title

logger = logging.getLogger(__name__)


def store_analysis(result: AnalysisResult) -> None:
    """Cache the article, its outgoing links and the run summary."""

    article = result.article
    if article.page_id is None:
        return

    with session_scope() as session:
        if session is None:
            return

        row = _upsert_article(session, article)
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
        logger.info(
            "Stored analysis for %s: %s links, %s missing, %s one-way",
            row.title,
            result.summary.total_links,
            result.summary.total_missing,
            result.summary.total_one_way,
        )


def _upsert_article(session: Session, article: ArticleDetail) -> Article | None:
    values = {
        "page_id": article.page_id,
        "title": article.title,
        "normalized_title": normalize_title(article.title),
        "description": article.description,
        "extract": article.extract,
        "url": article.url,
        "length": article.length,
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
                "fetched_at",
            )
        },
    )
    session.execute(statement)
    return session.get(Article, article.page_id)


def _replace_links(
    session: Session, source_page_id: int, links: list[ExtractedLink]
) -> None:
    session.execute(
        delete(ArticleLink).where(ArticleLink.source_page_id == source_page_id)
    )
    rows = [
        {
            "source_page_id": source_page_id,
            "target_title": link.title,
            "target_normalized_title": normalize_title(link.title),
            "target_page_id": link.page_id,
            "exists": link.exists,
        }
        for link in links
    ]
    if rows:
        session.execute(pg_insert(ArticleLink).values(rows))


def recent_analyses(limit: int = 20) -> list[dict[str, object]]:
    """Latest analyses, newest first. Empty when persistence is disabled."""

    with session_scope() as session:
        if session is None:
            return []
        statement = (
            select(AnalysisRun)
            .order_by(AnalysisRun.created_at.desc())
            .limit(max(1, min(limit, 100)))
        )
        return [
            {
                "id": run.id,
                "seed_title": run.seed_title,
                "total_links": run.total_links,
                "total_missing": run.total_missing,
                "total_one_way": run.total_one_way,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
            for run in session.execute(statement).scalars()
        ]
