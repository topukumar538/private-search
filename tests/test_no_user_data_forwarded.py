import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services import search as search_module
from app.sources.wikipedia import WikipediaSource

# Details a real user's browser would send. None may reach a provider.
USER_HEADERS = {
    "User-Agent": "SecretBrowser/1.0 (Windows 11)",
    "Cookie": "session=user-secret-cookie",
    "Accept-Language": "bn-BD",
    "X-Forwarded-For": "103.45.67.89",
    "Referer": "https://my-private-page.example/",
}


def test_only_the_query_leaves_the_server(network, monkeypatch):
    # Setup: only Wikipedia, connected to the fake internet.
    monkeypatch.setattr(search_module, "SOURCES", [WikipediaSource()])
    network.respond({"query": {"search": [{"title": "Python"}]}})

    with TestClient(app) as client:
        app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(network._handle))

        # 1. Submit a query, like a user's browser.
        client.post("/api/search", json={"query": "python"}, headers=USER_HEADERS)

    # 2. Catch what went outside.
    outgoing = network.requests[0]
    sent = str(outgoing.url) + " " + str(dict(outgoing.headers))

    # 3. Check it.
    assert outgoing.url.params["srsearch"] == "python"                 # the query went out
    assert outgoing.headers["User-Agent"].startswith("PrivateSearch/")  # our app's name, not the user's
    for value in USER_HEADERS.values():
        assert value not in sent                                        # nothing about the user