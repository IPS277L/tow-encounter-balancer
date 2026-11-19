"""Only observed Duellist actions may extend the ordinary round budget."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch
from jsonschema import ValidationError

from tests.support.magic_weapon_battles import magic_battle, native_document, Threes
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request,encode_pc_melee_simulation_result
from towr.adapters.pc_melee_json_schema import validate_pc_melee_simulation_document
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_extra_attack_statistics import PcExtraAttackCount
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest,PcMeleeSimulationResult
from towr.simulation.pc_melee_models import PcHelpActionCount,validate_automatic_action_budget
from towr.simulation.pc_melee_models import PcNpcExtraAttackCount,validate_npc_extra_attack_counts
from towr.simulation.pc_melee_models import (
    PcNpcHelpActionCount,PcNpcRecoverActionCount,validate_npc_action_budget,
)
from towr.simulation.pc_melee_simulation import run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class DuellistStatisticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=magic_battle('duellist_blades',pc_ws=1,npc_ws=6)
        cls.result=run_pc_melee_scenario(cls.source,Threes())
        cls.request=PcMeleeSimulationRequest(cls.source,42,1)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=cls.result):
            cls.record=run_pc_melee_trial(cls.request,0)
        cls.summary=summarize_pc_melee_simulation(PcMeleeSimulationResult(cls.request,(cls.record,)))

    def test_two_missed_attacks_and_the_npc_turn_are_three_real_actions(self):
        self.assertEqual(self.record.executed_actions,3)
        self.assertEqual(self.record.pc_extra_attack_counts,(PcExtraAttackCount('pc',1),))
        self.assertEqual(self.summary.pc_extra_attack_trial_count,1)
        self.assertEqual(self.summary.pc_extra_attack_counts,(PcExtraAttackCount('pc',1),))
        self.assertEqual(self.summary.total_action_count,3)

    def test_missing_or_inflated_observations_cannot_create_an_action_budget(self):
        for changes in (dict(pc_extra_attack_counts=None),
                dict(pc_extra_attack_counts=(PcExtraAttackCount('pc',0),)),
                dict(pc_extra_attack_counts=(PcExtraAttackCount('pc',2),)),
                dict(executed_actions=4)):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(self.record,**changes)

    def test_counts_require_exact_types_and_the_ordered_whole_party(self):
        for counts in ((),(PcExtraAttackCount('other',1),),[PcExtraAttackCount('pc',1)],(object(),)):
            with self.subTest(counts=counts),self.assertRaises((ValueError,TypeError)):
                replace(self.record,pc_extra_attack_counts=counts)
        forged=deepcopy(self.record)
        object.__setattr__(forged.pc_extra_attack_counts[0],'count',True)
        self.assertEqual(forged,self.record)
        with self.assertRaises(TypeError):
            replace(forged)

    def test_summary_requires_the_actual_union_of_extra_attack_trials(self):
        for changes in (dict(pc_extra_attack_trial_count=None),dict(pc_extra_attack_trial_count=True),
                dict(pc_extra_attack_trial_count=0),dict(pc_extra_attack_trial_count=2),
                dict(pc_extra_attack_counts=(PcExtraAttackCount('pc',2),)),
                dict(total_action_count=4)):
            with self.subTest(changes=changes),self.assertRaises((ValueError,TypeError)):
                replace(self.summary,**changes)

    def test_a_pair_cannot_share_its_standard_attack_with_another_support_action(self):
        with self.assertRaisesRegex(ValueError,'same actor turn'):
            validate_automatic_action_budget((PcHelpActionCount('pc',1),),
                self.record.ally_recover_action_counts,self.source,started_rounds=1,
                pc_extra_counts=self.record.pc_extra_attack_counts)

    def test_an_npc_pair_cannot_borrow_the_players_unused_turn_for_recover(self):
        with self.assertRaisesRegex(ValueError,'same actor turn'):
            validate_npc_action_budget((PcNpcExtraAttackCount('npc',1),),
                (PcNpcHelpActionCount('npc',0),),(PcNpcRecoverActionCount('npc',1),),started_rounds=1)

    def test_current_json_reports_observed_counts_without_old_source_placeholders(self):
        command=parse_pc_melee_simulation_request(json.dumps(native_document(self.source)))
        document=json.loads(encode_pc_melee_simulation_result(command,self.summary))
        self.assertEqual(document['summary']['pc_extra_attack_counts'],[dict(actor_id='pc',count=1)])
        self.assertEqual(document['summary']['pc_extra_attack_trial_count'],1)
        for field in ('pc_extra_attack_counts','pc_extra_attack_trial_count'):
            malformed=deepcopy(document)
            del malformed['summary'][field]
            with self.subTest(field=field),self.assertRaises(ValidationError):
                validate_pc_melee_simulation_document(malformed,'result')
        ordinary=magic_battle('trickster_blade')
        with self.assertRaises(ValueError):
            replace(self.record,source_scenario=ordinary)
        observation=replace(self.record,source_scenario=ordinary,
            pc_extra_attack_counts=None,executed_actions=2)
        summary=summarize_pc_melee_simulation(PcMeleeSimulationResult(
            PcMeleeSimulationRequest(ordinary,42,1),(observation,)))
        command=parse_pc_melee_simulation_request(json.dumps(native_document(ordinary)))
        ordinary_document=json.loads(encode_pc_melee_simulation_result(command,summary))
        self.assertNotIn('pc_extra_attack_counts',ordinary_document['summary'])
        self.assertNotIn('pc_extra_attack_trial_count',ordinary_document['summary'])

    def test_a_generated_npc_needs_the_actual_duellist_source(self):
        ordinary=magic_battle('trickster_blade',npc_magic=True)
        actor=ordinary.enemy_activation_order[0]
        with self.assertRaises(ValueError):
            validate_npc_extra_attack_counts((PcNpcExtraAttackCount(actor,1),),ordinary,
                trials=1,extra_trials=1,actions=3,started_rounds=1)


if __name__=='__main__':
    unittest.main()
