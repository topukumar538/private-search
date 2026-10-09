"""Find how many concurrent users the server handles within a latency target.

It runs Locust at increasing numbers of users. Once a level breaks the
target, it zooms in with bisection between the last passing and the first
failing level, then prints and saves a table of every run.

Target (SLO), for POST /api/search:
    p95 response time <= --p95-ms   (default 2000 ms)
    failure rate      <= --max-failure-pct   (default 1%)

Why 2000 ms: the fake slow source alone takes up to 1500 ms, so an idle
server already has a p95 of about 1500 ms. 2000 ms means "our server adds
at most about half a second".

Usage (stub_server.py must be running, run from the project root):
    python loadtest/find_capacity.py
    python loadtest/find_capacity.py --levels 100 500 1000 2000 --measure-seconds 30
"""

import argparse
import csv
import math
import subprocess
import sys
from pathlib import Path

ENDPOINT = "POST /api/search"
RESULTS_DIR = Path("loadtest/results/capacity")


def run_level(users: int, args) -> dict:
    """Run Locust at one load level and return its steady-state numbers."""
    prefix = RESULTS_DIR / f"{users}-users"
    ramp_seconds = math.ceil(users / args.spawn_rate)

    command = [
        "locust",
        "-f", "loadtest/locustfile.py",
        "--host", args.host,
        "--headless",
        "--only-summary",
        "--users", str(users),
        "--spawn-rate", str(args.spawn_rate),
        "--run-time", f"{ramp_seconds + args.measure_seconds}s",
        # Throw away numbers from the ramp-up; measure steady state only.
        "--reset-stats",
        "--csv", str(prefix),
    ]

    print(f"  running {users} users for {ramp_seconds + args.measure_seconds}s ...", flush=True)
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    stats_file = prefix.with_name(prefix.name + "_stats.csv")

    with stats_file.open(newline="") as file:
        for row in csv.DictReader(file):
            if row["Name"] == ENDPOINT:
                requests = int(row["Request Count"])
                failures = int(row["Failure Count"])

                return {
                    "users": users,
                    "requests": requests,
                    "rps": float(row["Requests/s"]),
                    "p50_ms": int(row["50%"]),
                    "p95_ms": int(row["95%"]),
                    "p99_ms": int(row["99%"]),
                    "failure_pct": 100 * failures / requests if requests else 100.0,
                }

    raise RuntimeError(f"No '{ENDPOINT}' row in {stats_file}. Is stub_server.py running?")


def passes(result: dict, args) -> bool:
    return result["p95_ms"] <= args.p95_ms and result["failure_pct"] <= args.max_failure_pct


def find_capacity(args) -> tuple[list[dict], int | None, int | None]:
    results = []
    last_pass = None
    first_fail = None

    # Phase 1: step up until a level breaks the target.
    for users in args.levels:
        result = run_level(users, args)
        results.append(result)
        print_row(result, args)

        if passes(result, args):
            last_pass = users
        else:
            first_fail = users
            break

    # Phase 2: bisect between the last pass and the first fail.
    while last_pass is not None and first_fail is not None and first_fail - last_pass > args.precision:
        users = (last_pass + first_fail) // 2
        result = run_level(users, args)
        results.append(result)
        print_row(result, args)

        if passes(result, args):
            last_pass = users
        else:
            first_fail = users

    return results, last_pass, first_fail


def print_row(result: dict, args) -> None:
    verdict = "PASS" if passes(result, args) else "FAIL"
    print(
        f"  {result['users']:>6} users | {result['rps']:7.1f} req/s | "
        f"p50 {result['p50_ms']:>5} ms | p95 {result['p95_ms']:>5} ms | "
        f"p99 {result['p99_ms']:>5} ms | errors {result['failure_pct']:.2f}% | {verdict}",
        flush=True,
    )


def save_table(results: list[dict], args) -> Path:
    path = RESULTS_DIR / "capacity.md"
    lines = [
        f"Target: p95 <= {args.p95_ms} ms and errors <= {args.max_failure_pct}%",
        "",
        "| Users | Searches/s | p50 (ms) | p95 (ms) | p99 (ms) | Errors | Result |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in sorted(results, key=lambda r: r["users"]):
        verdict = "pass" if passes(r, args) else "fail"
        lines.append(
            f"| {r['users']} | {r['rps']:.0f} | {r['p50_ms']} | {r['p95_ms']} | "
            f"{r['p99_ms']} | {r['failure_pct']:.2f}% | {verdict} |"
        )

    path.write_text("\n".join(lines) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--levels", type=int, nargs="+", default=[100, 250, 500, 1000, 1500, 2000, 3000])
    parser.add_argument("--p95-ms", type=int, default=2000)
    parser.add_argument("--max-failure-pct", type=float, default=1.0)
    parser.add_argument("--measure-seconds", type=int, default=30)
    parser.add_argument("--spawn-rate", type=int, default=100)
    parser.add_argument("--precision", type=int, default=250, help="stop bisecting below this gap in users")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Target: p95 <= {args.p95_ms} ms, errors <= {args.max_failure_pct}%\n", flush=True)

    results, last_pass, first_fail = find_capacity(args)
    table = save_table(results, args)

    print()
    if last_pass is None:
        print("Even the first level failed the target. Try lower --levels.")
    elif first_fail is None:
        print(f"Every level passed. Capacity is above {last_pass} users; try higher --levels.")
    else:
        print(f"Capacity: about {last_pass} concurrent users "
              f"(passes at {last_pass}, fails at {first_fail}).")
    print(f"Table saved to {table}")

    return 0


if __name__ == "__main__":
    sys.exit(main())