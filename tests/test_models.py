import pytest
from pydantic import ValidationError

from app.models import SearchResult


def make(**overrides):
    data = {
        "title": "Python",
        "url": "https://example.com/python",
        "snippet": "A programming language.",
        "source": "wikipedia",
    }
    data.update(overrides)
    return SearchResult(**data)


# ---------- normal cases ----------

def test_valid_result_keeps_its_values():
    result = make()

    assert result.title == "Python"
    assert result.url == "https://example.com/python"
    assert result.snippet == "A programming language."
    assert result.source == "wikipedia"


def test_snippet_is_optional_and_defaults_to_empty():
    result = SearchResult(title="T", url="https://example.com", source="tavily")

    assert result.snippet == ""


def test_model_dump_gives_a_plain_dict():
    # The rest of the pipeline still works with dicts for now.
    assert make().model_dump() == {
        "title": "Python",
        "url": "https://example.com/python",
        "snippet": "A programming language.",
        "source": "wikipedia",
    }


# ---------- edge cases ----------

def test_whitespace_is_stripped():
    result = make(title="  Python  ", snippet="\n text \n")

    assert result.title == "Python"
    assert result.snippet == "text"


def test_url_is_not_rewritten():
    # Normalizing is deduplication's job, so the model leaves URLs alone.
    url = "HTTPS://Example.com/Path?utm_source=x"

    assert make(url=url).url == url


def test_result_cannot_be_changed_after_creation():
    result = make()

    with pytest.raises(ValidationError):
        result.title = "Changed"


# ---------- failure cases ----------

@pytest.mark.parametrize("title", ["", "   "])
def test_empty_title_is_rejected(title):
    with pytest.raises(ValidationError):
        make(title=title)


@pytest.mark.parametrize(
    "url",
    ["ftp://example.com/file", "javascript:alert(1)", "example.com", "https://", ""],
)
def test_non_web_url_is_rejected(url):
    with pytest.raises(ValidationError):
        make(url=url)


def test_missing_required_field_is_rejected():
    with pytest.raises(ValidationError):
        SearchResult(title="T", url="https://example.com")