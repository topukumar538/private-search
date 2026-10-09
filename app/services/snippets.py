import re

MAX_SNIPPET_LENGTH = 280

# Markdown leftovers some providers include: "## Heading", "**bold**", "[...]".
HEADING_MARKS = re.compile(r"(^|\s)#{1,6}\s+")
EMPHASIS_MARKS = re.compile(r"\*{1,3}|_{2,3}")
ELLIPSIS_MARKS = re.compile(r"\[\s*(\.\.\.|…)\s*\]")
WHITESPACE = re.compile(r"\s+")


def clean_snippet(text: str, max_length: int = MAX_SNIPPET_LENGTH) -> str:
    """Turn raw provider text into a short, plain, readable snippet."""
    text = HEADING_MARKS.sub(r"\1", text)
    text = EMPHASIS_MARKS.sub("", text)
    text = ELLIPSIS_MARKS.sub("…", text)
    text = WHITESPACE.sub(" ", text).strip()

    if len(text) <= max_length:
        return text

    # Cut at the last space before the limit, so no word is split.
    cut = text[:max_length].rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:-…") + "…"