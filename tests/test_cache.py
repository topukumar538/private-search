from app.services.cache import SearchCache


class FakeClock:
    """A clock the test controls, so nobody waits 5 real minutes."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make_cache(ttl_seconds=300, max_entries=500):
    clock = FakeClock()
    return SearchCache(ttl_seconds=ttl_seconds, max_entries=max_entries, clock=clock), clock


# ---------- hits and misses ----------

def test_stored_results_are_returned():
    cache, _ = make_cache()

    cache.set("python asyncio", {"results": ["a"]})

    assert cache.get("python asyncio") == {"results": ["a"]}


def test_unknown_query_is_a_miss():
    cache, _ = make_cache()

    assert cache.get("never searched") is None


def test_case_and_extra_spaces_share_one_entry():
    cache, _ = make_cache()

    cache.set("Python Asyncio", {"results": ["a"]})

    assert cache.get("  python   asyncio ") == {"results": ["a"]}
    assert len(cache) == 1


def test_different_queries_do_not_mix():
    cache, _ = make_cache()

    cache.set("python", {"results": ["snake"]})

    assert cache.get("python asyncio") is None


def test_has_is_true_only_for_fresh_entries():
    cache, clock = make_cache(ttl_seconds=300)
    cache.set("python", {"results": ["a"]})

    assert cache.has("Python") is True
    assert cache.has("rust") is False

    clock.now = 300

    assert cache.has("python") is False


# ---------- expiry ----------

def test_entry_is_kept_until_it_expires():
    cache, clock = make_cache(ttl_seconds=300)
    cache.set("python", {"results": ["a"]})

    clock.now = 299

    assert cache.get("python") == {"results": ["a"]}


def test_entry_expires_after_ttl_and_is_removed():
    cache, clock = make_cache(ttl_seconds=300)
    cache.set("python", {"results": ["a"]})

    clock.now = 300

    assert cache.get("python") is None
    assert len(cache) == 0


def test_setting_again_restarts_the_timer():
    cache, clock = make_cache(ttl_seconds=300)
    cache.set("python", {"results": ["old"]})

    clock.now = 200
    cache.set("python", {"results": ["new"]})
    clock.now = 400

    assert cache.get("python") == {"results": ["new"]}


def test_searching_again_does_not_extend_the_time():
    cache, clock = make_cache(ttl_seconds=300)
    cache.set("python", {"results": ["a"]})

    clock.now = 200
    cache.get("python")          # a re-search
    clock.now = 300

    assert cache.get("python") is None


# ---------- scheduled cleanup ----------

def test_remove_expired_removes_only_old_entries():
    cache, clock = make_cache(ttl_seconds=300)
    cache.set("old", 1)
    clock.now = 200
    cache.set("new", 2)

    clock.now = 300
    removed = cache.remove_expired()

    assert removed == 1
    assert len(cache) == 1
    assert cache.get("new") == 2


def test_remove_expired_can_empty_the_whole_cache():
    cache, clock = make_cache(ttl_seconds=300)
    cache.set("a", 1)
    cache.set("b", 2)

    clock.now = 300

    assert cache.remove_expired() == 2
    assert len(cache) == 0


def test_remove_expired_on_fresh_cache_removes_nothing():
    cache, _ = make_cache()
    cache.set("a", 1)

    assert cache.remove_expired() == 0
    assert len(cache) == 1


# ---------- size limit (LRU) ----------

def test_oldest_entry_is_removed_when_full():
    cache, _ = make_cache(max_entries=2)

    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert len(cache) == 2


def test_recently_used_entry_is_kept_when_full():
    cache, _ = make_cache(max_entries=2)

    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")          # a is now the most recently used
    cache.set("c", 3)

    assert cache.get("a") == 1
    assert cache.get("b") is None