"""Tau-style live loop with MemoryWeaver lifecycle writes.

The environment can be deterministic, but the trajectory is not prewritten by
the benchmark script: an agent policy chooses each action from the current
observation plus MemoryWeaver context.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from memoryweaver.action_gate import (
    ActionGate,
    ActionGateStatus,
)
from memoryweaver.config import MemoryWeaverConfig
from memoryweaver.contract import EnvironmentContract
from memoryweaver.harness import MemoryWeaverHarness
from memoryweaver.lifecycle import MemoryLifecycle
from memoryweaver.runtime_authority import RuntimeMemoryAuthority, create_runtime_authority
from memoryweaver.schema import Source
from memoryweaver.store import MemoryWorkspace
from memoryweaver.trajectory import TrajectoryRegulator, TrajectoryStatus


@dataclass
class LiveObservation:
    task_id: str
    goal: str
    state: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    done: bool = False
    success: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LiveAction:
    name: str
    target: str = ""
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LiveStep:
    step: int
    observation: dict[str, Any]
    memory_context: str
    proposal: dict[str, Any]
    action: dict[str, Any]
    result: dict[str, Any]
    memory_write_ids: list[str] = field(default_factory=list)
    decision: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LiveLoopResult:
    task_id: str
    success: bool
    step_count: int
    verified_memory_write_count: int
    promotion_count: int
    known_bad_path_write_count: int
    online_llm_call_count: int
    blocked_action_count: int
    recovery_count: int
    checkpoint_recommended_count: int
    steps: list[LiveStep]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "step_count": self.step_count,
            "verified_memory_write_count": self.verified_memory_write_count,
            "promotion_count": self.promotion_count,
            "known_bad_path_write_count": self.known_bad_path_write_count,
            "online_llm_call_count": self.online_llm_call_count,
            "blocked_action_count": self.blocked_action_count,
            "recovery_count": self.recovery_count,
            "checkpoint_recommended_count": self.checkpoint_recommended_count,
            "steps": [step.to_dict() for step in self.steps],
        }


class LiveEnv(Protocol):
    def reset(self, task_id: str) -> LiveObservation: ...
    def step(self, action: LiveAction) -> tuple[LiveObservation, dict[str, Any]]: ...


class LiveAgent(Protocol):
    def choose_action(
        self,
        observation: LiveObservation,
        memory_context: str,
        *,
        step: int,
    ) -> LiveAction: ...


class MockTauEnv:
    """Tiny deterministic tau-style environment for local smoke runs."""

    def __init__(self) -> None:
        self._observation = LiveObservation(
            task_id="",
            goal="",
            state={"selected_organization": "wrong_org", "subscription_loaded": False},
        )

    def reset(self, task_id: str) -> LiveObservation:
        self._observation = LiveObservation(
            task_id=task_id,
            goal="Resolve Codex subscription load failure without blind reinstall.",
            state={"selected_organization": "wrong_org", "subscription_loaded": False},
            history=[],
        )
        return self._observation

    def step(self, action: LiveAction) -> tuple[LiveObservation, dict[str, Any]]:
        target = f"{action.name}:{action.target}".lower()
        if "reinstall" in target:
            result = {
                "status": "failed_known_bad",
                "signal": "negative",
                "evidence": "npm reinstall did not change subscription load failure",
            }
        elif "organization" in target or "entitlement" in target:
            self._observation.state["selected_organization"] = "correct_org"
            self._observation.state["subscription_loaded"] = True
            self._observation.done = True
            self._observation.success = True
            result = {
                "status": "evidence_observed",
                "signal": "positive",
                "evidence": "selected organization and entitlement fixed subscription load",
            }
        else:
            result = {
                "status": "no_signal",
                "signal": "neutral",
                "evidence": "generic diagnostic did not resolve the issue",
            }
        self._observation.history.append({"action": action.to_dict(), "result": result})
        return self._observation, result


class RuleAgent:
    """Simple policy agent used for deterministic local smoke tests."""

    def choose_action(
        self,
        observation: LiveObservation,
        memory_context: str,
        *,
        step: int,
    ) -> LiveAction:
        text = memory_context.lower()
        if "organization" in text or "entitlement" in text:
            return LiveAction(
                name="check_evidence",
                target="selected_organization_and_entitlement",
                reasoning="MemoryWeaver context recommends evidence-first org check.",
            )
        if step == 1:
            return LiveAction(
                name="tool_call",
                target="reinstall_npm",
                reasoning="No memory guidance; try common reinstall path.",
            )
        return LiveAction(
            name="check_evidence",
            target="selected_organization",
            reasoning="Fallback to account organization evidence.",
        )


class OpenAICompatibleAgent:
    """LLM action policy for OpenAI-compatible chat-completions endpoints."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        provider: str = "openai_compatible",
        timeout: int = 60,
        temperature: float = 0.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.provider = provider
        self.timeout = timeout
        self.temperature = temperature
        self.online_llm_call_count = 0

    @classmethod
    def from_config(
        cls,
        config: MemoryWeaverConfig,
        *,
        provider: str = "",
        model: str = "",
        base_url: str = "",
    ) -> "OpenAICompatibleAgent":
        provider_name = (provider or config.llm_provider or "deepseek").lower()
        endpoint = base_url or _default_base_url(provider_name)
        model_name = model or config.llm_model
        api_key = config.api_key_for_provider(provider_name)
        if not api_key:
            raise ValueError(f"missing API key for provider '{provider_name}'")
        return cls(
            api_key=api_key,
            model=model_name,
            base_url=endpoint,
            provider=provider_name,
            timeout=config.llm_timeout_seconds,
        )

    def choose_action(
        self,
        observation: LiveObservation,
        memory_context: str,
        *,
        step: int,
    ) -> LiveAction:
        recommended_evidence = observation.state.get("recommended_evidence")
        if not isinstance(recommended_evidence, list):
            recommended_evidence = [str(recommended_evidence)] if recommended_evidence else []
        system_prompt = (
            "You are an agent action selector inside MemoryWeaver's v0.7 live loop. "
            "Choose exactly one next action. Return strict JSON only with keys "
            "name, target, reasoning. Allowed names: tool_call, check_evidence, "
            "ask_user, resolve. Prefer MemoryWeaver required evidence over blind "
            "reinstallation. If context warns about a known bad path, avoid it."
        )
        payload = {
            "step": step,
            "goal": observation.goal,
            "state": observation.state,
            "recent_history": observation.history[-4:],
            "memoryweaver_context": memory_context,
        }
        if recommended_evidence:
            payload["recommended_safe_action"] = {
                "name": "check_evidence",
                "target": "_and_".join(str(item) for item in recommended_evidence),
            }
        user_message = json.dumps(payload, ensure_ascii=False)
        raw = self._post(system_prompt, user_message)
        parsed = _parse_action_json(raw)
        return LiveAction(
            name=parsed.get("name", "ask_user"),
            target=parsed.get("target", "clarify"),
            reasoning=parsed.get("reasoning", raw[:240]),
        )

    def _post(self, system_prompt: str, user_message: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self.temperature,
            "max_tokens": 256,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(1, 4):
            self.online_llm_call_count += 1
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return str(data["choices"][0]["message"]["content"])
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(0.5 * attempt)
                    continue
        raise RuntimeError(f"{self.provider} action selection failed: {last_error}") from last_error


def _default_base_url(provider: str) -> str:
    if provider == "deepseek":
        return "https://api.deepseek.com/chat/completions"
    return "https://api.openai.com/v1/chat/completions"


def _parse_action_json(raw: str) -> dict[str, str]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"name": "ask_user", "target": "clarify", "reasoning": raw[:240]}
    name = str(data.get("name", data.get("action", "ask_user")))
    if name not in {"tool_call", "check_evidence", "ask_user", "resolve"}:
        name = "ask_user"
    return {
        "name": name,
        "target": str(data.get("target", "")),
        "reasoning": str(data.get("reasoning", "")),
    }


