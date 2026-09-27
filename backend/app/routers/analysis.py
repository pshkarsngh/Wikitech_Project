"""Article analysis: missing connections, one-way connections, connection map."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app import repository
from app.dependencies import (
    AnalysisKeyDep,
    BudgetDep,
    ClientDep,
    SettingsDep,
    TitleQuery,
)
from app.schemas import AnalysisResult, ConnectionMap, MissingConnection, OneWayConnection
from app.services import classifier
from app.services.analysis import (
    analyze_article,
    build_connection_map,
    build_link_graph,
    classify_links,
    detect_one_way_connections,
)
from app.services.budget import AnalysisAborted
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


def _aborted_error(exc: AnalysisAborted) -> HTTPException:
    """Turn "we did not finish" into a gateway timeout.

    Deliberately 504 and not 200 with an empty list. Every route this serves
    returns a list, and a list that was cut short is indistinguishable from a
    complete answer once it has left the building: a client that reached zero
    missing connections by running out of time has been told a false thing, and
    nothing in the payload says otherwise. There is no body field to mark it
    here the way there is in the `/analyze` summary, so the request has to fail
    instead of answering.

    The detail is generic. A disconnect is not a failure worth reporting to a
    client that has already gone, and the deadline is a property of this
    deployment's settings rather than anything the caller did.
    """

    return HTTPException(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        detail="The analysis did not finish in time. Try again, or a smaller article.",
    )


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(
    _key: AnalysisKeyDep,
    _budget: BudgetDep,
    client: ClientDep,
    settings: SettingsDep,
    response: Response,
    payload: AnalyzeRequest,
) -> AnalysisResult:
    """Full analysis for one article: links, missing and one-way connections.

    Served from the cache when a recent one exists. An analysis of a real article costs
    25-35 calls to Wikimedia, and that budget is per deployment and shared by every user
    (docs/ARCHITECTURE.md section 12), so recomputing an answer that was computed an hour
    ago spends someone else's quota to return the same bytes. ``X-Cache`` says which path
    answered, because a silently cached result is indistinguishable from a fresh one.

    Gated by the shared key, because it is the route that costs the most: it crawls, it
    classifies, and it writes.

    Answers in one of three ways, and the difference matters to whoever reads the
    payload. A deadline after the link graph is complete returns the article's real
    links and missing connections with ``summary.aborted`` set, because the reader
    still gets the part that is evidence. A deadline before that, or a client that has
    disconnected, is a 504, because there is no partial answer to be honest about.
    """

    cached = repository.cached_analysis(
        payload.title, ttl_seconds=settings.analysis_cache_ttl_seconds
    )
    if cached is not None:
        response.headers["X-Cache"] = "hit"
        return cached

    try:
        result = await analyze_article(client, settings, payload.title)
    except AnalysisAborted as exc:
        raise _aborted_error(exc) from exc
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    response.headers["X-Cache"] = "miss"
    # An aborted result is deliberately not cached. It is a subset of the answer,
    # and storing it under the article's own key would serve that subset to whoever
    # asks next, for the whole TTL, with nothing in the payload to explain why.
    # The cost of recomputing is the price of not caching a partial answer.
    if not result.summary.aborted:
        repository.store_analysis(result, settings=settings)
    return result


@router.get("/connections/missing", response_model=list[MissingConnection])
async def missing_connections(
    _key: AnalysisKeyDep,
    _budget: BudgetDep,
    client: ClientDep,
    settings: SettingsDep,
    title: TitleQuery,
) -> list[MissingConnection]:
    """Missing connection detection.

    People and places that are mentioned in the article but have no article of
    their own yet.
    """

    # The whole body is inside the try, not just the graph build. The later stages
    # call Wikimedia too, and an unhandled `WikipediaError` from one of them is a
    # 500 that blames this app for an upstream failure it translates as a 502.
    try:
        graph = await build_link_graph(client, settings, title)
        # `classify_links` already types the missing names as part of classifying
        # every link, so the missing connections are read back out of that instead
        # of being classified a second time. This route is the reason the duplicate
        # existed: it needs types for the missing list and nothing else.
        types, _, _ = await classify_links(client, settings, graph)
    except AnalysisAborted as exc:
        raise _aborted_error(exc) from exc
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    return [
        MissingConnection(
            title=item.requested,
            entity_type=types.get(item.requested, classifier.OTHER),
            source_title=graph.title,
            source_url=graph.url,
        )
        for item in graph.missing
    ]


@router.get("/connections/one-way", response_model=list[OneWayConnection])
async def one_way_connections(
    _key: AnalysisKeyDep,
    _budget: BudgetDep,
    client: ClientDep,
    settings: SettingsDep,
    title: TitleQuery,
) -> list[OneWayConnection]:
    """One-way connection detection.

    Articles linked from the seed article that do not link back to it.
    """

    try:
        graph = await build_link_graph(client, settings, title)
        result = await detect_one_way_connections(client, settings, graph)
    except AnalysisAborted as exc:
        raise _aborted_error(exc) from exc
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    return result.connections


@router.get("/connections/map", response_model=ConnectionMap)
async def connection_map(
    _key: AnalysisKeyDep,
    _budget: BudgetDep,
    client: ClientDep,
    settings: SettingsDep,
    title: TitleQuery,
) -> ConnectionMap:
    """Connection map generation: nodes and edges ready for Cytoscape.js.

    Gated, because it crawls the same graph as `/analyze` and then classifies it, which is
    the single most expensive request this app makes.
    """

    try:
        graph = await build_link_graph(client, settings, title)
        # classify_links covers both existing and missing nodes so that
        # person / place entity types are attached to every map node, and it
        # classifies the missing names on the way through. The missing list is
        # therefore assembled from those types below rather than by calling
        # `detect_missing_connections`, which would classify the same names
        # again - one Wikidata request per missing name, the most expensive
        # thing this app can waste.
        types, _, _ = await classify_links(client, settings, graph)
        one_way = await detect_one_way_connections(client, settings, graph)
    except AnalysisAborted as exc:
        raise _aborted_error(exc) from exc
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    missing = [
        MissingConnection(
            title=item.requested,
            entity_type=types.get(item.requested, classifier.OTHER),
            source_title=graph.title,
            source_url=graph.url,
        )
        for item in graph.missing
    ]
    return build_connection_map(graph, missing, one_way, types, settings)



