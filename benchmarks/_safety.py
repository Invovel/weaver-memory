"""Shared safety helpers for benchmark filesystem cleanup."""

from __future__ import annotations

import shutil
from pathlib import Path


def ensure_child_path(parent: Path, child: Path) -> tuple[Path, Path]:
    """Resolve paths and require child to be inside parent."""
    resolved_parent = parent.resolve()
    resolved_child = child.resolve()
    try:
        resolved_child.relative_to(resolved_parent)
    except ValueError as exc:
        raise ValueError(
            f"refusing to operate outside benchmark output dir: {resolved_child}"
        ) from exc
    if resolved_child == resolved_parent:
        raise ValueError(f"refusing to operate on benchmark output dir itself: {resolved_child}")
    return resolved_parent, resolved_child


def safe_rmtree_child(parent: Path, child: Path, *, allowed_prefixes: tuple[str, ...]) -> None:
    """Remove an existing benchmark child directory after containment checks."""
    _, resolved_child = ensure_child_path(parent, child)
    if not resolved_child.exists():
        return
    if not resolved_child.is_dir():
        raise ValueError(f"refusing to remove non-directory path: {resolved_child}")
    if not any(resolved_child.name.startswith(prefix) for prefix in allowed_prefixes):
        raise ValueError(f"refusing to remove unexpected benchmark directory: {resolved_child}")
    shutil.rmtree(resolved_child)


def safe_unlink_child(parent: Path, child: Path) -> None:
    """Unlink a generated benchmark artifact after containment checks."""
    _, resolved_child = ensure_child_path(parent, child)
    if not resolved_child.exists():
        return
    if not resolved_child.is_file():
        raise ValueError(f"refusing to unlink non-file path: {resolved_child}")
    resolved_child.unlink()
