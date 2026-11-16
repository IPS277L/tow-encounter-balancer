"""Observed automatic PC shooting, Help and reload have separate budgets."""
from dataclasses import replace
import unittest

from tests.unit.test_generated_ranged_statistics import Ten
from tests.unit.test_pc_ranged_advice import ranged_source,shooting_help_source
from tests.support.pc_tactics_fixtures import automatic_source
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_ranged_statistics import PcRangedCount,validate_pc_ranged_counts


class PcRangedStatisticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=run_pc_melee_simulation(PcMeleeSimulationRequest(shooting_help_source(),42,2),
            rng_factory=lambda seed:Ten())
        cls.summary=summarize_pc_melee_simulation(cls.result)

    def test_bonus_help_is_not_a_shot_or_an_additional_action(self):
        rows=(PcRangedCount('pc1',0,0,1,1,0,0),PcRangedCount('pc2',1,0,0,0,0,0))
        for record in self.result.records:
            self.assertEqual(record.pc_ranged_counts,rows)
            self.assertEqual(record.executed_actions,3) # Help, shot, NPC Attack.
        self.assertEqual(self.summary.pc_ranged_counts,
            (PcRangedCount('pc1',0,0,2,2,0,0),PcRangedCount('pc2',2,0,0,0,0,0)))
        self.assertIsNot(self.result.records[0].pc_ranged_counts,self.result.records[1].pc_ranged_counts)

    def test_empty_reload_contributions_are_observed_without_invented_shots(self):
        result=run_pc_melee_simulation(PcMeleeSimulationRequest(ranged_source(rounds=4),42,2),
            rng_factory=lambda seed:Ten())
        for record in result.records:
            self.assertEqual(record.pc_ranged_counts,(PcRangedCount('pc1',1,0,0,0,2,0),))
        self.assertEqual(summarize_pc_melee_simulation(result).pc_ranged_counts,
            (PcRangedCount('pc1',2,0,0,0,4,0),))

    def test_source_order_zero_rows_and_typed_bonus_counts_are_mandatory(self):
        source=self.result.source_request.scenario
        for rows in (None,(),[],self.result.records[0].pc_ranged_counts[::-1],
                (PcRangedCount('foreign',0,0,0,0,0,0),)):
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                validate_pc_ranged_counts(rows,source,started_rounds=1,actions=3,help_counts=())
        validate_pc_ranged_counts(tuple(PcRangedCount(p.actor_id,0,0,0,0,0,0) for p in source.party),
            source,started_rounds=1,actions=0,help_counts=())
        with self.assertRaises(ValueError):
            validate_pc_ranged_counts((),automatic_source(),started_rounds=1,actions=0,help_counts=())
        for values in ((True,0,0,0,0,0),(0,1,0,0,0,0),(0,0,0,1,0,0),(0,0,0,0,-1,0)):
            with self.subTest(values=values),self.assertRaises(ValueError):
                PcRangedCount('pc1',*values)

    def test_trial_and_summary_reject_cross_actor_help_and_action_forgery(self):
        record=self.result.records[0]
        rows=record.pc_ranged_counts
        for bad in (None,rows[::-1],
                (replace(rows[0],shooting_help_tests=2),rows[1]),
                (rows[0],replace(rows[1],bonus_shots=1)),
                (replace(rows[0],weapon_swaps=3),rows[1])):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                replace(record,pc_ranged_counts=bad)
        for bad in (None,self.summary.pc_ranged_counts[::-1],
                (replace(self.summary.pc_ranged_counts[0],shooting_help_tests=3),self.summary.pc_ranged_counts[1])):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                replace(self.summary,pc_ranged_counts=bad)


if __name__=='__main__':
    unittest.main()
