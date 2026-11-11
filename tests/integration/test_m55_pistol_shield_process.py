"""One spawn representative preserves actual Pistol/shield reload cycles."""
from dataclasses import replace
from random import Random
import unittest

from tests.integration.test_m54_pistol_process import process_request as pistol_process_request
from tests.support.pc_shield_scenarios import shield_loadout
from tests.unit.test_m54_pistol_execution import shots, steps
from towr.domain.pc_melee_models import PcWeaponHand
from towr.domain.pc_melee_result_models import PcRecoverProof
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.pc_shield_models import PcShieldReleaseProof
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def process_request():
    request = pistol_process_request()
    scenario = request.scenario
    scenario = replace(scenario, max_rounds=12, party=tuple(replace(member,
        initial_weapon_hand=PcWeaponHand.RIGHT, shield=shield_loadout()) for member in scenario.party))
    return replace(request, scenario=scenario)


class PcPistolShieldProcessTests(unittest.TestCase):
    def test_actual_release_reload_pickup_cycles_match_indexed_spawn_records(self):
        request = process_request()
        journals = tuple(run_pc_melee_scenario(request.scenario,
            Random(request.seed_for(index))) for index in range(request.trials))
        self.assertTrue(all(steps(journal, PcRangedReloadProof) for journal in journals))
        self.assertTrue(all(steps(journal, PcShieldReleaseProof) for journal in journals))
        self.assertTrue(all(any(step.proof.result.source_request.choice.object_interaction is not None
            and step.proof.result.source_request.choice.object_interaction.object_id == 'pc1:shield'
            for step in steps(journal, PcRecoverProof)) for journal in journals))
        self.assertTrue(any(len(shots(journal)) >= 2 for journal in journals))
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request, workers=2, batch_size=1)
        self.assertEqual(parallel, sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel), summarize_pc_melee_simulation(sequential))
        for record, journal in zip(parallel.records, journals, strict=True):
            self.assertEqual(record.source_scenario, request.scenario)
            self.assertEqual(record.source_scenario.participant('pc1').shield,
                request.scenario.participant('pc1').shield)
            self.assertEqual(record.executed_actions, journal.executed_actions)
            self.assertFalse(hasattr(record, 'steps'))


if __name__ == '__main__':
    unittest.main()
