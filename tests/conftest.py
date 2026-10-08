import asyncio

import httpx
import pytest


class FakeNetwork:
    """Stands in for the internet: records requests, returns a set response."""

    def __init__(self):
        self.requests = []
        self.status = 200
        self.payload = {}
        self.text = None

    def respond(self, payload=None, status=200, text=None):
        self.payload = payload if payload is not None else {}
        self.status = status
        self.text = text

    def _handle(self, request):
        self.requests.append(request)

        if self.text is not None:
            return httpx.Response(self.status, text=self.text)

        return httpx.Response(self.status, json=self.payload)

    def search(self, source, query="python"):
        async def run():
            transport = httpx.MockTransport(self._handle)
            async with httpx.AsyncClient(transport=transport) as client:
                return await source.search(query, client)

        return asyncio.run(run())


@pytest.fixture
def network():
    return FakeNetwork()