import re
from urllib.parse import unquote_plus, urlsplit, urlunsplit


TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
}

UNRESERVED = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789-._~"
)


def normalize_percent_encoding(value: str) -> str:
    def replace(match):
        encoded = match.group(0)
        character = chr(int(encoded[1:], 16))

        if character in UNRESERVED:
            return character

        return encoded.upper()

    return re.sub(r"%[0-9a-fA-F]{2}", replace, value)


def strip_tracking_query(query: str) -> str:
    """Remove tracking parameters from a query string.

    Keeps every other parameter, in its original order and encoding.
    """
    kept = []

    for parameter in query.split("&"):
        name = unquote_plus(parameter.split("=", 1)[0])

        if name.lower() not in TRACKING_PARAMETERS:
            kept.append(parameter)

    return "&".join(kept)


def normalize_url(url: str) -> str:
    parts = urlsplit(url)

    scheme = parts.scheme.lower()
    hostname = parts.hostname

    if scheme not in {"http", "https"} or not hostname:
        raise ValueError("Invalid web URL.")

    if parts.username is not None or parts.password is not None:
        raise ValueError("URLs containing credentials are unsupported.")

    hostname = hostname.lower()

    # IPv6 addresses must be enclosed in brackets.
    if ":" in hostname:
        hostname = f"[{hostname}]"

    port = parts.port
    is_default_port = (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    )

    netloc = hostname

    if port is not None and not is_default_port:
        netloc = f"{hostname}:{port}"

    query = strip_tracking_query(parts.query)
    path = normalize_percent_encoding(parts.path or "/")

    return urlunsplit((
        scheme,
        netloc,
        path,
        query,
        parts.fragment,
    ))


def remove_tracking_parameters(url: str) -> str:
    """Return the same URL with tracking parameters removed.

    Everything else stays exactly as it was: host, path, other
    parameters and their order, and the fragment.
    """
    parts = urlsplit(url)
    return urlunsplit(parts._replace(query=strip_tracking_query(parts.query)))


def remove_duplicates(results: list[dict]) -> list[dict]:
    unique_results = {}

    for result in results:
        url = result.get("url")

        if not isinstance(url, str):
            continue

        try:
            key = normalize_url(url)
        except ValueError:
            continue

        source = result["source"]
        rank = result["rank"]

        if key not in unique_results:
            unique_results[key] = {
                **result,
                "url": remove_tracking_parameters(url),
                "sources": [source],
                "source_ranks": {source: rank},
            }
        else:
            existing = unique_results[key]

            if source not in existing["sources"]:
                existing["sources"].append(source)

            previous_rank = existing["source_ranks"].get(source)

            if previous_rank is None or rank < previous_rank:
                existing["source_ranks"][source] = rank

    return list(unique_results.values())