"""Unit tests for title handling, the existence check and classification."""

from __future__ import annotations

import asyncio
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.config import Settings
from app.services import classifier
from app.services.mediawiki import (
    ArticleNotFoundError,
    MediaWikiClient,
    WikipediaError,
    _retry_delay,
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


class _FakeResponse:
    """The parts of an httpx response that ``_api_get`` actually reads."""

    def __init__(self, status_code: int, payload: dict | None = None, headers=None) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = {} if payload is None else payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
            raise httpx.HTTPStatusError(
                f"status {self.status_code}",
                request=request,
                response=httpx.Response(self.status_code, request=request),
            )

    def json(self) -> dict:
        return self._payload


class _Transport:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    async def get(self, url, *, params):
        self.requests.append(dict(params))
        return self.responses.pop(0)


class TransportClient(MediaWikiClient):
    """MediaWikiClient with only the HTTP transport replaced.

    The existing stubs go the other way and replace ``_api_get``, which is right when the
    test is about a method's parsing. These are about the transport contract itself - the
    query every request carries, and what happens on 429 - so the real ``_api_get`` has to
    run and only the socket is faked.
    """

    def __init__(self, responses: list[_FakeResponse], settings: Settings | None = None) -> None:  # noqa: D107
        self._settings = settings or Settings()
        self._semaphore = asyncio.Semaphore(1)
        self._owns_client = False
        self.transport = _Transport(responses)
        self._client = self.transport


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

    assert result[2].titles == {"ada lovelace", "engine"}
    assert result[2].complete is True


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


# --- Wikimedia API etiquette -------------------------------------------------
# https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits and
# https://www.mediawiki.org/wiki/API:Etiquette. These are published limits on how this
# deployment is allowed to call Wikimedia, not internal tuning, so they are pinned by test
# rather than left to drift back to a value that merely looks reasonable.


def test_the_default_concurrency_is_within_the_published_wikimedia_limit() -> None:
    # "limit the number of concurrent requests to 3 or fewer". This was 4, which is over.
    # Asserts the field default rather than a built Settings, so a developer's local
    # .env - which is gitignored and absent in CI - cannot decide the result.
    assert Settings.model_fields["max_concurrent_requests"].default <= 3


async def test_every_request_declares_a_maxlag() -> None:
    # maxlag makes a busy Wikipedia refuse the request instead of queueing it, so a slow
    # upstream surfaces as an error the caller can see rather than a slow success.
    client = TransportClient([_FakeResponse(200, _search_hits("Germany"))])

    await client.search_articles("germany")

    assert client.transport.requests[0]["maxlag"] == 5


async def test_a_callers_maxlag_is_not_overwritten_by_the_default() -> None:
    client = TransportClient([_FakeResponse(200, _search_hits("Germany"))])

    await client._api_get({"action": "query", "maxlag": 1})

    assert client.transport.requests[0]["maxlag"] == 1


async def test_a_rate_limited_request_waits_for_the_window_wikimedia_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits: list[float] = []

    async def record(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", record)
    client = TransportClient(
        [
            _FakeResponse(429, headers={"retry-after": "7"}),
            _FakeResponse(200, _search_hits("Germany")),
        ]
    )

    hits = await client.search_articles("germany")

    assert [hit.title for hit in hits] == ["Germany"]
    # A fixed one-second wait re-enters the same limiter and is nearly guaranteed to be
    # refused again, which turns a rate limit into an outage.
    assert waits == [7.0]


async def test_a_refusal_without_a_retry_after_still_backs_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits: list[float] = []

    async def record(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", record)
    client = TransportClient(
        [
            _FakeResponse(429),
            _FakeResponse(200, _search_hits("Germany")),
        ]
    )

    await client.search_articles("germany")

    assert waits == [1.0]


async def test_a_persistently_rate_limited_request_surfaces_as_an_upstream_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_wait(seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_wait)
    client = TransportClient(
        [
            _FakeResponse(429, headers={"retry-after": "30"}),
            _FakeResponse(429, headers={"retry-after": "30"}),
        ]
    )

    with pytest.raises(WikipediaError, match="upstream busy"):
        await client.search_articles("germany")


def test_a_retry_after_date_is_understood() -> None:
    when = datetime.now(timezone.utc) + timedelta(seconds=12)
    response = _FakeResponse(429, headers={"retry-after": format_datetime(when)})

    delay = _retry_delay(response, default=1.0)

    assert 10 <= delay <= 13


def test_a_retry_after_date_already_in_the_past_does_not_wait() -> None:
    when = datetime.now(timezone.utc) - timedelta(seconds=30)
    response = _FakeResponse(429, headers={"retry-after": format_datetime(when)})

    assert _retry_delay(response, default=1.0) == 0.0


def test_an_unreadable_retry_after_falls_back_instead_of_failing_the_request() -> None:
    # A header is never worth losing a request over.
    assert _retry_delay(_FakeResponse(429, headers={"retry-after": "soon"}), default=1.0) == 1.0
    assert _retry_delay(_FakeResponse(429, headers={}), default=1.0) == 1.0
    assert _retry_delay(_FakeResponse(429, headers={"retry-after": "-5"}), default=1.0) == 0.0


# --- Reverse-link completeness ------------------------------------------------
# The one-way check reads a target's outgoing links and asks whether the seed is among
# them. MediaWiki caps a property query at 500 links without the `apihighlimits` right, so
# a longer target has a tail the request cannot reach. Reporting the short read as if it
# were the whole set produced a verifiable accusation with no evidence behind it.


def _links_page(page_id: int, *titles: str) -> dict:
    return {"query": {"pages": [{"pageid": page_id, "links": [{"title": t} for t in titles]}]}}


def _links_page_with_continue(page_id: int, token: str, *titles: str) -> dict:
    # The continuation token sits at the top level of the response in formatversion=2,
    # not inside `query`.
    payload = _links_page(page_id, *titles)
    payload["continue"] = {"plcontinue": token, "continue": "||"}
    return payload


async def test_a_target_whose_links_fit_in_one_page_is_complete() -> None:
    client = StubClient(_links_page(2, "Ada Lovelace", "Engine"))

    result = await client.get_links_for_page_ids([2])

    assert result[2].complete is True
    assert result[2].titles == {"ada lovelace", "engine"}


async def test_reverse_links_paginate_past_the_first_page() -> None:
    client = SequencedStubClient(
        [
            _links_page_with_continue(2, "123|abc", "Ada Lovelace"),
            _links_page(2, "Engine"),
        ]
    )

    result = await client.get_links_for_page_ids([2])

    # The token was followed, so a reverse link on the second page is still found.
    assert client.requests[1]["plcontinue"] == "123|abc"
    assert result[2].titles == {"ada lovelace", "engine"}
    assert result[2].complete is True


async def test_a_target_longer_than_the_cap_is_reported_incomplete() -> None:
    # 500 links is all an anonymous client can be given. The first page fills the cap and
    # a continuation says more exist, so the 501st is real and was not seen.
    first = [{"title": f"Link {n}"} for n in range(500)]
    client = SequencedStubClient(
        [
            {
                "query": {"pages": [{"pageid": 2, "links": first}]},
                "continue": {"plcontinue": "500|xyz", "continue": "||"},
            },
            _links_page(2, "Link 500"),
        ]
    )

    result = await client.get_links_for_page_ids([2])

    assert len(result[2].titles) == 500
    assert "link 500" not in result[2].titles
    assert result[2].complete is False


async def test_a_target_with_exactly_the_cap_and_no_continuation_is_still_complete() -> None:
    # Being at the cap is not the same as having more than the cap. Only a link that had
    # to be dropped proves the answer is short.
    links = [{"title": f"Link {n}"} for n in range(500)]
    client = StubClient({"query": {"pages": [{"pageid": 2, "links": links}]}})

    result = await client.get_links_for_page_ids([2])

    assert len(result[2].titles) == 500
    assert result[2].complete is True


async def test_the_cap_is_configurable() -> None:
    client = SequencedStubClient(
        [
            _links_page_with_continue(2, "2|abc", "A", "B"),
            _links_page(2, "C"),
        ]
    )

    result = await client.get_links_for_page_ids([2], max_links_per_page=1)

    assert result[2].titles == {"a"}
    assert result[2].complete is False


async def test_a_continuation_that_returns_nothing_new_stops_the_loop() -> None:
    # Otherwise the loop spins forever holding a request and a concurrency slot.
    client = SequencedStubClient(
        [
            _links_page_with_continue(2, "9|zzz", "Ada Lovelace"),
            _links_page_with_continue(2, "9|zzz"),
        ]
    )

    with pytest.raises(WikipediaError, match="no new links"):
        await client.get_links_for_page_ids([2])


async def test_a_target_with_more_links_than_the_cap_is_unverified_not_a_failure() -> None:
    # Delhi has more than 500 main-namespace links, so the cap fills up and every
    # link in the following pages is dropped. That makes the continuation stall,
    # which used to be reported as a broken token and fail the whole analysis with
    # a 502 - for any article that links somewhere huge, which is most of them.
    # The honest answer is the one the cap was designed to produce: the page is
    # marked incomplete and the caller treats the target as unverified.
    client = SequencedStubClient(
        [
            _links_page_with_continue(2, "2|aaa", "A"),
            _links_page_with_continue(2, "2|bbb", "B"),
        ]
    )

    result = await client.get_links_for_page_ids([2], max_links_per_page=1)

    assert result[2].titles == {"a"}
    assert result[2].complete is False
    # It stopped on its own rather than asking for a page it could not use.
    assert len(client.requests) == 2


async def test_a_broken_token_is_still_an_error_when_no_cap_stopped_the_page() -> None:
    # The anti-spin guard must not be weakened into a silent short read: with no cap
    # involved, a token that returns nothing really is broken and the caller has to
    # hear about it rather than receive a set that looks complete.
    client = SequencedStubClient(
        [
            _links_page_with_continue(2, "9|zzz", "A", "B"),
            _links_page_with_continue(2, "9|zzz", "A", "B"),
        ]
    )

    with pytest.raises(WikipediaError, match="no new links"):
        await client.get_links_for_page_ids([2], max_links_per_page=50)

