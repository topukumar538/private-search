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


def test_cache_cleaner_removes_expired_searches_while_app_runs(monkeypatch):
    import time

    from app import main as main_module
    from app.services.cache import SearchCache

    now = [0.0]
    cache = SearchCache(ttl_seconds=300, clock=lambda: now[0])
    cache.set("old search", {"results": []})
    now[0] = 300                                   # it has expired
    monkeypatch.setattr(search_module, "cache", cache)
    monkeypatch.setattr(main_module, "CACHE_CLEANUP_SECONDS", 0.01)

    with TestClient(app):
        time.sleep(0.2)                            # let the cleaner run

    assert len(cache) == 0

# ---------- rate limiting ----------

def test_eleventh_search_in_a_minute_gets_429(client, monkeypatch):
    use_sources(monkeypatch, WorkingSource())

    codes = [client.post("/api/search", json={"query": f"q{i}"}).status_code for i in range(11)]

    assert codes == [200] * 10 + [429]


def test_429_says_how_long_to_wait(client, monkeypatch):
    use_sources(monkeypatch, WorkingSource())
    for i in range(10):
        client.post("/api/search", json={"query": f"q{i}"})

    response = client.post("/api/search", json={"query": "one more"})

    assert int(response.headers["Retry-After"]) > 0
    assert "Too many searches" in response.json()["detail"]


def test_different_visitors_have_separate_limits(client, monkeypatch):
    use_sources(monkeypatch, WorkingSource())
    for i in range(10):
        client.post("/api/search", json={"query": f"q{i}"}, headers={"CF-Connecting-IP": "1.1.1.1"})

    response = client.post("/api/search", json={"query": "x"}, headers={"CF-Connecting-IP": "2.2.2.2"})

    assert response.status_code == 200


def test_changing_x_forwarded_for_does_not_bypass_the_limit(client, monkeypatch):
    use_sources(monkeypatch, WorkingSource())

    # A bot sends a different X-Forwarded-For each time; Cloudflare's header stays the same.
    codes = [
        client.post(
            "/api/search",
            json={"query": f"q{i}"},
            headers={"CF-Connecting-IP": "5.5.5.5", "X-Forwarded-For": f"10.0.0.{i}, 104.22.0.{i}"},
        ).status_code
        for i in range(11)
    ]

    assert codes[-1] == 429


def test_raw_ip_is_never_stored(client, monkeypatch):
    from app import main as main_module

    use_sources(monkeypatch, WorkingSource())
    client.post("/api/search", json={"query": "x"}, headers={"CF-Connecting-IP": "103.45.67.89"})

    assert "103.45.67.89" not in str(main_module.rate_limiter._windows)


def test_searches_answered_from_cache_do_not_count(client, monkeypatch):
    use_sources(monkeypatch, WorkingSource())
    client.post("/api/search", json={"query": "python"})          # 1 counted, now cached

    repeats = [client.post("/api/search", json={"query": "python"}).status_code for _ in range(30)]

    assert repeats == [200] * 30                                    # none of these counted


def test_new_searches_still_count_after_cached_ones(client, monkeypatch):
    use_sources(monkeypatch, WorkingSource())
    for i in range(10):
        client.post("/api/search", json={"query": f"q{i}"})        # 10 counted: limit reached

    cached = client.post("/api/search", json={"query": "q0"})      # answered from the cache
    new = client.post("/api/search", json={"query": "something new"})

    assert cached.status_code == 200
    assert new.status_code == 429