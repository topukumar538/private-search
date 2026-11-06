"""Simulated users searching at the same time.

A realistic mix: most people search something new (UNIQUE_SHARE), the rest
search something popular that others have searched too, so the cache can help.

Usage (with stub_server.py running):
    locust -f loadtest/locustfile.py --host http://127.0.0.1:8000 \\
        --headless --users 200 --spawn-rate 20 --run-time 60s

    UNIQUE_SHARE=1.0  ->  every search is new (the cache never helps)
    UNIQUE_SHARE=0.7  ->  70% new, 30% popular (default)

Or drop --headless and open http://localhost:8089 for live charts.
"""

import json
import os
import random
import uuid

from locust import HttpUser, between, events, task

UNIQUE_SHARE = float(os.getenv("UNIQUE_SHARE", "0.7"))
SUMMARY_FILE = os.getenv("SUMMARY_FILE")   # find_capacity.py reads this

POPULAR = [
    "how does tls encryption work",
    "python asyncio gather",
    "history of the printing press",
    "what is reciprocal rank fusion",
    "fastapi dependency injection",
    "how do search engines rank pages",
    "difference between tcp and udp",
    "what is a hash map",
    "how does garbage collection work",
    "binary search explained",
    "what is docker",
    "rest vs graphql",
    "how does dns work",
    "sql join types",
    "what is a race condition",
    "big o notation",
    "how does https work",
    "git rebase vs merge",
    "what is a load balancer",
    "how do neural networks learn",
]

counts = {"searches": 0, "cached": 0, "partial": 0}


def pick_query() -> str:
    if random.random() < UNIQUE_SHARE:
        # A new search nobody has made before.
        return f"{random.choice(POPULAR)} {uuid.uuid4().hex[:8]}"
    return random.choice(POPULAR)


class SearchUser(HttpUser):
    # A real person reads results for a few seconds before searching again.
    wait_time = between(1, 3)

    @task(10)
    def search(self):
        with self.client.post(
            "/api/search",
            json={"query": pick_query()},
            name="POST /api/search",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return

            data = response.json()

            if not isinstance(data.get("results"), list):
                response.failure("response has no results list")
                return

            counts["searches"] += 1
            counts["cached"] += bool(data.get("cached"))
            counts["partial"] += bool(data.get("failed_sources"))

    @task(1)
    def home_page(self):
        self.client.get("/", name="GET /")


@events.reset_stats.add_listener
def reset_counts(**kwargs):
    # Ramp-up is not measured: start counting with Locust's own statistics.
    for key in counts:
        counts[key] = 0


@events.test_stop.add_listener
def write_summary(**kwargs):
    if SUMMARY_FILE:
        with open(SUMMARY_FILE, "w") as file:
            json.dump(counts, file)