from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.downtime_models import RestAndRecoveryEndeavourRequest
from towr.domain.injury_models import (
    CharacterInjuryState,
    DecisionOwner,
    WoundEffectDuration,
    WoundEntryId,
    WoundRecord,
    WoundRestriction,
    WoundRestrictionEffect,
)
from towr.domain.surgery_models import (
    DOWNTIME_SURGERY_RULE_ID,
    SURGERY_FAILURE_RISK_RULE_ID,
    DowntimeSurgeryRequest,
    SurgeryFailureRisk,
)
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.domain.wound_healing_models import RestAndRecoveryHealingRequest
from towr.rules.downtime_resolution import (
    execute_rest_and_recovery_endeavour,
)
from towr.rules.surgery_resolution import resolve_downtime_surgery
from towr.rules.wound_healing_resolution import (
    apply_rest_and_recovery_healing,
)


def surgical_state(
    entry_id: WoundEntryId = WoundEntryId.SEVERED_ARM,
    total: int = 20,
) -> CharacterInjuryState:
    values = (10, 10) if total == 20 else (10, 10, total - 20)
    permanent = {
        WoundEntryId.SEVERED_ARM: WoundRestriction.ARM_LOST,
        WoundEntryId.SEVERED_LEG: WoundRestriction.LEG_LOST,
        WoundEntryId.RUPTURED_ORGANS: (
            WoundRestriction.PHYSICAL_STAGGER_BECOMES_WOUND
        ),
    }.get(entry_id)
    effects = (
        (
            WoundRestrictionEffect(
                1,
                permanent,
                WoundEffectDuration.PERMANENT,
            ),
        )
        if permanent is not None
        else ()
    )
    return CharacterInjuryState(
        wounds=(
            WoundRecord(
                1,
                entry_id,
                total,
                values,
                treated=True,
                effect_resolved=True,
            ),
            WoundRecord(
                2,
                WoundEntryId.SLASHED_FOREARMS,
                16,
                (10, 6),
                treated=True,
                effect_resolved=True,
            ),
        ),
        conditions=ConditionState(),
        active_wound_effects=effects,
    )


def surgery_request(
    state: CharacterInjuryState,
    *,
    wound_sequence: int = 1,
    downtime_id: str = "downtime:1",
    target_id: str = "hero",
    skill: Skill = Skill.DEXTERITY,
    rule_id: str = DOWNTIME_SURGERY_RULE_ID,
    **facts,
) -> DowntimeSurgeryRequest:
    values = {
        "id": "downtime:1:surgery:hero:1",
        "downtime_id": downtime_id,
        "surgeon_id": "doktor",
        "target_id": target_id,
        "injury_state": state,
        "wound_sequence": wound_sequence,
        "dexterity_test": TestRequest(
            id="downtime:1:surgery:hero:1:dexterity",
            profile=TestProfile(2, 6),
        ),
        "surgeon_has_anatomy_lore": True,
        "has_operating_theatre": True,
        "has_specialist_medical_tools": True,
        "has_time_to_work": True,
        "has_recovery_supports": True,
        "skill": skill,
        "rule_id": rule_id,
    }
    values.update(facts)
    return DowntimeSurgeryRequest(**values)


def successful_surgery(state: CharacterInjuryState):
    return resolve_downtime_surgery(
        surgery_request(state),
        SequenceRandom([3, 9]),
    )


def successful_recovery(state: CharacterInjuryState):
    request = RestAndRecoveryEndeavourRequest(
        id="downtime:1:recovery:hero",
        downtime_id="downtime:1",
        target_id="hero",
        injury_state=state,
        endurance_test=TestRequest(
            id="downtime:1:recovery:hero:endurance",
            profile=TestProfile(2, 6),
        ),
    )
    return execute_rest_and_recovery_endeavour(
        request,
        SequenceRandom([2, 9]),
    )


