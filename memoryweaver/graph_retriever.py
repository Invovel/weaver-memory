"""Graph-assisted candidate expansion for verified retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field

from memoryweaver.graph_linker import tag_node_id
from memoryweaver.graph_schema import GraphNodeType, GraphRelation, GraphStatus
from memoryweaver.graph_store import GraphStore
from memoryweaver.retriever import VerifiedRetriever
from memoryweaver.schema import MemoryItem


@dataclass
class GraphCandidateResult:
    seed_tags: list[str]
    expanded_tags: list[str]
    candidate_memory_ids: list[str]
    results: list[MemoryItem]
    candidate_reduction_ratio: float
    expanded_node_ids: list[str] = field(default_factory=list)


class GraphRetriever:
    """Use graph tag-linking to reduce the candidate set before verification."""

    def __init__(
        self,
        graph: GraphStore,
        retriever: VerifiedRetriever,
        total_memory_count: int,
    ):
        self._graph = graph
        self._retriever = retriever
        self._total_memory_count = total_memory_count

    def expand_tags(
        self,
        tags: list[str],
        *,
        hops: int = 1,
        relations: set[GraphRelation] | None = None,
    ) -> list[str]:
        nodes = self.expand_tag_nodes(tags, hops=hops, relations=relations)
        return sorted({node.ref_id or node.label for node in nodes})

    def expand_tag_nodes(
        self,
        tags: list[str],
        *,
        hops: int = 1,
        relations: set[GraphRelation] | None = None,
    ):
        allowed = relations or {
            GraphRelation.RELATED_TO,
            GraphRelation.ALIAS_OF,
            GraphRelation.SAME_TOPIC_AS,
            GraphRelation.SAME_ISSUE_AS,
            GraphRelation.CAUSED_BY,
            GraphRelation.LIMITS,
            GraphRelation.SUPERSEDES,
            GraphRelation.RESOLVES,
        }
        visited: set[str] = set()
        frontier = [tag_node_id(tag) for tag in tags]
        for node_id in frontier:
            if self._graph.get_node(node_id):
                visited.add(node_id)
        for _ in range(hops):
            next_frontier: list[str] = []
            for node_id in frontier:
                for edge, neighbor in self._graph.neighbors(node_id):
                    if edge.status in (GraphStatus.REJECTED, GraphStatus.STALE):
                        continue
                    if edge.relation not in allowed:
                        continue
                    if neighbor.node_type != GraphNodeType.TAG:
                        continue
                    if neighbor.id not in visited:
                        visited.add(neighbor.id)
                        next_frontier.append(neighbor.id)
            frontier = next_frontier
        nodes = [
            self._graph.get_node(node_id)
            for node_id in visited
            if self._graph.get_node(node_id) is not None
        ]
        return [node for node in nodes if node.node_type == GraphNodeType.TAG]

    def candidate_memory_ids_for_tags(self, tags: list[str]) -> list[str]:
        tag_ids = {tag_node_id(tag) for tag in tags}
        memory_ids: set[str] = set()
        for tag_id in tag_ids:
            for edge, neighbor in self._graph.neighbors(tag_id):
                if edge.status in (GraphStatus.REJECTED, GraphStatus.STALE):
                    continue
                if neighbor.node_type == GraphNodeType.MEMORY and neighbor.ref_id:
                    memory_ids.add(neighbor.ref_id)
        return sorted(memory_ids)

    def search_with_graph_candidates(
        self,
        query: str,
        seed_tags: list[str],
        *,
        limit: int = 10,
        threshold: float = 0.0,
        scope: str = "project",
    ) -> GraphCandidateResult:
        expanded_tags = self.expand_tags(seed_tags)
        candidate_ids = self.candidate_memory_ids_for_tags(expanded_tags)
        results = self._retriever.search(
            query,
            limit=limit,
            threshold=threshold,
            scope=scope,
            graph_candidates=candidate_ids,
        )
        if self._total_memory_count:
            reduction = 1 - (len(candidate_ids) / self._total_memory_count)
        else:
            reduction = 0.0
        return GraphCandidateResult(
            seed_tags=seed_tags,
            expanded_tags=expanded_tags,
            candidate_memory_ids=candidate_ids,
            results=results,
            candidate_reduction_ratio=round(reduction, 4),
            expanded_node_ids=[tag_node_id(tag) for tag in expanded_tags],
        )
