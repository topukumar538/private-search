"""Run the real app with fake search sources, for load testing.

Why fake sources: a load test against the live APIs would burn API quota,
could break their terms of use, and would mostly measure THEIR speed.
This measures OUR server: routing, validation, the orchestrator,
deduplication, ranking and JSON responses, under many users at once.

Each fake source waits a random, realistic time and sometimes fails,
so partial-failure paths are exercised too.

Usage (from the project root):
    python loadtest/stub_server.py
"""

import asyncio
import os
import random

import uvicorn

from app.main import app
from app.models import SearchResult
from app.services import search as search_module
from app.sources.base import SearchSource

FAILURE_RATE = 0.05


class FakeSource(SearchSource):
    name = "fake"

    def __init__(self, name: str, min_delay: float, max_delay: float):
        self.name = name
        self.min_delay = min_delay
        self.max_delay = max_delay

    async def search(self, query, client):
        await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))

        if random.random() < FAILURE_RATE:
            raise RuntimeError("simulated provider failure")

        # Five results each; two URLs overlap across sources, like real engines.
        return [
            SearchResult(
                title=f"{query} result {i}",
                url=f"https://example{i}.com/{self.name if i > 2 else 'shared'}",
                snippet="A realistic snippet length for a search result. " * 3,
                source=self.name,
            )
            for i in range(1, 6)
        ]


# Delays roughly match what real providers took in manual testing.
search_module.SOURCES[:] = [
    FakeSource("tavily", 0.6, 1.5),
    FakeSource("wikipedia", 0.2, 0.6),
]

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        log_level="warning",
    )