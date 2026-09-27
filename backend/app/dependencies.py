"""Shared FastAPI dependencies."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, Request, status
from pydantic import StringConstraints

from app.config import Settings
from app.services.mediawiki import MediaWikiClient


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_client(request: Request) -> MediaWikiClient:
    return request.app.state.wikipedia


TitleQuery = Annotated[
    str,
    Query(
        min_length=1,
        max_length=512,
        description="Wikipedia article title",
        examples=["Ada Lovelace"],
    ),
]

ClientDep = Annotated[MediaWikiClient, Depends(get_client)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]

# The key for the routes that crawl Wikipedia, read from the header rather than a query
# parameter so it does not land in nginx access logs, browser history or `Referer`.
ApiKeyHeader = Annotated[
    str | None,
    Header(
        alias="X-Api-Key",
        description="Shared analysis key, required when ANALYSIS_API_KEY is set",
    ),
]


def require_analysis_key(settings: SettingsDep, presented: ApiKeyHeader = None) -> None:
    """Refuse a request that cannot pay for a crawl, when a key is configured.

    Returns nothing on success, so a route declares the gate with a bare parameter and
    gets no value to thread through. An unset key means the deployment has chosen to be
    open, which is the same default as an unset database: the app runs, and reports that
    it is open in `/api/health`.

    The `= None` in the signature is load-bearing in two ways. FastAPI rejects a default
    written inside `Header()` when the annotation is an `Annotated`, and Pydantic v2
    treats a `Header()` with no default at all as *required* - so a missing header would
    answer 422 "Field required" instead of reaching the check below. It also has to sit
    last, because a parameter with a default cannot precede one without.
    """

    expected = settings.analysis_api_key.strip()
    if not expected:
        return

    # A missing header must not become the empty string and then be compared, or a
    # deployment whose key happens to be empty would be open. The empty case is refused
    # explicitly, before the compare.
    if not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This analysis key is required.",
        )

    # `compare_digest` rather than `==`: a plain comparison returns as soon as it finds a
    # differing byte, so the time it takes leaks how much of the key was correct. It also
    # only accepts ASCII, hence the encode.
    if not secrets.compare_digest(presented.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That analysis key is not correct.",
        )


AnalysisKeyDep = Annotated[None, Depends(require_analysis_key)]

# Whitespace is stripped before the length check, so " " is rejected like "".
SearchQuery = Annotated[
    str,
    Query(
        min_length=1,
        max_length=256,
        description="Article name to look up",
        examples=["Ada Lovelace"],
    ),
    StringConstraints(strip_whitespace=True, min_length=1),
]

# A batch of titles to resolve. The list itself is bounded, and so is each element:
# `Query(max_length=...)` on a `list[str]` constrains how many there are and does nothing
# about how long each one is, so without this a caller could send 50 megabyte titles and
# have every one of them forwarded to MediaWiki in a single `titles=` parameter.
BatchedTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]

TitlesQuery = Annotated[
    list[BatchedTitle],
    Query(
        min_length=1,
        max_length=50,
        description="Up to 50 article titles, reported as existing or missing",
        examples=["Ada Lovelace", "Ada Lovelaces husband"],
    ),
]
