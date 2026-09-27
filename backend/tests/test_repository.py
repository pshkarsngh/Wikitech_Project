"""Guards the rows `store_analysis` writes, because a violation fails silently.

Persistence is best effort by design: `db.session_scope` and `store_analysis` both
swallow a database failure so a request can still be answered from Wikipedia. That is
the right call, and it has a sharp edge - a write that fails every time is
indistinguishable from a write that was never attempted. `/api/health` reports
`database_enabled` from a lazily constructed `Engine`, so it says `true` whether or not
a single row has ever landed.

That is not hypothetical. Every real article tried at least one analysis hit the same
article through two different link targets - one canonical, one a redirect - so
`uq_link` rejected the insert, the transaction rolled back whole, and nothing was ever
cached. These tests pin the shape of the rows so that failure cannot return unnoticed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.models import Article
from app.repository import (
    _payload_json,
    _should_prune,
    _link_rows,
    cached_analysis,
    is_fresh,
    prune_statement,
    retention_cutoff,
)
from app.schemas import AnalysisResult, ExtractedLink


def _link(
    title: str, *, page_id: int | None, exists: bool, redirected: bool = False
) -> ExtractedLink:
    return ExtractedLink(
        title=title,
        page_id=page_id,
        url=(
            f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}" if exists else None
        ),
        exists=exists,
        entity_type="other",
        source_title="Ada Lovelace",
        source_url="https://en.wikipedia.org/wiki/Ada_Lovelace",
        is_internal=True,
        redirected=redirected,
    )


def test_a_target_reached_by_two_link_targets_is_stored_once() -> None:
    """The bug: a canonical link and a redirect to it resolve to the same row key.

    `Ada Lovelace` links both `Allan G. Bromley` and a title that redirects there, so
    `resolve_titles` returns the same page_id and the same canonical title twice. With
    both rows inserted, `uq_link` (source_page_id, target_normalized_title) rejects the
    statement and the whole transaction is lost.
    """

    rows = _link_rows(
        1,
        [
            _link("Allan G. Bromley", page_id=4341343, exists=True),
            _link("Allan G. Bromley", page_id=4341343, exists=True, redirected=True),
        ],
    )

    assert len(rows) == 1, "the duplicate must collapse or the insert aborts the transaction"
    assert rows[0] == {
        "source_page_id": 1,
        "target_title": "Allan G. Bromley",
        # `normalize_title` is what the column stores, and it preserves case - the
        # dedupe key has to be the constraint's key, not a stricter one.
        "target_normalized_title": "Allan G. Bromley",
        "target_page_id": 4341343,
        "exists": True,
    }


def test_the_stored_target_key_is_always_unique_per_source() -> None:
    """The property `uq_link` enforces, asserted directly rather than hoped for."""

    rows = _link_rows(
        1,
        [
            _link("Allan G. Bromley", page_id=4341343, exists=True),
            _link("Allan G. Bromley", page_id=4341343, exists=True, redirected=True),
            _link("Ada  Lovelace", page_id=1, exists=True),
            _link("Ada Lovelace", page_id=1, exists=True),
            _link("Somerton, Malta", page_id=None, exists=False),
        ],
    )

    keys = [(row["source_page_id"], row["target_normalized_title"]) for row in rows]
    assert len(keys) == len(set(keys)), f"these rows would violate uq_link: {keys}"


def test_collapsing_a_duplicate_does_not_drop_a_distinct_link() -> None:
    rows = _link_rows(
        1,
        [
            _link("Allan G. Bromley", page_id=4341343, exists=True),
            _link("Allan G. Bromley", page_id=4341343, exists=True, redirected=True),
            _link("Somerton, Malta", page_id=None, exists=False),
        ],
    )

    assert [row["target_title"] for row in rows] == [
        "Allan G. Bromley",
        "Somerton, Malta",
    ]


def test_underscore_and_space_spellings_collapse_too() -> None:
    """`normalize_title` turns underscores into spaces, so both spellings are one row."""

    rows = _link_rows(
        1,
        [
            _link("Ada Lovelace", page_id=1, exists=True),
            _link("Ada_Lovelace", page_id=1, exists=True),
        ],
    )

    assert len(rows) == 1, "underscore and space spellings are the same target"


def test_a_missing_link_is_stored_with_no_page_id() -> None:
    assert _link_rows(1, [_link("Gauri Shankar Temple", page_id=None, exists=False)]) == [
        {
            "source_page_id": 1,
            "target_title": "Gauri Shankar Temple",
            "target_normalized_title": "Gauri Shankar Temple",
            "target_page_id": None,
            "exists": False,
        }
    ]


def test_the_row_order_matches_the_link_order() -> None:
    """The map and the connection lists are built from the payload, not from this."""

    rows = _link_rows(
        1,
        [
            _link("London", page_id=3, exists=True),
            _link("Somerton, Malta", page_id=None, exists=False),
            _link("London", page_id=3, exists=True),
        ],
    )

    assert [row["target_title"] for row in rows] == ["London", "Somerton, Malta"]


def test_an_article_with_no_links_produces_no_rows() -> None:
    assert _link_rows(1, []) == []


def test_two_sources_may_link_the_same_target() -> None:
    """`uq_link` is per source, so the same target under a different source is fine."""

    assert len(_link_rows(1, [_link("London", page_id=3, exists=True)])) == 1
    assert len(_link_rows(2, [_link("London", page_id=3, exists=True)])) == 1


# --- retention ---------------------------------------------------------------
# `analysis_runs` is the one table here that no natural bound applies to. `articles` and
# `article_links` are capped by the size of Wikipedia; this grows with request volume, and
# `POST /api/analyze` inserts a row on every call with nothing deleting them. Left alone it
# is a slow, boring disk-exhaustion failure.
#
# There is no database in this suite - every fixture runs with an empty DATABASE_URL - so
# what is asserted here is the cutoff arithmetic, the amortisation decision, and the SQL
# that gets sent. The execution itself is not covered, and that is a known gap rather than
# an oversight: see docs/PUBLIC-READINESS.md B6.

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def test_the_cutoff_is_the_configured_window_ago() -> None:
    assert retention_cutoff(NOW, days=30) == NOW - timedelta(days=30)
    assert retention_cutoff(NOW, days=1) == NOW - timedelta(days=1)


def test_retention_of_zero_days_is_rejected_rather_than_pruning_everything() -> None:
    # A misconfigured 0 must not become "delete all history on the next write".
    with pytest.raises(ValueError):
        retention_cutoff(NOW, days=0)
    with pytest.raises(ValueError):
        retention_cutoff(NOW, days=-1)


def test_the_prune_only_deletes_runs_older_than_the_cutoff() -> None:
    cutoff = NOW - timedelta(days=30)
    sql = str(
        prune_statement(cutoff).compile(
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "DELETE FROM analysis_runs" in sql
    # Strictly older than, not at-or-before: a run exactly on the boundary is kept.
    assert "created_at <" in sql
    assert "2026-08-28" in sql
    # It must not touch the two tables that are the actual cache.
    assert "article_links" not in sql
    assert "DELETE FROM articles" not in sql


def test_the_prune_is_amortised_rather_than_running_on_every_write() -> None:
    settings = Settings()
    every = settings.analysis_run_prune_every

    assert every > 0
    # Below the threshold nothing happens, so a busy table does not pay for a count and a
    # delete on every single request.
    assert not _should_prune(0, every=every)
    assert not _should_prune(every - 1, every=every)
    assert _should_prune(every, every=every)
    assert _should_prune(every * 10, every=every)


def test_the_prune_can_be_switched_off_without_breaking_writes() -> None:
    assert not _should_prune(10_000, every=0)
    assert not _should_prune(10_000, every=-1)


# --- the read path ------------------------------------------------------------
# `articles.analysis_payload` holds a whole computed answer so a repeat request does not
# spend 25-35 Wikimedia calls to reproduce it. The query cannot be exercised here - there
# is no database in this suite - but the two things that decide whether the cache is
# *correct* rather than merely present can be: the freshness policy, and whether the
# serialised payload comes back as the identical object.


def test_a_recent_analysis_is_fresh() -> None:
    now = NOW
    assert is_fresh(now - timedelta(seconds=10), now=now, ttl_seconds=3600)
    assert is_fresh(now, now=now, ttl_seconds=3600)


def test_an_old_analysis_is_not_fresh() -> None:
    now = NOW
    assert not is_fresh(now - timedelta(seconds=3601), now=now, ttl_seconds=3600)
    # Exactly on the boundary counts as stale, so a ttl is an upper bound and not a hint.
    assert not is_fresh(now - timedelta(seconds=3600), now=now, ttl_seconds=3600)


def test_a_missing_timestamp_is_stale_rather_than_fresh() -> None:
    # Assuming fresh on a value nobody can date is how a cache ends up serving something
    # of unknown age with no way to tell.
    assert not is_fresh(None, now=NOW, ttl_seconds=3600)


def test_a_naive_timestamp_is_read_as_utc_rather_than_crashing() -> None:
    # Postgres can hand back a naive datetime for a timestamptz, and comparing that to an
    # aware one raises instead of answering.
    naive = (NOW - timedelta(minutes=5)).replace(tzinfo=None)
    assert is_fresh(naive, now=NOW, ttl_seconds=3600)


def test_a_ttl_of_zero_disables_the_read_path() -> None:
    assert not is_fresh(NOW, now=NOW, ttl_seconds=0)
    # And the lookup short-circuits before it would open a session at all.
    assert cached_analysis("Ada Lovelace", ttl_seconds=0) is None


def test_the_cache_misses_when_no_database_is_configured() -> None:
    # The suite runs with an empty DATABASE_URL, so this is the real "no cache" path and
    # it has to return None rather than raise. A cache that raises is a cache that breaks
    # requests.
    assert cached_analysis("Ada Lovelace", ttl_seconds=3600) is None
    assert cached_analysis("", ttl_seconds=3600) is None
    assert cached_analysis("   ", ttl_seconds=3600) is None


async def test_a_serialised_analysis_comes_back_as_the_identical_object() -> None:
    from app.services.analysis import analyze_article
    from tests.fake_wikipedia import ADA, FakeWikipediaClient

    original = await analyze_article(FakeWikipediaClient(), Settings(database_url=""), ADA)

    restored = AnalysisResult.model_validate_json(_payload_json(original))

    assert restored == original
    # Compared field by field as well, so a future field that silently fails to survive
    # the round trip is named rather than hidden inside an equality check.
    assert restored.article == original.article
    assert restored.summary == original.summary
    assert restored.links == original.links
    assert restored.missing_connections == original.missing_connections
    assert restored.one_way_connections == original.one_way_connections
    assert restored.generated_at == original.generated_at


async def test_the_cached_payload_preserves_the_fields_a_rebuilt_one_would_lose() -> None:
    """Why the payload is cached whole rather than re-derived from `article_links`.

    `article_links` stores the *resolved* target title. The requested one is what
    distinguishes a direct link from a redirect, and `redirected` only exists on the
    response. Re-deriving would change the answer, so the whole answer is stored instead.
    """

    from app.services.analysis import analyze_article
    from tests.fake_wikipedia import ADA, FakeWikipediaClient

    original = await analyze_article(FakeWikipediaClient(), Settings(database_url=""), ADA)
    restored = AnalysisResult.model_validate_json(_payload_json(original))

    assert restored.links == original.links
    assert [link.state for link in restored.links] == [link.state for link in original.links]
    assert [link.source_title for link in restored.links] == [
        link.source_title for link in original.links
    ]
    assert restored.summary.one_way_incomplete == original.summary.one_way_incomplete


def test_the_payload_column_is_nullable_so_a_cache_miss_is_representable() -> None:
    # A NOT NULL payload column would make the first write of an article fail, because
    # `_upsert_article` runs before the payload exists on the very first pass.
    assert Article.__table__.c.analysis_payload.nullable is True

