"""Unit tests for the analysis pipeline against a fake MediaWiki client."""

from __future__ import annotations

from app.config import Settings
from app.schemas import ResolvedTitle
from app.services import classifier
from app.services.analysis import (
    STATUS_MISSING,
    STATUS_MUTUAL,
    STATUS_ONE_WAY,
    analyze_article,
    build_connection_map,
    build_link_graph,
    classify_links,
    detect_missing_connections,
    detect_one_way_connections,
)
from tests.fake_wikipedia import ADA, ENGINE, LONDON, NOVEL, VILLAGE, FakeWikipediaClient


async def test_build_link_graph_splits_existing_and_missing(settings: Settings) -> None:
    graph = await build_link_graph(FakeWikipediaClient(), settings, ADA)

    assert graph.total_links == 4
    assert [item.requested for item in graph.existing] == [ENGINE, LONDON]
    assert [item.requested for item in graph.missing] == [NOVEL, VILLAGE]
    assert graph.page_id == 1
    assert graph.truncated is False


async def test_missing_connections_are_people_or_places(settings: Settings) -> None:
    client = FakeWikipediaClient()
    graph = await build_link_graph(client, settings, ADA)
    missing, types = await detect_missing_connections(client, settings, graph)

    assert [item.title for item in missing] == [NOVEL, VILLAGE]
    assert types[VILLAGE] == classifier.PLACE
    assert types[NOVEL] == classifier.OTHER
    assert all(item.source_title == ADA for item in missing)


async def test_one_way_connections_exclude_targets_that_link_back(settings: Settings) -> None:
    client = FakeWikipediaClient()
    graph = await build_link_graph(client, settings, ADA)
    result = await detect_one_way_connections(client, settings, graph)

    assert [item.target_title for item in result.connections] == [LONDON]
    assert result.links_back["analytical engine"] is True
    assert result.links_back["london"] is False
    assert result.checked_count == 2
    assert result.truncated is False


async def test_one_way_detection_respects_the_target_budget(settings: Settings) -> None:
    limited = settings.model_copy(update={"one_way_max_targets": 1})
    client = FakeWikipediaClient()
    graph = await build_link_graph(client, settings, ADA)
    result = await detect_one_way_connections(client, limited, graph)

    assert result.checked_count == 1
    assert result.truncated is True
    # Only the first candidate was checked, and it links back to Ada Lovelace.
    assert result.connections == []


async def test_one_way_needs_a_page_id(settings: Settings) -> None:
    client = FakeWikipediaClient()
    graph = await build_link_graph(client, settings, ADA)
    graph.page_id = None

    result = await detect_one_way_connections(client, settings, graph)

    assert result.connections == []
    assert result.checked_count == 0


async def test_analyze_article_summary(settings: Settings) -> None:
    result = await analyze_article(FakeWikipediaClient(), settings, ADA)

    assert result.article.title == ADA
    assert result.summary.total_links == 4
    assert result.summary.total_missing == 2
    assert result.summary.total_one_way == 1
    assert result.summary.one_way_targets_checked == 2

    assert [item.title for item in result.missing_connections] == [NOVEL, VILLAGE]
    assert [item.target_title for item in result.one_way_connections] == [LONDON]

    existing = {link.title for link in result.links if link.exists}
    absent = [link.title for link in result.links if not link.exists]
    assert existing == {ENGINE, LONDON}
    assert absent == [NOVEL, VILLAGE]


async def test_summary_reports_a_truncated_link_set(settings: Settings) -> None:
    # The article links to four pages; a cap of two checks only two of them, so
    # the summary has to admit the link set is a checked subset.
    capped = settings.model_copy(update={"max_links_per_article": 2})

    result = await analyze_article(FakeWikipediaClient(), capped, ADA)

    assert result.summary.links_truncated is True
    assert result.summary.total_links == 2
    # The two checked links are the existing ones, so nothing is reported missing.
    assert result.summary.total_missing == 0
    assert result.missing_connections == []


async def test_summary_is_not_truncated_when_every_link_fits(
    settings: Settings,
) -> None:
    result = await analyze_article(FakeWikipediaClient(), settings, ADA)

    assert result.summary.links_truncated is False
    assert result.summary.total_links == 4


async def test_existing_links_are_typed_from_their_own_article(
    settings: Settings,
) -> None:
    # A link that resolves to an article is described by that article, so an
    # existing place is identified without any Wikidata search.
    result = await analyze_article(FakeWikipediaClient(), settings, ADA)
    types = {link.title: link.entity_type for link in result.links}

    assert types[LONDON] == "place"
    assert types[ENGINE] == "other"
    assert result.summary.described_links == 2


