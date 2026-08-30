from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_infection_resolution import tracked_day
from towr.domain.festering_wound_models import (
    FesteringWoundRecord,
    FesteringWoundState,
)
from towr.domain.infection_models import DailyWoundState
from towr.domain.infection_prevention_models import (
    ANATOMY_INFECTION_ALLOCATION_RULE_ID,
    ANATOMY_INFECTION_RECALL_RULE_ID,
    AUTOMATIC_INFECTION_SUCCESS_APPLICATION_RULE_ID,
    AnatomyInfectionAllocationRequest,
    AnatomyInfectionRecallRequest,
    AutomaticInfectionSuccessApplicationRequest,
    InfectionPreventionRelationship,
    InfectionPreventionTarget,
)
from towr.domain.injury_models import CharacterInjuryState, WoundEntryId
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.rules.infection_prevention_resolution import (
    allocate_anatomy_infection_successes,
    apply_automatic_infection_success,
    resolve_anatomy_infection_recall,
)


def retarget_daily_wounds(
    state: DailyWoundState,
    target_id: str,
) -> DailyWoundState:
    return replace(
        state,
        target_id=target_id,
        receipts=tuple(
            replace(item, target_id=target_id) for item in state.receipts
        ),
    )


def recall_result(
    values: tuple[int, ...] = (1, 2, 9),
    *,
    practitioner_id: str = "healer",
    day_id: str = "day:1",
):
    request = AnatomyInfectionRecallRequest(
        id=f"{day_id}:{practitioner_id}:anatomy-infection",
        day_id=day_id,
        practitioner_id=practitioner_id,
        has_anatomy_lore=True,
        recall_test=TestRequest(
            id=f"{day_id}:{practitioner_id}:anatomy-infection:recall",
            profile=TestProfile(len(values), 6),
        ),
    )
    return resolve_anatomy_infection_recall(
        request,
        SequenceRandom(values),
    )


def two_target_allocation():
    daily, injury = tracked_day(1)
    healer_day = retarget_daily_wounds(daily, "healer")
    hero_day = retarget_daily_wounds(daily, "hero")
    request = AnatomyInfectionAllocationRequest(
        id="day:1:healer:anatomy-allocation",
        recall=recall_result(),
        targets=(
            InfectionPreventionTarget(
                healer_day,
                InfectionPreventionRelationship.SELF,
            ),
            InfectionPreventionTarget(
                hero_day,
                InfectionPreventionRelationship.ALLY,
            ),
        ),
        consumed_recall_ids=("prior-recall",),
    )
    return allocate_anatomy_infection_successes(request), injury


