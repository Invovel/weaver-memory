"""Raw protocol compatibility probe for PathoFlow LLM relays."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "pathoflow-tool-native-workflow-compare-2026-06-14"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe raw Responses vs Chat Completions compatibility.")
    parser.add_argument("--base-url", default="https://api.66hk.top/v1")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    headers = {
        "Authorization": f"Bearer {args.api_key}",
        "Content-Type": "application/json",
    }
    probes = {
        "responses": {
            "url": args.base_url.rstrip("/") + "/responses",
            "json": {
                "model": args.model,
                "input": [{"role": "user", "content": "Reply with exactly OK"}],
                "max_output_tokens": 32,
            },
        },
        "chat_completions": {
            "url": args.base_url.rstrip("/") + "/chat/completions",
            "json": {
                "model": args.model,
                "messages": [{"role": "user", "content": "Reply with exactly OK"}],
                "max_tokens": 32,
            },
        },
    }

    results: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "base_url": args.base_url,
        "model": args.model,
        "probes": {},
    }

    for name, spec in probes.items():
        try:
            resp = requests.post(spec["url"], headers=headers, json=spec["json"], timeout=60)
            try:
                body_json = resp.json()
            except Exception:
                body_json = None
            results["probes"][name] = {
                "status_code": resp.status_code,
                "content_type": resp.headers.get("Content-Type", ""),
                "body_json": body_json,
                "body_text": resp.text[:2000],
            }
        except Exception as exc:
            results["probes"][name] = {
                "exception_type": type(exc).__name__,
                "exception": str(exc),
            }

    responses_ok = results["probes"].get("responses", {}).get("status_code") == 200
    chat_ok = results["probes"].get("chat_completions", {}).get("status_code") == 200
    results["interpretation"] = {
        "responses_supported": responses_ok,
        "chat_completions_supported": chat_ok,
        "recommended_protocol": "chat_completions" if chat_ok and not responses_ok else ("responses" if responses_ok else "none"),
    }

    write_json(Path(args.output_dir) / "protocol_compat_probe.json", results)
    print(f"[pathoflow-protocol-compat-probe] wrote probe to {args.output_dir}")


if __name__ == "__main__":
    main()
