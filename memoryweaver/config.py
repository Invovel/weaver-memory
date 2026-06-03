"""Configuration for optional low-privilege LLM graph proposals."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def load_env_file(path: str | Path = ".env") -> dict[str, str]:
    """Read a simple KEY=VALUE file without mutating os.environ."""
    env_path = Path(path)
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass(frozen=True)
class MemoryWeaverConfig:
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    enable_llm_graph_proposal: bool = False
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2
    llm_proposal_confidence_cap: float = 0.6
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    dashscope_api_key: str = ""

    @classmethod
    def from_env(
        cls,
        *,
        env: dict[str, str] | None = None,
        env_file: str | Path | None = None,
    ) -> "MemoryWeaverConfig":
        values = dict(os.environ if env is None else env)
        if env_file is not None:
            file_values = load_env_file(env_file)
            file_values.update(values)
            values = file_values
        cap = max(0.0, min(_float(
            values.get("MEMORYWEAVER_LLM_PROPOSAL_CONFIDENCE_CAP"),
            0.6,
        ), 1.0))
        return cls(
            llm_provider=values.get("MEMORYWEAVER_LLM_PROVIDER", "openai"),
            llm_model=values.get("MEMORYWEAVER_LLM_MODEL", "gpt-4.1-mini"),
            enable_llm_graph_proposal=_bool(
                values.get("MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL"),
                False,
            ),
            llm_timeout_seconds=_int(
                values.get("MEMORYWEAVER_LLM_TIMEOUT_SECONDS"),
                30,
            ),
            llm_max_retries=_int(values.get("MEMORYWEAVER_LLM_MAX_RETRIES"), 2),
            llm_proposal_confidence_cap=cap,
            openai_api_key=values.get("OPENAI_API_KEY", ""),
            anthropic_api_key=values.get("ANTHROPIC_API_KEY", ""),
            deepseek_api_key=values.get("DEEPSEEK_API_KEY", ""),
            dashscope_api_key=values.get("DASHSCOPE_API_KEY", ""),
        )

    def api_key_for_provider(self, provider: str | None = None) -> str:
        name = (provider or self.llm_provider).lower()
        if name == "openai":
            return self.openai_api_key
        if name == "anthropic":
            return self.anthropic_api_key
        if name == "deepseek":
            return self.deepseek_api_key
        if name == "qwen":
            return self.dashscope_api_key
        if name == "local":
            return "local"
        return ""

    def graph_proposals_available(self) -> bool:
        return (
            self.enable_llm_graph_proposal
            and bool(self.api_key_for_provider())
        )
