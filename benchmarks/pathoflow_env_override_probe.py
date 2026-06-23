"""Probe PathoFlow .env override behavior for the live ask path."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHOFLOW_ROOT = Path(r"D:\Download\PathoFlow")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "pathoflow-tool-native-workflow-compare-2026-06-14"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe PathoFlow .env override effects on live ask.")
    parser.add_argument("--pathoflow-root", default=str(DEFAULT_PATHOFLOW_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--backend", default="gpt-5.5")
    args = parser.parse_args()

    pathoflow_root = Path(args.pathoflow_root)
    output_dir = Path(args.output_dir)

    sys.path.insert(0, str(pathoflow_root.parent))
    load_dotenv(pathoflow_root / ".env", override=True)

    from PathoFlow.core.engine import PathoFlowEngine
    import os

    env_snapshot = {
        "OPENAI_API_KEY_present": bool(os.environ.get("OPENAI_API_KEY")),
        "RIGHTCODE_OPENAI_API_KEY_present": bool(os.environ.get("RIGHTCODE_OPENAI_API_KEY")),
        "IKUNCODE_OPENAI_API_KEY_present": bool(os.environ.get("IKUNCODE_OPENAI_API_KEY")),
        "IKUNCODING_OPENAI_API_KEY_present": bool(os.environ.get("IKUNCODING_OPENAI_API_KEY")),
        "PATHOFLOW_GPT_5_5_PROVIDER": os.environ.get("PATHOFLOW_GPT_5_5_PROVIDER", ""),
        "PATHOFLOW_DEFAULT_MODEL": os.environ.get("PATHOFLOW_DEFAULT_MODEL", ""),
    }

    kb = str(pathoflow_root / "backups" / "kb" / "knowledge_base_aligned_before_p0_1_2026-05-02.xlsx")
    engine = PathoFlowEngine(kb, use_hybrid_retrieval=True)
    result = engine.ask(
        query="目前没有IHC，也没有稳定ROI，切片来自两个中心，先希望全片跑，再抽几张人工复核。",
        user_type="科研型",
        return_raw_json=True,
        backend=args.backend,
        conversation_history=[
            {"role": "user", "content": "我们有36张肺癌NDPI HE切片，想看肿瘤浸润淋巴细胞密度和免疫冷热趋势。"},
            {"role": "assistant", "content": "这应走H&E免疫/TME代理链路，而不是MIL、泛癌检测或IHC定量。建议为IMM-TME-001记录29信息汇总、40质控、1前景分割、53核分割分类和77核级pathomics；输出淋巴细胞样细胞密度、空间分布和邻域特征。 需要确认是否有肿瘤区/间质区ROI，还是先按全片探索。"},
            {"role": "user", "content": "目前没有IHC，也没有稳定ROI，切片来自两个中心，先希望全片跑，再抽几张人工复核。"},
        ],
    )

    payload = {
        "generated_at": datetime.now().isoformat(),
        "pathoflow_env_path": str(pathoflow_root / ".env"),
        "backend": args.backend,
        "env_snapshot": env_snapshot,
        "python_requests_proxy_env": {
            "HTTP_PROXY_present": bool(os.environ.get("HTTP_PROXY")),
            "HTTPS_PROXY_present": bool(os.environ.get("HTTPS_PROXY")),
            "ALL_PROXY_present": bool(os.environ.get("ALL_PROXY")),
            "NO_PROXY": os.environ.get("NO_PROXY", ""),
        },
        "ask_result": result,
        "interpretation": {
            "env_loaded": True,
            "provider_route_effective": env_snapshot["PATHOFLOW_GPT_5_5_PROVIDER"] == "ikuncode",
            "default_model_effective": bool(env_snapshot["PATHOFLOW_DEFAULT_MODEL"]),
            "live_ask_success": not bool(result.get("_error")) if isinstance(result, dict) else False,
            "likely_root_cause": "provider token invalid or unsupported for current relay" if isinstance(result, dict) and result.get("_error") else "",
        },
    }
    write_json(output_dir / "env_override_probe.json", payload)
    print(f"[pathoflow-env-override-probe] wrote probe to {output_dir}")


if __name__ == "__main__":
    main()
