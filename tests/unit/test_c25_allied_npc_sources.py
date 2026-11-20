"""C25 fixed same-side NPC sources, current JSON and hostile-only generation."""
from dataclasses import replace
import json
from pathlib import Path
from random import Random
from unittest import TestCase

from tests.unit.test_c24_common_actor_sources import document,space
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request,DynamicEncounterInputError
from towr.adapters._pc_melee_scenario_json import scenario_document,generated_components_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.turn_models import CombatSide
from towr.domain.minion_defeat_models import NpcDefeatDisposition


def with_allies(*,champion=False,automatic_space=False):
    raw=document()
    npc=space().sample(Random(3))
    if champion:npc=replace(npc,injury_policy=TargetInjuryPolicy.CHAMPION,endurance=4)
    raw['npc_allies']=[{'actor_id':'ally:medic','npc':generated_components_document(npc)}]
    if automatic_space:raw['search_space']=None
    return raw


def command(raw):return parse_dynamic_encounter_request(json.dumps(raw))


def candidate_source(command):
    request=command.request
    return request.scenario((request.space.sample(Random(6)),),'c25:source')


def native(source):
    raw=json.loads(Path('docs/examples/m54/pc-melee-simulation.request.json').read_text(encoding='utf-8'))
    raw['scenario']=scenario_document(source)
    return raw


class AlliedNpcSourceTests(TestCase):
    def test_no_ally_request_retains_existing_banks_and_optional_wire_absence(self):
        source=candidate_source(command(document()))
        self.assertEqual(source.npc_allies,())
        self.assertEqual(source.npc_sources,source.enemies)
        self.assertEqual(source.npc_activation_order,source.enemy_activation_order)
        self.assertEqual(source.player_activation_order,source.pc_activation_order)
        self.assertNotIn('npc_allies',scenario_document(source))
        self.assertNotIn('npc_defeat_decisions',scenario_document(source))

    def test_fixed_allies_are_separate_from_hostile_search_composition_and_fate(self):
        current=command(with_allies(champion=True));source=candidate_source(current)
        ally=source.npc_allies[0]
        self.assertEqual(ally.state.side,CombatSide.PLAYERS_AND_ALLIES)
        self.assertEqual(source.enemy('ally:medic'),ally)
        self.assertEqual(source.npc('ally:medic'),ally)
        self.assertEqual(source.npc_sources,(*source.enemies,ally))
        self.assertEqual(source.player_activation_order,(*source.pc_activation_order,'ally:medic'))
        self.assertEqual(source.npc_activation_order,(*source.enemy_activation_order,'ally:medic'))
        self.assertEqual(source.enemy_target_priority,(*source.pc_activation_order,'ally:medic'))
        self.assertFalse(hasattr(ally.state,'fate'))
        another=current.request.scenario(tuple(current.request.space.sample(Random(i)) for i in (5,6)), 'c25:second')
        self.assertEqual(another.npc_allies,source.npc_allies)
        self.assertEqual(len(source.enemies),1)
        self.assertEqual(len(another.enemies),2)

    def test_explicit_player_order_roundtrips_native_and_dynamic_without_changing_pc_order(self):
        raw=with_allies();pc_id=raw['party'][0]['actor_id'];raw['player_side_activation_order']=['ally:medic',pc_id]
        source=candidate_source(command(raw))
        self.assertEqual(source.player_activation_order,('ally:medic',pc_id))
        self.assertEqual(source.pc_activation_order,(pc_id,))
        encoded=native(source)
        restored=parse_pc_melee_simulation_request(json.dumps(encoded)).request.scenario
        self.assertEqual(restored,source)
        self.assertEqual(encoded['scenario']['npc_allies'][0]['npc'],raw['npc_allies'][0]['npc'])

    def test_missing_duplicate_or_unknown_order_actors_and_colliding_ids_are_rejected(self):
        for order in (['ally:medic'],['ally:medic','ally:medic'],['foreign','ally:medic']):
            with self.subTest(order=order),self.assertRaises(DynamicEncounterInputError):
                raw=with_allies();raw['player_side_activation_order']=order;command(raw)
        for actor in (document()['party'][0]['actor_id'],'generated-npc:1'):
            with self.subTest(actor=actor),self.assertRaises(DynamicEncounterInputError):
                raw=with_allies();raw['npc_allies'][0]['actor_id']=actor;command(raw)

    def test_npc_profile_defeat_decisions_derive_from_the_existing_explicit_gm_disposition(self):
        raw=with_allies();raw['defeat_disposition']='knocked_out'
        source=candidate_source(command(raw))
        self.assertEqual({(row.attacker_id,row.target_id) for row in source.npc_defeat_decisions},
            {('ally:medic','generated-npc:1'),('generated-npc:1','ally:medic')})
        self.assertTrue(all(row.gm_approved and row.disposition is NpcDefeatDisposition.KNOCKED_OUT
            for row in source.npc_defeat_decisions))
        malformed=native(source);del malformed['scenario']['npc_defeat_decisions']
        with self.assertRaises(PcMeleeSimulationInputError):parse_pc_melee_simulation_request(json.dumps(malformed))
        malformed=native(source);malformed['scenario']['npc_defeat_decisions'][0]['gm_approved']=False
        with self.assertRaises(PcMeleeSimulationInputError):parse_pc_melee_simulation_request(json.dumps(malformed))

    def test_champion_target_never_receives_synthetic_profile_defeat_policy(self):
        source=candidate_source(command(with_allies(champion=True)))
        self.assertEqual([(row.attacker_id,row.target_id) for row in source.npc_defeat_decisions],
            [('ally:medic','generated-npc:1')])

    def test_automatic_search_envelope_uses_actual_fixed_ally_characteristics(self):
        raw=with_allies(automatic_space=True)
        raw['npc_allies'][0]['npc']['strength']=8
        request=command(raw).request
        self.assertIn(9,request.space.strength)
        self.assertEqual(request.npc_allies[0].definition.generated_components.strength,8)

    def test_explicit_single_combat_can_pair_a_fixed_ally_with_a_hostile(self):
        raw=with_allies();raw['scene']['single_combat_pairs']=[{'actor_id':'ally:medic','target_id':'generated-npc:1'}]
        source=candidate_source(command(raw))
        self.assertEqual((source.single_combat_pairs[0].actor_id,source.single_combat_pairs[0].target_id),
            ('ally:medic','generated-npc:1'))

    def test_ally_source_is_the_current_standalone_npc_format_with_no_fate_or_side_override(self):
        for extra in ({'fate':3},{'side':'opposition'},{'definition':{}}):
            with self.subTest(extra=extra),self.assertRaises(DynamicEncounterInputError):
                raw=with_allies();raw['npc_allies'][0]['npc'].update(extra);command(raw)
