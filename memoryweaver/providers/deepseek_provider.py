"""DeepSeek provider for low-privilege GraphProposal generation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from memoryweaver.graph_schema import GraphProposal, GraphRelation
from memoryweaver.providers.base import BaseHTTPGraphProposalProvider, ProviderRequest


class DeepSeekGraphProposalProvider(BaseHTTPGraphProposalProvider):
    provider_name = "deepseek"
    api_key_attr = "deepseek_api_key"
    endpoint = "https://api.deepseek.com/chat/completions"

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
        instruction = {
            "task": "Generate candidate graph link proposals only.",
            "hard_rules": [
                "Return JSON only.",
                "Do not create graph edges.",
                "Do not write memory.",
                "Do not write or promote Pattern records.",
                "Each proposal must require review.",
            ],
            "schema": {
                "proposals": [
                    {
                        "source": "llm",
                        "proposal_type": "link_tags",
                        "from_node": "tag_or_node",
                        "to_node": "tag_or_node",
                        "relation": "related_to",
                        "reason": "short reason",
                        "confidence": 0.0,
                        "status": "pending",
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
                    "content": (
                        "You are a low-privilege graph proposal generator. "
                        "You can only propose candidate tag links as JSON."
                    ),
                },
                {"role": "user", "content": json.dumps(instruction, ensure_ascii=False)},
            ],
            "stream": False,
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
                parsed.append(GraphProposal(
                    proposal_type=item.get("proposal_type", "link_tags"),
                    source="llm",
                    from_node=item.get("from_node", item.get("from_text", "")),
                    to_node=item.get("to_node", item.get("to_text", "")),
                    relation=relation,
                    reason=item.get("reason", ""),
                    confidence=min(
                        float(item.get("confidence", 0.0)),
                        self.config.llm_proposal_confidence_cap,
                    ),
                    status="pending",
                    requires_review=True,
                    evidence_links=list(item.get("evidence_links", [])),
                    metadata={"provider": "deepseek", "model": self.config.llm_model},
                ))
            except (TypeError, ValueError):
                continue
        return [
            proposal for proposal in parsed
            if proposal.from_node and proposal.to_node
        ]
