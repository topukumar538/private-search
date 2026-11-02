import asyncio

import pytest

from app.models import SearchResult
from app.services import search as search_module
from app.services.search import search_all
from app.sources.base import SearchSource


def make_source(source_name, urls=(), error=None, delay=0.0):
    """Build a fake source that returns the given URLs, or raises `error`."""

    class Fake(SearchSource):
        name = source_name

        async def search(self, query, client):
            await asyncio.sleep(delay)
            if error:
                raise error
            return [
                SearchResult(title=f"{source_name} {i}", url=url, source=source_name)
                for i, url in enumerate(urls, start=1)
            ]

    return Fake()


def run(sources):
    # Fake sources never use the network, so no real client is needed.
    return asyncio.run(search_all("query", client=None, sources=sources))


# ---------- normal cases ----------

def test_merges_results_from_all_sources():
    response = run([
        make_source("a", ["https://one.com/", "https://two.com/"]),
        make_source("b", ["https://three.com/"]),
    ])

    assert response["returned_count"] == 3
    assert response["partial"] is False
    assert response["failed_sources"] == []


def test_result_found_by_both_sources_ranks_first():
    response = run([
        make_source("a", ["https://only-a.com/", "https://shared.com/"]),
        make_source("b", ["https://only-b.com/", "https://shared.com/"]),
    ])

    top = response["results"][0]
    assert top["url"] == "https://shared.com/"
    assert top["sources"] == ["a", "b"]


# ---------- failure cases ----------

def test_one_failing_source_gives_partial_results():
    response = run([
        make_source("a", ["https://one.com/"]),
        make_source("b", error=RuntimeError("down")),
    ])

    assert response["returned_count"] == 1
    assert response["partial"] is True
    assert response["failed_sources"] == ["b"]


def test_all_sources_failing_raises():
    with pytest.raises(RuntimeError, match="All search sources failed"):
        run([
            make_source("a", error=RuntimeError("down")),
            make_source("b", error=ValueError("bad data")),
        ])


def test_slow_source_times_out_without_blocking_others(monkeypatch):
    monkeypatch.setattr(search_module, "SOURCE_TIMEOUT", 0.05)

    response = run([
        make_source("fast", ["https://fast.com/"]),
        make_source("slow", ["https://slow.com/"], delay=1.0),
    ])

    assert [r["url"] for r in response["results"]] == ["https://fast.com/"]
    assert response["failed_sources"] == ["slow"]


def test_source_returning_nothing_is_not_a_failure():
    response = run([
        make_source("a", ["https://one.com/"]),
        make_source("b", []),
    ])

    assert response["partial"] is False


def test_real_sources_are_registered_with_unique_names():
    names = [source.name for source in search_module.SOURCES]

    assert names == ["tavily", "wikipedia", "stackoverflow"]
    assert len(names) == len(set(names))


def test_response_lists_every_source_asked_even_if_it_found_nothing():
    response = run([
        make_source("a", ["https://one.com/"]),
        make_source("b", []),
        make_source("c", error=RuntimeError("down")),
    ])

    assert response["sources_asked"] == ["a", "b", "c"]


# ---------- cache ----------

def counting_source(source_name, error=None):
    """A fake source that remembers every query it was asked."""

    class Counting(SearchSource):
        name = source_name
        queries = []

        async def search(self, query, client):
            self.queries.append(query)
            if error:
                raise error
            return [SearchResult(title="T", url=f"https://{source_name}.com/", source=source_name)]

    return Counting()


def search(query, sources):
    return asyncio.run(search_all(query, client=None, sources=sources))


def test_repeated_search_is_answered_from_cache():
    source = counting_source("a")

    first = search("python", [source])
    second = search("python", [source])

    assert source.queries == ["python"]          # the provider was asked once
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["results"] == first["results"]


def test_cache_matches_case_but_providers_get_the_query_as_typed():
    source = counting_source("a")

    search("Python Asyncio", [source])
    second = search("python asyncio", [source])

    assert source.queries == ["Python Asyncio"]  # sent exactly as typed
    assert second["cached"] is True


def test_different_query_is_not_a_cache_hit():
    source = counting_source("a")

    search("python", [source])
    search("rust", [source])

    assert source.queries == ["python", "rust"]


def test_partial_results_are_not_cached():
    good = counting_source("good")
    bad = counting_source("bad", error=RuntimeError("down"))

    search("python", [good, bad])
    second = search("python", [good, bad])

    assert good.queries == ["python", "python"]  # asked again: nothing was stored
    assert second["cached"] is False