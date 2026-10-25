import json

import pytest

from app.sources.wikipedia import WikipediaSource, remove_html


def search_payload(*items):
    return {"query": {"search": list(items)}}


# ---------- normal cases ----------

def test_returns_results_with_article_urls(network):
    network.respond(search_payload({"title": "Python", "snippet": "A language"}))

    results = network.search(WikipediaSource())

    assert len(results) == 1
    assert results[0].title == "Python"
    assert results[0].url == "https://en.wikipedia.org/wiki/Python"
    assert results[0].source == "wikipedia"


def test_sends_query_and_user_agent(network):
    network.respond(search_payload())

    network.search(WikipediaSource(), query="rust language")

    request = network.requests[0]
    assert request.url.params["srsearch"] == "rust language"
    assert request.headers["User-Agent"].startswith("PrivateSearch/")


# ---------- edge cases ----------

def test_title_spaces_and_special_characters_are_encoded(network):
    network.respond(search_payload({"title": "C++ (language)", "snippet": ""}))

    results = network.search(WikipediaSource())

    assert results[0].url == "https://en.wikipedia.org/wiki/C%2B%2B_%28language%29"


def test_snippet_html_is_removed_and_entities_decoded():
    snippet = '<span class="searchmatch">Python</span> &amp; friends'

    assert remove_html(snippet) == "Python & friends"


def test_missing_or_wrong_type_snippet_becomes_empty(network):
    network.respond(search_payload(
        {"title": "No snippet"},
        {"title": "Number snippet", "snippet": 42},
    ))

    results = network.search(WikipediaSource())

    assert [r.snippet for r in results] == ["", ""]


def test_bad_items_are_skipped(network):
    network.respond(search_payload(
        {"title": "Good"},
        {"snippet": "no title"},
        "not a dict",
        {"title": 123},
    ))

    results = network.search(WikipediaSource())

    assert [r.title for r in results] == ["Good"]


def test_no_matches_gives_empty_list(network):
    network.respond(search_payload())

    assert network.search(WikipediaSource()) == []


# ---------- failure cases ----------

def test_http_error_raises(network):
    network.respond(status=503)

    with pytest.raises(RuntimeError, match="503"):
        network.search(WikipediaSource())


def test_api_error_raises(network):
    network.respond({"error": {"code": "badvalue"}})

    with pytest.raises(RuntimeError):
        network.search(WikipediaSource())


def test_invalid_json_raises(network):
    network.respond(text="not json")

    with pytest.raises(json.JSONDecodeError):
        network.search(WikipediaSource())