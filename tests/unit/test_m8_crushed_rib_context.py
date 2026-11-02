"""Finite original-owner admission and refusal checks for ADR-0056."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import pickle
from random import getstate
import unittest

from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext as Context, NpcCrushedRibConsumptionWitness as Witness
from towr.domain.turn_models import CombatSide
from towr.domain.crushed_rib_test_models import CrushedRibTestPreparationRequest
from towr.domain.test_models import TestRequest, InlineProfile
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.crushed_rib_test_resolution import prepare_crushed_rib_test, resolve_crushed_rib_test


def actual_state():
    dice = Dice((1, 2, 3, 10, 10, 10, 10))
    result = run_npc_magic_scenario(admitted(wizard_side=CombatSide.OPPOSITION), dice)
    dice.exhausted()
    return result.current


class CrushedRibContextTests(unittest.TestCase):
    def setUp(self):
        self.rng = getstate()
        self.state = actual_state()

    def tearDown(self):
        self.assertEqual(getstate(), self.rng)

    def test_actual_registered_owner_is_pure_frozen_and_pickleable(self):
        before = deepcopy(self.state)
        context = Context(self.state, 'wizard', True)
        context.validate_source(self.state, 'wizard')
        self.assertEqual(self.state, before)
        self.assertEqual(pickle.loads(pickle.dumps(context)), context)
        self.assertIsNone(context.consumption)
        self.assertFalse(hasattr(context, '__dict__'))
        with self.assertRaises(FrozenInstanceError):
            context.actor_id = 'other'

    def test_explicit_fact_and_owner_role_are_required(self):
        for flag in (1, 'true', None, False):
            with self.subTest(flag=flag), self.assertRaises((TypeError, ValueError)):
                Context(self.state, 'wizard', flag)
        with self.assertRaises(ValueError):
            Context(self.state, 'enemy', True)

    def test_full_source_and_actor_are_required(self):
        context = Context(self.state, 'wizard', True)
        with self.assertRaises(ValueError):
            context.validate_source(replace(self.state, consumed_execution_ids=(*self.state.consumed_execution_ids, 'foreign')), 'wizard')
        with self.assertRaises(ValueError):
            context.validate_source(self.state, 'enemy')

    def test_missing_daily_and_lifecycle_histories_are_not_reconstructed(self):
        for name in ('daily', 'rolls'):
            state = deepcopy(self.state)
            child = state.champion_attack
            if name == 'daily':
                object.__setattr__(child.daily_wounds, 'receipts', ())
            else:
                object.__setattr__(child, 'consumed_wound_roll_ids', ())
            with self.subTest(name=name), self.assertRaises(ValueError):
                Context(state, 'wizard', True)

    def test_original_bool_integer_aliases_are_rejected_before_equality(self):
        mutations = (
            lambda s: object.__setattr__(s.round_state, 'round_number', True),
            lambda s: object.__setattr__(s.roster.participants[0].state.current_resilience, 'bonus', False),
            lambda s: object.__setattr__(s.champion_attack.daily_wounds.receipts[0].wound, 'sequence', True),
            lambda s: object.__setattr__(s.round_state.active_turn.action_slots[0], 'index', True),
        )
        for index, mutate in enumerate(mutations):
            state = deepcopy(self.state)
            mutate(state)
            with self.subTest(index=index), self.assertRaises((TypeError, ValueError)):
                Context(state, 'wizard', True)

    def test_detached_child_wizard_injury_is_readmitted_before_owner_equality(self):
        state = deepcopy(self.state)
        child_roster = deepcopy(state.champion_attack.roster)
        object.__setattr__(child_roster.participant('wizard').state.injury.wounds[0], 'sequence', True)
        self.assertEqual(child_roster, state.roster)
        object.__setattr__(state.champion_attack, 'roster', child_roster)
        with self.assertRaises(TypeError):
            Context(state, 'wizard', True)

    def test_original_list_histories_and_string_side_alias_are_rejected(self):
        for mutate in (
            lambda s: object.__setattr__(s, 'consumed_execution_ids', list(s.consumed_execution_ids)),
            lambda s: object.__setattr__(s.roster.participants[0].state, 'side', s.roster.participants[0].state.side.value),
            lambda s: object.__setattr__(next(p.state.injury.conditions for p in s.roster.participants
                if p.state.actor_id != 'wizard'), 'conditions', []),
            lambda s: object.__setattr__(s.spatial_state, 'gave_ground_entity_ids', list(s.spatial_state.gave_ground_entity_ids)),
            lambda s: object.__setattr__(s.wound_turn_end_receipts[0], 'round_number', True),
        ):
            state = deepcopy(self.state)
            mutate(state)
            with self.assertRaises((TypeError, ValueError)):
                Context(state, 'wizard', True)

    def test_k1_consumption_alone_cannot_authorize_full_owner(self):
        context = Context(self.state, 'wizard', True)
        preparation = prepare_crushed_rib_test(CrushedRibTestPreparationRequest(
            'k1-only', 'wizard', context.injury, TestRequest('test', InlineProfile(3, 5))))
        receipt = resolve_crushed_rib_test(preparation, Dice((10, 10, 10)))
        with self.assertRaises(TypeError):
            Witness(receipt, receipt)
        with self.assertRaises((TypeError, ValueError)):
            replace(context, consumption=receipt)

    def test_forged_effect_removal_without_full_witness_is_rejected(self):
        state = deepcopy(self.state)
        injury = state.roster.participant('wizard').state.injury
        object.__setattr__(injury, 'active_wound_effects', injury.active_wound_effects[:1])
        with self.assertRaises(ValueError):
            Context(state, 'wizard', True)

    def test_raw_mutation_of_context_fact_is_revalidated(self):
        context = Context(self.state, 'wizard', True)
        object.__setattr__(context, 'no_external_condition_sources', 1)
        with self.assertRaises(TypeError):
            context.validate_source(self.state, 'wizard')

    def test_actual_first_casting_witness_admits_consumed_owner(self):
        from tests.unit.test_m8_crushed_rib_casting import prepared, execute
        result, state = execute(prepared(), (10, 10, 10))
        witness = Witness(result, result.casting.crushed_rib)
        context = Context(state, 'wizard', True, witness)
        context.validate_source(state, 'wizard')
        self.assertEqual(context.injury, witness.consumption.state)
        self.assertEqual(pickle.loads(pickle.dumps(context)), context)

    def test_first_receipt_is_not_replaceable_by_a_detached_k1_trace(self):
        from tests.unit.test_m8_crushed_rib_casting import prepared, execute
        result, state = execute(prepared(), (10, 10, 10))
        receipt = result.casting.crushed_rib
        forged = deepcopy(receipt)
        object.__setattr__(forged.casting.test.trace, 'successes', False)
        self.assertEqual(forged, receipt)  # Equality alone hides bool/int aliases.
        with self.assertRaises((TypeError, ValueError)):
            Witness(result, forged)

    def test_witness_rejects_late_or_cyclic_context_before_readmission(self):
        from tests.unit.test_m8_crushed_rib_casting import prepared, execute
        result, state = execute(prepared(), (10, 10, 10))
        witness = Witness(result, result.casting.crushed_rib)
        late = deepcopy(result)
        object.__setattr__(late.source.crushed_rib_context, 'consumption', witness)
        with self.assertRaisesRegex(ValueError, 'first pending-context'):
            Witness(late, late.casting.crushed_rib)

    def test_consumed_context_cannot_lose_actual_action_history(self):
        from tests.unit.test_m8_crushed_rib_casting import prepared, execute
        result, state = execute(prepared(), (10, 10, 10))
        witness = Witness(result, result.casting.crushed_rib)
        lost = replace(state, consumed_execution_ids=tuple(
            i for i in state.consumed_execution_ids if i != result.source.casting.id))
        with self.assertRaisesRegex(ValueError, 'provenance/history'):
            Context(lost, 'wizard', True, witness)

    def test_consumed_context_cannot_change_caster_definition(self):
        from tests.unit.test_m8_crushed_rib_casting import prepared, execute
        result, state = execute(prepared(), (10, 10, 10))
        witness = Witness(result, result.casting.crushed_rib)
        changed = replace(state, wizard=replace(state.wizard, caster=replace(
            state.wizard.caster, wizard_level=state.wizard.caster.wizard_level - 1)))
        with self.assertRaisesRegex(ValueError, 'provenance/history'):
            Context(changed, 'wizard', True, witness)

    def test_every_daily_record_retains_strict_original_rolls_and_sequence(self):
        values = (1, 2, 3, 10, 10, 10, 1, *((10,) * 9), 1, 2, 3, 10, 10, 10, 1, 9)
        dice = Dice(values)
        state = run_npc_magic_scenario(admitted(wizard_side=CombatSide.OPPOSITION), dice).current
        dice.exhausted()
        Context(state, 'wizard', True)
        for mutate in (
            lambda s: object.__setattr__(s.champion_attack.daily_wounds.receipts[0].wound, 'sequence', True),
            lambda s: object.__setattr__(s.champion_attack.daily_wounds.receipts[1].wound, 'roll_values', (True, 9)),
        ):
            bad = deepcopy(state)
            mutate(bad)
            with self.assertRaises((TypeError, ValueError)):
                Context(bad, 'wizard', True)

    def test_turn_end_cannot_erase_context_after_actual_casting(self):
        from tests.unit.test_m8_crushed_rib_casting import prepared, execute
        from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
        from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result
        result, state = execute(prepared(), (10, 10, 10))
        context = Context(state, 'wizard', True, Witness(result, result.casting.crushed_rib))
        end = end_npc_wound_turn(NpcWoundTurnEndRequest('context:end', state, 'wizard', crushed_rib_context=context))
        bad = deepcopy(end)
        object.__setattr__(bad.source, 'crushed_rib_context', None)
        with self.assertRaises(ValueError):
            replace(bad)
        with self.assertRaises(ValueError):
            end_npc_wound_turn(bad.source)
        with self.assertRaises(ValueError):
            apply_npc_wound_turn_end_result(state, bad)


if __name__ == '__main__':
    unittest.main()
