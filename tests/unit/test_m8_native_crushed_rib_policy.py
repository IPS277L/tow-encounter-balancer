"""Pure prefix-derived first consumption; real ADR56 actions, no Test replay."""
from copy import deepcopy
from dataclasses import fields, replace
from itertools import product
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from tests.unit.test_m8_crushed_rib_casting import prepared, execute, first_ten
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.integration.test_m8_crushed_rib_protection_owner import public_fixture
from towr.domain.npc_magic_scenario_models import (
    NpcMagicScenario, NpcMagicCrushedRibPolicy as Policy,
    NpcMagicStationaryWoundPolicy as Stationary, NpcMagicRepeatedLegSpasmPolicy as Repeated,
    validate_npc_magic_scenario_admission,
)
from towr.domain.npc_magic_crushed_rib_policy import (
    NpcMagicCrushedRibHistory as History, initial_magic_crushed_rib_history as initial,
    advance_magic_crushed_rib_history as advance, magic_crushed_rib_context as context,
    magic_crushed_rib_required as required, validate_magic_crushed_rib_step as validate,
    _validate_crushed_rib_history,
)
from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext as Context, NpcCrushedRibConsumptionWitness as Witness
from towr.domain.npc_magic_step_models import NpcMagicStep as Step
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.turn_models import CombatSide, CombatActionDeclaration, CombatActionKind
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


def selected(source):
    return replace(source, crushed_rib_continuation=Policy.NEXT_TEST_WITH_JOURNAL_WITNESSES)


def casting_prefix():
    source = admitted(wizard_side=CombatSide.OPPOSITION)
    source = replace(source, initial=replace(source.initial, wizard=replace(source.initial.wizard,
        caster=replace(source.initial.wizard.caster, wizard_level=4))))
    dice = Dice((1, 2, 3, 10, 10, 10, 10))
    stopped = run_npc_magic_scenario(source, dice)
    dice.exhausted()
    source = selected(source)
    history = initial(source)
    for step in stopped.steps:
        history = advance(source, history, step)
    assert history.state == stopped.current
    return source, history


