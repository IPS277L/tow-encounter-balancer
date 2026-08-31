from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.fate_models import (
    FATE_NEAR_MISS_RULE_ID,
    FateNearMissBurnRequest,
    FateSessionState,
)
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import (
    CharacterInjuryState,
    WoundDiceModifier,
)
from towr.domain.resolution_models import ConsumeWoundNegationRequest
from towr.domain.retreat_models import (
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.domain.run_for_your_lives_trapped_models import (
    RunForYourLivesTrappedCostRequest,
    TrappedEscapeCostDecision,
    TrappedEscapeCostKind,
)
from towr.domain.run_for_your_lives_trapped_wound_models import (
    RunForYourLivesTrappedWoundRequest,
    TrappedWoundCostTarget,
)
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionRequest,
    CharacterWoundLifecycleOutcome,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_trapped_resolution import (
    resolve_run_for_your_lives_trapped_cost,
)
from towr.rules.run_for_your_lives_trapped_wound_resolution import (
    advance_run_for_your_lives_trapped_wound_application,
    begin_run_for_your_lives_trapped_wound_application,
)
from towr.rules.wound_lifecycle_resolution import (
    complete_character_wound_lifecycle,
)


def trapped_cost(
    kind: TrappedEscapeCostKind = TrappedEscapeCostKind.WOUNDS,
    *,
    affected_actor_ids: tuple[str, ...] = ("hero", "ally"),
):
    consequence_references = tuple(
        f"cost:escape:{actor_id}" for actor_id in affected_actor_ids
    )
    source = RunForYourLivesCampaignConsequenceRequest(
        id="campaign-follow-up:trapped:1",
        source_request_id="run-for-your-lives:1",
        battle_id="battle:1",
        retreat_id="retreat:battle:1:round:3",
        player_character_ids=("hero", "ally", "scout"),
        cover_kind=RetreatCoverKind.FATE_REARGUARD,
        cover_proof_id="proof:fate-rearguard:1",
        rearguard_actor_id="hero",
        failed_actor_ids=("hero", "ally", "scout"),
        complication_ids=(),
        table_total=25,
        outcome=RunForYourLivesOutcome.TRAPPED,
    )
    registered = register_run_for_your_lives_campaign_consequence(
        RunForYourLivesCampaignApplicationRequest(
            id="application:trapped:1",
            source_consequence=source,
            campaign_state=CampaignConsequenceState("campaign:1"),
            consequence_id="consequence:trapped:1",
            specification=RunForYourLivesConsequenceSpecification(
                id="specification:trapped:1",
                outcome=RunForYourLivesOutcome.TRAPPED,
                description_reference_id="gm-description:trapped:1",
                affected_subject_reference_ids=tuple(
                    f"actor:{actor_id}" for actor_id in affected_actor_ids
                ),
                concrete_consequence_reference_ids=consequence_references,
            ),
        )
    )
    return resolve_run_for_your_lives_trapped_cost(
        RunForYourLivesTrappedCostRequest(
            id="trapped-cost:1",
            source_campaign=registered,
        ),
        TrappedEscapeCostDecision(
            id=f"decision:trapped:{kind.value}",
            cost_kind=kind,
            affected_actor_ids=affected_actor_ids,
            consequence_reference_ids=consequence_references,
        ),
    )


def wound_target(
    actor_id: str,
    wound_count: int = 1,
    *,
    state: CharacterInjuryState = CharacterInjuryState(),
    modifiers: tuple[WoundDiceModifier, ...] = (),
) -> TrappedWoundCostTarget:
    return TrappedWoundCostTarget(
        actor_id=actor_id,
        wound_count=wound_count,
        state=state,
        daily_wounds=DailyWoundState("day:1", actor_id),
        wound_dice_modifiers=modifiers,
    )


def wound_request(
    *targets: TrappedWoundCostTarget,
    source_cost=None,
    consumed_application_ids: tuple[str, ...] = (),
) -> RunForYourLivesTrappedWoundRequest:
    source = source_cost or trapped_cost(
        affected_actor_ids=tuple(item.actor_id for item in targets)
    )
    return RunForYourLivesTrappedWoundRequest(
        id="trapped-wounds:1",
        source_cost=source,
        targets=targets,
        consumed_application_ids=consumed_application_ids,
    )


def completion(
    result,
    *,
    near_miss: FateNearMissBurnRequest | None = None,
    daily_wounds: DailyWoundState | None = None,
    consumed_roll_ids: tuple[str, ...] | None = None,
):
    pending = result.pending_wound
    assert pending is not None
    progress = next(
        item for item in result.target_progress if item.actor_id == result.active_target_id
    )
    accepted = pending.wound_result.wound_accepted
    request = CharacterWoundLifecycleCompletionRequest(
        id=f"{pending.request_id}:completion",
        roll=pending,
        current_state=progress.state,
        daily_wounds=daily_wounds or progress.daily_wounds,
        daily_registration_id=(
            f"{pending.request_id}:daily"
            if accepted and near_miss is None
            else None
        ),
        near_miss=near_miss,
        consumed_roll_ids=(
            progress.consumed_roll_ids
            if consumed_roll_ids is None
            else consumed_roll_ids
        ),
        consumed_near_miss_effect_ids=(
            progress.consumed_near_miss_effect_ids
        ),
    )
    return complete_character_wound_lifecycle(request)


def near_miss_for(result) -> FateNearMissBurnRequest:
    pending = result.pending_wound
    assert pending is not None
    actor_id = pending.source_request.target_id
    return FateNearMissBurnRequest(
        id=f"burn:trapped:{pending.request_id}",
        state=FateSessionState("session:1", actor_id, 1, 0),
        wound_negation=ConsumeWoundNegationRequest(
            resolution_id=pending.source_request.wound.id,
            rule_id=FATE_NEAR_MISS_RULE_ID,
        ),
    )


class K1RunForYourLivesTrappedWoundResolutionTests(unittest.TestCase):
    def test_begin_rolls_first_target_and_consumes_application_once(self) -> None:
        request = wound_request(
            wound_target("hero", 2),
            wound_target("ally"),
        )

        result = begin_run_for_your_lives_trapped_wound_application(
            request,
            SequenceRandom([4]),
        )

        self.assertEqual(result.active_target_id, "hero")
        self.assertFalse(result.completed)
        self.assertEqual(
            result.pending_wound.source_request.wound.id,
            "trapped-wounds:1:hero:wound:1",
        )
        self.assertEqual(
            result.consumed_application_ids,
            (request.source_cost.application_request.id,),
        )
        self.assertEqual(
            tuple(item.assigned_wound_count for item in result.target_progress),
            (2, 1),
        )

    def test_next_wound_uses_completed_state_and_accumulated_daily_state(self) -> None:
        first = begin_run_for_your_lives_trapped_wound_application(
            wound_request(wound_target("hero", 2)),
            SequenceRandom([4]),
        )
        first_completion = completion(first)

        second = advance_run_for_your_lives_trapped_wound_application(
            first,
            first_completion,
            SequenceRandom([2, 3]),
        )

        pending = second.pending_wound
        assert pending is not None
        progress = second.target_progress[0]
        self.assertEqual(pending.source_request.wound.state, first_completion.state)
        self.assertEqual(pending.wound_result.table_roll.dice, 2)
        self.assertEqual(pending.wound_result.table_roll.values, (2, 3))
        self.assertEqual(progress.completed_wound_count, 1)
        self.assertEqual(progress.daily_wounds.wound_count, 1)

    def test_near_miss_closes_one_attempt_before_next_wound_roll(self) -> None:
        initial = CharacterInjuryState()
        first = begin_run_for_your_lives_trapped_wound_application(
            wound_request(wound_target("hero", 2, state=initial)),
            SequenceRandom([10]),
        )
        first_completion = completion(first, near_miss=near_miss_for(first))

        second = advance_run_for_your_lives_trapped_wound_application(
            first,
            first_completion,
            SequenceRandom([5]),
        )

        pending = second.pending_wound
        assert pending is not None
        self.assertIs(first_completion.outcome, CharacterWoundLifecycleOutcome.NEAR_MISS)
        self.assertEqual(pending.source_request.wound.state, initial)
        self.assertEqual(pending.wound_result.table_roll.dice, 1)
        self.assertEqual(second.target_progress[0].daily_wounds.wound_count, 0)

    def test_targets_are_processed_in_original_group_order(self) -> None:
        first = begin_run_for_your_lives_trapped_wound_application(
            wound_request(wound_target("hero"), wound_target("ally")),
            SequenceRandom([3]),
        )
        second = advance_run_for_your_lives_trapped_wound_application(
            first,
            completion(first),
            SequenceRandom([4]),
        )
        final = advance_run_for_your_lives_trapped_wound_application(
            second,
            completion(second),
            SequenceRandom([]),
        )

        self.assertEqual(second.active_target_id, "ally")
        self.assertTrue(final.completed)
        self.assertIsNone(final.active_target_id)
        self.assertEqual(
            tuple(item.completed_wound_count for item in final.target_progress),
            (1, 1),
        )

    def test_death_skips_remaining_wounds_for_target_and_advances_group(self) -> None:
        first = begin_run_for_your_lives_trapped_wound_application(
            wound_request(
                wound_target(
                    "hero",
                    3,
                    modifiers=(WoundDiceModifier("RULE-TEST:LETHAL", 2),),
                ),
                wound_target("ally"),
            ),
            SequenceRandom([10, 10, 10]),
        )
        lethal = completion(first)

        second = advance_run_for_your_lives_trapped_wound_application(
            first,
            lethal,
            SequenceRandom([2]),
        )

        hero = second.target_progress[0]
        self.assertTrue(hero.state.dead)
        self.assertEqual(hero.completed_wound_count, 1)
        self.assertEqual(hero.skipped_wound_count, 2)
        self.assertEqual(second.active_target_id, "ally")

    def test_requires_wound_branch_exact_targets_and_positive_counts(self) -> None:
        capture = trapped_cost(
            TrappedEscapeCostKind.CAPTURE,
            affected_actor_ids=("hero",),
        )
        with self.assertRaisesRegex(ValueError, "not Wounds"):
            wound_request(wound_target("hero"), source_cost=capture)
        with self.assertRaisesRegex(ValueError, "group order"):
            wound_request(
                wound_target("ally"),
                wound_target("hero"),
                source_cost=trapped_cost(),
            )
        with self.assertRaisesRegex(ValueError, "positive integer"):
            wound_target("hero", 0)
        with self.assertRaisesRegex(ValueError, "initially living"):
            wound_target("hero", state=CharacterInjuryState(dead=True))

        source = wound_request(wound_target("hero"))
        application_id = source.source_cost.application_request.id
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(source, consumed_application_ids=(application_id,))

    def test_rejects_foreign_completion_and_stale_daily_chain(self) -> None:
        first = begin_run_for_your_lives_trapped_wound_application(
            wound_request(wound_target("hero", 2)),
            SequenceRandom([4]),
        )
        other = begin_run_for_your_lives_trapped_wound_application(
            replace(first.source_request, id="trapped-wounds:other"),
            SequenceRandom([5]),
        )
        with self.assertRaisesRegex(ValueError, "another Trapped"):
            advance_run_for_your_lives_trapped_wound_application(
                first,
                completion(other),
                SequenceRandom([]),
            )

        second = advance_run_for_your_lives_trapped_wound_application(
            first,
            completion(first),
            SequenceRandom([2, 2]),
        )
        stale = completion(
            second,
            daily_wounds=DailyWoundState("day:1", "hero"),
        )
        with self.assertRaisesRegex(ValueError, "stale daily state"):
            advance_run_for_your_lives_trapped_wound_application(
                second,
                stale,
                SequenceRandom([]),
            )

    def test_completed_and_forged_results_are_closed(self) -> None:
        pending = begin_run_for_your_lives_trapped_wound_application(
            wound_request(wound_target("hero")),
            SequenceRandom([4]),
        )
        with self.assertRaisesRegex(ValueError, "require the next pending"):
            replace(pending, pending_wound=None)
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(pending, applied_rule_ids=())

        final = advance_run_for_your_lives_trapped_wound_application(
            pending,
            completion(pending),
            SequenceRandom([]),
        )
        self.assertTrue(final.completed)
        with self.assertRaisesRegex(ValueError, "already complete"):
            advance_run_for_your_lives_trapped_wound_application(
                final,
                completion(pending),
                SequenceRandom([]),
            )


if __name__ == "__main__":
    unittest.main()
