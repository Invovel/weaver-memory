"""LongMemEval-V2 local snapshot adapter.

This module reads the raw Hugging Face snapshot layout:

    questions.jsonl
    trajectories.jsonl
    haystacks/lme_v2_small.json

and converts a bounded subset into MemoryWeaver ExternalEpisode records. It is
streaming by design: trajectories.jsonl can be large, so only referenced
trajectory ids are loaded.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from memoryweaver.external.adapters import adapt_external_record
from memoryweaver.external.schema import ExternalEpisode


DEFAULT_TIMESTAMP = "2026-02-01T00:00:00+00:00"
DATASET_REPO_ID = "xiaowu0162/longmemeval-v2"
DEFAULT_BENCHMARK_ROOT = Path(r"D:\benchmarks\longmemeval-v2")
DEFAULT_HF_CACHE_ROOT = Path(r"D:\hf_cache")
REQUIRED_SNAPSHOT_FILES = (
    "questions.jsonl",
    "trajectories.jsonl",
    "haystacks/lme_v2_small.json",
)


def is_lme_v2_snapshot_root(root: Path) -> bool:
    return root.exists() and all((root / relative).exists() for relative in REQUIRED_SNAPSHOT_FILES)


def resolve_lme_v2_root(
    root: Path | None = None,
    *,
    hf_cache_root: Path | None = None,
    allow_download: bool = False,
    download_root: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Resolve a usable LongMemEval-V2 snapshot root.

    Search order:
    1. Explicit root
    2. `MEMORYWEAVER_LME_V2_ROOT`
    3. `D:\\benchmarks\\longmemeval-v2`
    4. Hugging Face cache snapshot layout under `D:\\hf_cache`
    5. Optional download via `huggingface_hub`
    """

    checked: list[str] = []
    for label, candidate in _root_candidates(root):
        if candidate is None:
            continue
        checked.append(str(candidate))
        if is_lme_v2_snapshot_root(candidate):
            return candidate, {"source": label, "root": str(candidate)}

    resolved_hf_cache = hf_cache_root or DEFAULT_HF_CACHE_ROOT
    checked.append(str(resolved_hf_cache))
    snapshot_root = _snapshot_from_hf_cache(resolved_hf_cache)
    if snapshot_root is not None:
        return snapshot_root, {"source": "hf_cache", "root": str(snapshot_root)}

    if allow_download:
        target_root = download_root or root or os.environ.get("MEMORYWEAVER_LME_V2_ROOT")
        destination = Path(target_root) if target_root else DEFAULT_BENCHMARK_ROOT
        downloaded = download_lme_v2_snapshot(destination, hf_cache_root=resolved_hf_cache)
        return downloaded, {"source": "download", "root": str(downloaded)}

    raise FileNotFoundError(
        "Unable to resolve a LongMemEval-V2 snapshot root. "
        f"Checked: {checked}. "
        "Provide --input-root, set MEMORYWEAVER_LME_V2_ROOT, place the snapshot under "
        "D:\\benchmarks\\longmemeval-v2, or rerun with download enabled."
    )


def download_lme_v2_snapshot(
    destination: Path,
    *,
    hf_cache_root: Path | None = None,
) -> Path:
    """Download the minimal LongMemEval-V2 snapshot layout via huggingface_hub."""

    from huggingface_hub import snapshot_download

    destination.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=DATASET_REPO_ID,
        repo_type="dataset",
        local_dir=str(destination),
        allow_patterns=[
            "questions.jsonl",
            "trajectories.jsonl",
            "haystacks/*",
            "README.md",
            "LICENSE",
            "DATA_CARD.md",
            "SCHEMA.md",
            "checksums.sha256",
        ],
        cache_dir=str(hf_cache_root) if hf_cache_root else None,
    )
    if not is_lme_v2_snapshot_root(destination):
        raise FileNotFoundError(
            f"Downloaded LongMemEval-V2 snapshot at '{destination}' is incomplete"
        )
    return destination


def default_lme_v2_root() -> Path:
    root, _ = resolve_lme_v2_root()
    return root


