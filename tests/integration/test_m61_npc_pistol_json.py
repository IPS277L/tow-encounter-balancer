"""Canonical NPC firearm source facts survive JSON, services and count search."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import parse_scenario, scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import PcAdjacentNpcExitPolicy, PcMeleeWeapon
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.pc_npc_pistol_source_models import (
    PcNpcPistolPolicy, PcNpcPistolReloadHandPolicy,
)


def firearm_source(*, rounds=8):
    source = make_pc_melee_party_scenario(pc_count=1, enemy_count=2, max_rounds=rounds)
    profiles = (PcBookNpcProfile.EMPIRE_OFFICIAL_PISTOL, PcBookNpcProfile.IMPERIAL_OGRE_PISTOL)
    enemies = tuple(create_pc_book_npc(profile, actor)
        for profile, actor in zip(profiles, source.enemy_activation_order, strict=True))
    # High Toughness keeps the PC alive to observe actual Reload. Printed
    # NPCs retain Wounds, Staggered conversion and the Official's real exit.
    member = replace(source.party[0], pc=replace(source.party[0].pc,
        weapon=PcMeleeWeapon.DAGGER, strength=1, toughness=10, armour_bonus=2))
    return replace(source, party=(member,), enemies=enemies,
        facts=replace(source.facts, can_leave_zone=True),
        npc_broken_exit_policy=PcAdjacentNpcExitPolicy('outside', True, True),
        npc_pistol_policies=tuple(PcNpcPistolPolicy(actor, True, True, True, True,
            PcNpcPistolReloadHandPolicy.TWO_AVAILABLE_HANDS) for actor in source.enemy_activation_order))


def request_document(*, balance=False):
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(firearm_source())
    if balance:
        raw['generation'].update(groups=[
            {'group_id':'official', 'actor_ids':['minion1'], 'minimum_count':0, 'maximum_count':1},
            {'group_id':'ogre', 'actor_ids':['minion2'], 'minimum_count':1, 'maximum_count':1}],
            facts=deepcopy(raw['template']['facts']), max_candidates=2)
        raw['evaluation'].update(trials_per_candidate=1, max_total_trials=2)
    else:
        raw['simulation']['trials'] = 2
    return raw


class NpcPistolJsonTests(unittest.TestCase):
    def test_both_canonical_profiles_roundtrip_the_complete_closed_source(self):
        for balance in (False, True):
            raw = request_document(balance=balance)
            command = (wire.parse_pc_melee_balance_request if balance else
                wire.parse_pc_melee_simulation_request)(json.dumps(raw))
            source = command.request.template if balance else command.request.scenario
            encoded = scenario_document(source)
            self.assertEqual(encoded, raw['template' if balance else 'scenario'])
            self.assertEqual(raw['schema_version'], '1')
            for index, enemy in enumerate(encoded['enemies']):
                attack = enemy['definition']['attack']
                self.assertEqual((attack['skill'], attack['range_min'], attack['range_max']),
                    ('shooting', 'close', 'short' if index == 0 else 'medium'))
                self.assertIs(attack['ignores_armour'], True)
                self.assertEqual(set(enemy['pistol']), {'initially_loaded', 'has_blackpowder_lore',
                    'has_blackpowder_kit', 'ammunition_supply_confirmed', 'reload_hand_policy'})

    def test_partial_facts_numeric_forgeries_and_foreign_loadouts_fail_before_rng(self):
        mutations = (
            lambda enemy: enemy.pop('pistol'),
            lambda enemy: enemy.update(pistol={}),
            lambda enemy: enemy['pistol'].pop('has_blackpowder_kit'),
            lambda enemy: enemy['pistol'].update(initially_loaded=False),
            lambda enemy: enemy['pistol'].update(has_blackpowder_lore=1),
            lambda enemy: enemy['pistol'].update(has_blackpowder_kit=False),
            lambda enemy: enemy['pistol'].update(ammunition_supply_confirmed=False),
            lambda enemy: enemy['pistol'].update(reload_hand_policy='one_hand'),
            lambda enemy: enemy['pistol'].update(dexterity=10),
            lambda enemy: enemy.update(holds_shield=True),
            lambda enemy: enemy['definition']['attack'].pop('skill'),
            lambda enemy: enemy['definition']['attack'].pop('range_min'),
            lambda enemy: enemy['definition']['attack'].pop('ignores_armour'),
            lambda enemy: enemy['definition']['attack'].update(skill='melee'),
            lambda enemy: enemy['definition']['attack'].update(ignores_armour=False),
            lambda enemy: enemy['definition']['attack'].update(range_max='long'),
            lambda enemy: enemy['definition']['attack']['test_profile'].update(dice=4),
            lambda enemy: enemy['definition']['attack']['damage'].update(base=6),
            lambda enemy: enemy['definition'].update(id='authored:pistol'),
            lambda enemy: enemy['definition'].update(source_rule_id='authored:pistol'),
        )
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                for mutate in mutations:
                    raw = request_document(balance=balance)
                    mutate(raw[key]['enemies'][0])
                    with self.subTest(balance=balance, mutate=mutate), self.assertRaises(error):
                        parse(json.dumps(raw))
                rng.assert_not_called()

    def test_direct_codec_keeps_closed_sources_and_old_melee_fields(self):
        base = request_document()['scenario']
        for mutate in (
                lambda enemy: enemy.update(pistol={}),
                lambda enemy: enemy['pistol'].update(unknown=True),
                lambda enemy: enemy['definition']['attack'].update(extra=True),
                lambda enemy: enemy['definition']['attack'].pop('range_min')):
            raw = deepcopy(base)
            mutate(raw['enemies'][0])
            with self.subTest(mutate=mutate), self.assertRaises(PcMeleeSimulationInputError):
                parse_scenario(raw, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)
        old = document()['scenario']
        for field, value in (('skill', 'shooting'), ('range_min', 'close'), ('ignores_armour', True)):
            raw = deepcopy(old)
            raw['enemies'][0]['definition']['attack'][field] = value
            with self.subTest(field=field), self.assertRaises(PcMeleeSimulationInputError):
                parse_scenario(raw, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)
        old['enemies'][0]['pistol'] = deepcopy(base['enemies'][0]['pistol'])
        with self.assertRaises(PcMeleeSimulationInputError):
            parse_scenario(old, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)

    def test_full_excluded_template_is_validated_and_projection_filters_exact_actor_policy(self):
        raw = request_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        for counts, actors in (((0, 1), ('minion2',)), ((1, 1), ('minion1', 'minion2'))):
            candidate = project_pc_melee_candidate(command.request, counts).scenario
            self.assertEqual(tuple(policy.actor_id for policy in candidate.npc_pistol_policies), actors)
            echoed = scenario_document(candidate)
            self.assertTrue(all('pistol' in enemy for enemy in echoed['enemies']))
            for enemy in echoed['enemies']:
                original = next(source for source in raw['template']['enemies']
                    if source['actor_id'] == enemy['actor_id'])
                self.assertEqual(enemy, original)
        raw['generation']['groups'][0]['maximum_count'] = 0
        raw['template']['enemies'][0]['pistol']['has_blackpowder_lore'] = False
        with patch('towr.simulation.pc_melee_simulation.Random') as rng:
            with self.assertRaises(PcMeleeBalanceInputError):
                wire.parse_pc_melee_balance_request(json.dumps(raw))
            rng.assert_not_called()

    def test_current_services_echo_full_source_and_actual_candidate_counts(self):
        for balance in (False, True):
            raw = request_document(balance=balance)
            if balance:
                command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                result = execute_pc_melee_balance(command)
                encoded = json.loads(wire.encode_pc_melee_balance_result(command, result))
                validate_pc_melee_balance_document(encoded, 'result')
                self.assertEqual(len(encoded['candidates']), 2)
                for row in encoded['candidates']:
                    expected = ('minion2',) if row['counts'][0] == 0 else ('minion1', 'minion2')
                    self.assertEqual(tuple(enemy['actor_id'] for enemy in row['request']['scenario']['enemies']), expected)
                    self.assertTrue(all('pistol' in enemy for enemy in row['request']['scenario']['enemies']))
            else:
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                result = execute_pc_melee_simulation(command)
                encoded = json.loads(wire.encode_pc_melee_simulation_result(command, result))
                validate_pc_melee_simulation_document(encoded, 'result')
            self.assertEqual(encoded['request'], raw)

    def test_208_previous_current_json_examples_keep_their_original_scenario_objects(self):
        root = Path(__file__).resolve().parents[2] / 'docs/examples'
        examples = tuple(path for path in root.glob('m*/*.json')
            if path.parent.name[1:].isdigit() and 9 <= int(path.parent.name[1:]) <= 60)
        self.assertEqual(len(examples), 208)
        for path in examples:
            document = json.loads(path.read_bytes())
            sources = []
            request = document.get('request', document)
            sources.append(request.get('scenario', request.get('template')))
            sources.extend(candidate['request']['scenario'] for candidate in document.get('candidates', ()))
            for raw in sources:
                with self.subTest(path=path, source=raw['id']):
                    source = parse_scenario(raw, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)
                    self.assertEqual(scenario_document(source), raw)
                    self.assertEqual(source.npc_pistol_policies, ())


if __name__ == '__main__':
    unittest.main()
