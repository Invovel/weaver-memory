"""Reproducibility manifests for external repos and snapshots."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_sha(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def git_remote(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def snapshot_entry(path: Path, *, sample_limit: int = 200) -> dict[str, Any]:
    path = path.resolve()
    if path.is_file():
        return {
            "path": str(path),
            "kind": "file",
            "size_bytes": path.stat().st_size,
            "sha256": hash_file(path),
        }
    files = sorted(item for item in path.rglob("*") if item.is_file())
    sample_hashes = [
        {
            "path": str(item.relative_to(path)),
            "size_bytes": item.stat().st_size,
            "sha256": hash_file(item),
        }
        for item in files[:sample_limit]
    ]
    return {
        "path": str(path),
        "kind": "directory",
        "repo_sha": git_sha(path),
        "repo_remote": git_remote(path),
        "file_count": len(files),
        "sample_hashes": sample_hashes,
        "sample_limit": sample_limit,
    }


def write_manifest(
    paths: list[Path],
    output: Path,
    *,
    sample_limit: int = 200,
) -> dict[str, Any]:
    manifest = {
        "schema_version": "memoryweaver-external-lock-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entries": [snapshot_entry(path, sample_limit=sample_limit) for path in paths],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
