"""Three creature loadouts use the existing PC JSON1/trials/count-search path."""
from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
import unittest
from unittest.mock import Mock,patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import validate_pc_melee_simulation_document,validate_pc_melee_balance_document
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(demigryphs=2 if balance else 1,centigors=1,white_wolf_claws=1,
        footpads=0,townsfolk=0,pc_count=2,max_rounds=2)
    source=replace(source,party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE))
        for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            dict(group_id='demigryphs',actor_ids=['demigryph1','demigryph2'],minimum_count=1,maximum_count=2),
            dict(group_id='centigors',actor_ids=['centigor1'],minimum_count=0,maximum_count=1),
            dict(group_id='white_wolf_claws',actor_ids=['white_wolf_claws1'],minimum_count=0,maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=8,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcCreatureChunkIntegrationTests(unittest.TestCase):
    def test_current_json_keeps_three_canonical_profiles_gear_and_ranges(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw['template' if balance else 'scenario'])
            self.assertEqual(raw['schema_version'],'1')
            for enemy in source.enemies:
                validate_pc_book_npc_definition(enemy.definition)
                attack,=enemy.definition.attacks
                protection,=enemy.definition.protection
                centigor=enemy.state.actor_id=='centigor1'
                wolf=enemy.state.actor_id=='white_wolf_claws1'
                self.assertEqual((attack.test_profile.dice,attack.test_profile.threshold,attack.damage.base),
                    (3 if wolf else 4,4,6 if wolf else 4 if centigor else 5))
                self.assertEqual((protection.skill,protection.test_profile.dice,protection.test_profile.threshold),
                    (Skill.ATHLETICS,4,4 if wolf else 3))
                self.assertIs(attack.hands,RangedWeaponHands.ONE_HANDED if centigor else None)
                self.assertIs(attack.range_max,RangedWeaponRange.SHORT if centigor else RangedWeaponRange.CLOSE)
                self.assertIs(enemy.state.holds_shield,centigor)
                self.assertEqual(enemy.definition.resilience.bonus,1 if centigor else 0)
                self.assertEqual(source.npc_extra_attack_actor_ids,())

    def test_wrong_printed_damage_armour_shield_or_range_rejected_before_rng(self):
        source=chunk_document()
        for index,key,value in ((0,'armour',1),(0,'shield',True),
                                (1,'shield',False),(1,'range','close'),(2,'damage',5)):
            raw=deepcopy(source)
            enemy=raw['scenario']['enemies'][index]
            if key=='armour':enemy['definition']['resilience']['bonus']=value
            elif key=='shield':enemy['holds_shield']=value
            elif key=='range':enemy['definition']['attack']['range_max']=value
            else:enemy['definition']['attack']['damage']['base']=value
            with self.subTest(index=index,key=key),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_each_new_profile_is_ineligible_for_bear_optional_extra_attack(self):
        for actor in ('demigryph1','centigor1','white_wolf_claws1'):
            raw=chunk_document()
            raw['scenario']['npc_extra_attack_actor_ids']=[actor]
            with self.subTest(actor=actor),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_real_trials_and_result_preserve_full_source_and_zero_extra_counts(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(len(result.records),2)
        self.assertGreater(summary.total_action_count,0)
        self.assertEqual(summary.total_npc_extra_attack_count,0)
        self.assertEqual(summary.npc_extra_attack_trial_count,0)
        self.assertEqual(tuple((i.actor_id,i.count) for i in summary.npc_extra_attack_counts),
            (('demigryph1',0),('centigor1',0),('white_wolf_claws1',0)))
        output=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(output,'result')
        self.assertEqual(output['request'],raw)
        self.assertFalse(hasattr(summary,'records'))

    def test_eight_count_compositions_keep_only_actual_source_npcs(self):
        raw=chunk_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(8,8))
        self.assertEqual(tuple(c.counts for c in report.candidates),tuple(product((1,2),(0,1),(0,1))))
        for candidate in report.candidates:
            source=candidate.source_request.scenario
            order=tuple(e.state.actor_id for e in source.enemies)
            self.assertEqual(tuple(i.actor_id for i in candidate.summary.npc_extra_attack_counts),order)
            self.assertEqual(source.npc_extra_attack_actor_ids,())
            self.assertEqual(candidate.summary.total_npc_extra_attack_count,0)
        output=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(output,'result')
        self.assertEqual(output['request'],raw)

    def test_cached_equal_numeric_source_alias_cannot_reach_trial_rng(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        forged=deepcopy(command.request)
        object.__setattr__(forged.scenario.enemies[-1].definition.attacks[0].damage,'base',6.0)
        self.assertEqual(forged,command.request)
        rng=Mock(side_effect=AssertionError('invalid source must not construct RNG'))
        runner=Mock(side_effect=AssertionError('invalid source must not execute'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
            with self.assertRaises(TypeError):
                run_pc_melee_trial(forged,0,rng_factory=rng)
        rng.assert_not_called()
        runner.assert_not_called()


if __name__=='__main__':
    unittest.main()
