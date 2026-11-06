import hashlib
import hmac
import secrets
import time

SEARCHES_PER_MINUTE = 10
WINDOW_SECONDS = 60

# A random key made at startup and kept only in memory. Hashing an IP with it
# means the dictionary never holds a real IP address, and nobody can work the
# IP back out of the hash. A restart makes a new key, so old hashes mean nothing.
SECRET = secrets.token_bytes(32)


def visitor_key(ip: str) -> str:
    """Turn an IP address into a short, irreversible key."""
    return hmac.new(SECRET, ip.encode(), hashlib.sha256).hexdigest()[:16]


class RateLimiter:
    """Allows each visitor `limit` searches per `window_seconds`.

    Each visitor gets a one-minute window that starts with their first
    search. Once the minute is over, the next search starts a new window.
    """

    def __init__(self, limit=SEARCHES_PER_MINUTE, window_seconds=WINDOW_SECONDS, clock=time.monotonic):
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock                     # tests pass a fake clock
        self._windows = {}                     # visitor key -> (window start, searches so far)

    def check(self, key: str) -> int:
        """Count one search. Returns 0 if allowed, or the seconds to wait if not."""
        now = self.clock()
        start, count = self._windows.get(key, (now, 0))

        if now - start >= self.window_seconds:
            start, count = now, 0              # the minute is over: start a new one

        if count >= self.limit:
            return max(1, round(start + self.window_seconds - now))

        self._windows[key] = (start, count + 1)
        return 0

    def remaining(self, key: str) -> int:
        """How many more searches this visitor may make in their current minute."""
        now = self.clock()
        start, count = self._windows.get(key, (now, 0))

        if now - start >= self.window_seconds:
            return self.limit

        return max(0, self.limit - count)

    def remove_expired(self) -> int:
        """Forget visitors whose minute is over. Returns how many were removed."""
        now = self.clock()
        old = [key for key, (start, _) in self._windows.items() if now - start >= self.window_seconds]

        for key in old:
            del self._windows[key]

        return len(old)

    def __len__(self) -> int:
        return len(self._windows)