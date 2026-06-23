"""Write a reproducibility manifest for external repos and local snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from memoryweaver.external.manifest import write_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos", nargs="+", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sample-limit", type=int, default=200)
    args = parser.parse_args(argv)
    manifest = write_manifest(
        args.repos,
        args.out,
        sample_limit=args.sample_limit,
    )
    print(json.dumps({"output": str(args.out), "entry_count": len(manifest["entries"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
