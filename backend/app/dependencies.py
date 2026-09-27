"""Shared FastAPI dependencies."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, Request, status
from pydantic import StringConstraints

from app.config import Settings
from app.services.budget import AnalysisBudget, budget_scope
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


async def analysis_budget_scope(
    request: Request, settings: SettingsDep
) -> AsyncIterator[None]:
    """Give this request a deadline, and take it away again when the request ends.

    A dependency rather than a line in each handler, for the same reason
    ``require_analysis_key`` is one: the budget has to be in place before the
    first call to Wikimedia, and a handler that forgot to set one up would then
    run unbounded. Anything that reaches the client gets the budget on the way.

    The yield matters twice over. It installs the budget for the endpoint that
    follows, and the teardown below runs after the response, so the deadline
    covers the work rather than stopping the moment the route is entered.

    ``request.is_disconnected`` is passed as a callable instead of being called
    here, because a disconnect can only be observed from inside the event loop
    while a request is actually in flight, and because the budget module must not
    know that a `Request` exists.
    """

    budget = AnalysisBudget(
        deadline_seconds=settings.analysis_deadline_seconds,
        is_disconnected=request.is_disconnected,
    )
    with budget_scope(budget):
        yield


BudgetDep = Annotated[None, Depends(analysis_budget_scope)]

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

# A budget is only installed on the routes that crawl. The read routes are a single
# MediaWiki request each and are already bounded by `http_timeout_seconds`, so a
# deadline there would only add a way to fail a request that was going to answer.
# The four routes that build a graph are the ones with no natural wall-clock bound.
#
# Deliberately not combined into the `SettingsDep` path. `get_settings_dep` runs for
# every route including `/api/health`, and an unrequested budget that silently
# installed itself would make a route's time behaviour depend on which dependencies
# it happens to declare.

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
