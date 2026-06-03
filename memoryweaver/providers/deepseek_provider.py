"""DeepSeek provider for low-privilege GraphProposal generation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from memoryweaver.graph_schema import GraphProposal, GraphRelation
from memoryweaver.providers.base import BaseHTTPGraphProposalProvider, ProviderRequest


class DeepSeekGraphProposalProvider(BaseHTTPGraphProposalProvider):
    provider_name = "deepseek"
    api_key_attr = "deepseek_api_key"
    endpoint = "https://api.deepseek.com/chat/completions"
    prompt_version = "graph_proposal_deepseek_v0.4"

    def propose_graph_links(self, request: ProviderRequest) -> list[GraphProposal]:
        if not self.available():
            return []
        payload = self._build_payload(request)
        response = self._post_json(payload)
        content = (
            response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return self._parse_proposals(content)

    def _build_payload(self, request: ProviderRequest) -> dict:
        prompt = _load_prompt()
        instruction = {
            "task": "Generate candidate GraphProposal objects only.",
            "prompt_version": self.prompt_version,
            "schema": {
                "proposals": [
                    {
                        "from_tag": "codex_subscription_failed",
                        "to_tag": "selected_organization",
                        "relation": "related_to",
                        "confidence": 0.58,
                        "reason": "short evidence-grounded reason",
                        "evidence_ids": ["evidence_001"],
                        "risk": "medium",
                        "requires_review": True,
                    }
                ]
            },
            "input": {
                "query": request.query,
                "tags": request.tags,
                "memories": request.memories[:8],
                "evidence": request.evidence[:8],
            },
        }
        return {
            "model": self.config.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": prompt,
                },
                {"role": "user", "content": json.dumps(instruction, ensure_ascii=False)},
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
        }

    def _post_json(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.deepseek_api_key}",
        }
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers=headers,
            method="POST",
        )
        last_error: Exception | None = None
        attempts = max(1, self.config.llm_max_retries + 1)
        for _ in range(attempts):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.config.llm_timeout_seconds,
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
        raise RuntimeError(f"DeepSeek graph proposal request failed: {last_error}")

    def _parse_proposals(self, content: str) -> list[GraphProposal]:
        raw = content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        data = json.loads(raw)
        proposals = data.get("proposals", data if isinstance(data, list) else [])
        parsed: list[GraphProposal] = []
        for item in proposals:
            try:
                relation = GraphRelation(item.get("relation", "related_to"))
                evidence_ids = list(item.get("evidence_ids", []))
                evidence_links = list(item.get("evidence_links", [])) or evidence_ids
                from_tag = item.get("from_tag", item.get("from_node", item.get("from_text", "")))
                to_tag = item.get("to_tag", item.get("to_node", item.get("to_text", "")))
                confidence = _coerce_confidence(item.get("confidence", 0.0))
                if not evidence_ids:
                    confidence = min(confidence, self.config.llm_proposal_confidence_cap)
                parsed.append(GraphProposal(
                    proposal_type=item.get("proposal_type", "link_tags"),
                    source="llm",
                    from_node=from_tag,
                    to_node=to_tag,
                    from_tag=from_tag,
                    to_tag=to_tag,
                    relation=relation,
                    reason=item.get("reason", ""),
                    confidence=confidence,
                    status="pending",
                    requires_review=True,
                    risk=item.get("risk", "medium"),
                    evidence_links=evidence_links,
                    evidence_ids=evidence_ids,
                    metadata={
                        "provider": "deepseek",
                        "model": self.config.llm_model,
                        "prompt_version": self.prompt_version,
                    },
                ))
            except (TypeError, ValueError):
                continue
        return [
            proposal for proposal in parsed
            if proposal.from_node and proposal.to_node
        ]


def _load_prompt() -> str:
    path = Path(__file__).resolve().parents[1] / "prompts" / "graph_proposal_deepseek.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return (
            "You are a low-privilege LLM GraphProposal Provider. "
            "Return strict JSON only. Never write edges, memories, or patterns."
        )


def _coerce_confidence(value: object) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.0
