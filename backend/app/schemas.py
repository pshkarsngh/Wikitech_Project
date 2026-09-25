from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

EntityType = str
ConnectionStatus = str

# How an existence check classified one connection.
CONNECTION_EXISTS = "exists"
CONNECTION_MISSING = "missing"
ConnectionState = Literal["exists", "missing"]


class ExistenceMixin(BaseModel):
    """Classifies a connection as an existing article or a missing one.

    ``exists`` stays the single source of truth and ``state`` is derived from
    it, so the boolean and the classification can never disagree.
    """

    @computed_field  # type: ignore[prop-decorator]
    @property
    def state(self) -> ConnectionState:
        return CONNECTION_EXISTS if self.exists else CONNECTION_MISSING


class ArticleRef(BaseModel):
    page_id: int | None = None
    title: str
    url: str | None = None
    description: str | None = None


class ArticleDetail(ArticleRef):
    extract: str | None = None
    length: int | None = Field(
        default=None, description="Article size in bytes, as reported by MediaWiki"
    )
    exists: bool = True


class SearchResultItem(BaseModel):
    page_id: int | None = None
    title: str
    description: str | None = None
    wordcount: int | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]


class ArticleSearchResult(ArticleDetail):
    """One article matched from a name, with the page id, url and extract."""

    query: str


class ResolvedTitle(ExistenceMixin):
    """The result of an existence check for one title.

    ``redirected`` records that MediaWiki followed a redirect to reach the
    final article, which still counts as existing: the target is reachable, it
    just lives under a different name.
    """

    requested: str
    title: str | None = None
    page_id: int | None = None
    url: str | None = None
    exists: bool
    redirected: bool = False


class ExistsResponse(BaseModel):
    titles: list[ResolvedTitle]
    missing: list[str]


class ExtractedLink(ExistenceMixin):
    """One article link found inside an article.

    ``title`` is the link title, ``url`` its target, ``source_title`` /
    ``source_url`` the article it was found in, and ``is_internal`` says
    whether the target is an article on the same wiki. External websites,
    images, files, categories and other non-article resources are never
    extracted, so ``is_internal`` is true for every link in practice; it is
    carried explicitly so a consumer never has to re-derive it. ``state`` is
    the existence check: ``exists`` or ``missing``.
    """

    title: str
    page_id: int | None = None
    url: str | None = None
    exists: bool = True
    entity_type: EntityType = "other"
    source_title: str | None = None
    source_url: str | None = None
    is_internal: bool = True
    redirected: bool = False


class ArticleLinksResponse(BaseModel):
    article: ArticleRef
    total_links: int
    links: list[ExtractedLink]


class MissingConnection(ExistenceMixin):
    title: str
    entity_type: EntityType = "other"
    source_title: str
    source_url: str | None = None
    exists: bool = False


class OneWayConnection(BaseModel):
    source_title: str
    target_title: str
    target_page_id: int | None = None
    target_url: str | None = None
    links_back: bool = False


class AnalysisSummary(BaseModel):
    total_links: int = 0
    total_missing: int = 0
    total_one_way: int = 0
    one_way_targets_checked: int = 0
    one_way_truncated: bool = False


class AnalysisResult(BaseModel):
    article: ArticleDetail
    generated_at: datetime
    summary: AnalysisSummary
    missing_connections: list[MissingConnection]
    one_way_connections: list[OneWayConnection]
    links: list[ExtractedLink]


class MapNode(BaseModel):
    id: str
    label: str
    page_id: int | None = None
    url: str | None = None
    exists: bool = True
    entity_type: EntityType = "other"
    is_seed: bool = False


class MapEdge(BaseModel):
    id: str
    source: str
    target: str
    status: ConnectionStatus
    exists: bool = True


class ConnectionMap(BaseModel):
    article: ArticleRef
    generated_at: datetime
    nodes: list[MapNode]
    edges: list[MapEdge]
    truncated: bool = False


class HealthResponse(BaseModel):
    status: str
    version: str
    database_enabled: bool
