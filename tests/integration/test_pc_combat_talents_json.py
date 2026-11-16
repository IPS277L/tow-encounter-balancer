"""PC combat talent source facts across editable and executable JSON."""
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import unittest
from unittest.mock import patch

from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError, parse_dynamic_encounter_request
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.generated_npc_models import GeneratedTalent
from towr.domain.pc_combat_talent_models import TalentAcquisition


def combat_talent_request():
    return json.loads(Path('docs/examples/dynamic/pc-talents.request.json').read_text('utf-8'))


def native_document(raw):
    command=parse_dynamic_encounter_request(json.dumps(raw))
    npc=command.request.space.sample(Random(42))
    scenario=command.request.scenario((npc,),'pc-talents:replay')
    return dict(schema_version='1',kind='pc_melee_simulation',request_id='pc-talents',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(scenario),
        simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential')),scenario


class PcCombatTalentJsonTests(unittest.TestCase):
    def test_dynamic_facts_default_to_earned_and_preserve_explicit_free_acquisition(self):
        raw=combat_talent_request()
        command=parse_dynamic_encounter_request(json.dumps(raw))
        party=command.request.party
        self.assertEqual([(t.talent,t.acquisition) for t in party[0].combat_talents],
            [(GeneratedTalent.DEFENSIVE_STANCE,TalentAcquisition.EARNED),
             (GeneratedTalent.WILD_ATTACK,TalentAcquisition.EARNED)])
        self.assertEqual(party[1].combat_talents[0].acquisition,TalentAcquisition.CREATION_FREE)

    def test_metadata_is_closed_and_never_applies_to_an_unselected_talent(self):
        invalid=[None,[],{'unknown':'earned'},{'lucky':'creation_free'},
            {'wild_attack':True},{'wild_attack':'automatic'},
            {'defensive_stance':'creation_free'}]
        for acquisition in invalid:
            raw=combat_talent_request()
            raw['party'][1]['talent_acquisition']=acquisition
            with self.subTest(acquisition=acquisition),patch('towr.application.dynamic_encounter.Random.randint') as roll:
                with self.assertRaises(DynamicEncounterInputError):
                    parse_dynamic_encounter_request(json.dumps(raw))
                roll.assert_not_called()

    def test_earned_requirements_fail_before_simulation_but_remain_valid_editable_drafts(self):
        for talent,characteristic,value in [('wild_attack','strength',3),('defensive_stance','weapon_skill',2)]:
            raw=combat_talent_request()
            member=raw['party'][0]
            member['talents']=[talent]
            member['characteristics'][characteristic]=value
            with self.subTest(talent=talent):
                self.assertEqual(parse_character_file(json.dumps(member),'player'),member)
                with self.assertRaises(DynamicEncounterInputError):
                    parse_dynamic_encounter_request(json.dumps(raw))
                member['talent_acquisition']={talent:'creation_free'}
                parse_dynamic_encounter_request(json.dumps(raw))
                self.assertEqual(parse_character_file(json.dumps(member),'player'),member)

    def test_character_files_preserve_facts_and_reject_orphan_or_ranked_sources(self):
        player=combat_talent_request()['party'][1]
        self.assertEqual(parse_character_file(json.dumps(player),'player'),player)
        for changes in [dict(talent_acquisition={'wild_attack':'unknown'}),
                dict(talent_acquisition={'defensive_stance':'creation_free'}),
                dict(talents=['wild_attack','wild_attack']),
                dict(talents=[dict(talent='wild_attack',rank=2)])]:
            with self.subTest(changes=changes),self.assertRaises(DynamicEncounterInputError):
                parse_character_file(json.dumps(dict(player,**changes)),'player')

    def test_native_roundtrip_retains_complete_facts_and_omits_empty_sources(self):
        raw=combat_talent_request()
        document,scenario=native_document(raw)
        self.assertEqual(document['scenario']['party'][1]['combat_talents'],
            [dict(talent='wild_attack',acquisition='creation_free')])
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(document)).request.scenario,scenario)
        for member in raw['party']:
            member['talents']=[]
            member.pop('talent_acquisition',None)
        empty,_=native_document(raw)
        self.assertTrue(all('combat_talents' not in member for member in empty['scenario']['party']))

    def test_native_rejects_false_requirements_duplicate_ids_and_wrong_policy(self):
        document,_=native_document(combat_talent_request())
        alterations=[('pc',{'strength':3}),('combat_talents',[
            dict(talent='wild_attack',acquisition='earned'),
            dict(talent='wild_attack',acquisition='creation_free')]),
            ('combat_talents',[dict(talent='wild_attack',acquisition='unknown')]),
            ('policy','attack_or_recover_self')]
        for field,value in alterations:
            changed=deepcopy(document)
            member=changed['scenario']['party'][0]
            if field=='pc':
                member[field].update(value)
            else:
                member[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(PcMeleeInputError):
                parse_pc_melee_simulation_request(json.dumps(changed))


class PcCombatTalentProcessTests(unittest.TestCase):
    def test_full_pc_talents_and_provenance_survive_real_process_trials(self):
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation

        _,scenario=native_document(combat_talent_request())
        request=PcMeleeSimulationRequest(scenario,42,2)
        sequential=run_pc_melee_simulation(request)
        parallel=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(sequential,parallel)
        self.assertEqual(summarize_pc_melee_simulation(sequential),summarize_pc_melee_simulation(parallel))
        self.assertEqual(parallel.source_request.scenario.party[1].combat_talents[0].acquisition,
            TalentAcquisition.CREATION_FREE)


if __name__=='__main__':
    unittest.main()
