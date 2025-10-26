from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:  # pragma: no cover - import guard for optional dependency
    import httpx


def _build_seed_queries() -> list[tuple[str, str]]:
    greek_symbols = [
        r"\alpha",
        r"\beta",
        r"\gamma",
        r"\delta",
        r"\epsilon",
        r"\zeta",
        r"\eta",
        r"\theta",
        r"\iota",
        r"\kappa",
        r"\lambda",
        r"\mu",
        r"\nu",
        r"\xi",
        r"\pi",
        r"\rho",
        r"\sigma",
        r"\tau",
        r"\upsilon",
        r"\phi",
        r"\chi",
        r"\psi",
        r"\omega",
    ]
    literal_templates = [
        "{sym}",
        "{sym}^2",
        "\\frac{{{sym}}}{{2}}",
        "\\int {sym} \\,dx",
        "\\sum_{{n=0}}^{{10}} {sym}_n",
    ]
    literal_queries = [
        template.format(sym=sym)
        for sym in greek_symbols
        for template in literal_templates
    ][:80]

    literal_queries.extend(
        [
            r"\mathbb{R}",
            r"\mathbb{C}",
            r"\mathbf{x}",
            r"\mathbf{A}",
            r"\mathrm{grad}",
            r"\mathrm{div}",
            r"\begin{align}",
            r"\end{align}",
            r"\begin{tikzpicture}",
            r"\end{tikzpicture}",
            r"\section{Introduction}",
            r"\subsection{Background}",
            r"\paragraph{Motivation}",
            r"\cite{knuth1984}",
            r"\cite{lamport1994}",
            r"\label{eq:main}",
            r"\includegraphics",
            r"\bibliography{references}",
            r"\newcommand{\vect}",
            r"\DeclareMathOperator",
        ]
    )

    regex_prefixes = [
        "new",
        "renew",
        "math",
        "mathbf",
        "mathcal",
        "text",
        "frac",
        "sqrt",
        "sum",
        "prod",
        "int",
        "oint",
        "left",
        "right",
        "label",
        "ref",
        "cite",
        "include",
        "tikz",
        "begin",
    ]
    regex_queries = []
    for prefix in regex_prefixes:
        regex_queries.extend(
            [
                rf"\\{prefix}\\w+",
                rf"\\{prefix}[A-Za-z]+",
                rf"\\{prefix}\\{{[^}}]+\\}}",
                rf"\\{prefix}\\[[^]]+\\]",
            ]
        )
    regex_queries = regex_queries[:80]

    regex_queries.extend(
        [
            r"\begin\{[a-z]+\}",
            r"\end\{[a-z]+\}",
            r"\mathbb\{[A-Z]\}",
            r"\mathbf\{[a-z]+\}",
            r"\mathrm\{[a-z]+\}",
            r"\mathfrak\{[A-Za-z]+\}",
            r"\operatorname\*?\{[^}]+\}",
            r"\int\s+[^d]+dx",
            r"\oint\s+[^d]+dx",
            r"\sum_\{n=0\}\^{10}",
            r"\prod_\{k=1\}\^{n}",
            r"\lim_\{[a-z]\\to 0\}",
            r"\frac\{[^}]+\}\{[^}]+\}",
            r"\\[A-Za-z]{3,}",
            r"\\math[A-Za-z]+",
            r"\includegraphics\[[^]]+\]",
            r"\DeclareMathOperator\*?\{[^}]+\}",
            r"\tikzstyle\{[^}]+\}",
            r"\tikzset\{[^}]+\}",
            r"\chapter\{[^}]+\}",
        ]
    )

    seeds: list[tuple[str, str]] = []
    seeds.extend((query, "literal") for query in literal_queries)
    seeds.extend((query, "regex") for query in regex_queries)
    assert len(seeds) == 200, f"expected 200 seeds, got {len(seeds)}"
    return seeds


SEED_QUERIES: list[tuple[str, str]] = _build_seed_queries()


def percentile(values: Iterable[float], fraction: float) -> float | None:
    data = sorted(values)
    if not data:
        return None
    if fraction <= 0:
        return data[0]
    if fraction >= 1:
        return data[-1]
    k = (len(data) - 1) * fraction
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return data[int(k)]
    d0 = data[f] * (c - k)
    d1 = data[c] * (k - f)
    return d0 + d1


