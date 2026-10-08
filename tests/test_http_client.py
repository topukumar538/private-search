import asyncio

from app.services import search as search_module
from app.services.http_client import create_http_client


def test_timeouts_are_set_for_every_phase():
    client = create_http_client()

    assert client.timeout.connect == 4.0
    assert client.timeout.read == 4.0


def test_http_timeout_is_shorter_than_source_timeout():
    # httpx should give up first, with a clear error, before the
    # orchestrator's hard cap cancels the call.
    client = create_http_client()

    assert client.timeout.read < search_module.SOURCE_TIMEOUT
    assert client.timeout.connect < search_module.SOURCE_TIMEOUT


def test_redirects_are_not_followed():
    assert create_http_client().follow_redirects is False


def test_client_closes_cleanly():
    async def open_and_close():
        async with create_http_client() as client:
            pass
        return client.is_closed

    assert asyncio.run(open_and_close()) is True