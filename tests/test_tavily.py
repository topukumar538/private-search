import json

import pytest

from app.sources.tavily import TavilySource


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")


def result(title="Python", url="https://python.org", content="A language"):
    return {"title": title, "url": url, "content": content}


# ---------- normal cases ----------

def test_returns_results(network, api_key):
    network.respond({"results": [result()]})

    results = network.search(TavilySource())

    assert len(results) == 1
    assert results[0].title == "Python"
    assert results[0].url == "https://python.org"
    assert results[0].snippet == "A language"
    assert results[0].source == "tavily"


def test_sends_key_and_query(network, api_key):
    network.respond({"results": []})

    network.search(TavilySource(), query="rust language")

    request = network.requests[0]
    body = json.loads(request.content)
    assert request.headers["Authorization"] == "Bearer test-key"
    assert body["query"] == "rust language"
    assert body["include_answer"] is False


# ---------- edge cases ----------

def test_item_without_title_is_skipped_not_fatal(network, api_key):
    # The old code used item["title"] and crashed the whole source here.
    network.respond({"results": [
        result(title="Good 1"),
        {"url": "https://example.com/no-title", "content": "x"},
        result(title="Good 2"),
    ]})

    results = network.search(TavilySource())

    assert [r.title for r in results] == ["Good 1", "Good 2"]


def test_missing_content_becomes_empty_snippet(network, api_key):
    network.respond({"results": [{"title": "T", "url": "https://example.com"}]})

    results = network.search(TavilySource())

    assert results[0].snippet == ""


def test_unsafe_url_is_skipped(network, api_key):
    network.respond({"results": [result(url="javascript:alert(1)")]})

    assert network.search(TavilySource()) == []


def test_missing_results_key_gives_empty_list(network, api_key):
    network.respond({})

    assert network.search(TavilySource()) == []


# ---------- failure cases ----------

def test_missing_api_key_raises_before_any_request(network, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        network.search(TavilySource())

    assert network.requests == []


def test_http_error_raises(network, api_key):
    network.respond(status=401)

    with pytest.raises(RuntimeError, match="401"):
        network.search(TavilySource())