def inspect_lme_v2_storage(
    root: Path | None = None,
    *,
    hf_cache_root: Path | None = None,
) -> dict[str, Any]:
    """Return a read-only report for LongMemEval-V2 local/cache storage.

    This distinguishes a Hugging Face cache root from a readable snapshot root.
    It intentionally avoids reading token files.
    """

    resolved_hf_cache = hf_cache_root or DEFAULT_HF_CACHE_ROOT
    dataset_cache_root = resolved_hf_cache / "hub" / "datasets--xiaowu0162--longmemeval-v2"
    refs_main = dataset_cache_root / "refs" / "main"
    refs_main_revision = refs_main.read_text(encoding="utf-8").strip() if refs_main.exists() else ""
    refs_snapshot = dataset_cache_root / "snapshots" / refs_main_revision if refs_main_revision else None
    complete_cache_snapshot = _snapshot_from_hf_cache(resolved_hf_cache)

    candidate_roots = {
        "explicit": root,
        "env": Path(os.environ["MEMORYWEAVER_LME_V2_ROOT"])
        if os.environ.get("MEMORYWEAVER_LME_V2_ROOT")
        else None,
        "benchmarks": DEFAULT_BENCHMARK_ROOT,
        "hf_cache_snapshot": complete_cache_snapshot,
    }
    root_status = {
        label: _snapshot_root_status(candidate)
        for label, candidate in candidate_roots.items()
        if candidate is not None
    }

    resolved_root = ""
    resolution_source = ""
    resolution_error = ""
    try:
        resolved, resolution = resolve_lme_v2_root(
            root,
            hf_cache_root=resolved_hf_cache,
            allow_download=False,
        )
        resolved_root = str(resolved)
        resolution_source = str(resolution["source"])
    except FileNotFoundError as exc:
        resolution_error = str(exc)

    return {
        "dataset_repo_id": DATASET_REPO_ID,
        "hf_cache_root": str(resolved_hf_cache),
        "hf_cache_root_exists": resolved_hf_cache.exists(),
        "dataset_cache_root": str(dataset_cache_root),
        "dataset_cache_root_exists": dataset_cache_root.exists(),
        "refs_main_exists": refs_main.exists(),
        "refs_main_revision": refs_main_revision,
        "refs_snapshot_root": str(refs_snapshot) if refs_snapshot else "",
        "refs_snapshot_exists": refs_snapshot.exists() if refs_snapshot else False,
        "refs_snapshot_complete": is_lme_v2_snapshot_root(refs_snapshot) if refs_snapshot else False,
        "complete_cache_snapshot_root": str(complete_cache_snapshot) if complete_cache_snapshot else "",
        "complete_cache_snapshot_exists": complete_cache_snapshot is not None,
        "root_status": root_status,
        "resolved_root": resolved_root,
        "root_resolution_source": resolution_source,
        "resolution_error": resolution_error,
        "can_build_external_records": bool(resolved_root and not resolution_error),
        "required_snapshot_files": list(REQUIRED_SNAPSHOT_FILES),
    }


def load_lme_v2_questions(root: Path, *, limit: int) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for record in read_jsonl(root / "questions.jsonl"):
        questions.append(record)
        if len(questions) >= limit:
            break
    return questions


def load_lme_v2_haystack(root: Path, *, name: str = "lme_v2_small.json") -> dict[str, list[str]]:
    path = root / "haystacks" / name
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): [str(item) for item in value] for key, value in raw.items()}


