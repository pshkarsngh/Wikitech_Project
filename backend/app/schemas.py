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
    # Link targets found in the wikitext, counted as written and before redirects
    # are followed, so two spellings of one redirect both count. `total_articles`
    # is the same set after resolution, keyed by page, which is what a reader can
    # count in the lists. The two differ only when the article links a redirect
    # under more than one name, so both are carried rather than one being
    # redefined: the raw count is a fact about the article, the other is a fact
    # about the destination.
    total_links: int = 0
    total_articles: int = 0
    total_missing: int = 0
    total_one_way: int = 0
    one_way_targets_checked: int = 0
    one_way_truncated: bool = False
    # Targets whose outgoing links could not be read in full, so whether they link back
    # is unknown. Distinct from `one_way_truncated`, which counts targets never looked at
    # because of the budget: here a target *was* looked at and the answer came back short.
    one_way_incomplete: int = 0
    # True when the article has more links than `max_links_per_article` and only
    # the first ones were checked, so `total_links` is a checked subset rather
    # than the article's real link count.
    links_truncated: bool = False
    # How many links were typed from a real article description, and whether the
    # `classify_max_items` cap left any missing names unclassified. Together they
    # say how much of the entity breakdown is evidence and how much is a default.
    described_links: int = 0
    classify_truncated: bool = False
    # People and places found, split by whether the target has an article.
    total_people: int = 0
    total_places: int = 0
    missing_people: int = 0
    missing_places: int = 0
    # Set when the analysis stopped on its deadline instead of finishing. The
    # article's links and missing connections are real, because they are resolved
    # before anything optional runs, but the entity types and the one-way check are
    # whatever finished. Every count below is therefore a floor rather than a
    # finding, and `abort_reason` says which stop it was.
    #
    # "Real" is not "exhaustive": `links_truncated` is a separate, independent
    # reason the link set is short, and a client must not read `aborted` as
    # describing that one.
    #
    # There is no disconnect counterpart: a client that has gone is not answered at
    # all, so a partial result is never built for one.
    aborted: bool = False
    abort_reason: str | None = None
    # Distinguishes "found no people" from "ran out of time before typing them".
    # Without it the entity counts of an aborted analysis read as a real answer
    # about an article that has any.
    entity_types_incomplete: bool = False


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
    # "A database is configured", which is a fact about this process.
    database_enabled: bool
    # "A database is actually answering", which is a fact about the world. The two come
    # apart: `create_engine` is lazy, so a wrong host or a wrong password still leaves
    # an Engine object and this would report enabled. A deployment whose every write
    # fails looks healthy otherwise, because persistence degrades to a silent no-op.
    database_reachable: bool
    # "The crawl routes demand a shared key", which is a fact about this process. Reported
    # rather than assumed: a deployment that meant to be invite-only and is not is the
    # failure nobody notices until Wikimedia blocks it, and this is the one endpoint a
    # human reads before deciding the deployment is ready.
    auth_required: bool
