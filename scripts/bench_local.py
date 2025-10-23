from __future__ import annotations

import json
import random
import statistics
import time

import httpx

LITERAL_QUERIES = [r"\\newcommand", r"\\iiint", r"\\tikzpicture", r"\\mathbb{R}", r"\\frac{1}{2}"]
REGEX_QUERIES = [r"\\\\\\w+command", r"\\\\tikz\\w+", r"\\\\i+nt", r"\\\\\\w+picture"]
TOTAL_REQUESTS = 200


def run_benchmark(base_url: str = "http://localhost:8000") -> None:
    durations: list[float] = []
    errors = 0
    queries = []
    for _ in range(TOTAL_REQUESTS):
        if random.random() < 0.3:
            queries.append((random.choice(REGEX_QUERIES), "regex"))
        else:
            queries.append((random.choice(LITERAL_QUERIES), "literal"))

    with httpx.Client(timeout=5) as client:
        for query, mode in queries:
            payload = {"q": query, "mode": mode, "filters": {"source": "samples"}}
            start = time.perf_counter()
            try:
                response = client.post(f"{base_url}/api/search", json=payload)
                response.raise_for_status()
                data = response.json()
                durations.append(data.get("took_ms", (time.perf_counter() - start) * 1000))
            except Exception as exc:  # pragma: no cover - observational
                errors += 1
                print(f"error for {mode} {query}: {exc}")

    if durations:
        p50 = statistics.median(durations)
        p95 = statistics.quantiles(durations, n=20)[18]
    else:
        p50 = p95 = float("nan")

    print(json.dumps({
        "requests": TOTAL_REQUESTS,
        "errors": errors,
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2)
    }, indent=2))


if __name__ == "__main__":
    run_benchmark()
