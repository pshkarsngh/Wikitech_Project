"""Article analysis: missing connections, one-way connections, connection map."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app import repository
from app.dependencies import ClientDep, SettingsDep, TitleQuery
from app.schemas import AnalysisResult, ConnectionMap, MissingConnection, OneWayConnection
from app.services.analysis import (
    analyze_article,
    build_connection_map,
    build_link_graph,
    detect_missing_connections,
    detect_one_way_connections,
)
from app.services.mediawiki import ArticleNotFoundError, WikipediaError

router = APIRouter(tags=["analysis"])


class AnalyzeRequest(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=512,
        description="Wikipedia article title to analyse",
        examples=["Ada Lovelace"],
    )


def _upstream_error(exc: WikipediaError) -> HTTPException:
    if isinstance(exc, ArticleNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Wikipedia request failed: {exc}",
    )


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(
    client: ClientDep, settings: SettingsDep, payload: AnalyzeRequest
) -> AnalysisResult:
    """Full analysis for one article: links, missing and one-way connections."""

    try:
        result = await analyze_article(client, settings, payload.title)
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    repository.store_analysis(result)
    return result


@router.get("/connections/missing", response_model=list[MissingConnection])
async def missing_connections(
    client: ClientDep, settings: SettingsDep, title: TitleQuery
) -> list[MissingConnection]:
    """Missing connection detection.

    People and places that are mentioned in the article but have no article of
    their own yet.
    """

    try:
        graph = await build_link_graph(client, settings, title)
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    connections, _ = await detect_missing_connections(client, settings, graph)
    return connections


@router.get("/connections/one-way", response_model=list[OneWayConnection])
async def one_way_connections(
    client: ClientDep, settings: SettingsDep, title: TitleQuery
) -> list[OneWayConnection]:
    """One-way connection detection.

    Articles linked from the seed article that do not link back to it.
    """

    try:
        graph = await build_link_graph(client, settings, title)
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    result = await detect_one_way_connections(client, settings, graph)
    return result.connections


@router.get("/connections/map", response_model=ConnectionMap)
async def connection_map(
    client: ClientDep, settings: SettingsDep, title: TitleQuery
) -> ConnectionMap:
    """Connection map generation: nodes and edges ready for Cytoscape.js."""

    try:
        graph = await build_link_graph(client, settings, title)
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    missing, types = await detect_missing_connections(client, settings, graph)
    one_way = await detect_one_way_connections(client, settings, graph)
    return build_connection_map(graph, missing, one_way, types, settings)


@router.get("/analyses/recent")
async def recent_analyses(limit: int = Query(20, ge=1, le=100)) -> list[dict[str, object]]:
    """Recently stored analyses. Requires a configured database."""

    return repository.recent_analyses(limit=limit)
