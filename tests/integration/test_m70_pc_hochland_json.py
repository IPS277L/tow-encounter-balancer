"""Aim resource observations cross compact records, reports and JSON1 echoes."""
from copy import deepcopy
from dataclasses import replace
import json
import pickle
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

from tests.support.pc_hochland_scenarios import make_pc_hochland_scenario
from tests.support.pc_handgun_scenarios import make_pc_handgun_scenario, handgun_profile
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import PcFatePolicy, PcGloriousPolicy, PcMeleeWeapon
from towr.domain.fate_models import FateSpendFunding, FateSpendKind
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import (
    PcAimCount, PcAimCounts, PcGloriousSpendCount, PcMeleeSimulationRequest, validate_aim_counts,
)
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation, run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def request_document(*, balance=False, second=True, rating=1, lucky=False):
    scene = make_pc_hochland_scenario(pc_count=2, enemy_count=3, max_rounds=2,
        use_second_action=second, fate_rating=rating, has_lucky=lucky,
        npc_toughness=6, npc_armour_bonus=2)
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(scene)
    if balance:
        raw['generation']['groups'] = [{'group_id':'minions',
            'actor_ids':['minion3','minion1','minion2'], 'minimum_count':1, 'maximum_count':3}]
        raw['generation']['facts'] = deepcopy(raw['template']['facts'])
        raw['generation']['max_candidates'] = 3
        raw['evaluation'].update(trials_per_candidate=1, max_total_trials=3)
    else:
        raw['simulation']['trials'] = 2
    return raw


