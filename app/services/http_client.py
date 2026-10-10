import httpx

HTTP_TIMEOUT = httpx.Timeout(4.0)

HTTP_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20)


def create_http_client() -> httpx.AsyncClient:
    """The one HTTP client the whole app shares."""
    return httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        limits=HTTP_LIMITS,
        follow_redirects=False,
    )
