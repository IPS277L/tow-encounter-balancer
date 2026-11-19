"""GM pairs retain exact scene actors through the dynamic/native boundary."""
from dataclasses import replace
import json
from random import Random
from unittest.mock import patch
import unittest

from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError,parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.pc_melee_models import validate_pc_single_combat_pairs
from towr.domain.pc_single_combat_models import PcSingleCombatPair as Pair
from tests.support.magic_weapon_fixtures import request,native


class PcSingleCombatSourceTests(unittest.TestCase):
    def test_exact_identifiers_distinct_opponents_and_disjoint_pairs(self):
        for actor,target in ((True,'npc'),('pc',1),('','npc'),('pc',' ')):
            with self.subTest(actor=actor,target=target),self.assertRaises(TypeError):Pair(actor,target)
        with self.assertRaises(ValueError):Pair('pc','pc')
        pcs=('pc','pc2');npcs=('npc','npc2')
        accepted=(Pair('pc','npc'),Pair('npc2','pc2'))
        validate_pc_single_combat_pairs(accepted,pcs,npcs)
        for pairs in ((Pair('pc','missing'),),(Pair('pc','pc2'),),(Pair('npc','npc2'),),
                (Pair('pc','npc'),Pair('npc','pc')),
                (Pair('pc','npc'),Pair('pc2','npc')),
                (Pair('pc','npc'),Pair('pc','npc2'))):
            with self.subTest(pairs=pairs),self.assertRaises(ValueError):
                validate_pc_single_combat_pairs(pairs,pcs,npcs)
        with self.assertRaises(TypeError):validate_pc_single_combat_pairs(list(accepted),pcs,npcs)
        bad=Pair('pc','npc');object.__setattr__(bad,'actor_id',True)
        with self.assertRaises(TypeError):validate_pc_single_combat_pairs((bad,),pcs,npcs)

    def test_dynamic_pairs_keep_orientation_at_every_permitted_count_and_native_replay(self):
        for reverse in (False,True):
            raw=request('sword_of_justice')
            raw['npc_count']=dict(minimum=1,maximum=3)
            pc=raw['party'][0]['actor_id'];npc='generated-npc:1'
            pair=dict(actor_id=npc if reverse else pc,target_id=pc if reverse else npc)
            raw['scene']['single_combat_pairs']=[pair]
            command=parse_dynamic_encounter_request(json.dumps(raw))
            self.assertEqual(json.loads(command.source_json),raw)
            self.assertEqual(command.request.single_combat_pairs,(Pair(**pair),))
            for count in (1,2,3):
                source=command.request.scenario(tuple(command.request.space.sample(Random(i))
                    for i in range(count)),'single:'+str(count))
                document=native(source)
                self.assertEqual(document['scenario']['single_combat_pairs'],[pair])
                restored=parse_pc_melee_simulation_request(json.dumps(document)).request.scenario
                self.assertEqual(restored,source)
                self.assertEqual(restored.single_combat_pairs,(Pair(**pair),))

    def test_optional_generated_target_is_rejected_before_proposal_rng_or_simulation(self):
        raw=request('sword_of_justice');raw['npc_count']=dict(minimum=1,maximum=3)
        raw['scene']['single_combat_pairs']=[dict(actor_id=raw['party'][0]['actor_id'],target_id='generated-npc:2')]
        with patch('towr.application.dynamic_encounter.NpcSearchSpace.sample',side_effect=AssertionError('no preflight RNG')):
            with self.assertRaises(DynamicEncounterInputError):parse_dynamic_encounter_request(json.dumps(raw))

    def test_duplicate_unknown_and_closed_wire_pairs_are_rejected(self):
        for pairs in ([dict(actor_id='pc',target_id='generated-npc:1',invented=True)],
                [dict(actor_id='pc',target_id='generated-npc:1'),dict(actor_id='generated-npc:1',target_id='pc')],
                [dict(actor_id='pc',target_id='generated-npc:01')],
                [dict(actor_id='unknown',target_id='generated-npc:1')]):
            raw=request('sword_of_justice');raw['scene']['single_combat_pairs']=pairs
            with self.subTest(pairs=pairs),self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))
        command=parse_dynamic_encounter_request(json.dumps(request('sword_of_justice')))
        source=command.request.scenario((command.request.space.sample(Random(1)),),'source')
        self.assertEqual(source.single_combat_pairs,())
        with self.assertRaises(ValueError):replace(source,single_combat_pairs=(Pair('pc','unknown'),))

