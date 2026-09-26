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

from app.repository import _link_rows
from app.schemas import ExtractedLink


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
