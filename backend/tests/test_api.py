"""Route tests: the API is wired to the fake client instead of Wikipedia."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.mediawiki import WikipediaError
from tests.fake_wikipedia import ADA, ENGINE, LONDON, NOVEL, VILLAGE, FakeWikipediaClient


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    # The fake replaces the live MediaWiki client, so no request leaves the process.
    app.state.settings = Settings(database_url="")
    app.state.wikipedia = FakeWikipediaClient()
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "database_enabled": False,
    }


def test_search(client: TestClient) -> None:
    response = client.get("/api/articles/search", params={"q": "ada"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "ada"
    assert body["results"][0]["title"] == ADA


def test_get_article(client: TestClient) -> None:
    response = client.get("/api/article", params={"title": ADA})
    assert response.status_code == 200
    assert response.json()["page_id"] == 1


def test_find_article(client: TestClient) -> None:
    response = client.get("/api/articles/find", params={"q": "ada"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "ada"
    assert body["title"] == ADA
    assert body["page_id"] == 1
    assert body["url"] == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert body["extract"] == f"{ADA} is a test article."


def test_find_article_not_found(client: TestClient) -> None:
    response = client.get("/api/articles/find", params={"q": "Zzqx Nonexistent"})
    assert response.status_code == 404
    assert "No article found" in response.json()["detail"]


def test_find_article_rejects_empty_query(client: TestClient) -> None:
    assert client.get("/api/articles/find", params={"q": ""}).status_code == 422
    assert client.get("/api/articles/find", params={"q": "   "}).status_code == 422


def test_get_article_rejects_empty_title(client: TestClient) -> None:
    assert client.get("/api/article", params={"title": ""}).status_code == 422


def test_get_article_links(client: TestClient) -> None:
    response = client.get("/api/article/links", params={"title": ADA})
    assert response.status_code == 200
    body = response.json()
    assert body["total_links"] == 4
    assert {link["title"] for link in body["links"]} == {ENGINE, LONDON, NOVEL, VILLAGE}
    village = next(link for link in body["links"] if link["title"] == VILLAGE)
    assert village["exists"] is False
    assert village["entity_type"] == "place"


def test_get_article_links_returns_title_target_source_and_internality(
    client: TestClient,
) -> None:
    response = client.get("/api/article/links", params={"title": ADA})
    assert response.status_code == 200
    link = next(item for item in response.json()["links"] if item["title"] == ENGINE)

    assert link == {
        "title": ENGINE,
        "page_id": 2,
        "url": "https://en.wikipedia.org/wiki/Analytical_Engine",
        "exists": True,
        "state": "exists",
        "entity_type": "other",
        "source_title": ADA,
        "source_url": "https://en.wikipedia.org/wiki/Ada_Lovelace",
        "is_internal": True,
        "redirected": False,
    }


def test_analyze_returns_extracted_links(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"title": ADA})
    assert response.status_code == 200
    links = response.json()["links"]

    assert len(links) == 4
    assert {link["source_title"] for link in links} == {ADA}
    assert all(link["is_internal"] is True for link in links)
    assert {link["state"] for link in links} == {"exists", "missing"}


def test_check_articles_exist(client: TestClient) -> None:
    response = client.get(
        "/api/articles/resolve", params=[("titles", ENGINE), ("titles", NOVEL)]
    )
    assert response.status_code == 200
    body = response.json()
    assert body["missing"] == [NOVEL]
    assert body["titles"][0]["exists"] is True


def test_check_articles_exist_returns_structured_states(client: TestClient) -> None:
    response = client.get(
        "/api/articles/resolve", params=[("titles", ENGINE), ("titles", NOVEL)]
    )
    assert response.status_code == 200
    body = response.json()

    assert [item["requested"] for item in body["titles"]] == [ENGINE, NOVEL]
    assert [item["state"] for item in body["titles"]] == ["exists", "missing"]
    assert body["titles"][0]["url"] == (
        "https://en.wikipedia.org/wiki/Analytical_Engine"
    )
    assert body["titles"][1]["url"] is None
    assert body["titles"][1]["page_id"] is None


def test_existence_check_surfaces_an_upstream_failure() -> None:
    class FailingWikipedia(FakeWikipediaClient):
        async def resolve_titles(self, titles):
            raise WikipediaError("MediaWiki API error: maxlag")

    app = create_app()
    app.state.settings = Settings(database_url="")
    app.state.wikipedia = FailingWikipedia()

    with TestClient(app) as test_client:
        response = test_client.get("/api/articles/resolve", params={"titles": ENGINE})

    assert response.status_code == 502
    assert "maxlag" in response.json()["detail"]


def test_analyze(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"title": ADA})
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary == {
        "total_links": 4,
        "total_missing": 2,
        "total_one_way": 1,
        "one_way_targets_checked": 2,
        "one_way_truncated": False,
    }


def test_missing_connections(client: TestClient) -> None:
    response = client.get("/api/connections/missing", params={"title": ADA})
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert titles == [NOVEL, VILLAGE]


def test_one_way_connections(client: TestClient) -> None:
    response = client.get("/api/connections/one-way", params={"title": ADA})
    assert response.status_code == 200
    body = response.json()
    assert [item["target_title"] for item in body] == [LONDON]
    assert body[0]["links_back"] is False


def test_connection_map(client: TestClient) -> None:
    response = client.get("/api/connections/map", params={"title": ADA})
    assert response.status_code == 200
    body = response.json()
    assert body["article"]["title"] == ADA
    assert len(body["nodes"]) == 5
    assert len(body["edges"]) == 4
    statuses = {edge["status"] for edge in body["edges"]}
    assert statuses == {"missing", "one-way", "mutual"}


def test_missing_article_returns_404(client: TestClient) -> None:
    response = client.get("/api/connections/missing", params={"title": "Zzqx Nonexistent"})
    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


def test_missing_article_on_analyze_returns_404(client: TestClient) -> None:
    assert client.post("/api/analyze", json={"title": "Zzqx Nonexistent"}).status_code == 404
