from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_combat_surgeon_battle_surgery import (
    surgical_state,
    surgery_request,
)
from towr.domain.combat_surgeon_surgery_models import (
    COMBAT_SURGEON_BATTLE_SURGERY_RULE_ID,
    CombatSurgeonBattleSurgeryProof,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.downtime_models import RestAndRecoveryEndeavourRequest
from towr.domain.injury_models import (
    CharacterInjuryState,
    WoundEntryId,
    WoundRecord,
    WoundRecordOrigin,
)
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.wound_healing_models import RestAndRecoveryHealingRequest
from towr.rules.combat_surgeon_surgery_resolution import (
    execute_combat_surgeon_battle_surgery_action,
)
from towr.rules.downtime_resolution import (
    execute_rest_and_recovery_endeavour,
)
from towr.rules.wound_healing_resolution import (
    apply_rest_and_recovery_healing,
)


def completed_battle_surgery(
    state: CharacterInjuryState,
) -> CombatSurgeonBattleSurgeryProof:
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
    proof = third.proof
    assert proof is not None
    return proof


def successful_recovery(
    state: CharacterInjuryState,
    *,
    target_id: str = "surgeon",
):
    return execute_rest_and_recovery_endeavour(
        RestAndRecoveryEndeavourRequest(
            id="downtime:1:recovery:surgeon",
            downtime_id="downtime:1",
            target_id=target_id,
            injury_state=state,
            endurance_test=TestRequest(
                id="downtime:1:recovery:surgeon:endurance",
                profile=TestProfile(2, 6),
            ),
        ),
        SequenceRandom([2, 9]),
    )


def evolved_state(state: CharacterInjuryState) -> CharacterInjuryState:
    return replace(
        state,
        wounds=(
            state.wounds[0],
            WoundRecord(
                2,
                WoundEntryId.SLASHED_FOREARMS,
                16,
                (10, 6),
                treated=True,
                effect_resolved=True,
            ),
        ),
        conditions=ConditionState({Condition.STAGGERED}),
    )


class K1CombatSurgeonBattleSurgeryHealingTests(unittest.TestCase):
    def test_completed_proof_unlocks_later_recovery_for_same_wound(self) -> None:
        battle_state = surgical_state()
        proof = completed_battle_surgery(battle_state)
        current_state = evolved_state(battle_state)
        endeavour = successful_recovery(current_state)

        result = apply_rest_and_recovery_healing(
            RestAndRecoveryHealingRequest(
                id="downtime:1:recovery:surgeon:heal",
                endeavour=endeavour,
                target_id="surgeon",
                injury_state=current_state,
                wound_sequence=1,
                surgery=proof,
                consumed_source_ids=("prior-source",),
            )
        )

        self.assertNotEqual(proof.injury_state, current_state)
        self.assertTrue(result.state.wounds[0].healed)
        self.assertFalse(result.state.wounds[1].healed)
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertEqual(
            result.consumed_source_ids,
            ("prior-source", proof.id, endeavour.request_id),
        )
        self.assertIn(
            COMBAT_SURGEON_BATTLE_SURGERY_RULE_ID,
            result.applied_rule_ids,
        )

    def test_proof_cannot_be_moved_to_another_wound_identity(self) -> None:
        battle_state = surgical_state()
        proof = completed_battle_surgery(battle_state)
        replacements = (
            WoundRecord(
                1,
                WoundEntryId.SEVERED_LEG,
                21,
                (10, 10, 1),
                treated=True,
                effect_resolved=True,
            ),
            WoundRecord(
                1,
                WoundEntryId.SEVERED_ARM,
                20,
                (9, 10, 1),
                treated=True,
                effect_resolved=True,
            ),
            WoundRecord(
                1,
                WoundEntryId.SEVERED_ARM,
                20,
                (),
                treated=True,
                effect_resolved=True,
                origin=WoundRecordOrigin.FIXED_ENTRY,
            ),
        )
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                current_state = replace(
                    battle_state,
                    wounds=(replacement,),
                )
                with self.assertRaisesRegex(ValueError, "Wound identity"):
                    RestAndRecoveryHealingRequest(
                        id="wrong-wound",
                        endeavour=successful_recovery(current_state),
                        target_id="surgeon",
                        injury_state=current_state,
                        wound_sequence=1,
                        surgery=proof,
                    )

    def test_proof_cannot_be_used_for_another_target_or_twice(self) -> None:
        state = surgical_state()
        proof = completed_battle_surgery(state)

        with self.assertRaisesRegex(ValueError, "another healing target"):
            RestAndRecoveryHealingRequest(
                id="wrong-target",
                endeavour=successful_recovery(state, target_id="other"),
                target_id="other",
                injury_state=state,
                wound_sequence=1,
                surgery=proof,
            )
        with self.assertRaisesRegex(ValueError, "already consumed"):
            RestAndRecoveryHealingRequest(
                id="reused-proof",
                endeavour=successful_recovery(state),
                target_id="surgeon",
                injury_state=state,
                wound_sequence=1,
                surgery=proof,
                consumed_source_ids=(proof.id,),
            )

    def test_proof_cannot_be_used_after_the_wound_was_healed(self) -> None:
        battle_state = surgical_state()
        proof = completed_battle_surgery(battle_state)
        healed_state = replace(
            battle_state,
            wounds=(replace(battle_state.wounds[0], healed=True),),
        )

        with self.assertRaisesRegex(ValueError, "not healed"):
            RestAndRecoveryHealingRequest(
                id="already-healed",
                endeavour=successful_recovery(healed_state),
                target_id="surgeon",
                injury_state=healed_state,
                wound_sequence=1,
                surgery=proof,
            )

    def test_noncanonical_battle_proof_is_rejected(self) -> None:
        state = surgical_state()
        proof = completed_battle_surgery(state)

        with self.assertRaisesRegex(ValueError, "canonical battle surgery"):
            RestAndRecoveryHealingRequest(
                id="noncanonical-proof",
                endeavour=successful_recovery(state),
                target_id="surgeon",
                injury_state=state,
                wound_sequence=1,
                surgery=replace(proof, rule_id="HOUSE:battle-surgery"),
            )


if __name__ == "__main__":
    unittest.main()
