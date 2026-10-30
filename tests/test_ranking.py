import pytest

from app.services.ranking import rank_results


def make_result(url, **source_ranks):
    return {"title": "Example", "url": url, "source_ranks": source_ranks}


# ---------- score ----------

def test_score_for_one_source():
    ranked = rank_results([make_result("https://a.com/", tavily=1)])

    assert ranked[0]["score"] == pytest.approx(1 / 61)


def test_score_adds_up_across_sources():
    ranked = rank_results([make_result("https://a.com/", tavily=1, wikipedia=3)])

    assert ranked[0]["score"] == pytest.approx(1 / 61 + 1 / 63)


# ---------- order ----------

def test_results_found_by_more_sources_rank_higher():
    # B is never ranked first, but two sources agree on it.
    results = [
        make_result("https://a.com/", tavily=1),
        make_result("https://b.com/", tavily=3, wikipedia=3),
    ]

    ranked = rank_results(results)

    assert [r["url"] for r in ranked] == ["https://b.com/", "https://a.com/"]


def test_better_rank_wins_with_same_number_of_sources():
    results = [
        make_result("https://a.com/", tavily=2),
        make_result("https://b.com/", tavily=1),
    ]

    ranked = rank_results(results)

    assert [r["url"] for r in ranked] == ["https://b.com/", "https://a.com/"]


def test_ties_are_broken_by_url():
    # Given in reverse order, so the test fails if the tie-break is missing.
    results = [
        make_result("https://b.com/", tavily=1),
        make_result("https://a.com/", tavily=1),
    ]

    ranked = rank_results(results)

    assert [r["url"] for r in ranked] == ["https://a.com/", "https://b.com/"]


# ---------- output shape ----------

def test_keeps_original_fields_and_adds_score():
    ranked = rank_results([make_result("https://a.com/", tavily=1)])

    assert ranked[0]["title"] == "Example"
    assert ranked[0]["url"] == "https://a.com/"
    assert ranked[0]["source_ranks"] == {"tavily": 1}
    assert "score" in ranked[0]


def test_does_not_change_the_input():
    results = [make_result("https://a.com/", tavily=1)]

    rank_results(results)

    assert "score" not in results[0]


def test_empty_list_returns_empty_list():
    assert rank_results([]) == []


# ---------- everything together ----------

RESULTS = [
    {"title": "Page A", "url": "https://a.com/", "source_ranks": {"tavily": 1}},
    {"title": "Page B", "url": "https://b.com/", "source_ranks": {"tavily": 2, "wikipedia": 2}},
    {"title": "Page C", "url": "https://c.com/", "source_ranks": {"wikipedia": 1}},
    {"title": "Page D", "url": "https://d.com/", "source_ranks": {"tavily": 3, "wikipedia": 1}},
]


def test_full_ranking_scenario():
    # D: 1/63 + 1/61 = 0.032266   B: 2/62 = 0.032258
    # A and C: 1/61 each, so the URL decides.
    ranked = rank_results(RESULTS)

    assert [r["url"] for r in ranked] == [
        "https://d.com/",
        "https://b.com/",
        "https://a.com/",
        "https://c.com/",
    ]