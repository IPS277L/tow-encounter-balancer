"""Current source wire and real deterministic Rapid Reload process execution.

Literal dice make these contract/budget checks reproducible; they are not a
Monte Carlo accuracy sample or a claim about the probability of victory.
"""
import json
from dataclasses import replace
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_talent_rapid_reload_execution import pc_source,npc_source
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import (
    parse_pc_melee_simulation_request,encode_pc_melee_simulation_result,
)
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def pc_literal_dice(seed):
    return ScriptedD10([1,1,1]+[10]*11)


def npc_literal_dice(seed):
    return ScriptedD10([10]*6+[1,1,1]+[10]*7)


def command(source,*,trials=1):
    raw=dict(schema_version='1',kind='pc_melee_simulation',request_id='rapid:wire',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
        simulation=dict(master_seed='42',trials=trials),execution=dict(mode='sequential'))
    parsed=parse_pc_melee_simulation_request(json.dumps(raw))
    if parsed.request.scenario!=source:
        raise AssertionError('current source roundtrip changed the actor/weapon/Talent')
    return parsed


class RapidReloadJsonTests(unittest.TestCase):
    def test_dynamic_search_report_preserves_generated_talent_and_observed_counters(self):
        from tests.integration.test_generated_talents_json import talent_request
        from tests.support.talent_sources import paid_talent
        from towr.domain.talent_catalog import TalentId
        from towr.application.dynamic_encounter import NpcSearchSpace
        from towr.adapters.dynamic_encounter_json import (
            parse_dynamic_encounter_request,execute_dynamic_encounter,encode_dynamic_encounter_result,
        )
        raw=talent_request()
        raw['search_space'].update(weapon=['pistol'],initial_loaded=[False],
            ballistic_skill=[4],shooting=[4],initiative=[3],dexterity=[5],awareness=[4],
            toughness=[20],shield=[None],allowed_talents=['rapid_reload'])
        parsed=parse_dynamic_encounter_request(json.dumps(raw))
        sampled=parsed.request.space.sample(Random(0))
        npc=replace(sampled,talents=(paid_talent(TalentId.RAPID_RELOAD),))
        self.assertTrue(parsed.request.space.contains(npc))
        # Fix only the permitted component selection. Both exploration and
        # independent validation execute actual fresh battles with their RNG.
        with patch.object(NpcSearchSpace,'sample',return_value=npc):
            result=execute_dynamic_encounter(parsed)
        report=json.loads(encode_dynamic_encounter_result(parsed,result))
        for candidate in (*report['explored'],*report['validations']):
            self.assertEqual(candidate['npcs'][0]['talents'][0]['id'],'rapid_reload')
            self.assertEqual(len(candidate['rapid_reload_counts']),1)
            row=candidate['rapid_reload_counts'][0]
            ranged,=candidate['npc_ranged_counts']
            self.assertEqual(row['actor_id'],ranged['actor_id'])
            self.assertLessEqual(row['count'],ranged['reload_actions'])
            replay=dict(candidate['replay'])
            native=parse_pc_melee_simulation_request(json.dumps(replay)).request.scenario
            self.assertEqual(native.enemies[0].definition.generated_components,npc)

    def test_actual_pc_and_npc_two_action_turns_survive_summary_and_current_json(self):
        for source,factory in ((pc_source(),pc_literal_dice),(npc_source(),npc_literal_dice)):
            with self.subTest(actor=source.party[0].actor_id, npc=source.enemies[0].definition.talents):
                parsed=command(source)
                result=run_pc_melee_simulation(parsed.request,rng_factory=factory)
                summary=summarize_pc_melee_simulation(result)
                encoded=json.loads(encode_pc_melee_simulation_result(parsed,summary))
                self.assertEqual(encoded['request']['scenario'],scenario_document(source))
                self.assertEqual(summary.total_action_count,3)
                counts=(summary.pc_ranged_counts if factory is pc_literal_dice
                    else summary.npc_ranged_counts)
                self.assertEqual(tuple((row.shots,row.reload_actions) for row in counts),((1,1),))

    def test_npc_owned_rapid_reload_and_paired_counters_survive_real_spawn(self):
        parsed=command(npc_source(),trials=2)
        sequential=run_pc_melee_simulation(parsed.request,rng_factory=npc_literal_dice)
        parallel=run_pc_melee_simulation_parallel(parsed.request,workers=2,batch_size=1,
            rng_factory=npc_literal_dice)
        self.assertEqual(parallel,sequential)
        summary=summarize_pc_melee_simulation(parallel)
        self.assertEqual(summary.total_action_count,6)
        self.assertEqual(tuple((row.shots,row.reload_actions) for row in summary.npc_ranged_counts),((2,2),))
        encode_pc_melee_simulation_result(parsed,summary)


if __name__=='__main__':
    unittest.main()
