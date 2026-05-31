"""Sprint 0 Demo — Full memory lifecycle without LLM or vector DB.

This script demonstrates the core MemoryWeaver loop:
  1. Feed a user correction → stored as negative memory (Layer 1)
  2. Feed a success confirmation → stored as positive memory (Layer 1)
  3. Score & promote memories → Layer 2
  4. Compose a diagnostic pattern → Layer 3
  5. Query the store and get a mode routing recommendation
"""

from memoryweaver.schema import MemoryItem, Polarity, Layer, MemoryType, Status
from memoryweaver.store import MemoryStore
from memoryweaver.scorer import MemoryScorer
from memoryweaver.extractor import FeedbackClassifier, EventDetector
from memoryweaver.router import ModeRouter


def main():
    print("=" * 60)
    print("  MemoryWeaver — Sprint 0: Basic Memory Loop")
    print("=" * 60)

    store = MemoryStore("demo_memory.json")
    scorer = MemoryScorer()
    classifier = FeedbackClassifier()
    detector = EventDetector(classifier)

    # ── Step 1: User correction → negative memory ──────────────────
    print("\n[Step 1] Detecting user correction...")
    correction_text = "不对，还是报错 — 重新安装 npm 没有解决问题"
    event = detector.detect(correction_text, source="user")

    if event:
        polarity, conf = classifier.classify(event.text)
        print(f"  Event: {event.type.value}")
        print(f"  Polarity: {polarity} (confidence={conf})")

        neg_memory = MemoryItem(
            polarity=Polarity.NEGATIVE,
            memory_type=MemoryType.FAILED_ATTEMPT,
            content="重新安装 npm 没有解决 Codex CLI 的 subscription load failed 问题",
            tags=["codex", "npm", "reinstall", "subscription", "failed"],
            source="user",
            evidence="用户纠正：'不对，还是报错'",
            scope="project",
        )
        store.add(neg_memory)
        print(f"  Stored as: {neg_memory.id} [Layer {neg_memory.layer.value}]")
        scorer.record_correction(neg_memory)

    # ── Step 2: Success confirmation → positive memory ─────────────
    print("\n[Step 2] Detecting success confirmation...")
    success_text = "可以了！检查了组织选择和订阅状态后就解决了"
    event = detector.detect(success_text, source="user")

    if event:
        polarity, conf = classifier.classify(event.text)
        print(f"  Event: {event.type.value}")
        print(f"  Polarity: {polarity} (confidence={conf})")

        pos_memory = MemoryItem(
            polarity=Polarity.POSITIVE,
            memory_type=MemoryType.SUCCESS_PATH,
            content="检查组织选择和订阅状态后 Codex CLI subscription 问题解决",
            tags=["codex", "auth", "organization", "subscription", "fix"],
            source="user",
            evidence="用户确认：'可以了！'",
            scope="project",
        )
        store.add(pos_memory)
        print(f"  Stored as: {pos_memory.id} [Layer {pos_memory.layer.value}]")
        scorer.record_success(pos_memory)

    # ── Step 3: Neutral context ────────────────────────────────────
    print("\n[Step 3] Storing neutral context...")
    neutral_memory = MemoryItem(
        polarity=Polarity.NEUTRAL,
        memory_type=MemoryType.FACT,
        content="用户使用 WSL 环境, Codex CLI 通过 npm 全局安装成功, codex --version 正常返回",
        tags=["wsl", "codex", "npm", "install", "env"],
        source="terminal",
        evidence="codex --version 返回正常",
        scope="project",
    )
    store.add(neutral_memory)
    print(f"  Stored as: {neutral_memory.id} [Layer {neutral_memory.layer.value}]")

    # ── Step 4: Ambiguous hypothesis ───────────────────────────────
    print("\n[Step 4] Storing ambiguous hypothesis...")
    amb_memory = MemoryItem(
        polarity=Polarity.AMBIGUOUS,
        memory_type=MemoryType.HYPOTHESIS,
        content="subscription load failed 可能与组织选择或订阅权限有关，而非安装问题",
        tags=["codex", "subscription", "organization", "hypothesis"],
        source="assistant",
        evidence="基于用户反馈推测",
        scope="project",
    )
    store.add(amb_memory)
    print(f"  Stored as: {amb_memory.id} [Layer {amb_memory.layer.value}]")

    # ── Step 5: Access memories repeatedly to build heat ───────────
    print("\n[Step 5] Simulating repeated access to build heat...")
    for _ in range(4):
        scorer.record_access(pos_memory)
        scorer.record_access(neg_memory)
        scorer.record_access(neutral_memory)
    print(f"  pos_memory heat: {pos_memory.heat}")
    print(f"  neg_memory heat: {neg_memory.heat}")
    print(f"  neutral_memory heat: {neutral_memory.heat}")

    # ── Step 6: Evaluate and promote ───────────────────────────────
    print("\n[Step 6] Evaluating memories for promotion...")
    all_items = store.list_all()
    for item in all_items:
        old_layer = item.layer.value
        scorer.evaluate(item)
        if item.layer.value != old_layer:
            print(f"  {item.id}: Layer {old_layer} → {item.layer.value} "
                  f"[{item.status.value}] (confidence={item.confidence})")
        else:
            print(f"  {item.id}: Layer {item.layer.value} "
                  f"[{item.status.value}] (confidence={item.confidence})")
        store.update(item)

    # ── Step 7: Compose a Layer-3 pattern ──────────────────────────
    print("\n[Step 7] Composing Layer-3 diagnostic pattern...")
    from memoryweaver.schema import Pattern

    pattern = Pattern(
        pattern_type="diagnostic_rule",
        composed_from=[neg_memory.id, pos_memory.id, neutral_memory.id, amb_memory.id],
        rule=(
            "If Codex CLI is installed successfully in WSL "
            "but subscription loading still fails, "
            "do not prioritize npm reinstall. "
            "Check authentication, selected organization, or subscription state first."
        ),
        applies_when=["codex", "subscription", "wsl", "install success"],
        avoid_when=["reinstall", "npm reinstall", "reinstall-first"],
        confidence=0.82,
        model_fit=["coding-agent"],
        promotion_reason="Repeatedly helped diagnose similar Codex subscription issues",
    )
    print(f"  Pattern: {pattern.id}")
    print(f"  Rule: {pattern.rule}")
    print(f"  Confidence: {pattern.confidence}")

    # Store the pattern as a Layer-3 MemoryItem as well
    pattern_memory = MemoryItem(
        layer=Layer.PATTERN,
        polarity=Polarity.NEUTRAL,
        memory_type=MemoryType.PATTERN,
        content=pattern.rule,
        tags=["codex", "subscription", "wsl", "diagnostic", "pattern"],
        linked_tags=["codex", "npm", "auth", "organization"],
        source="composer",
        evidence=f"Composed from: {', '.join(pattern.composed_from)}",
        confidence=pattern.confidence,
        model_fit=pattern.model_fit,
        status=Status.PROMOTED,
    )
    store.add(pattern_memory)
    print(f"  Stored as Layer-3 MemoryItem: {pattern_memory.id}")

    # ── Step 8: Query the store ────────────────────────────────────
    print("\n[Step 8] Querying store...")
    codex_memories = store.find_by_tags(["codex", "subscription"])
    print(f"  Found {len(codex_memories)} memories tagged 'codex'+'subscription':")
    for m in codex_memories:
        print(f"    [{m.polarity.value}] L{m.layer.value} {m.content[:60]}...")

    # ── Step 9: Mode routing ───────────────────────────────────────
    print("\n[Step 9] Mode routing for a new query...")
    router = ModeRouter(store)
    decision = router.route("Codex CLI subscription load failed in WSL after npm install")
    print(f"  Query: 'Codex CLI subscription load failed in WSL after npm install'")
    print(f"  Recommendation: {decision.mode.value}")
    print(f"  Reason: {decision.reason}")
    print(f"  Confidence: {decision.confidence}")

    # ── Step 10: Summary ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Demo Complete")
    print("=" * 60)
    print(f"  Total memories: {store.count()}")
    layer_counts = {1: 0, 2: 0, 3: 0}
    for m in store.list_all():
        layer_counts[m.layer.value] += 1
    print(f"  Layer 1 (candidate):  {layer_counts[1]}")
    print(f"  Layer 2 (activated):  {layer_counts[2]}")
    print(f"  Layer 3 (pattern):    {layer_counts[3]}")
    print(f"\n  Memory file: {store._path.resolve()}")


if __name__ == "__main__":
    main()
