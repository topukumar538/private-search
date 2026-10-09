from html.parser import HTMLParser
from urllib.parse import quote

import httpx

from app.models import SearchResult
from app.services.snippets import clean_snippet
from app.sources.base import SearchSource

API_URL = "https://en.wikipedia.org/w/api.php"
ARTICLE_URL = "https://en.wikipedia.org/wiki/"
USER_AGENT = "PrivateSearch/0.1 (Personal search project)"
MAX_RESULTS = 5


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def remove_html(value: str) -> str:
    """Keep only the text of an HTML fragment (also decodes &amp; etc.)."""
    parser = TextExtractor()
    parser.feed(value)
    parser.close()
    return "".join(parser.parts)


class WikipediaSource(SearchSource):
    name = "wikipedia"

    async def search(self, query: str, client: httpx.AsyncClient) -> list[SearchResult]:
        response = await client.get(
            API_URL,
            headers={"User-Agent": USER_AGENT},
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": MAX_RESULTS,
                "srprop": "snippet",
                "format": "json",
            },
        )

        if response.status_code != 200:
            raise RuntimeError(f"Wikipedia search failed: HTTP {response.status_code}")

        data = response.json()

        if "error" in data:
            raise RuntimeError("Wikipedia returned an API error.")

        return self.parse(data)

    def parse(self, data: dict) -> list[SearchResult]:
        items = []

        for item in data.get("query", {}).get("search", []):
            if not isinstance(item, dict) or not isinstance(item.get("title"), str):
                continue

            title = item["title"]
            page = quote(title.replace(" ", "_"), safe="")
            snippet = item.get("snippet")

            items.append({
                "title": title,
                "url": ARTICLE_URL + page,
                "snippet": clean_snippet(remove_html(snippet)) if isinstance(snippet, str) else "",
            })

        return self.build_results(items)