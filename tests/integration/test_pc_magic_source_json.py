"""The same explicit wizard facts survive generator input, files and native replay."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

from tests.support.pc_tactics_fixtures import automatic_source
from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import (
    DynamicEncounterInputError, parse_dynamic_encounter_request, validate_dynamic_encounter_document, _validator,
)
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.pc_magic_source_models import PcSpellId, PcWizardProfile


def wizard_request():
    document = json.loads(Path('docs/examples/dynamic/search.request.json').read_text(encoding='utf-8'))
    member = document['party'][0]
    member['talents'] = [*member['talents'], 'wizard']
    member['characteristics']['reason'] = 3
    member['skills']['willpower'] = 5
    member['magic'] = dict(origin='human',wizard_level=1,lores=['elementalism'],
        memorised_spells=['lightning_blast','fire_breath'],arcane_paraphernalia=True)
    return document


class PcMagicSourceJsonTests(unittest.TestCase):
    def test_wizard_facts_compile_without_running_search_or_losing_source_fields(self):
        document = wizard_request()
        with patch('towr.adapters.dynamic_encounter_json.search_dynamic_encounter') as search:
            command = parse_dynamic_encounter_request(json.dumps(document))
        search.assert_not_called()
        wizard = command.request.party[0].wizard
        self.assertEqual((wizard.reason,wizard.willpower,wizard.wizard_level),(3,5,1))
        self.assertEqual(wizard.memorised_spells,(PcSpellId.LIGHTNING_BLAST,PcSpellId.FIRE_BREATH))
        self.assertEqual(json.loads(command.source_json),document)
        self.assertIs(command.request.facts.daylight_confirmed,True)
        self.assertEqual(command.request.party[0].pc.weapon_skill,document['party'][0]['characteristics']['weapon_skill'])

    def test_magic_stats_and_wizard_talent_are_required_together(self):
        for missing in ('reason','willpower','magic','wizard'):
            document = wizard_request()
            member = document['party'][0]
            if missing == 'reason':
                del member['characteristics']['reason']
            elif missing == 'willpower':
                del member['skills']['willpower']
            elif missing == 'magic':
                del member['magic']
            else:
                member['talents'].remove('wizard')
            with self.subTest(missing=missing), self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(document))
        document = wizard_request()
        del document['party'][0]['magic']
        document['party'][0]['talents'].remove('wizard')
        with self.assertRaises(ValidationError):
            validate_dynamic_encounter_document(document)

    def test_invalid_prerequisites_are_rejected_before_monte_carlo(self):
        for field,value in (('origin','dwarf'),('origin','halfling'),('arcane_paraphernalia',False),
                ('wizard_level',True),('wizard_level',0),('wizard_level',5),
                ('memorised_spells',[]),('memorised_spells',['fireball']),
                ('memorised_spells',['lightning_blast','lightning_blast']),('lores',['battle_magic'])):
            document = wizard_request()
            document['party'][0]['magic'][field] = value
            with self.subTest(field=field,value=value), patch(
                    'towr.adapters.dynamic_encounter_json.search_dynamic_encounter') as search:
                with self.assertRaises(DynamicEncounterInputError):
                    parse_dynamic_encounter_request(json.dumps(document))
                search.assert_not_called()

    def test_granular_player_file_preserves_descriptive_magic_draft(self):
        member = wizard_request()['party'][0]
        member['magic']['arcane_paraphernalia'] = False
        self.assertEqual(parse_character_file(json.dumps(member),'player'),member)
        member['magic']['origin'] = 'dwarf'
        self.assertEqual(parse_character_file(json.dumps(member),'player'),member)

    def test_worn_helmet_retains_casting_armour_fact_without_inventing_resilience(self):
        document = wizard_request()
        document['party'][0]['equipment']['armour'] = [dict(id='helmet',kind='helmet',location='worn')]
        member = parse_dynamic_encounter_request(json.dumps(document)).request.party[0]
        self.assertTrue(member.armour_worn)
        self.assertEqual(member.pc.armour_bonus,0)

    def test_current_native_replay_preserves_full_wizard_profile(self):
        wizard = parse_dynamic_encounter_request(json.dumps(wizard_request())).request.party[0].wizard
        scenario = automatic_source()
        scenario = replace(scenario,party=(replace(scenario.party[0],wizard=wizard),scenario.party[1]),
            facts=replace(scenario.facts,daylight_confirmed=True))
        raw = dict(schema_version='1',kind='pc_melee_simulation',request_id='magic-source-roundtrip',
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(scenario),
            simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))
        self.assertEqual(raw['scenario']['party'][0]['wizard']['memorised_spells'],['lightning_blast','fire_breath'])
        self.assertNotIn('wizard',raw['scenario']['party'][1])
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario,scenario)
        invalid = deepcopy(raw)
        invalid['scenario']['party'][0]['wizard']['arcane_paraphernalia'] = False
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(invalid))

    def test_native_wizard_scene_requires_explicit_daylight_without_guessing_it(self):
        wizard = parse_dynamic_encounter_request(json.dumps(wizard_request())).request.party[0].wizard
        source = automatic_source()
        with self.assertRaises(ValueError):
            replace(source,party=(replace(source.party[0],wizard=wizard),source.party[1]))
        source = replace(source,party=(replace(source.party[0],wizard=wizard),source.party[1]),
            facts=replace(source.facts,daylight_confirmed=True))
        raw = dict(schema_version='1',kind='pc_melee_simulation',request_id='daylight',
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
            simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))
        del raw['scenario']['facts']['daylight_confirmed']
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(raw))


class DynamicMagicObservationSchemaTests(unittest.TestCase):
    def candidate(self, *, wizard):
        source = automatic_source(pc_count=1)
        if wizard:
            profile = PcWizardProfile('human',3,5,1,('elementalism',),(PcSpellId.LIGHTNING_BLAST,),True)
            source = replace(source,party=(replace(source.party[0],wizard=profile),),
                facts=replace(source.facts,daylight_confirmed=True))
        return dict(npcs=[dict(weapon_skill=3,strength=3,toughness=3,agility=3,
                melee=3,defence=3,shield=False,athletics=3,weapon='staff',light_armour=False,abilities=[],talents=[],
                ranged=None,weapon_grip=None,mount=None,throwing=None,brawn=None,ballistic_skill=None)],
            win_rate=0.5,win_interval_95=[0.1,0.9],mean_started_rounds=1,
            rounds_interval_95=[1,1],outcomes=dict(objective_achieved=1,party_defeated=1,round_limit=0,unsupported_path=0),
            target_assessment=dict(status='within_targets',win_rate_in_range=True,started_rounds_in_range=True,
                win_rate_deviation=0,started_rounds_deviation=0,normalized_max_deviation=0,normalized_total_deviation=0),
            trials=2,replay=dict(schema_version='1',kind='pc_melee_simulation',request_id='observations',
                ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
                simulation=dict(master_seed='42',trials=2),execution=dict(mode='sequential')))

    def validator(self):
        return _validator('result').evolve(schema={
            '$ref':'urn:towr:dynamic-encounter:common:1#/$defs/candidate'})

    def test_wizard_candidate_requires_even_zero_actual_magic_observations(self):
        candidate = self.candidate(wizard=True)
        with self.assertRaises(ValidationError):
            self.validator().validate(candidate)
        candidate['magic_counts'] = [dict(actor_id='pc1',casting_actions=0,spell_casts=0,miscasts=0,unsupported_miscasts=0)]
        self.validator().validate(candidate)
        candidate['magic_counts'][0]['casting_actions'] = True
        with self.assertRaises(ValidationError):
            self.validator().validate(candidate)

    def test_nonwizard_candidate_cannot_invent_magic_observations(self):
        candidate = self.candidate(wizard=False)
        self.validator().validate(candidate)
        candidate['magic_counts'] = [dict(actor_id='pc1',casting_actions=0,spell_casts=0,miscasts=0,unsupported_miscasts=0)]
        with self.assertRaises(ValidationError):
            self.validator().validate(candidate)


if __name__ == '__main__':
    unittest.main()
