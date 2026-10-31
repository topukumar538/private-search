import pytest
from app.sources.stackexchange import StackExchangeSource


def make_item(**overrides):
    item = {
        "title": "How to limit concurrency with Python asyncio?",
        "link": "https://stackoverflow.com/questions/48483348",
        "score": 160,
        "answer_count": 11,
        "accepted_answer_id": 48484593,
        "tags": ["python", "python-asyncio"],
    }
    item.update(overrides)
    return item


def parse(*items):
    return StackExchangeSource().parse({"items": list(items)})


# ---------- normal case ----------

def test_parses_title_link_and_builds_snippet():
    results = parse(make_item())

    assert len(results) == 1
    assert results[0].title == "How to limit concurrency with Python asyncio?"
    assert results[0].url == "https://stackoverflow.com/questions/48483348"
    assert results[0].snippet == "160 votes · 11 answers · accepted answer · python, python-asyncio"
    assert results[0].source == "stackoverflow"


def test_keeps_api_order():
    results = parse(
        make_item(link="https://stackoverflow.com/questions/1"),
        make_item(link="https://stackoverflow.com/questions/2"),
    )

    assert [r.url for r in results] == [
        "https://stackoverflow.com/questions/1",
        "https://stackoverflow.com/questions/2",
    ]


# ---------- cleaning ----------

def test_decodes_html_entities_in_title():
    results = parse(make_item(title="Why doesn&#39;t &quot;await&quot; work?"))

    assert results[0].title == "Why doesn't \"await\" work?"


def test_no_accepted_answer_and_no_tags():
    item = make_item(tags=[])
    del item["accepted_answer_id"]

    results = parse(item)

    assert results[0].snippet == "160 votes · 11 answers"


def test_missing_counts_default_to_zero():
    item = make_item()
    del item["score"]
    del item["answer_count"]

    results = parse(item)

    assert results[0].snippet.startswith("0 votes · 0 answers")


# ---------- bad data ----------

def test_skips_bad_items_and_keeps_good_ones():
    good = make_item()

    results = parse(
        "not a dict",
        make_item(title=None),
        make_item(link=None),
        {"title": "No link at all"},
        make_item(link="javascript:alert(1)"),
        good,
    )

    assert [r.url for r in results] == [good["link"]]


def test_missing_or_empty_items_returns_empty_list():
    source = StackExchangeSource()

    assert source.parse({}) == []
    assert source.parse({"items": []}) == []

# ---------- search(): the network part ----------

def test_sends_query_and_search_settings(network):
    network.respond({"items": []})

    network.search(StackExchangeSource(), query="python asyncio timeout")

    request = network.requests[0]
    assert request.method == "GET"
    assert request.url.host == "api.stackexchange.com"
    assert request.url.params["q"] == "python asyncio timeout"
    assert request.url.params["site"] == "stackoverflow"
    assert request.url.params["sort"] == "relevance"
    assert request.url.params["pagesize"] == "5"


def test_search_returns_parsed_results(network):
    network.respond({"items": [make_item()]})

    results = network.search(StackExchangeSource())

    assert [r.url for r in results] == ["https://stackoverflow.com/questions/48483348"]


def test_http_error_raises(network):
    network.respond(status=503)

    with pytest.raises(RuntimeError):
        network.search(StackExchangeSource())


def test_api_error_in_body_raises(network):
    # Stack Exchange can report errors with HTTP 200, e.g. when out of quota.
    network.respond({"error_id": 502, "error_name": "throttle_violation"})

    with pytest.raises(RuntimeError):
        network.search(StackExchangeSource())


def test_invalid_json_raises(network):
    network.respond(text="not json")

    with pytest.raises(ValueError):
        network.search(StackExchangeSource())


# ---------- search(): the network part ----------


def test_one_vote_and_one_answer_are_singular():
    results = parse(make_item(score=1, answer_count=1))

    assert results[0].snippet.startswith("1 vote · 1 answer ·")


def test_bad_tags_are_ignored_not_fatal():
    results = parse(
        make_item(tags=["python", None, 42]),
        make_item(link="https://stackoverflow.com/questions/2", tags="python"),
    )

    assert results[0].snippet.endswith("accepted answer · python")
    assert results[1].snippet.endswith("accepted answer")