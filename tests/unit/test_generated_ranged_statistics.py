"""Actual NPC shot/Reload observations and independent source budgets."""
from dataclasses import replace
import unittest

from tests.unit.test_generated_ranged_advice import source
from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_npc_ranged_statistics import PcNpcRangedCount,validate_npc_ranged_counts


class Ten:
    def randint(self,low,high):
        if (low,high)!=(1,10):
            raise AssertionError('unexpected RNG call')
        return 10


class GeneratedRangedStatisticsTests(unittest.TestCase):
    def test_fixed_protection_help_does_not_target_a_known_reload_turn(self):
        from tests.unit.test_m63_pc_close_shooting_protection import help_scene
        from towr.domain.pc_melee_result_models import PcHelpProof,PcAttackProof
        from towr.domain.pc_help_models import pc_help_incoming_actor
        from towr.engine.pc_melee_runner import run_pc_melee_scenario
        scenario=replace(help_scene(),max_rounds=2)
        result=run_pc_melee_scenario(scenario,Ten())
        helps=[step for step in result.steps if type(step.proof) is PcHelpProof]
        self.assertEqual(len(helps),1)
        fallback=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1')
        self.assertFalse(pc_npc_ranged_weapon(fallback.source,'minion1').loaded)
        self.assertIsNone(pc_help_incoming_actor(fallback.source,scenario.party[0].help_policy))

    def test_actual_empty_reload_actions_are_separate_from_shots_in_independent_trials(self):
        scenario=source(weapon=GeneratedWeapon.PISTOL,rounds=4)
        request=PcMeleeSimulationRequest(scenario,42,2)
        result=run_pc_melee_simulation(request,rng_factory=lambda seed:Ten())
        for record in result.records:
            self.assertEqual(record.npc_ranged_counts,(PcNpcRangedCount('minion1',1,0,3),))
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.npc_ranged_counts,(PcNpcRangedCount('minion1',2,0,6),))
        self.assertEqual(result.source_request.scenario,scenario)
        self.assertIsNot(result.records[0].npc_ranged_counts,result.records[1].npc_ranged_counts)

    def test_complete_source_order_and_zero_rows_cannot_be_removed_or_invented(self):
        scenario=source()
        for counts in (None,(),[],(PcNpcRangedCount('other',0,0,0),)):
            with self.subTest(counts=counts),self.assertRaises(ValueError):
                validate_npc_ranged_counts(counts,scenario,started_rounds=1,actions=2)
        validate_npc_ranged_counts((PcNpcRangedCount('minion1',0,0,0),),scenario,
            started_rounds=1,actions=0)
        with self.assertRaises(ValueError):
            validate_npc_ranged_counts((),automatic_source(),started_rounds=1,actions=0)

    def test_counter_types_bonus_membership_and_turn_action_budgets(self):
        for args in (('minion1',True,0,0),('minion1',1,2,0),('minion1',0,0,-1)):
            with self.subTest(args=args),self.assertRaises(ValueError):
                PcNpcRangedCount(*args)
        scenario=source(weapon=GeneratedWeapon.PISTOL)
        for row,rounds,actions in ((PcNpcRangedCount('minion1',1,1,0),1,2),
                (PcNpcRangedCount('minion1',1,0,1),1,2),
                (PcNpcRangedCount('minion1',1,0,1),2,1)):
            with self.subTest(row=row,rounds=rounds),self.assertRaises(ValueError):
                validate_npc_ranged_counts((row,),scenario,started_rounds=rounds,actions=actions)

    def test_trial_and_summary_reject_cross_actor_or_impossible_observations(self):
        result=run_pc_melee_simulation(PcMeleeSimulationRequest(source(),42,1),
            rng_factory=lambda seed:Ten())
        record=result.records[0]
        summary=summarize_pc_melee_simulation(result)
        for counts in (None,(PcNpcRangedCount('pc1',0,0,0),),
                (PcNpcRangedCount('minion1',record.started_rounds+1,0,0),)):
            with self.subTest(counts=counts):
                with self.assertRaises(ValueError): replace(record,npc_ranged_counts=counts)
                with self.assertRaises(ValueError): replace(summary,npc_ranged_counts=counts)


if __name__=='__main__':
    unittest.main()
