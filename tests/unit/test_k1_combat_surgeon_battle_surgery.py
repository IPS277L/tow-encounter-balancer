from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.combat_surgeon_models import COMBAT_SURGEON_RULE_ID
from towr.domain.combat_surgeon_surgery_models import (
    COMBAT_SURGEON_BATTLE_SURGERY_REQUIRED_SUCCESSES,
    COMBAT_SURGEON_BATTLE_SURGERY_RULE_ID,
    CombatSurgeonBattleSurgeryActionRequest,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.exacting_test_models import (
    EXACTING_TEST_RULE_ID,
    ExactingTestContributionRequest,
    ExactingTestProgress,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    WoundEffectDuration,
    WoundEntryId,
    WoundRecord,
    WoundRestriction,
    WoundRestrictionEffect,
)
from towr.domain.surgery_models import SURGERY_FAILURE_RISK_RULE_ID
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlotRequest,
    CombatRoundState,
    CombatSide,
    CombatTurnEndRequest,
    CombatTurnParticipant,
    CombatTurnStartRequest,
    ImproviseKind,
)
from towr.rules.combat_surgeon_surgery_resolution import (
    execute_combat_surgeon_battle_surgery_action,
)
from towr.rules.exacting_test_resolution import (
    resolve_exacting_test_contribution,
)
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def active_round(
    round_number: int = 1,
    *,
    kind: CombatActionKind = CombatActionKind.IMPROVISE,
    improvise_kind: ImproviseKind = ImproviseKind.ABILITY,
    approach_id: str = COMBAT_SURGEON_RULE_ID,
    produces_attack: bool = False,
) -> CombatRoundState:
    state = CombatRoundState(
        round_number=round_number,
        participants=(
            CombatTurnParticipant("surgeon", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("ally", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    state = start_combat_turn(
        CombatTurnStartRequest(f"turn:{round_number}", state, "surgeon")
    ).state
    declaration = CombatActionDeclaration(
        kind,
        improvise_kind=(
            improvise_kind if kind is CombatActionKind.IMPROVISE else None
        ),
        improvise_approach_id=(
            approach_id if kind is CombatActionKind.IMPROVISE else None
        ),
        improvise_produces_attack=produces_attack,
    )
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id=f"slot:{round_number}",
            state=state,
            actor_id="surgeon",
            declaration=declaration,
            grant=ActionSlotGrant.STANDARD,
        )
    ).state


def surgical_state(
    *,
    entry_id: WoundEntryId = WoundEntryId.SEVERED_ARM,
    total: int = 20,
) -> CharacterInjuryState:
    return CharacterInjuryState(
        wounds=(
            WoundRecord(
                1,
                entry_id,
                total,
                (10, total - 10),
                treated=True,
                effect_resolved=True,
            ),
        ),
        active_wound_effects=(
            WoundRestrictionEffect(
                1,
                WoundRestriction.ARM_LOST,
                WoundEffectDuration.PERMANENT,
            ),
        ),
    )


def surgery_request(
    action_number: int,
    state: CharacterInjuryState,
    *,
    round_state: CombatRoundState | None = None,
    progress=None,
    target_id: str = "surgeon",
    target_in_close_range: bool | None = None,
    **changes,
) -> CombatSurgeonBattleSurgeryActionRequest:
    values = {
        "id": f"battle:1:surgery:action:{action_number}",
        "surgery_id": "battle:1:surgery:hero:1",
        "battle_id": "battle:1",
        "round_state": (
            round_state
            if round_state is not None
            else active_round(action_number)
        ),
        "surgeon_id": "surgeon",
        "surgeon_conditions": ConditionState(),
        "surgeon_talent_rule_ids": (COMBAT_SURGEON_RULE_ID,),
        "slot_index": 1,
        "target_id": target_id,
        "target_in_close_range": target_in_close_range,
        "injury_state": state,
        "wound_sequence": 1,
        "dexterity_test": TestRequest(
            f"battle:1:surgery:dexterity:{action_number}",
            TestProfile(3, 5),
        ),
        "has_specialist_medical_tools": True,
        "has_recovery_supports": True,
        "progress": progress,
    }
    values.update(changes)
    return CombatSurgeonBattleSurgeryActionRequest(**values)


class K1ExactingTestResolutionTests(unittest.TestCase):
    def test_basic_contributions_accumulate_and_preserve_overshoot(self) -> None:
        progress = ExactingTestProgress("task:1", 4)
        first = resolve_exacting_test_contribution(
            ExactingTestContributionRequest(
                "task:1:attempt:1",
                progress,
                "hero",
                TestRequest("task:1:test:1", TestProfile(3, 5)),
            ),
            SequenceRandom([1, 2, 10]),
        )
        second = resolve_exacting_test_contribution(
            ExactingTestContributionRequest(
                "task:1:attempt:2",
                first.progress,
                "ally",
                TestRequest("task:1:test:2", TestProfile(3, 5)),
            ),
            SequenceRandom([1, 2, 3]),
        )

        self.assertEqual(first.progress.accumulated_successes, 2)
        self.assertFalse(first.progress.completed)
        self.assertEqual(second.progress.accumulated_successes, 5)
        self.assertTrue(second.progress.completed)
        self.assertEqual(
            tuple(item.contributor_id for item in second.progress.contributions),
            ("hero", "ally"),
        )

    def test_failure_adds_zero_without_reducing_progress(self) -> None:
        initial = ExactingTestProgress("task:1", 4)
        result = resolve_exacting_test_contribution(
            ExactingTestContributionRequest(
                "task:1:attempt:1",
                initial,
                "hero",
                TestRequest("task:1:test:1", TestProfile(2, 5)),
            ),
            SequenceRandom([9, 10]),
        )

        self.assertEqual(result.contribution.successes, 0)
        self.assertEqual(result.progress.accumulated_successes, 0)
        self.assertEqual(len(result.progress.contributions), 1)

    def test_completed_progress_and_reused_ids_are_rejected(self) -> None:
        first = resolve_exacting_test_contribution(
            ExactingTestContributionRequest(
                "attempt:1",
                ExactingTestProgress("task:1", 1),
                "hero",
                TestRequest("test:1", TestProfile(1, 5)),
            ),
            SequenceRandom([1]),
        )
        with self.assertRaises(ValueError):
            ExactingTestContributionRequest(
                "attempt:2",
                first.progress,
                "hero",
                TestRequest("test:2", TestProfile(1, 5)),
            )

        incomplete = replace(first.progress, required_successes=2)
        for request_id, test_id in (
            ("attempt:1", "test:2"),
            ("attempt:2", "test:1"),
        ):
            with self.subTest(request_id=request_id, test_id=test_id):
                with self.assertRaises(ValueError):
                    ExactingTestContributionRequest(
                        request_id,
                        incomplete,
                        "hero",
                        TestRequest(test_id, TestProfile(1, 5)),
                    )

    def test_unknown_rule_and_forged_transition_are_rejected(self) -> None:
        request = ExactingTestContributionRequest(
            "attempt:1",
            ExactingTestProgress("task:1", 2, rule_id="RULE:wrong"),
            "hero",
            TestRequest("test:1", TestProfile(1, 5)),
            rule_id="RULE:wrong",
        )
        with self.assertRaises(ValueError):
            resolve_exacting_test_contribution(request, SequenceRandom([]))

        canonical = resolve_exacting_test_contribution(
            ExactingTestContributionRequest(
                "attempt:canonical",
                ExactingTestProgress("task:canonical", 2),
                "hero",
                TestRequest("test:canonical", TestProfile(1, 5)),
            ),
            SequenceRandom([1]),
        )
        with self.assertRaises(ValueError):
            replace(
                canonical,
                progress=replace(canonical.progress, required_successes=3),
            )


class K1CombatSurgeonBattleSurgeryTests(unittest.TestCase):
    def test_three_actions_accumulate_eight_successes_and_create_proof(
        self,
    ) -> None:
        state = surgical_state()
        first = execute_combat_surgeon_battle_surgery_action(
            surgery_request(1, state),
            SequenceRandom([1, 2, 10]),
        )
        second = execute_combat_surgeon_battle_surgery_action(
            surgery_request(2, state, progress=first.progress),
            SequenceRandom([1, 2, 3]),
        )
        third = execute_combat_surgeon_battle_surgery_action(
            surgery_request(3, state, progress=second.progress),
            SequenceRandom([1, 2, 3]),
        )

        self.assertEqual(first.progress.exacting.accumulated_successes, 2)
        self.assertEqual(second.progress.exacting.accumulated_successes, 5)
        self.assertEqual(third.progress.exacting.accumulated_successes, 8)
        self.assertFalse(first.completed)
        self.assertFalse(second.completed)
        self.assertTrue(third.completed)
        proof = third.proof
        assert proof is not None
        self.assertEqual(
            proof.required_successes,
            COMBAT_SURGEON_BATTLE_SURGERY_REQUIRED_SUCCESSES,
        )
        self.assertEqual(proof.accumulated_successes, 8)
        self.assertEqual(proof.final_action_request_id, third.request_id)
        self.assertEqual(proof.injury_state, state)

    def test_each_contribution_executes_exactly_one_action(self) -> None:
        state = surgical_state()
        result = execute_combat_surgeon_battle_surgery_action(
            surgery_request(1, state),
            SequenceRandom([1, 10, 10]),
        )

        self.assertTrue(result.slot.executed)
        receipt = result.slot.execution
        assert receipt is not None
        self.assertEqual(receipt.source_request_id, result.request_id)
        self.assertEqual(receipt.result_request_id, result.exacting.request_id)
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", result.round_state, "surgeon")
        )
        self.assertEqual(ended.completed_turn.actor_id, "surgeon")

    def test_failed_action_preserves_progress_and_returns_book_risk(self) -> None:
        state = surgical_state()
        first = execute_combat_surgeon_battle_surgery_action(
            surgery_request(1, state),
            SequenceRandom([1, 2, 10]),
        )
        failed = execute_combat_surgeon_battle_surgery_action(
            surgery_request(2, state, progress=first.progress),
            SequenceRandom([8, 9, 10]),
        )

        self.assertEqual(failed.exacting.contribution.successes, 0)
        self.assertEqual(failed.progress.exacting.accumulated_successes, 2)
        self.assertIsNone(failed.proof)
        risk = failed.failure_risk
        assert risk is not None
        self.assertEqual(risk.rule_id, SURGERY_FAILURE_RISK_RULE_ID)
        self.assertEqual(risk.source_surgery_id, failed.request_id)
        self.assertEqual(risk.source_test_id, "battle:1:surgery:dexterity:2")
        self.assertIs(failed.state, state)

    def test_no_operating_theatre_fact_is_required_but_tools_and_supports_are(
        self,
    ) -> None:
        state = surgical_state()
        result = execute_combat_surgeon_battle_surgery_action(
            surgery_request(1, state),
            SequenceRandom([1, 10, 10]),
        )
        self.assertTrue(result.slot.executed)

        for changes in (
            {"has_specialist_medical_tools": False},
            {"has_recovery_supports": False},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    surgery_request(1, state, **changes)

    def test_talent_dexterity_ability_slot_and_defenceless_preflight(self) -> None:
        state = surgical_state()
        invalid = (
            {
                "surgeon_talent_rule_ids": (),
            },
            {"skill": Skill.RECALL},
            {
                "surgeon_conditions": ConditionState({Condition.DEFENCELESS}),
            },
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    surgery_request(1, state, **changes)

        invalid_rounds = (
            active_round(kind=CombatActionKind.RECOVER),
            active_round(improvise_kind=ImproviseKind.SKILL),
            active_round(approach_id="RULE:other"),
            active_round(produces_attack=True),
        )
        for round_state in invalid_rounds:
            with self.subTest(round_state=round_state):
                request = surgery_request(1, state, round_state=round_state)
                with self.assertRaises(ValueError):
                    execute_combat_surgeon_battle_surgery_action(
                        request,
                        SequenceRandom([]),
                    )

    def test_self_or_close_ally_is_allowed_but_enemy_and_distant_ally_are_not(
        self,
    ) -> None:
        state = surgical_state()
        ally = surgery_request(
            1,
            state,
            target_id="ally",
            target_in_close_range=True,
        )
        result = execute_combat_surgeon_battle_surgery_action(
            ally,
            SequenceRandom([1, 10, 10]),
        )
        self.assertEqual(result.progress.target_id, "ally")

        for target_id, close in (("ally", False), ("enemy", True)):
            with self.subTest(target_id=target_id, close=close):
                with self.assertRaises(ValueError):
                    surgery_request(
                        1,
                        state,
                        target_id=target_id,
                        target_in_close_range=close,
                    )

    def test_surgical_wound_and_history_are_checked_before_rng(self) -> None:
        ordinary = surgical_state(
            entry_id=WoundEntryId.BLACKING_OUT,
            total=19,
        )
        with self.assertRaises(ValueError):
            execute_combat_surgeon_battle_surgery_action(
                surgery_request(1, ordinary),
                SequenceRandom([]),
            )

        stale_history = surgical_state(
            entry_id=WoundEntryId.SEVERED_LEG,
            total=20,
        )
        with self.assertRaises(ValueError):
            execute_combat_surgeon_battle_surgery_action(
                surgery_request(1, stale_history),
                SequenceRandom([]),
            )

    def test_progress_is_bound_to_exact_battle_surgeon_target_wound_and_state(
        self,
    ) -> None:
        state = surgical_state()
        first = execute_combat_surgeon_battle_surgery_action(
            surgery_request(1, state),
            SequenceRandom([1, 10, 10]),
        )
        stale_state = replace(state, dead=True)
        invalid = (
            {"battle_id": "battle:2"},
            {"surgery_id": "other:surgery"},
            {"target_id": "ally", "target_in_close_range": True},
            {"injury_state": stale_state},
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    surgery_request(
                        2,
                        state,
                        progress=first.progress,
                        **changes,
                    )

    def test_completed_progress_repeat_and_forged_result_are_rejected(self) -> None:
        state = surgical_state()
        almost = execute_combat_surgeon_battle_surgery_action(
            surgery_request(1, state),
            SequenceRandom([1, 2, 3]),
        )
        completed = execute_combat_surgeon_battle_surgery_action(
            surgery_request(2, state, progress=almost.progress),
            SequenceRandom([1, 2, 3]),
        )
        completed = execute_combat_surgeon_battle_surgery_action(
            surgery_request(3, state, progress=completed.progress),
            SequenceRandom([1, 2, 10]),
        )
        self.assertTrue(completed.completed)

        with self.assertRaises(ValueError):
            surgery_request(4, state, progress=completed.progress)
        with self.assertRaises(ValueError):
            replace(completed, proof=None)
        with self.assertRaises(ValueError):
            replace(completed, state=replace(state, dead=True))

    def test_unknown_rule_is_rejected_before_rng(self) -> None:
        state = surgical_state()
        request = surgery_request(1, state, rule_id="RULE:wrong")
        with self.assertRaises(ValueError):
            execute_combat_surgeon_battle_surgery_action(
                request,
                SequenceRandom([]),
            )


if __name__ == "__main__":
    unittest.main()