@dataclass(slots=True)
class BenchmarkResult:
    requests: int
    errors: int
    error_rate: float
    p50_ms: float | None
    p95_ms: float | None
    concurrency: int
    duration_s: float


async def _run_payloads(
    payloads: list[dict],
    *,
    base_url: str,
    concurrency: int,
    timeout: float,
) -> tuple[list[float], list[str]]:
    import httpx

    durations: list[float] = []
    errors: list[str] = []
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        async def send(payload: dict) -> None:
            async with semaphore:
                start = time.perf_counter()
                try:
                    response = await client.post("/api/search", json=payload)
                    response.raise_for_status()
                except Exception as exc:  # pragma: no cover - observational
                    errors.append(f"{payload['mode']} {payload['q']}: {exc}")
                    return

                elapsed = (time.perf_counter() - start) * 1000
                try:
                    data = response.json()
                except ValueError:
                    errors.append(f"{payload['mode']} {payload['q']}: invalid JSON response")
                    return

                took = data.get("took_ms")
                if isinstance(took, (int, float)):
                    durations.append(float(took))
                else:
                    durations.append(elapsed)

        await asyncio.gather(*(send(payload) for payload in payloads))

    return durations, errors


def run_benchmark(
    *,
    base_url: str,
    total_requests: int,
    concurrency: int,
    timeout: float,
    rng: random.Random,
) -> BenchmarkResult:
    payloads = []
    for _ in range(total_requests):
        query, mode = rng.choice(SEED_QUERIES)
        payloads.append({"q": query, "mode": mode, "filters": {"source": "samples"}})

    start = time.perf_counter()
    durations, errors = asyncio.run(
        _run_payloads(
            payloads,
            base_url=base_url,
            concurrency=max(1, concurrency),
            timeout=timeout,
        )
    )
    total_elapsed = time.perf_counter() - start

    error_rate = len(errors) / total_requests if total_requests else 0.0
    p50 = percentile(durations, 0.5)
    p95 = percentile(durations, 0.95)

    for message in errors:
        print(message, file=sys.stderr)

    return BenchmarkResult(
        requests=total_requests,
        errors=len(errors),
        error_rate=error_rate,
        p50_ms=p50,
        p95_ms=p95,
        concurrency=concurrency,
        duration_s=total_elapsed,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark the /api/search endpoint")
    parser.add_argument("--base-url", default="http://backend:8000", help="API base URL")
    parser.add_argument("--requests", type=int, default=200, help="Number of requests to send")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Number of concurrent in-flight requests",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Request timeout in seconds",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Index provider identifier (accepted for compatibility, not sent to the API)",
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument(
        "--max-error-rate",
        type=float,
        default=None,
        help="Fail if the observed error rate exceeds this value",
    )
    parser.add_argument(
        "--max-p95",
        type=float,
        default=None,
        help="Fail if the observed p95 latency in ms exceeds this value",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    result = run_benchmark(
        base_url=args.base_url,
        total_requests=args.requests,
        concurrency=args.concurrency,
        timeout=args.timeout,
        rng=rng,
    )

    output = {
        "requests": result.requests,
        "errors": result.errors,
        "error_rate": round(result.error_rate, 4),
        "p50_ms": round(result.p50_ms, 2) if result.p50_ms is not None else None,
        "p95_ms": round(result.p95_ms, 2) if result.p95_ms is not None else None,
        "concurrency": result.concurrency,
        "duration_s": round(result.duration_s, 2),
    }
    print(json.dumps(output, indent=2))

    if args.max_error_rate is not None and result.error_rate > args.max_error_rate:
        raise SystemExit(
            f"error rate {result.error_rate:.4f} exceeds threshold {args.max_error_rate:.4f}"
        )
    if args.max_p95 is not None and (result.p95_ms or 0.0) > args.max_p95:
        raise SystemExit(
            f"p95 {result.p95_ms:.2f}ms exceeds threshold {args.max_p95:.2f}ms"
        )


if __name__ == "__main__":
    main()
