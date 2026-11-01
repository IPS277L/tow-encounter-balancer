"""ADR-0049 canonical stationary views, with actual active/expired Wound6 witnesses.

Mixed fixtures explicitly append authored Wound9 to actual Wound6 owners; they
do not claim that an automatic mixed battle has already been implemented.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_leg_spasm_stand import (
    actual_state, leg, prone, request as stand_request, source_state, superficial, terrain,
)
from tests.unit.test_m8_npc_roster_minion_attack import changed_roster
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_npc_roster_miscast_preparation import casting_pending, interruption_pending
from tests.unit.test_m8_npc_roster_miscast_roll import request as miscast_request
from tests.unit.test_m8_npc_roster_prone_stand import with_round
from tests.unit.test_m8_npc_roster_casting import bound_request
from tests.unit.test_m8_npc_roster_turn import ATTACK, CAST
from tests.unit.test_m8_npc_wound_turn_end import wounded, request as end_request
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundConditionEffect, WoundConditionSourceSnapshot, WoundEffectDuration, WoundEntryId, WoundRecord,
    WoundRecordOrigin, WoundRestriction,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext as Context
from towr.domain.npc_wound_turn_models import NpcWoundTurnEndReceipt
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import InlineProfile, Skill
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting
from towr.rules.npc_roster_leg_spasm_resolution import stand_npc_roster_leg_spasm
from towr.rules.npc_roster_shooting_preparation import prepare_npc_roster_shooting
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


def with_wizard_injury(state, transform):
    return changed_roster(state, lambda p: replace(p, state=replace(p.state,
        injury=transform(p.state.injury))) if p.state.actor_id == state.wizard.actor_id else p)


def post_stand(*, actual=False):
    return stand_npc_roster_leg_spasm(stand_request(actual_state() if actual else None)).state


def append_authored_terrain(state):
    """Preserve the actual6 witness; author only the later post-stand9 snapshot."""
    return with_wizard_injury(state, lambda i: replace(i,
        wounds=(*i.wounds, leg(len(i.wounds) + 1)),
        active_wound_effects=(*i.active_wound_effects, terrain(len(i.wounds) + 1)),
        conditions=i.conditions.without_condition(Condition.BROKEN)))


def active_six(*, completed=False):
    return append_authored_terrain(wounded(completed=completed))


def expired_six():
    # The new explicit-context end archives the actual expiry witness. Merely
    # appending terrain after a legacy IDs-only end is deliberately insufficient.
    original = end_request()
    state = append_authored_terrain(original.state)
    request = NpcWoundTurnEndRequest(original.id, state, state.wizard.actor_id,
        original.condition_sources, stationary_wounds=context(state))
    return end_npc_wound_turn(request).state


def context(state=None):
    state = post_stand() if state is None else state
    return Context(state, state.wizard.actor_id, True)


def with_daily(state, transform):
    return replace(state, champion_attack=replace(state.champion_attack,
        daily_wounds=transform(state.champion_attack.daily_wounds)))


class StationaryWoundContextTests(unittest.TestCase):
    def test_two_actual_stomach_blows_have_one_drained_condition_and_both_expire(self):
        # The first6 has an actual witness; only the intervening post-stand9 is
        # authored. The second6 and all subsequent scheduler/Casting/end steps
        # are real bound transitions, without copied or fabricated expiries.
        original = active_six()
        old = deepcopy(original)
        actor = original.wizard.actor_id
        state = end_npc_wound_turn(NpcWoundTurnEndRequest(
            'multiple-six:end-first', original, 'brigand:0')).state
        state = start_npc_roster_turn(NpcRosterTurnStartRequest(
            'multiple-six:start-second', state, 'brigand:1', ATTACK)).state
        source = prepare_npc_roster_shooting(request_id='multiple-six:second',
            state=state, actor_id='brigand:1', target_id=actor, selected_attack_id='warbow',
            target_range=RangedWeaponRange.SHORT, has_enemy_in_close_range=False,
            range_approved_by_gm=False, defender_is_aware=True,
            selected_protection_skill=Skill.ATHLETICS, can_target_leave_zone=True,
            stationary_wounds=context(state))
        # This warbow is outside its optimum: two attack dice, three normal
        # Protection dice, then three Wound dice (two untreated prior Wounds).
        dice = Dice((1, 2, 10, 10, 10, 1, 2, 3))
        attack = execute_npc_champion_attack(source.attack, dice)
        dice.exhausted()
        state = NpcRosterChampionAttackResult(source, attack).state
        view = context(state)
        expiries = state.wound_expiries
        self.assertEqual(tuple(w.table_total for w in view.injury.wounds), (6, 9, 6))
        self.assertEqual(len(expiries), 2)
        self.assertEqual(view.active_stomach_blows, expiries)
        self.assertIs(expiries[1].source, attack)
        self.assertEqual(tuple(e.deadline_round_number for e in expiries), (1, 1))
        self.assertEqual(view.condition_effects, tuple(e.effect for e in expiries))
        self.assertEqual(view.terrain_effects, (terrain(2),))
        self.assertEqual(view.injury.conditions.conditions, frozenset({Condition.DRAINED}))
        with self.assertRaises(ValueError):
            context(with_wizard_injury(state, lambda i: replace(i,
                conditions=i.conditions.without_condition(Condition.DRAINED))))
        state = end_npc_wound_turn(NpcWoundTurnEndRequest(
            'multiple-six:end-second', state, 'brigand:1')).state
        self.assertEqual(state.wound_expiries, expiries)
        self.assertTrue(context(state).injury.conditions.has(Condition.DRAINED))
        state = start_npc_roster_turn(NpcRosterTurnStartRequest(
            'multiple-six:start-wizard', state, actor, CAST)).state
        fixture = bound_request().casting
        casting = prepare_npc_roster_casting(request_id='multiple-six:cast', state=state,
            selected_zone_id='arena', targets=tuple(NpcRosterCastingTargetContext(
                target, InlineProfile(3, 3), False) for target in ('brigand:0', 'brigand:1')),
            facts=fixture.facts, policy=fixture.policy, stationary_wounds=context(state))
        state = NpcRosterCastingResult(casting, execute_cowardly_flight_casting(
            casting.casting, SequenceRandom((10, 10, 10)))).state
        before_end = deepcopy(state)
        request = NpcWoundTurnEndRequest('multiple-six:end-wizard', state, actor,
            (WoundConditionSourceSnapshot(Condition.DRAINED, False),),
            stationary_wounds=context(state))
        final = end_npc_wound_turn(request).state
        final_view = context(final)
        self.assertEqual(final_view.active_stomach_blows, ())
        self.assertEqual(final_view.condition_effects, ())
        self.assertEqual(final_view.expired_stomach_blow_attack_ids, tuple(e.attack_id for e in expiries))
        self.assertEqual(final_view.terrain_effects, (terrain(2),))
        self.assertFalse(final_view.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(final.wound_turn_end_receipts[-1].expired_attack_ids, tuple(e.attack_id for e in expiries))
        self.assertEqual(final.wound_turn_end_receipts[-1].expired_sources, expiries)
        self.assertEqual(final_view.injury.wounds, context(before_end).injury.wounds)
        self.assertEqual(final.champion_attack.daily_wounds, before_end.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids, before_end.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.roster, final.champion_attack.roster)
        self.assertEqual(original, old)
        self.assertEqual(state, before_end)

    def test_actual_stand_has_lossless_derived_views_and_give_ground_prohibition(self):
        state = post_stand(actual=True)
        original = deepcopy(state)
        view = context(state)
        self.assertIs(view.state, state)
        self.assertIs(view.injury, state.roster.participant(state.wizard.actor_id).state.injury)
        self.assertEqual(view.terrain_effects, (terrain(1),))
        self.assertEqual(view.condition_effects, ())
        self.assertEqual(view.active_stomach_blows, ())
        self.assertEqual(view.expired_stomach_blow_attack_ids, ())
        self.assertIs(view.can_give_ground, False)
        self.assertEqual(state, original)

    def test_terrain_view_preserves_original_order_and_superficial_history(self):
        state = source_state(wounds=(superficial(), leg(2), leg(3)),
            effects=(terrain(3), prone(2), terrain(2), prone(3)))
        state = stand_npc_roster_leg_spasm(stand_request(state)).state
        view = context(state)
        self.assertEqual(view.terrain_effects, (terrain(3), terrain(2)))
        self.assertEqual(view.injury.wounds, (superficial(), leg(2), leg(3)))

    def test_active_six_retains_actual_attack_expiry_receipt_and_typed_effects(self):
        for completed, deadline in ((False, 1), (True, 2)):
            state = active_six(completed=completed)
            before = deepcopy(state)
            view = context(state)
            with self.subTest(deadline=deadline):
                self.assertEqual(view.active_stomach_blows, state.wound_expiries)
                self.assertEqual(view.active_stomach_blows[0].deadline_round_number, deadline)
                self.assertEqual(view.condition_effects, (state.wound_expiries[0].effect,))
                self.assertEqual(view.terrain_effects, (terrain(2),))
                self.assertEqual(view.expired_stomach_blow_attack_ids, ())
                self.assertTrue(view.injury.conditions.has(Condition.DRAINED))
                self.assertEqual(state, before)

    def test_actual_expired_six_uses_real_registration_and_lifecycle_id_conventions(self):
        state = expired_six()
        view = context(state)
        end = state.wound_turn_end_receipts[-1]
        attack_id, = end.expired_attack_ids
        receipt, = state.champion_attack.daily_wounds.receipts
        self.assertEqual(receipt.id, attack_id + ':daily-wound:receipt')
        self.assertIn(receipt.source_request_id + '-lifecycle', state.champion_attack.consumed_wound_roll_ids)
        self.assertFalse(receipt.wound.effect_resolved)
        self.assertTrue(view.injury.wounds[0].effect_resolved)
        self.assertEqual(view.expired_stomach_blow_attack_ids, (attack_id,))
        self.assertEqual(tuple(e.attack_id for e in end.expired_sources), (attack_id,))
        self.assertEqual(end.expired_sources[0].deadline_round_number, end.round_number)
        self.assertEqual(view.active_stomach_blows, ())
        self.assertEqual(view.condition_effects, ())
        self.assertEqual(view.terrain_effects, (terrain(2),))
        self.assertFalse(view.injury.conditions.has(Condition.DRAINED))
        self.assertFalse(view.injury.wounds[0].treated)
        self.assertFalse(view.injury.wounds[0].healed)

    def test_legacy_ids_only_end_is_not_a_stationary_expiry_witness(self):
        legacy = end_npc_wound_turn(end_request()).state
        self.assertTrue(legacy.wound_turn_end_receipts[-1].expired_attack_ids)
        self.assertEqual(legacy.wound_turn_end_receipts[-1].expired_sources, ())
        state = append_authored_terrain(legacy)
        self.assertFalse(state.roster.participant(state.wizard.actor_id).state.injury.conditions.has(Condition.DRAINED))
        with self.assertRaises(ValueError): context(state)

    def test_forged_early_expiry_is_rejected_with_and_without_bound_witness(self):
        state = active_six(completed=True)
        actor = state.wizard.actor_id
        expiry, = context(state).active_stomach_blows
        self.assertEqual(expiry.deadline_round_number, 2)
        self.assertEqual(state.round_state.round_number, 1)
        with self.assertRaises(ValueError):
            NpcWoundTurnEndReceipt('forged:early', actor, 1, (expiry.attack_id,),
                expired_sources=(expiry,))
        # Legacy IDs alone cannot conceal premature Condition removal. Build
        # the typed historical snapshot without mutating the original owner.
        false_end = NpcWoundTurnEndReceipt('forged:early', actor, 1, (expiry.attack_id,))
        altered = with_wizard_injury(replace(state, wound_expiries=()), lambda i: replace(i,
            active_wound_effects=tuple(e for e in i.active_wound_effects if e != expiry.effect),
            conditions=i.conditions.without_condition(Condition.DRAINED)))
        altered = replace(altered, wound_turn_end_receipts=(*altered.wound_turn_end_receipts, false_end))
        with self.assertRaises(ValueError): context(altered)
        self.assertEqual(context(state).active_stomach_blows, (expiry,))

    def test_fixed_leg_spasm_preserves_origin_without_synthetic_roll(self):
        state = stand_npc_roster_leg_spasm(stand_request(source_state(wounds=(leg(fixed=True),)))).state
        view = context(state)
        self.assertEqual(view.injury.wounds[0].roll_values, ())
        self.assertIs(view.injury.wounds[0].origin, WoundRecordOrigin.FIXED_ENTRY)

    def test_staggered_is_independent_but_drained_requires_bidirectional_active_six(self):
        for state in (post_stand(), active_six(), expired_six()):
            state = with_wizard_injury(state, lambda i: replace(i,
                conditions=i.conditions.with_condition(Condition.STAGGERED)))
            self.assertTrue(context(state).injury.conditions.has(Condition.STAGGERED))
        for state in (post_stand(), expired_six()):
            with self.assertRaises(ValueError):
                context(with_wizard_injury(state, lambda i: replace(i,
                    conditions=i.conditions.with_condition(Condition.DRAINED))))
        with self.assertRaises(ValueError):
            context(with_wizard_injury(active_six(), lambda i: replace(i,
                conditions=i.conditions.without_condition(Condition.DRAINED))))

    def test_context_does_not_require_free_move_spent_or_an_active_wizard_turn(self):
        state = post_stand()
        state = replace(state, spatial_state=replace(state.spatial_state, free_move_used_entity_ids=()))
        self.assertIs(context(state).can_give_ground, False)
        self.assertIs(context(active_six()).can_give_ground, False)  # Attacker owns the turn.
        self.assertIs(context(expired_six()).can_give_ground, False)  # Round is idle/completed.

    def test_required_strict_true_fact_identifiers_and_owner_type(self):
        valid = context()
        for bad in (None, 0, 1, 'true', object()):
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                replace(valid, no_external_condition_sources=bad)
        with self.assertRaises(ValueError): replace(valid, no_external_condition_sources=False)
        for bad in (None, True, 1):
            with self.assertRaises(TypeError): replace(valid, actor_id=bad)
        for bad in ('', ' ', 'missing', 'ally', 'enemy'):
            with self.subTest(actor=bad), self.assertRaises(ValueError): replace(valid, actor_id=bad)
        for bad in (None, {}, True, valid.injury):
            with self.assertRaises(TypeError): replace(valid, state=bad)
        for omitted in fields(valid):
            with self.assertRaises(TypeError):
                Context(**{f.name: getattr(valid, f.name) for f in fields(valid) if f != omitted})

    def test_validate_source_binds_entire_root_even_when_lower_child_is_unchanged(self):
        view = context()
        state = view.state
        self.assertIsNone(view.validate_source(deepcopy(state), view.actor_id))
        alternatives = (replace(state, wizard=replace(state.wizard, magic_state=WizardMagicState(1))),
            replace(state, spatial_state=replace(state.spatial_state, gave_ground_entity_ids=('enemy',))),
            replace(state, consumed_execution_ids=(*state.consumed_execution_ids, 'foreign')))
        for other in alternatives:
            self.assertEqual(other.champion_attack, state.champion_attack)
            with self.assertRaises(ValueError): view.validate_source(other, view.actor_id)
        for bad in ('ally', 'enemy', 'missing', ''):
            with self.assertRaises(ValueError): view.validate_source(state, bad)
        for bad in (None, {}, True):
            with self.assertRaises(TypeError): view.validate_source(bad, view.actor_id)
            with self.assertRaises(TypeError): view.validate_source(state, bad)

    def test_all_other_conditions_and_dead_wizard_are_rejected(self):
        state = post_stand()
        for condition in Condition:
            if condition in (Condition.STAGGERED, Condition.DRAINED):
                continue
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                context(with_wizard_injury(state, lambda i: replace(i,
                    conditions=i.conditions.with_condition(condition))))
        with self.assertRaises(ValueError):
            context(with_wizard_injury(state, lambda i: replace(i, dead=True)))

    def test_missing_duplicate_noncanonical_and_unrelated_effects_rejected(self):
        state = post_stand()
        alternatives = ((), (terrain(1), terrain(1)), (terrain(1), prone(1)),
            (replace(terrain(1), duration=WoundEffectDuration.UNTIL_HEALED),),
            (replace(terrain(1), restriction=WoundRestriction.SPEED_IS_SLOW),),
            (terrain(1), WoundConditionEffect(1, Condition.STAGGERED, WoundEffectDuration.UNTIL_REMOVED)))
        for effects in alternatives:
            with self.subTest(effects=effects), self.assertRaises(ValueError):
                context(with_wizard_injury(state, lambda i: replace(i, active_wound_effects=effects)))
        state = active_six()
        with self.assertRaises(ValueError):
            context(with_wizard_injury(state, lambda i: replace(i,
                active_wound_effects=(*i.active_wound_effects, state.wound_expiries[0].effect))))

    def test_every_leg_requires_own_terrain_and_superficial_cannot_own_effect(self):
        base = post_stand()
        for wounds, effects in (((leg(), leg(2)), (terrain(1),)),
                               ((superficial(), leg(2)), (terrain(1),))):
            with self.subTest(wounds=wounds), self.assertRaises(ValueError):
                context(with_wizard_injury(base, lambda i: replace(i, wounds=wounds,
                    active_wound_effects=effects)))

    def test_no_leg_or_other_wound_entry_not_admitted(self):
        base = post_stand()
        for wounds, effects in (((), ()), ((superficial(),), ()),
                ((WoundRecord(1, WoundEntryId.TORN_LEG, 13, (6, 7), effect_resolved=True),), (terrain(1),))):
            with self.subTest(wounds=wounds), self.assertRaises(ValueError):
                context(with_wizard_injury(base, lambda i: replace(i, wounds=wounds, active_wound_effects=effects)))

    def test_noncanonical_totals_boolean_dice_and_lifecycle_flags_rejected(self):
        base = post_stand()
        bad_records = (replace(leg(), table_total=8, roll_values=(8,)),
            replace(leg(), roll_values=(True, 8)), replace(leg(), effect_resolved=False),
            replace(leg(), treated=True))
        for wound in bad_records:
            with self.subTest(wound=wound), self.assertRaises(ValueError):
                context(with_wizard_injury(base, lambda i: replace(i, wounds=(wound,))))
        for wound in (replace(superficial(), table_total=4, roll_values=(4,)),
                      replace(superficial(), treated=True, healed=True)):
            with self.subTest(wound=wound), self.assertRaises(ValueError):
                context(with_wizard_injury(base, lambda i: replace(i, wounds=(wound, leg(2)),
                    active_wound_effects=(terrain(2),))))

    def test_unwitnessed_or_fixed_six_is_not_expired_just_because_effect_is_absent(self):
        for fixed in (False, True):
            wound = WoundRecord(2, WoundEntryId.STOMACH_BLOW, 6, () if fixed else (6,),
                effect_resolved=True, origin=WoundRecordOrigin.FIXED_ENTRY if fixed else WoundRecordOrigin.TABLE_ROLL)
            with self.subTest(fixed=fixed), self.assertRaises(ValueError):
                context(with_wizard_injury(post_stand(), lambda i: replace(i, wounds=(*i.wounds, wound))))

    def test_active_six_requires_full_expiry_and_valid_clock(self):
        state = active_six()
        with self.assertRaises(ValueError): context(replace(state, wound_expiries=()))
        with self.assertRaises(ValueError):
            context(replace(state, wound_expiries=(*state.wound_expiries, state.wound_expiries[0])))
        combat = replace(state.round_state, round_number=2, active_turn=None)
        overdue = replace(state, round_state=combat,
            champion_attack=replace(state.champion_attack, round_state=combat),
            spatial_state=replace(state.spatial_state, round_number=2))
        with self.assertRaises(ValueError): context(overdue)
        with self.assertRaises(ValueError):
            context(replace(state, wound_expiries=wounded(completed=True).wound_expiries))

    def test_expired_six_requires_actual_end_and_daily_receipts(self):
        state = expired_six()
        with self.assertRaises(ValueError): context(replace(state, wound_turn_end_receipts=()))
        with self.assertRaises(ValueError): context(with_daily(state, lambda d: replace(d, receipts=())))
        for changes in ({'id': 'foreign'}, {'id': state.champion_attack.daily_wounds.receipts[0].id + ':extra'},
                        {'source_request_id': 'foreign-roll'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                context(with_daily(state, lambda d: replace(d,
                    receipts=(replace(d.receipts[0], **changes),))))

    def test_expired_six_requires_consumed_execution_and_roll_history(self):
        state = expired_six()
        for changes in ({'consumed_wound_roll_ids': ()}, {'consumed_execution_ids': ()}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                context(replace(state, champion_attack=replace(state.champion_attack, **changes)))
        attack_id = state.wound_turn_end_receipts[-1].expired_attack_ids[0]
        with self.assertRaises(ValueError):
            context(replace(state, consumed_execution_ids=tuple(i for i in state.consumed_execution_ids if i != attack_id)))

    def test_pending_phases_and_live_exclusion_still_block_context(self):
        _, casting = casting_pending()
        for state in (casting, interruption_pending(), miscast_request(casting).state):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'pending|Miscast'):
                context(state)
        state = post_stand()
        with self.assertRaises(ValueError):
            context(with_round(state, replace(state.round_state, excluded_turn_entity_ids=('enemy',))))

    def test_models_are_derived_frozen_slotted_picklable_and_do_not_execute_rules(self):
        state = active_six()
        before, rng_before = deepcopy(state), getstate()
        with (patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test')),
              patch('towr.rules.npc_roster_leg_spasm_resolution.resolve_free_move_prone_removal', side_effect=AssertionError('no stand'))):
            view = context(state)
            self.assertEqual(deepcopy(view), view)
            self.assertEqual(pickle.loads(pickle.dumps(view)), view)
            self.assertIsNone(view.validate_source(state, state.wizard.actor_id))
        self.assertFalse(hasattr(view, '__dict__'))
        self.assertEqual(tuple(f.name for f in fields(view)), ('state', 'actor_id', 'no_external_condition_sources'))
        with self.assertRaises(FrozenInstanceError): view.state = None
        with self.assertRaises(TypeError): Context(state, state.wizard.actor_id, True, can_give_ground=True)
        self.assertEqual(state, before)
        self.assertEqual(getstate(), rng_before)


if __name__ == '__main__':
    unittest.main()
