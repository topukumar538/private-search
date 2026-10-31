import html

import httpx

from app.models import SearchResult
from app.sources.base import SearchSource

API_URL = "https://api.stackexchange.com/2.3/search/advanced"
MAX_RESULTS = 5


def count(number: int, word: str) -> str:
    """'1 answer', '2 answers', '0 answers'."""
    return f"{number} {word}" if number == 1 else f"{number} {word}s"


class StackExchangeSource(SearchSource):
    name = "stackoverflow"

    async def search(self, query: str, client: httpx.AsyncClient) -> list[SearchResult]:
        response = await client.get(
            API_URL,
            params={
                "q": query,
                "site": "stackoverflow",
                "sort": "relevance",
                "order": "desc",
                "pagesize": MAX_RESULTS,
            },
        )

        if response.status_code != 200:
            raise RuntimeError(f"Stack Exchange search failed: HTTP {response.status_code}")

        data = response.json()

        # Errors can also arrive in the body, e.g. when the daily quota runs out.
        if "error_id" in data:
            raise RuntimeError("Stack Exchange returned an API error.")

        return self.parse(data)

    def parse(self, data: dict) -> list[SearchResult]:
        items = []

        for item in data.get("items", []):
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("title"), str)
                or not isinstance(item.get("link"), str)
            ):
                continue

            title = html.unescape(item["title"])

            # Stack Exchange sends no text, so describe the question instead.
            parts = [
                count(item.get("score", 0), "vote"),
                count(item.get("answer_count", 0), "answer"),
            ]

            if "accepted_answer_id" in item:
                parts.append("accepted answer")

            tags = item.get("tags")
            if isinstance(tags, list):
                names = [tag for tag in tags if isinstance(tag, str)]
                if names:
                    parts.append(", ".join(names))

            items.append({
                "title": title,
                "url": item["link"],
                "snippet": " · ".join(parts),
            })

        return self.build_results(items)