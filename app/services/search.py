import asyncio
import logging
import time

import httpx

from app.models import SearchResult
from app.services.deduplication import remove_duplicates
from app.services.ranking import rank_results
from app.sources.base import SearchSource
from app.sources.tavily import TavilySource
from app.sources.wikipedia import WikipediaSource

logger = logging.getLogger(__name__)

# Hard cap on one source call, however its time is spent.
SOURCE_TIMEOUT = 5.0

# Every source the app can use. Adding a source means adding it here.
SOURCES: list[SearchSource] = [TavilySource(), WikipediaSource()]


async def run_source(
    source: SearchSource,
    query: str,
    client: httpx.AsyncClient,
) -> list[SearchResult]:
    """Call one source with a time limit, and log how it went.

    Privacy rule: logs record the source, outcome, timing and error TYPE,
    never the query and never the error message (messages can contain
    request URLs, and URLs can contain the query).
    """
    start = time.perf_counter()

    try:
        results = await asyncio.wait_for(source.search(query, client), timeout=SOURCE_TIMEOUT)
    except Exception as error:
        logger.warning(
            "source=%s status=error error=%s duration_ms=%d",
            source.name,
            type(error).__name__,
            elapsed_ms(start),
        )
        raise

    logger.info(
        "source=%s status=ok results=%d duration_ms=%d",
        source.name,
        len(results),
        elapsed_ms(start),
    )
    return results


def elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


async def search_all(
    query: str,
    client: httpx.AsyncClient,
    sources: list[SearchSource] | None = None,
) -> dict:
    # Tests pass fake sources; the app uses the real ones.
    if sources is None:
        sources = SOURCES

    responses = await asyncio.gather(
        *(run_source(source, query, client) for source in sources),
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
        logger.error("status=all_sources_failed sources=%d", len(sources))
        raise RuntimeError("All search sources failed.")

    results = remove_duplicates(results)
    results = rank_results(results)

    return {
        "results": results,
        "returned_count": len(results),
        "sources_asked": [source.name for source in sources],
        "partial": bool(failed_sources),
        "failed_sources": failed_sources,
    }