class K1AnatomyInfectionRecallTests(unittest.TestCase):
    def test_recall_successes_become_allocation_capacity(self) -> None:
        result = recall_result()

        self.assertEqual(result.test_result.successes, 2)
        self.assertEqual(result.available_successes, 2)
        self.assertIn(
            ANATOMY_INFECTION_RECALL_RULE_ID,
            result.applied_rule_ids,
        )

    def test_recall_requires_anatomy_lore_recall_skill_and_known_rule(
        self,
    ) -> None:
        base = {
            "id": "day:1:healer:anatomy",
            "day_id": "day:1",
            "practitioner_id": "healer",
            "has_anatomy_lore": True,
            "recall_test": TestRequest(
                "day:1:healer:recall",
                TestProfile(2, 6),
            ),
        }
        for changes in (
            {"has_anatomy_lore": False},
            {"skill": Skill.ENDURANCE},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    AnatomyInfectionRecallRequest(**{**base, **changes})

        unknown = AnatomyInfectionRecallRequest(
            **base,
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            resolve_anatomy_infection_recall(
                unknown,
                SequenceRandom([1, 9]),
            )

    def test_recall_result_rejects_forged_capacity(self) -> None:
        result = recall_result()

        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, available_successes=3)


class K1AnatomyInfectionAllocationTests(unittest.TestCase):
    def test_ordered_self_and_ally_targets_receive_one_proof_each(
        self,
    ) -> None:
        result, _ = two_target_allocation()

        self.assertEqual(result.allocated_successes, 2)
        self.assertEqual(result.unused_successes, 0)
        self.assertEqual(
            tuple(item.target_id for item in result.proofs),
            ("healer", "hero"),
        )
        self.assertEqual(
            tuple(item.relationship for item in result.proofs),
            (
                InfectionPreventionRelationship.SELF,
                InfectionPreventionRelationship.ALLY,
            ),
        )
        self.assertEqual(
            result.consumed_recall_ids,
            ("prior-recall", result.source_request.recall.request_id),
        )
        self.assertIn(
            ANATOMY_INFECTION_ALLOCATION_RULE_ID,
            result.applied_rule_ids,
        )

    def test_allocation_may_leave_successes_unused_or_allocate_none(
        self,
    ) -> None:
        daily, _ = tracked_day(1)
        hero_day = retarget_daily_wounds(daily, "hero")
        source = recall_result()
        one = allocate_anatomy_infection_successes(
            AnatomyInfectionAllocationRequest(
                id="allocate:one",
                recall=source,
                targets=(
                    InfectionPreventionTarget(
                        hero_day,
                        InfectionPreventionRelationship.ALLY,
                    ),
                ),
            )
        )
        none = allocate_anatomy_infection_successes(
            AnatomyInfectionAllocationRequest(
                id="allocate:none",
                recall=recall_result((8, 9)),
            )
        )

        self.assertEqual(one.unused_successes, 1)
        self.assertEqual(len(one.proofs), 1)
        self.assertEqual(none.allocated_successes, 0)
        self.assertEqual(none.proofs, ())

    def test_allocation_rejects_overspend_duplicate_and_bad_context(
        self,
    ) -> None:
        daily, _ = tracked_day(1)
        healer = retarget_daily_wounds(daily, "healer")
        hero = retarget_daily_wounds(daily, "hero")
        other_day = replace(hero, day_id="day:2", receipts=tuple(
            replace(item, day_id="day:2") for item in hero.receipts
        ))
        source = recall_result((1, 9))
        targets = (
            (
                InfectionPreventionTarget(
                    healer,
                    InfectionPreventionRelationship.SELF,
                ),
                InfectionPreventionTarget(
                    hero,
                    InfectionPreventionRelationship.ALLY,
                ),
            ),
            (
                InfectionPreventionTarget(
                    hero,
                    InfectionPreventionRelationship.ALLY,
                ),
                InfectionPreventionTarget(
                    hero,
                    InfectionPreventionRelationship.ALLY,
                ),
            ),
            (
                InfectionPreventionTarget(
                    other_day,
                    InfectionPreventionRelationship.ALLY,
                ),
            ),
            (
                InfectionPreventionTarget(
                    healer,
                    InfectionPreventionRelationship.ALLY,
                ),
            ),
        )
        for selected in targets:
            with self.subTest(selected=selected):
                with self.assertRaises(ValueError):
                    AnatomyInfectionAllocationRequest(
                        id="invalid:allocation",
                        recall=source,
                        targets=selected,
                    )

    def test_empty_or_closed_target_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            InfectionPreventionTarget(
                DailyWoundState("day:1", "hero"),
                InfectionPreventionRelationship.ALLY,
            )
        daily, _ = tracked_day(1)
        with self.assertRaises(ValueError):
            InfectionPreventionTarget(
                replace(daily, closed_by_infection_id="infection:done"),
                InfectionPreventionRelationship.ALLY,
            )

    def test_recall_is_allocated_once_and_result_cannot_be_forged(self) -> None:
        result, _ = two_target_allocation()
        with self.assertRaisesRegex(ValueError, "already allocated"):
            AnatomyInfectionAllocationRequest(
                id="repeat:allocation",
                recall=result.source_request.recall,
                consumed_recall_ids=result.consumed_recall_ids,
            )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, proofs=result.proofs[:1])