def load_lme_v2_trajectories(root: Path, ids: set[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    if not ids:
        return found
    for record in read_jsonl(root / "trajectories.jsonl"):
        trajectory_id = str(record.get("id", ""))
        if trajectory_id in ids:
            found[trajectory_id] = record
            if len(found) == len(ids):
                break
    return found


def build_lme_v2_external_records(
    root: Path | None,
    *,
    question_limit: int = 20,
    trajectories_per_question: int = 2,
    states_per_trajectory: int = 3,
    max_observation_chars: int = 1800,
    haystack_name: str = "lme_v2_small.json",
    hf_cache_root: Path | None = None,
    allow_download: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resolved_root, resolution = resolve_lme_v2_root(
        root,
        hf_cache_root=hf_cache_root,
        allow_download=allow_download,
        download_root=root,
    )
    questions = load_lme_v2_questions(resolved_root, limit=question_limit)
    haystack = load_lme_v2_haystack(resolved_root, name=haystack_name)
    question_ids = [str(question["id"]) for question in questions]
    requested_ids: set[str] = set()
    for question_id in question_ids:
        requested_ids.update(haystack.get(question_id, [])[:trajectories_per_question])
    trajectories_by_id = load_lme_v2_trajectories(resolved_root, requested_ids)

    records: list[dict[str, Any]] = []
    missing_refs = 0
    for question in questions:
        selected: list[dict[str, Any]] = []
        for trajectory_id in haystack.get(str(question["id"]), [])[:trajectories_per_question]:
            trajectory = trajectories_by_id.get(trajectory_id)
            if trajectory is None:
                missing_refs += 1
            else:
                selected.append(trajectory)
        records.append(
            lme_v2_question_to_external_record(
                question,
                selected,
                states_per_trajectory=states_per_trajectory,
                max_observation_chars=max_observation_chars,
            )
        )

    metadata = {
        "resolved_root": str(resolved_root),
        "root_resolution_source": resolution["source"],
        "question_count": len(questions),
        "requested_trajectory_refs": len(requested_ids),
        "loaded_trajectory_count": len(trajectories_by_id),
        "missing_trajectory_refs": missing_refs,
        "haystack": haystack_name,
        "trajectories_per_question": trajectories_per_question,
        "states_per_trajectory": states_per_trajectory,
        "max_observation_chars": max_observation_chars,
    }
    return records, metadata


def build_lme_v2_external_episodes(
    root: Path | None,
    **kwargs: Any,
) -> tuple[list[ExternalEpisode], dict[str, Any]]:
    records, metadata = build_lme_v2_external_records(root, **kwargs)
    return [adapt_external_record("longmemeval-v2", record) for record in records], metadata


def lme_v2_question_to_external_record(
    question: dict[str, Any],
    trajectories: Iterable[dict[str, Any]],
    *,
    states_per_trajectory: int,
    max_observation_chars: int,
) -> dict[str, Any]:
    turns: list[dict[str, Any]] = []
    for trajectory in trajectories:
        turns.extend(
            lme_v2_trajectory_to_turns(
                trajectory,
                states_per_trajectory=states_per_trajectory,
                max_observation_chars=max_observation_chars,
            )
        )
    return {
        "id": str(question.get("id", "")),
        "split": "local_snapshot",
        "question_type": str(question.get("question_type", "")),
        "domain": str(question.get("domain", "")),
        "environment": str(question.get("environment", "")),
        "sessions": turns,
        "query": str(question.get("question", "")),
        "answer": str(question.get("answer", "")),
    }


def lme_v2_trajectory_to_turns(
    trajectory: dict[str, Any],
    *,
    states_per_trajectory: int,
    max_observation_chars: int,
) -> list[dict[str, Any]]:
    tags = [
        "longmemeval-v2",
        str(trajectory.get("domain", "")),
        str(trajectory.get("environment", "")),
        str(trajectory.get("outcome", "")),
    ]
    turns: list[dict[str, Any]] = [
        {
            "id": f"{trajectory.get('id', 'trajectory')}_goal",
            "role": "user",
            "content": str(trajectory.get("goal", "")),
            "timestamp": DEFAULT_TIMESTAMP,
            "tags": tags,
        }
    ]
    states = list(trajectory.get("states", []))[:states_per_trajectory]
    for state in states:
        index = int(state.get("state_index", len(turns)))
        timestamp = f"2026-02-01T00:{index + 1:02d}:00+00:00"
        if state.get("thought"):
            turns.append(
                {
                    "id": f"{trajectory.get('id', 'trajectory')}_s{index:03d}_thought",
                    "role": "assistant",
                    "content": str(state.get("thought", "")),
                    "timestamp": timestamp,
                    "tags": ["thought", "trajectory", str(trajectory.get("outcome", ""))],
                }
            )
        if state.get("action"):
            turns.append(
                {
                    "id": f"{trajectory.get('id', 'trajectory')}_s{index:03d}_action",
                    "role": "tool",
                    "content": json.dumps(
                        {
                            "status": "observed",
                            "action": state.get("action"),
                            "url": state.get("url", ""),
                        },
                        ensure_ascii=False,
                    ),
                    "timestamp": timestamp,
                    "tags": ["tool", "action", "trajectory"],
                }
            )
        if state.get("accessibility_tree"):
            turns.append(
                {
                    "id": f"{trajectory.get('id', 'trajectory')}_s{index:03d}_observation",
                    "role": "web",
                    "source": "web",
                    "content": shorten(
                        str(state.get("accessibility_tree", "")),
                        limit=max_observation_chars,
                    ),
                    "timestamp": timestamp,
                    "tags": ["web", "observation", "accessibility_tree"],
                }
            )
    return turns


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def shorten(text: str, *, limit: int) -> str:
    collapsed = " ".join(str(text).split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def _root_candidates(root: Path | None) -> list[tuple[str, Path | None]]:
    env_root = os.environ.get("MEMORYWEAVER_LME_V2_ROOT")
    return [
        ("explicit", root),
        ("env", Path(env_root) if env_root else None),
        ("benchmarks", DEFAULT_BENCHMARK_ROOT),
    ]


def _snapshot_from_hf_cache(hf_cache_root: Path) -> Path | None:
    dataset_root = hf_cache_root / "hub" / "datasets--xiaowu0162--longmemeval-v2"
    if not dataset_root.exists():
        return None
    refs_main = dataset_root / "refs" / "main"
    if refs_main.exists():
        revision = refs_main.read_text(encoding="utf-8").strip()
        candidate = dataset_root / "snapshots" / revision
        if is_lme_v2_snapshot_root(candidate):
            return candidate
    snapshots_root = dataset_root / "snapshots"
    if snapshots_root.exists():
        for candidate in snapshots_root.iterdir():
            if candidate.is_dir() and is_lme_v2_snapshot_root(candidate):
                return candidate
    return None


def _snapshot_root_status(root: Path) -> dict[str, Any]:
    return {
        "root": str(root),
        "exists": root.exists(),
        "complete": is_lme_v2_snapshot_root(root),
        "required_files": {
            relative: (root / relative).exists()
            for relative in REQUIRED_SNAPSHOT_FILES
        },
    }
