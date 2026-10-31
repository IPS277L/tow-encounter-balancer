"""ADR-0046 source-bound self-stand; no runner policy or new action."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from tests.unit.test_m8_npc_roster_minion_attack import changed_roster, request as minion_request
from tests.unit.test_m8_npc_roster_turn import ATTACK, CAST
from tests.unit.test_m8_npc_roster_miscast_preparation import casting_pending, interruption_pending
from tests.unit.test_m8_npc_roster_miscast_roll import request as roll_request
from tests.unit.test_m8_npc_roster_casting_completion import begin as movement_pending
from tests.unit.test_m8_npc_wound_turn_end import wounded
from tests.integration.test_m8_champion_casting_handoff import incoming_attack
from tests.integration.test_m8_npc_broken_recover import wounded_broken_wizard
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundConditionEffect, WoundEffectDuration, WoundEntryId, WoundRecord,
    WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import ProneRemovalTargetKind
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_prone_models import (
    NpcRosterProneStandRequest as Request, NpcRosterProneStandResult as Result,
)
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
from towr.domain.turn_models import ActionSlotGrant, CombatActionSlot
from towr.rules.free_movement_resolution import resolve_free_move_prone_removal
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_miscast_resolution import roll_npc_roster_miscast
from towr.rules.npc_roster_prone_resolution import (
    stand_npc_roster_prone as stand, apply_npc_roster_prone_stand as apply,
)
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn


def with_injury(state, actor_id, transform):
    """Author one injury fact, retaining both child roster references."""
    return changed_roster(state, lambda p: replace(p, state=replace(p.state,
        injury=transform(p.state.injury))) if p.state.actor_id == actor_id else p)


def with_round(state, combat):
    return replace(state, round_state=combat, champion_attack=None if state.champion_attack is None
                   else replace(state.champion_attack, round_state=combat))


def ready(actor_id='wizard'):
    """Authored Prone fact plus a real bound start/standard reservation."""
    state = admitted().initial_runtime_state
    state = with_injury(state, actor_id, lambda i: replace(i,
        conditions=i.conditions.with_condition(Condition.PRONE)))
    if state.roster.participant(actor_id).state.side is not state.round_state.next_side:
        state = with_round(state, replace(state.round_state, side_order=tuple(reversed(state.round_state.side_order))))
    return start_npc_roster_turn(NpcRosterTurnStartRequest(
        'start:' + actor_id, state, actor_id, CAST if actor_id == 'wizard' else ATTACK)).state


def request(state=None, actor_id='wizard'):
    return Request('stand:' + actor_id, ready(actor_id) if state is None else state, actor_id, False, True)


class NpcRosterProneStandTests(unittest.TestCase):
    def test_champion_and_minion_remove_only_prone_and_spend_one_free_move(self):
        for actor in ('wizard', 'ally', 'enemy'):
            source = request(actor_id=actor)
            result = stand(source)
            final = apply(source.state, result)
            self.assertIs(result.source, source)
            self.assertEqual(final.spatial_state.free_move_used_entity_ids, (actor,))
            self.assertFalse(final.roster.participant(actor).state.injury.conditions.has(Condition.PRONE))
            self.assertEqual(final.round_state, source.state.round_state)
            self.assertFalse(final.round_state.active_turn.action_slots[0].executed)
            self.assertEqual(final.consumed_execution_ids, ())

    def test_k1_request_binds_complete_current_snapshots_and_self_metadata(self):
        source = request(); low = source.stand_request
        self.assertEqual((low.id, low.actor_id, low.target_id), (source.id, source.actor_id, source.actor_id))
        self.assertIs(low.target_kind, ProneRemovalTargetKind.SELF)
        self.assertIsNone(low.target_in_close_range)
        self.assertIs(low.actor_has_enemy_in_close_range, False)
        self.assertEqual(low.round_state, source.state.round_state)
        self.assertEqual(low.state, source.state.spatial_state)
        self.assertEqual(low.target_conditions, source.state.roster.participant(source.actor_id).state.injury.conditions)
        self.assertEqual(low.rule_id, 'RULE-COMBAT-014:free-move-prone-removal')

    def test_projection_preserves_every_other_owner_field_and_unrelated_conditions(self):
        state = ready()
        state = with_injury(state, 'wizard', lambda i: replace(i, conditions=i.conditions
            .with_condition(Condition.STAGGERED).with_condition(Condition.DRAINED).with_condition(Condition.BROKEN)))
        state = replace(state, consumed_execution_ids=('earlier',),
            wizard=replace(state.wizard, magic_state=WizardMagicState(1)),
            spatial_state=replace(state.spatial_state, gave_ground_entity_ids=('enemy',),
                free_move_used_entity_ids=('ally',), difficult_terrain_tested_entity_ids=('enemy',)))
        before = deepcopy(state); final = stand(request(state)).state
        for f in fields(state):
            if f.name not in ('roster', 'spatial_state', 'champion_attack', 'minion_attack'):
                self.assertEqual(getattr(final, f.name), getattr(state, f.name), f.name)
        for old, new in ((state.champion_attack, final.champion_attack), (state.minion_attack, final.minion_attack)):
            self.assertEqual(new.roster, final.roster)
            self.assertEqual(replace(new, roster=old.roster), old)
        self.assertEqual(replace(final.spatial_state, free_move_used_entity_ids=('ally',)), state.spatial_state)
        self.assertEqual(final.spatial_state.free_move_used_entity_ids, ('ally', 'wizard'))
        for p in state.roster.participants:
            actual = final.roster.participant(p.state.actor_id)
            if p.state.actor_id != 'wizard': self.assertEqual(actual, p)
            else:
                self.assertEqual(actual.state.injury.conditions.conditions,
                                 p.state.injury.conditions.conditions - {Condition.PRONE})
                self.assertEqual(replace(actual.state.injury, conditions=p.state.injury.conditions), p.state.injury)
        self.assertEqual(state, before)

    def test_optional_child_owners_are_not_created(self):
        state = replace(ready(), champion_attack=None, minion_attack=None)
        final = stand(request(state)).state
        self.assertIsNone(final.champion_attack)
        self.assertIsNone(final.minion_attack)

    def test_required_strict_flags_and_identifiers(self):
        source = request()
        for name in ('actor_has_enemy_in_close_range', 'underlying_cause_allows_removal'):
            for value in (None, 0, 1, 'false', object()):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError): replace(source, **{name: value})
        for changes in ({'actor_has_enemy_in_close_range': True}, {'underlying_cause_allows_removal': False}):
            with self.assertRaises(ValueError): replace(source, **changes)
        for name in ('id', 'actor_id'):
            for value in (None, 1, False):
                with self.assertRaises(TypeError): replace(source, **{name: value})
            for value in ('', '  '):
                with self.assertRaises(ValueError): replace(source, **{name: value})
        for omitted in fields(source):
            with self.assertRaises(TypeError):
                Request(**{f.name: getattr(source, f.name) for f in fields(source) if f != omitted})

    def test_wrong_actor_idle_and_empty_or_extra_slots_rejected(self):
        source = request(); state = source.state; turn = state.round_state.active_turn
        with self.assertRaises(ValueError): replace(source, actor_id='ally')
        for active in (None, replace(turn, action_slots=()), replace(turn, action_slots=(
                *turn.action_slots, CombatActionSlot(2, ATTACK, ActionSlotGrant.ABILITY, 'authored:extra')))):
            with self.assertRaises(ValueError): request(with_round(state, replace(state.round_state, active_turn=active)))

    def test_executed_slot_is_rejected_even_without_pending(self):
        result = execute_npc_roster_minion_attack(minion_request(), SequenceRandom((10,) * 6))
        state = with_injury(result.state, 'ally', lambda i: replace(i, conditions=i.conditions.with_condition(Condition.PRONE)))
        with self.assertRaisesRegex(ValueError, 'unexecuted standard'): request(state, 'ally')

    def test_no_prone_used_resource_dead_and_unsupported_conditions_rejected(self):
        for actor in ('wizard', 'ally'):
            state = ready(actor)
            invalid = (with_injury(state, actor, lambda i: replace(i, conditions=i.conditions.without_condition(Condition.PRONE))),
                replace(state, spatial_state=replace(state.spatial_state, free_move_used_entity_ids=(actor,))),
                with_injury(state, actor, lambda i: replace(i, **({'dead': True} if actor == 'wizard'
                            else {'defeated': True, 'wounds': 1}))),
                with_injury(state, actor, lambda i: replace(i, conditions=i.conditions.with_condition(Condition.DEFENCELESS))))
            for bad in invalid:
                with self.subTest(actor=actor, bad=bad), self.assertRaises(ValueError): request(bad, actor)

    def test_all_actual_mandatory_pending_families_block_stand(self):
        _, raw = casting_pending(); prepared = roll_request(raw).state
        rolled = roll_npc_roster_miscast(roll_request(raw), Dice((7, 7, 7))).state
        attack_source = incoming_attack()
        attack = execute_npc_champion_attack(attack_source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 4)))
        champion = NpcRosterChampionAttackResult(attack_source, attack).state
        minion = execute_npc_roster_minion_attack(minion_request(), SequenceRandom((1, 2, 3, 10, 10, 10))).state
        for state in (raw, prepared, rolled, interruption_pending(), movement_pending()[2], champion, minion):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'pending|Miscast'):
                Request('stand', state, state.round_state.active_turn.actor_id, False, True)

    def test_unresolved_wounds_and_known_ongoing_causes_cannot_be_overridden(self):
        wound = WoundRecord(1, WoundEntryId.INTERNAL_INJURY, 14, (4, 10), effect_resolved=True)
        effects = (WoundConditionEffect(1, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),
            WoundConditionEffect(1, Condition.BROKEN, WoundEffectDuration.UNTIL_TREATED),
            WoundRestrictionEffect(1, WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL, WoundEffectDuration.UNTIL_TREATED),
            WoundRestrictionEffect(1, WoundRestriction.SPEED_IS_SLOW, WoundEffectDuration.UNTIL_HEALED),
            WoundConditionEffect(1, Condition.DRAINED, WoundEffectDuration.NEXT_TEST))
        for effect in effects:
            state = with_injury(ready(), 'wizard', lambda i: replace(i, wounds=(wound,), active_wound_effects=(effect,),
                conditions=i.conditions.with_condition(effect.condition) if isinstance(effect, WoundConditionEffect) else i.conditions))
            with self.subTest(effect=effect), self.assertRaisesRegex(ValueError, 'ongoing Wound'): request(state)
        state = with_injury(ready(), 'wizard', lambda i: replace(i, wounds=(replace(wound, effect_resolved=False),)))
        with self.assertRaisesRegex(ValueError, 'ongoing Wound'): request(state)

    def test_supported_independent_wound_sources_are_retained_not_removed(self):
        for condition in (Condition.STAGGERED, Condition.DRAINED):
            wound = WoundRecord(1, WoundEntryId.INTERNAL_INJURY, 14, (4, 10), effect_resolved=True)
            effect = WoundConditionEffect(1, condition, WoundEffectDuration.UNTIL_HEALED)
            state = with_injury(ready(), 'wizard', lambda i: replace(i, wounds=(wound,), active_wound_effects=(effect,),
                conditions=i.conditions.with_condition(condition)))
            result = stand(request(state)).state.roster.participant('wizard').state.injury
            self.assertEqual(result.wounds, (wound,)); self.assertEqual(result.active_wound_effects, (effect,))
            self.assertTrue(result.conditions.has(condition))
            missing = with_injury(state, 'wizard', lambda i: replace(i, conditions=i.conditions.without_condition(condition)))
            with self.assertRaises(ValueError): request(missing)

    def test_real_expiry_is_retained_and_untracked_or_overdue_clock_rejected(self):
        _, _, state = wounded_broken_wizard(1); actor = state.wizard.actor_id
        state = with_injury(state, actor, lambda i: replace(i, conditions=i.conditions.with_condition(Condition.PRONE)))
        final = stand(request(state, actor)).state
        self.assertEqual(final.wound_expiries, state.wound_expiries)
        self.assertEqual(final.wound_turn_end_receipts, state.wound_turn_end_receipts)
        self.assertEqual(final.champion_attack.daily_wounds, state.champion_attack.daily_wounds)
        with self.assertRaisesRegex(ValueError, 'chronology'): request(replace(state, wound_expiries=()), actor)
        combat = replace(state.round_state, round_number=state.round_state.round_number + 1)
        overdue = replace(state, round_state=combat,
            spatial_state=replace(state.spatial_state, round_number=combat.round_number),
            champion_attack=replace(state.champion_attack, round_state=combat))
        with self.assertRaisesRegex(ValueError, 'expiry'): request(overdue, actor)

    def test_metadata_substitutions_and_foreign_complete_k1_sources_rejected(self):
        source = request(); actual = stand(source).stand
        for changes in ({'request_id': 'foreign'}, {'rule_id': 'foreign:rule'},
                        {'applied_rule_ids': ('foreign:rule',)}, {'applied_rule_ids': (*actual.applied_rule_ids, 'extra')}):
            with self.assertRaises(ValueError): Result(source, replace(actual, **changes))
        foreign = (replace(source.stand_request, id='another'),
                   replace(source.stand_request, target_conditions=source.stand_request.target_conditions.with_condition(Condition.STAGGERED)),
                   replace(source.stand_request, state=replace(source.state.spatial_state, gave_ground_entity_ids=('enemy',))))
        for low in foreign:
            with self.assertRaises(ValueError): Result(source, resolve_free_move_prone_removal(low))
        with self.assertRaises(ValueError): Result(source, stand(request(actor_id='ally')).stand)

    def test_future_target_deadline_and_excluded_source_are_rejected(self):
        _, _, state = wounded_broken_wizard(1); actor = state.wizard.actor_id
        state = with_injury(state, actor, lambda i: replace(i, conditions=i.conditions.with_condition(Condition.PRONE)))
        for other in (wounded(completed=True), wounded(excluded=True)):
            current = replace(state, wound_expiries=other.wound_expiries)
            with self.assertRaisesRegex(ValueError, 'chronology'): request(current, actor)

    def test_live_excluded_actor_is_not_silently_accepted(self):
        state = ready()
        invalid = with_round(state, replace(state.round_state, excluded_turn_entity_ids=('enemy',)))
        with self.assertRaisesRegex(ValueError, 'live excluded'): request(invalid)

    def test_apply_rejects_replay_and_whole_owner_changes_not_just_actor(self):
        source = request(); result = stand(source)
        alternatives = (result.state, replace(source.state, consumed_execution_ids=('foreign',)),
            replace(source.state, wizard=replace(source.state.wizard, magic_state=WizardMagicState(1))),
            with_injury(source.state, 'enemy', lambda i: replace(i, conditions=i.conditions.with_condition(Condition.STAGGERED))))
        for state in alternatives:
            with self.assertRaisesRegex(ValueError, 'stale full source'): apply(state, result)
        with self.assertRaises(ValueError): replace(source, id='new', state=result.state)
        prone_again = with_injury(result.state, 'wizard', lambda i: replace(i, conditions=i.conditions.with_condition(Condition.PRONE)))
        with self.assertRaisesRegex(ValueError, 'unused free movement'): replace(source, id='new', state=prone_again)

    def test_one_reducer_no_rng_or_action_and_no_reexecution_on_validation_or_apply(self):
        source = request(); before = deepcopy(source); random_state = getstate()
        with (patch('towr.rules.npc_roster_prone_resolution.resolve_free_move_prone_removal', wraps=resolve_free_move_prone_removal) as reducer,
              patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test')),
              patch('random.Random', side_effect=AssertionError('no RNG'))):
            result = stand(source)
            reducer.assert_called_once_with(source.stand_request)
        with patch('towr.rules.npc_roster_prone_resolution.resolve_free_move_prone_removal', side_effect=AssertionError('no rerun')):
            self.assertEqual(Result(source, result.stand), result)
            self.assertEqual(apply(source.state, result), result.state)
        self.assertEqual(source, before); self.assertEqual(getstate(), random_state)

    def test_failure_propagates_once_without_partial_owner_or_retry(self):
        source = request(); before = deepcopy(source); failure = RuntimeError('stand failure')
        with patch('towr.rules.npc_roster_prone_resolution.resolve_free_move_prone_removal', side_effect=failure) as reducer:
            with self.assertRaises(RuntimeError) as caught: stand(source)
            self.assertIs(caught.exception, failure); reducer.assert_called_once()
        self.assertEqual(source, before)

    def test_typed_boundaries_and_frozen_slotted_copy_pickle(self):
        source = request(); result = stand(source)
        for bad in (None, {}, True, source.stand_request):
            with self.assertRaises(TypeError): stand(bad)
            with self.assertRaises(TypeError): replace(source, state=bad)
            with self.assertRaises(TypeError): Result(bad, result.stand)
            with self.assertRaises(TypeError): Result(source, bad)
            with self.assertRaises(TypeError): apply(bad, result)
            with self.assertRaises(TypeError): apply(source.state, bad)
        for value, attribute in ((source, 'actor_id'), (result, 'stand')):
            self.assertFalse(hasattr(value, '__dict__'))
            self.assertEqual(deepcopy(value), value)
            self.assertEqual(pickle.loads(pickle.dumps(value)), value)
            self.assertEqual(replace(value), value)
            with self.assertRaises(FrozenInstanceError): setattr(value, attribute, None)
