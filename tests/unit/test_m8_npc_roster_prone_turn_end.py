"""ADR-0046: full-owner Prone end, preserving Conditions and expiry clocks."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.integration.test_m8_champion_casting_handoff import incoming_attack
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_npc_roster_casting_completion import begin as movement_pending
from tests.unit.test_m8_npc_roster_minion_attack import request as minion_request
from tests.unit.test_m8_npc_roster_miscast_preparation import casting_pending, interruption_pending
from tests.unit.test_m8_npc_roster_miscast_roll import request as roll_request
from tests.unit.test_m8_npc_roster_prone_stand import with_injury, with_round
from tests.unit.test_m8_npc_roster_turn import ATTACK
from tests.unit.test_m8_npc_roster_unnatural_wind import request as wind_request
from tests.unit.test_m8_npc_wound_turn_end import ready as wounded_ready, wounded
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundConditionEffect, WoundConditionSourceSnapshot, WoundEffectDuration,
    WoundEntryId, WoundRecord, WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_prone_models import (
    NpcRosterProneTurnEndRequest as Request, NpcRosterProneTurnEndResult as Result,
)
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.npc_wound_turn_models import NpcWoundTurnEndReceipt
from towr.domain.turn_models import ActionSlotGrant, CombatActionSlot
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_miscast_resolution import roll_npc_roster_miscast, resolve_npc_roster_unnatural_wind
from towr.rules.npc_roster_prone_resolution import (
    end_npc_roster_prone_turn as end, apply_npc_roster_prone_turn_end as apply,
)
from towr.rules.turn_resolution import end_combat_turn


def ready(actor_id='wizard'):
    if actor_id == 'wizard':
        return resolve_npc_roster_unnatural_wind(wind_request()).state
    result = execute_npc_roster_minion_attack(minion_request(), SequenceRandom((10,) * 6))
    return with_injury(result.state, actor_id, lambda i: replace(
        i, conditions=i.conditions.with_condition(Condition.PRONE)))


def request(state=None, actor_id='wizard', sources=()):
    return Request('prone:end:' + actor_id, ready(actor_id) if state is None else state,
                   actor_id, sources)


def wound_request(*, other=False):
    state = wounded_ready()
    actor_id = state.wizard.actor_id
    state = with_injury(state, actor_id, lambda i: replace(
        i, conditions=i.conditions.with_condition(Condition.PRONE)))
    return request(state, actor_id, (WoundConditionSourceSnapshot(Condition.DRAINED, other),))


class NpcRosterProneTurnEndTests(unittest.TestCase):
    def test_actual_wind_prone_survives_one_complete_turn_end(self):
        source = request(); final = end(source).state
        self.assertIsNone(final.round_state.active_turn)
        self.assertEqual(final.round_state.completed_turn_entity_ids,
                         (*source.state.round_state.completed_turn_entity_ids, source.actor_id))
        self.assertEqual(final.roster, source.state.roster)
        self.assertEqual(final.wizard.magic_state.miscast_dice, 0)
        self.assertTrue(final.roster.participant(source.actor_id).state.injury.conditions.has(Condition.PRONE))
        self.assertEqual(final.wound_turn_end_receipts[-1], NpcWoundTurnEndReceipt(
            source.id, source.actor_id, source.state.round_state.round_number, ()))

    def test_minion_executed_attack_can_end_without_changing_its_prone(self):
        source = request(actor_id='ally'); result = end(source)
        self.assertEqual(result.state.roster, source.state.roster)
        self.assertEqual(result.state.wizard, source.state.wizard)
        self.assertIn('ally', result.state.round_state.completed_turn_entity_ids)
        self.assertTrue(result.state.roster.participant('ally').state.injury.conditions.has(Condition.PRONE))

    def test_full_owner_projection_preserves_history_spatial_magic_and_other_actors(self):
        source = request(); old = source.state; final = end(source).state
        changed = {'round_state', 'champion_attack', 'minion_attack', 'wound_turn_end_receipts'}
        for field in fields(old):
            if field.name not in changed:
                self.assertEqual(getattr(final, field.name), getattr(old, field.name), field.name)
        self.assertEqual(final.champion_attack.roster, final.roster)
        self.assertEqual(final.champion_attack.round_state, final.round_state)
        self.assertEqual(replace(final.champion_attack, round_state=old.round_state), old.champion_attack)
        self.assertEqual(final.minion_attack, old.minion_attack)
        self.assertEqual(final.consumed_execution_ids, old.consumed_execution_ids)
        self.assertEqual(final.spatial_state.free_move_used_entity_ids, old.spatial_state.free_move_used_entity_ids)

    def test_optional_owners_are_not_created(self):
        source = request(replace(ready(), champion_attack=None, minion_attack=None))
        final = end(source).state
        self.assertIsNone(final.champion_attack)
        self.assertIsNone(final.minion_attack)

    def test_real_stomach_blow_expiry_removes_drained_but_not_prone_broken_or_wound(self):
        source = wound_request(); old = source.state; final = end(source).state
        before = old.roster.participant(source.actor_id).state.injury
        after = final.roster.participant(source.actor_id).state.injury
        self.assertEqual(after.wounds, before.wounds)
        self.assertFalse(after.conditions.has(Condition.DRAINED))
        self.assertTrue(after.conditions.has(Condition.PRONE))
        self.assertTrue(after.conditions.has(Condition.BROKEN))
        self.assertEqual(after.active_wound_effects, ())
        self.assertEqual(final.wound_expiries, ())
        self.assertEqual(final.wound_turn_end_receipts[-1].expired_attack_ids,
                         tuple(e.attack_id for e in source.expiries))
        self.assertEqual(final.champion_attack.daily_wounds, old.champion_attack.daily_wounds)

    def test_independent_external_and_remaining_wound_drained_sources_are_preserved(self):
        source = wound_request(other=True)
        self.assertTrue(end(source).state.roster.participant(source.actor_id).state.injury.conditions.has(Condition.DRAINED))
        extra = WoundConditionEffect(2, Condition.DRAINED, WoundEffectDuration.UNTIL_HEALED)
        state = with_injury(source.state, source.actor_id, lambda i: replace(i,
            wounds=(*i.wounds, replace(i.wounds[0], sequence=2, entry_id=WoundEntryId.INTERNAL_INJURY,
                                      table_total=14, roll_values=(4, 10))),
            active_wound_effects=(*i.active_wound_effects, extra)))
        with self.assertRaisesRegex(ValueError, 'cannot be denied'):
            replace(source, state=state, condition_sources=(WoundConditionSourceSnapshot(Condition.DRAINED, False),))
        injury = end(replace(source, state=state)).state.roster.participant(source.actor_id).state.injury
        self.assertEqual(injury.active_wound_effects, (extra,))
        self.assertTrue(injury.conditions.has(Condition.DRAINED))
        self.assertTrue(injury.conditions.has(Condition.PRONE))

    def test_other_actor_end_does_not_expire_wizard_effect(self):
        state = wounded(); actor = state.round_state.active_turn.actor_id
        state = with_injury(state, actor, lambda i: replace(i, conditions=i.conditions.with_condition(Condition.PRONE)))
        source = request(state, actor); final = end(source).state
        self.assertEqual(source.expiries, ())
        self.assertEqual(final.wound_expiries, state.wound_expiries)
        self.assertEqual(final.roster, state.roster)

    def test_sources_are_exact_ordered_and_typed(self):
        source = wound_request()
        self.assertEqual(replace(source, condition_sources=list(source.condition_sources)), source)
        for sources in ((), (*source.condition_sources, *source.condition_sources),
                        (WoundConditionSourceSnapshot(Condition.PRONE, False),)):
            with self.assertRaises(ValueError): replace(source, condition_sources=sources)
        for sources in (None, set(source.condition_sources), (False,)):
            with self.assertRaises(TypeError): replace(source, condition_sources=sources)

    def test_untracked_early_overdue_and_excluded_expiries_are_rejected(self):
        source = wound_request(); state = source.state
        with self.assertRaises(ValueError): replace(source, state=replace(state, wound_expiries=()))
        for other in (wounded(completed=True), wounded(excluded=True)):
            with self.assertRaises(ValueError): replace(source, state=replace(state, wound_expiries=other.wound_expiries))
        turn = state.round_state.active_turn; slot = turn.action_slots[0]
        combat = replace(state.round_state, round_number=2, active_turn=replace(turn,
            action_slots=(replace(slot, execution=replace(slot.execution, round_number=2)),)))
        overdue = replace(state, round_state=combat,
            champion_attack=replace(state.champion_attack, round_state=combat),
            spatial_state=replace(state.spatial_state, round_number=2))
        with self.assertRaises(ValueError): replace(source, state=overdue)

    def test_all_actual_mandatory_pending_families_block_end(self):
        _, raw = casting_pending(); prepared = roll_request(raw).state
        rolled = roll_npc_roster_miscast(roll_request(raw), Dice((7, 7, 7))).state
        attack_source = incoming_attack()
        attack = execute_npc_champion_attack(attack_source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 4)))
        champion = NpcRosterChampionAttackResult(attack_source, attack).state
        minion = execute_npc_roster_minion_attack(minion_request(), SequenceRandom((1, 2, 3, 10, 10, 10))).state
        for state in (raw, prepared, rolled, interruption_pending(), movement_pending()[2], champion, minion):
            with self.subTest(pending=state.round_state.active_turn.actor_id), self.assertRaisesRegex(ValueError, 'pending|Miscast'):
                request(state, state.round_state.active_turn.actor_id)

    def test_global_live_exclusion_and_foreign_untracked_clock_block_end(self):
        source = request(); state = source.state
        excluded = with_round(state, replace(state.round_state, excluded_turn_entity_ids=('enemy',)))
        with self.assertRaises(ValueError): replace(source, state=excluded)
        state = wounded(); actor = state.round_state.active_turn.actor_id
        state = with_injury(state, actor, lambda i: replace(i, conditions=i.conditions.with_condition(Condition.PRONE)))
        # The clock belongs to the Wizard, not this Minion's own turn.
        with self.assertRaises(ValueError): request(replace(state, wound_expiries=()), actor)

    def test_prone_is_required_and_dead_or_unsupported_actor_rejected(self):
        for actor in ('wizard', 'ally'):
            source = request(actor_id=actor)
            for transform in (
                lambda i: replace(i, conditions=i.conditions.without_condition(Condition.PRONE)),
                lambda i: replace(i, conditions=i.conditions.with_condition(Condition.ABLAZE)),
                lambda i: replace(i, **({'dead': True} if actor == 'wizard' else {'defeated': True, 'wounds': 1})),
            ):
                with self.subTest(actor=actor), self.assertRaises(ValueError):
                    replace(source, state=with_injury(source.state, actor, transform))

    def test_ongoing_prone_restrictions_unresolved_wounds_and_other_effects_rejected(self):
        source = request(); wound = WoundRecord(1, WoundEntryId.INTERNAL_INJURY, 14, (4, 10), effect_resolved=True)
        effects = (
            WoundConditionEffect(1, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),
            WoundConditionEffect(1, Condition.BROKEN, WoundEffectDuration.UNTIL_TREATED),
            WoundRestrictionEffect(1, WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL, WoundEffectDuration.UNTIL_TREATED),
            WoundConditionEffect(1, Condition.DRAINED, WoundEffectDuration.NEXT_TEST),
        )
        for effect in effects:
            state = with_injury(source.state, source.actor_id, lambda i: replace(i, wounds=(wound,),
                active_wound_effects=(effect,), conditions=i.conditions.with_condition(effect.condition)
                if isinstance(effect, WoundConditionEffect) else i.conditions))
            with self.subTest(effect=effect), self.assertRaises(ValueError): replace(source, state=state)
        state = with_injury(source.state, source.actor_id, lambda i: replace(i, wounds=(replace(wound, effect_resolved=False),)))
        with self.assertRaises(ValueError): replace(source, state=state)

    def test_supported_non_timed_wound_effects_remain_without_upkeep(self):
        source = request(); wound = WoundRecord(1, WoundEntryId.INTERNAL_INJURY, 14, (4, 10), effect_resolved=True)
        for condition in (Condition.STAGGERED, Condition.DRAINED):
            for duration in (WoundEffectDuration.UNTIL_REMOVED, WoundEffectDuration.UNTIL_TREATED,
                             WoundEffectDuration.UNTIL_HEALED):
                effect = WoundConditionEffect(1, condition, duration)
                state = with_injury(source.state, source.actor_id, lambda i: replace(i, wounds=(wound,),
                    active_wound_effects=(effect,), conditions=i.conditions.with_condition(condition)))
                with self.subTest(condition=condition, duration=duration):
                    final = end(replace(source, state=state)).state
                    self.assertEqual(final.roster, state.roster)
                    self.assertTrue(final.roster.participant(source.actor_id).state.injury.conditions.has(Condition.PRONE))
                    missing = with_injury(state, source.actor_id, lambda i: replace(
                        i, conditions=i.conditions.without_condition(condition)))
                    with self.assertRaises(ValueError): replace(source, state=missing)

    def test_active_actor_standard_execution_and_bound_consumption_required(self):
        source = request(); state = source.state; turn = state.round_state.active_turn; slot = turn.action_slots[0]
        with self.assertRaises(ValueError): replace(source, actor_id='ally')
        for active in (None, replace(turn, action_slots=()), replace(turn, action_slots=(replace(slot, execution=None),)),
                       replace(turn, action_slots=(*turn.action_slots, CombatActionSlot(
                           2, ATTACK, ActionSlotGrant.ABILITY, 'extra')))):
            with self.assertRaises(ValueError): replace(source, state=with_round(state, replace(state.round_state, active_turn=active)))
        with self.assertRaises(ValueError): replace(source, state=replace(state, consumed_execution_ids=()))

    def test_old_end_request_still_rejects_actual_prone(self):
        source = request()
        with self.assertRaisesRegex(ValueError, 'unsupported end-turn Condition'):
            NpcWoundTurnEndRequest(source.id, source.state, source.actor_id)

    def test_scheduler_metadata_and_complete_state_substitution_rejected(self):
        source = request(); actual = end(source)
        for changes in ({'request_id': 'foreign'}, {'completed_turn': None}, {'next_side': None},
                        {'round_complete': not actual.turn_end.round_complete},
                        {'round_complete': int(actual.turn_end.round_complete)}, {'applied_rule_ids': ()},
                        {'state': replace(actual.turn_end.state, completed_turn_entity_ids=('enemy',))}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Result(source, replace(actual.turn_end, **changes))
        with self.assertRaises(ValueError): Result(source, end(replace(source, id='foreign')).turn_end)

    def test_replay_changed_full_owner_and_new_id_same_actor_round_are_rejected(self):
        source = request(); result = end(source); final = result.state
        with self.assertRaises(ValueError): apply(final, result)
        with self.assertRaises(ValueError): replace(source, state=final)
        with self.assertRaises(ValueError): replace(source, id='new', state=final)
        for state in (replace(source.state, consumed_execution_ids=(*source.state.consumed_execution_ids, 'foreign')),
                      with_injury(source.state, 'ally', lambda i: replace(i, conditions=i.conditions.with_condition(Condition.STAGGERED)))):
            with self.assertRaises(ValueError): apply(state, result)

    def test_one_scheduler_no_rng_no_reexecution_on_validation_or_apply(self):
        source = request(); before = deepcopy(source); random_state = getstate()
        with (patch('towr.rules.npc_roster_prone_resolution.end_combat_turn', wraps=end_combat_turn) as scheduler,
              patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test')),
              patch('random.Random', side_effect=AssertionError('no RNG'))):
            result = end(source)
            scheduler.assert_called_once()
        with patch('towr.rules.npc_roster_prone_resolution.end_combat_turn', side_effect=AssertionError('no replay')):
            self.assertEqual(Result(source, result.turn_end), result)
            self.assertEqual(apply(source.state, result), result.state)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), random_state)

    def test_scheduler_exception_propagates_without_retry_or_partial_mutation(self):
        source = request(); before = deepcopy(source); failure = RuntimeError('scheduler failed')
        with patch('towr.rules.npc_roster_prone_resolution.end_combat_turn', side_effect=failure) as scheduler:
            with self.assertRaises(RuntimeError) as caught: end(source)
            self.assertIs(caught.exception, failure)
            scheduler.assert_called_once()
        self.assertEqual(source, before)

    def test_typed_boundaries_and_frozen_slotted_copy_pickle(self):
        source = request(); result = end(source)
        for bad in (None, {}, True):
            with self.assertRaises(TypeError): end(bad)
            with self.assertRaises(TypeError): replace(source, state=bad)
            with self.assertRaises(TypeError): Result(bad, result.turn_end)
            with self.assertRaises(TypeError): Result(source, bad)
            with self.assertRaises(TypeError): apply(bad, result)
            with self.assertRaises(TypeError): apply(source.state, bad)
        for name in ('id', 'actor_id'):
            for value in (None, 1, False):
                with self.assertRaises(TypeError): replace(source, **{name: value})
            for value in ('', '  '):
                with self.assertRaises(ValueError): replace(source, **{name: value})
        for value, attribute in ((source, 'actor_id'), (result, 'turn_end')):
            self.assertFalse(hasattr(value, '__dict__'))
            self.assertEqual(deepcopy(value), value)
            self.assertEqual(pickle.loads(pickle.dumps(value)), value)
            self.assertEqual(replace(value), value)
            with self.assertRaises(FrozenInstanceError): setattr(value, attribute, None)
