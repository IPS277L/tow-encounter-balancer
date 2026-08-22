from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    CharacterInjuryState,
    WoundEntryId,
    WoundRecord,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.recover_models import (
    RECOVER_ACTION_RULE_ID,
    RecoverActionExecutionRequest,
    RecoverConditionRemovalChoice,
    RecoverConditionRemovalResult,
    RecoverConditionTarget,
    RecoverMode,
    RecoverMountFollowUp,
    RecoverObjectInteractionFollowUp,
    RecoverStandardChoice,
    RecoverStandardResult,
    RecoverTreatWoundChoice,
    RecoverTreatWoundResult,
)
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
)
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def active_round() -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("ally", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    return start_combat_turn(
        CombatTurnStartRequest("turn:hero", state, "hero")
    ).state


def reserve_action(
    state: CombatRoundState,
    kind: CombatActionKind,
) -> CombatRoundState:
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id="slot:1",
            state=state,
            actor_id="hero",
            declaration=CombatActionDeclaration(kind),
            grant=ActionSlotGrant.STANDARD,
        )
    ).state


def self_target(conditions: ConditionState) -> RecoverConditionTarget:
    return RecoverConditionTarget("hero", conditions, None)


def ally_target(conditions: ConditionState) -> RecoverConditionTarget:
    return RecoverConditionTarget("ally", conditions, True)


def recover_request(
    state: CombatRoundState,
    *,
    actor_conditions: ConditionState,
    mode: RecoverMode,
    choice,
    actor_has_enemy_in_zone: bool = False,
) -> RecoverActionExecutionRequest:
    return RecoverActionExecutionRequest(
        id="recover:execute",
        round_state=state,
        actor_id="hero",
        actor_conditions=actor_conditions,
        actor_has_enemy_in_zone=actor_has_enemy_in_zone,
        slot_index=1,
        mode=mode,
        choice=choice,
    )


def wound_state(*, conditions: ConditionState = ConditionState()):
    return CharacterInjuryState(
        wounds=(
            WoundRecord(
                sequence=1,
                entry_id=WoundEntryId.SUPERFICIAL_INJURY,
                table_total=1,
                roll_values=(1,),
            ),
        ),
        conditions=conditions,
    )


class K1RecoverStandardTests(unittest.TestCase):
    def test_standard_recover_applies_all_selected_benefits(self) -> None:
        conditions = ConditionState(
            {Condition.STAGGERED, Condition.PRONE, Condition.DISTRACTED}
        )
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        choice = RecoverStandardChoice(
            magic_state=WizardMagicState(
                miscast_dice=2,
                casting_successes=3,
                casting_lore_id="lore:fire",
                latest_casting_roll_successes=1,
            ),
            staggered_target=self_target(conditions),
            prone_target=self_target(conditions),
            object_interaction=RecoverObjectInteractionFollowUp(
                id="recover:object",
                actor_id="hero",
                object_id="potion",
                object_in_close_range=True,
            ),
        )

        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=conditions,
                mode=RecoverMode.STANDARD,
                choice=choice,
                actor_has_enemy_in_zone=True,
            ),
            SequenceRandom([]),
        )

        self.assertIsInstance(result.resolution, RecoverStandardResult)
        resolution = result.resolution
        self.assertEqual(len(resolution.condition_changes), 1)
        change = resolution.condition_changes[0]
        self.assertEqual(
            change.removed_conditions,
            (Condition.STAGGERED, Condition.PRONE),
        )
        self.assertEqual(change.conditions.conditions, {Condition.DISTRACTED})
        self.assertEqual(resolution.miscast_dice_removed, 1)
        self.assertEqual(resolution.magic_state.miscast_dice, 1)
        self.assertEqual(resolution.magic_state.casting_successes, 3)
        self.assertIs(
            resolution.object_interaction_follow_up,
            choice.object_interaction,
        )
        self.assertTrue(result.slot.executed)

    def test_standard_recover_can_choose_different_self_and_ally_targets(self) -> None:
        actor_conditions = ConditionState({Condition.STAGGERED})
        ally_conditions = ConditionState({Condition.PRONE, Condition.DRAINED})
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        choice = RecoverStandardChoice(
            magic_state=WizardMagicState(),
            staggered_target=self_target(actor_conditions),
            prone_target=ally_target(ally_conditions),
        )

        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=actor_conditions,
                mode=RecoverMode.STANDARD,
                choice=choice,
            ),
            SequenceRandom([]),
        )

        resolution = result.resolution
        assert isinstance(resolution, RecoverStandardResult)
        self.assertEqual(
            tuple(item.entity_id for item in resolution.condition_changes),
            ("hero", "ally"),
        )
        self.assertEqual(resolution.miscast_dice_removed, 0)

    def test_mount_replaces_prone_removal_benefit(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        mount = RecoverMountFollowUp(
            id="recover:mount",
            actor_id="hero",
            mount_id="horse",
            mount_in_close_range=True,
        )
        choice = RecoverStandardChoice(
            magic_state=WizardMagicState(),
            mount=mount,
        )

        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=ConditionState(),
                mode=RecoverMode.STANDARD,
                choice=choice,
            ),
            SequenceRandom([]),
        )

        resolution = result.resolution
        assert isinstance(resolution, RecoverStandardResult)
        self.assertIs(resolution.mount_follow_up, mount)

        prone = ConditionState({Condition.PRONE})
        with self.assertRaises(ValueError):
            recover_request(
                state,
                actor_conditions=prone,
                mode=RecoverMode.STANDARD,
                choice=choice,
            )
        with self.assertRaises(ValueError):
            RecoverStandardChoice(
                magic_state=WizardMagicState(),
                prone_target=self_target(prone),
                mount=mount,
            )

    def test_standard_target_requires_condition_and_close_ally(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        with self.assertRaises(ValueError):
            recover_request(
                state,
                actor_conditions=ConditionState(),
                mode=RecoverMode.STANDARD,
                choice=RecoverStandardChoice(
                    magic_state=WizardMagicState(),
                    staggered_target=self_target(ConditionState()),
                ),
            )
        with self.assertRaises(ValueError):
            recover_request(
                state,
                actor_conditions=ConditionState(),
                mode=RecoverMode.STANDARD,
                choice=RecoverStandardChoice(
                    magic_state=WizardMagicState(),
                    prone_target=RecoverConditionTarget(
                        "ally",
                        ConditionState({Condition.PRONE}),
                        False,
                    ),
                ),
            )

    def test_standard_result_rejects_forged_condition_change(self) -> None:
        conditions = ConditionState({Condition.STAGGERED})
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=conditions,
                mode=RecoverMode.STANDARD,
                choice=RecoverStandardChoice(
                    magic_state=WizardMagicState(),
                    staggered_target=self_target(conditions),
                ),
            ),
            SequenceRandom([]),
        )
        resolution = result.resolution
        assert isinstance(resolution, RecoverStandardResult)
        with self.assertRaises(ValueError):
            replace(resolution, condition_changes=())


