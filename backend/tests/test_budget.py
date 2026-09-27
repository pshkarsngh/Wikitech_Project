"""C6/C7: a request that runs out of time, or whose client has gone, stops working.

Two different things are being pinned down here, and they are tested separately on
purpose. The first half is the transport: the budget is checked at the one place
every Wikimedia request passes through, so an analysis cannot keep spending calls
after it should have stopped. The second half is what the pipeline and the routers
do with that stop, which is the part that decides whether a reader is told the
truth.

The distinction the whole module exists to protect: a *partial* answer is only
allowed to leave the building if it says it is partial. A list that was cut short
and a list that is genuinely empty are the same bytes, so a route that returns a
bare list has to fail rather than answer, and a route that returns a summary has to
mark it.

One thing to know before adding a test here. The budget is enforced in
`MediaWikiClient._api_get`, which is the only place a real request to Wikimedia is
made, and `FakeWikipediaClient` does not go through it - it returns canned
responses directly. A test that injects the fake therefore never sees a deadline
fire, no matter how long it makes the fake wait, and an end-to-end "this request
times out" test built on it will hang rather than fail. That is why
`_AbortingClient` below raises `AnalysisAborted` itself: the budget's job is to
produce that exception, and the pipeline's job is to handle it, so the tests cover
each half where it lives. Measured against the real client, a budget of 2s with a
20s per-request timeout aborts at 2.0s with one attempt made.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import classifier
from app.services.analysis import analyze_article
from app.services.budget import (
    DEADLINE,
    DISCONNECT,
    AnalysisAborted,
    AnalysisBudget,
    budget_scope,
    current_budget,
    request_timeout,
)
from tests.fake_wikipedia import ADA, ENGINE, LONDON, NOVEL, VILLAGE, FakeWikipediaClient
from tests.test_mediawiki import TransportClient, _FakeResponse


# ---------------------------------------------------------------------------
# the budget itself
# ---------------------------------------------------------------------------


async def test_budget_reports_no_stop_reason_while_there_is_time() -> None:
    budget = AnalysisBudget(deadline_seconds=60.0)
    assert await budget.stop_reason() is None


async def test_budget_reports_a_deadline_once_it_has_passed() -> None:
    # A zero deadline stops before any work, which is what a test or an operator
    # setting it to 0 means, so the comparison has to be `<=` and not `<`.
    budget = AnalysisBudget(deadline_seconds=0.0)
    assert await budget.stop_reason() == DEADLINE
    with pytest.raises(AnalysisAborted) as raised:
        await budget.check()
    assert raised.value.reason == DEADLINE


async def test_budget_reports_a_disconnect() -> None:
    async def gone() -> bool:
        return True

    budget = AnalysisBudget(deadline_seconds=60.0, is_disconnected=gone)
    assert await budget.stop_reason() == DISCONNECT
    with pytest.raises(AnalysisAborted) as raised:
        await budget.check()
    assert raised.value.reason == DISCONNECT


async def test_the_clock_is_consulted_before_the_disconnect_probe() -> None:
    # Not a preference. A blown deadline is a fact we already know, and paying for
    # an await on the receive channel to discover it anyway would let a hung peer
    # delay the answer to an already-doomed request.
    calls: list[int] = []

    async def counting_probe() -> bool:
        calls.append(1)
        return False

    budget = AnalysisBudget(deadline_seconds=0.0, is_disconnected=counting_probe)
    assert await budget.stop_reason() == DEADLINE
    assert calls == []


async def test_budget_scope_unsets_the_budget_afterwards() -> None:
    # The scope has to clean up. A budget left in the context would apply to the
    # next request served by the same worker task, and that request's deadline
    # would be measured from when this one started.
    assert current_budget() is None
    with budget_scope(AnalysisBudget(deadline_seconds=60.0)):
        assert current_budget() is not None
    assert current_budget() is None


def test_request_timeout_leaves_the_caller_s_timeout_alone_without_a_budget() -> None:
    # `None` here means "no budget", so the client's own `http_timeout_seconds`
    # stays in charge. Every test, `smoke_live` and the scripts depend on this.
    assert current_budget() is None
    assert request_timeout(20.0) == 20.0


def test_request_timeout_never_exceeds_the_callers_own_timeout() -> None:
    # `min`, so a generous `http_timeout_seconds` cannot become a reason to
    # overrun a deadline that is nearly spent.
    with budget_scope(AnalysisBudget(deadline_seconds=600.0)):
        assert request_timeout(20.0) == 20.0


def test_request_timeout_clamps_to_the_remaining_budget() -> None:
    with budget_scope(AnalysisBudget(deadline_seconds=0.05)):
        assert request_timeout(20.0) < 1.0


def test_request_timeout_stays_positive_once_the_deadline_has_passed() -> None:
    # A negative timeout is not a short wait, it is a value `asyncio.timeout`
    # rejects outright, which would turn an expired budget into a crash instead of
    # a clean abort.
    with budget_scope(AnalysisBudget(deadline_seconds=0.0)):
        assert request_timeout(20.0) > 0.0


async def test_a_budget_does_not_leak_into_a_concurrent_task() -> None:
    # The load-bearing assumption of the whole design. The MediaWiki client is one
    # shared instance, so the budget cannot live on it; it travels in a ContextVar
    # instead, and that only isolates requests if the two do not see each other.
    async def run(deadline: float) -> float:
        with budget_scope(AnalysisBudget(deadline_seconds=deadline)):
            await asyncio.sleep(0)
            assert current_budget() is not None
            return current_budget().deadline_seconds

    first, second = await asyncio.gather(run(11.0), run(22.0))
    assert (first, second) == (11.0, 22.0)
    assert current_budget() is None


# ---------------------------------------------------------------------------
# the transport: the one chokepoint
# ---------------------------------------------------------------------------


class _FlippableBudget(AnalysisBudget):
    """A budget whose deadline can be made to pass on demand.

    Expiring it from a fake transport is deterministic, where a real sleep would
    make the test depend on how fast the machine running it is.
    """

    def __init__(self) -> None:  # noqa: D107 - no super().__init__()
        self.deadline_seconds = 3600.0
        self.is_disconnected = None
        self._started = 0.0
        self.passed = False

    def expired(self) -> bool:
        return self.passed


async def test_no_budget_means_no_limit() -> None:
    # The default outside a request. Every test that does not care about time must
    # keep working, and `smoke_live` and the scripts run this way.
    assert current_budget() is None
    client = TransportClient([_FakeResponse(200, {"query": {"pages": []}})])
    assert await client._api_get({"action": "query"}) == {"query": {"pages": []}}


async def test_an_expired_budget_stops_the_request_before_it_is_sent() -> None:
    budget = _FlippableBudget()
    budget.passed = True
    client = TransportClient([_FakeResponse(200, {"query": {"pages": []}})])

    with budget_scope(budget), pytest.raises(AnalysisAborted) as raised:
        await client._api_get({"action": "query"})

    assert raised.value.reason == DEADLINE
    # Nothing was sent. The point of checking first is that a request that is
    # already doomed does not spend one more call on the shared Wikimedia budget.
    assert client.transport.requests == []


async def test_a_deadline_that_passes_mid_request_stops_the_caller() -> None:
    # The response arrived in time to be useful and too late to be the answer.
    # Reporting it anyway would let the analysis keep building on a request that
    # arrived after it was supposed to stop.
    budget = _FlippableBudget()
    client = TransportClient([_FakeResponse(200, {"query": {"pages": []}})])

    async def expire_during_the_call(url, *, params) -> _FakeResponse:
        budget.passed = True
        return _FakeResponse(200, {"query": {"pages": []}})

    client.transport.get = expire_during_the_call

    with budget_scope(budget), pytest.raises(AnalysisAborted) as raised:
        await client._api_get({"action": "query"})

    assert raised.value.reason == DEADLINE


async def test_the_deadline_bounds_a_request_that_is_already_in_flight() -> None:
    # The check sits at the `_api_get` boundary, so without a per-request bound a
    # request that has already started runs to its own 20s timeout before anyone
    # notices the deadline. That makes the real ceiling
    # `deadline + http_timeout_seconds` - at the shipped defaults, exactly nginx's
    # `proxy_read_timeout`, so the proxy would give up at the same moment and the
    # reader would get a bare 502 instead of the partial result and its marker.
    budget = AnalysisBudget(deadline_seconds=0.05)
    client = TransportClient([_FakeResponse(200, {"query": {"pages": []}})])

    async def slow(url, *, params) -> _FakeResponse:
        await asyncio.sleep(30)
        return _FakeResponse(200, {"query": {"pages": []}})

    client.transport.get = slow

    loop = asyncio.get_running_loop()
    started = loop.time()
    with budget_scope(budget), pytest.raises(AnalysisAborted) as raised:
        await client._api_get({"action": "query"})

    # Asserted as a generous upper bound, not an exact duration: the point is that
    # it is bounded by the budget and not by the 30s the transport would have taken.
    assert loop.time() - started < 5.0
    assert raised.value.reason == DEADLINE


async def test_a_timeout_with_time_to_spare_is_not_a_deadline() -> None:
    # The converse of the case above, and the reason `_api_get` tells them apart
    # instead of merging them: a request that times out with minutes left on the
    # budget is Wikimedia being slow. That is a 502 blaming upstream and it is
    # worth a retry, not this deployment giving up, and turning it into an abort
    # would make a slow upstream look like a short deadline.
    budget = AnalysisBudget(deadline_seconds=600.0)
    with budget_scope(budget):
        try:
            async with asyncio.timeout(request_timeout(600.0)):
                raise TimeoutError
        except TimeoutError:
            live = current_budget()
            assert live is not None
            assert not live.expired(), "600s of budget cannot be gone"
        # Which is the condition `_api_get` branches on, asserted directly here
        # rather than through a transport that would have to sleep for 30s.
        assert current_budget() is not None and not current_budget().expired()


async def test_a_deadline_during_retry_backoff_stops_the_second_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The backoff sleeps, so the deadline can pass while waiting, and a retry that
    # is already doomed is one more request to a service that just refused us.
    monkeypatch.setattr("app.services.mediawiki._RETRY_BACKOFF_SECONDS", 0.0)
    budget = _FlippableBudget()
    client = TransportClient(
        [
            _FakeResponse(429),
            _FakeResponse(200, {"query": {"pages": []}}),
        ]
    )

    async def refuse_then_expire(url, *, params) -> _FakeResponse:
        client.transport.requests.append(dict(params))
        budget.passed = True
        return _FakeResponse(429)

    client.transport.get = refuse_then_expire

    with budget_scope(budget), pytest.raises(AnalysisAborted):
        await client._api_get({"action": "query"})

    assert len(client.transport.requests) == 1


# ---------------------------------------------------------------------------
# the pipeline: what an aborted analysis is allowed to say
# ---------------------------------------------------------------------------


class _AbortingClient(FakeWikipediaClient):
    """A fake client that stops at a chosen stage, the way the transport does.

    `FakeWikipediaClient` does not go through `_api_get`, so it cannot exercise the
    budget itself. It stands in for a transport that did, which is enough to pin
    down what the pipeline and the routers do once the stop has happened.
    """

    def __init__(self, *, at: str, reason: str = DEADLINE) -> None:
        super().__init__()
        self.at = at
        self.reason = reason
        self.wikidata_calls: list[str] = []

    def _maybe_abort(self, stage: str) -> None:
        if self.at == stage:
            raise AnalysisAborted(self.reason)

    async def get_article(self, title: str, *, include_extract: bool = True):
        self._maybe_abort("article")
        return await super().get_article(title, include_extract=include_extract)

    async def get_article_links(self, title: str, *, max_links: int | None = None):
        self._maybe_abort("graph")
        return await super().get_article_links(title, max_links=max_links)

    async def get_page_descriptions(self, page_ids) -> dict[int, str]:
        self._maybe_abort("classify")
        return await super().get_page_descriptions(page_ids)

    async def get_links_for_page_ids(self, page_ids, **kwargs):
        self._maybe_abort("one_way")
        return await super().get_links_for_page_ids(page_ids, **kwargs)

    async def wikidata_descriptions(self, term: str) -> str | None:
        self.wikidata_calls.append(term)
        return await super().wikidata_descriptions(term)


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url="")


async def test_a_deadline_during_classification_keeps_the_resolved_links(
    settings: Settings,
) -> None:
    # The link graph is resolved before anything optional runs, so the part a
    # reader cannot do without survives. What is lost is the entity types, and the
    # summary has to say that rather than report zero people.
    client = _AbortingClient(at="classify")
    result = await analyze_article(client, settings, ADA)

    assert result.summary.aborted is True
    assert result.summary.abort_reason == DEADLINE
    assert result.summary.entity_types_incomplete is True
    # Real findings, not zeros: the article's links and its missing targets.
    assert result.summary.total_missing > 0
    assert [item.title for item in result.missing_connections]
    assert result.summary.total_articles > 0


async def test_a_deadline_during_the_one_way_check_keeps_the_entity_types(
    settings: Settings,
) -> None:
    # Classification finished, so the entity breakdown is real. Only the one-way
    # stage is missing, and `entity_types_incomplete` must not be raised for it.
    client = _AbortingClient(at="one_way")
    result = await analyze_article(client, settings, ADA)

    assert result.summary.aborted is True
    assert result.summary.entity_types_incomplete is False
    assert result.summary.total_people + result.summary.total_places > 0
    # The one-way list is empty because it never ran, which is not the same as an
    # article that has no one-way links, so it is flagged as unchecked.
    assert result.summary.one_way_targets_checked == 0
    assert result.summary.one_way_truncated is True


async def test_a_deadline_before_the_graph_exists_is_not_a_partial_result(
    settings: Settings,
) -> None:
    # There is nothing to be honest about yet: no article, no links. Returning an
    # empty summary here would be the "partial answer as complete answer" case in
    # its purest form.
    client = _AbortingClient(at="graph")
    with pytest.raises(AnalysisAborted) as raised:
        await analyze_article(client, settings, ADA)
    assert raised.value.reason == DEADLINE


async def test_a_disconnect_never_produces_a_partial_result(
    settings: Settings,
) -> None:
    # Even after the graph is complete. There is no longer a client to read the
    # answer, and building one spends the rest of the budget for nothing.
    for stage in ("classify", "one_way"):
        client = _AbortingClient(at=stage, reason=DISCONNECT)
        with pytest.raises(AnalysisAborted) as raised:
            await analyze_article(client, settings, ADA)
        assert raised.value.reason == DISCONNECT


async def test_a_complete_analysis_is_not_marked_aborted(settings: Settings) -> None:
    client = FakeWikipediaClient()
    result = await analyze_article(client, settings, ADA)

    assert result.summary.aborted is False
    assert result.summary.abort_reason is None
    assert result.summary.entity_types_incomplete is False
    assert result.summary.one_way_truncated is False


# ---------------------------------------------------------------------------
# the routes: a cut-short list is a 504, not an empty answer
# ---------------------------------------------------------------------------


def _client_for(app, fake: FakeWikipediaClient) -> TestClient:
    app.state.settings = Settings(database_url="")
    app.state.wikipedia = fake
    return TestClient(app)


def test_analyze_returns_the_partial_result_and_marks_it() -> None:
    app = create_app()
    client = _client_for(app, _AbortingClient(at="classify"))

    response = client.post("/api/analyze", json={"title": ADA})

    # 200, because the article's real links and missing connections are in there.
    assert response.status_code == 200
    assert response.json()["summary"]["aborted"] is True
    assert response.json()["summary"]["abort_reason"] == DEADLINE
    assert response.headers["X-Cache"] == "miss"


def test_an_analyzed_partial_result_is_never_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Storing it would serve the subset to whoever asks next, for the whole TTL,
    # with nothing in the payload to explain why it is short.
    stored: list[str] = []
    monkeypatch.setattr(
        "app.repository.store_analysis",
        lambda result, **kwargs: stored.append(result.article.title),
    )
    app = create_app()
    client = _client_for(app, _AbortingClient(at="classify"))

    client.post("/api/analyze", json={"title": ADA})

    assert stored == []


def test_a_complete_result_is_still_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    # The other half of the rule, so the fix above cannot be "never cache".
    stored: list[str] = []
    monkeypatch.setattr(
        "app.repository.store_analysis",
        lambda result, **kwargs: stored.append(result.article.title),
    )
    app = create_app()
    client = _client_for(app, FakeWikipediaClient())

    client.post("/api/analyze", json={"title": ADA})

    assert stored == [ADA]


def test_analyze_before_the_graph_is_a_gateway_timeout() -> None:
    app = create_app()
    client = _client_for(app, _AbortingClient(at="graph"))

    response = client.post("/api/analyze", json={"title": ADA})

    assert response.status_code == 504
    assert "did not finish" in response.json()["detail"]


def test_analyze_with_a_disconnected_client_is_a_gateway_timeout() -> None:
    app = create_app()
    client = _client_for(app, _AbortingClient(at="one_way", reason=DISCONNECT))

    assert client.post("/api/analyze", json={"title": ADA}).status_code == 504


@pytest.mark.parametrize(
    ("path", "params", "at"),
    [
        # The stage that stops is the last one each route reaches, which is the
        # point at which a partial answer would otherwise have been returned.
        ("/api/connections/missing", {"title": ADA}, "classify"),
        ("/api/connections/one-way", {"title": ADA}, "one_way"),
        ("/api/connections/map", {"title": ADA}, "one_way"),
    ],
)
def test_a_connection_route_never_answers_with_a_cut_short_list(
    path: str, params: dict[str, str], at: str
) -> None:
    # Each of these returns a bare list. A list that was cut short is
    # indistinguishable from a complete one once it has left the building, so the
    # only honest options are a marked partial or a failure, and there is nowhere
    # in a bare list to put the mark.
    app = create_app()
    client = _client_for(app, _AbortingClient(at=at))

    response = client.get(path, params=params)

    assert response.status_code == 504
    assert response.json() != []


def test_a_connection_route_still_fails_loudly_before_the_graph() -> None:
    app = create_app()
    client = _client_for(app, _AbortingClient(at="graph"))

    assert client.get("/api/connections/missing", params={"title": ADA}).status_code == 504


# ---------------------------------------------------------------------------
# the duplicate classification the map route used to pay for
# ---------------------------------------------------------------------------


def test_the_map_route_classifies_each_missing_name_once() -> None:
    # `classify_links` already types the missing names. The map route used to call
    # `detect_missing_connections` as well, which classifies them again, at one
    # Wikidata request per name - the most expensive waste this app can make, on
    # the request it documents as its most expensive.
    fake = _AbortingClient(at="nothing")
    app = create_app()
    client = _client_for(app, fake)

    response = client.get("/api/connections/map", params={"title": ADA})

    assert response.status_code == 200
    missing = [item["label"] for item in response.json()["nodes"] if not item["exists"]]
    assert missing
    assert sorted(fake.wikidata_calls) == sorted(set(fake.wikidata_calls))
    assert len(fake.wikidata_calls) == len(missing)


def test_the_missing_route_classifies_each_missing_name_once() -> None:
    fake = _AbortingClient(at="nothing")
    app = create_app()
    client = _client_for(app, fake)

    response = client.get("/api/connections/missing", params={"title": ADA})

    assert response.status_code == 200
    assert len(fake.wikidata_calls) == len(response.json())
    assert sorted(fake.wikidata_calls) == sorted(set(fake.wikidata_calls))


async def test_an_aborted_lookup_is_not_recorded_as_an_untyped_name() -> None:
    # `classify_titles` treats a failed lookup as best effort and carries on, which
    # is right for a name it cannot type. It is wrong for a deadline: the carry-on
    # is one more request to Wikidata for a result nobody is waiting for, and the
    # name would be recorded as "other" - a finding - when nothing was looked up.
    class _Cancelling:
        async def wikidata_descriptions(self, term: str) -> str:
            raise AnalysisAborted(DEADLINE)

    with pytest.raises(AnalysisAborted):
        await classifier.classify_titles(
            _Cancelling(), [NOVEL, VILLAGE], Settings(database_url="")
        )
