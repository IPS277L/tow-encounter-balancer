"""One representative spawn path preserves an actual one-way Pistol fallback."""
from dataclasses import replace
from pathlib import Path
from random import Random
import unittest

from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.pc_melee_models import PcBackupWeaponPolicy, PcMeleeWeapon, PcWeaponHand
from towr.domain.pc_melee_result_models import PcAttackProof, PcBackupWeaponDrawProof
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def process_request():
    example = Path(__file__).resolve().parents[2] / 'docs/examples/m58/pc-melee-simulation.request.json'
    request = parse_pc_melee_simulation_request(example.read_bytes()).request
    scenario = replace(request.scenario, party=tuple(replace(member,
        backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.SWORD, PcWeaponHand.LEFT))
        if member.actor_id == 'pc1' else member for member in request.scenario.party))
    return replace(request, scenario=scenario, trials=3)


class PcPistolBackupProcessTests(unittest.TestCase):
    def test_actual_draw_and_owned_gun_match_spawn_records_and_summary(self):
        request = process_request()
        journals = tuple(run_pc_melee_scenario(request.scenario,
            Random(request.seed_for(index))) for index in range(request.trials))
        drawn = []
        for journal in journals:
            for position, step in enumerate(journal.steps):
                if type(step.proof) is not PcBackupWeaponDrawProof:
                    continue
                drawn.append((journal, step))
                actor = step.proof.actor_id
                self.assertEqual(step.source.participant(actor).ranged,
                    step.state.participant(actor).ranged)
                self.assertEqual(step.state.participant(actor).ranged,
                    journal.state.participant(actor).ranged)
                own_followups = tuple(later for later in journal.steps[position+1:]
                    if type(later.proof) is PcAttackProof and later.proof.request.actor_id == actor)
                self.assertTrue(own_followups)
                self.assertTrue(all(later.proof.ranged_shot is None for later in own_followups))
                self.assertFalse(any(type(later.proof) is PcRangedReloadProof
                    and later.proof.request.actor_id == actor for later in journal.steps[position+1:]))
        # These seeds were checked natively: the representative actually draws,
        # rather than merely serializing an unused backup policy.
        self.assertTrue(drawn)
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request, workers=2, batch_size=1)
        self.assertEqual(parallel, sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),
            summarize_pc_melee_simulation(sequential))
        for record, journal in zip(parallel.records, journals, strict=True):
            self.assertEqual(record.source_scenario, request.scenario)
            self.assertEqual(record.source_scenario.participant('pc1').backup_weapon_policy,
                request.scenario.participant('pc1').backup_weapon_policy)
            self.assertEqual(record.source_scenario.participant('pc1').pc.ranged,
                request.scenario.participant('pc1').pc.ranged)
            self.assertEqual(record.executed_actions, journal.executed_actions)
            self.assertFalse(hasattr(record, 'steps'))


if __name__ == '__main__':
    unittest.main()
