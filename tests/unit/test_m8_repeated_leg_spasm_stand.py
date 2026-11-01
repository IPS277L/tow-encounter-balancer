"""ADR-0052: actual first stand and repeated Wound, finite full-owner lineage."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_leg_spasm_stand import prone, terrain
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_stationary_wound_context import with_wizard_injury
from tests.unit.test_m8_stationary_wound_runner import scenario
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundEntryId, WoundRecordOrigin
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_repeated_leg_spasm_models import (
    NpcRosterRepeatedLegSpasmStandRequest as Request,
    NpcRosterRepeatedLegSpasmStandResult as Result,
)
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.free_movement_resolution import resolve_free_move_prone_removal
from towr.rules.npc_roster_repeated_leg_spasm_resolution import (
    stand_npc_roster_repeated_leg_spasm as stand,
    apply_npc_roster_repeated_leg_spasm_stand as apply,
)


VALUES = (1, 2, 3, 10, 10, 10, 9, *((10,) * 9), 1, 2, 3, 10, 10, 10, 4, 5)


def actual(*, miscast=False, values=VALUES):
    source = scenario(miscast=miscast)
    dice = Dice(values)
    stopped = run_npc_magic_scenario(source, dice)
    dice.exhausted()
    assert dice.calls == 24
    assert stopped.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    previous = tuple(s.result for s in stopped.steps if isinstance(s.result, NpcRosterLegSpasmStandResult))
    attacks = tuple(s.result for s in stopped.steps if isinstance(s.result, NpcRosterChampionAttackResult))
    assert len(previous) == 1 and len(attacks) == 2
    return stopped, Request('repeated:stand', stopped.current, 'wizard', False, True, previous[0], attacks[-1])


def detached(value, **changes):
    """Emulate transported frozen records; deliberately bypass their constructor."""
    result = deepcopy(value)
    for name, replacement in changes.items():
        object.__setattr__(result, name, replacement)
    return result


class RepeatedLegSpasmStandTests(unittest.TestCase):
    def test_actual_second_wound_projects_only_prone_and_one_free_move(self):
        _, source = actual()
        old, rng_before = deepcopy(source), getstate()
        result = stand(source)
        final = apply(source.state, result)
        before = source.state
        injury = before.roster.participant('wizard').state.injury
        self.assertEqual(tuple(w.roll_values for w in injury.wounds), ((9,), (4, 5)))
        self.assertEqual(result.removed_effects, (prone(2),))
        self.assertEqual(final.roster.participant('wizard').state.injury, replace(injury,
            conditions=injury.conditions.without_condition(Condition.PRONE),
            active_wound_effects=(terrain(1), terrain(2))))
        self.assertEqual(final.spatial_state, replace(before.spatial_state,
            free_move_used_entity_ids=(*before.spatial_state.free_move_used_entity_ids, 'wizard')))
        for field in fields(before):
            if field.name not in ('roster', 'spatial_state', 'champion_attack', 'minion_attack'):
                self.assertEqual(getattr(final, field.name), getattr(before, field.name), field.name)
        for name in ('champion_attack', 'minion_attack'):
            self.assertEqual(getattr(final, name), replace(getattr(before, name), roster=final.roster))
        self.assertEqual(final.roster, final.champion_attack.roster)
        self.assertEqual(final.roster, final.minion_attack.roster)
        self.assertEqual(len(final.champion_attack.daily_wounds.receipts), 2)
        self.assertEqual(len(final.champion_attack.consumed_wound_roll_ids), 2)
        self.assertFalse(final.round_state.active_turn.action_slots[0].executed)
        self.assertIs(result.source, source)
        self.assertEqual(source, old)
        self.assertEqual(getstate(), rng_before)

    def test_executor_calls_one_primitive_and_constructors_apply_do_not_reexecute(self):
        _, source = actual()
        path = 'towr.rules.npc_roster_repeated_leg_spasm_resolution.resolve_free_move_prone_removal'
        with patch(path, wraps=resolve_free_move_prone_removal) as primitive, \
                patch('random.Random', side_effect=AssertionError('no RNG')):
            result = stand(source)
            primitive.assert_called_once()
            self.assertEqual(Result(source, result.stand), result)
            self.assertEqual(replace(source), source)
            self.assertEqual(apply(source.state, result), result.state)
            self.assertEqual(primitive.call_count, 1)

    def test_frozen_pickle_preserves_both_full_witnesses(self):
        _, source = actual()
        result = stand(source)
        self.assertEqual(pickle.loads(pickle.dumps(result)), result)
        self.assertEqual(pickle.loads(pickle.dumps(source)), source)
        with self.assertRaises(FrozenInstanceError): source.actor_id = 'enemy'
        with self.assertRaises(FrozenInstanceError): result.source = source
        self.assertFalse(hasattr(source, '__dict__'))

    def test_required_strict_booleans_ids_and_typed_witnesses(self):
        _, source = actual()
        for name in ('actor_has_enemy_in_close_range', 'underlying_cause_allows_removal'):
            for bad in (None, 0, 1, 'false'):
                with self.subTest(name=name, bad=bad), self.assertRaises(TypeError):
                    replace(source, **{name: bad})
        for name in ('state', 'previous_stand', 'wound_attack'):
            for bad in (None, True, {}, source.id):
                with self.subTest(name=name, bad=bad), self.assertRaises(TypeError):
                    replace(source, **{name: bad})
        for name in ('id', 'actor_id'):
            with self.assertRaises(TypeError): replace(source, **{name: 1})
            with self.assertRaises(ValueError): replace(source, **{name: ' '})
        for field in fields(source):
            with self.assertRaises(TypeError):
                Request(**{f.name: getattr(source, f.name) for f in fields(source) if f != field})

    def test_close_cause_wrong_actor_and_spent_free_move_reject(self):
        _, source = actual()
        alternatives = ({'actor_has_enemy_in_close_range': True},
            {'underlying_cause_allows_removal': False}, {'actor_id': 'ally'},
            {'state': replace(source.state, spatial_state=replace(source.state.spatial_state,
                free_move_used_entity_ids=('wizard',)))})
        for changes in alternatives:
            with self.subTest(changes=tuple(changes)), self.assertRaises(ValueError):
                replace(source, **changes)

    def test_missing_duplicate_old_reactivated_or_reordered_causes_reject(self):
        _, source = actual()
        effects = source.state.roster.participant('wizard').state.injury.active_wound_effects
        alternatives = ((), effects[:-1], effects[1:], (terrain(1), terrain(2)),
            (*effects, prone(1)), (*effects, prone(2)), (*effects, terrain(1)), tuple(reversed(effects)))
        for bad in alternatives:
            with self.subTest(effects=bad), self.assertRaises(ValueError):
                replace(source, state=with_wizard_injury(source.state,
                    lambda injury: replace(injury, active_wound_effects=bad)))

    def test_current_wound_identity_and_flags_cannot_be_normalized(self):
        _, source = actual()
        injury = source.state.roster.participant('wizard').state.injury
        for changes in ({'roll_values': (3, 6)}, {'effect_resolved': False}, {'treated': True},
                        {'origin': WoundRecordOrigin.FIXED_ENTRY, 'roll_values': ()}):
            wound = replace(injury.wounds[-1], **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, state=with_wizard_injury(source.state,
                    lambda i: replace(i, wounds=(*i.wounds[:-1], wound))))

    def test_other_wounds_extra_new_wound_and_conditions_do_not_bypass_scope(self):
        _, source = actual()
        for condition in (Condition.DRAINED, Condition.BROKEN, Condition.CRITICALLY_INJURED):
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                replace(source, state=with_wizard_injury(source.state,
                    lambda i: replace(i, conditions=i.conditions.with_condition(condition))))
        injury = source.state.roster.participant('wizard').state.injury
        for entry, total, values in ((WoundEntryId.STOMACH_BLOW, 6, (1, 5)),
            (WoundEntryId.CRUSHED_RIB, 10, (5, 5)), (WoundEntryId.TORN_LEG, 13, (6, 7)),
            (WoundEntryId.SHATTERED_KNEE, 17, (7, 10))):
            bad = replace(injury.wounds[-1], entry_id=entry, table_total=total, roll_values=values)
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                replace(source, state=with_wizard_injury(source.state,
                    lambda i: replace(i, wounds=(i.wounds[0], bad))))
        extra = replace(injury.wounds[-1], sequence=3, roll_values=(3, 3, 3))
        with self.assertRaises(ValueError):
            replace(source, state=with_wizard_injury(source.state, lambda i: replace(i,
                wounds=(*i.wounds, extra), active_wound_effects=(*i.active_wound_effects, prone(3), terrain(3)))))

    def test_first_attack_or_foreign_previous_stand_cannot_supply_new_wound(self):
        stopped, source = actual()
        first = next(s.result for s in stopped.steps if isinstance(s.result, NpcRosterChampionAttackResult))
        with self.assertRaises(ValueError): replace(source, wound_attack=first)
        old = source.previous_stand
        foreign_source = replace(old.source, state=replace(old.source.state,
            wizard=replace(old.source.state.wizard, caster=replace(old.source.state.wizard.caster,
                id='foreign:caster'))))
        from towr.rules.npc_roster_leg_spasm_resolution import stand_npc_roster_leg_spasm
        foreign = stand_npc_roster_leg_spasm(foreign_source)
        with self.assertRaises(ValueError): replace(source, previous_stand=foreign)

    def test_daily_day_roll_prefix_and_current_consumed_history_are_exact(self):
        _, source = actual()
        state = source.state
        champion = state.champion_attack
        alternatives = (
            detached(state, champion_attack=detached(champion,
                daily_wounds=detached(champion.daily_wounds, day_id='foreign:day'))),
            replace(state, champion_attack=replace(champion, consumed_wound_roll_ids=tuple(reversed(champion.consumed_wound_roll_ids)))),
            replace(state, consumed_execution_ids=(*state.consumed_execution_ids, 'unrelated:execution')),
            detached(state, champion_attack=replace(champion, consumed_execution_ids=(*champion.consumed_execution_ids, 'unrelated:execution'))),
        )
        for bad in alternatives:
            with self.subTest(state=bad), self.assertRaises(ValueError): replace(source, state=bad)

    def test_current_magic_and_placement_cannot_hide_behind_equal_injury(self):
        _, source = actual()
        state = source.state
        destination = next(z for z in state.spatial_state.graph.zone_ids if z != 'arena')
        moved = tuple(replace(p, zone_id=destination) if p.entity_id == 'ally' else p
                      for p in state.spatial_state.placements)
        alternatives = (replace(state, wizard=replace(state.wizard, magic_state=WizardMagicState(1))),
            replace(state, spatial_state=replace(state.spatial_state, placements=moved)),
            replace(state, spatial_state=replace(state.spatial_state, gave_ground_entity_ids=('ally',))))
        for bad in alternatives:
            self.assertEqual(bad.roster.participant('wizard').state.injury,
                             state.roster.participant('wizard').state.injury)
            with self.assertRaises(ValueError): replace(source, state=bad)

    def test_clock_and_scheduler_receipt_delta_cannot_be_forged(self):
        _, source = actual()
        state = source.state
        alternatives = (detached(state, round_state=replace(state.round_state, round_number=3)),
            detached(state, round_state=replace(state.round_state, active_turn=None)),
            detached(state, wound_turn_end_receipts=state.wound_turn_end_receipts[:-1]),
            detached(state, wound_turn_end_receipts=(*state.wound_turn_end_receipts, state.wound_turn_end_receipts[-1])))
        for bad in alternatives:
            with self.subTest(state=bad), self.assertRaises(ValueError): replace(source, state=bad)
        receipt = state.wound_turn_end_receipts[-1]
        for changes in ({'actor_id': 'ally'}, {'round_number': 1}):
            bad = detached(state, wound_turn_end_receipts=(*state.wound_turn_end_receipts[:-1],
                detached(receipt, **changes)))
            with self.assertRaises(ValueError): replace(source, state=bad)

    def test_prior_k1_and_boolean_sources_are_readmitted_before_equality(self):
        _, source = actual()
        previous = source.previous_stand
        bad = detached(previous, source=detached(previous.source, underlying_cause_allows_removal=1))
        self.assertEqual(bad, previous)
        with self.assertRaises(TypeError): replace(source, previous_stand=bad)
        bad = detached(previous, stand=detached(previous.stand,
            state=replace(previous.stand.state, free_move_used_entity_ids=())))
        with self.assertRaises(ValueError): replace(source, previous_stand=bad)

    def test_detached_current_bool_and_enum_aliases_are_not_laundered(self):
        _, source = actual()
        for field, value in (('effect_resolved', 1), ('treated', 0),
                             ('entry_id', WoundEntryId.LEG_SPASM.value),
                             ('origin', WoundRecordOrigin.TABLE_ROLL.value)):
            bad = deepcopy(source.state)
            wound = bad.roster.participant('wizard').state.injury.wounds[-1]
            object.__setattr__(wound, field, value)
            self.assertEqual(bad, source.state)
            with self.subTest(field=field), self.assertRaises(TypeError): replace(source, state=bad)
            self.assertIs(type(getattr(wound, field)), type(value))

    def test_attack_context_and_full_source_are_readmitted_without_replay(self):
        _, source = actual()
        bad = deepcopy(source.wound_attack)
        object.__setattr__(bad.source.attack.stationary_wounds, 'no_external_condition_sources', 1)
        self.assertEqual(bad, source.wound_attack)
        with self.assertRaises(TypeError): replace(source, wound_attack=bad)
        bad = deepcopy(source.wound_attack)
        object.__setattr__(bad.source.state.champion_attack.daily_wounds, 'day_id', 'foreign:day')
        with self.assertRaises(ValueError): replace(source, wound_attack=bad)

    def test_pending_and_executed_slot_do_not_admit_free_stand(self):
        _, source = actual()
        state = source.state
        for name in ('pending_movement', 'pending_miscast', 'pending_interruption',
                     'pending_minion_attack', 'pending_miscast_continuation'):
            with self.subTest(name=name), self.assertRaises((TypeError, ValueError)):
                replace(source, state=detached(state, **{name: object()}))
        turn = deepcopy(state.round_state.active_turn)
        object.__setattr__(turn.action_slots[0], 'execution', object())
        with self.assertRaises((TypeError, ValueError)):
            replace(source, state=detached(state, round_state=detached(state.round_state, active_turn=turn)))

    def test_result_rejects_forged_primitive_even_after_transport(self):
        _, source = actual()
        result = stand(source)
        for bad in (detached(result.stand, state=source.state.spatial_state),
            detached(result.stand, target_conditions=result.stand.previous_target_conditions),
            detached(result.stand, applied_rule_ids=('wrong:rule',))):
            with self.assertRaises(ValueError): Result(source, bad)
        for bad in (None, {}, source):
            with self.assertRaises(TypeError): Result(source, bad)

    def test_apply_checks_full_source_and_rejects_repeat_without_mutation(self):
        _, source = actual()
        result = stand(source)
        before = deepcopy(source)
        for bad in (result.state, replace(source.state,
            consumed_execution_ids=(*source.state.consumed_execution_ids, 'foreign'))):
            with self.assertRaises(ValueError): apply(bad, result)
        with self.assertRaises(TypeError): apply(None, result)
        with self.assertRaises(TypeError): apply(source.state, source)
        self.assertEqual(source, before)

    def test_multiple_prior_causes_and_superficial_history_keep_order_after_one_new_wound(self):
        # Explicitly authored older prefix; new stand48, incoming attack and scheduler are real.
        from tests.unit.test_m8_leg_spasm_stand import leg, superficial
        from tests.unit.test_m8_stationary_wound_shooting import prepare
        from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
        from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
        from towr.rules.npc_roster_leg_spasm_resolution import stand_npc_roster_leg_spasm
        from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
        from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
        from towr.rules.npc_wound_turn_end import end_npc_wound_turn
        _, source = actual()
        original_prior = source.previous_stand.source
        authored = with_wizard_injury(original_prior.state, lambda injury: replace(injury,
            wounds=(*injury.wounds, leg(2, fixed=True), superficial(3)),
            active_wound_effects=(terrain(2), prone(1), terrain(1), prone(2))))
        prior = stand_npc_roster_leg_spasm(replace(original_prior, state=authored))
        old_injury = prior.state.roster.participant('wizard').state.injury
        before_attack = with_wizard_injury(source.wound_attack.source.state, lambda _: old_injury)
        attack_request = prepare(before_attack, request_id='multi-prefix:attack')
        dice = Dice((1, 2, 3, 10, 10, 10, 1, 2, 3, 3))
        attack = NpcRosterChampionAttackResult(attack_request,
            execute_npc_champion_attack(attack_request.attack, dice))
        dice.exhausted()
        current = end_npc_wound_turn(NpcWoundTurnEndRequest('multi-prefix:end', attack.state, 'enemy')).state
        current = start_npc_roster_turn(NpcRosterTurnStartRequest('multi-prefix:start', current, 'wizard',
            source.state.round_state.active_turn.action_slots[0].declaration)).state
        request = Request('multi-prefix:stand', current, 'wizard', False, True, prior, attack)
        result = stand(request)
        injury = result.state.roster.participant('wizard').state.injury
        self.assertEqual(prior.removed_effects, (prone(1), prone(2)))
        self.assertEqual(result.removed_effects, (prone(4),))
        self.assertEqual(injury.active_wound_effects, (terrain(2), terrain(1), terrain(4)))
        self.assertEqual(injury.wounds[:3], old_injury.wounds)
        self.assertEqual(injury.wounds[-1].roll_values, (1, 2, 3, 3))
        self.assertEqual(result.state.spatial_state.free_move_used_entity_ids, ('wizard',))

    def test_detached_protection_fact_and_lifecycle_outcome_keep_strict_types(self):
        _, source = actual()
        bad = deepcopy(source.wound_attack)
        object.__setattr__(bad.source.attack.preparation.protection.source_request, 'defender_is_aware', 1)
        self.assertEqual(bad, source.wound_attack)
        with self.assertRaises(TypeError): replace(source, wound_attack=bad)
        bad = deepcopy(source.wound_attack)
        outcome = bad.attack.completion.outcome
        object.__setattr__(bad.attack.completion, 'outcome', outcome.value)
        self.assertEqual(bad, source.wound_attack)
        with self.assertRaises((TypeError, ValueError)): replace(source, wound_attack=bad)

    def test_detached_attacker_and_defender_traces_reject_equal_value_scalar_aliases(self):
        # Second Protection rolls one success; the attack still inflicts Wound9.
        # Both Tests now have an actual initial 1, making True equality measurable.
        values = (*VALUES[:19], 1, *VALUES[20:])
        _, source = actual(values=values)
        before = deepcopy(source)
        for side in ('attacker_test', 'defender_test'):
            for field in ('quality', 'initial_values', 'final_values'):
                bad = deepcopy(source.wound_attack)
                trace = getattr(bad.attack.execution.resolution.attack, side).trace
                previous = getattr(trace, field)
                if field == 'quality':
                    replacement = previous.value
                else:
                    self.assertEqual(previous[0], 1)
                    replacement = (True, *previous[1:])
                object.__setattr__(trace, field, replacement)
                self.assertEqual(bad, source.wound_attack)
                with self.subTest(side=side, field=field), self.assertRaises((TypeError, ValueError)):
                    replace(source, wound_attack=bad)
                self.assertIs(getattr(trace, field), replacement)
        self.assertEqual(source, before)


if __name__ == '__main__':
    unittest.main()
