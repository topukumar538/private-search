import asyncio

import pytest

from app.models import SearchResult
from app.sources.base import SearchSource


class FakeSource(SearchSource):
    """A source that returns fixed data, so tests never touch the network."""

    name = "fake"

    def __init__(self, items):
        self.items = items

    async def search(self, query: str) -> list[SearchResult]:
        return self.build_results(self.items)


def item(title="Python", url="https://example.com/python", snippet="Text"):
    return {"title": title, "url": url, "snippet": snippet}


# ---------- the contract ----------

def test_base_class_cannot_be_used_directly():
    with pytest.raises(TypeError):
        SearchSource()


def test_source_without_search_method_cannot_be_created():
    class NoSearch(SearchSource):
        name = "no-search"

    with pytest.raises(TypeError):
        NoSearch()


def test_source_without_name_is_rejected_when_defined():
    with pytest.raises(TypeError, match="name"):

        class NoName(SearchSource):
            async def search(self, query):
                return []


def test_fake_source_returns_results_through_the_interface():
    source = FakeSource([item()])

    results = asyncio.run(source.search("python"))

    assert len(results) == 1
    assert isinstance(results[0], SearchResult)


# ---------- build_results: normal cases ----------

def test_build_results_sets_source_name_automatically():
    results = FakeSource([]).build_results([item()])

    assert results[0].source == "fake"


def test_build_results_keeps_order():
    items = [item(title="First"), item(title="Second"), item(title="Third")]

    results = FakeSource([]).build_results(items)

    assert [r.title for r in results] == ["First", "Second", "Third"]


# ---------- build_results: edge and failure cases ----------

def test_one_bad_item_does_not_lose_the_good_ones():
    items = [
        item(title="Good 1"),
        item(title=""),                          # empty title
        item(title="Good 2"),
        item(url="javascript:alert(1)"),         # unsafe URL
        {"title": "No URL"},                     # missing field
        item(title=None),                        # wrong type
        item(title="Good 3"),
    ]

    results = FakeSource([]).build_results(items)

    assert [r.title for r in results] == ["Good 1", "Good 2", "Good 3"]


def test_item_cannot_pretend_to_be_another_source():
    # A provider's data must never override which source it came from.
    results = FakeSource([]).build_results([{**item(), "source": "wikipedia"}])

    assert results == []


def test_extra_provider_fields_are_ignored():
    results = FakeSource([]).build_results([{**item(), "score": 0.9}])

    assert len(results) == 1


def test_empty_input_gives_empty_list():
    assert FakeSource([]).build_results([]) == []