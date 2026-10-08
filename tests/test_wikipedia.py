import asyncio
import json

import httpx
import pytest

from app.sources.wikipedia import WikipediaSource, remove_html


def fake_wikipedia(payload, status=200, seen=None):
    """A fake network that answers every request with the given JSON."""

    def handler(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=payload)

    return WikipediaSource(transport=httpx.MockTransport(handler))


def search_payload(*items):
    return {"query": {"search": list(items)}}


# ---------- normal cases ----------

def test_returns_results_with_article_urls():
    source = fake_wikipedia(search_payload({"title": "Python", "snippet": "A language"}))

    results = asyncio.run(source.search("python"))

    assert len(results) == 1
    assert results[0].title == "Python"
    assert results[0].url == "https://en.wikipedia.org/wiki/Python"
    assert results[0].source == "wikipedia"


def test_sends_query_and_user_agent():
    seen = []
    source = fake_wikipedia(search_payload(), seen=seen)

    asyncio.run(source.search("rust language"))

    request = seen[0]
    assert request.url.params["srsearch"] == "rust language"
    assert request.headers["User-Agent"].startswith("PrivateSearch/")


# ---------- edge cases ----------

def test_title_spaces_and_special_characters_are_encoded():
    source = fake_wikipedia(search_payload({"title": "C++ (language)", "snippet": ""}))

    results = asyncio.run(source.search("c++"))

    assert results[0].url == "https://en.wikipedia.org/wiki/C%2B%2B_%28language%29"


def test_snippet_html_is_removed_and_entities_decoded():
    snippet = '<span class="searchmatch">Python</span> &amp; friends'

    assert remove_html(snippet) == "Python & friends"


def test_missing_or_wrong_type_snippet_becomes_empty():
    source = fake_wikipedia(search_payload(
        {"title": "No snippet"},
        {"title": "Number snippet", "snippet": 42},
    ))

    results = asyncio.run(source.search("x"))

    assert [r.snippet for r in results] == ["", ""]


def test_bad_items_are_skipped():
    source = fake_wikipedia(search_payload(
        {"title": "Good"},
        {"snippet": "no title"},
        "not a dict",
        {"title": 123},
    ))

    results = asyncio.run(source.search("x"))

    assert [r.title for r in results] == ["Good"]


def test_no_matches_gives_empty_list():
    source = fake_wikipedia(search_payload())

    assert asyncio.run(source.search("zzzz")) == []


# ---------- failure cases ----------

def test_http_error_raises():
    source = fake_wikipedia({}, status=503)

    with pytest.raises(RuntimeError, match="503"):
        asyncio.run(source.search("python"))


def test_api_error_raises():
    source = fake_wikipedia({"error": {"code": "badvalue"}})

    with pytest.raises(RuntimeError):
        asyncio.run(source.search("python"))


def test_invalid_json_raises():
    source = WikipediaSource(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="not json"))
    )

    with pytest.raises(json.JSONDecodeError):
        asyncio.run(source.search("python"))