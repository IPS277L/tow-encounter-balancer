"""Existing pair JSON now preserves Skill-bound NPC Shooting Help end to end."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from tests.support.npc_shooting_help_scenarios import make_npc_shooting_help_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import parse_scenario, scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_npc_catalog import PcBookNpcProfile as Profile, create_pc_book_npc


HELPERS = (Profile.FREE_COMPANY_MILITIA_BLADES, Profile.GOBLIN_WARRIOR_SPEAR,
    Profile.NIGHT_GOBLIN_SPEAR, Profile.NIGHT_GOBLIN_NET_SPEAR)
SHOOTERS = (Profile.EMPIRE_OFFICIAL_PISTOL, Profile.IMPERIAL_OGRE_PISTOL)
MELEE_ONLY = (Profile.EMPIRE_PEASANT, Profile.SIGMARITE_CULTIST_WARHAMMER,
    Profile.ORC_BOY_CHOPPAS, Profile.BIG_UN_CHOPPAS)


def service_source():
    source = make_npc_shooting_help_scenario(helpers=(HELPERS[0], HELPERS[1]), max_rounds=4)
    member = source.party[0]
    priority = (source.enemy_activation_order[-1], *source.enemy_activation_order[:-1])
    member = replace(member, pc=replace(member.pc, weapon=PcMeleeWeapon.DAGGER,
        strength=1, toughness=12), target_priority=priority,
        defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority))
    return replace(source, party=(member,))


def request_document(*, balance=False):
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(service_source())
    if balance:
        raw['generation'].update(groups=[
            {'group_id':name, 'actor_ids':[actor], 'minimum_count':0, 'maximum_count':1}
            for name, actor in (('militia','minion1'), ('goblin','minion2'), ('ogre','minion3'))],
            facts=deepcopy(raw['template']['facts']), max_candidates=7)
        raw['evaluation'].update(trials_per_candidate=1, max_total_trials=7)
    else:
        raw['simulation']['trials'] = 2
    return raw


def melee_only_document(profile, *, balance=False):
    raw = request_document(balance=balance)
    key = 'template' if balance else 'scenario'
    source = service_source()
    unsupported = replace(source, enemies=(create_pc_book_npc(profile, 'minion1'),
        *source.enemies[1:]), npc_help_policies=())
    pairs = raw[key]['npc_help_policies']
    raw[key] = scenario_document(unsupported)
    raw[key]['npc_help_policies'] = pairs
    return raw


class NpcShootingHelpJsonTests(unittest.TestCase):
    def test_all_four_helper_loadouts_and_both_shooters_keep_existing_pair_source(self):
        for helper in HELPERS:
            for shooter in SHOOTERS:
                with self.subTest(helper=helper, shooter=shooter):
                    source = make_npc_shooting_help_scenario(helpers=(helper,), shooter=shooter)
                    raw = document()
                    raw['scenario'] = scenario_document(source)
                    command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                    self.assertEqual(command.request.scenario, source)
                    self.assertEqual(scenario_document(command.request.scenario), raw['scenario'])
                    self.assertEqual(raw['scenario']['npc_help_policies'],
                        [{'helper_id':'minion1', 'beneficiary_id':'minion2'}])
                    self.assertEqual(set(raw['scenario']['npc_help_policies'][0]),
                        {'helper_id','beneficiary_id'})
                    self.assertEqual(raw['schema_version'], '1')
                    if helper is Profile.NIGHT_GOBLIN_NET_SPEAR:
                        self.assertEqual(raw['scenario']['enemies'][0]['net_policy'],
                            {'initial_count':1, 'mode':'throw_once_then_spear'})

    def test_helpers_and_shooter_builders_return_independent_fresh_sources(self):
        left = make_npc_shooting_help_scenario(helpers=HELPERS)
        right = make_npc_shooting_help_scenario(helpers=HELPERS)
        self.assertEqual(left, right)
        self.assertIsNot(left, right)
        self.assertIsNot(left.party[0], right.party[0])
        self.assertIsNot(left.enemies[0], right.enemies[0])
        self.assertEqual(len(left.npc_help_policies), 4)
        self.assertEqual(tuple(policy.helper_id for policy in left.npc_help_policies),
            ('minion1','minion2','minion3','minion4'))
        self.assertFalse(left.facts.outnumbering_bonus_approved)

    def test_melee_only_abilities_and_full_excluded_templates_fail_before_rng(self):
        for balance in (False, True):
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                for helper in MELEE_ONLY:
                    raw = melee_only_document(helper, balance=balance)
                    if balance:
                        raw['generation']['groups'][0]['maximum_count'] = 0
                    with self.subTest(balance=balance, helper=helper), self.assertRaises(error):
                        parse(json.dumps(raw))
                rng.assert_not_called()

    def test_malformed_pairs_foreign_skill_ability_and_actor_order_fail_before_rng(self):
        mutations = (
            lambda source: source['npc_help_policies'][0].update(skill='shooting'),
            lambda source: source['npc_help_policies'][0].update(bonus=1),
            lambda source: source['npc_help_policies'][0].update(helper_id='foreign'),
            lambda source: source['npc_help_policies'][0].update(beneficiary_id='pc'),
            lambda source: source['npc_help_policies'][0].update(beneficiary_id='minion1'),
            lambda source: source['npc_help_policies'].append(deepcopy(source['npc_help_policies'][0])),
            lambda source: source['npc_help_policies'][0].update(beneficiary_id='minion2'),
            lambda source: source.update(enemy_activation_order=['minion3','minion2','minion1']),
            lambda source: source['enemies'][0]['definition']['attack']['damage'].update(base=8),
            lambda source: source['enemies'][0]['definition'].update(source_rule_id='authored:militia'),
        )
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                for mutate in mutations:
                    raw = request_document(balance=balance)
                    mutate(raw[key])
                    with self.subTest(balance=balance, mutate=mutate), self.assertRaises(error):
                        parse(json.dumps(raw))
                rng.assert_not_called()
        raw = request_document()['scenario']
        raw['npc_help_policies'][0]['skill'] = 'shooting'
        with self.assertRaises(PcMeleeSimulationInputError):
            parse_scenario(raw, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)

    def test_generation_filters_both_endpoints_without_retargeting_or_repair(self):
        raw = request_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        template = command.request.template
        for counts in ((1,1,0), (0,0,1), (1,0,1), (0,1,1), (1,1,1)):
            with self.subTest(counts=counts):
                source = project_pc_melee_candidate(command.request, counts).scenario
                actors = tuple(enemy.state.actor_id for enemy in source.enemies)
                expected = tuple(policy for policy in template.npc_help_policies
                    if policy.helper_id in actors and policy.beneficiary_id in actors)
                self.assertEqual(source.npc_help_policies, expected)
                self.assertEqual(source.enemy_activation_order,
                    tuple(actor for actor in template.enemy_activation_order if actor in actors))
                self.assertEqual(tuple(policy.actor_id for policy in source.npc_pistol_policies),
                    ('minion3',) if counts[2] else ())
                self.assertEqual(scenario_document(template), raw['template'])

    def test_actual_sequential_services_keep_help_costs_full_echoes_and_candidate_sources(self):
        for balance in (False, True):
            raw = request_document(balance=balance)
            if balance:
                command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                report = execute_pc_melee_balance(command)
                output = json.loads(wire.encode_pc_melee_balance_result(command, report))
                validate_pc_melee_balance_document(output, 'result')
                self.assertEqual(len(report.candidates), 7)
                for row, candidate in zip(output['candidates'], report.candidates, strict=True):
                    source = candidate.source_request.scenario
                    self.assertEqual(row['request']['scenario'], scenario_document(source))
                    self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_help_action_counts),
                        source.enemy_activation_order)
                    if not source.npc_help_policies:
                        self.assertEqual(candidate.summary.total_npc_help_action_count, 0)
                self.assertTrue(any(candidate.summary.total_npc_help_action_count > 0
                    for candidate in report.candidates))
            else:
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                summary = execute_pc_melee_simulation(command)
                output = json.loads(wire.encode_pc_melee_simulation_result(command, summary))
                validate_pc_melee_simulation_document(output, 'result')
                self.assertGreater(summary.total_npc_help_action_count, 0)
                self.assertEqual(summary.npc_help_action_trial_count, 2)
                self.assertEqual(tuple(item.actor_id for item in summary.npc_help_action_counts),
                    ('minion1','minion2','minion3'))
                self.assertGreater(summary.npc_help_action_counts[0].count, 0)
                self.assertGreater(summary.npc_help_action_counts[1].count, 0)
                self.assertEqual(summary.npc_help_action_counts[2].count, 0)
                self.assertLess(summary.total_npc_help_action_count, summary.total_action_count)
                self.assertEqual(output['summary']['total_npc_help_action_count'],
                    summary.total_npc_help_action_count)
            self.assertEqual(output['request'], raw)


if __name__ == '__main__':
    unittest.main()
