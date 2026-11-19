"""NPC Protection belongs to its reachable target, not first alive priority."""
from dataclasses import replace
import unittest

from tests.support.magic_weapon_battles import Threes, magic_battle, run_native
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeStep
from towr.domain.test_models import Skill


def scene(*, spend=False):
    source = magic_battle('warbow', players=2, distance='medium', fate=1)
    melee = magic_battle('staff', players=2, distance='medium', fate=int(spend)).party[1]
    melee = replace(melee, pc=replace(melee.pc, melee=1,
        defence=1 if spend else 5, athletics=1 if spend else 4))
    if spend:
        melee = replace(melee, glorious_policy=replace(melee.glorious_policy,
            skills=(Skill.DEFENCE, Skill.ATHLETICS)))
    return replace(source, party=(source.party[0], melee))


def fixed_dice(seed):
    return Threes()


class ActualProtectionOwnerTests(unittest.TestCase):
    def test_actual_defender_fate_counts_have_process_parity(self):
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
        request = PcMeleeSimulationRequest(scene(spend=True), 42, 1)
        sequential = run_pc_melee_simulation(request, rng_factory=fixed_dice)
        parallel = run_pc_melee_simulation_parallel(request, workers=2,
            batch_size=1, rng_factory=fixed_dice)
        self.assertEqual(parallel, sequential)
        counts = {row.actor_id: row.count for row in sequential.records[0].glorious_spend_counts}
        self.assertEqual(counts, {'pc': 0, 'ally:1': 1})

    def test_npc_protection_decline_and_spend_use_the_actual_reachable_pc(self):
        for spend in (False, True):
            with self.subTest(spend=spend):
                source = scene(spend=spend)
                result = run_native(self, source)
                attack, = (step for step in result.steps if type(step.proof) is PcAttackProof
                    and step.proof.request.actor_id == 'generated-npc:1')
                self.assertEqual(attack.proof.request.target_id, 'ally:1')
                self.assertFalse(attack.source.participant('pc').injury.dead)
                self.assertEqual(result.state.participant('pc').fate, source.party[0].fate)
                self.assertEqual(result.state.participant('pc').injury,
                    attack.source.participant('pc').injury)
                proof = attack.proof
                if spend:
                    self.assertIsNone(proof.fate_decline)
                    self.assertEqual(proof.glorious.source_request.state.actor_id, 'ally:1')
                    self.assertEqual(len(result.state.participant('ally:1').fate.spends), 1)
                else:
                    self.assertIsNone(proof.glorious)
                    self.assertEqual(proof.fate_decline.actor_id, 'ally:1')
                    with self.assertRaises(ValueError):
                        PcMeleeStep(attack.source, replace(proof, fate_decline=replace(
                            proof.fate_decline, actor_id='pc')))
