import pytest

from app.services.snippets import MAX_SNIPPET_LENGTH, clean_snippet


# ---------- normal cases ----------

def test_short_plain_text_is_unchanged():
    assert clean_snippet("A cryptographic protocol.") == "A cryptographic protocol."


def test_markdown_headings_are_removed():
    text = "## How Does TLS Work? It uses keys."

    assert clean_snippet(text) == "How Does TLS Work? It uses keys."


def test_heading_in_the_middle_is_removed():
    assert clean_snippet("Intro. ### Details here") == "Intro. Details here"


def test_bold_and_italic_marks_are_removed():
    assert clean_snippet("This is **very** *important*.") == "This is very important."


def test_bracketed_ellipsis_becomes_one_character():
    assert clean_snippet("first part [...] second part") == "first part … second part"


def test_newlines_and_repeated_spaces_collapse():
    assert clean_snippet("line one\n\n  line   two\t end") == "line one line two end"


# ---------- edge cases ----------

def test_long_text_is_cut_at_a_word_boundary_with_ellipsis():
    text = "word " * 100

    snippet = clean_snippet(text)

    assert len(snippet) <= MAX_SNIPPET_LENGTH + 1
    assert snippet.endswith("word…")


def test_text_exactly_at_the_limit_is_not_cut():
    text = "a" * MAX_SNIPPET_LENGTH

    assert clean_snippet(text) == text


def test_cut_does_not_leave_trailing_punctuation_before_ellipsis():
    text = "Short sentence, " + "x" * 400

    assert clean_snippet(text, max_length=30) == "Short sentence…"


def test_hash_inside_words_is_kept():
    # "C#" and "#1" are content, not markdown headings.
    assert clean_snippet("Learn C# and rank #1 today") == "Learn C# and rank #1 today"


@pytest.mark.parametrize("text", ["", "   ", "\n\n", "## "])
def test_empty_or_only_markup_gives_empty_string(text):
    assert clean_snippet(text) == ""