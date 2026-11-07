#!/usr/bin/env python3
"""Bounded, loopback-only traffic with per-request faults; no persistent state."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import random
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def options(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["baseline", "latency", "errors"])
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/work")
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--rate", type=float, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--fraction", type=float, default=.25)
    parser.add_argument("--latency-ms", type=int, default=800)
    args = parser.parse_args(argv)
    url = urlsplit(args.url)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username or url.password or url.path != "/api/work" or url.query or url.fragment):
        parser.error("Use a loopback HTTP /api/work URL, directly or through kubectl port-forward")
    if not (1 <= args.duration <= 1800 and 0 < args.rate <= 50 and 1 <= args.workers <= 8
            and 0 <= args.fraction <= 1 and 0 <= args.latency_ms <= 2000):
        parser.error("Bounds: duration 1..1800, rate >0..50, workers 1..8, fraction 0..1, latency 0..2000")
    return args


def run(args):
    deadline = time.monotonic() + args.duration

    def worker(index):
        rng, opener = random.Random(42 + index), build_opener(NoRedirect)
        counts = {"200": 0, "503": 0, "other_http": 0, "network_errors": 0, "fault_requests": 0}
        interval = args.workers / args.rate
        while time.monotonic() < deadline:
            start, headers = time.monotonic(), {}
            if args.mode != "baseline" and rng.random() < args.fraction:
                headers = ({"X-Demo-Error": "true"} if args.mode == "errors"
                           else {"X-Demo-Latency-Ms": str(args.latency_ms)})
                counts["fault_requests"] += 1
            try:
                with opener.open(Request(args.url, headers=headers), timeout=5) as response:
                    code = str(response.status)
                    response.read()
                counts[code if code in ("200", "503") else "other_http"] += 1
            except HTTPError as error:
                counts["503" if error.code == 503 else "other_http"] += 1
                error.close()
            except (URLError, TimeoutError):
                counts["network_errors"] += 1
            time.sleep(max(0, min(interval - (time.monotonic() - start), deadline - time.monotonic())))
        return counts

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(worker, range(args.workers)))
    totals = {key: sum(item[key] for item in results) for key in results[0]}
    print(json.dumps({"mode": args.mode, "duration_seconds": args.duration, **totals}, indent=2))
    return 1 if totals["network_errors"] or totals["other_http"] else 0


if __name__ == "__main__":
    raise SystemExit(run(options()))
