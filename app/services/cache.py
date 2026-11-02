import time
from collections import OrderedDict

CACHE_TTL_SECONDS = 300   # 5 minutes
CACHE_MAX_ENTRIES = 500
CACHE_CLEANUP_SECONDS = 300   # how often the app removes expired entries


class SearchCache:
    """Recent search results, kept in memory only.

    - An entry expires `ttl_seconds` after its results were fetched.
      Searching it again does not extend that time, so results stay fresh.
    - When the cache is full, the entry used least recently is removed (LRU).
    - remove_expired() is called on a schedule, so a query nobody repeats
      does not stay in memory.

    Nothing is written to disk, so everything is gone when the app restarts.
    """

    def __init__(self, ttl_seconds=CACHE_TTL_SECONDS, max_entries=CACHE_MAX_ENTRIES, clock=time.monotonic):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.clock = clock          # tests pass a fake clock instead of waiting
        self._entries = OrderedDict()   # key -> (expires_at, value), oldest first

    @staticmethod
    def make_key(query: str) -> str:
        """'  Python   Asyncio ' and 'python asyncio' share one entry.

        Only used for matching. The query sent to providers is never changed.
        """
        return " ".join(query.lower().split())

    def get(self, query: str):
        key = self.make_key(query)
        entry = self._entries.get(key)

        if entry is None:
            return None

        expires_at, value = entry

        if self.clock() >= expires_at:
            del self._entries[key]
            return None

        # Just used, so it's now the newest. Its expiry time does not change.
        self._entries.move_to_end(key)
        return value

    def set(self, query: str, value) -> None:
        key = self.make_key(query)
        self._entries[key] = (self.clock() + self.ttl_seconds, value)
        self._entries.move_to_end(key)

        if len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)   # remove the least recently used

    def remove_expired(self) -> int:
        """Delete every expired entry, even ones nobody asked for again.

        Returns how many were removed. If everything is old, the cache ends empty.
        """
        now = self.clock()
        expired = [key for key, (expires_at, _) in self._entries.items() if now >= expires_at]

        for key in expired:
            del self._entries[key]

        return len(expired)

    def __len__(self) -> int:
        return len(self._entries)