class PcHochlandJsonTests(unittest.TestCase):
    def test_declined_second_action_keeps_lucky_for_the_later_melee_glorious(self):
        source = make_pc_hochland_scenario(max_rounds=2,use_second_action=False,
            has_lucky=True,fate_rating=0)
        source = replace(source,party=(replace(source.party[0],
            fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.MELEE,),0,0)),))
        rng = ScriptedD10([10,10,10, 10,10,1,1,1, 10,10,10, 1,1,1, 10,10])
        battle = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        spend, = battle.state.participant('pc1').fate.spends
        self.assertIs(spend.kind,FateSpendKind.GLORIOUS_TEST)
        self.assertIs(spend.funding,FateSpendFunding.LUCKY_FREE)
        self.assertEqual(spend.session_cost,0)
        # Observe the actual admitted journal once; the compact boundary must
        # preserve that free Glorious without manufacturing a Second Action.
        request = PcMeleeSimulationRequest(source,42,1)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=battle):
            record = run_pc_melee_trial(request,0)
        self.assertEqual(record.executed_actions,3)
        self.assertEqual(record.aim.total_action_count,1)
        self.assertEqual(record.aim.total_second_action_spend_count,0)
        self.assertEqual(record.glorious_spend_counts,(PcGloriousSpendCount('pc1',1),))

    def test_actual_lucky_second_action_and_paid_glorious_remain_separate_observations(self):
        source = make_pc_hochland_scenario(max_rounds=1,has_lucky=True,fate_rating=1)
        source = replace(source,party=(replace(source.party[0],
            glorious_policy=PcGloriousPolicy((Skill.SHOOTING,),0,0)),))
        # Aim has no successes. Lucky funds the second slot; paid Fate then
        # rerolls the two failed Short-range Shooting dice before Protection.
        rng = ScriptedD10([10,10,10,10,10,1,1,10,10])
        request = PcMeleeSimulationRequest(source,42,1)
        record = run_pc_melee_trial(request,0,rng_factory=lambda seed:rng)
        rng.assert_exhausted()
        self.assertEqual(record.executed_actions,2)
        self.assertEqual(record.aim.total_action_count,1)
        self.assertEqual(record.aim.total_second_action_spend_count,1)
        self.assertEqual(record.glorious_spend_counts,(PcGloriousSpendCount('pc1',1),))
        # Each marginal could fit two source resources; together they cannot
        # spend the single Lucky funding and the single session point twice.
        with self.assertRaises(ValueError):
            replace(record,glorious_spend_counts=(PcGloriousSpendCount('pc1',2),))

    def test_paid_and_lucky_second_actions_have_distinct_actual_aim_counters(self):
        for rating,lucky in ((1,False),(0,True)):
            raw = request_document(rating=rating,lucky=lucky)
            command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
            result = execute_pc_melee_simulation(command)
            output = json.loads(wire.encode_pc_melee_simulation_result(command,result))
            validate_pc_melee_simulation_document(output,'result')
            self.assertEqual(output['request'],raw)
            self.assertEqual(output['summary']['aim'],{
                'action_counts':[{'actor_id':'pc1','count':2},{'actor_id':'pc2','count':2}],
                'total_action_count':4,
                'second_action_spend_counts':[{'actor_id':'pc1','count':2},{'actor_id':'pc2','count':2}],
                'total_second_action_spend_count':4})
            self.assertEqual(output['summary']['total_glorious_spend_count'],0)
            self.assertGreaterEqual(result.total_action_count,8)
            self.assertEqual(pickle.loads(pickle.dumps(result)),result)

    def test_declined_and_unfunded_aim_keep_zero_second_action_observations(self):
        for second,rating in ((False,1),(True,0)):
            command = wire.parse_pc_melee_simulation_request(json.dumps(
                request_document(second=second,rating=rating)))
            result = execute_pc_melee_simulation(command)
            self.assertEqual(result.aim.total_action_count,4)
            self.assertEqual(result.aim.total_second_action_spend_count,0)
            self.assertEqual(tuple(row.count for row in result.aim.second_action_spend_counts),(0,0))
            self.assertEqual(result.total_glorious_spend_count,0)

    def test_mixed_party_counters_include_every_actor_in_source_order(self):
        source = make_pc_hochland_scenario(pc_count=2,enemy_count=3,max_rounds=1)
        member = source.party[1]
        source = replace(source,party=(source.party[0],replace(member,
            pc=replace(member.pc,weapon=PcMeleeWeapon.HANDGUN,ranged=handgun_profile()),
            fate_policy=PcFatePolicy.DECLINE_OPTIONAL_FATE,aim_second_action_policy=None)))
        result = run_pc_melee_simulation(PcMeleeSimulationRequest(source,42,1))
        record, = result.records
        self.assertEqual(record.aim.action_counts,(PcAimCount('pc1',1),PcAimCount('pc2',0)))
        self.assertEqual(record.aim.second_action_spend_counts,(PcAimCount('pc1',1),PcAimCount('pc2',0)))
        summary = summarize_pc_melee_simulation(result)
        self.assertEqual(summary.aim,record.aim)
        self.assertEqual(pickle.loads(pickle.dumps(record)),record)

    def test_native_counts_reject_missing_foreign_overbudget_and_joint_resource_forgeries(self):
        source = make_pc_hochland_scenario(pc_count=2,enemy_count=3,max_rounds=1)
        record, = run_pc_melee_simulation(PcMeleeSimulationRequest(source,42,1)).records
        variants = (None, PcAimCounts((),()),
            PcAimCounts((PcAimCount('pc2',1),PcAimCount('pc1',1)),
                (PcAimCount('pc2',1),PcAimCount('pc1',1))),
            PcAimCounts((PcAimCount('pc1',9),PcAimCount('pc2',1)),record.aim.second_action_spend_counts),
            PcAimCounts(record.aim.action_counts,(PcAimCount('pc1',2),PcAimCount('pc2',1))))
        for counts in variants:
            with self.subTest(counts=counts),self.assertRaises((TypeError,ValueError)):
                replace(record,aim=counts)
        with self.assertRaises(TypeError):
            PcAimCount('pc1',True)
        with self.assertRaises(TypeError):
            PcAimCounts(list(record.aim.action_counts),record.aim.second_action_spend_counts)
        lucky = make_pc_hochland_scenario(max_rounds=2,has_lucky=True,fate_rating=1)
        member = lucky.party[0]
        lucky = replace(lucky,party=(replace(member,
            glorious_policy=PcGloriousPolicy((Skill.SHOOTING,),0,0)),))
        counts = PcAimCounts((PcAimCount('pc1',1),),(PcAimCount('pc1',1),))
        glorious = (PcGloriousSpendCount('pc1',1),)
        validate_aim_counts(counts,lucky,trials=1,actions=2,started_rounds=1,glorious_counts=glorious)
        paid = replace(lucky,party=(replace(lucky.party[0],fate=replace(lucky.party[0].fate,has_lucky=False)),))
        with self.assertRaises(ValueError):
            validate_aim_counts(counts,paid,trials=1,actions=2,started_rounds=1,glorious_counts=glorious)

    def test_current_result_schemas_require_aim_only_for_hochland_sources(self):
        raw = request_document()
        command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result = execute_pc_melee_simulation(command)
        output = json.loads(wire.encode_pc_melee_simulation_result(command,result))
        for change in (lambda d:d['summary'].pop('aim'),
                lambda d:d['summary']['aim'].update(extra=0),
                lambda d:d['summary']['aim'].update(total_second_action_spend_count=True),
                lambda d:d['summary']['aim']['action_counts'][0].update(count=-1)):
            broken = deepcopy(output);change(broken)
            with self.assertRaises(ValidationError):
                validate_pc_melee_simulation_document(broken,'result')
        plain = deepcopy(raw)
        plain['scenario'] = scenario_document(make_pc_handgun_scenario(enemy_count=3,max_rounds=2))
        command = wire.parse_pc_melee_simulation_request(json.dumps(plain))
        result = execute_pc_melee_simulation(command)
        self.assertIsNone(result.aim)
        plain_output = json.loads(wire.encode_pc_melee_simulation_result(command,result))
        self.assertNotIn('aim',plain_output['summary'])
        plain_output['summary']['aim'] = output['summary']['aim']
        with self.assertRaises(ValidationError):
            validate_pc_melee_simulation_document(plain_output,'result')

    def test_balance_projection_and_candidate_reports_preserve_source_and_aim_capability(self):
        raw = request_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        for count in (1,2,3):
            source = project_pc_melee_candidate(command.request,(count,)).scenario
            for member,original in zip(source.party,command.request.template.party,strict=True):
                self.assertEqual(member.pc,original.pc)
                self.assertEqual(member.aim_second_action_policy,original.aim_second_action_policy)
                self.assertEqual(member.fate,original.fate)
        result = execute_pc_melee_balance(command)
        output = json.loads(wire.encode_pc_melee_balance_result(command,result))
        validate_pc_melee_balance_document(output,'result')
        self.assertEqual(output['request'],raw)
        for row,candidate in zip(output['candidates'],result.candidates,strict=True):
            self.assertEqual(row['request']['scenario'],scenario_document(candidate.source_request.scenario))
            self.assertEqual(row['summary']['aim']['total_action_count'],candidate.summary.aim.total_action_count)
            self.assertEqual(row['summary']['aim']['total_second_action_spend_count'],candidate.summary.aim.total_second_action_spend_count)
            self.assertEqual(tuple(item['actor_id'] for item in row['summary']['aim']['action_counts']),('pc1','pc2'))
        broken = deepcopy(output)
        broken['candidates'][0]['summary'].pop('aim')
        with self.assertRaises(ValidationError):
            validate_pc_melee_balance_document(broken,'result')


if __name__ == '__main__':
    unittest.main()
