"""M70 observations follow a carried Hochland source, without widening families."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator,ValidationError
from tests.support.pc_hochland_scenarios import make_pc_hochland_scenario
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request,encode_pc_melee_simulation_result
from towr.adapters.pc_melee_json_schema import validate_pc_melee_simulation_document
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation as L
from towr.domain.pc_melee_models import PcFatePolicy,PcMeleePolicy,PcMeleeWeapon as W,PcWeaponHand as H,PcRangedProfile
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.simulation.pc_melee_models import (
    PcAimCount,PcAimCounts,PcGloriousSpendCount,pc_has_aim_capability,validate_aim_counts,
)
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class Tens:
    """Deterministic misses keep this source/observation test free of Wounds."""
    def randint(self,low,high):
        if (low,high)!=(1,10):raise AssertionError('unexpected die range')
        return 10


def carried_source(*,pcs=1,weapon=W.HOCHLAND_LONG_RIFLE):
    source=make_pc_hochland_scenario(pc_count=pcs,max_rounds=1,npc_toughness=20)
    party=[]
    for index,member in enumerate(source.party):
        ranged=(member.pc.ranged if weapon is W.HOCHLAND_LONG_RIFLE else
            PcRangedProfile(3,4,ammunition_supply_confirmed=True)) if index==0 else None
        items=(PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT),)
        if index==0:
            items+=(PcWeaponItem('carried-gun',weapon,L.CARRIED,None,
                initially_loaded=True if weapon is W.HOCHLAND_LONG_RIFLE else None),)
        party.append(replace(member,pc=replace(member.pc,weapon=W.SWORD,weapon_skill=1,melee=1,
            strength=2,ranged=ranged),policy=PcMeleePolicy.AUTOMATIC_COMBAT,
            fate_policy=member.fate_policy if index==0 and weapon is W.HOCHLAND_LONG_RIFLE
                else PcFatePolicy.DECLINE_OPTIONAL_FATE,
            initial_weapon_hand=H.LEFT,backup_weapon_policy=None,combat_equipment=items,
            aim_second_action_policy=member.aim_second_action_policy
                if index==0 and weapon is W.HOCHLAND_LONG_RIFLE else None))
    return replace(source,party=tuple(party),short_range_opening=None,
        battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT,RangedWeaponRange.LONG),
        facts=replace(source.facts,can_leave_zone=True,all_opponents_close=False))


class InventoryAimCounterTests(unittest.TestCase):
    def test_capability_and_counts_follow_inventory_with_actor_specific_negatives(self):
        source=carried_source(pcs=2)
        self.assertTrue(pc_has_aim_capability(source))
        self.assertTrue(all(member.pc.weapon is W.SWORD for member in source.party))
        counts=PcAimCounts((PcAimCount('pc1',1),PcAimCount('pc2',0)),
            (PcAimCount('pc1',1),PcAimCount('pc2',0)))
        glorious=tuple(PcGloriousSpendCount(member.actor_id,0) for member in source.party)
        validate_aim_counts(counts,source,trials=1,actions=2,started_rounds=1,glorious_counts=glorious)
        forged=replace(counts,action_counts=(PcAimCount('pc1',1),PcAimCount('pc2',1)))
        with self.assertRaises(ValueError):
            validate_aim_counts(forged,source,trials=1,actions=3,started_rounds=1,glorious_counts=glorious)
        with self.assertRaises(TypeError):
            validate_aim_counts(None,source,trials=1,actions=0,started_rounds=1,glorious_counts=glorious)

    def test_other_bows_do_not_expand_the_m70_counter_family(self):
        source=carried_source(weapon=W.SHORTBOW)
        self.assertFalse(pc_has_aim_capability(source))
        validate_aim_counts(None,source,trials=1,actions=0,started_rounds=1,glorious_counts=())
        with self.assertRaises(ValueError):
            validate_aim_counts(PcAimCounts((PcAimCount('pc1',0),),(PcAimCount('pc1',0),)),
                source,trials=1,actions=0,started_rounds=1,glorious_counts=())

    def test_result_presence_gates_use_inventory_in_simulation_and_both_balance_layers(self):
        root=Path('src/towr/adapters/schemas')
        sim=json.loads((root/'pc-melee-simulation-result-v1.schema.json').read_text('utf-8'))
        balance=json.loads((root/'pc-melee-balance-result-v1.schema.json').read_text('utf-8'))
        for schema in (sim,balance):Draft202012Validator.check_schema(schema)
        for weapon,has_counts in ((W.HOCHLAND_LONG_RIFLE,True),(W.SHORTBOW,False)):
            source=scenario_document(carried_source(weapon=weapon))
            summary={'aim':{}} if has_counts else {}
            # Isolated presence rules; the native case below validates the full
            # result shape and offline references with genuine observations.
            for gate,document in (
                (sim['allOf'][2],dict(request=dict(scenario=source),summary=summary)),
                (balance['properties']['candidates']['items']['allOf'][3],
                    dict(request=dict(scenario=source),summary=summary)),
                (balance['allOf'][0],dict(request=dict(template=source),candidates=[dict(summary=summary)]))):
                validator=Draft202012Validator(gate)
                validator.validate(document)
                malformed=deepcopy(document)
                target=malformed['summary'] if 'summary' in malformed else malformed['candidates'][0]['summary']
                if has_counts:target.pop('aim')
                else:target['aim']={}
                with self.assertRaises(ValidationError):validator.validate(malformed)

    def test_one_actual_trial_encodes_carried_hochland_aim_and_second_action(self):
        source=carried_source()
        raw=dict(schema_version='1',kind='pc_melee_simulation',request_id='inventory-aim',
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
            simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))
        command=parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request,rng_factory=lambda seed:Tens())
        record,=result.records
        self.assertEqual(record.aim.action_counts,(PcAimCount('pc1',1),))
        self.assertEqual(record.aim.second_action_spend_counts,(PcAimCount('pc1',1),))
        summary=summarize_pc_melee_simulation(result)
        encoded=json.loads(encode_pc_melee_simulation_result(command,summary))
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(encoded['summary']['aim']['total_action_count'],1)
        self.assertEqual(encoded['summary']['aim']['total_second_action_spend_count'],1)
        validate_pc_melee_simulation_document(encoded,'result')


if __name__=='__main__':unittest.main()