async def test_people_and_places_are_counted_and_split_by_existence(
    settings: Settings,
) -> None:
    result = await analyze_article(FakeWikipediaClient(), settings, ADA)

    # London exists and is a place; Somerton, Malta is a place with no article.
    # `total_places` counts every place found, `missing_places` only the ones
    # without an article, which is what the two sections each need.
    assert result.summary.total_places == 2
    assert result.summary.missing_places == 1
    assert result.summary.total_people == 0
    assert result.summary.missing_people == 0

    # Every person or place is reachable from the link list, so a consumer can
    # build the people, places, missing people and missing places sections from
    # one source without a second request.
    links = result.links
    assert {link.title for link in links if link.entity_type == "place"} == {LONDON, VILLAGE}
    assert {
        link.title
        for link in links
        if link.entity_type == "place" and not link.exists
    } == {VILLAGE}


async def test_every_entity_carries_name_type_source_and_status(
    settings: Settings,
) -> None:
    result = await analyze_article(FakeWikipediaClient(), settings, ADA)

    for link in result.links:
        assert link.title
        assert link.entity_type in {"person", "place", "other"}
        assert link.source_title == ADA
        assert link.source_url
        assert link.state in {"exists", "missing"}
        # A Wikipedia link is present exactly when the article exists.
        assert bool(link.url) is link.exists


async def test_a_missing_name_is_left_untyped_when_the_classify_cap_is_hit(
    settings: Settings,
) -> None:
    # Two missing names, but only one may be sent to Wikidata.
    capped = settings.model_copy(update={"classify_max_items": 1})

    result = await analyze_article(FakeWikipediaClient(), capped, ADA)

    assert result.summary.classify_truncated is True
    typed = {item.title: item.entity_type for item in result.missing_connections}
    # Only the first missing name reaches Wikidata, so the second stays at the
    # default rather than being guessed at.
    assert typed[VILLAGE] == "other"
    assert typed[NOVEL] == "other"


async def test_classification_is_not_truncated_when_every_name_fits(
    settings: Settings,
) -> None:
    result = await analyze_article(FakeWikipediaClient(), settings, ADA)

    assert result.summary.classify_truncated is False


async def test_classified_existing_link_is_not_the_default_other(
    settings: Settings,
) -> None:
    # Guards the regression where only missing names were classified, which left
    # every existing person and place reported as "other".
    graph = await build_link_graph(FakeWikipediaClient(), settings, ADA)
    types, described, truncated = await classify_links(
        FakeWikipediaClient(), settings, graph
    )

    assert types[LONDON] == "place"
    assert described == 2
    assert truncated is False


async def test_a_compound_word_is_not_read_as_a_role(settings: Settings) -> None:
    # "general-purpose" must not be read as the military rank "general".
    assert classifier.classify_description(
        "mechanical general-purpose computer"
    ) == "other"
    assert classifier.classify_description("general relativity") == "other"
    assert classifier.classify_description("association football player") == "person"


async def test_extracted_links_carry_article_urls(settings: Settings) -> None:
    result = await analyze_article(FakeWikipediaClient(), settings, ADA)
    links = {link.title: link for link in result.links}

    assert links[ENGINE].url == "https://en.wikipedia.org/wiki/Analytical_Engine"
    assert links[ENGINE].page_id == 2
    assert links[NOVEL].exists is False
    assert links[NOVEL].url is None


async def test_extracted_links_record_their_source_article(settings: Settings) -> None:
    result = await analyze_article(FakeWikipediaClient(), settings, ADA)

    assert result.links
    for link in result.links:
        assert link.source_title == ADA
        assert link.source_url == "https://en.wikipedia.org/wiki/Ada_Lovelace"


async def test_extracted_links_are_internal_article_links(settings: Settings) -> None:
    result = await analyze_article(FakeWikipediaClient(), settings, ADA)

    # A red link has no target yet but still points at an article on this wiki.
    assert all(link.is_internal for link in result.links)
    assert next(link for link in result.links if link.title == NOVEL).is_internal is True


async def test_extracted_links_flag_an_external_target(settings: Settings) -> None:
    client = FakeWikipediaClient()
    original = client.resolve_titles

    async def resolve_to_an_external_site(titles):
        resolved = await original(titles)
        return [
            item.model_copy(update={"url": "https://example.com/analytical-engine"})
            if item.requested == ENGINE
            else item
            for item in resolved
        ]

    client.resolve_titles = resolve_to_an_external_site  # type: ignore[method-assign]

    result = await analyze_article(client, settings, ADA)
    links = {link.title: link for link in result.links}

    assert links[ENGINE].is_internal is False
    assert links[LONDON].is_internal is True


async def test_every_extracted_link_is_classified_as_exists_or_missing(
    settings: Settings,
) -> None:
    result = await analyze_article(FakeWikipediaClient(), settings, ADA)
    states = {link.title: link.state for link in result.links}

    # Every extracted link lands in exactly one of the two buckets, and the
    # classification always agrees with the boolean it is derived from.
    assert states == {
        ENGINE: "exists",
        LONDON: "exists",
        NOVEL: "missing",
        VILLAGE: "missing",
    }
    assert all(link.state in {"exists", "missing"} for link in result.links)
    assert all(
        (link.state == "exists") == link.exists for link in result.links
    )
    assert all(item.state == "missing" for item in result.missing_connections)


