"""The shared analysis key: which routes ask for it, and what happens without one.

A separate module from `test_api.py` because the fixture here has to configure the key,
and `test_api.py`'s deliberately does not. The default is an open deployment, and these
tests are the only place that asserts the closed one works.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import require_analysis_key
from app.main import create_app
from tests.fake_wikipedia import ADA, FakeWikipediaClient

KEY = "correct-horse-battery-staple"

# The routes that fan out to Wikimedia. All four crawl, so all four are gated; a gate that
# missed one would leave the expensive path open, which is the entire point of the gate.
GATED = [
    ("post", "/api/analyze"),
    ("get", "/api/connections/missing"),
    ("get", "/api/connections/one-way"),
    ("get", "/api/connections/map"),
]

# The read routes. `/api/articles/resolve` calls Wikidata, so it is not free either, but it
# is a lookup behind the 60r/m read limit and gating it would lock a reader out of the
# search box. This test exists to make that exclusion a decision on the record rather than
# an accident: if someone adds the dependency to one of these, this fails.
UNGATED = [
    ("get", "/api/articles/search"),
    ("get", "/api/articles/find"),
    ("get", "/api/article"),
    ("get", "/api/article/links"),
    ("get", "/api/articles/resolve"),
]


def _client(key: str) -> TestClient:
    app = create_app()
    app.state.settings = Settings(database_url="", analysis_api_key=key)
    app.state.wikipedia = FakeWikipediaClient()
    return TestClient(app)


@pytest.fixture
def open_client() -> TestClient:
    return _client("")


@pytest.fixture
def gated_client() -> TestClient:
    return _client(KEY)


def _call(client: TestClient, method: str, path: str, **kwargs: object) -> int:
    return client.request(method, path, **kwargs).status_code


def test_an_unset_key_leaves_every_route_open(open_client: TestClient) -> None:
    """The default is open, exactly as an unset database is a normal state."""

    for method, path in GATED:
        assert _call(open_client, method, path, params={"title": ADA}, json={"title": ADA}) == 200


def test_health_says_a_key_is_not_required_when_there_is_none(
    open_client: TestClient,
) -> None:
    """A deployment that is accidentally open has to be able to notice."""

    assert open_client.get("/api/health").json()["auth_required"] is False


def test_health_says_a_key_is_required_when_one_is_configured(
    gated_client: TestClient,
) -> None:
    assert gated_client.get("/api/health").json()["auth_required"] is True


@pytest.mark.parametrize("method,path", GATED)
def test_a_crawl_route_without_a_key_is_refused(
    gated_client: TestClient, method: str, path: str
) -> None:
    response = gated_client.request(method, path, params={"title": ADA}, json={"title": ADA})
    assert response.status_code == 401


@pytest.mark.parametrize("method,path", GATED)
def test_a_crawl_route_with_the_right_key_answers(
    gated_client: TestClient, method: str, path: str
) -> None:
    response = gated_client.request(
        method,
        path,
        params={"title": ADA},
        json={"title": ADA},
        headers={"X-Api-Key": KEY},
    )
    assert response.status_code == 200


def test_a_wrong_key_is_refused(gated_client: TestClient) -> None:
    response = gated_client.post(
        "/api/analyze",
        json={"title": ADA},
        headers={"X-Api-Key": f"{KEY}-but-longer"},
    )
    assert response.status_code == 401


def test_a_key_that_is_a_prefix_of_the_real_one_is_refused(
    gated_client: TestClient,
) -> None:
    """Guards the compare: a caller must not be able to stop partway through."""

    response = gated_client.post(
        "/api/analyze", json={"title": ADA}, headers={"X-Api-Key": KEY[:10]}
    )
    assert response.status_code == 401


def test_an_empty_key_header_is_refused_not_accepted(
    gated_client: TestClient,
) -> None:
    """A deployment whose key is unset is open, so an empty header must not slip
    through as a match."""

    response = gated_client.post("/api/analyze", json={"title": ADA}, headers={"X-Api-Key": ""})
    assert response.status_code == 401


def test_a_key_of_only_spaces_does_not_gate_anything() -> None:
    """A key nobody can type must not lock the operator out of their own deployment."""

    client = _client("   ")
    assert client.get("/api/health").json()["auth_required"] is False
    assert _call(client, "post", "/api/analyze", json={"title": ADA}) == 200


def test_a_surrounding_space_in_the_configured_key_is_not_part_of_it() -> None:
    """The setting is stripped before comparison, so a stray newline in a `.env` or a
    secret manager does not produce a key no caller can reproduce."""

    client = _client(f"  {KEY}\n")
    response = client.post("/api/analyze", json={"title": ADA}, headers={"X-Api-Key": KEY})
    assert response.status_code == 200


def test_a_non_ascii_key_does_not_raise_from_the_comparison() -> None:
    """`compare_digest` only accepts ASCII, so the encode in the dependency is not
    optional. Called directly rather than over HTTP because httpx refuses to *send* a
    non-ASCII header value at all, so the transport cannot express this case - the
    TypeError would come from the comparison, and that is what is being guarded."""

    key = "schlüssel-🔑"
    require_analysis_key(Settings(analysis_api_key=key), key)
    with pytest.raises(HTTPException) as wrong:
        require_analysis_key(Settings(analysis_api_key=key), "something-else")
    assert wrong.value.status_code == 401


@pytest.mark.parametrize("method,path", UNGATED)
def test_a_read_route_stays_open_when_a_key_is_configured(
    gated_client: TestClient, method: str, path: str
) -> None:
    assert _call(gated_client, method, path, params={"title": ADA, "q": "ada", "titles": [ADA]}) == 200


def test_a_refused_crawl_costs_wikipedia_nothing(gated_client: TestClient) -> None:
    """The gate has to run before the crawl, not after it. If the key were checked once
    the graph was built, the request would still have spent 25-35 calls."""

    client = gated_client
    fake = client.app.state.wikipedia
    before = len(fake.link_calls) + len(fake.resolve_calls) + len(fake.reverse_calls)
    assert client.post("/api/analyze", json={"title": ADA}).status_code == 401
    after = len(fake.link_calls) + len(fake.resolve_calls) + len(fake.reverse_calls)
    assert after == before