class K1AutomaticInfectionSuccessTests(unittest.TestCase):
    def test_proof_closes_day_without_changing_festering_state(self) -> None:
        allocation, injury = two_target_allocation()
        proof = allocation.proofs[1]
        existing = FesteringWoundState(
            "hero",
            (
                FesteringWoundRecord(
                    "hero:festering:old",
                    "day:0:hero:infection",
                ),
            ),
        )
        request = AutomaticInfectionSuccessApplicationRequest(
            id="day:1:hero:automatic-infection-success",
            allocation=allocation,
            proof_id=proof.id,
            target_id="hero",
            daily_wounds=proof.daily_wounds,
            injury_state=injury,
            festering_wound_state=existing,
            consumed_proof_ids=("prior-proof",),
        )

        result = apply_automatic_infection_success(request)

        self.assertTrue(result.daily_wounds.is_closed)
        self.assertEqual(
            result.daily_wounds.closed_by_infection_id,
            request.id,
        )
        self.assertEqual(result.festering_wound_state, existing)
        self.assertEqual(
            result.consumed_proof_ids,
            ("prior-proof", proof.id),
        )
        self.assertIn(
            AUTOMATIC_INFECTION_SUCCESS_APPLICATION_RULE_ID,
            result.applied_rule_ids,
        )

    def test_each_allocated_proof_is_independently_target_bound(self) -> None:
        allocation, injury = two_target_allocation()
        for proof in allocation.proofs:
            with self.subTest(target_id=proof.target_id):
                result = apply_automatic_infection_success(
                    AutomaticInfectionSuccessApplicationRequest(
                        id=f"{proof.target_id}:apply-proof",
                        allocation=allocation,
                        proof_id=proof.id,
                        target_id=proof.target_id,
                        daily_wounds=proof.daily_wounds,
                        injury_state=injury,
                        festering_wound_state=FesteringWoundState(
                            proof.target_id
                        ),
                    )
                )
                self.assertEqual(result.target_id, proof.target_id)

    def test_wrong_proof_target_or_stale_day_is_rejected(self) -> None:
        allocation, injury = two_target_allocation()
        proof = allocation.proofs[1]
        invalid = (
            {"proof_id": "missing-proof"},
            {"target_id": "other"},
            {
                "daily_wounds": replace(
                    proof.daily_wounds,
                    closed_by_infection_id="infection:done",
                )
            },
        )
        base = {
            "id": "invalid:application",
            "allocation": allocation,
            "proof_id": proof.id,
            "target_id": "hero",
            "daily_wounds": proof.daily_wounds,
            "injury_state": injury,
            "festering_wound_state": FesteringWoundState("hero"),
        }
        for changes in invalid:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    AutomaticInfectionSuccessApplicationRequest(
                        **{**base, **changes}
                    )

    def test_repeat_changed_wound_and_dead_target_are_rejected(self) -> None:
        allocation, injury = two_target_allocation()
        proof = allocation.proofs[1]
        with self.assertRaisesRegex(ValueError, "already consumed"):
            AutomaticInfectionSuccessApplicationRequest(
                id="repeat:application",
                allocation=allocation,
                proof_id=proof.id,
                target_id="hero",
                daily_wounds=proof.daily_wounds,
                injury_state=injury,
                festering_wound_state=FesteringWoundState("hero"),
                consumed_proof_ids=(proof.id,),
            )

        changed = replace(
            injury,
            wounds=(
                replace(
                    injury.wounds[0],
                    entry_id=WoundEntryId.NICKED_ARM,
                ),
            ),
        )
        for current in (changed, replace(injury, dead=True)):
            with self.subTest(current=current):
                with self.assertRaises(ValueError):
                    AutomaticInfectionSuccessApplicationRequest(
                        id="invalid:history",
                        allocation=allocation,
                        proof_id=proof.id,
                        target_id="hero",
                        daily_wounds=proof.daily_wounds,
                        injury_state=current,
                        festering_wound_state=FesteringWoundState("hero"),
                    )

    def test_unknown_rule_and_forged_result_are_rejected(self) -> None:
        allocation, injury = two_target_allocation()
        proof = allocation.proofs[1]
        request = AutomaticInfectionSuccessApplicationRequest(
            id="hero:automatic-success",
            allocation=allocation,
            proof_id=proof.id,
            target_id="hero",
            daily_wounds=proof.daily_wounds,
            injury_state=injury,
            festering_wound_state=FesteringWoundState("hero"),
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            apply_automatic_infection_success(request)

        valid = replace(
            request,
            rule_id=AUTOMATIC_INFECTION_SUCCESS_APPLICATION_RULE_ID,
        )
        result = apply_automatic_infection_success(valid)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, daily_wounds=result.previous_daily_wounds)


if __name__ == "__main__":
    unittest.main()
