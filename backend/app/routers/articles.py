"""Article retrieval, link extraction and article existence checking."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import ClientDep, SearchQuery, SettingsDep, TitleQuery
from app.schemas import (
    ArticleDetail,
    ArticleLinksResponse,
    ArticleSearchResult,
    ExistsResponse,
    ResolvedTitle,
    SearchResponse,
)
from app.services.analysis import build_extracted_links, build_link_graph, classify_links
from app.services.mediawiki import ArticleNotFoundError, WikipediaError

router = APIRouter(tags=["articles"])


def _upstream_error(exc: WikipediaError) -> HTTPException:
    if isinstance(exc, ArticleNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Wikipedia request failed: {exc}",
    )


@router.get("/articles/search", response_model=SearchResponse)
async def search_articles(
    client: ClientDep,
    q: str = Query(
        min_length=1,
        max_length=256,
        description="Full text search over English Wikipedia",
        examples=["ada lovelace"],
    ),
    limit: int = Query(10, ge=1, le=50),
) -> SearchResponse:
    """Search articles by name or keyword."""

    try:
        results = await client.search_articles(q, limit=limit)
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc
    return SearchResponse(query=q, results=results)


@router.get("/articles/find", response_model=ArticleSearchResult)
async def find_article(client: ClientDep, q: SearchQuery) -> ArticleSearchResult:
    """Resolve an article name to one article: title, url, extract and page id."""

    try:
        article = await client.find_article(q)
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    return ArticleSearchResult(**article.model_dump(), query=q)


@router.get("/article", response_model=ArticleDetail)
async def get_article(client: ClientDep, title: TitleQuery) -> ArticleDetail:
    """Article retrieval: metadata plus the lead section."""

    try:
        return await client.get_article(title)
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc


@router.get("/article/links", response_model=ArticleLinksResponse)
async def get_article_links(
    client: ClientDep, settings: SettingsDep, title: TitleQuery
) -> ArticleLinksResponse:
    """Article link extraction.

    Returns every link inside the article with its title, target, source
    article and whether it is an internal article link, annotated with
    existence and a person/place guess. External websites, images, files,
    categories, navigation and other non-article resources are excluded.
    """

    try:
        graph = await build_link_graph(client, settings, title)
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    types, _described, _truncated = await classify_links(client, settings, graph)
    links = build_extracted_links(graph, types)

    return ArticleLinksResponse(
        article={
            "page_id": graph.page_id,
            "title": graph.title,
            "url": graph.url,
        },
        total_links=graph.total_links,
        links=links,
    )


@router.get("/articles/resolve", response_model=ExistsResponse)
async def check_articles_exist(
    client: ClientDep,
    titles: list[str] = Query(
        min_length=1,
        max_length=50,
        description="Up to 50 article titles, reported as existing or missing",
        examples=["Ada Lovelace", "Ada Lovelaces husband"],
    ),
) -> ExistsResponse:
    """Article existence checking. A redirect counts as existing."""

    try:
        resolved: list[ResolvedTitle] = await client.resolve_titles(titles)
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    return ExistsResponse(
        titles=resolved,
        missing=[item.requested for item in resolved if not item.exists],
    )
