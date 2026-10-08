import os

import httpx
from dotenv import load_dotenv

load_dotenv()


async def search_tavily(query: str) -> list[dict]:
    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is missing from .env.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
                "auto_parameters": False,
                "include_answer": False,
                "include_raw_content": False,
            },
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Tavily search failed: HTTP {response.status_code}"
            )

        data = response.json()

    results = []

    for item in data.get("results", []):
        results.append({
            "title": item["title"],
            "url": item["url"],
            "snippet": item.get("content", ""),
            "source": "tavily",
        })

    return results