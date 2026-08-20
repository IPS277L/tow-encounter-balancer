from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.action_execution_models import (
    CastingActionMiscastPreparationRequest,
    CastingActionPostTestRequest,
    CastingActionPostTestResult,
    CastingAttemptExecutionRequest,
    CastingAttemptExecutionResult,
)
from towr.domain.magic_models import (
    CastingChoice,
    CastingDecisionRequest,
    CastingSpellSelection,
    CastingTestRequest,
    MiscastPreparationRequest,
    MiscastPoolOutcome,
    MiscastRollRequest,
    SpellCastRequest,
    WizardMagicState,
)
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlotRequest,
    CombatRoundState,
    CombatSide,
    CombatTurnParticipant,
    CombatTurnStartRequest,
    ImproviseKind,
)
from towr.rules.casting_action_execution import (
    CASTING_MISCAST_PREPARATION_RULE_ID,
    CASTING_POST_TEST_RULE_ID,
    execute_casting_attempt,
    prepare_casting_action_miscast,
    resolve_casting_action_post_test,
)
from towr.rules.casting_decision_resolution import CAST_OR_WAIT_RULE_ID
from towr.rules.casting_test_resolution import CASTING_TEST_RULE_ID
from towr.rules.miscast_pool_resolution import (
    MISCAST_POOL_RULE_ID,
    RULE_OF_NINE_RULE_ID,
)
from towr.rules.turn_resolution import (
    reserve_combat_action_slot,
    start_combat_turn,
)


def executed_casting(
    rolls: list[int],
    *,
    magic_state: WizardMagicState = WizardMagicState(),
) -> CastingAttemptExecutionResult:
    round_state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant(
                "wizard",
                CombatSide.PLAYERS_AND_ALLIES,
            ),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    started = start_combat_turn(
        CombatTurnStartRequest("turn:start", round_state, "wizard")
    ).state
    reserved = reserve_combat_action_slot(
        CombatActionSlotRequest(
            id="slot:casting",
            state=started,
            actor_id="wizard",
            declaration=CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=ImproviseKind.SPELL,
                improvise_approach_id="lore:beasts",
            ),
            grant=ActionSlotGrant.STANDARD,
        )
    ).state
    return execute_casting_attempt(
        CastingAttemptExecutionRequest(
            id="execute:casting",
            state=reserved,
            actor_id="wizard",
            slot_index=1,
            casting_request=_casting_test(magic_state),
        ),
        SequenceRandom(rolls),
    )


def _casting_test(state: WizardMagicState) -> CastingTestRequest:
    return CastingTestRequest(
        id="casting:test",
        caster_id="wizard",
        lore_id="lore:beasts",
        test=TestRequest(
            id="casting:willpower",
            profile=TestProfile(3, 5),
        ),
        state=state,
    )


def decision(
    state: WizardMagicState,
    *,
    choice: CastingChoice = CastingChoice.WAIT,
    caster_id: str = "wizard",
    wizard_level: int = 2,
) -> CastingDecisionRequest:
    spell = (
        CastingSpellSelection(
            spell_rule_id="RULE-SPELL:beast-form",
            lore_id="lore:beasts",
            casting_value=state.casting_successes,
        )
        if choice is CastingChoice.CAST
        else None
    )
    return CastingDecisionRequest(
        id="casting:decision",
        caster_id=caster_id,
        state=state,
        wizard_level=wizard_level,
        choice=choice,
        selected_spell=spell,
    )


def post_test_request(
    execution: CastingAttemptExecutionResult,
    *,
    wizard_level: int = 2,
    casting_decision: CastingDecisionRequest | None,
) -> CastingActionPostTestRequest:
    return CastingActionPostTestRequest(
        id="casting:post-test",
        execution=execution,
        wizard_level=wizard_level,
        decision=casting_decision,
    )