class MemoryWeaverLiveLoop:
    """Run a per-step agent loop with runtime authority and lifecycle writes."""

    def __init__(
        self,
        workspace: MemoryWorkspace,
        *,
        harness: MemoryWeaverHarness | None = None,
        authority: RuntimeMemoryAuthority | None = None,
        environment_contract: EnvironmentContract | None = None,
        action_gate: ActionGate | None = None,
        trajectory: TrajectoryRegulator | None = None,
    ) -> None:
        self.workspace = workspace
        self.lifecycle = MemoryLifecycle(workspace)
        self.harness = harness or MemoryWeaverHarness(
            workspace,
            environment_contract=environment_contract,
            runtime_authority=authority,
            action_gate=action_gate,
            trajectory=trajectory,
        )
        self.environment_contract = self.harness.environment_contract
        self.action_gate = self.harness.action_gate
        self.trajectory = self.harness.trajectory
        self.authority = self.harness.runtime_authority

    def run(
        self,
        *,
        task_id: str,
        env: LiveEnv,
        agent: LiveAgent,
        max_steps: int = 8,
        arm: str = "mw_marker",
    ) -> LiveLoopResult:
        effective_max_steps = min(max_steps, self.environment_contract.max_steps)
        self.trajectory.history.clear()
        self.trajectory.max_steps = effective_max_steps
        self.trajectory.max_tool_calls = self.environment_contract.max_tool_calls
        observation = env.reset(task_id)
        steps: list[LiveStep] = []
        verified_writes = 0
        promotions = 0
        known_bad_writes = 0
        blocked_actions = 0
        recoveries = 0
        checkpoint_recommendations = 0
        for step in range(1, effective_max_steps + 1):
            conditioning = self.harness.task_conditioning(
                observation.goal,
                tags=["codex", "subscription"],
                arm=arm,
                step=step,
            )
            decision = conditioning.runtime_decision
            if decision["required_evidence"]:
                observation.state["recommended_evidence"] = list(decision["required_evidence"])
            if decision["suppressed_actions"]:
                observation.state["known_bad_actions"] = list(decision["suppressed_actions"])
            memory_context = conditioning.combined_context or conditioning.runtime_context
            action = agent.choose_action(observation, memory_context, step=step)
            execution = self.harness.before_execution(
                action,
                task_id=task_id,
                step=step,
            )
            proposal = execution.proposal
            gate = execution.decision
            if gate.allowed:
                observation, result = env.step(action)
            else:
                blocked_actions += 1
                result_status = (
                    "needs_confirmation"
                    if gate.status == ActionGateStatus.NEEDS_CONFIRMATION
                    else "blocked_by_action_gate"
                )
                result = {
                    "status": result_status,
                    "signal": "negative",
                    "evidence": "; ".join(gate.reasons),
                }
                observation.history.append({"action": action.to_dict(), "result": result})

            feedback = self.harness.after_feedback(
                step=step,
                proposal=proposal,
                result=result,
                gate_status=gate.status.value,
            )
            trajectory = feedback.trajectory
            if trajectory.status == TrajectoryStatus.RECOVER:
                recoveries += 1
            if trajectory.checkpoint_recommended:
                checkpoint_recommendations += 1
            outcome = self.harness.after_task_outcome(
                task_id=task_id,
                step=step,
                action=action,
                result=result,
            )
            memory_ids = list(outcome.recorded_memory_ids)
            if memory_ids:
                verified_writes += outcome.verified_write_count
                promotions += outcome.promotion_count
                if result.get("status") == "failed_known_bad":
                    known_bad_writes += len(memory_ids)
            steps.append(
                LiveStep(
                    step=step,
                    observation=observation.to_dict(),
                    memory_context=memory_context,
                    proposal=proposal.to_dict(),
                    action=action.to_dict(),
                    result=result,
                    memory_write_ids=memory_ids,
                    decision={
                        **decision,
                        "skill_result": conditioning.skill_result.to_dict(),
                        "action_gate": gate.to_dict(),
                        "trajectory": trajectory.to_dict(),
                    },
                )
            )
            if observation.done or trajectory.status == TrajectoryStatus.HALT:
                break
        return LiveLoopResult(
            task_id=task_id,
            success=observation.success,
            step_count=len(steps),
            verified_memory_write_count=verified_writes,
            promotion_count=promotions,
            known_bad_path_write_count=known_bad_writes,
            online_llm_call_count=int(getattr(agent, "online_llm_call_count", 0)),
            blocked_action_count=blocked_actions,
            recovery_count=recoveries,
            checkpoint_recommended_count=checkpoint_recommendations,
            steps=steps,
        )
