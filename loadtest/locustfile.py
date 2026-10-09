"""Simulated users searching at the same time.

Usage (with stub_server.py running):
    locust -f loadtest/locustfile.py --host http://127.0.0.1:8000 \
        --headless --users 200 --spawn-rate 20 --run-time 60s

Or drop --headless and open http://localhost:8089 for live charts.
"""

import random

from locust import HttpUser, between, task

QUERIES = [
    "how does tls encryption work",
    "python asyncio gather",
    "history of the printing press",
    "what is reciprocal rank fusion",
    "fastapi dependency injection",
    "how do search engines rank pages",
    "difference between tcp and udp",
    "what is a hash map",
]


class SearchUser(HttpUser):
    # A real person reads results for a few seconds before searching again.
    wait_time = between(1, 3)

    @task(10)
    def search(self):
        with self.client.post(
            "/api/search",
            json={"query": random.choice(QUERIES)},
            name="POST /api/search",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return

            data = response.json()

            if not isinstance(data.get("results"), list):
                response.failure("response has no results list")

    @task(1)
    def home_page(self):
        self.client.get("/", name="GET /")