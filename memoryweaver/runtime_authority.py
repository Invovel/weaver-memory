"""Runtime Memory Authority — the core intervention layer.

This module is NOT a benchmark. It is the runtime component that sits between
LLM agent and memory store. At each agent step it:

1. Retrieves candidate memories (source-gated, freshness-filtered)
2. Checks marker eligibility (matched CoreIssueNode → HarnessMarker)
3. Builds a policy decision: what context can enter, what actions are warned
4. Records the decision in a hash-chained ledger

Principles (HARD):
- CAN inject context, route hints, evidence requirements, known-bad warnings
- CANNOT execute tools, promote memory, mutate Layer 3, bypass source gate
- Every decision is auditable via decision ledger
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from memoryweaver.contradiction import ContradictionResolver
from memoryweaver.policy import MemoryPolicy, RetrievalPolicy
from memoryweaver.retriever import VerifiedRetriever
from memoryweaver.schema import MemoryItem, Source
from memoryweaver.store import MemoryStore


# ---------------------------------------------------------------------------
# Runtime decision types
# ---------------------------------------------------------------------------


@dataclass
class RuntimePolicyDecision:
    """What MemoryWeaver decided about this agent step.

    This is NOT an action. It's a set of constraints on what can enter context
    and what the agent should be warned about.
    """

    decision_id: str
    step: int
    arm: str  # no_memory, mw_memory, mw_marker

    # Context injection — what MW allows into the LLM's system prompt
    allowed_memories: list[MemoryItem] = field(default_factory=list)
    blocked_memories: list[MemoryItem] = field(default_factory=list)

    # Marker signals — from CoreIssueNode → HarnessMarker matching
    marker_activated: bool = False
    marker_id: str = ""
    core_issue_title: str = ""
    recommended_route: str = "thinking"  # thinking | fast_verify
    max_route: str = "fast_verify"       # never "fast" without stable pattern

    # Known bad path suppression
    known_bad_warnings: list[str] = field(default_factory=list)
    suppressed_actions: list[str] = field(default_factory=list)

    # Evidence requirements — what MUST be checked before acting
    required_evidence: list[str] = field(default_factory=list)
    evidence_checklist_complete: bool = False

    # Safety counters (always zero — these are hard invariants)
    tool_execution_count: int = 0
    memory_promotion_count: int = 0
    layer3_mutation_count: int = 0
    online_llm_call_count: int = 0

    # Audit
    policy_version: str = "runtime-memory-authority-v1"
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))


# ---------------------------------------------------------------------------
# Marker store — maps CoreIssueNodes to HarnessMarkers
# ---------------------------------------------------------------------------


@dataclass
class CoreIssueRecord:
    """A recognized recurring issue."""

    issue_id: str
    title: str
    scope: dict  # {project, environment, tool, platform}
    trigger_tags: list[str]
    trigger_query_patterns: list[str]
    supporting_memory_ids: list[str]
    confidence: float
    status: str  # candidate | active | stable


@dataclass
class HarnessMarkerRecord:
    """A runtime projection of a CoreIssueRecord."""

    marker_id: str
    source_issue_id: str
    marker_type: str  # guard | route | evidence
    level: str  # L0_trace | L1_hint | L2_route | L3_guard
    trigger_tags: list[str]
    trigger_query_patterns: list[str]
    suppressed_actions: list[str]
    required_evidence: list[str]
    recommended_route: str
    max_route: str
    status: str  # candidate | active | verified
    drift_score: float = 0.0


class MarkerStore:
    """In-memory store for CoreIssues and HarnessMarkers.

    In production this would be backed by JSON/DB. For the runtime authority
    prototype it's an in-memory registry populated by mw marker CLI or manual seed.
    """

    def __init__(self) -> None:
        self._issues: dict[str, CoreIssueRecord] = {}
        self._markers: dict[str, HarnessMarkerRecord] = {}

    def add_issue(self, issue: CoreIssueRecord) -> None:
        self._issues[issue.issue_id] = issue

    def add_marker(self, marker: HarnessMarkerRecord) -> None:
        self._markers[marker.marker_id] = marker

    def get_marker(self, marker_id: str) -> HarnessMarkerRecord | None:
        return self._markers.get(marker_id)

    def match(self, query: str, tags: list[str]) -> list[HarnessMarkerRecord]:
        """Find markers whose trigger conditions match the current query + tags."""
        matched: list[HarnessMarkerRecord] = []
        query_lower = query.lower()
        tag_set = set(tags)

        for marker in self._markers.values():
            if marker.status not in ("active", "verified"):
                continue

            # Check tag overlap
            marker_tags = set(marker.trigger_tags)
            if marker_tags and not marker_tags.intersection(tag_set):
                continue

            # Check query patterns
            patterns = marker.trigger_query_patterns
            if patterns:
                if not any(p.lower() in query_lower for p in patterns):
                    continue

            matched.append(marker)

        # Sort by level priority: L3 > L2 > L1 > L0
        level_order = {"L3_guard": 4, "L2_route": 3, "L1_hint": 2, "L0_trace": 1}
        matched.sort(key=lambda m: level_order.get(m.level, 0), reverse=True)
        return matched


# ---------------------------------------------------------------------------
# Decision ledger — hash-chained audit trail
# ---------------------------------------------------------------------------

ZERO_HASH = "0" * 64


def _hash_record(record: dict) -> str:
    payload = dict(record)
    payload.pop("record_hash", None)
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


class DecisionLedger:
    """Hash-chained record of every MW runtime decision."""

    def __init__(self) -> None:
        self._decisions: list[dict] = []
        self._previous_hash = ZERO_HASH
        self._sequence = 0

    def record(self, decision: RuntimePolicyDecision) -> str:
        self._sequence += 1
        record = {
            "sequence": self._sequence,
            "previous_hash": self._previous_hash,
            "decision_id": decision.decision_id,
            "step": decision.step,
            "arm": decision.arm,
            "marker_activated": decision.marker_activated,
            "marker_id": decision.marker_id,
            "recommended_route": decision.recommended_route,
            "max_route": decision.max_route,
            "suppressed_actions": decision.suppressed_actions,
            "required_evidence": decision.required_evidence,
            "allowed_memory_count": len(decision.allowed_memories),
            "blocked_memory_count": len(decision.blocked_memories),
            "tool_execution_count": decision.tool_execution_count,
            "memory_promotion_count": decision.memory_promotion_count,
            "layer3_mutation_count": decision.layer3_mutation_count,
            "policy_version": decision.policy_version,
            "timestamp": decision.timestamp,
        }
        record["record_hash"] = _hash_record(record)
        self._decisions.append(record)
        self._previous_hash = record["record_hash"]
        return record["record_hash"]

    def validate_chain(self) -> list[str]:
        errors: list[str] = []
        previous = ZERO_HASH
        for i, record in enumerate(self._decisions, 1):
            if record.get("sequence") != i:
                errors.append(f"sequence mismatch at {i}")
            if record.get("previous_hash") != previous:
                errors.append(f"previous_hash break at {i}")
            computed = _hash_record(record)
            if record.get("record_hash") != computed:
                errors.append(f"hash mismatch at {i}")
            previous = str(record.get("record_hash", ""))
        return errors

    @property
    def decisions(self) -> list[dict]:
        return list(self._decisions)


# ---------------------------------------------------------------------------
# Runtime Memory Authority — the core
# ---------------------------------------------------------------------------


class RuntimeMemoryAuthority:
    """The central runtime component.

    Usage per agent step:
        auth = RuntimeMemoryAuthority(store, marker_store, ledger)
        decision = auth.evaluate(query, tags, arm, step)

        # Inject allowed memories into LLM system prompt
        context = auth.build_context(decision)

        # After agent action, check if marker was followed
        auth.record_outcome(decision, action_result)
    """

    def __init__(
        self,
        store: MemoryStore,
        marker_store: MarkerStore | None = None,
        ledger: DecisionLedger | None = None,
    ) -> None:
        self._store = store
        self._retriever = VerifiedRetriever(store)
        self._memory_policy = MemoryPolicy()
        self._retrieval_policy = RetrievalPolicy()
        self._contradiction_resolver = ContradictionResolver()
        self._marker_store = marker_store or MarkerStore()
        self._ledger = ledger or DecisionLedger()

    # ------------------------------------------------------------------
    # Step 1: Evaluate — what should happen at this step
    # ------------------------------------------------------------------

    def evaluate(
        self,
        query: str,
        tags: list[str],
        arm: str,
        step: int,
        *,
        candidate_ids: list[str] | None = None,
    ) -> RuntimePolicyDecision:
        """Produce a policy decision for one agent step.

        The decision says:
        - Which memories can enter context
        - Whether a marker matches
        - What evidence is required
        - What actions are warned

        It does NOT:
        - Execute tools
        - Promote memory
        - Call an LLM
        """

        # --- Retrieve candidates ---
        if arm == "no_memory":
            # No persistent memory — empty context
            allowed = []
            blocked = []
        else:
            # Retrieve with source gate
            if candidate_ids:
                all_candidates = []
                for mid in candidate_ids:
                    m = self._store.get(mid)
                    if m is not None:
                        all_candidates.append(m)
            else:
                all_candidates = self._store.find_similar(query, threshold=0.1)

            allowed = []
            blocked = []
            for item in all_candidates:
                if self._retrieval_policy.should_include(item, include_unverified=(arm == "mw_marker")):
                    allowed.append(item)
                else:
                    blocked.append(item)

        # --- Match markers ---
        markers = self._marker_store.match(query, tags)
        best_marker = markers[0] if markers else None

        # --- Build decision ---
        decision_id = f"d_{step}_{arm}_{int(time.time() * 1000)}"

        if best_marker and arm == "mw_marker":
            decision = RuntimePolicyDecision(
                decision_id=decision_id,
                step=step,
                arm=arm,
                allowed_memories=allowed,
                blocked_memories=blocked,
                marker_activated=True,
                marker_id=best_marker.marker_id,
                core_issue_title="",
                recommended_route=best_marker.recommended_route,
                max_route=best_marker.max_route,
                known_bad_warnings=best_marker.suppressed_actions,
                suppressed_actions=best_marker.suppressed_actions,
                required_evidence=best_marker.required_evidence,
            )
        else:
            decision = RuntimePolicyDecision(
                decision_id=decision_id,
                step=step,
                arm=arm,
                allowed_memories=allowed,
                blocked_memories=blocked,
            )

        # --- Record in ledger ---
        self._ledger.record(decision)

        return decision

    # ------------------------------------------------------------------
    # Step 2: Build context — format memories + markers for LLM prompt
    # ------------------------------------------------------------------

    def build_context(self, decision: RuntimePolicyDecision) -> str:
        """Build the context string to inject into the LLM system prompt.

        This is what the LLM sees about past experience. It is NOT an action plan.
        """

        if decision.arm == "no_memory":
            return ""

        parts: list[str] = []

        # Verified memories
        if decision.allowed_memories:
            parts.append("## Relevant Past Experience")
            for i, item in enumerate(decision.allowed_memories[:5], 1):
                src_label = f"[{item.source.value}]"
                memory_label = item.id.replace("_", " ")
                polarity_mark = ""
                if item.polarity.value == "negative":
                    polarity_mark = " ⚠️ AVOID"
                elif item.polarity.value == "ambiguous":
                    polarity_mark = " [UNVERIFIED]"
                parts.append(
                    f"{i}. {src_label}{polarity_mark} ({memory_label}) {item.content}"
                )

        # Marker guidance
        if decision.marker_activated:
            parts.append("")
            parts.append("## Diagnostic Guidance (MemoryWeaver Marker)")
            parts.append(f"Issue recognized: {decision.marker_id}")
            parts.append(f"Recommended route: {decision.recommended_route}")

            if decision.known_bad_warnings:
                parts.append(
                    f"KNOWN BAD PATHS (avoid these): {', '.join(decision.known_bad_warnings)}"
                )

            if decision.required_evidence:
                parts.append(
                    f"RECOMMENDED EVIDENCE (check these first): {', '.join(decision.required_evidence)}"
                )

        # Blocked summary (optional — for debugging)
        if decision.blocked_memories and False:  # set True for debug
            parts.append("")
            parts.append(f"[debug] {len(decision.blocked_memories)} memories blocked by source gate")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Step 3: Record outcome — did the agent follow the marker?
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        decision: RuntimePolicyDecision,
        agent_action: str,
        agent_target: str,
    ) -> dict[str, bool]:
        """After the agent acts, check whether it followed the marker.

        Returns a dict of compliance checks (for trace/metrics, not enforcement).
        """

        checks: dict[str, bool] = {}

        if decision.marker_activated:
            # Did agent avoid known bad paths?
            target_lower = agent_target.lower().replace(" ", "_")
            for bad in decision.suppressed_actions:
                bad_norm = bad.lower().replace(" ", "_")
                if bad_norm in target_lower or target_lower in bad_norm:
                    checks["known_bad_attempted"] = True
                    break
            else:
                checks["known_bad_attempted"] = False

            # Did agent check required evidence?
            for evidence in decision.required_evidence:
                ev_norm = evidence.lower().replace(" ", "_")
                if ev_norm in target_lower:
                    checks[f"evidence_checked:{evidence}"] = True
                else:
                    checks[f"evidence_checked:{evidence}"] = False

        return checks

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def ledger(self) -> DecisionLedger:
        return self._ledger

    @property
    def marker_store(self) -> MarkerStore:
        return self._marker_store


# ---------------------------------------------------------------------------
# Factory — build a runtime authority from a workspace
# ---------------------------------------------------------------------------


def create_runtime_authority(
    store: MemoryStore,
    core_issues: list[dict] | None = None,
    markers: list[dict] | None = None,
) -> RuntimeMemoryAuthority:
    """Create a RuntimeMemoryAuthority with optional marker seeding."""

    ms = MarkerStore()

    if core_issues:
        for ci in core_issues:
            ms.add_issue(CoreIssueRecord(
                issue_id=str(ci["id"]),
                title=str(ci.get("title", "")),
                scope=dict(ci.get("scope", {})),
                trigger_tags=list(ci.get("trigger_tags", [])),
                trigger_query_patterns=list(ci.get("trigger_query_patterns", [])),
                supporting_memory_ids=list(ci.get("supporting_memory_ids", [])),
                confidence=float(ci.get("confidence", 0.5)),
                status=str(ci.get("status", "candidate")),
            ))

    if markers:
        for m in markers:
            ms.add_marker(HarnessMarkerRecord(
                marker_id=str(m["id"]),
                source_issue_id=str(m.get("source_issue_id", "")),
                marker_type=str(m.get("marker_type", "guard")),
                level=str(m.get("level", "L1_hint")),
                trigger_tags=list(m.get("trigger_tags", [])),
                trigger_query_patterns=list(m.get("trigger_query_patterns", [])),
                suppressed_actions=list(m.get("suppressed_actions", [])),
                required_evidence=list(m.get("required_evidence", [])),
                recommended_route=str(m.get("recommended_route", "fast_verify")),
                max_route=str(m.get("max_route", "fast_verify")),
                status=str(m.get("status", "active")),
            ))

    return RuntimeMemoryAuthority(store, marker_store=ms)
