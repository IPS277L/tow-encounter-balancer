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
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import TalentAcquisitionPhase, TalentFunding


def combat_talent_request():
    return json.loads(Path('docs/examples/dynamic/pc-talents.request.json').read_text('utf-8'))


def talent_source(id, *, phase='advancement', funding='xp'):
    """An explicit current acquisition fixture; malformed variants stay malformed."""
    return dict(id=id,acquisitions=[dict(phase=phase,funding=funding)])


def native_document(raw):
    command=parse_dynamic_encounter_request(json.dumps(raw))
    npc=command.request.space.sample(Random(42))
    scenario=command.request.scenario((npc,),'pc-talents:replay')
    return dict(schema_version='1',kind='pc_melee_simulation',request_id='pc-talents',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(scenario),
        simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential')),scenario


class PcCombatTalentJsonTests(unittest.TestCase):
    def test_dynamic_facts_preserve_explicit_paid_and_free_acquisition(self):
        raw=combat_talent_request()
        command=parse_dynamic_encounter_request(json.dumps(raw))
        party=command.request.party
        self.assertEqual([(t.id,t.acquisitions[0].phase,t.acquisitions[0].funding)
            for t in party[0].talents],
            [(TalentId.DEFENSIVE_STANCE,TalentAcquisitionPhase.ADVANCEMENT,TalentFunding.XP),
             (TalentId.WILD_ATTACK,TalentAcquisitionPhase.ADVANCEMENT,TalentFunding.XP)])
        acquisition,=party[1].talents[0].acquisitions
        self.assertIs(acquisition.phase,TalentAcquisitionPhase.CREATION)
        self.assertIs(acquisition.funding,TalentFunding.FREE)

    def test_metadata_is_closed_typed_and_fails_before_simulation(self):
        invalid=[dict(id='unknown',acquisitions=[dict(phase='creation',funding='free')]),
            dict(id='wild_attack'),dict(id='wild_attack',acquisitions=[]),
            dict(id='wild_attack',acquisitions=[dict(phase='automatic',funding='xp')]),
            dict(id='wild_attack',acquisitions=[dict(phase='creation',funding=True)]),
            talent_source('wild_attack',funding='free'),
            dict(id='wild_attack',acquisitions=[dict(phase='creation',funding='free',
                choice=dict(kind='unknown',id='unrelated'))])]
        for acquisition in invalid:
            raw=combat_talent_request()
            raw['party'][1]['talents']=[acquisition]
            with self.subTest(acquisition=acquisition),patch('towr.application.dynamic_encounter.Random.randint') as roll:
                with self.assertRaises(DynamicEncounterInputError):
                    parse_dynamic_encounter_request(json.dumps(raw))
                roll.assert_not_called()

    def test_earned_requirements_fail_before_simulation_but_remain_valid_editable_drafts(self):
        for talent,characteristic,value in [('wild_attack','strength',3),('defensive_stance','weapon_skill',2)]:
            raw=combat_talent_request()
            member=raw['party'][0]
            member['talents']=[talent_source(talent)]
            member['characteristics'][characteristic]=value
            with self.subTest(talent=talent):
                self.assertEqual(parse_character_file(json.dumps(member),'player'),member)
                with self.assertRaises(DynamicEncounterInputError):
                    parse_dynamic_encounter_request(json.dumps(raw))
                member['talents']=[talent_source(talent,phase='creation',funding='free')]
                parse_dynamic_encounter_request(json.dumps(raw))
                self.assertEqual(parse_character_file(json.dumps(member),'player'),member)

    def test_character_files_preserve_facts_and_reject_duplicate_or_malformed_acquisitions(self):
        player=combat_talent_request()['party'][1]
        self.assertEqual(parse_character_file(json.dumps(player),'player'),player)
        for changes in [dict(talents=[talent_source('wild_attack',funding='unknown')]),
                dict(talents=[talent_source('wild_attack'),talent_source('wild_attack',
                    phase='creation',funding='free')]),
                dict(talents=[dict(id='wild_attack',acquisitions=[
                    dict(phase='creation',funding='free'),dict(phase='advancement',funding='xp')])]),
                dict(talents=[dict(id='wild_attack',rank=2,acquisitions=[
                    dict(phase='creation',funding='free')])])]:
            with self.subTest(changes=changes),self.assertRaises(DynamicEncounterInputError):
                parse_character_file(json.dumps(dict(player,**changes)),'player')

    def test_native_roundtrip_retains_complete_acquisition_and_empty_sources(self):
        raw=combat_talent_request()
        document,scenario=native_document(raw)
        self.assertEqual(document['scenario']['party'][1]['talents'],
            [dict(id='wild_attack',acquisitions=[dict(phase='creation',funding='free',
                choice=None,devotion_confirmed=None)])])
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(document)).request.scenario,scenario)
        for member in raw['party']:
            member['talents']=[]
        empty,empty_scenario=native_document(raw)
        self.assertTrue(all(not member.talents for member in empty_scenario.party))
        self.assertTrue(all(member.get('talents',[])==[] for member in empty['scenario']['party']))
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(empty)).request.scenario,empty_scenario)

    def test_native_rejects_false_requirements_duplicate_ids_and_wrong_policy(self):
        document,_=native_document(combat_talent_request())
        alterations=[('pc',{'strength':3}),('talents',[
            talent_source('wild_attack'),
            talent_source('wild_attack',phase='creation',funding='free')]),
            ('talents',[talent_source('wild_attack',phase='unknown')]),
            ('policy','attack_or_recover_self')]
        for field,value in alterations:
            changed=deepcopy(document)
            member=changed['scenario']['party'][0]
            if field=='pc':
                member[field].update(value)
                if type(member.get('talent_facts')) is dict:
                    member['talent_facts'].update(value)
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
        acquisition,=parallel.source_request.scenario.party[1].talents[0].acquisitions
        self.assertIs(acquisition.phase,TalentAcquisitionPhase.CREATION)
        self.assertIs(acquisition.funding,TalentFunding.FREE)


if __name__=='__main__':
    unittest.main()
