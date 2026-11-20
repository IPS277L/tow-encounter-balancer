"""Current Magic/PC source transport; no simulated battles or invented stats."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest

from tests.support.magic_json_fixtures import simulation_document
from tests.support.pc_tactics_fixtures import automatic_source
from tests.support.talent_sources import free_talent, paid_talent, paid_talent_document
from tests.unit.test_generated_inventory_source import source as generated_source
from tests.unit.test_npc_talent_source import WIZARD_FACTS, wizard_talent
from towr.adapters._magic_scenario_json import scenario_document as magic_scenario_document
from towr.adapters._pc_melee_scenario_json import (
    parse_scenario as parse_pc_scenario, scenario_document as pc_scenario_document,
)
from towr.adapters._talent_json import acquired_talents_document, talent_owner_facts_document
from towr.adapters.magic_json_errors import MagicSimulationInputError
from towr.adapters.magic_json_schema import validate_magic_simulation_document
from towr.adapters.magic_simulation_json import parse_magic_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.domain.talent_actor_models import npc_definition_acquired_talents
from towr.domain.talent_catalog import TalentId, TalentOrigin
from towr.domain.talent_models import TalentOwnerFacts
from towr.domain.npc_roster_models import NpcRoster


class NpcTalentSourceJsonTests(unittest.TestCase):
    def test_magic6_hardy_and_wizard_sources_roundtrip_with_offline_refs(self):
        document = simulation_document()
        actor = document['scenario']['wizard']['actor_id']
        definition_id = next(value['definition_id'] for value in document['scenario']['actors']
            if value['id'] == actor)
        definition = next(value for value in document['scenario']['definitions']
            if value['id'] == definition_id)
        level = document['scenario']['wizard']['caster']['wizard_level']
        talents = (wizard_talent(level), paid_talent(TalentId.HARDY))
        definition['talents'] = acquired_talents_document(talents)
        definition['talent_facts'] = talent_owner_facts_document(WIZARD_FACTS)
        validate_magic_simulation_document(document)
        command = parse_magic_simulation_request(json.dumps(document))
        actual = command.request.scenario.initial.roster.participant(actor).definition
        self.assertEqual(npc_definition_acquired_talents(actual), talents)
        self.assertEqual(actual.talent_facts, WIZARD_FACTS)
        encoded = magic_scenario_document(command.request.scenario, command.definition_order)
        self.assertEqual(encoded['definitions'], document['scenario']['definitions'])
        replay = deepcopy(document)
        replay['scenario'] = encoded
        self.assertEqual(parse_magic_simulation_request(json.dumps(replay)), command)
        self.assertEqual(command.schema_version, '6')

    def test_magic_ordinary_sources_do_not_gain_invented_acquisitions(self):
        document = simulation_document()
        command = parse_magic_simulation_request(json.dumps(document))
        encoded = magic_scenario_document(command.request.scenario, command.definition_order)
        for definition in encoded['definitions']:
            self.assertNotIn('talents', definition)
            self.assertNotIn('talent_facts', definition)

    def test_magic_invalid_sources_keep_deep_paths_and_do_not_get_corrected(self):
        document = simulation_document()
        actor = document['scenario']['wizard']['actor_id']
        definition_id = next(value['definition_id'] for value in document['scenario']['actors']
            if value['id'] == actor)
        index = next(index for index, value in enumerate(document['scenario']['definitions'])
            if value['id'] == definition_id)
        for malformed in (['hardy'], [paid_talent_document(TalentId.HARDY)] * 2,
                [dict(paid_talent_document(TalentId.HARDY), rank=1)],
                [dict(paid_talent_document(TalentId.HARDY), id='unknown')]):
            raw = deepcopy(document)
            raw['scenario']['definitions'][index]['talents'] = malformed
            with self.subTest(malformed=malformed), self.assertRaises(MagicSimulationInputError) as caught:
                parse_magic_simulation_request(json.dumps(raw))
            self.assertIn(f'/scenario/definitions/{index}/talents', caught.exception.path)
        raw = deepcopy(document)
        raw['scenario']['definitions'][index]['talents'] = [paid_talent_document(TalentId.HARDY)]
        raw['scenario']['definitions'][index]['talents'][0]['acquisitions'][0]['funding'] = True
        with self.assertRaises(MagicSimulationInputError) as caught:
            parse_magic_simulation_request(json.dumps(raw))
        self.assertIn('/acquisitions/0/funding', caught.exception.path)

    def test_pc_generated_source_emits_exact_derived_witnesses(self):
        source = automatic_source(pc_count=1)
        npc = generated_source(talents=(paid_talent(TalentId.DEFENSIVE_STANCE),),
            talent_facts=TalentOwnerFacts(origin=TalentOrigin.HUMAN))
        source = replace(source, enemies=(npc.participant(source.enemies[0].state.actor_id),))
        document = pc_scenario_document(source)
        definition = document['enemies'][0]['definition']
        self.assertEqual(definition['talents'], definition['generated_components']['talents'])
        self.assertEqual(definition['talent_facts'], definition['generated_components']['talent_facts'])
        self.assertEqual(parse_pc_scenario(document, path_prefix='/scenario',
            error_type=PcMeleeSimulationInputError), source)
        for field in ('talents', 'talent_facts'):
            invalid = deepcopy(document)
            del invalid['enemies'][0]['definition'][field]
            with self.subTest(field=field), self.assertRaises(PcMeleeSimulationInputError):
                parse_pc_scenario(invalid, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)

    def test_old_bounded_families_reject_source_dropping(self):
        from tests.unit.test_m6_npc_melee_scenario import scenario as melee_source
        from tests.unit.test_m2_npc_ranged_scenario import scenario as ranged_source
        from tests.unit.test_m7_npc_mixed_scenario import scenario as mixed_source
        from towr.adapters._melee_scenario_json import scenario_document as melee_document
        from towr.adapters._ranged_scenario_json import scenario_document as ranged_document
        from towr.adapters._mixed_scenario_json import scenario_document as mixed_document

        for factory, encode in ((melee_source, melee_document), (ranged_source, ranged_document),
                (mixed_source, mixed_document)):
            source = factory()
            roster = source.initial.current.state.roster
            order = tuple(dict.fromkeys(p.definition.id for p in roster.participants))
            self.assertTrue(encode(source, order))
            for changes in ({'talents': (free_talent(TalentId.HARDY),)},
                    {'talent_facts': TalentOwnerFacts(origin=TalentOrigin.HUMAN)}):
                participants = tuple(replace(p, definition=replace(p.definition, **changes))
                    for p in roster.participants)
                initial = replace(source.initial, current=replace(source.initial.current,
                    state=replace(source.initial.current.state, roster=NpcRoster(participants))))
                changed = replace(source, initial=initial)
                with self.subTest(family=encode.__module__, changes=changes), self.assertRaisesRegex(
                        ValueError, 'cannot drop declared NPC Talent sources'):
                    encode(changed, order)


if __name__ == '__main__':
    unittest.main()
