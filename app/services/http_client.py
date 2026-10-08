import httpx

# Each phase of a request (connect, read, ...) may take up to 4 seconds.
# The orchestrator also caps a whole source call at SOURCE_TIMEOUT (5 s),
# so a slow source normally fails here first, with a clear httpx error.
HTTP_TIMEOUT = httpx.Timeout(4.0)

# Upper bounds on open connections, so a traffic spike cannot open
# thousands of sockets to the search providers.
HTTP_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20)


def create_http_client() -> httpx.AsyncClient:
    """The one HTTP client the whole app shares."""
    return httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        limits=HTTP_LIMITS,
        follow_redirects=False,
    )