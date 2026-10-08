import asyncio

from app.services.deduplication import remove_duplicates
from app.services.ranking import rank_results
from app.sources.base import SearchSource
from app.sources.tavily import TavilySource
from app.sources.wikipedia import WikipediaSource

SOURCE_TIMEOUT = 5.0

# Every source the app can use. Adding a source means adding it here.
SOURCES: list[SearchSource] = [TavilySource(), WikipediaSource()]


async def search_all(query: str, sources: list[SearchSource] | None = None) -> dict:
    # Tests pass fake sources; the app uses the real ones.
    if sources is None:
        sources = SOURCES

    responses = await asyncio.gather(
        *(asyncio.wait_for(source.search(query), timeout=SOURCE_TIMEOUT) for source in sources),
        return_exceptions=True,
    )

    results = []
    failed_sources = []

    for source, response in zip(sources, responses):
        if isinstance(response, Exception):
            failed_sources.append(source.name)
            continue

        for rank, result in enumerate(response, start=1):
            results.append({**result.model_dump(), "rank": rank})

    if len(failed_sources) == len(sources):
        raise RuntimeError("All search sources failed.")

    results = remove_duplicates(results)
    results = rank_results(results)

    return {
        "results": results,
        "returned_count": len(results),
        "partial": bool(failed_sources),
        "failed_sources": failed_sources,
    }