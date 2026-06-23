"""Deterministic lifecycle contracts for environment, tools, and sources."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from memoryweaver.schema import Source


@dataclass
class SourceAuthority:
    """What a source may do inside the lifecycle harness."""

    source: Source
    may_enter_candidate: bool = True
    may_become_verified: bool = False
    may_drive_runtime_context: bool = False
    max_confidence_without_external_verification: float = 0.0
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            self.source = Source(self.source)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceAuthority":
        payload = dict(data)
        payload["source"] = Source(payload["source"])
        return cls(**payload)


@dataclass
class ToolContract:
    """Allowlisted execution shape for one tool or action surface."""

    name: str
    description: str = ""
    allowed: bool = True
    required_args: list[str] = field(default_factory=list)
    optional_args: list[str] = field(default_factory=list)
    idempotency_required: bool = False
    requires_confirmation: bool = False
    confirmation_targets: list[str] = field(default_factory=list)
    allowed_workdirs: list[str] = field(default_factory=list)
    max_timeout_seconds: int = 60
    resource_budget: dict[str, int] = field(default_factory=dict)
    side_effect_level: str = "none"
    notes: str = ""

    def validate_arguments(self, arguments: dict[str, Any]) -> list[str]:
        missing = []
        for name in self.required_args:
            value = arguments.get(name)
            if value in ("", None):
                missing.append(name)
        return missing

    def target_requires_confirmation(self, target: str) -> bool:
        if self.requires_confirmation:
            return True
        normalized = target.lower().replace(" ", "_")
        return any(
            token.lower().replace(" ", "_") in normalized
            for token in self.confirmation_targets
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolContract":
        return cls(**data)


@dataclass
class EnvironmentContract:
    """Explicit runtime contract loaded before interaction begins."""

    contract_id: str = "memoryweaver-live-loop"
    version: str = "environment-contract-v1"
    description: str = ""
    tool_contracts: dict[str, ToolContract] = field(default_factory=dict)
    source_authority: dict[str, SourceAuthority] = field(default_factory=dict)
    allowed_workdirs: list[str] = field(default_factory=list)
    max_steps: int = 8
    max_tool_calls: int = 4
    default_timeout_seconds: int = 30
    resource_budget: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.tool_contracts = {
            name: contract
            if isinstance(contract, ToolContract)
            else ToolContract.from_dict(contract)
            for name, contract in self.tool_contracts.items()
        }
        self.source_authority = {
            name: authority
            if isinstance(authority, SourceAuthority)
            else SourceAuthority.from_dict(authority)
            for name, authority in self.source_authority.items()
        }

    def tool(self, name: str) -> ToolContract | None:
        return self.tool_contracts.get(name)

    def authority_for(self, source: Source | str) -> SourceAuthority | None:
        key = source.value if isinstance(source, Source) else str(source)
        return self.source_authority.get(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "version": self.version,
            "description": self.description,
            "tool_contracts": {
                name: contract.to_dict()
                for name, contract in self.tool_contracts.items()
            },
            "source_authority": {
                name: authority.to_dict()
                for name, authority in self.source_authority.items()
            },
            "allowed_workdirs": list(self.allowed_workdirs),
            "max_steps": self.max_steps,
            "max_tool_calls": self.max_tool_calls,
            "default_timeout_seconds": self.default_timeout_seconds,
            "resource_budget": dict(self.resource_budget),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnvironmentContract":
        return cls(**data)

    @classmethod
    def default_live_loop(
        cls,
        *,
        max_steps: int = 8,
        max_tool_calls: int = 4,
    ) -> "EnvironmentContract":
        return cls(
            description=(
                "Default MemoryWeaver runtime contract for the v0.7 live loop. "
                "Only structured allowlisted actions may execute."
            ),
            tool_contracts={
                "tool_call": ToolContract(
                    name="tool_call",
                    description="Potentially side-effecting tool execution.",
                    required_args=["target"],
                    idempotency_required=True,
                    max_timeout_seconds=60,
                    resource_budget={"tool_calls": 1, "wall_clock_seconds": 60},
                    side_effect_level="medium",
                    confirmation_targets=[
                        "reset_auth_files",
                        "delete",
                        "drop_database",
                        "publish_release",
                        "push_latest",
                    ],
                    notes="High-risk destructive targets require explicit confirmation.",
                ),
                "check_evidence": ToolContract(
                    name="check_evidence",
                    description="Read-only evidence or diagnostic observation.",
                    required_args=["target"],
                    max_timeout_seconds=30,
                    side_effect_level="none",
                ),
                "ask_user": ToolContract(
                    name="ask_user",
                    description="Pause and ask the user for confirmation or clarification.",
                    required_args=["target"],
                    max_timeout_seconds=30,
                    side_effect_level="none",
                ),
                "resolve": ToolContract(
                    name="resolve",
                    description="Return a final answer or success signal without side effects.",
                    max_timeout_seconds=30,
                    side_effect_level="none",
                ),
            },
            source_authority=_default_source_authority(),
            max_steps=max_steps,
            max_tool_calls=max_tool_calls,
            default_timeout_seconds=30,
            resource_budget={
                "steps": max_steps,
                "tool_calls": max_tool_calls,
                "wall_clock_seconds": 120,
            },
        )


def _default_source_authority() -> dict[str, SourceAuthority]:
    return {
        Source.USER.value: SourceAuthority(
            source=Source.USER,
            may_enter_candidate=True,
            may_become_verified=True,
            may_drive_runtime_context=True,
            max_confidence_without_external_verification=1.0,
            notes="Direct human feedback remains highest authority.",
        ),
        Source.TERMINAL.value: SourceAuthority(
            source=Source.TERMINAL,
            may_enter_candidate=True,
            may_become_verified=True,
            may_drive_runtime_context=True,
            max_confidence_without_external_verification=1.0,
            notes="Terminal observations are externally verifiable.",
        ),
        Source.TOOL.value: SourceAuthority(
            source=Source.TOOL,
            may_enter_candidate=True,
            may_become_verified=True,
            may_drive_runtime_context=True,
            max_confidence_without_external_verification=0.9,
            notes="Tool feedback is admissible evidence when structured.",
        ),
        Source.FILE.value: SourceAuthority(
            source=Source.FILE,
            may_enter_candidate=True,
            may_become_verified=True,
            may_drive_runtime_context=True,
            max_confidence_without_external_verification=0.6,
            notes="File evidence requires provenance and version awareness.",
        ),
        Source.WEB.value: SourceAuthority(
            source=Source.WEB,
            may_enter_candidate=True,
            may_become_verified=True,
            may_drive_runtime_context=True,
            max_confidence_without_external_verification=0.6,
            notes="Web evidence needs freshness and provenance checks.",
        ),
        Source.COMPOSER.value: SourceAuthority(
            source=Source.COMPOSER,
            may_enter_candidate=True,
            may_become_verified=False,
            may_drive_runtime_context=True,
            max_confidence_without_external_verification=0.5,
            notes="Composed patterns are advisory until explicitly validated.",
        ),
        Source.ASSISTANT.value: SourceAuthority(
            source=Source.ASSISTANT,
            may_enter_candidate=True,
            may_become_verified=False,
            may_drive_runtime_context=False,
            max_confidence_without_external_verification=0.3,
            notes="Assistant output stays ambiguous until externally verified.",
        ),
        Source.SYNTHETIC.value: SourceAuthority(
            source=Source.SYNTHETIC,
            may_enter_candidate=True,
            may_become_verified=False,
            may_drive_runtime_context=False,
            max_confidence_without_external_verification=0.3,
            notes="Synthetic text is a retrieval aid, not verified memory.",
        ),
        Source.UNKNOWN.value: SourceAuthority(
            source=Source.UNKNOWN,
            may_enter_candidate=True,
            may_become_verified=False,
            may_drive_runtime_context=False,
            max_confidence_without_external_verification=0.0,
            notes="Unknown provenance cannot become verified by default.",
        ),
    }
