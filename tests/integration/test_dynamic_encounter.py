from dataclasses import replace
from pathlib import Path
from random import Random
import unittest

from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.application.dynamic_encounter import DynamicEncounterRequest, NpcSearchSpace, search_dynamic_encounter
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
        NpcSearchSpace(), 1, 1, .6, 2., 42, 4, 1, 2, 2, 8, 3,
        NpcDefeatDisposition.KILLED), **changes)


class DynamicEncounterTests(unittest.TestCase):
    def test_builder_derives_values_and_identity_does_not_select_effects(self):
        npc = GeneratedNpc(4, 1, 3, 2, 5, 4, GeneratedWeapon.DAGGER, True,
            (GeneratedAbility.DRAINED_ON_HIT,))
        a, b = npc.participant('a'), npc.participant('b')
        self.assertEqual(a.definition.attacks, b.definition.attacks)
        attack = a.definition.attacks[0]
        self.assertEqual((attack.test_profile.dice, attack.test_profile.threshold,
            attack.test_profile.maximum_dice, attack.damage.base), (4, 5, 8, 0))
        self.assertEqual(a.definition.resilience.total, 4)
        self.assertEqual(len(attack.secondary_effects), 1)
        self.assertEqual(a.definition.protection[0].test_profile.maximum_dice, 4)

    def test_unsupported_components_rejected(self):
        for change in ({'weapon': ('axe',)}, {'melee': (True,)}, {'strength': (0,)},
                {'athletics': (7,)}, {'abilities': (('unknown',),)}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                NpcSearchSpace(**change)

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
        space = NpcSearchSpace((2,), (2,), (2,), (2,), (4,), (4,), (GeneratedWeapon.STAFF,), (False,), ((),))
        result = search_dynamic_encounter(request(space=space))
        self.assertEqual(len(result.explored), 1)
        self.assertTrue(result.proposal_limit_reached)
        self.assertEqual(result.total_trials, 3)

    def test_drained_component_admitted_and_executed_without_catalog_id(self):
        source = request(space=replace(NpcSearchSpace(), abilities=((GeneratedAbility.DRAINED_ON_HIT,),)),
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
        npc = GeneratedNpc(10, 1, 20, 1, 6, 2, GeneratedWeapon.STAFF, False,
            (GeneratedAbility.DRAINED_ON_HIT,))
        battle = run_pc_melee_scenario(source.scenario((npc,), 'actual-effect'), Random(42))
        state = battle.state.participant(pc.actor_id)
        self.assertTrue(state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(len(state.hit_condition_sources), 1)

    def test_mutation_changes_one_allowed_component(self):
        space, rng = NpcSearchSpace(), Random(7)
        npc = space.sample(rng)
        mutated = space.mutate(npc, rng)
        self.assertEqual(sum(getattr(npc, name) != getattr(mutated, name)
            for name in npc.__dataclass_fields__), 1)

    def test_variable_count_and_ordered_distinct_profiles(self):
        result = search_dynamic_encounter(request(minimum_npcs=1, maximum_npcs=3,
            max_candidates=5, max_total_trials=9))
        self.assertTrue(all(1 <= len(c.composition) <= 3 for c in result.explored))
        self.assertGreater(len({len(c.composition) for c in result.explored}), 1)


if __name__ == '__main__':
    unittest.main()
