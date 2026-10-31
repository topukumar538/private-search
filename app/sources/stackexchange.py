import html

import httpx

from app.models import SearchResult
from app.sources.base import SearchSource

API_URL = "https://api.stackexchange.com/2.3/search/advanced"
MAX_RESULTS = 5


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
                f"{item.get('score', 0)} votes",
                f"{item.get('answer_count', 0)} answers",
            ]

            if "accepted_answer_id" in item:
                parts.append("accepted answer")

            tags = item.get("tags", [])
            if tags:
                parts.append(", ".join(tags))

            items.append({
                "title": title,
                "url": item["link"],
                "snippet": " · ".join(parts),
            })

        return self.build_results(items)