class NativeCrushedRibPolicyTests(unittest.TestCase):
    def test_append_last_and_twelve_independent_permission_combinations(self):
        source = admitted()
        self.assertEqual(fields(NpcMagicScenario)[-2].name, 'crushed_rib_continuation')
        old_values = tuple(getattr(source, f.name) for f in fields(source)[:-2])
        self.assertEqual(NpcMagicScenario(*old_values), source)
        valid = invalid = 0
        for miscast, stationary, repeated, crushed in product((False, True), repeat=4):
            kwargs = dict(miscast_continuation=continuation_policy() if miscast else None,
                stationary_wound_continuation=Stationary.LEG_SPASM_STAND_AND_CONTINUE if stationary else None,
                repeated_leg_spasm_continuation=Repeated.STAND_ONCE_WITH_JOURNAL_WITNESSES if repeated else None,
                crushed_rib_continuation=Policy.NEXT_TEST_WITH_JOURNAL_WITNESSES if crushed else None)
            if repeated and not stationary:
                with self.assertRaises(ValueError): replace(source, **kwargs)
                invalid += 1
            else:
                new = replace(source, **kwargs)
                validate_npc_magic_scenario_admission(new)
                self.assertEqual(new.crushed_rib_continuation, kwargs['crushed_rib_continuation'])
                valid += 1
        self.assertEqual((valid, invalid), (12, 4))

    def test_initial_is_fresh_runtime_owner_and_opt_in_history_is_required(self):
        source = admitted()
        self.assertIsNone(initial(source))
        opted = selected(source)
        history = initial(opted)
        self.assertEqual(history.state, opted.initial_runtime_state)
        self.assertNotEqual(history.state, opted.initial)
        self.assertIsNone(history.consumption)
        with self.assertRaises(TypeError): context(opted, history.state, 'wizard', None)
        with self.assertRaises(ValueError): context(source, history.state, 'wizard', history)
        self.assertIsNone(context(opted, history.state, 'wizard', history))
        self.assertIsNone(context(opted, history.state, 'ally', history))
        with self.assertRaises(ValueError): context(opted, history.state, 'foreign', history)
        with self.assertRaises(TypeError): context(opted, history.state, True, history)

    def test_actual_fresh_prefix_retains_pending_effect_until_first_casting(self):
        source, history = casting_prefix()
        before, rng = deepcopy((source, history)), getstate()
        pending = context(source, history.state, 'wizard', history)
        self.assertIsNone(pending.consumption)
        self.assertTrue(required(history.state, 'wizard'))
        self.assertFalse(required(history.state, 'enemy'))
        result, state = execute(prepared(history.state, context=pending), (10, 10, 10))
        with patch('towr.engine.cowardly_flight_casting.execute_casting_attempt', side_effect=AssertionError('replay')):
            updated = advance(source, history, Step(result))
        self.assertEqual(updated.state, state)
        self.assertEqual(updated.consumption, Witness(result, result.casting.crushed_rib))
        self.assertEqual(result.casting.crushed_rib.casting.test.successes, 0)
        self.assertTrue(required(state, 'wizard'))
        self.assertEqual(context(source, state, 'wizard', updated).consumption, updated.consumption)
        self.assertEqual((source, history), before)
        self.assertEqual(getstate(), rng)

    def test_end_turn_preserves_first_witness_without_consumption(self):
        source, history = casting_prefix()
        result, state = execute(prepared(history.state), (1, 9, 10, 9))
        history = advance(source, history, Step(result))
        end = end_npc_wound_turn(NpcWoundTurnEndRequest('native57:end', state, 'wizard',
            crushed_rib_context=context(source, state, 'wizard', history)))
        updated = advance(source, history, Step(end))
        self.assertIs(updated.consumption, history.consumption)
        self.assertEqual(updated.state.roster, history.state.roster)
        self.assertIsNone(updated.state.round_state.active_turn)

    def test_history_keeps_actual_miscast_pending_without_narrow_context(self):
        source = selected(admitted(wizard_side=CombatSide.OPPOSITION))
        state = first_ten(level=2)
        history = History(state)
        result, pending = execute(prepared(state), (9, 9, 9))
        updated = advance(source, history, Step(result))
        self.assertIsNotNone(pending.pending_miscast)
        self.assertEqual(updated.state, pending)
        self.assertIsNotNone(updated.consumption)
        self.assertIsNone(context(source, pending, 'wizard', updated))
        self.assertEqual(replace(updated), updated)

    def test_none_permission_refuses_actual_and_stripped_upper_markers(self):
        source, history = casting_prefix()
        result, _ = execute(prepared(history.state), (10, 10, 10))
        old = replace(source, crushed_rib_continuation=None)
        for remove in (False, True):
            bad = deepcopy(result)
            if remove:
                object.__setattr__(bad.source, 'crushed_rib_context', None)
            with self.subTest(remove=remove), self.assertRaises(ValueError):
                validate(old, Step(bad), None)
        with self.assertRaises(ValueError):
            validate(source, Step(bad), history)

    def test_same_id_same_current_different_actual_first_test_cannot_replace_witness(self):
        example = public_fixture()
        legacy = example.enemy_first()
        state = example.first_ten(legacy)
        source = selected(legacy)
        history = History(state)
        request = example.shooting(source, state, 'native57:first', Context(state, 'wizard', True))
        first, current = example.attack(request, (10, 10, 10, 1, 6, 10, 9))
        foreign, same = example.attack(request, (10,) * 6)
        self.assertEqual(current, same)
        self.assertNotEqual(first, foreign)
        history = advance(source, history, Step(first))
        end = end_npc_wound_turn(NpcWoundTurnEndRequest('native57:end:E2', current, 'E2'))
        history = advance(source, history, Step(end))
        start = start_npc_roster_turn(NpcRosterTurnStartRequest('native57:start:E3', end.state, 'E3',
            CombatActionDeclaration(CombatActionKind.ATTACK)))
        history = advance(source, history, Step(start))
        foreign_context = Context(start.state, 'wizard', True, Witness(foreign, foreign.attack.crushed_rib))
        request = example.shooting(source, start.state, 'native57:later', foreign_context)
        later, _ = example.attack(request, (10,) * 6)
        with self.assertRaisesRegex(ValueError, 'prefix-derived'):
            validate(source, Step(later), history)
        good = example.shooting(source, start.state, 'native57:later',
            context(source, start.state, 'wizard', history))
        later, _ = example.attack(good, (10,) * 6)
        updated = advance(source, history, Step(later))
        self.assertIsNone(later.attack.crushed_rib)
        self.assertIs(updated.consumption, history.consumption)

    def test_first_protection_new_wound_pending_is_published_then_context_stops(self):
        example = public_fixture()
        legacy = example.enemy_first()
        state = example.first_ten(legacy)
        source = selected(legacy)
        history = History(state)
        request = example.shooting(source, state, 'native57:new4', context(source, state, 'wizard', history))
        result, current = example.attack(request, (1, 2, 3, 10, 10, 10, 1, 3))
        updated = advance(source, history, Step(result))
        self.assertIsNotNone(updated.consumption)
        self.assertIsNotNone(current.champion_attack.pending)
        self.assertEqual(len(current.roster.participant('wizard').state.injury.wounds), 2)
        self.assertIsNone(context(source, current, 'wizard', updated))

    def test_history_cannot_replay_a_consuming_step_or_overwrite_first_receipt(self):
        source, history = casting_prefix()
        result, state = execute(prepared(history.state), (10, 10, 10))
        updated = advance(source, history, Step(result))
        with self.assertRaises(ValueError): advance(source, updated, Step(result))
        prior_with_late_receipt = History(history.state, updated.consumption)
        with self.assertRaises(ValueError): advance(source, prior_with_late_receipt, Step(result))
        changed = replace(state, consumed_execution_ids=(*state.consumed_execution_ids, 'foreign'))
        with self.assertRaises(ValueError): _validate_crushed_rib_history(source, changed, updated)

    def test_original_equal_aliases_do_not_pass_policy_or_history_admission(self):
        source, history = casting_prefix()
        for field, value in (('crushed_rib_continuation', Policy.NEXT_TEST_WITH_JOURNAL_WITNESSES.value),):
            bad = deepcopy(source)
            object.__setattr__(bad, field, value)
            self.assertEqual(bad, source)
            with self.assertRaises(TypeError): initial(bad)
        bad = deepcopy(source)
        object.__setattr__(bad.facts, 'no_external_condition_sources', 1)
        self.assertEqual(bad, source)
        with self.assertRaises(TypeError): context(bad, history.state, 'wizard', history)
        for field, value in (('treated', 0), ('entry_id', 'crushed_rib'), ('roll_values', [10])):
            state = deepcopy(history.state)
            object.__setattr__(state.roster.participant('wizard').state.injury.wounds[-1], field, value)
            with self.subTest(field=field), self.assertRaises(TypeError): History(state)
        state = deepcopy(history.state)
        object.__setattr__(state, 'consumed_execution_ids', list(state.consumed_execution_ids))
        with self.assertRaises(TypeError): History(state)

    def test_reset_spent_history_is_an_error_not_an_unsupported_scope(self):
        source, history = casting_prefix()
        result, state = execute(prepared(history.state), (10, 10, 10))
        updated = advance(source, history, Step(result))
        reset = History(state)  # Storage alone does not claim journal membership.
        with self.assertRaisesRegex(ValueError, 'first consumption history'):
            context(source, state, 'wizard', reset)
        self.assertEqual(context(source, state, 'wizard', updated).consumption, updated.consumption)

    def test_miscast_preparation_and_roll_keep_receipt_and_none_rejects_descendants(self):
        from towr.domain.npc_roster_miscast_models import NpcRosterMiscastPreparationRequest, NpcRosterMiscastRollRequest
        from towr.rules.npc_roster_miscast_resolution import prepare_npc_roster_miscast, roll_npc_roster_miscast
        source = replace(selected(admitted(wizard_side=CombatSide.OPPOSITION)),
                         miscast_continuation=continuation_policy())
        state = first_ten(level=2)
        history = History(state)
        result, pending = execute(prepared(state), (9, 9, 9))
        history = advance(source, history, Step(result))
        policy = source.miscast_continuation
        prep = prepare_npc_roster_miscast(NpcRosterMiscastPreparationRequest('native57:prepare', pending,
            policy.choice, policy.facts))
        step = Step(prep, origin_witness=result)
        old = replace(source, crushed_rib_continuation=None)
        with self.assertRaises(ValueError): validate(old, step, None)
        continued = advance(source, history, step)
        self.assertIs(continued.consumption, history.consumption)
        self.assertIsNone(context(source, continued.state, 'wizard', continued))
        dice = Dice((7, 7, 7))
        rolled = roll_npc_roster_miscast(NpcRosterMiscastRollRequest(prep.roll_request.resolution_id, continued.state), dice)
        dice.exhausted()
        with self.assertRaises(ValueError): validate(old, Step(rolled), None)
        after = advance(source, continued, Step(rolled))
        self.assertIs(after.consumption, history.consumption)
        self.assertIsNone(context(source, after.state, 'wizard', after))

    def test_broad_storage_accepts_dead_owner_and_retains_actual_first_receipt(self):
        source, history = casting_prefix()
        result, state = execute(prepared(history.state), (10, 10, 10))
        history = advance(source, history, Step(result))
        # Storage-only authored snapshot, not a claim of an executed lethal action.
        roster = replace(state.roster, participants=tuple(
            replace(p, state=replace(p.state, injury=replace(p.state.injury, dead=True)))
            if p.state.actor_id == 'wizard' else p for p in state.roster.participants))
        dead = replace(state, roster=roster, champion_attack=replace(state.champion_attack, roster=roster),
                       minion_attack=replace(state.minion_attack, roster=roster))
        archived = History(dead, history.consumption)
        self.assertIs(archived.consumption, history.consumption)
        self.assertFalse(required(dead, 'wizard'))
        self.assertIsNone(context(source, dead, 'wizard', archived))

    def test_detached_daily_receipt_alias_is_rejected_before_full_state_equality(self):
        source, history = casting_prefix()
        forged = deepcopy(history.state)
        receipt = forged.champion_attack.daily_wounds.receipts[0]
        object.__setattr__(receipt.wound, 'treated', 0)
        self.assertEqual(forged, history.state)
        with self.assertRaises(TypeError): _validate_crushed_rib_history(source, forged, history)

    def test_spent_wound_cannot_use_prone_end_as_a_context_free_journal_consumer(self):
        from towr.domain.condition_models import Condition
        from towr.domain.npc_roster_prone_models import NpcRosterProneTurnEndRequest
        from towr.rules.npc_roster_prone_resolution import end_npc_roster_prone_turn
        source, history = casting_prefix()
        result, state = execute(prepared(history.state), (10, 10, 10))
        history = advance(source, history, Step(result))
        # Standalone lower scope permits this explicitly authored current view.
        # Native57 must still refuse it, regardless of other permissions.
        wizard = state.roster.participant('wizard')
        injury = replace(wizard.state.injury, conditions=replace(wizard.state.injury.conditions,
            conditions=wizard.state.injury.conditions.conditions | {Condition.PRONE}))
        roster = replace(state.roster, participants=tuple(
            replace(p, state=replace(p.state, injury=injury)) if p.state.actor_id == 'wizard' else p
            for p in state.roster.participants))
        current = replace(state, roster=roster, champion_attack=replace(state.champion_attack, roster=roster),
            minion_attack=replace(state.minion_attack, roster=roster))
        end = end_npc_roster_prone_turn(NpcRosterProneTurnEndRequest('native57:prone-end', current, 'wizard'))
        for opted in (False, True):
            src = source if opted else replace(source, crushed_rib_continuation=None)
            cursor = History(current, history.consumption) if opted else None
            with self.subTest(opted=opted), self.assertRaisesRegex(ValueError, 'Broken/Prone'):
                validate(src, Step(end), cursor)

    def test_forged_context_free_spent_end_cannot_enter_none_journal(self):
        source, history = casting_prefix()
        result, state = execute(prepared(history.state), (10, 10, 10))
        history = advance(source, history, Step(result))
        end = end_npc_wound_turn(NpcWoundTurnEndRequest('native57:end', state, 'wizard',
            crushed_rib_context=context(source, state, 'wizard', history)))
        forged = deepcopy(end)
        object.__setattr__(forged.source, 'crushed_rib_context', None)
        with self.assertRaisesRegex(ValueError, 'Wound10'):
            validate(replace(source, crushed_rib_continuation=None), Step(forged), None)

    def test_original_current_and_daily_wound_scalars_are_strict_before_comparison(self):
        source, history = casting_prefix()
        cases = (('sequence', True), ('entry_id', 'crushed_rib'), ('origin', 'table_roll'),
                 ('treated', 0), ('healed', 0))
        for daily, (field, value) in product((False, True), cases):
            state = deepcopy(history.state)
            wound = (state.champion_attack.daily_wounds.receipts[0].wound if daily
                     else state.roster.participant('wizard').state.injury.wounds[0])
            object.__setattr__(wound, field, value)
            self.assertEqual(state, history.state)
            with self.subTest(daily=daily, field=field), self.assertRaises(TypeError):
                _validate_crushed_rib_history(source, state, history)


if __name__ == '__main__':
    unittest.main()
