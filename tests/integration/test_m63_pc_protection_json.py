"""Optional PC Shooting opposition and Melee Protection Help keep full sources."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario, make_pc_melee_party_scenario
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_shield_scenarios import make_pc_shield_scenario, shield_loadout
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import parse_scenario, scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import (
    PcBackupWeaponPolicy, PcHelpPolicy, PcHelpTarget, PcMeleePolicy,
    PcMeleeWeapon, PcWeaponHand,
)
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.pc_npc_pistol_source_models import PcNpcPistolPolicy, PcNpcPistolReloadHandPolicy
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


FIELD = 'close_shooting_protection_skill'


def source_loadouts():
    for weapon in PcMeleeWeapon:
        if weapon.value not in ('pistol','repeater_handbow','repeater_pistol','shortbow','warbow','longbow','crossbow','repeater_crossbow','handgun','repeater_handgun','sling','blunderbuss','hochland_long_rifle'):
            yield make_pc_melee_scenario(weapon=weapon)
    yield make_pc_pistol_scenario()
    yield make_pc_shield_scenario()
    pistol = make_pc_pistol_scenario()
    member = replace(pistol.party[0], shield=shield_loadout(PcWeaponHand.RIGHT))
    yield replace(pistol, party=(member,))
    member = replace(member, backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.SWORD, PcWeaponHand.LEFT))
    yield replace(pistol, party=(member,))
    two_handed = make_pc_melee_scenario(weapon=PcMeleeWeapon.GREATAXE)
    yield replace(two_handed, party=(replace(two_handed.party[0],
        backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.DAGGER, PcWeaponHand.LEFT)),))


def service_source(*, choice=Skill.MELEE):
    source = make_pc_melee_party_scenario(pc_count=2, enemy_count=2, max_rounds=3)
    enemies = (create_pc_book_npc(PcBookNpcProfile.IMPERIAL_OGRE_PISTOL, 'minion1'),
        create_pc_book_npc(PcBookNpcProfile.FOOTPAD, 'minion2'))
    helper, receiver = source.party
    helper = replace(helper, policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
        help_policy=PcHelpPolicy('pc2', PcHelpTarget.FIRST_INCOMING_PROTECTION, Skill.MELEE))
    receiver = replace(receiver, close_shooting_protection_skill=choice)
    priority = ('minion2','minion1')
    party = tuple(replace(member, pc=replace(member.pc, toughness=10), target_priority=priority,
        defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority))
        for member in (helper, receiver))
    return replace(source, party=party, enemies=enemies, enemy_target_priority=('pc2','pc1'),
        facts=replace(source.facts, outnumbering_bonus_approved=False),
        npc_pistol_policies=(PcNpcPistolPolicy('minion1', True, True, True, True,
            PcNpcPistolReloadHandPolicy.TWO_AVAILABLE_HANDS),))


def request_document(*, balance=False):
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(service_source())
    if balance:
        raw['generation'].update(groups=[
            {'group_id':'ogre', 'actor_ids':['minion1'], 'minimum_count':0, 'maximum_count':1},
            {'group_id':'footpad', 'actor_ids':['minion2'], 'minimum_count':1, 'maximum_count':1}],
            facts=deepcopy(raw['template']['facts']), max_candidates=2)
        raw['evaluation'].update(trials_per_candidate=1, max_total_trials=2)
    else:
        raw['simulation']['trials'] = 2
    return raw


class PcProtectionChoiceJsonTests(unittest.TestCase):
    def test_thirteen_melee_pistol_shield_and_backup_sources_roundtrip_choices_and_absence(self):
        loadouts = tuple(source_loadouts())
        self.assertEqual(len(loadouts), 18)
        for source in loadouts:
            for choice in (None, Skill.MELEE, Skill.ATHLETICS):
                member = replace(source.party[0], close_shooting_protection_skill=choice)
                selected = replace(source, party=(member,))
                raw = document()
                raw['scenario'] = scenario_document(selected)
                with self.subTest(weapon=member.pc.weapon, shield=member.shield,
                        backup=member.backup_weapon_policy, choice=choice):
                    command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                    self.assertEqual(command.request.scenario, selected)
                    self.assertEqual(scenario_document(command.request.scenario), raw['scenario'])
                    if choice is None:
                        self.assertNotIn(FIELD, raw['scenario']['party'][0])
                    else:
                        self.assertEqual(raw['scenario']['party'][0][FIELD], choice.value)

    def test_native_exact_choice_and_help_skill_admission(self):
        class Alias(str, Enum):
            MELEE = 'melee'
        member = make_pc_melee_scenario().party[0]
        for value in ('melee', Alias.MELEE, True, 1, Skill.DEFENCE, Skill.SHOOTING):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                replace(member, close_shooting_protection_skill=value)
        policy = PcHelpPolicy('ally', PcHelpTarget.FIRST_INCOMING_PROTECTION, Skill.MELEE)
        self.assertIs(policy.protection_skill, Skill.MELEE)
        for value in (Alias.MELEE, 'melee', Skill.SHOOTING, None):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                replace(policy, protection_skill=value)
        with self.assertRaises(ValueError):
            PcHelpPolicy('ally', PcHelpTarget.MELEE_ATTACK, Skill.MELEE)

    def test_optional_field_and_help_malformed_values_fail_before_rng(self):
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                for value in (None, True, 1, 'defence', 'shooting', 'Melee', {}, []):
                    raw = request_document(balance=balance)
                    raw[key]['party'][1][FIELD] = value
                    with self.subTest(balance=balance, value=value), self.assertRaises(error):
                        parse(json.dumps(raw))
                for value in ('shooting', None, True):
                    raw = request_document(balance=balance)
                    raw[key]['party'][0]['help_policy']['protection_skill'] = value
                    with self.subTest(balance=balance, help_skill=value), self.assertRaises(error):
                        parse(json.dumps(raw))
                raw = request_document(balance=balance)
                raw[key]['party'][1]['close_shooting_protection'] = 'melee'
                with self.assertRaises(error):
                    parse(json.dumps(raw))
                rng.assert_not_called()
        for value in (None, True, Skill.MELEE, 'defence'):
            raw = request_document()['scenario']
            raw['party'][1][FIELD] = value
            with self.subTest(direct=value), self.assertRaises(PcMeleeSimulationInputError):
                parse_scenario(raw, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)

    def test_cached_choice_and_help_alias_forgeries_fail_before_trial_rng(self):
        class Alias(str, Enum):
            MELEE = 'melee'
        request = PcMeleeSimulationRequest(service_source(), 42, 1)
        for field, value in ((FIELD, 'melee'), (FIELD, Alias.MELEE), (FIELD, Skill.DEFENCE),
                ('protection_skill', Alias.MELEE)):
            forged = deepcopy(request)
            target = forged.scenario.party[1] if field == FIELD else forged.scenario.party[0].help_policy
            object.__setattr__(target, field, value)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(field=field, value=value), self.assertRaises((TypeError, ValueError)):
                    run_pc_melee_trial(forged, 0, rng_factory=rng)
                rng.assert_not_called()

    def test_count_projection_preserves_party_policy_when_last_shooter_is_removed(self):
        raw = request_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        for counts in ((0,1), (1,1)):
            with self.subTest(counts=counts):
                candidate = project_pc_melee_candidate(command.request, counts).scenario
                self.assertIs(candidate.party[1].close_shooting_protection_skill, Skill.MELEE)
                self.assertIs(candidate.party[0].help_policy.protection_skill, Skill.MELEE)
                self.assertEqual(scenario_document(candidate)['party'][1][FIELD], 'melee')
                self.assertEqual(len(candidate.npc_pistol_policies), counts[0])

    def test_actual_services_preserve_choices_help_costs_and_full_candidate_echoes(self):
        for balance in (False, True):
            raw = request_document(balance=balance)
            if balance:
                command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                report = execute_pc_melee_balance(command)
                output = json.loads(wire.encode_pc_melee_balance_result(command, report))
                validate_pc_melee_balance_document(output, 'result')
                for row, candidate in zip(output['candidates'], report.candidates, strict=True):
                    self.assertEqual(row['request']['scenario'], scenario_document(candidate.source_request.scenario))
                    self.assertEqual(row['request']['scenario']['party'][1][FIELD], 'melee')
                    if candidate.counts[0] == 0:
                        self.assertEqual(candidate.summary.total_help_action_count, 0)
                self.assertTrue(any(candidate.summary.total_help_action_count > 0 for candidate in report.candidates))
            else:
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                summary = execute_pc_melee_simulation(command)
                output = json.loads(wire.encode_pc_melee_simulation_result(command, summary))
                validate_pc_melee_simulation_document(output, 'result')
                self.assertGreater(summary.total_help_action_count, 0)
                self.assertEqual(summary.help_action_counts[1].count, 0)
                self.assertLess(summary.total_help_action_count, summary.total_action_count)
            self.assertEqual(output['request'], raw)


if __name__ == '__main__':
    unittest.main()
