import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import SearchResult
from app.services import search as search_module
from app.sources.base import SearchSource


class WorkingSource(SearchSource):
    name = "working"

    async def search(self, query, client):
        return [SearchResult(title="Result", url="https://example.com/", source=self.name)]


class BrokenSource(SearchSource):
    name = "broken"

    async def search(self, query, client):
        raise RuntimeError("down")


@pytest.fixture
def client():
    # "with" runs the app's startup and shutdown, like a real server.
    with TestClient(app) as test_client:
        yield test_client


def use_sources(monkeypatch, *sources):
    monkeypatch.setattr(search_module, "SOURCES", list(sources))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_shared_http_client_exists_while_running(client):
    assert app.state.http_client.is_closed is False


def test_shared_http_client_is_closed_at_shutdown():
    with TestClient(app):
        http_client = app.state.http_client

    assert http_client.is_closed is True


def test_search_returns_results(client, monkeypatch):
    use_sources(monkeypatch, WorkingSource())

    response = client.post("/api/search", json={"query": "python"})

    assert response.status_code == 200
    assert response.json()["results"][0]["sources"] == ["working"]


def test_responses_are_never_cached(client, monkeypatch):
    use_sources(monkeypatch, WorkingSource())

    response = client.post("/api/search", json={"query": "python"})

    assert response.headers["Cache-Control"] == "no-store"


def test_all_sources_failing_gives_502_without_details(client, monkeypatch):
    use_sources(monkeypatch, BrokenSource())

    response = client.post("/api/search", json={"query": "python"})

    assert response.status_code == 502
    assert "down" not in response.text


@pytest.mark.parametrize("query", ["", "   ", "x" * 501])
def test_invalid_queries_are_rejected(client, query):
    response = client.post("/api/search", json={"query": query})

    assert response.status_code == 422