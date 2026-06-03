"""SDK v0.2.0 demo: explicit Layer 2 promotion and provisional Pattern.

This example keeps the Sprint 0 loop small and deterministic:
  1. Store two Layer-1 memory candidates.
  2. Promote them to Layer 2 through MemoryPolicy.
  3. Store a small EvidenceNode and EvidenceLink.
  4. Compose a canonical provisional Layer-3 Pattern.
  5. Route a similar query with Memory + Pattern context.
"""

from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoryweaver.composer import PatternComposer
from memoryweaver.evidence import EvidenceLink, EvidenceNode
from memoryweaver.extractor import EventDetector, FeedbackClassifier
from memoryweaver.router import ModeRouter
from memoryweaver.schema import MemoryItem, MemoryType, Polarity
from memoryweaver.scorer import MemoryScorer
from memoryweaver.store import MemoryWorkspace


def main() -> None:
    print("=" * 60)
    print("  MemoryWeaver SDK v0.2.0: Basic Memory Loop")
    print("=" * 60)

    workspace_root = tempfile.TemporaryDirectory(prefix="memoryweaver-demo-")
    workspace = MemoryWorkspace(Path(workspace_root.name))
    scorer = MemoryScorer()
    classifier = FeedbackClassifier()
    detector = EventDetector(classifier)

    correction_text = "不对，还是报错 — 重新安装 npm 没有解决问题"
    success_text = "可以了！检查了组织选择和订阅状态后就解决了"

    print("\n[Step 1] Detect and store memory candidates")
    for text, polarity, memory_type, content, tags in [
        (
            correction_text,
            Polarity.NEGATIVE,
            MemoryType.FAILED_ATTEMPT,
            "重新安装 npm 没有解决 Codex CLI subscription load failed 问题",
            ["codex", "npm", "subscription", "failed"],
        ),
        (
            success_text,
            Polarity.POSITIVE,
            MemoryType.SUCCESS_PATH,
            "检查组织选择和订阅状态后 Codex CLI subscription 问题解决",
            ["codex", "auth", "organization", "subscription", "fix"],
        ),
    ]:
        event = detector.detect(text, source="user")
        label, confidence = classifier.classify(event.text if event else text)
        item = MemoryItem(
            polarity=polarity,
            memory_type=memory_type,
            content=content,
            tags=tags,
            source="user",
            evidence=text,
            scope="project",
            confidence=confidence,
        )
        workspace.memories.add(item)
        print(f"  {item.id}: {label}, Layer {item.layer.value}")
        if polarity == Polarity.POSITIVE:
            scorer.record_success(item)
        else:
            scorer.record_correction(item)
        workspace.memories.update(item)

    print("\n[Step 2] Explicit Layer 2 promotion through MemoryPolicy")
    promoted = []
    for item in workspace.memories.list_all():
        if workspace.memory_policy.can_promote_to_layer2(item, []):
            workspace.memory_policy.promote_to_layer2(item, [])
            workspace.memories.update(item)
            promoted.append(item)
            print(f"  {item.id}: promoted to Layer {item.layer.value}")

    print("\n[Step 3] Add small evidence and link it to memory")
    node = EvidenceNode(
        text="User confirmed organization and subscription check resolved the issue.",
        source="user",
        source_uri="conversation://demo",
        language="en",
    )
    workspace.evidence.add_node(node)
    link = EvidenceLink(evidence_id=node.id, memory_id=promoted[0].id)
    workspace.evidence.add_link(link)
    print(f"  EvidenceNode: {node.id}")
    print(f"  EvidenceLink: {link.id} -> {promoted[0].id}")

    print("\n[Step 4] Compose provisional Layer-3 Pattern")
    composer = PatternComposer(
        workspace.memories,
        workspace.patterns,
        workspace.evidence,
        workspace.memory_policy,
    )
    pattern = composer.compose(
        supporting_memory_ids=[item.id for item in promoted[:2]],
        rule=(
            "If Codex CLI is installed but subscription loading fails, "
            "check selected organization and subscription state before reinstalling npm."
        ),
        applies_when=["Codex CLI installed", "subscription load failed", "WSL"],
        avoid_when=["reinstall npm first"],
        success_path=["check organization", "check subscription state"],
        failed_path=["npm reinstall"],
        evidence_link_ids=[link.id],
        scope="project",
    )
    print(f"  Pattern: {pattern.id} [{pattern.status.value}]")

    print("\n[Step 5] Route a similar query")
    route_query = (
        "Codex CLI is installed but subscription loading fails; "
        "check selected organization and subscription state before reinstalling npm."
    )
    decision = ModeRouter(
        workspace.memories,
        pattern_store=workspace.patterns,
    ).route(route_query)
    print(f"  Recommendation: {decision.mode.value}")
    print(f"  Reason: {decision.reason}")

    print("\n[Step 6] Validate workspace")
    report = workspace.validate()
    print(f"  Valid: {report['valid']}")
    print(f"  Workspace: {workspace.root.resolve()}")
    workspace_root.cleanup()


if __name__ == "__main__":
    main()
