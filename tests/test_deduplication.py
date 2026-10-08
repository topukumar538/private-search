import pytest

from app.services.deduplication import normalize_url, remove_duplicates


def make_result(url, source="tavily", rank=1):
    return {"title": "Example", "url": url, "source": source, "rank": rank}


# ---------- normalize_url: normal cases ----------

def test_lowercases_scheme_and_host():
    assert normalize_url("HTTPS://Example.COM/Page") == "https://example.com/Page"


def test_keeps_path_case():
    # Paths are case-sensitive on most servers, so they must not change.
    assert normalize_url("https://example.com/ABC") == "https://example.com/ABC"


def test_empty_path_becomes_slash():
    assert normalize_url("https://example.com") == "https://example.com/"


# ---------- normalize_url: edge cases ----------

@pytest.mark.parametrize(
    "url, expected",
    [
        ("http://example.com:80/a", "http://example.com/a"),
        ("https://example.com:443/a", "https://example.com/a"),
        ("https://example.com:8443/a", "https://example.com:8443/a"),
    ],
)
def test_default_ports_removed_other_ports_kept(url, expected):
    assert normalize_url(url) == expected


def test_removes_tracking_parameters_and_keeps_others_in_order():
    url = "https://example.com/a?b=2&utm_source=x&a=1&gclid=y"
    assert normalize_url(url) == "https://example.com/a?b=2&a=1"


def test_tracking_parameter_names_are_case_insensitive():
    assert normalize_url("https://example.com/?UTM_Source=x") == "https://example.com/"


def test_decodes_unreserved_percent_encoding():
    # %7E is "~", which never needs encoding.
    assert normalize_url("https://example.com/%7Euser") == "https://example.com/~user"


def test_uppercases_reserved_percent_encoding():
    # %2f is "/", which must stay encoded, but in canonical uppercase.
    assert normalize_url("https://example.com/a%2fb") == "https://example.com/a%2Fb"


def test_ipv6_host_keeps_brackets():
    assert normalize_url("http://[::1]:8080/x") == "http://[::1]:8080/x"


# ---------- normalize_url: failure cases ----------

@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "javascript:alert(1)",
        "not a url",
        "https://",
    ],
)
def test_rejects_non_web_urls(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_rejects_urls_with_credentials():
    with pytest.raises(ValueError):
        normalize_url("https://user:pass@example.com/")


# ---------- remove_duplicates ----------

def test_same_url_from_two_sources_is_merged():
    results = [
        make_result("https://example.com/a", source="tavily", rank=2),
        make_result("https://EXAMPLE.com/a?utm_source=x", source="wikipedia", rank=1),
    ]

    merged = remove_duplicates(results)

    assert len(merged) == 1
    assert merged[0]["sources"] == ["tavily", "wikipedia"]
    assert merged[0]["source_ranks"] == {"tavily": 2, "wikipedia": 1}


def test_first_seen_result_keeps_its_title_and_url():
    results = [
        make_result("https://example.com/a", source="tavily"),
        {**make_result("https://example.com/a", source="wikipedia"), "title": "Other"},
    ]

    merged = remove_duplicates(results)

    assert merged[0]["title"] == "Example"
    assert merged[0]["url"] == "https://example.com/a"


def test_same_source_twice_keeps_best_rank():
    results = [
        make_result("https://example.com/a", source="tavily", rank=4),
        make_result("https://example.com/a", source="tavily", rank=2),
    ]

    merged = remove_duplicates(results)

    assert merged[0]["sources"] == ["tavily"]
    assert merged[0]["source_ranks"] == {"tavily": 2}


def test_different_urls_stay_separate_and_keep_order():
    results = [
        make_result("https://example.com/b"),
        make_result("https://example.com/a"),
    ]

    merged = remove_duplicates(results)

    assert [r["url"] for r in merged] == [
        "https://example.com/b",
        "https://example.com/a",
    ]


def test_invalid_or_missing_urls_are_skipped_not_crashing():
    results = [
        make_result("ftp://example.com/file"),
        make_result("https://user:pass@example.com/"),
        {"title": "No URL", "source": "tavily", "rank": 1},
        {**make_result("x"), "url": None},
        make_result("https://example.com/ok"),
    ]

    merged = remove_duplicates(results)

    assert [r["url"] for r in merged] == ["https://example.com/ok"]


def test_empty_input_returns_empty_list():
    assert remove_duplicates([]) == []