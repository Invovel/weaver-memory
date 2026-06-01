"""Benchmark the current MemoryWeaver prototype.

This script intentionally measures the implementation as it exists today.
It does not modify application code or hide known correctness gaps.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoryweaver import (
    Freshness,
    Layer,
    MemoryItem,
    MemoryStore,
    ModeRouter,
    Polarity,
    VerifiedRetriever,
)


def percentile(values: list[float], percent: float) -> float:
    """Return a nearest-rank percentile for a non-empty list."""
    ordered = sorted(values)
    rank = max(0, math.ceil((percent / 100) * len(ordered)) - 1)
    return ordered[rank]


def latency_summary(fn: Callable[[], object], iterations: int) -> dict[str, float]:
    """Measure repeated calls and summarize latency and throughput."""
    samples_ms: list[float] = []
    started = time.perf_counter()
    for _ in range(iterations):
        iteration_started = time.perf_counter()
        fn()
        samples_ms.append((time.perf_counter() - iteration_started) * 1000)
    elapsed = time.perf_counter() - started
    return {
        "iterations": iterations,
        "p50_ms": round(statistics.median(samples_ms), 4),
        "p95_ms": round(percentile(samples_ms, 95), 4),
        "p99_ms": round(percentile(samples_ms, 99), 4),
        "ops_per_second": round(iterations / elapsed, 2),
    }


def make_item(index: int) -> MemoryItem:
    sources = ("user", "terminal", "tool", "web", "composer")
    source = sources[index % len(sources)]
    group = index % 20
    return MemoryItem(
        content=(
            f"Project {group} Codex CLI subscription issue fixed by checking "
            f"organization auth state item {index}"
        ),
        tags=["codex", "subscription", f"project-{group}", f"item-{index}"],
        source=source,
        confidence=0.8,
        heat=2,
    )


def benchmark_store(item_count: int, query_iterations: int) -> dict[str, object]:
    """Benchmark one JSON-backed store size."""
    with tempfile.TemporaryDirectory(prefix="memoryweaver-benchmark-") as temp_dir:
        path = Path(temp_dir) / "memory.json"
        store = MemoryStore(path)

        write_started = time.perf_counter()
        for index in range(item_count):
            store.add(make_item(index))
        write_seconds = time.perf_counter() - write_started

        retriever = VerifiedRetriever(store)
        tag_query = lambda: store.find_by_tags(["project-3"])
        verified_tag_query = lambda: retriever.search_by_tags(["project-3"])
        text_query = lambda: store.find_similar(
            "Codex CLI subscription auth organization", threshold=0.25
        )
        verified_text_query = lambda: retriever.search(
            "Codex CLI subscription auth organization", limit=10
        )

        reload_started = time.perf_counter()
        reloaded = MemoryStore(path)
        reload_ms = (time.perf_counter() - reload_started) * 1000

        return {
            "items": item_count,
            "json_bytes": path.stat().st_size,
            "write": {
                "seconds": round(write_seconds, 4),
                "items_per_second": round(item_count / write_seconds, 2),
            },
            "reload_ms": round(reload_ms, 4),
            "reloaded_items": reloaded.count(),
            "find_by_tags": latency_summary(tag_query, query_iterations),
            "verified_search_by_tags": latency_summary(
                verified_tag_query, query_iterations
            ),
            "find_similar": latency_summary(text_query, query_iterations),
            "verified_search": latency_summary(
                verified_text_query, query_iterations
            ),
        }


def correctness_probes() -> dict[str, object]:
    """Record known trust-boundary and retrieval behavior."""
    with tempfile.TemporaryDirectory(prefix="memoryweaver-probes-") as temp_dir:
        path = Path(temp_dir) / "memory.json"
        store = MemoryStore(path)

        editable = MemoryItem(content="before")
        store.add(editable)
        editable.content = "after"
        store.update(editable)

        assistant_tag = MemoryItem(
            content="fabricated assistant claim",
            tags=["shared"],
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            confidence=0.2,
        )
        store.add(assistant_tag)
        tag_sources = [
            item.source for item in VerifiedRetriever(store).search_by_tags(["shared"])
        ]

        chinese_store = MemoryStore(Path(temp_dir) / "chinese.json")
        chinese_store.add(MemoryItem(content="检查组织选择解决订阅问题"))
        chinese_matches = chinese_store.find_similar(
            "订阅问题检查组织选择", threshold=0.1
        )

        router_store = MemoryStore(Path(temp_dir) / "router.json")
        router_store.add(
            MemoryItem(
                content="Codex CLI subscription load failed WSL",
                source="assistant",
                polarity=Polarity.AMBIGUOUS,
                layer=Layer.PATTERN,
                confidence=1.0,
                freshness=Freshness.STABLE,
            )
        )
        route = ModeRouter(router_store).route(
            "Codex CLI subscription load failed WSL"
        )

        assistant_positive = MemoryItem(
            source="assistant",
            polarity=Polarity.POSITIVE,
            confidence=1.0,
        )

        return {
            "cli_module_exists": importlib.util.find_spec("memoryweaver.cli")
            is not None,
            "plain_update_heat": editable.heat,
            "tag_search_returns_unverified_assistant": "assistant" in tag_sources,
            "assistant_positive_is_accepted": (
                assistant_positive.polarity == Polarity.POSITIVE
                and assistant_positive.confidence == 1.0
            ),
            "router_route_from_unverified_assistant_pattern": route.mode.value,
            "chinese_reordered_query_match_count": len(chinese_matches),
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark the current JSON-backed MemoryWeaver prototype."
    )
    parser.add_argument(
        "--items",
        nargs="+",
        type=int,
        default=[100, 500, 1000],
        help="Store sizes to benchmark.",
    )
    parser.add_argument(
        "--query-iterations",
        type=int,
        default=100,
        help="Iterations per query benchmark.",
    )
    args = parser.parse_args()

    result = {
        "benchmark": "memoryweaver-prototype-baseline",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "query_iterations": args.query_iterations,
        "correctness_probes": correctness_probes(),
        "performance": [
            benchmark_store(item_count, args.query_iterations)
            for item_count in args.items
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
