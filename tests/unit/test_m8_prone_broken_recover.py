"""ADR-0046: safe alternative Broken Recover never removes standalone Prone."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import pickle
import random
import unittest
from unittest.mock import patch

from tests.integration.test_m8_npc_broken_recover import wounded_broken_wizard
from tests.integration.test_m8_champion_casting_handoff import incoming_attack
from tests.helpers import SequenceRandom
from tests.unit.test_m8_cowardly_flight_casting import CountingDice
from tests.unit.test_m8_npc_broken_recover import request as ordinary_request
from tests.unit.test_m8_npc_roster_casting_completion import begin as movement_pending
from tests.unit.test_m8_npc_roster_miscast_preparation import casting_pending, interruption_pending
from tests.unit.test_m8_npc_roster_miscast_roll import request as roll_request
from tests.unit.test_m8_npc_roster_minion_attack import request as minion_request
from tests.unit.test_m8_npc_roster_prone_stand import with_injury, with_round
from tests.unit.test_m8_npc_wound_turn_end import wounded
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundConditionEffect, WoundEffectDuration, WoundEntryId, WoundRecord,
    WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest as Request
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.recover_models import RecoverMode, RecoverStandardChoice
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.engine.npc_broken_recover import (
    execute_npc_broken_recover as execute, apply_npc_broken_recover_result as apply,
)
from towr.rules.npc_roster_miscast_resolution import roll_npc_roster_miscast
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.recover_resolution import execute_recover_action


def request(*, actor='wizard', pool=0, active_casting=False, used=False):
    source = ordinary_request(actor=actor, safe=True, pool=pool, active_casting=active_casting)
    state = with_injury(source.state, actor, lambda injury: replace(injury,
        conditions=injury.conditions.with_condition(Condition.PRONE)
            .with_condition(Condition.STAGGERED).with_condition(Condition.DRAINED)))
    if used:
        state = replace(state, spatial_state=replace(state.spatial_state,
            free_move_used_entity_ids=(actor,)))
    return replace(source, state=state)


def wound_request():
    _, _, state = wounded_broken_wizard(1)
    actor = state.wizard.actor_id
    state = with_injury(state, actor, lambda injury: replace(injury,
        conditions=injury.conditions.with_condition(Condition.PRONE)))
    state = replace(state, spatial_state=replace(state.spatial_state,
        placements=tuple(replace(p, zone_id='empty') if p.entity_id == actor else p
                         for p in state.spatial_state.placements)))
    return Request('prone:recover', state, actor, InlineProfile(3, 3), None, True, True)


class ProneBrokenRecoverTests(unittest.TestCase):
    def test_success_removes_only_broken_for_wizard_and_minion(self):
        for actor in ('wizard', 'first'):
            source = request(actor=actor); rng = CountingDice([1, 10, 10])
            result = execute(source, rng)
            final = result.state.roster.participant(actor).state.injury
            self.assertEqual(final.conditions, source.state.roster.participant(actor).state.injury
                             .conditions.without_condition(Condition.BROKEN))
            self.assertEqual(rng.calls, 3)
            self.assertEqual(result.recover.source_request.mode, RecoverMode.REMOVE_CONDITION)
            self.assertIsNone(result.movement)
            self.assertTrue(result.state.round_state.active_turn.action_slots[0].executed)
            self.assertEqual(result.state.consumed_execution_ids, (source.id,))

    def test_failed_willpower_keeps_all_conditions_and_spends_action(self):
        for actor in ('wizard', 'first'):
            source = request(actor=actor); result = execute(source, CountingDice([10] * 3))
            self.assertFalse(result.recover.resolution.removed)
            self.assertEqual(result.state.roster, source.state.roster)
            self.assertTrue(result.state.round_state.active_turn.action_slots[0].executed)
            self.assertEqual(result.state.consumed_execution_ids, (source.id,))

    def test_used_and_unused_free_move_are_preserved_without_movement(self):
        for used in (False, True):
            source = request(used=used)
            with patch('towr.engine.npc_broken_recover.resolve_free_movement',
                       side_effect=AssertionError('Recover is stationary')):
                result = execute(source, CountingDice([1, 2, 3]))
            self.assertIs(result.state.spatial_state, source.state.spatial_state)
            self.assertTrue(result.state.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))

    def test_no_standard_pool_reduction_and_no_own_prone_test_penalty(self):
        source = request(pool=2)
        ordinary = ordinary_request(safe=True, pool=2, active_casting=False,
                                    extra_conditions=(Condition.STAGGERED, Condition.DRAINED))
        result = execute(source, CountingDice([1, 10, 10]))
        control = execute(ordinary, CountingDice([1, 10, 10]))
        self.assertEqual(result.recover.resolution.test_result, control.recover.resolution.test_result)
        self.assertEqual(result.state.wizard.magic_state, WizardMagicState(2))
        self.assertIsNone(result.interruption)

    def test_skipped_casting_adds_one_die_and_triggered_pending_keeps_prone(self):
        for pool in (0, 2):
            source = request(pool=pool, active_casting=True)
            result = execute(source, CountingDice([9, 9, 9]))
            self.assertEqual(result.state.wizard.magic_state.miscast_dice, pool + 1)
            self.assertEqual(result.interruption.miscast_pool.dice_added, 1)
            self.assertTrue(result.state.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))
            self.assertEqual(result.state.pending_interruption is not None, pool == 2)

    def test_minion_does_not_touch_active_wizard_magic(self):
        source = request(actor='first', pool=2, active_casting=True)
        result = execute(source, CountingDice([1, 2, 3]))
        self.assertIs(result.state.wizard, source.state.wizard)
        self.assertIsNone(result.interruption)
        self.assertEqual(result.state.roster.participant('wizard'), source.state.roster.participant('wizard'))

    def test_real_timed_wound_and_full_champion_history_are_preserved(self):
        source = wound_request(); result = execute(source, CountingDice([1, 2, 3])); final = result.state
        before = source.state.roster.participant(source.actor_id).state.injury
        after = final.roster.participant(source.actor_id).state.injury
        self.assertEqual(after.wounds, before.wounds)
        self.assertEqual(after.active_wound_effects, before.active_wound_effects)
        self.assertEqual(final.wound_expiries, source.state.wound_expiries)
        self.assertEqual(final.champion_attack.daily_wounds, source.state.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_execution_ids, source.state.champion_attack.consumed_execution_ids)
        self.assertEqual(final.champion_attack.roster, final.roster)
        self.assertEqual(final.champion_attack.round_state, final.round_state)
        self.assertTrue(after.conditions.has(Condition.DRAINED))
        self.assertTrue(after.conditions.has(Condition.PRONE))

    def test_unsafe_prone_is_rejected_even_with_a_complete_escape_route(self):
        source = request(); state = source.state
        state = replace(state, spatial_state=replace(state.spatial_state,
            placements=tuple(replace(p, zone_id='arena') if p.entity_id == source.actor_id else p
                             for p in state.spatial_state.placements)))
        movement = FreeMovementRequest(source.id + ':free-move', state.round_state,
            state.spatial_state, source.actor_id, MovementSpeed.NORMAL,
            state.roster.participant(source.actor_id).state.injury.conditions, ('empty',))
        for route in (None, movement):
            with self.assertRaises(ValueError): replace(source, state=state, movement=route)

    def test_safe_prone_rejects_route_and_false_or_untyped_cause_facts(self):
        source = request()
        movement = FreeMovementRequest(source.id + ':free-move', source.state.round_state,
            source.state.spatial_state, source.actor_id, MovementSpeed.NORMAL,
            source.state.roster.participant(source.actor_id).state.injury.conditions, ('arena',))
        with self.assertRaises(ValueError): replace(source, movement=movement)
        for bad in (False, {}, 'route'):
            with self.assertRaises(TypeError): replace(source, movement=bad)
        for name in ('fastest_route_confirmed', 'underlying_cause_allows_removal'):
            with self.assertRaises(ValueError): replace(source, **{name: False})
            with self.assertRaises(TypeError): replace(source, **{name: 1})

    def test_ongoing_prone_unresolved_wounds_and_restrictions_are_rejected(self):
        source = request(); wound = WoundRecord(1, WoundEntryId.INTERNAL_INJURY, 14, (4, 10), effect_resolved=True)
        for effect in (
            WoundConditionEffect(1, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),
            WoundConditionEffect(1, Condition.BROKEN, WoundEffectDuration.UNTIL_REMOVED),
            WoundConditionEffect(1, Condition.DRAINED, WoundEffectDuration.NEXT_TEST),
            WoundConditionEffect(1, Condition.DRAINED, WoundEffectDuration.PERMANENT),
            WoundRestrictionEffect(1, WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL,
                                   WoundEffectDuration.UNTIL_TREATED),
        ):
            state = with_injury(source.state, source.actor_id, lambda i: replace(
                i, wounds=(wound,), active_wound_effects=(effect,)))
            with self.subTest(effect=effect), self.assertRaises(ValueError): replace(source, state=state)
        state = with_injury(source.state, source.actor_id, lambda i: replace(
            i, wounds=(replace(wound, effect_resolved=False),)))
        with self.assertRaises(ValueError): replace(source, state=state)

    def test_supported_persistent_wound_conditions_survive_recover(self):
        source = request(); wound = WoundRecord(1, WoundEntryId.INTERNAL_INJURY, 14, (4, 10), effect_resolved=True)
        for condition in (Condition.STAGGERED, Condition.DRAINED):
            for duration in (WoundEffectDuration.UNTIL_REMOVED, WoundEffectDuration.UNTIL_TREATED,
                             WoundEffectDuration.UNTIL_HEALED):
                effect = WoundConditionEffect(1, condition, duration)
                state = with_injury(source.state, source.actor_id, lambda i: replace(
                    i, wounds=(wound,), active_wound_effects=(effect,)))
                result = execute(replace(source, state=state), CountingDice([1, 2, 3]))
                self.assertEqual(result.state.roster.participant(source.actor_id).state.injury.active_wound_effects, (effect,))
                self.assertTrue(result.state.roster.participant(source.actor_id).state.injury.conditions.has(condition))

    def test_untracked_early_overdue_and_excluded_expiry_are_rejected(self):
        source = wound_request(); state = source.state
        with self.assertRaises(ValueError): replace(source, state=replace(state, wound_expiries=()))
        for alternate in (wounded(completed=True), wounded(excluded=True)):
            with self.assertRaises(ValueError):
                replace(source, state=replace(state, wound_expiries=alternate.wound_expiries))
        combat = replace(state.round_state, round_number=state.round_state.round_number + 1)
        overdue = replace(state, round_state=combat,
            champion_attack=replace(state.champion_attack, round_state=combat),
            spatial_state=replace(state.spatial_state, round_number=combat.round_number))
        with self.assertRaises(ValueError): replace(source, state=overdue)
        source = request()
        excluded = with_round(source.state, replace(source.state.round_state, excluded_turn_entity_ids=('first',)))
        with self.assertRaises(ValueError): replace(source, state=excluded)

    def test_all_pending_families_block_before_action(self):
        source = request(); _, raw = casting_pending(); prepared = roll_request(raw).state
        rolled = roll_npc_roster_miscast(roll_request(raw), CountingDice([7, 7, 7])).state
        attack_source = incoming_attack()
        attack = execute_npc_champion_attack(attack_source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 4)))
        champion = NpcRosterChampionAttackResult(attack_source, attack).state
        minion = execute_npc_roster_minion_attack(minion_request(), SequenceRandom((1, 2, 3, 10, 10, 10))).state
        for state in (raw, prepared, rolled, interruption_pending(), movement_pending()[2], champion, minion):
            with self.subTest(state=state.round_state.active_turn.actor_id), self.assertRaisesRegex(ValueError, 'pending|Miscast'):
                replace(source, state=state)

    def test_wrong_actor_declaration_and_already_executed_slot_are_rejected(self):
        source = request()
        with self.assertRaises(ValueError): replace(source, actor_id='first')
        turn = source.state.round_state.active_turn
        slot = replace(turn.action_slots[0], declaration=CombatActionDeclaration(CombatActionKind.ATTACK))
        with self.assertRaises(ValueError):
            replace(source, state=with_round(source.state, replace(source.state.round_state,
                active_turn=replace(turn, action_slots=(slot,)))))
        result = execute(source, CountingDice([10] * 3))
        with self.assertRaises(ValueError): replace(source, state=result.state)

    def test_standard_recover_result_cannot_replace_alternative_result(self):
        source = request(); result = execute(source, CountingDice([1, 2, 3]))
        standard = replace(source.recover_request, mode=RecoverMode.STANDARD,
                           choice=RecoverStandardChoice(source.state.wizard.magic_state))
        standard_result = execute_recover_action(standard, CountingDice([]))
        with self.assertRaisesRegex(ValueError, 'complete Broken request'):
            replace(result, recover=standard_result)
        with self.assertRaises(ValueError):
            replace(result, source=replace(source, willpower_profile=InlineProfile(3, 4)))

    def test_apply_rejects_replay_and_unaffected_source_changes_without_reexecution(self):
        source = request(); result = execute(source, CountingDice([1, 2, 3]))
        with self.assertRaises(ValueError): apply(result.state, result)
        changed = with_injury(source.state, 'friend', lambda i: replace(
            i, conditions=i.conditions.with_condition(Condition.STAGGERED)))
        with self.assertRaises(ValueError): apply(changed, result)
        with patch('towr.engine.npc_broken_recover.execute_recover_action', side_effect=AssertionError('no replay')):
            self.assertEqual(apply(deepcopy(source.state), deepcopy(result)), result.state)
            self.assertEqual(replace(result), result)

    def test_typed_frozen_slotted_requests_and_results_roundtrip(self):
        source = request(); result = execute(source, CountingDice([1, 2, 3]))
        for value, attribute in ((source, 'actor_id'), (result, 'recover')):
            self.assertFalse(hasattr(value, '__dict__'))
            self.assertEqual(deepcopy(value), value)
            self.assertEqual(pickle.loads(pickle.dumps(value)), value)
            with self.assertRaises(FrozenInstanceError): setattr(value, attribute, None)
        for bad in (None, True, {}):
            with self.assertRaises(TypeError): execute(bad, CountingDice([]))
            with self.assertRaises(TypeError): replace(source, state=bad)
            with self.assertRaises(TypeError): replace(result, source=bad)
            with self.assertRaises(TypeError): replace(result, recover=bad)
            with self.assertRaises(TypeError): apply(source.state, bad)

    def test_rng_failure_has_no_partial_mutation_and_success_preserves_global_rng(self):
        source = request(used=True); before = deepcopy(source); rng_state = random.getstate()
        failure = RuntimeError('test RNG failure'); rng = CountingDice([])
        with patch.object(rng, 'randint', side_effect=failure):
            with self.assertRaises(RuntimeError) as caught: execute(source, rng)
        self.assertIs(caught.exception, failure)
        self.assertEqual(source, before)
        execute(source, CountingDice([1, 2, 3]))
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), rng_state)
