from app.services.circuit_breaker import CircuitBreaker


class FakeClock:
    """A clock the test controls, so nobody waits real seconds."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make_breaker():
    clock = FakeClock()
    breaker = CircuitBreaker(
        threshold=3, window_seconds=60, first_open_seconds=30, max_open_seconds=300, clock=clock,
    )
    return breaker, clock


def fail(breaker, times):
    for _ in range(times):
        breaker.record_failure()


# ---------- closed ----------

def test_new_breaker_is_closed_and_allows_requests():
    breaker, _ = make_breaker()

    assert breaker.state == "closed"
    assert breaker.allow_request() is True


def test_three_failures_in_a_row_within_the_window_open_it():
    breaker, clock = make_breaker()

    breaker.record_failure()
    clock.now = 20
    breaker.record_failure()
    clock.now = 40
    breaker.record_failure()

    assert breaker.state == "open"
    assert breaker.allow_request() is False


def test_two_failures_are_not_enough():
    breaker, _ = make_breaker()

    fail(breaker, 2)

    assert breaker.state == "closed"


def test_failures_far_apart_do_not_open_it():
    breaker, clock = make_breaker()

    for hour in range(3):
        clock.now = hour * 3600
        breaker.record_failure()

    assert breaker.state == "closed"


def test_a_success_in_between_resets_the_count():
    breaker, _ = make_breaker()

    fail(breaker, 2)
    breaker.record_success()
    fail(breaker, 2)

    assert breaker.state == "closed"


# ---------- open and half-open ----------

def test_stays_open_for_the_first_open_time():
    breaker, clock = make_breaker()
    fail(breaker, 3)

    clock.now = 29

    assert breaker.allow_request() is False


def test_after_the_open_time_only_one_trial_request_is_allowed():
    breaker, clock = make_breaker()
    fail(breaker, 3)

    clock.now = 30

    assert breaker.state == "half-open"
    assert breaker.allow_request() is True     # the trial
    assert breaker.allow_request() is False    # everyone else still skips


def test_successful_trial_closes_it():
    breaker, clock = make_breaker()
    fail(breaker, 3)
    clock.now = 30
    breaker.allow_request()

    breaker.record_success()

    assert breaker.state == "closed"
    assert breaker.allow_request() is True


def test_failed_trial_opens_it_for_twice_as_long():
    breaker, clock = make_breaker()
    fail(breaker, 3)
    clock.now = 30
    breaker.allow_request()

    breaker.record_failure()                   # still down

    clock.now = 30 + 59
    assert breaker.state == "open"
    clock.now = 30 + 60
    assert breaker.state == "half-open"


def test_open_time_never_grows_past_the_maximum():
    breaker, clock = make_breaker()
    fail(breaker, 3)

    for _ in range(10):                        # the source stays down for a long time
        clock.now = breaker.open_until
        breaker.allow_request()
        breaker.record_failure()

    assert breaker.open_seconds == 300


def test_recovering_resets_the_open_time():
    breaker, clock = make_breaker()
    fail(breaker, 3)
    clock.now = 30
    breaker.allow_request()
    breaker.record_failure()                   # next opening would be 60 s
    clock.now = breaker.open_until
    breaker.allow_request()
    breaker.record_success()                   # back to normal

    fail(breaker, 3)

    assert breaker.open_until == clock.now + 30


def test_late_failures_while_open_do_not_extend_it():
    breaker, clock = make_breaker()
    fail(breaker, 3)
    opened_until = breaker.open_until

    clock.now = 10
    fail(breaker, 5)                           # requests that started before it opened

    assert breaker.open_until == opened_until


def test_cancelled_trial_lets_the_next_request_try():
    breaker, clock = make_breaker()
    fail(breaker, 3)
    clock.now = 30
    breaker.allow_request()                    # the trial starts...

    breaker.record_cancelled()                 # ...but is cancelled before an answer

    assert breaker.allow_request() is True     # another request may try