class K1DowntimeSurgeryTests(unittest.TestCase):
    def test_successful_proof_unlocks_one_surgical_wound(self) -> None:
        state = surgical_state()
        surgery = successful_surgery(state)
        endeavour = successful_recovery(state)
        request = RestAndRecoveryHealingRequest(
            id="downtime:1:recovery:hero:heal",
            endeavour=endeavour,
            surgery=surgery,
            target_id="hero",
            injury_state=state,
            wound_sequence=1,
            consumed_source_ids=("prior-source",),
        )

        result = apply_rest_and_recovery_healing(request)

        self.assertTrue(surgery.succeeded)
        self.assertIsNone(surgery.failure_risk)
        self.assertEqual(surgery.state, state)
        self.assertTrue(result.state.wounds[0].healed)
        self.assertFalse(result.state.wounds[1].healed)
        self.assertEqual(result.state.active_wound_effects, state.active_wound_effects)
        self.assertEqual(
            result.consumed_source_ids,
            ("prior-source", surgery.request_id, endeavour.request_id),
        )
        self.assertIn(DOWNTIME_SURGERY_RULE_ID, result.applied_rule_ids)

    def test_every_surgical_table_row_20_to_23_is_supported(self) -> None:
        entries = (
            WoundEntryId.SEVERED_ARM,
            WoundEntryId.SEVERED_LEG,
            WoundEntryId.RUPTURED_ORGANS,
            WoundEntryId.RUINED_EYES,
        )
        for entry_id, total in zip(entries, range(20, 24), strict=True):
            with self.subTest(total=total):
                state = surgical_state(entry_id, total)
                surgery = successful_surgery(state)
                healing = RestAndRecoveryHealingRequest(
                    id=f"heal:{total}",
                    endeavour=successful_recovery(state),
                    surgery=surgery,
                    target_id="hero",
                    injury_state=state,
                    wound_sequence=1,
                )
                result = apply_rest_and_recovery_healing(healing)
                self.assertTrue(result.state.wounds[0].healed)

    def test_failed_surgery_exposes_risks_without_choosing_outcome(self) -> None:
        state = surgical_state()

        result = resolve_downtime_surgery(
            surgery_request(state),
            SequenceRandom([8, 9]),
        )

        self.assertFalse(result.succeeded)
        self.assertEqual(result.state, state)
        risk = result.failure_risk
        self.assertIsNotNone(risk)
        assert risk is not None
        self.assertEqual(
            risk.possible_risks,
            (
                SurgeryFailureRisk.PERMANENT_DISFIGUREMENT,
                SurgeryFailureRisk.DEATH,
            ),
        )
        self.assertIs(risk.decision_owner, DecisionOwner.GM)
        self.assertEqual(risk.rule_id, SURGERY_FAILURE_RISK_RULE_ID)
        with self.assertRaisesRegex(ValueError, "successful surgery"):
            RestAndRecoveryHealingRequest(
                id="failed-surgery:heal",
                endeavour=successful_recovery(state),
                surgery=result,
                target_id="hero",
                injury_state=state,
                wound_sequence=1,
            )

    def test_ordinary_surgery_requires_every_book_resource(self) -> None:
        state = surgical_state()
        facts = (
            "surgeon_has_anatomy_lore",
            "has_operating_theatre",
            "has_specialist_medical_tools",
            "has_time_to_work",
            "has_recovery_supports",
        )
        for fact in facts:
            with self.subTest(missing=fact):
                with self.assertRaises(ValueError):
                    surgery_request(state, **{fact: False})

    def test_request_requires_dexterity_and_ready_wound(self) -> None:
        state = surgical_state()
        with self.assertRaisesRegex(ValueError, "Dexterity Test"):
            surgery_request(state, skill=Skill.RECALL)

        untreated = replace(
            state,
            wounds=(replace(state.wounds[0], treated=False), state.wounds[1]),
        )
        with self.assertRaisesRegex(ValueError, "treated Wound"):
            surgery_request(untreated)

        unresolved = replace(
            state,
            wounds=(
                replace(state.wounds[0], effect_resolved=False),
                state.wounds[1],
            ),
        )
        with self.assertRaisesRegex(ValueError, "resolved Wound"):
            surgery_request(unresolved)

    def test_non_surgical_wound_and_unknown_rule_fail_before_test(self) -> None:
        state = surgical_state()
        with self.assertRaisesRegex(ValueError, "surgery-and-recovery"):
            resolve_downtime_surgery(
                surgery_request(state, wound_sequence=2),
                SequenceRandom([1, 1]),
            )
        with self.assertRaisesRegex(ValueError, "unknown source rule"):
            resolve_downtime_surgery(
                surgery_request(state, rule_id="HOUSE:surgery"),
                SequenceRandom([1, 1]),
            )

    def test_healing_requires_exact_surgery_provenance(self) -> None:
        state = surgical_state()
        surgery = successful_surgery(state)
        endeavour = successful_recovery(state)

        with self.assertRaisesRegex(ValueError, "another downtime"):
            RestAndRecoveryHealingRequest(
                id="wrong-downtime",
                endeavour=replace(
                    endeavour,
                    source_request=replace(
                        endeavour.source_request,
                        downtime_id="downtime:2",
                    ),
                ),
                surgery=surgery,
                target_id="hero",
                injury_state=state,
                wound_sequence=1,
            )
        with self.assertRaisesRegex(ValueError, "already consumed"):
            RestAndRecoveryHealingRequest(
                id="repeat",
                endeavour=endeavour,
                surgery=surgery,
                target_id="hero",
                injury_state=state,
                wound_sequence=1,
                consumed_source_ids=(surgery.request_id,),
            )

    def test_ordinary_proof_remains_bound_to_exact_injury_state(self) -> None:
        state = surgical_state()
        surgery = successful_surgery(state)
        changed_state = replace(
            state,
            conditions=ConditionState({Condition.STAGGERED}),
        )

        with self.assertRaisesRegex(ValueError, "stale surgery injury state"):
            RestAndRecoveryHealingRequest(
                id="changed-after-ordinary-surgery",
                endeavour=successful_recovery(changed_state),
                surgery=surgery,
                target_id="hero",
                injury_state=changed_state,
                wound_sequence=1,
            )

    def test_surgery_result_rejects_forged_state_and_risk(self) -> None:
        state = surgical_state()
        success = successful_surgery(state)
        with self.assertRaisesRegex(ValueError, "must not mutate"):
            replace(
                success,
                state=replace(
                    state,
                    conditions=ConditionState({Condition.STAGGERED}),
                ),
            )

        failure = resolve_downtime_surgery(
            surgery_request(state),
            SequenceRandom([8, 9]),
        )
        assert failure.failure_risk is not None
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                failure,
                failure_risk=replace(
                    failure.failure_risk,
                    target_id="other",
                ),
            )


if __name__ == "__main__":
    unittest.main()
