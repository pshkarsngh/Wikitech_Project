"""Unit tests for title handling, the existence check and classification."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services import classifier
from app.services.mediawiki import (
    ArticleNotFoundError,
    MediaWikiClient,
    WikipediaError,
    chunked,
    is_internal_article_link,
    normalize_title,
    title_key,
    wiki_host,
)


def test_normalize_and_key() -> None:
    assert normalize_title("Ada_Lovelace ") == "Ada Lovelace"
    assert title_key("ADA_lovelace") == "ada lovelace"
    assert title_key("Ada Lovelace") == title_key("ada lovelace")


def test_chunked_splits_evenly_and_safely() -> None:
    assert list(chunked([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
    assert list(chunked([], 10)) == []
    assert list(chunked([1, 2], 0)) == [[1], [2]]


def test_classify_description() -> None:
    assert classifier.classify_description("English politician") == classifier.PERSON
    assert (
        classifier.classify_description("capital and largest city of England")
        == classifier.PLACE
    )
    assert classifier.classify_description("village in Malta") == classifier.PLACE
    assert classifier.classify_description("mechanical computer") == classifier.OTHER
    assert classifier.classify_description(None) == classifier.OTHER
    assert classifier.classify_description("") == classifier.OTHER


def test_classify_description_avoids_substring_false_positives() -> None:
    # "man" is part of "human" and "woman", and must not trigger the person rule.
    assert classifier.classify_description("human settlement") == classifier.PLACE
    assert classifier.classify_description("software") == classifier.OTHER


class StubClient(MediaWikiClient):
    """MediaWikiClient with the HTTP layer replaced by a canned response."""

    def __init__(self, response: dict) -> None:  # noqa: D107 - no super().__init__()
        self._settings = Settings()
        self.response = response
        self.requests: list[dict] = []

    async def _api_get(self, params, *, endpoint=None):
        self.requests.append(params)
        return self.response


class SequencedStubClient(MediaWikiClient):
    """MediaWikiClient that replays one canned response per request."""

    def __init__(self, responses: list[dict]) -> None:  # noqa: D107
        self._settings = Settings()
        self.responses = list(responses)
        self.requests: list[dict] = []

    async def _api_get(self, params, *, endpoint=None):
        self.requests.append(params)
        return self.responses.pop(0)


def _missing_page(title: str) -> dict:
    return {"query": {"pages": [{"title": title, "missing": True}]}}


def _search_hits(*titles: str) -> dict:
    return {
        "query": {
            "search": [{"pageid": index + 1, "title": title} for index, title in enumerate(titles)]
        }
    }


def _page(**overrides) -> dict:
    page = {
        "pageid": 1,
        "title": "Ada Lovelace",
        "fullurl": "https://en.wikipedia.org/wiki/Ada_Lovelace",
        "extract": "Ada Lovelace was an English mathematician.",
    }
    return {"query": {"pages": [page | overrides]}}


async def test_find_article_prefers_an_exact_title() -> None:
    client = SequencedStubClient([_page()])

    article = await client.find_article("Ada Lovelace")

    assert article.page_id == 1
    assert article.url == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert article.extract.startswith("Ada Lovelace was")
    # One request: the exact title needed no fallback search.
    assert len(client.requests) == 1


async def test_find_article_falls_back_to_a_title_only_search() -> None:
    client = SequencedStubClient(
        [_missing_page("londn"), _search_hits("London"), _page(title="London", pageid=3)]
    )

    article = await client.find_article("londn")

    assert article.title == "London"
    assert article.page_id == 3
    # The fallback must not match body text, or a typo returns an unrelated page.
    assert client.requests[1]["srsearch"] == "intitle:londn"


async def test_find_article_does_not_search_when_the_title_is_exact() -> None:
    client = SequencedStubClient([_page()])

    await client.find_article("Ada Lovelace")

    assert len(client.requests) == 1
    assert "list" not in client.requests[0]


async def test_find_article_without_results_raises_not_found() -> None:
    client = SequencedStubClient([_missing_page("Zzqx"), {"query": {"search": []}}])

    try:
        await client.find_article("Zzqx")
    except ArticleNotFoundError as exc:
        assert "No article found" in str(exc)
    else:
        raise AssertionError("expected ArticleNotFoundError")


async def test_find_article_rejects_a_blank_name() -> None:
    client = SequencedStubClient([])

    try:
        await client.find_article("   ")
    except ArticleNotFoundError:
        pass
    else:
        raise AssertionError("expected ArticleNotFoundError")

    assert client.requests == []


async def test_resolve_titles_marks_missing_pages() -> None:
    client = StubClient(
        {
            "query": {
                "pages": [
                    {"pageid": 2, "title": "Analytical Engine", "fullurl": "https://x/1"},
                    {"title": "Byron's Daughter", "missing": True},
                ]
            }
        }
    )

    resolved = await client.resolve_titles(["Analytical Engine", "Byron's Daughter"])

    assert [item.requested for item in resolved] == [
        "Analytical Engine",
        "Byron's Daughter",
    ]
    assert resolved[0].exists is True
    assert resolved[0].page_id == 2
    assert resolved[1].exists is False
    assert resolved[1].page_id is None


async def test_resolve_titles_follows_normalisation_and_redirects() -> None:
    client = StubClient(
        {
            "query": {
                "normalized": [{"from": "ada lovelace", "to": "Ada Lovelace"}],
                "redirects": [{"from": "Ada Lovelace", "to": "Ada King"}],
                "pages": [{"pageid": 99, "title": "Ada King", "fullurl": "https://x/2"}],
            }
        }
    )

    resolved = await client.resolve_titles(["ada lovelace"])

    assert resolved[0].requested == "ada lovelace"
    assert resolved[0].title == "Ada King"
    assert resolved[0].page_id == 99
    assert resolved[0].exists is True
    # A redirect is still an existing article, reached under another name.
    assert resolved[0].state == "exists"
    assert resolved[0].redirected is True


async def test_resolve_titles_does_not_call_normalisation_a_redirect() -> None:
    client = StubClient(
        {
            "query": {
                "normalized": [{"from": "ada lovelace", "to": "Ada Lovelace"}],
                "pages": [{"pageid": 1, "title": "Ada Lovelace", "fullurl": "https://x/1"}],
            }
        }
    )

    resolved = await client.resolve_titles(["ada lovelace"])

    # Only the case and the underscores changed, so no redirect was followed.
    assert resolved[0].title == "Ada Lovelace"
    assert resolved[0].redirected is False


async def test_resolve_titles_classifies_each_target() -> None:
    client = StubClient(
        {
            "query": {
                "pages": [
                    {"pageid": 5, "title": "Germany", "fullurl": "https://x/5"},
                    {"title": "Example Person", "missing": True},
                    {"title": "Foo:", "invalid": True},
                ]
            }
        }
    )

    resolved = await client.resolve_titles(["Germany", "Example Person", "Foo:"])
    states = {item.requested: item.state for item in resolved}

    assert states == {
        "Germany": "exists",
        "Example Person": "missing",
        "Foo:": "missing",
    }


async def test_resolve_titles_treats_an_invalid_title_as_missing() -> None:
    # MediaWiki flags a title that is not a valid page title with "invalid" and
    # sends no "missing" key, so it must not read as an existing article.
    client = StubClient({"query": {"pages": [{"title": "Foo:", "invalid": True}]}})

    resolved = await client.resolve_titles(["Foo:"])

    assert resolved[0].exists is False
    assert resolved[0].page_id is None
    assert resolved[0].url is None


async def test_resolve_titles_treats_an_absent_page_as_missing() -> None:
    # Some responses omit the page entirely instead of marking it missing.
    client = StubClient({"query": {"pages": []}})

    resolved = await client.resolve_titles(["Germany"])

    assert resolved[0].exists is False
    assert resolved[0].title is None


async def test_resolve_titles_propagates_api_errors() -> None:
    # A batch that cannot be answered must raise rather than look like a
    # complete answer, so the caller reports an upstream failure.
    class FailingClient(MediaWikiClient):
        def __init__(self) -> None:  # noqa: D107 - no super().__init__()
            self._settings = Settings()

        async def _api_get(self, params, *, endpoint=None):
            raise WikipediaError("MediaWiki API error: maxlag")

    with pytest.raises(WikipediaError):
        await FailingClient().resolve_titles(["Germany"])


async def test_resolve_titles_asks_the_api_rather_than_parsing_html() -> None:
    client = StubClient({"query": {"pages": [{"pageid": 5, "title": "Germany"}]}})

    await client.resolve_titles(["Germany"])

    request = client.requests[0]
    assert request["action"] == "query"
    assert request["prop"] == "info"
    assert request["titles"] == "Germany"
    assert "redirects" in request


async def test_resolve_titles_deduplicates_and_splits_batches() -> None:
    client = StubClient({"query": {"pages": [{"pageid": 1, "title": "A"}]}})
    await client.resolve_titles(["A", "A", "A"])

    assert len(client.requests) == 1
    assert client.requests[0]["titles"] == "A"


async def test_get_links_for_page_ids_returns_comparison_keys() -> None:
    client = StubClient(
        {
            "query": {
                "pages": [
                    {"pageid": 2, "links": [{"title": "Ada Lovelace"}, {"title": "Engine"}]}
                ]
            }
        }
    )

    result = await client.get_links_for_page_ids([2])

    assert result[2] == {"ada lovelace", "engine"}


def _links_payload(*links: dict) -> dict:
    return {
        "query": {
            "pages": [
                {
                    "pageid": 1,
                    "title": "Albert Einstein",
                    "fullurl": "https://en.wikipedia.org/wiki/Albert_Einstein",
                    "links": list(links),
                }
            ]
        }
    }


def test_wiki_host() -> None:
    assert wiki_host("https://en.wikipedia.org/w/api.php") == "en.wikipedia.org"
    assert wiki_host("https://EN.wikipedia.org/wiki/Ada_Lovelace") == "en.wikipedia.org"
    assert wiki_host(None) == ""


def test_is_internal_article_link() -> None:
    host = wiki_host("https://en.wikipedia.org/w/api.php")

    assert is_internal_article_link(
        "https://en.wikipedia.org/wiki/Germany", host=host
    )
    # A red link: no article yet, but still a link to an article on this wiki.
    assert is_internal_article_link(None, host=host)
    # External websites, same-host non-article paths and non-http targets are
    # not internal article links. Other namespaces never get this far: the
    # main-namespace request drops them before a URL is ever built.
    assert not is_internal_article_link("https://example.com/germany", host=host)
    assert not is_internal_article_link("https://en.wikipedia.org/", host=host)
    assert not is_internal_article_link("https://en.wikipedia.org/w/index.php", host=host)
    assert not is_internal_article_link("#cite_note-1", host=host)
    # With no known host the main-namespace request is trusted.
    assert is_internal_article_link("https://en.wikipedia.org/wiki/Germany", host="")


async def test_get_article_links_only_returns_article_links() -> None:
    client = StubClient(
        _links_payload(
            {"ns": 0, "title": "Germany"},
            {"ns": 6, "title": "File:Einstein 1921.png"},
            {"ns": 14, "title": "Category:Physicists"},
            {"ns": 10, "title": "Template:Infobox scientist"},
            {"ns": 0, "title": "Switzerland"},
        )
    )

    result = await client.get_article_links("Albert Einstein")

    # Images, files, categories and templates are dropped; articles survive.
    assert result.links == ["Germany", "Switzerland"]
    assert result.page_id == 1
    assert result.title == "Albert Einstein"
    assert client.requests[0]["plnamespace"] == 0
    # External links need a separate prop, which is never requested.
    assert "extlinks" not in client.requests[0]["prop"]


async def test_get_article_links_trusts_the_namespace_when_it_is_absent() -> None:
    client = StubClient(_links_payload({"title": "Germany"}))

    result = await client.get_article_links("Albert Einstein")

    assert result.links == ["Germany"]


async def test_get_article_links_deduplicates_case_insensitively() -> None:
    client = StubClient(
        _links_payload(
            {"ns": 0, "title": "Germany"},
            {"ns": 0, "title": "germany"},
            {"ns": 0, "title": "Germany"},
        )
    )

    result = await client.get_article_links("Albert Einstein")

    assert result.links == ["Germany"]
