import os

import httpx
from dotenv import load_dotenv

from app.models import SearchResult
from app.sources.base import SearchSource

load_dotenv()

API_URL = "https://api.tavily.com/search"
MAX_RESULTS = 5


class TavilySource(SearchSource):
    name = "tavily"

    async def search(self, query: str, client: httpx.AsyncClient) -> list[SearchResult]:
        # Read the key on every search, so a missing key fails only this source.
        api_key = os.getenv("TAVILY_API_KEY")

        if not api_key:
            raise RuntimeError("TAVILY_API_KEY is not set.")

        response = await client.post(
            API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "query": query,
                "search_depth": "basic",
                "max_results": MAX_RESULTS,
                "auto_parameters": False,
                "include_answer": False,
                "include_raw_content": False,
            },
        )

        if response.status_code != 200:
            raise RuntimeError(f"Tavily search failed: HTTP {response.status_code}")

        return self.parse(response.json())

    def parse(self, data: dict) -> list[SearchResult]:
        items = []

        for item in data.get("results", []):
            if not isinstance(item, dict):
                continue

            # .get() instead of item["title"]: a missing field now skips one
            # result instead of failing the whole source.
            items.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("content") or "",
            })

        return self.build_results(items)