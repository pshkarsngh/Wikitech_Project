"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query, Request
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
