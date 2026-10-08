from html.parser import HTMLParser
from urllib.parse import quote

import httpx

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def remove_html(value: str) -> str:
    parser = TextExtractor()
    parser.feed(value)
    return "".join(parser.parts)


async def search_wikipedia(query: str) -> list[dict]:
    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://en.wikipedia.org/w/api.php",
            headers={
                "User-Agent": "PrivateSearch/0.1 (Personal search project)",
            },
        
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 5,
                "format": "json",
                "srprop": "snippet",
            },
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Wikipedia search failed: HTTP {response.status_code}"
            )

        data = response.json()

    if "error" in data:
        raise RuntimeError("Wikipedia returned an API error.")

    results = []

    for item in data.get("query", {}).get("search", []):
        page_title = quote(item["title"].replace(" ", "_"), safe="")

        results.append({
            "title": item["title"],
            "url": f"https://en.wikipedia.org/wiki/{page_title}",
            "snippet": remove_html(item.get("snippet", "")),
            "source": "wikipedia",
        })

    return results