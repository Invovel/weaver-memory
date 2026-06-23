"""v0.8 GBrain contracts and a minimal executable engine.

The contracts keep these boundaries explicit:

- LLM-authored candidate graph bundles
- GBrain raw retrieval output (`search`)
- GBrain synthesized answer output (`think`)
- Mind-map / runtime-graph projection payloads

The minimal engine at the bottom is intentionally deterministic. It lets v0.8
validation exercise candidate graph ingestion, point search, synthesis, and
mind-map projection without giving GBrain authority to promote memory or Layer-3
patterns.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol

from memoryweaver.graph_linker import tag_node_id
from memoryweaver.graph_schema import GraphEdge, GraphNode, GraphNodeType, GraphRelation, GraphStatus
from memoryweaver.schema import Layer, PatternStatus
from memoryweaver.store import MemoryWorkspace, token_jaccard


SearchMode = Literal["search", "think"]
GraphLayer = Literal["candidate", "verified", "runtime"]


@dataclass
class GBrainScope:
    """Scope contract inspired by gbrain's brain/source split.

    `brain_id` is the top-level memory authority boundary.
    `source_id` is the repo / subdomain / project slice inside that brain.
    """

    brain_id: str = "workspace"
    source_id: str = "default"
    workspace_root: str = ""
    owner_scope: str = "project"
    federated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GBrainCitation:
    ref_id: str
    ref_type: str
    layer: str = ""
    authority: str = ""
    freshness: str = ""
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GBrainGap:
    kind: str
    detail: str
    severity: str = "warn"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GBrainSearchHit:
    ref_id: str
    ref_type: str
    title: str
    score: float
    graph_layer: GraphLayer = "candidate"
    evidence: list[GBrainCitation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [item.to_dict() for item in self.evidence]
        return data


@dataclass
class GBrainSearchResult:
    mode: Literal["search"] = "search"
    query: str = ""
    scope: GBrainScope = field(default_factory=GBrainScope)
    hits: list[GBrainSearchHit] = field(default_factory=list)
    graph_signals: list[str] = field(default_factory=list)
    retrieval_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "query": self.query,
            "scope": self.scope.to_dict(),
            "hits": [hit.to_dict() for hit in self.hits],
            "graph_signals": list(self.graph_signals),
            "retrieval_notes": list(self.retrieval_notes),
        }


@dataclass
class GBrainThinkResult:
    mode: Literal["think"] = "think"
    query: str = ""
    scope: GBrainScope = field(default_factory=GBrainScope)
    answer: str = ""
    citations: list[GBrainCitation] = field(default_factory=list)
    gaps: list[GBrainGap] = field(default_factory=list)
    contradiction_warnings: list[str] = field(default_factory=list)
    stale_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "query": self.query,
            "scope": self.scope.to_dict(),
            "answer": self.answer,
            "citations": [item.to_dict() for item in self.citations],
            "gaps": [item.to_dict() for item in self.gaps],
            "contradiction_warnings": list(self.contradiction_warnings),
            "stale_warnings": list(self.stale_warnings),
        }


@dataclass
class GBrainCandidateNode:
    node_id: str
    node_type: str
    label: str
    source_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GBrainCandidateEdge:
    source_id: str
    target_id: str
    relation: str
    confidence: float = 0.0
    graph_layer: GraphLayer = "candidate"
    source_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GBrainCandidateBundle:
    """The only shape an LLM may propose into GBrain."""

    scope: GBrainScope = field(default_factory=GBrainScope)
    nodes: list[GBrainCandidateNode] = field(default_factory=list)
    edges: list[GBrainCandidateEdge] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)
    branch_notes: list[str] = field(default_factory=list)
    proposed_by: str = "llm"
    authority_granted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope.to_dict(),
            "nodes": [item.to_dict() for item in self.nodes],
            "edges": [item.to_dict() for item in self.edges],
            "summaries": list(self.summaries),
            "branch_notes": list(self.branch_notes),
            "proposed_by": self.proposed_by,
            "authority_granted": self.authority_granted,
        }


@dataclass
class GBrainMindMapDocument:
    """A layered mind-map payload for UI / runtime visualization."""

    scope: GBrainScope = field(default_factory=GBrainScope)
    center_query: str = ""
    candidate_nodes: list[dict[str, Any]] = field(default_factory=list)
    verified_nodes: list[dict[str, Any]] = field(default_factory=list)
    runtime_nodes: list[dict[str, Any]] = field(default_factory=list)
    candidate_edges: list[dict[str, Any]] = field(default_factory=list)
    verified_edges: list[dict[str, Any]] = field(default_factory=list)
    runtime_edges: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GBrainEngineV08(Protocol):
    """Contract-first interface, similar in spirit to garrytan/gbrain's engine."""

    def search(
        self,
        query: str,
        *,
        scope: GBrainScope,
        limit: int = 10,
    ) -> GBrainSearchResult: ...

    def think(
        self,
        query: str,
        *,
        scope: GBrainScope,
        limit: int = 10,
    ) -> GBrainThinkResult: ...

    def ingest_candidate_bundle(
        self,
        bundle: GBrainCandidateBundle,
    ) -> dict[str, Any]: ...

    def project_mind_map(
        self,
        *,
        scope: GBrainScope,
        center_query: str,
    ) -> GBrainMindMapDocument: ...