class K1RecoverTreatmentTests(unittest.TestCase):
    def treatment_choice(
        self,
        *,
        recall_test: TestRequest | None = None,
        automatic_lore_id: str | None = None,
        has_required_trappings: bool = True,
    ) -> RecoverTreatWoundChoice:
        injury = wound_state()
        return RecoverTreatWoundChoice(
            target=self_target(injury.conditions),
            injury_state=injury,
            wound_sequence=1,
            has_required_trappings=has_required_trappings,
            recall_test=recall_test,
            automatic_lore_id=automatic_lore_id,
        )

    def test_successful_recall_creates_treatment_application(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        choice = self.treatment_choice(
            recall_test=TestRequest("recover:recall", TestProfile(2, 5))
        )

        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=ConditionState(),
                mode=RecoverMode.TREAT_WOUND,
                choice=choice,
            ),
            SequenceRandom([1, 10]),
        )

        resolution = result.resolution
        assert isinstance(resolution, RecoverTreatWoundResult)
        self.assertFalse(resolution.automatically_succeeded)
        self.assertIsNotNone(resolution.treatment)
        self.assertEqual(resolution.treatment.source_test_id, "recover:recall")
        self.assertEqual(resolution.treatment.wound_sequence, 1)

    def test_failed_recall_completes_action_without_treatment(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        choice = self.treatment_choice(
            recall_test=TestRequest("recover:recall", TestProfile(2, 5))
        )

        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=ConditionState(),
                mode=RecoverMode.TREAT_WOUND,
                choice=choice,
            ),
            SequenceRandom([8, 10]),
        )

        resolution = result.resolution
        assert isinstance(resolution, RecoverTreatWoundResult)
        self.assertIsNone(resolution.treatment)
        self.assertTrue(result.slot.executed)

    def test_relevant_lore_succeeds_automatically_without_rng(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        choice = self.treatment_choice(automatic_lore_id="lore:anatomy")

        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=ConditionState(),
                mode=RecoverMode.TREAT_WOUND,
                choice=choice,
            ),
            SequenceRandom([]),
        )

        resolution = result.resolution
        assert isinstance(resolution, RecoverTreatWoundResult)
        self.assertTrue(resolution.automatically_succeeded)
        self.assertIsNone(resolution.test_result)
        self.assertEqual(
            resolution.treatment.automatic_lore_id,
            "lore:anatomy",
        )

    def test_treatment_requires_trappings_and_an_untreated_wound(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        no_tools = self.treatment_choice(
            recall_test=TestRequest("recover:recall", TestProfile(2, 5)),
            has_required_trappings=False,
        )
        with self.assertRaises(ValueError):
            execute_recover_action(
                recover_request(
                    state,
                    actor_conditions=ConditionState(),
                    mode=RecoverMode.TREAT_WOUND,
                    choice=no_tools,
                ),
                SequenceRandom([1, 1]),
            )

        treated_state = replace(
            wound_state(),
            wounds=(replace(wound_state().wounds[0], treated=True),),
        )
        with self.assertRaises(ValueError):
            RecoverTreatWoundChoice(
                target=self_target(treated_state.conditions),
                injury_state=treated_state,
                wound_sequence=1,
                has_required_trappings=True,
                automatic_lore_id="lore:anatomy",
            )


class K1RecoverConditionTests(unittest.TestCase):
    def condition_choice(
        self,
        *,
        allowed: bool = True,
    ) -> RecoverConditionRemovalChoice:
        conditions = ConditionState({Condition.DISTRACTED})
        return RecoverConditionRemovalChoice(
            target=self_target(conditions),
            condition=Condition.DISTRACTED,
            test=TestRequest("recover:awareness", TestProfile(2, 5)),
            test_skill=Skill.AWARENESS,
            underlying_cause_allows_removal=allowed,
        )

    def test_success_removes_one_selected_condition(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        choice = self.condition_choice()

        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=choice.target.conditions,
                mode=RecoverMode.REMOVE_CONDITION,
                choice=choice,
            ),
            SequenceRandom([1, 10]),
        )

        resolution = result.resolution
        assert isinstance(resolution, RecoverConditionRemovalResult)
        self.assertTrue(resolution.removed)
        self.assertFalse(resolution.conditions.has(Condition.DISTRACTED))

    def test_failure_keeps_condition_but_completes_action(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        choice = self.condition_choice()

        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=choice.target.conditions,
                mode=RecoverMode.REMOVE_CONDITION,
                choice=choice,
            ),
            SequenceRandom([8, 10]),
        )

        resolution = result.resolution
        assert isinstance(resolution, RecoverConditionRemovalResult)
        self.assertFalse(resolution.removed)
        self.assertEqual(resolution.conditions, choice.target.conditions)
        self.assertTrue(result.slot.executed)

    def test_ongoing_cause_prevents_test_and_standard_conditions_are_rejected(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        choice = self.condition_choice(allowed=False)
        with self.assertRaises(ValueError):
            execute_recover_action(
                recover_request(
                    state,
                    actor_conditions=choice.target.conditions,
                    mode=RecoverMode.REMOVE_CONDITION,
                    choice=choice,
                ),
                SequenceRandom([1, 1]),
            )

        with self.assertRaises(ValueError):
            RecoverConditionRemovalChoice(
                target=self_target(ConditionState({Condition.PRONE})),
                condition=Condition.PRONE,
                test=TestRequest("recover:test", TestProfile(2, 5)),
                test_skill=Skill.ATHLETICS,
                underlying_cause_allows_removal=True,
            )


class K1RecoverActionGateTests(unittest.TestCase):
    def test_defenceless_and_unsafe_broken_actor_cannot_recover(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        choice = RecoverStandardChoice(magic_state=WizardMagicState())
        for conditions, enemy_in_zone in (
            (ConditionState({Condition.DEFENCELESS}), False),
            (ConditionState({Condition.BROKEN}), True),
        ):
            with self.subTest(conditions=conditions):
                with self.assertRaises(ValueError):
                    execute_recover_action(
                        recover_request(
                            state,
                            actor_conditions=conditions,
                            mode=RecoverMode.STANDARD,
                            choice=choice,
                            actor_has_enemy_in_zone=enemy_in_zone,
                        ),
                        SequenceRandom([]),
                    )

    def test_broken_actor_can_recover_in_zone_without_enemy(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        conditions = ConditionState({Condition.BROKEN})
        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=conditions,
                mode=RecoverMode.STANDARD,
                choice=RecoverStandardChoice(magic_state=WizardMagicState()),
            ),
            SequenceRandom([]),
        )
        self.assertTrue(result.slot.executed)

    def test_wrong_slot_and_unexecuted_recover_turn_end_are_rejected(self) -> None:
        attack_state = reserve_action(active_round(), CombatActionKind.ATTACK)
        with self.assertRaises(ValueError):
            execute_recover_action(
                recover_request(
                    attack_state,
                    actor_conditions=ConditionState(),
                    mode=RecoverMode.STANDARD,
                    choice=RecoverStandardChoice(
                        magic_state=WizardMagicState()
                    ),
                ),
                SequenceRandom([]),
            )

        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        with self.assertRaises(ValueError):
            end_combat_turn(CombatTurnEndRequest("turn:end", state, "hero"))

    def test_completed_recover_allows_turn_end(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=ConditionState(),
                mode=RecoverMode.STANDARD,
                choice=RecoverStandardChoice(magic_state=WizardMagicState()),
            ),
            SequenceRandom([]),
        )
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", result.round_state, "hero")
        )
        self.assertIsNone(ended.state.active_turn)

    def test_result_rejects_forged_round_transition(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        result = execute_recover_action(
            recover_request(
                state,
                actor_conditions=ConditionState(),
                mode=RecoverMode.STANDARD,
                choice=RecoverStandardChoice(magic_state=WizardMagicState()),
            ),
            SequenceRandom([]),
        )
        with self.assertRaises(ValueError):
            replace(result, round_state=result.previous_round_state)


if __name__ == "__main__":
    unittest.main()
