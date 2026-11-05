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
from app.sources.stackexchange import StackExchangeSource

from app.services.cache import SearchCache
from app.services.circuit_breaker import CircuitBreaker, CircuitOpenError

# Recent complete answers, shared by every search. Memory only.
cache = SearchCache()

# One circuit breaker per source name, created the first time it's needed.
breakers: dict[str, CircuitBreaker] = {}

logger = logging.getLogger(__name__)

# Hard cap on one source call, however its time is spent.
SOURCE_TIMEOUT = 5.0

# Every source the app can use. Adding a source means adding it here.
SOURCES: list[SearchSource] = [TavilySource(), WikipediaSource(), StackExchangeSource()]


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
    breaker = breakers.setdefault(source.name, CircuitBreaker())

    if not breaker.allow_request():
        logger.warning("source=%s status=skipped reason=circuit_open", source.name)
        raise CircuitOpenError(source.name)

    start = time.perf_counter()

    try:
        results = await asyncio.wait_for(source.search(query, client), timeout=SOURCE_TIMEOUT)
    except asyncio.CancelledError:
        breaker.record_cancelled()
        raise
    except Exception as error:
        breaker.record_failure()
        logger.warning(
            "source=%s status=error error=%s duration_ms=%d",
            source.name,
            type(error).__name__,
            elapsed_ms(start),
        )
        raise

    breaker.record_success()
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

    # A recent identical search: answer from memory, ask no provider.
    cached = cache.get(query)
    if cached is not None:
        logger.info("status=cache_hit")
        return {**cached, "cached": True}

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

    response = {
        "results": results,
        "returned_count": len(results),
        "sources_asked": [source.name for source in sources],
        "partial": bool(failed_sources),
        "failed_sources": failed_sources,
    }

    # Only complete answers are kept: one failed source must not be
    # missing from everyone's results for the next 5 minutes.
    if not failed_sources:
        cache.set(query, response)

    return {**response, "cached": False}