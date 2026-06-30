import pytest

from memoryweaver.option_harness import (
    OptionGuidedPredictiveHarness,
    OptionCandidate,
    OptionRisk,
    OptionStatus,
    PredictionCandidate,
    PredictionStatus,
    UserSelection,
    common_prefix_unit,
    normalize_option_set,
    prediction_cache_hit,
    retain_prediction_if_matched,
)


def test_option_candidate_is_not_promotable_by_default():
    option = OptionCandidate(
        option_id="A",
        intent_guess="run focused tests",
        action_plan=("inspect failing test", "run pytest"),
    )

    assert option.risk == OptionRisk.LOW
    assert option.promotion_allowed is False


def test_high_risk_option_requires_confirmation_after_normalization():
    option = OptionCandidate(
        option_id="dangerous-cleanup",
        intent_guess="clean generated files",
        action_plan=("delete temporary files",),
        risk=OptionRisk.HIGH,
    )

    (normalized,) = normalize_option_set([option])

    assert normalized.confirmation_required is True
    assert normalized.promotion_allowed is False


def test_normalization_rejects_duplicate_option_ids():
    option = OptionCandidate(
        option_id="A",
        intent_guess="run focused tests",
        action_plan=("run pytest",),
    )

    with pytest.raises(ValueError, match="duplicate option_id"):
        normalize_option_set([option, option])


def test_matched_prediction_is_only_route_hint():
    prediction = PredictionCandidate(
        prediction_id="p-run-tests",
        predicted_intent="run tests",
        predicted_next_request="run pytest",
        confidence=0.7,
    )

    retained = retain_prediction_if_matched(prediction, "please run pytest now")

    assert retained is not None
    assert retained.matched is True
    assert retained.status == PredictionStatus.MATCHED
    assert retained.retained_as == "route_hint"
    assert retained.verified_memory_allowed is False


def test_unmatched_prediction_is_discarded():
    prediction = PredictionCandidate(
        prediction_id="p-docs",
        predicted_intent="edit docs",
        predicted_next_request="update readme",
        confidence=0.7,
    )

    retained = retain_prediction_if_matched(prediction, "run pytest now")

    assert retained is None


def test_deepseek_style_prefix_hit_retains_prediction_only_as_route_hint():
    prediction = PredictionCandidate(
        prediction_id="p-prefix",
        predicted_intent="run focused tests",
        predicted_next_request="pytest",
        confidence=0.8,
        cache_prefix="please run",
    )

    retained = retain_prediction_if_matched(prediction, "Please run focused pytest now")

    assert prediction_cache_hit(prediction, "Please run focused pytest now") is True
    assert retained is not None
    assert retained.status == PredictionStatus.MATCHED
    assert retained.verified_memory_allowed is False


def test_common_prefix_unit_requires_minimum_length():
    assert common_prefix_unit("please run pytest", "please run tests") == "please run"
    assert common_prefix_unit("abc", "abd") == ""


def test_full_option_guided_harness_selects_option_without_memory_authority():
    harness = OptionGuidedPredictiveHarness(max_options=3)
    prediction = PredictionCandidate(
        prediction_id="p-inspect",
        predicted_intent="inspect first",
        predicted_next_request="inspect",
        confidence=0.6,
        cache_prefix="please inspect",
    )
    option_set = harness.build_option_set(
        option_set_id="turn-1",
        user_query="please inspect and suggest options",
        predictions=[prediction],
    )

    decision = harness.select_option(
        option_set,
        UserSelection(option_set_id="turn-1", selected_option_id="inspect"),
        thread_id="thread",
        step=1,
    )

    assert len(option_set.options) == 3
    assert option_set.predictions[0].status == PredictionStatus.MATCHED
    assert decision.status == "action_proposal_ready"
    assert decision.selected_option is not None
    assert decision.selected_option.status == OptionStatus.SELECTED
    assert decision.memory_authority_granted is False
    assert decision.layer3_authority_granted is False
    assert decision.action_proposal_payload is not None
    assert decision.action_proposal_payload["metadata"]["promotion_allowed"] is False


def test_high_risk_selection_requires_user_confirmation():
    harness = OptionGuidedPredictiveHarness()
    option_set = harness.build_option_set(
        option_set_id="turn-2",
        user_query="delete cache",
        options=[
            OptionCandidate(
                option_id="delete",
                intent_guess="delete cache",
                action_plan=("delete files",),
                risk=OptionRisk.HIGH,
                action_name="tool_call",
                target="delete_cache",
            )
        ],
    )

    decision = harness.select_option(
        option_set,
        UserSelection(option_set_id="turn-2", selected_option_id="delete", confirmed=False),
    )

    assert option_set.options[0].confirmation_required is True
    assert decision.status == "needs_confirmation"
    assert decision.action_proposal_payload is None
