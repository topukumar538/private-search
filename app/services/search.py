import asyncio

from app.services.deduplication import remove_duplicates
from app.services.ranking import rank_results
from app.sources.tavily import search_tavily
from app.sources.wikipedia import search_wikipedia


SOURCE_TIMEOUT = 5.0


async def search_all(query: str) -> dict:
    sources = ["tavily", "wikipedia"]

    responses = await asyncio.gather(
        asyncio.wait_for(
            search_tavily(query),
            timeout=SOURCE_TIMEOUT,
        ),
        asyncio.wait_for(
            search_wikipedia(query),
            timeout=SOURCE_TIMEOUT,
        ),
        return_exceptions=True,
    )

    results = []
    failed_sources = []

    for source, response in zip(sources, responses):
        if isinstance(response, Exception):
            failed_sources.append(source)
            continue

        for rank, result in enumerate(response, start=1):
            results.append({
                **result,
                "source": source,
                "rank": rank,
            })

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