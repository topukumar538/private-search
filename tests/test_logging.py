import asyncio
import logging

import pytest

from app.models import SearchResult
from app.services import search as search_module
from app.services.logging_config import QUIET_LOGGERS, configure_logging
from app.services.search import search_all
from app.sources.base import SearchSource
from app.sources.wikipedia import WikipediaSource

SECRET_QUERY = "my private medical question"


def make_source(source_name, error=None, delay=0.0):
    class Fake(SearchSource):
        name = source_name

        async def search(self, query, client):
            await asyncio.sleep(delay)
            if error:
                # Simulate an error whose message contains the query.
                raise error(f"request failed for {query}")
            return [SearchResult(title="T", url="https://example.com/", source=source_name)]

    return Fake()


def run(*sources):
    return asyncio.run(search_all(SECRET_QUERY, client=None, sources=list(sources)))


def all_log_text(caplog):
    return "\n".join(record.getMessage() for record in caplog.records)


@pytest.fixture
def logs(caplog):
    caplog.set_level(logging.INFO)
    return caplog


# ---------- what IS logged ----------

def test_successful_source_is_logged_with_count_and_timing(logs):
    run(make_source("good"))

    text = all_log_text(logs)
    assert "source=good status=ok results=1" in text
    assert "duration_ms=" in text


def test_failed_source_is_logged_with_error_type(logs):
    run(make_source("good"), make_source("bad", error=ConnectionError))

    record = next(r for r in logs.records if "source=bad" in r.getMessage())
    assert record.levelno == logging.WARNING
    assert "error=ConnectionError" in record.getMessage()


def test_timeout_is_logged_as_timeout(logs, monkeypatch):
    monkeypatch.setattr(search_module, "SOURCE_TIMEOUT", 0.05)

    run(make_source("good"), make_source("slow", delay=1.0))

    assert "source=slow status=error error=TimeoutError" in all_log_text(logs)


def test_all_sources_failing_is_logged_as_error(logs):
    with pytest.raises(RuntimeError):
        run(make_source("bad", error=RuntimeError))

    assert any(
        r.levelno == logging.ERROR and "all_sources_failed" in r.getMessage()
        for r in logs.records
    )


# ---------- what is NEVER logged ----------

def test_query_never_appears_in_logs_on_success(logs):
    run(make_source("good"))

    assert SECRET_QUERY not in all_log_text(logs)


def test_query_never_appears_in_logs_even_when_error_message_contains_it(logs):
    run(make_source("good"), make_source("bad", error=RuntimeError))

    assert SECRET_QUERY not in all_log_text(logs)


# ---------- third-party loggers ----------

def test_httpx_would_leak_the_query_without_our_config(network, logs):
    # Negative control: proves the next test can actually detect a leak.
    httpx_logger = logging.getLogger("httpx")
    original_level = httpx_logger.level
    httpx_logger.setLevel(logging.INFO)

    try:
        network.respond({"query": {"search": []}})
        network.search(WikipediaSource(), query=SECRET_QUERY)
    finally:
        httpx_logger.setLevel(original_level)

    assert "my+private+medical+question" in all_log_text(logs)


def test_configured_logging_keeps_httpx_from_logging_the_query(network, logs):
    configure_logging()

    network.respond({"query": {"search": []}})
    network.search(WikipediaSource(), query=SECRET_QUERY)

    text = all_log_text(logs)
    assert "my+private+medical+question" not in text
    assert SECRET_QUERY not in text


def test_quiet_loggers_still_report_warnings():
    configure_logging()

    for name in QUIET_LOGGERS:
        assert logging.getLogger(name).getEffectiveLevel() == logging.WARNING