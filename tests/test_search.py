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

    assert names == ["tavily", "wikipedia"]
    assert len(names) == len(set(names))