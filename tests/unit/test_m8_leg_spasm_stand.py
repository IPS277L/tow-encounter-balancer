"""ADR-0048: exact Leg Spasm source, one free move, retained terrain/history."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.integration.test_m8_champion_casting_handoff import incoming_attack
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from tests.unit.test_m8_npc_roster_casting_completion import begin as movement_pending
from tests.unit.test_m8_npc_roster_minion_attack import request as minion_request
from tests.unit.test_m8_npc_roster_miscast_preparation import casting_pending, interruption_pending
from tests.unit.test_m8_npc_roster_miscast_roll import request as roll_request
from tests.unit.test_m8_npc_roster_prone_stand import ready, with_injury, with_round
from tests.unit.test_m8_npc_roster_turn import ATTACK
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundConditionEffect, WoundEffectDuration, WoundEntryId, WoundRecord,
    WoundRecordOrigin, WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import ProneRemovalTargetKind
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_leg_spasm_models import (
    NpcRosterLegSpasmStandRequest as Request,
    NpcRosterLegSpasmStandResult as Result,
)
from towr.domain.npc_roster_prone_models import NpcRosterProneStandRequest
from towr.domain.turn_models import ActionExecutionReceipt, ActionSlotGrant, CombatActionSlot, CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.free_movement_resolution import resolve_free_move_prone_removal
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_leg_spasm_resolution import (
    stand_npc_roster_leg_spasm as stand,
    apply_npc_roster_leg_spasm_stand as apply,
)
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_miscast_resolution import roll_npc_roster_miscast


def prone(sequence):
    return WoundConditionEffect(sequence, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED)


def terrain(sequence):
    return WoundRestrictionEffect(sequence, WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
                                  WoundEffectDuration.UNTIL_TREATED)


def leg(sequence=1, *, fixed=False):
    return WoundRecord(sequence, WoundEntryId.LEG_SPASM, 9, () if fixed else (9,),
        effect_resolved=True,
        origin=WoundRecordOrigin.FIXED_ENTRY if fixed else WoundRecordOrigin.TABLE_ROLL)


def superficial(sequence=1):
    return WoundRecord(sequence, WoundEntryId.SUPERFICIAL_INJURY, 3, (3,), effect_resolved=True)


def source_state(*, wounds=None, effects=None):
    """Authored canonical injury; chronology/turn/child owners use existing fixtures."""
    return with_injury(ready(), 'wizard', lambda i: replace(i,
        wounds=(leg(),) if wounds is None else wounds,
        active_wound_effects=(prone(1), terrain(1)) if effects is None else effects))


def request(state=None):
    return Request('leg-spasm:stand', source_state() if state is None else state,
                   'wizard', False, True)


def actual_state():
    source = admitted(wizard_side=CombatSide.OPPOSITION)
    dice = Dice((1, 2, 3, 10, 10, 10, 9))
    result = run_npc_magic_scenario(source, dice)
    dice.exhausted()
    assert result.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    assert result.current.roster.participant('wizard').state.injury.wounds[-1].entry_id is WoundEntryId.LEG_SPASM
    return result.current


class LegSpasmStandTests(unittest.TestCase):
    def test_real_registered_wound_preserves_receipts_rolls_and_both_child_owners(self):
        state = actual_state()
        before = deepcopy(state)
        result = stand(request(state))
        final = apply(state, result)
        injury = final.roster.participant('wizard').state.injury
        original = state.roster.participant('wizard').state.injury
        self.assertFalse(injury.conditions.has(Condition.PRONE))
        self.assertEqual(injury.active_wound_effects, (terrain(1),))
        self.assertEqual(injury.wounds, original.wounds)
        self.assertEqual(len(state.champion_attack.daily_wounds.receipts), 1)
        self.assertEqual(len(state.champion_attack.consumed_wound_roll_ids), 1)
        self.assertIs(result.source.state, state)
        self.assertEqual(result.removed_effects, (prone(1),))
        self.assertEqual(state, before)
        for old, new in ((state.champion_attack, final.champion_attack),
                         (state.minion_attack, final.minion_attack)):
            self.assertIsNotNone(old)
            self.assertEqual(new.roster, final.roster)
            self.assertEqual(replace(new, roster=old.roster), old)

    def test_projection_changes_only_proven_prone_effects_condition_and_free_move(self):
        state = source_state()
        state = with_injury(state, 'wizard', lambda i: replace(i,
            conditions=i.conditions.with_condition(Condition.STAGGERED)))
        state = replace(state, consumed_execution_ids=('earlier',),
            wizard=replace(state.wizard, magic_state=WizardMagicState(1)),
            spatial_state=replace(state.spatial_state, free_move_used_entity_ids=('ally',),
                gave_ground_entity_ids=('enemy',), difficult_terrain_tested_entity_ids=('ally',)))
        final = stand(request(state)).state
        for f in fields(state):
            if f.name not in ('roster', 'spatial_state', 'champion_attack', 'minion_attack'):
                self.assertEqual(getattr(final, f.name), getattr(state, f.name), f.name)
        self.assertEqual(final.spatial_state.free_move_used_entity_ids, ('ally', 'wizard'))
        self.assertEqual(replace(final.spatial_state, free_move_used_entity_ids=('ally',)), state.spatial_state)
        for old in state.roster.participants:
            new = final.roster.participant(old.state.actor_id)
            if old.state.actor_id != 'wizard':
                self.assertEqual(new, old)
            else:
                self.assertEqual(new.state.injury, replace(old.state.injury,
                    conditions=old.state.injury.conditions.without_condition(Condition.PRONE),
                    active_wound_effects=(terrain(1),)))
                self.assertEqual(replace(new, state=old.state), old)
                self.assertEqual(replace(new.state, injury=old.state.injury), old.state)
        self.assertFalse(final.round_state.active_turn.action_slots[0].executed)

    def test_multiple_wounds_remove_all_causes_preserving_both_effect_orders(self):
        effects = (terrain(3), prone(2), terrain(2), prone(3))
        state = source_state(wounds=(superficial(), leg(2), leg(3)), effects=effects)
        result = stand(request(state))
        injury = result.state.roster.participant('wizard').state.injury
        self.assertEqual(result.removed_effects, (prone(2), prone(3)))
        self.assertEqual(injury.active_wound_effects, (terrain(3), terrain(2)))
        self.assertEqual(injury.wounds, state.roster.participant('wizard').state.injury.wounds)
        self.assertEqual(result.state.spatial_state.free_move_used_entity_ids, ('wizard',))
        self.assertFalse(any(w.treated or w.healed for w in injury.wounds))

    def test_fixed_entry_keeps_empty_rolls_and_does_not_invent_provenance(self):
        state = source_state(wounds=(leg(fixed=True),))
        final = stand(request(state)).state.roster.participant('wizard').state.injury
        self.assertEqual(final.wounds, (leg(fixed=True),))
        self.assertIs(final.wounds[0].origin, WoundRecordOrigin.FIXED_ENTRY)
        self.assertEqual(final.wounds[0].roll_values, ())

    def test_optional_child_owners_are_not_created(self):
        state = replace(source_state(), champion_attack=None, minion_attack=None)
        final = stand(request(state)).state
        self.assertIsNone(final.champion_attack)
        self.assertIsNone(final.minion_attack)

    def test_low_level_request_is_bound_to_complete_round_spatial_and_conditions(self):
        source = request()
        low = source.stand_request
        self.assertEqual((low.id, low.actor_id, low.target_id), (source.id, 'wizard', 'wizard'))
        self.assertEqual(low.round_state, source.state.round_state)
        self.assertEqual(low.state, source.state.spatial_state)
        self.assertEqual(low.target_conditions, source.state.roster.participant('wizard').state.injury.conditions)
        self.assertIs(low.target_kind, ProneRemovalTargetKind.SELF)
        self.assertIsNone(low.target_in_close_range)
        self.assertIs(low.actor_has_enemy_in_close_range, False)
        self.assertEqual(low.rule_id, 'RULE-COMBAT-014:free-move-prone-removal')

    def test_required_strict_booleans_ids_and_types(self):
        source = request()
        for name in ('actor_has_enemy_in_close_range', 'underlying_cause_allows_removal'):
            for bad in (None, 0, 1, 'false', object()):
                with self.subTest(name=name, bad=bad), self.assertRaises(TypeError):
                    replace(source, **{name: bad})
        for name in ('id', 'actor_id'):
            for bad in (None, True, 1):
                with self.assertRaises(TypeError): replace(source, **{name: bad})
            for bad in ('', '  '):
                with self.assertRaises(ValueError): replace(source, **{name: bad})
        for omitted in fields(source):
            with self.assertRaises(TypeError):
                Request(**{f.name: getattr(source, f.name) for f in fields(source) if f != omitted})
        for changes in ({'actor_has_enemy_in_close_range': True}, {'underlying_cause_allows_removal': False}):
            with self.assertRaises(ValueError): replace(source, **changes)

    def test_missing_duplicate_foreign_and_noncanonical_effects_are_rejected(self):
        alternatives = ((), (prone(1),), (terrain(1),), (prone(1), terrain(1), prone(1)),
            (prone(1), terrain(1), terrain(1)),
            (replace(prone(1), duration=WoundEffectDuration.UNTIL_TREATED), terrain(1)),
            (prone(1), replace(terrain(1), duration=WoundEffectDuration.UNTIL_HEALED)),
            (prone(1), replace(terrain(1), restriction=WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL)),
            (prone(1), terrain(1), WoundConditionEffect(1, Condition.STAGGERED, WoundEffectDuration.UNTIL_REMOVED)))
        for effects in alternatives:
            with self.subTest(effects=effects), self.assertRaises(ValueError):
                request(source_state(effects=effects))
        for effects in ((prone(1), terrain(1), prone(2), terrain(2)),
                        (prone(1), terrain(2)), (prone(2), terrain(1))):
            with self.subTest(effects=effects), self.assertRaises(ValueError):
                request(source_state(wounds=(superficial(), leg(2)), effects=effects))

    def test_multiple_leg_spasm_requires_every_pair_not_only_one_valid_wound(self):
        for effects in ((prone(1), terrain(1)), (prone(1), terrain(1), prone(2)),
                        (prone(1), terrain(1), terrain(2))):
            with self.subTest(effects=effects), self.assertRaises(ValueError):
                request(source_state(wounds=(leg(), leg(2)), effects=effects))

    def test_no_leg_superficial_only_and_wrong_canonical_entries_rejected(self):
        for wounds, effects in (((), ()), ((superficial(),), ()),
                               ((superficial(),), (prone(1), terrain(1)))):
            with self.subTest(wounds=wounds), self.assertRaises(ValueError):
                request(source_state(wounds=wounds, effects=effects))
        for entry, total, rolls in ((WoundEntryId.TORN_LEG, 13, (6, 7)),
                                    (WoundEntryId.CRUSHED_RIB, 10, (10,)),
                                    (WoundEntryId.SHATTERED_KNEE, 17, (7, 10))):
            wound = WoundRecord(1, entry, total, rolls, effect_resolved=True)
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                request(source_state(wounds=(wound,)))

    def test_roll_total_cannot_mislabel_table_entry_even_with_canonical_effects(self):
        for fixed in (False, True):
            wound = replace(leg(fixed=fixed), table_total=8, roll_values=() if fixed else (8,))
            with self.subTest(fixed=fixed), self.assertRaises(ValueError):
                request(source_state(wounds=(wound,)))
        wrong = replace(superficial(), table_total=4, roll_values=(4,))
        with self.assertRaises(ValueError):
            request(source_state(wounds=(wrong, leg(2)), effects=(prone(2), terrain(2))))

    def test_roll_values_reject_boolean_dice_even_when_sum_matches(self):
        wound = replace(leg(), roll_values=(True, 8))
        with self.assertRaises(ValueError): request(source_state(wounds=(wound,)))

    def test_unresolved_treated_healed_histories_are_not_overridden_by_explicit_true(self):
        for changes in ({'effect_resolved': False}, {'treated': True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                request(source_state(wounds=(replace(leg(), **changes),)))
        for changes in ({'effect_resolved': False}, {'treated': True}, {'treated': True, 'healed': True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                request(source_state(wounds=(replace(superficial(), **changes), leg(2)),
                    effects=(prone(2), terrain(2))))
        # Healed wounds cannot retain non-permanent effects even at injury admission.
        with self.assertRaises(ValueError):
            request(source_state(wounds=(replace(leg(), treated=True, healed=True),), effects=()))

    def test_non_prone_dead_and_every_other_condition_are_rejected(self):
        state = source_state()
        for condition in Condition:
            if condition in (Condition.PRONE, Condition.STAGGERED):
                continue
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                request(with_injury(state, 'wizard', lambda i: replace(i,
                    conditions=i.conditions.with_condition(condition))))
        for transform in (lambda i: replace(i, dead=True),
                          lambda i: replace(i, conditions=i.conditions.without_condition(Condition.PRONE))):
            with self.assertRaises(ValueError): request(with_injury(state, 'wizard', transform))

    def test_only_active_wizard_not_minion_or_unknown_actor(self):
        source = request()
        for actor in ('ally', 'enemy', 'missing'):
            with self.subTest(actor=actor), self.assertRaises(ValueError): replace(source, actor_id=actor)
        with self.assertRaises(ValueError):
            Request('minion', ready('ally'), 'ally', False, True)

    def test_idle_extra_slots_spent_move_and_live_exclusion_rejected(self):
        state = source_state()
        turn = state.round_state.active_turn
        for active in (None, replace(turn, action_slots=()), replace(turn, action_slots=(
                *turn.action_slots, CombatActionSlot(2, ATTACK, ActionSlotGrant.ABILITY, 'authored:extra')))):
            with self.subTest(active=active), self.assertRaises(ValueError):
                request(with_round(state, replace(state.round_state, active_turn=active)))
        with self.assertRaises(ValueError):
            request(replace(state, spatial_state=replace(state.spatial_state, free_move_used_entity_ids=('wizard',))))
        with self.assertRaises(ValueError):
            request(with_round(state, replace(state.round_state, excluded_turn_entity_ids=('enemy',))))

    def test_all_actual_mandatory_pending_families_block_before_stand(self):
        _, raw = casting_pending()
        prepared = roll_request(raw).state
        rolled = roll_npc_roster_miscast(roll_request(raw), Dice((7, 7, 7))).state
        attack_source = incoming_attack()
        attack = execute_npc_champion_attack(attack_source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 4)))
        champion = NpcRosterChampionAttackResult(attack_source, attack).state
        minion = execute_npc_roster_minion_attack(minion_request(), SequenceRandom((1, 2, 3, 10, 10, 10))).state
        for state in (raw, prepared, rolled, interruption_pending(), movement_pending()[2], champion, minion):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'pending|Miscast'):
                Request('stand', state, 'wizard', False, True)

    def test_executed_standard_slot_cannot_be_reused_even_without_pending(self):
        state = source_state()
        turn = state.round_state.active_turn
        slot = turn.action_slots[0]
        receipt = ActionExecutionReceipt('authored:execution', 'authored:rule',
            'authored:source', 'authored:result', 'wizard', state.round_state.round_number,
            slot.index, slot.declaration)
        combat = replace(state.round_state, active_turn=replace(turn,
            action_slots=(replace(slot, execution=receipt),)))
        state = replace(with_round(state, combat), consumed_execution_ids=(receipt.id,))
        with self.assertRaisesRegex(ValueError, 'unexecuted standard'): request(state)

    def test_untracked_timed_effect_is_not_discarded_to_make_stand_possible(self):
        state = source_state(effects=(prone(1), terrain(1), WoundConditionEffect(
            1, Condition.STAGGERED, WoundEffectDuration.END_OF_NEXT_TURN)))
        with self.assertRaisesRegex(ValueError, 'chronology'): request(state)

    def test_existing_standalone_boundary_keeps_rejecting_leg_spasm(self):
        for state in (source_state(), stand(request()).state):
            with self.assertRaises(ValueError):
                NpcRosterProneStandRequest('old', state, 'wizard', False, True)

    def test_result_rejects_metadata_trace_and_other_complete_primitive_sources(self):
        source = request()
        actual = stand(source).stand
        for changes in ({'request_id': 'foreign'}, {'rule_id': 'foreign:rule'},
                        {'applied_rule_ids': ('foreign:rule',)},
                        {'applied_rule_ids': (*actual.applied_rule_ids, 'extra')}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Result(source, replace(actual, **changes))
        for low in (replace(source.stand_request, id='other'),
                    replace(source.stand_request, target_conditions=source.stand_request.target_conditions.with_condition(Condition.STAGGERED)),
                    replace(source.stand_request, state=replace(source.state.spatial_state, gave_ground_entity_ids=('enemy',)))):
            with self.assertRaises(ValueError): Result(source, resolve_free_move_prone_removal(low))

    def test_apply_requires_complete_snapshot_and_rejects_replay(self):
        source = request()
        result = stand(source)
        for state in (result.state, replace(source.state, consumed_execution_ids=('foreign',)),
                replace(source.state, wizard=replace(source.state.wizard, magic_state=WizardMagicState(1))),
                with_injury(source.state, 'enemy', lambda i: replace(i, conditions=i.conditions.with_condition(Condition.STAGGERED)))):
            with self.subTest(state=state), self.assertRaises(ValueError): apply(state, result)
        self.assertEqual(apply(deepcopy(source.state), result), result.state)
        with self.assertRaises(ValueError): replace(source, id='new', state=result.state)
        reintroduced = with_injury(result.state, 'wizard', lambda i: replace(i,
            conditions=i.conditions.with_condition(Condition.PRONE), active_wound_effects=(prone(1), terrain(1))))
        with self.assertRaises(ValueError): replace(source, id='new', state=reintroduced)

    def test_one_existing_reducer_no_test_rng_retry_or_validation_reexecution(self):
        source = request()
        before, global_rng = deepcopy(source), getstate()
        with (patch('towr.rules.npc_roster_leg_spasm_resolution.resolve_free_move_prone_removal', wraps=resolve_free_move_prone_removal) as reducer,
              patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test')),
              patch('random.Random', side_effect=AssertionError('no RNG'))):
            result = stand(source)
            reducer.assert_called_once_with(source.stand_request)
        with patch('towr.rules.npc_roster_leg_spasm_resolution.resolve_free_move_prone_removal', side_effect=AssertionError('no rerun')):
            self.assertEqual(Result(source, result.stand), result)
            self.assertEqual(apply(source.state, result), result.state)
            self.assertEqual(result.removed_effects, (prone(1),))
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_reducer_failure_propagates_once_and_leaves_whole_source_unchanged(self):
        source = request()
        before = deepcopy(source)
        failure = RuntimeError('stand failure')
        with patch('towr.rules.npc_roster_leg_spasm_resolution.resolve_free_move_prone_removal', side_effect=failure) as reducer:
            with self.assertRaises(RuntimeError) as caught: stand(source)
            self.assertIs(caught.exception, failure)
            reducer.assert_called_once()
        self.assertEqual(source, before)

    def test_typed_frozen_slotted_models_and_derived_only_views(self):
        source = request()
        result = stand(source)
        for bad in (None, {}, True, source.stand_request):
            with self.assertRaises(TypeError): stand(bad)
            with self.assertRaises(TypeError): replace(source, state=bad)
            with self.assertRaises(TypeError): Result(bad, result.stand)
            with self.assertRaises(TypeError): Result(source, bad)
            with self.assertRaises(TypeError): apply(bad, result)
            with self.assertRaises(TypeError): apply(source.state, bad)
        self.assertEqual(tuple(f.name for f in fields(result)), ('source', 'stand'))
        for value in (source, result):
            self.assertFalse(hasattr(value, '__dict__'))
            self.assertEqual(deepcopy(value), value)
            self.assertEqual(pickle.loads(pickle.dumps(value)), value)
            with self.assertRaises(FrozenInstanceError): setattr(value, fields(value)[0].name, None)
        with self.assertRaises(TypeError): Result(source, result.stand, state=result.state)
        with self.assertRaises(TypeError): Result(source, result.stand, removed_effects=())


if __name__ == '__main__':
    unittest.main()
