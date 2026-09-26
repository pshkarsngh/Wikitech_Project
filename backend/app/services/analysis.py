"""Connection analysis.

A *connection* is a directed link from one Wikipedia article to another.

* A **missing connection** is a link whose target has no article of its own
  ("red link"). Often these are people or places that are mentioned but never
  documented.
* A **one-way connection** is a link ``A -> B`` where ``B`` does not link back
  to ``A``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import Settings
from app.schemas import (
    AnalysisResult,
    AnalysisSummary,
    ArticleDetail,
    ConnectionMap,
    ExtractedLink,
    MapEdge,
    MapNode,
    MissingConnection,
    OneWayConnection,
    ResolvedTitle,
)
from app.services import classifier
from app.services.mediawiki import (
    ArticleLinks,
    ArticleNotFoundError,
    MediaWikiClient,
    is_internal_article_link,
    normalize_title,
    title_key,
    wiki_host,
)

STATUS_MISSING = "missing"
STATUS_ONE_WAY = "one-way"
STATUS_MUTUAL = "mutual"
STATUS_UNCHECKED = "unchecked"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def index_resolved(resolved: Iterable[ResolvedTitle]) -> dict[str, ResolvedTitle]:
    """Index existence results by every name their link can be found under.

    A connection is known by the title the source article links to, which is the
    title the existence check echoes back as ``requested``, so that is the
    primary key. The canonical title it resolved to is indexed as well, so a
    record is still attributed to its link when following a redirect made the
    two names differ, instead of the link being silently dropped.

    A requested title always wins, so two different links that resolve to the
    same article cannot claim each other's record.
    """

    items = list(resolved)
    index: dict[str, ResolvedTitle] = {}
    for item in items:
        index.setdefault(title_key(item.requested), item)
    for item in items:
        if item.title:
            index.setdefault(title_key(item.title), item)
    return index


@dataclass
class LinkGraph:
    """Outgoing links of one article, with existence resolved."""

    page_id: int | None
    title: str
    url: str | None
    order: list[str]
    existing: list[ResolvedTitle] = field(default_factory=list)
    missing: list[ResolvedTitle] = field(default_factory=list)
    truncated: bool = False

    @property
    def total_links(self) -> int:
        return len(self.order)


@dataclass
class OneWayResult:
    connections: list[OneWayConnection] = field(default_factory=list)
    links_back: dict[str, bool] = field(default_factory=dict)
    checked_count: int = 0
    truncated: bool = False


async def build_link_graph(
    client: MediaWikiClient, settings: Settings, title: str
) -> LinkGraph:
    """Extract the links of an article and check which targets have articles."""

    article_links: ArticleLinks = await client.get_article_links(
        title, max_links=settings.max_links_per_article
    )
    if article_links.page_id is None:
        raise ArticleNotFoundError(f"Article '{title}' does not exist on Wikipedia")

    resolved = await client.resolve_titles(article_links.links)
    by_title = index_resolved(resolved)

    graph = LinkGraph(
        page_id=article_links.page_id,
        title=article_links.title,
        url=article_links.url,
        order=article_links.links,
        truncated=article_links.truncated,
    )

    for link_title in article_links.links:
        info = by_title.get(title_key(link_title))
        if info is None:
            continue
        if info.exists:
            graph.existing.append(info)
        else:
            graph.missing.append(info)

    # The article never links to itself.
    seed_key = title_key(graph.title)
    graph.existing = [item for item in graph.existing if title_key(item.requested) != seed_key]
    graph.missing = [item for item in graph.missing if title_key(item.requested) != seed_key]
    return graph


async def classify_links(
    client: MediaWikiClient, settings: Settings, graph: LinkGraph
) -> tuple[dict[str, str], int, bool]:
    """Entity type for every extracted link, keyed by the linked title.

    Two different sources, because the two kinds of link carry different
    information:

    * A link that resolves to an article is described by that article. The
      descriptions are fetched in batches, so classifying every link of an
      article costs a handful of requests rather than one request per link.
    * A missing link has no article and so no description of its own. Its type
      has to come from Wikidata, one request per name, which is capped by
      ``classify_max_items``.

    Returns the types, how many links were classified from a real description,
    and whether the cap left any missing names unclassified.
    """

    types: dict[str, str] = {}
    described = 0

    descriptions = await client.get_page_descriptions(
        item.page_id for item in graph.existing if item.page_id is not None
    )
    for item in graph.existing:
        description = descriptions.get(item.page_id) if item.page_id else None
        types[item.requested] = classifier.classify_description(description)
        if description:
            described += 1

    missing_types, truncated = await classifier.classify_titles(
        client, [item.requested for item in graph.missing], settings
    )
    types.update(missing_types)

    return types, described, truncated


async def detect_missing_connections(
    client: MediaWikiClient, settings: Settings, graph: LinkGraph
) -> tuple[list[MissingConnection], dict[str, str]]:
    """Every mentioned person or place that has no article yet."""

    missing_types, _ = await classifier.classify_titles(
        client, [item.requested for item in graph.missing], settings
    )

    connections = [
        MissingConnection(
            title=item.requested,
            entity_type=missing_types.get(item.requested, classifier.OTHER),
            source_title=graph.title,
            source_url=graph.url,
        )
        for item in graph.missing
    ]
    return connections, missing_types


async def detect_one_way_connections(
    client: MediaWikiClient, settings: Settings, graph: LinkGraph
) -> OneWayResult:
    """Links that the target articles do not return.

    Only the first ``one_way_max_targets`` existing targets are checked, because
    each one needs its own request to the MediaWiki API.
    """

    result = OneWayResult()
    if graph.page_id is None:
        return result

    seed_key = title_key(graph.title)

    # Two different link titles can resolve to the same page, so check each page
    # only once.
    candidates: list[ResolvedTitle] = []
    seen_page_ids: set[int] = set()
    for item in graph.existing:
        if item.page_id is None or item.page_id in seen_page_ids:
            continue
        seen_page_ids.add(item.page_id)
        candidates.append(item)

    result.truncated = len(candidates) > settings.one_way_max_targets
    candidates = candidates[: settings.one_way_max_targets]

    outgoing = await client.get_links_for_page_ids(
        [item.page_id for item in candidates if item.page_id is not None]
    )

    for item in candidates:
        if item.page_id is None:
            continue
        target_links = outgoing.get(item.page_id)
        if target_links is None:
            continue

        result.checked_count += 1
        links_back = seed_key in target_links
        label = item.title or item.requested
        result.links_back[title_key(label)] = links_back

        if not links_back:
            result.connections.append(
                OneWayConnection(
                    source_title=graph.title,
                    target_title=label,
                    target_page_id=item.page_id,
                    target_url=item.url,
                    links_back=False,
                )
            )

    return result


def build_extracted_links(
    graph: LinkGraph, types: dict[str, str]
) -> list[ExtractedLink]:
    """The article's links, annotated with existence and a person/place guess.

    Every link records its own title and target, the article it was found in,
    whether it is an internal article link, and the ``exists`` / ``missing``
    classification of its target. Only article links ever reach this point:
    the MediaWiki client requests the main namespace and no external links, so
    external websites, images, files, categories, navigation and other
    non-article resources are not in ``graph.order``.

    ``title`` is the target's own article title once the link has been resolved
    to an existing page, which is the canonical name even when a redirect was
    followed to reach it. A missing target keeps the title the article links to,
    because there is no article to take a name from.
    """

    by_title = index_resolved([*graph.existing, *graph.missing])
    host = wiki_host(graph.url)

    links: list[ExtractedLink] = []
    for link_title in graph.order:
        info = by_title.get(title_key(link_title))
        if info is None:
            # The existence check answers for every extracted link, so this is
            # not expected. A link with no answer is left out rather than being
            # reported as existing or missing on no evidence.
            continue
        links.append(
            ExtractedLink(
                title=info.title or normalize_title(link_title),
                page_id=info.page_id,
                url=info.url,
                exists=info.exists,
                entity_type=types.get(info.requested, classifier.OTHER),
                source_title=graph.title,
                source_url=graph.url,
                is_internal=is_internal_article_link(info.url, host=host),
                redirected=info.redirected,
            )
        )
    return links


def build_connection_map(
    graph: LinkGraph,
    missing: list[MissingConnection],
    one_way: OneWayResult,
    types: dict[str, str],
    settings: Settings,
) -> ConnectionMap:
    """Build a directed graph ready for Cytoscape.js.

    Every node is one hop away from the seed article. Missing targets and
    one-way targets are included first because they are the point of the app.
    """

    seed_id = f"seed:{title_key(graph.title)}"
    seed = MapNode(
        id=seed_id,
        label=graph.title,
        page_id=graph.page_id,
        url=graph.url,
        exists=True,
        entity_type=classifier.OTHER,
        is_seed=True,
    )
    nodes: list[MapNode] = [seed]
    edges: list[MapEdge] = []
    seen: set[str] = {seed_id}

    missing_keys = {title_key(item.title) for item in missing}
    missing_types = {title_key(item.title): item.entity_type for item in missing}
    missing_labels = {title_key(item.title): item.title for item in missing}
    existing_by_key: dict[str, ResolvedTitle] = {}
    for item in graph.existing:
        existing_by_key[title_key(item.title or item.requested)] = item

    ordered_keys: list[str] = []

    def push(key: str) -> None:
        if key and key not in seen and len(ordered_keys) < settings.map_node_limit:
            seen.add(key)
            ordered_keys.append(key)

    for item in missing:
        push(title_key(item.title))
    for item in one_way.connections:
        push(title_key(item.target_title))
    for key in existing_by_key:
        push(key)

    for key in ordered_keys:
        is_missing = key in missing_keys
        info = existing_by_key.get(key)
        node_id = f"page:{key}" if info and info.page_id else f"missing:{key}"
        label = (info.title or info.requested) if info else missing_labels.get(key, key)
        nodes.append(
            MapNode(
                id=node_id,
                label=label,
                page_id=info.page_id if info else None,
                url=info.url if info else None,
                exists=not is_missing,
                entity_type=missing_types.get(key, classifier.OTHER)
                if is_missing
                else classifier.OTHER,
            )
        )

        if is_missing:
            status = STATUS_MISSING
        elif key in one_way.links_back:
            status = STATUS_MUTUAL if one_way.links_back[key] else STATUS_ONE_WAY
        else:
            # Outside the one-way check budget, so the direction is unknown.
            status = STATUS_UNCHECKED

        edges.append(
            MapEdge(
                id=f"{seed_id}->{node_id}",
                source=seed_id,
                target=node_id,
                status=status,
                exists=not is_missing,
            )
        )

    return ConnectionMap(
        article={
            "page_id": graph.page_id,
            "title": graph.title,
            "url": graph.url,
        },
        generated_at=_utcnow(),
        nodes=nodes,
        edges=edges,
        truncated=len(ordered_keys) < len(missing_keys | set(existing_by_key)),
    )


async def analyze_article(
    client: MediaWikiClient, settings: Settings, title: str
) -> AnalysisResult:
    """Run the full pipeline for one article."""

    article = await client.get_article(title)
    graph = await build_link_graph(client, settings, article.title)
    types, described, classify_truncated = await classify_links(client, settings, graph)
    one_way = await detect_one_way_connections(client, settings, graph)

    missing = [
        MissingConnection(
            title=item.requested,
            entity_type=types.get(item.requested, classifier.OTHER),
            source_title=graph.title,
            source_url=graph.url,
        )
        for item in graph.missing
    ]

    return AnalysisResult(
        article=article,
        generated_at=_utcnow(),
        summary=AnalysisSummary(
            total_links=graph.total_links,
            total_missing=len(missing),
            total_one_way=len(one_way.connections),
            one_way_targets_checked=one_way.checked_count,
            one_way_truncated=one_way.truncated,
            links_truncated=graph.truncated,
            described_links=described,
            classify_truncated=classify_truncated,
            total_people=sum(1 for value in types.values() if value == classifier.PERSON),
            total_places=sum(1 for value in types.values() if value == classifier.PLACE),
            missing_people=sum(
                1 for item in missing if item.entity_type == classifier.PERSON
            ),
            missing_places=sum(
                1 for item in missing if item.entity_type == classifier.PLACE
            ),
        ),
        missing_connections=missing,
        one_way_connections=one_way.connections,
        links=build_extracted_links(graph, types),
    )