def triggered_post_test() -> CastingActionPostTestResult:
    active = WizardMagicState(
        miscast_dice=2,
        casting_successes=2,
        casting_lore_id="lore:beasts",
        latest_casting_roll_successes=2,
    )
    execution = executed_casting([9, 1, 10], magic_state=active)
    return resolve_casting_action_post_test(
        post_test_request(execution, casting_decision=None)
    )


class K1CastingActionPostTestTests(unittest.TestCase):
    def test_no_nine_resolves_wait_without_miscast_pool_phase(self) -> None:
        execution = executed_casting([1, 2, 10])

        result = resolve_casting_action_post_test(
            post_test_request(
                execution,
                casting_decision=decision(execution.casting.state),
            )
        )

        self.assertIsNone(result.miscast_pool)
        self.assertIsNotNone(result.decision)
        assert result.decision is not None
        self.assertIs(result.decision.choice, CastingChoice.WAIT)
        self.assertIs(result.state, execution.casting.state)
        self.assertEqual(
            result.applied_rule_ids,
            (CASTING_POST_TEST_RULE_ID, CAST_OR_WAIT_RULE_ID),
        )

    def test_accumulated_miscast_die_precedes_normal_cast(self) -> None:
        active = WizardMagicState(
            casting_successes=2,
            casting_lore_id="lore:beasts",
            latest_casting_roll_successes=2,
        )
        execution = executed_casting([9, 1, 10], magic_state=active)
        post_pool_state = replace(
            execution.casting.state,
            miscast_dice=1,
        )

        result = resolve_casting_action_post_test(
            post_test_request(
                execution,
                casting_decision=decision(
                    post_pool_state,
                    choice=CastingChoice.CAST,
                ),
            )
        )

        self.assertIsNotNone(result.miscast_pool)
        assert result.miscast_pool is not None
        self.assertIs(
            result.miscast_pool.outcome,
            MiscastPoolOutcome.ACCUMULATED,
        )
        self.assertEqual(result.miscast_pool.state.miscast_dice, 1)
        self.assertIsNotNone(result.decision)
        assert result.decision is not None
        self.assertIs(result.decision.choice, CastingChoice.CAST)
        self.assertEqual(result.state.miscast_dice, 1)
        self.assertIsNone(result.state.casting_lore_id)
        self.assertEqual(result.decision.follow_ups[0].base_potency, 1)
        self.assertEqual(
            result.applied_rule_ids,
            (
                CASTING_POST_TEST_RULE_ID,
                CASTING_TEST_RULE_ID,
                RULE_OF_NINE_RULE_ID,
                MISCAST_POOL_RULE_ID,
                CAST_OR_WAIT_RULE_ID,
            ),
        )

    def test_triggered_miscast_stops_before_normal_decision(self) -> None:
        active = WizardMagicState(
            miscast_dice=2,
            casting_successes=2,
            casting_lore_id="lore:beasts",
            latest_casting_roll_successes=2,
        )
        execution = executed_casting([9, 1, 10], magic_state=active)

        result = resolve_casting_action_post_test(
            post_test_request(execution, casting_decision=None)
        )

        self.assertIsNotNone(result.miscast_pool)
        assert result.miscast_pool is not None
        self.assertIs(
            result.miscast_pool.outcome,
            MiscastPoolOutcome.MISCAST_TRIGGERED,
        )
        self.assertEqual(result.state.miscast_dice, 3)
        self.assertEqual(result.state.casting_successes, 3)
        self.assertIsNone(result.decision)
        self.assertIsNotNone(result.miscast_pool.roll_request)
        assert result.miscast_pool.roll_request is not None
        self.assertEqual(result.miscast_pool.roll_request.dice_count, 3)

    def test_decision_presence_must_match_threshold_outcome(self) -> None:
        normal = executed_casting([1, 2, 10])
        with self.assertRaises(ValueError):
            resolve_casting_action_post_test(
                post_test_request(normal, casting_decision=None)
            )

        active = WizardMagicState(miscast_dice=2)
        triggered = executed_casting([9, 1, 10], magic_state=active)
        with self.assertRaises(ValueError):
            resolve_casting_action_post_test(
                post_test_request(
                    triggered,
                    casting_decision=decision(triggered.casting.state),
                )
            )

    def test_decision_must_match_actor_level_and_post_pool_state(self) -> None:
        execution = executed_casting([1, 2, 10])
        cases = (
            decision(execution.casting.state, caster_id="enemy"),
            decision(execution.casting.state, wizard_level=1),
            decision(
                replace(execution.casting.state, miscast_dice=1),
            ),
        )
        for invalid in cases:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    resolve_casting_action_post_test(
                        post_test_request(
                            execution,
                            casting_decision=invalid,
                        )
                    )

    def test_forged_casting_follow_up_is_rejected(self) -> None:
        execution = executed_casting([9, 1, 10])
        source = execution.casting.follow_ups[0]
        forged_casting = replace(
            execution.casting,
            follow_ups=(replace(source, target_id="enemy"),),
        )
        forged_execution = replace(execution, casting=forged_casting)

        with self.assertRaises(ValueError):
            resolve_casting_action_post_test(
                post_test_request(
                    forged_execution,
                    casting_decision=None,
                )
            )

    def test_forged_miscast_count_or_lore_is_rejected(self) -> None:
        execution = executed_casting([1, 2, 10])
        forged_results = (
            replace(execution.casting, miscast_dice_added=1),
            replace(execution.casting, lore_id="lore:fire"),
        )
        for casting in forged_results:
            with self.subTest(casting=casting):
                forged_execution = replace(execution, casting=casting)
                with self.assertRaises(ValueError):
                    resolve_casting_action_post_test(
                        post_test_request(
                            forged_execution,
                            casting_decision=None,
                        )
                    )

    def test_result_rejects_state_or_nested_decision_forgery(self) -> None:
        execution = executed_casting([1, 2, 10])
        result = resolve_casting_action_post_test(
            post_test_request(
                execution,
                casting_decision=decision(execution.casting.state),
            )
        )

        with self.assertRaises(ValueError):
            replace(result, state=WizardMagicState())
        with self.assertRaises(ValueError):
            replace(result, decision=None)