async def test_extracted_links_report_a_redirected_target(settings: Settings) -> None:
    client = FakeWikipediaClient()
    original = client.resolve_titles

    async def resolve_via_redirect(titles):
        resolved = await original(titles)
        return [
            item.model_copy(
                update={"requested": "Babbage's Engine", "redirected": True}
            )
            if item.requested == ENGINE
            else item
            for item in resolved
        ]

    client.resolve_titles = resolve_via_redirect  # type: ignore[method-assign]

    result = await analyze_article(client, settings, ADA)
    links = {link.title: link for link in result.links}

    # Following a redirect does not change the classification.
    assert links[ENGINE].redirected is True
    assert links[ENGINE].state == "exists"
    assert links[LONDON].redirected is False


async def test_a_redirect_does_not_overwrite_another_links_result(
    settings: Settings,
) -> None:
    # "Bangaon" redirects to "Bongaon" and the article links to both. The
    # Bongaon link must keep its own result: inheriting the redirect would
    # report a red link as an existing article.
    client = FakeWikipediaClient()
    get_links = client.get_article_links
    resolve = client.resolve_titles

    async def with_both_links(title, *, max_links=None):
        links = await get_links(title, max_links=max_links)
        links.links.extend(["Bangaon", "Bongaon"])
        return links

    async def resolve_bangaon_as_a_redirect(titles):
        resolved = await resolve(titles)
        return [
            *resolved,
            *(
                ResolvedTitle(
                    requested=name,
                    title="Bongaon",
                    page_id=9,
                    url="https://en.wikipedia.org/wiki/Bongaon",
                    exists=True,
                    redirected=True,
                )
                for name in titles
                if name == "Bangaon"
            ),
        ]

    client.get_article_links = with_both_links  # type: ignore[method-assign]
    client.resolve_titles = resolve_bangaon_as_a_redirect  # type: ignore[method-assign]

    result = await analyze_article(client, settings, ADA)
    links = {link.title: link for link in result.links}

    assert links["Bangaon"].exists is False
    assert links["Bongaon"].exists is False
    assert all(link.redirected is False for link in result.links)


async def test_connection_map_edges_carry_direction_status(settings: Settings) -> None:
    client = FakeWikipediaClient()
    graph = await build_link_graph(client, settings, ADA)
    missing, types = await detect_missing_connections(client, settings, graph)
    one_way = await detect_one_way_connections(client, settings, graph)

    map_ = build_connection_map(graph, missing, one_way, types, settings)

    assert [node.label for node in map_.nodes if node.is_seed] == [ADA]
    assert map_.truncated is False

    status_by_label = {edge.target: edge.status for edge in map_.edges}
    label_by_id = {node.id: node.label for node in map_.nodes}

    def status_for(label: str) -> str:
        return status_by_label[next(n.id for n in map_.nodes if n.label == label)]

    assert status_for(NOVEL) == STATUS_MISSING
    assert status_for(VILLAGE) == STATUS_MISSING
    assert status_for(LONDON) == STATUS_ONE_WAY
    assert status_for(ENGINE) == STATUS_MUTUAL

    missing_nodes = [node for node in map_.nodes if not node.exists]
    assert [node.label for node in missing_nodes] == [NOVEL, VILLAGE]
    assert all(node.id.startswith("missing:") for node in missing_nodes)
    assert next(n for n in map_.nodes if n.label == LONDON).id.startswith("page:")

    seed = next(node for node in map_.nodes if node.is_seed)
    assert {edge.source for edge in map_.edges} == {seed.id}


async def test_map_node_limit_truncates(settings: Settings) -> None:
    tiny = settings.model_copy(update={"map_node_limit": 1})
    client = FakeWikipediaClient()
    graph = await build_link_graph(client, settings, ADA)
    missing, types = await detect_missing_connections(client, settings, graph)
    one_way = await detect_one_way_connections(client, settings, graph)

    map_ = build_connection_map(graph, missing, one_way, types, tiny)

    # Seed plus the first missing target.
    assert len(map_.nodes) == 2
    assert map_.nodes[1].label == NOVEL
    assert map_.truncated is True


async def test_self_links_are_ignored(settings: Settings) -> None:
    client = FakeWikipediaClient()
    original = client.get_article_links

    async def with_self_link(title, *, max_links=None):
        links = await original(title, max_links=max_links)
        links.links.append(ADA)
        return links

    client.get_article_links = with_self_link  # type: ignore[method-assign]
    graph = await build_link_graph(client, settings, ADA)

    assert all(item.requested != ADA for item in graph.existing)
    assert all(item.requested != ADA for item in graph.missing)
