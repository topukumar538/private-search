import time
from collections import deque

FAILURE_THRESHOLD = 3       # failures in a row...
FAILURE_WINDOW_SECONDS = 60  # ...all within this many seconds, open the breaker
FIRST_OPEN_SECONDS = 30      # how long it stays open the first time
MAX_OPEN_SECONDS = 300       # longest it ever stays open (5 minutes)


class CircuitOpenError(Exception):
    """The source was skipped because its circuit breaker is open."""


class CircuitBreaker:
    """Stops asking a source that keeps failing, then checks if it's back.

    closed:    ask the source normally, remembering recent failures.
    open:      skip the source instantly, for `open_seconds`.
    half-open: let one trial request through. Success closes the breaker;
               failure opens it again for twice as long (up to a maximum).
    """

    def __init__(
        self,
        threshold=FAILURE_THRESHOLD,
        window_seconds=FAILURE_WINDOW_SECONDS,
        first_open_seconds=FIRST_OPEN_SECONDS,
        max_open_seconds=MAX_OPEN_SECONDS,
        clock=time.monotonic,
    ):
        self.threshold = threshold
        self.window_seconds = window_seconds
        self.first_open_seconds = first_open_seconds
        self.max_open_seconds = max_open_seconds
        self.clock = clock                       # tests pass a fake clock

        self.failures = deque()                  # times of recent failures in a row
        self.open_until = None                   # None means closed
        self.open_seconds = first_open_seconds   # length of the next opening
        self.trial_running = False

    @property
    def state(self) -> str:
        if self.open_until is None:
            return "closed"
        if self.clock() < self.open_until:
            return "open"
        return "half-open"

    def allow_request(self) -> bool:
        state = self.state

        if state == "closed":
            return True

        if state == "open" or self.trial_running:
            return False

        self.trial_running = True                # half-open: exactly one trial
        return True

    def record_cancelled(self) -> None:
        """The request was cancelled before the source answered.

        That proves nothing either way, so a running trial is given back
        and the next request may try again.
        """
        self.trial_running = False

    def record_success(self) -> None:
        self.failures.clear()
        self.open_until = None
        self.open_seconds = self.first_open_seconds
        self.trial_running = False

    def record_failure(self) -> None:
        now = self.clock()

        if self.trial_running:
            # The source is still down: wait longer before the next trial.
            self.trial_running = False
            self.open_seconds = min(self.open_seconds * 2, self.max_open_seconds)
            self.open_until = now + self.open_seconds
            return

        if self.open_until is not None:
            return    # a request that started before the breaker opened

        self.failures.append(now)

        while now - self.failures[0] >= self.window_seconds:
            self.failures.popleft()               # too old to count

        if len(self.failures) >= self.threshold:
            self.open_until = now + self.open_seconds
            self.failures.clear()