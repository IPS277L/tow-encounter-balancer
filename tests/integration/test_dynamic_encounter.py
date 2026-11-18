from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from dataclasses import replace
from pathlib import Path
from random import Random
import unittest
from threading import Event
from unittest.mock import patch

from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.application.dynamic_encounter import DynamicEncounterRequest, NpcSearchSpace, search_dynamic_encounter
from towr.application.dynamic_encounter import DynamicEncounterCancelled, validate_dynamic_encounter_result
from towr.domain.generated_npc_models import GeneratedAbility, GeneratedNpc, GeneratedWeapon
from towr.domain.condition_models import Condition
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_melee_models import PcMeleeWeapon, validate_pc_melee_scenario_admission
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def request(**changes):
    source = parse_pc_melee_simulation_request(Path('docs/examples/m10/pc-melee-simulation.request.json').read_bytes()).request.scenario
    return replace(DynamicEncounterRequest(source.party, source.facts, source.day_id,
        NpcSearchSpace(weapon_count=(1,), allowed_talents=()), 1, 1, .6, 2., 42, 4, 1, 2, 2, 8, 3,
        NpcDefeatDisposition.KILLED), **changes)


class DynamicEncounterTests(unittest.TestCase):
    def test_cancellation_before_execution_returns_no_partial_report(self):
        with patch('towr.application.dynamic_encounter.Random.randint') as roll:
            with self.assertRaises(DynamicEncounterCancelled):
                search_dynamic_encounter(request(),cancel_requested=lambda:True)
            roll.assert_not_called()

    def test_cancellation_inside_dice_stops_without_more_rolls(self):
        cancel=Event()
        def first_roll(*args):cancel.set();return 1
        with patch('towr.application.dynamic_encounter.Random.randint',side_effect=first_roll) as roll:
            with self.assertRaises(DynamicEncounterCancelled):
                search_dynamic_encounter(request(),cancel_requested=cancel.is_set)
            self.assertEqual(roll.call_count,1)

    def test_non_cancelled_callback_preserves_full_seeded_result(self):
        source=request()
        self.assertEqual(search_dynamic_encounter(source),search_dynamic_encounter(source,cancel_requested=lambda:False))

    def test_builder_derives_values_and_identity_does_not_select_effects(self):
        npc = GeneratedNpc(4, 1, 3, 2, 5, 4, initial_generated_weapons(GeneratedWeapon.DAGGER), light_loadout(light=True, shield=False),
            (GeneratedAbility.DRAINED_ON_HIT,),defence=4)
        a, b = npc.participant('a'), npc.participant('b')
        self.assertEqual(a.definition.attacks, b.definition.attacks)
        attack = a.definition.attacks[0]
        self.assertEqual((attack.test_profile.dice, attack.test_profile.threshold,
            attack.test_profile.maximum_dice, attack.damage.base), (4, 5, 8, 0))
        self.assertEqual(a.definition.resilience.total, 4)
        self.assertEqual(len(attack.secondary_effects), 1)
        self.assertEqual(a.definition.protection[0].test_profile.maximum_dice, 8)
        self.assertEqual(a.definition.protection[1].test_profile.maximum_dice, 4)

    def test_unsupported_components_rejected(self):
        for change in ({'weapon': ('axe',)}, {'melee': (True,)}, {'strength': (0,)},
                {'athletics': (7,)}, {'abilities': (('unknown',),)}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                NpcSearchSpace(weapon_count=(1,), **change)

    def test_budget_and_targets_rejected_before_simulation(self):
        for change in ({'max_total_trials': 7}, {'target_win_rate': float('nan')},
                {'target_rounds': 0}, {'minimum_npcs': 2}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                request(**change)

    def test_new_profiles_at_fixed_count_full_execution_and_replay(self):
        source = request()
        first = search_dynamic_encounter(source)
        self.assertEqual(first, search_dynamic_encounter(source))
        self.assertEqual(len(first.explored), 4)
        self.assertEqual(len({c.composition for c in first.explored}), 4)
        self.assertTrue(all(len(c.composition) == 1 for c in first.explored))
        self.assertEqual(first.total_trials, 8)
        for candidate in first.explored + first.validations:
            scenario = candidate.summary.source_request.scenario
            validate_pc_melee_scenario_admission(scenario)
            self.assertEqual(scenario.enemies[0], candidate.composition[0].participant('generated-npc:1'))
            low, high = candidate.win_interval_95
            self.assertTrue(0 <= low <= candidate.win_rate <= high <= 1)
            self.assertTrue(candidate.rounds_interval_95[0] <= candidate.mean_started_rounds <= candidate.rounds_interval_95[1])
        explored_seeds = {c.summary.source_request.master_seed for c in first.explored}
        self.assertFalse(explored_seeds & {c.summary.source_request.master_seed for c in first.validations})

    def test_single_configuration_stops_without_filling_duplicates(self):
        space = NpcSearchSpace(weapon_count=(1,), weapon_skill=(2,),strength=(2,),toughness=(2,),agility=(2,),
            melee=(4,),athletics=(4,),defence=(4,),weapon=(GeneratedWeapon.STAFF,),
            armour=(None,),shield=(None,),abilities=((),),allowed_talents=(),brawn=(4,))
        result = search_dynamic_encounter(request(space=space))
        self.assertEqual(len(result.explored), 1)
        self.assertTrue(result.proposal_limit_reached)
        self.assertEqual(result.total_trials, 3)

    def test_drained_component_admitted_and_executed_without_catalog_id(self):
        source = request(space=replace(NpcSearchSpace(weapon_count=(1,), ),weapon=(GeneratedWeapon.STAFF,),
            abilities=((GeneratedAbility.DRAINED_ON_HIT,),)),
            max_candidates=1, top_k=1, max_total_trials=3)
        result = search_dynamic_encounter(source)
        self.assertEqual(result.explored[0].summary.outcome_counts.unsupported_path, 0)
        self.assertEqual(len(result.explored[0].summary.source_request.scenario.enemies[0].definition.attacks[0].secondary_effects), 1)

    def test_wrong_simulator_source_rejected(self):
        def wrong(source):
            other = replace(source, master_seed=source.master_seed ^ 1)
            return summarize_pc_melee_simulation(run_pc_melee_simulation(other))
        with self.assertRaisesRegex(ValueError, 'another candidate'):
            search_dynamic_encounter(request(), wrong)

    def test_generated_drained_has_actual_independent_condition_source(self):
        source = request()
        pc = source.party[0]
        pc = replace(pc, pc=replace(pc.pc, weapon_skill=1, strength=1, toughness=20,
            defence=2, weapon=PcMeleeWeapon.STAFF), near_miss_policy=None, glorious_policy=None)
        source = replace(source, party=(pc,), max_rounds=1, target_rounds=1)
        npc = GeneratedNpc(10, 1, 20, 1, 6, 2, initial_generated_weapons(GeneratedWeapon.STAFF), light_loadout(light=False, shield=False),
            (GeneratedAbility.DRAINED_ON_HIT,),defence=2)
        battle = run_pc_melee_scenario(source.scenario((npc,), 'actual-effect'), Random(42))
        state = battle.state.participant(pc.actor_id)
        self.assertTrue(state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(len(state.hit_condition_sources), 1)

    def test_mutation_changes_one_allowed_component(self):
        space, rng = NpcSearchSpace(weapon_count=(1,), ), Random(7)
        npc = space.sample(rng)
        mutated = space.mutate(npc, rng)
        # Changing an implement also changes the actor preparation it needs;
        # both facts are one admitted equipment mutation, not two independent edits.
        self.assertNotEqual(mutated.weapons,npc.weapons)
        self.assertNotEqual(mutated.ranged,npc.ranged)
        self.assertEqual(replace(npc,weapons=mutated.weapons,ranged=mutated.ranged),mutated)
        self.assertTrue(space.contains(mutated))
        from towr.domain.generated_npc_models import GENERATED_RANGED_WEAPONS,validate_generated_definition
        self.assertEqual(mutated.ranged is not None,
            any(item.kind.value in {kind.value for kind in GENERATED_RANGED_WEAPONS}
                for item in mutated.weapons))
        validate_generated_definition(mutated.participant('mutated-source').definition)

    def test_variable_count_and_ordered_distinct_profiles(self):
        result = search_dynamic_encounter(request(minimum_npcs=1, maximum_npcs=3,
            max_candidates=5, max_total_trials=9))
        self.assertTrue(all(1 <= len(c.composition) <= 3 for c in result.explored))
        self.assertGreater(len({len(c.composition) for c in result.explored}), 1)

    def test_directed_resize_preserves_other_profiles_and_advances_plateau(self):
        source=request(minimum_npcs=1,maximum_npcs=10,max_candidates=6,
            max_total_trials=10,max_rounds=1,target_rounds=1)
        with patch('towr.application.dynamic_encounter.Random.random',return_value=.5):
            result=search_dynamic_encounter(source)
        first,second=result.explored[:2]
        self.assertEqual([len(first.composition),len(second.composition)],[6,5])
        self.assertTrue(any(first.composition[:i]+first.composition[i+1:]==second.composition
            for i in range(len(first.composition))))
        self.assertEqual(len(result.explored[3].composition),4)
        self.assertEqual(result.total_trials,10)
        validate_dynamic_encounter_result(result)


if __name__ == '__main__':
    unittest.main()