class MemoryWeaverGBrainEngineV08:
    """Deterministic GBrain v0.8 engine backed by `MemoryWorkspace.graph`.

    It is deliberately authority-limited:

    - candidate bundles are stored as candidate graph nodes / edges
    - `search` returns refs with graph/evidence citations
    - `think` synthesizes an answer but marks missing evidence as gaps
    - no method promotes MemoryItem, Pattern, or EvidenceLink state
    """

    def __init__(self, workspace: MemoryWorkspace):
        self.workspace = workspace

    def search(
        self,
        query: str,
        *,
        scope: GBrainScope,
        limit: int = 10,
    ) -> GBrainSearchResult:
        hits: list[GBrainSearchHit] = []
        for memory in self.workspace.memories.list_all():
            if memory.scope != scope.owner_scope:
                continue
            score = max(
                token_jaccard(query, memory.content),
                token_jaccard(query, " ".join(memory.tags)),
            )
            if score <= 0:
                continue
            layer: GraphLayer = "verified" if memory.layer == Layer.ACTIVATED else "candidate"
            hits.append(
                GBrainSearchHit(
                    ref_id=memory.id,
                    ref_type="memory",
                    title=memory.content[:80],
                    score=round(score, 4),
                    graph_layer=layer,
                    evidence=[
                        GBrainCitation(
                            ref_id=link.evidence_id,
                            ref_type="evidence",
                            layer="evidence",
                            authority=memory.source.value,
                        )
                        for link in self.workspace.evidence.links_for_memory(memory.id)
                    ],
                    metadata={
                        "scope": memory.scope,
                        "source": memory.source.value,
                        "freshness": memory.freshness.value,
                    },
                )
            )

        for pattern in self.workspace.patterns.list_all():
            if pattern.scope != scope.owner_scope:
                continue
            score = max(
                token_jaccard(query, pattern.rule),
                token_jaccard(query, " ".join(pattern.applies_when + pattern.success_path)),
            )
            if score <= 0:
                continue
            hits.append(
                GBrainSearchHit(
                    ref_id=pattern.id,
                    ref_type="pattern",
                    title=pattern.rule[:80],
                    score=round(score + pattern.path_fitness_score, 4),
                    graph_layer="runtime" if pattern.status == PatternStatus.STABLE else "candidate",
                    evidence=[
                        GBrainCitation(ref_id=link_id, ref_type="evidence_link", layer="evidence")
                        for link_id in pattern.evidence_links
                    ],
                    metadata={
                        "status": pattern.status.value,
                        "path_fitness_score": pattern.path_fitness_score,
                    },
                )
            )

        for node in self.workspace.graph.list_nodes():
            score = token_jaccard(query, f"{node.label} {node.ref_id}")
            if score <= 0:
                continue
            graph_layer: GraphLayer = "candidate"
            if node.metadata.get("graph_layer") in {"candidate", "verified", "runtime"}:
                graph_layer = node.metadata["graph_layer"]
            hits.append(
                GBrainSearchHit(
                    ref_id=node.ref_id or node.id,
                    ref_type=node.node_type.value,
                    title=node.label or node.id,
                    score=round(score * 0.8, 4),
                    graph_layer=graph_layer,
                    evidence=[
                        GBrainCitation(
                            ref_id=str(ref),
                            ref_type="source_ref",
                            layer=str(node.metadata.get("source_layer", "")),
                        )
                        for ref in node.metadata.get("source_refs", [])
                    ],
                    metadata=dict(node.metadata),
                )
            )

        hits.sort(key=lambda hit: (hit.score, hit.graph_layer, hit.ref_id), reverse=True)
        return GBrainSearchResult(
            query=query,
            scope=scope,
            hits=hits[:limit],
            graph_signals=[
                "candidate_graph_available" if self.workspace.graph.list_nodes() else "empty_graph",
                "scope_checked",
            ],
            retrieval_notes=[
                "search returns raw refs and citations only; synthesis is separate"
            ],
        )

    def think(
        self,
        query: str,
        *,
        scope: GBrainScope,
        limit: int = 10,
    ) -> GBrainThinkResult:
        search = self.search(query, scope=scope, limit=limit)
        citations: list[GBrainCitation] = []
        for hit in search.hits:
            citations.append(GBrainCitation(ref_id=hit.ref_id, ref_type=hit.ref_type, layer=hit.graph_layer))
            citations.extend(hit.evidence)
        answer = (
            "Evidence-backed candidate: "
            + (search.hits[0].title if search.hits else "no supported candidate")
        )
        gaps: list[GBrainGap] = []
        if not search.hits:
            gaps.append(GBrainGap(kind="recall", detail="No graph or memory hit found for query."))
        if not any(hit.evidence for hit in search.hits):
            gaps.append(GBrainGap(kind="citation", detail="Top hits need stronger evidence citations."))
        return GBrainThinkResult(
            query=query,
            scope=scope,
            answer=answer,
            citations=citations,
            gaps=gaps,
            contradiction_warnings=[
                hit.ref_id for hit in search.hits
                if str(hit.metadata.get("status", "")) == PatternStatus.CHALLENGED.value
            ],
            stale_warnings=[
                hit.ref_id for hit in search.hits
                if str(hit.metadata.get("freshness", "")) == "expired"
            ],
        )

    def ingest_candidate_bundle(
        self,
        bundle: GBrainCandidateBundle,
    ) -> dict[str, Any]:
        node_ids: list[str] = []
        edge_ids: list[str] = []
        for candidate in bundle.nodes:
            node_type = _node_type(candidate.node_type)
            node_id = _candidate_node_id(candidate.node_id)
            node_ids.append(
                self.workspace.graph.add_node(
                    GraphNode(
                        id=node_id,
                        node_type=node_type,
                        label=candidate.label,
                        ref_id=candidate.node_id,
                        metadata={
                            **candidate.metadata,
                            "graph_layer": "candidate",
                            "source_refs": list(candidate.source_refs),
                            "proposed_by": bundle.proposed_by,
                            "authority_granted": False,
                            "scope": bundle.scope.to_dict(),
                        },
                    )
                )
            )
        for candidate in bundle.edges:
            source_id = _candidate_node_id(candidate.source_id)
            target_id = _candidate_node_id(candidate.target_id)
            if self.workspace.graph.get_node(source_id) is None:
                node_ids.append(self.workspace.graph.add_node(
                    GraphNode(id=source_id, node_type=GraphNodeType.TAG, label=candidate.source_id, ref_id=candidate.source_id)
                ))
            if self.workspace.graph.get_node(target_id) is None:
                node_ids.append(self.workspace.graph.add_node(
                    GraphNode(id=target_id, node_type=GraphNodeType.TAG, label=candidate.target_id, ref_id=candidate.target_id)
                ))
            edge_ids.append(
                self.workspace.graph.add_edge(
                    GraphEdge(
                        id=f"edge_{source_id}_{_relation(candidate.relation).value}_{target_id}",
                        source_id=source_id,
                        target_id=target_id,
                        relation=_relation(candidate.relation),
                        confidence=candidate.confidence,
                        source="gbrain_v08_candidate_bundle",
                        status=GraphStatus.CANDIDATE,
                        evidence_links=list(candidate.source_refs),
                        metadata={
                            **candidate.metadata,
                            "graph_layer": "candidate",
                            "source_refs": list(candidate.source_refs),
                            "proposed_by": bundle.proposed_by,
                            "authority_granted": False,
                            "scope": bundle.scope.to_dict(),
                        },
                    ),
                    replace=True,
                )
            )
        return {
            "accepted_for_storage": True,
            "authority_granted": False,
            "candidate_node_count": len(set(node_ids)),
            "candidate_edge_count": len(edge_ids),
            "summary_count": len(bundle.summaries),
            "branch_note_count": len(bundle.branch_notes),
        }

    def project_mind_map(
        self,
        *,
        scope: GBrainScope,
        center_query: str,
    ) -> GBrainMindMapDocument:
        document = GBrainMindMapDocument(scope=scope, center_query=center_query)
        for node in self.workspace.graph.list_nodes():
            item = {
                "id": node.id,
                "label": node.label,
                "ref_id": node.ref_id,
                "node_type": node.node_type.value,
                "metadata": dict(node.metadata),
            }
            layer = node.metadata.get("graph_layer", "candidate")
            if layer == "runtime":
                document.runtime_nodes.append(item)
            elif layer == "verified":
                document.verified_nodes.append(item)
            else:
                document.candidate_nodes.append(item)
        for edge in self.workspace.graph.list_edges():
            item = {
                "id": edge.id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "relation": edge.relation.value,
                "status": edge.status.value,
                "confidence": edge.confidence,
                "metadata": dict(edge.metadata),
            }
            layer = edge.metadata.get("graph_layer", "candidate")
            if layer == "runtime":
                document.runtime_edges.append(item)
            elif layer == "verified":
                document.verified_edges.append(item)
            else:
                document.candidate_edges.append(item)
        return document


def _candidate_node_id(node_id: str) -> str:
    return f"v08_{tag_node_id(node_id)}"


def _node_type(value: str) -> GraphNodeType:
    normalized = value.lower()
    if normalized in {item.value for item in GraphNodeType}:
        return GraphNodeType(normalized)
    return GraphNodeType.TAG


def _relation(value: str) -> GraphRelation:
    normalized = value.lower()
    if normalized in {item.value for item in GraphRelation}:
        return GraphRelation(normalized)
    return GraphRelation.RELATED_TO