class K1CastingActionMiscastPreparationTests(unittest.TestCase):
    def test_declining_spell_prepares_unmodified_miscast_roll(self) -> None:
        post_test = triggered_post_test()
        pool = post_test.miscast_pool
        assert pool is not None and pool.roll_request is not None
        preparation_request = MiscastPreparationRequest(
            id="casting:miscast-preparation",
            source=pool.roll_request,
            state=post_test.state,
        )

        result = prepare_casting_action_miscast(
            CastingActionMiscastPreparationRequest(
                id="casting:action-miscast",
                post_test=post_test,
                preparation=preparation_request,
            )
        )

        self.assertEqual(result.preparation.previous_casting_successes, 3)
        self.assertEqual(result.state.miscast_dice, 3)
        self.assertEqual(result.state.casting_successes, 0)
        self.assertIsNone(result.state.casting_lore_id)
        self.assertEqual(len(result.preparation.follow_ups), 1)
        roll = result.preparation.follow_ups[0]
        self.assertIsInstance(roll, MiscastRollRequest)
        assert isinstance(roll, MiscastRollRequest)
        self.assertEqual(roll.pool_dice_count, 3)
        self.assertEqual(roll.bonus_dice, 0)
        self.assertEqual(
            result.applied_rule_ids,
            (
                CASTING_MISCAST_PREPARATION_RULE_ID,
                MISCAST_POOL_RULE_ID,
            ),
        )

    def test_spell_is_ordered_before_miscast_roll_and_adds_one_die(self) -> None:
        post_test = triggered_post_test()
        pool = post_test.miscast_pool
        assert pool is not None and pool.roll_request is not None
        preparation_request = MiscastPreparationRequest(
            id="casting:miscast-preparation",
            source=pool.roll_request,
            state=post_test.state,
            spell_to_cast=CastingSpellSelection(
                spell_rule_id="RULE-SPELL:beast-form",
                lore_id="lore:beasts",
                casting_value=3,
            ),
        )

        result = prepare_casting_action_miscast(
            CastingActionMiscastPreparationRequest(
                id="casting:action-miscast",
                post_test=post_test,
                preparation=preparation_request,
            )
        )

        self.assertEqual(len(result.preparation.follow_ups), 2)
        spell, roll = result.preparation.follow_ups
        self.assertIsInstance(spell, SpellCastRequest)
        assert isinstance(spell, SpellCastRequest)
        self.assertEqual(spell.caster_id, "wizard")
        self.assertEqual(spell.base_potency, 1)
        self.assertIsInstance(roll, MiscastRollRequest)
        assert isinstance(roll, MiscastRollRequest)
        self.assertEqual(roll.pool_dice_count, 3)
        self.assertEqual(roll.bonus_dice, 1)
        self.assertEqual(roll.dice_count, 4)

    def test_normal_post_test_cannot_enter_miscast_preparation(self) -> None:
        normal_execution = executed_casting([1, 2, 10])
        normal = resolve_casting_action_post_test(
            post_test_request(
                normal_execution,
                casting_decision=decision(normal_execution.casting.state),
            )
        )
        triggered = triggered_post_test()
        pool = triggered.miscast_pool
        assert pool is not None and pool.roll_request is not None
        preparation = MiscastPreparationRequest(
            id="casting:miscast-preparation",
            source=pool.roll_request,
            state=triggered.state,
        )

        with self.assertRaises(ValueError):
            prepare_casting_action_miscast(
                CastingActionMiscastPreparationRequest(
                    id="casting:action-miscast",
                    post_test=normal,
                    preparation=preparation,
                )
            )

    def test_preparation_must_match_source_actor_and_state(self) -> None:
        post_test = triggered_post_test()
        pool = post_test.miscast_pool
        assert pool is not None and pool.roll_request is not None
        source = pool.roll_request
        cases = (
            MiscastPreparationRequest(
                id="preparation:wrong-source",
                source=replace(source, resolution_id="forged:roll"),
                state=post_test.state,
            ),
            MiscastPreparationRequest(
                id="preparation:wrong-actor",
                source=replace(source, target_id="enemy"),
                state=post_test.state,
            ),
            MiscastPreparationRequest(
                id="preparation:wrong-state",
                source=source,
                state=replace(
                    post_test.state,
                    casting_successes=4,
                ),
            ),
            MiscastPreparationRequest(
                id="preparation:wrong-rule",
                source=source,
                state=post_test.state,
                rule_id="RULE-MAGIC:forged",
            ),
        )
        for preparation in cases:
            with self.subTest(preparation=preparation):
                with self.assertRaises(ValueError):
                    prepare_casting_action_miscast(
                        CastingActionMiscastPreparationRequest(
                            id="casting:action-miscast",
                            post_test=post_test,
                            preparation=preparation,
                        )
                    )

    def test_result_rejects_state_or_actor_forgery(self) -> None:
        post_test = triggered_post_test()
        pool = post_test.miscast_pool
        assert pool is not None and pool.roll_request is not None
        result = prepare_casting_action_miscast(
            CastingActionMiscastPreparationRequest(
                id="casting:action-miscast",
                post_test=post_test,
                preparation=MiscastPreparationRequest(
                    id="casting:miscast-preparation",
                    source=pool.roll_request,
                    state=post_test.state,
                ),
            )
        )

        with self.assertRaises(ValueError):
            replace(result, state=post_test.state)
        with self.assertRaises(ValueError):
            replace(
                result,
                preparation=replace(
                    result.preparation,
                    target_id="enemy",
                ),
            )


if __name__ == "__main__":
    unittest.main()
