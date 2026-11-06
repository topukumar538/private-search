from app.services.rate_limiter import RateLimiter, visitor_key


class FakeClock:
    """A clock the test controls, so nobody waits a real minute."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make_limiter():
    clock = FakeClock()
    return RateLimiter(limit=10, window_seconds=60, clock=clock), clock


def search_times(limiter, key, times):
    return [limiter.check(key) for _ in range(times)]


# ---------- the limit ----------

def test_ten_searches_in_a_minute_are_allowed():
    limiter, _ = make_limiter()

    assert search_times(limiter, "visitor", 10) == [0] * 10


def test_the_eleventh_search_is_refused_with_seconds_to_wait():
    limiter, clock = make_limiter()
    search_times(limiter, "visitor", 10)

    clock.now = 20

    assert limiter.check("visitor") == 40      # the minute started at 0, so 40 s left


def test_a_new_minute_allows_searches_again():
    limiter, clock = make_limiter()
    search_times(limiter, "visitor", 10)

    clock.now = 60

    assert limiter.check("visitor") == 0


def test_refused_searches_do_not_count():
    limiter, clock = make_limiter()
    search_times(limiter, "visitor", 15)       # 10 allowed, 5 refused

    clock.now = 60

    assert search_times(limiter, "visitor", 10) == [0] * 10


def test_visitors_are_limited_separately():
    limiter, _ = make_limiter()
    search_times(limiter, "alice", 10)

    assert limiter.check("bob") == 0


def test_remaining_counts_down_and_resets():
    limiter, clock = make_limiter()

    assert limiter.remaining("visitor") == 10
    search_times(limiter, "visitor", 4)
    assert limiter.remaining("visitor") == 6

    clock.now = 60
    assert limiter.remaining("visitor") == 10


# ---------- cleanup ----------

def test_remove_expired_forgets_finished_minutes_only():
    limiter, clock = make_limiter()
    limiter.check("old")
    clock.now = 30
    limiter.check("new")

    clock.now = 60
    removed = limiter.remove_expired()

    assert removed == 1
    assert len(limiter) == 1


# ---------- privacy ----------

def test_visitor_key_hides_the_ip():
    key = visitor_key("103.45.67.89")

    assert "103.45.67.89" not in key
    assert key == visitor_key("103.45.67.89")  # same visitor, same key
    assert key != visitor_key("103.45.67.90")  # different visitor, different key