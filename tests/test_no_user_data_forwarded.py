import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import search as search_module
from app.sources.stackexchange import StackExchangeSource
from app.sources.tavily import TavilySource
from app.sources.wikipedia import WikipediaSource

# Details a real user's browser would send. None may reach a provider.
USER_HEADERS = {
    "User-Agent": "SecretBrowser/1.0 (Windows 11)",
    "Cookie": "session=user-secret-cookie",
    "Accept-Language": "bn-BD",
    "X-Forwarded-For": "103.45.67.89",
    "Referer": "https://my-private-page.example/",
}

# The only headers our server ever sends to a provider. Anything else fails.
ALLOWED_HEADERS = {
    "host", "accept", "accept-encoding", "connection", "user-agent",
    "authorization", "content-type", "content-length",  # Tavily: API key and JSON body
}


@pytest.mark.parametrize(
    "source",
    [WikipediaSource(), StackExchangeSource(), TavilySource()],
    ids=lambda source: source.name,
)
def test_only_the_query_leaves_the_server(network, monkeypatch, source):
    # Setup: one source, connected to the fake internet.
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(search_module, "SOURCES", [source])

    with TestClient(app) as client:
        app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(network._handle))

        # 1. Submit a query, like a user's browser.
        client.post("/api/search", json={"query": "python"}, headers=USER_HEADERS)

    # 2. Catch what went outside: URL, headers and body.
    outgoing = network.requests[0]
    sent = str(outgoing.url) + str(dict(outgoing.headers)) + outgoing.content.decode()

    # 3. Check it.
    assert "python" in sent                                     # the query went out
    assert set(outgoing.headers.keys()) <= ALLOWED_HEADERS      # only allowed headers
    for value in USER_HEADERS.values():
        assert value not in sent                                # nothing about the user