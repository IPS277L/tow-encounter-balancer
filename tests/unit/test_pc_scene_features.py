"""PG115 ground features and sight facts use the actual line and actors."""
from copy import deepcopy
from dataclasses import replace
import json
from random import Random
from types import SimpleNamespace
import unittest

from tests.support.magic_weapon_fixtures import request,native
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError,parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.condition_models import Condition
from towr.domain.pc_battlefield_models import PcBattlefieldSpec,with_actor_placement
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_scene_feature_models import (
    PcZoneFeatures,PcVisibilityFact,SCENE_COVER_RULE_ID,
    scene_attack_visibility,difficult_terrain_crossed,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.test_models import Skill,DiceModifier
from towr.domain.turn_models import (
    CombatActionKind,CombatActionDeclaration,CombatActionSlotRequest,
    CombatTurnStartRequest,ActionSlotGrant,ManoeuvreKind,
)
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot


def state(**scene):
    raw=request('dragon_bow');raw['npc_count']=dict(minimum=1,maximum=1)
    if scene.pop('flying',False):
        raw['party'][0].update(mount='pegasus',rider_kind='human')
        raw['scene']['airspace']=dict(open_sky_confirmed=True,fall_hazard_rating=2)
    raw['scene'].update(scene)
    command=parse_dynamic_encounter_request(json.dumps(raw))
    source=command.request.scenario((command.request.space.sample(Random(2)),),'features')
    return initial_pc_melee_state(source)


class PcSceneFeatureTests(unittest.TestCase):
    def test_closed_source_roundtrip_keeps_each_feature_and_directed_visibility(self):
        source=state(zone_features=[dict(index=0,difficult_terrain=True),dict(index=1,cover=True,concealment=True)],
            visibility=[dict(observer_id='pc',target_id='generated-npc:1',visible=False)],darkness=True).source
        restored=parse_pc_melee_simulation_request(json.dumps(native(source))).request.scenario
        self.assertEqual(restored,source)
        self.assertEqual(restored.battlefield.zone_features,(PcZoneFeatures(0,True),PcZoneFeatures(1,False,True,True)))
        self.assertEqual(restored.battlefield.visibility,(PcVisibilityFact('pc','generated-npc:1',False),))
        self.assertIs(restored.battlefield.darkness,True)

    def test_cover_and_concealment_are_one_penalty_and_do_not_hide_or_awareness(self):
        current=state(zone_features=[dict(index=1,cover=True,concealment=True)])
        source=deepcopy(current)
        sight=scene_attack_visibility(current,'pc','generated-npc:1',Skill.SHOOTING)
        self.assertTrue(sight.visible)
        self.assertTrue(sight.cover and sight.concealment)
        self.assertEqual(sight.modifiers,(DiceModifier(SCENE_COVER_RULE_ID,-1),))
        self.assertEqual(scene_attack_visibility(current,'pc','generated-npc:1',Skill.THROWING).modifiers,sight.modifiers)
        self.assertEqual(scene_attack_visibility(current,'pc','generated-npc:1',Skill.MELEE).modifiers,())
        self.assertEqual(current,source)

    def test_features_follow_actual_target_zone_without_leaking_to_air(self):
        current=state(zone_features=[dict(index=1,cover=True)],flying=True)
        self.assertTrue(scene_attack_visibility(current,'pc','generated-npc:1',Skill.SHOOTING).cover)
        # A pure visibility query uses a prepared typed placement; this is not
        # claimed to be an executed movement history or native battle replay.
        actual=SimpleNamespace(source=current.source,participant=current.participant,enemy=current.enemy,
            battlefield=with_actor_placement(current.battlefield,'generated-npc:1','arena:zone:0'))
        self.assertFalse(scene_attack_visibility(actual,'pc','generated-npc:1',Skill.SHOOTING).cover)
        actual=SimpleNamespace(source=current.source,participant=current.participant,enemy=current.enemy,
            battlefield=with_actor_placement(current.battlefield,'generated-npc:1','arena:air:1'))
        self.assertFalse(scene_attack_visibility(actual,'pc','generated-npc:1',Skill.SHOOTING).cover)

    def test_visibility_is_directed_and_true_does_not_override_blinded_or_darkness(self):
        current=state(visibility=[dict(observer_id='pc',target_id='generated-npc:1',visible=False)])
        self.assertFalse(scene_attack_visibility(current,'pc','generated-npc:1',Skill.SHOOTING).visible)
        self.assertTrue(scene_attack_visibility(current,'generated-npc:1','pc',Skill.SHOOTING).visible)
        current=state(range='long',darkness=True,
            visibility=[dict(observer_id='pc',target_id='generated-npc:1',visible=True)])
        self.assertFalse(scene_attack_visibility(current,'pc','generated-npc:1',Skill.SHOOTING).visible)
        current=state(range='medium',darkness=True,
            visibility=[dict(observer_id='pc',target_id='generated-npc:1',visible=True)])
        self.assertTrue(scene_attack_visibility(current,'pc','generated-npc:1',Skill.SHOOTING).visible)
        actor=current.participant('pc')
        current=replace(current,party=(replace(actor,injury=replace(actor.injury,
            conditions=actor.injury.conditions.with_condition(Condition.BLINDED))),))
        self.assertFalse(scene_attack_visibility(current,'pc','generated-npc:1',Skill.SHOOTING).visible)
        self.assertTrue(scene_attack_visibility(current,'pc','generated-npc:1',Skill.MELEE).visible)

    def test_unknown_visibility_ids_malformed_features_and_duplicate_indices_are_rejected(self):
        for scene in (dict(zone_features=[dict(index=True)]),dict(zone_features=[dict(index=-4)]),
                dict(zone_features=[dict(index=5)]),dict(zone_features=[dict(index=0,cover=1)]),
                dict(zone_features=[dict(index=0),dict(index=0,cover=True)]),
                dict(visibility=[dict(observer_id='pc',target_id='pc',visible=True)]),
                dict(visibility=[dict(observer_id='pc',target_id='generated-npc:2',visible=True)]),
                dict(visibility=[dict(observer_id='pc',target_id='generated-npc:1',visible=True),
                    dict(observer_id='pc',target_id='generated-npc:1',visible=False)]),dict(darkness=1)):
            with self.subTest(scene=scene),self.assertRaises(DynamicEncounterInputError):state(**scene)
        with self.assertRaises(TypeError):PcBattlefieldSpec(R.SHORT,R.LONG,zone_features=[PcZoneFeatures(0)])

    def test_terrain_route_covers_actual_departure_arrival_and_within_zone_movement(self):
        current=state(zone_features=[dict(index=0,difficult_terrain=True),dict(index=1,difficult_terrain=True)])
        before=current.battlefield
        self.assertEqual(difficult_terrain_crossed(current,'pc',before,('arena:zone:1',),moved=True),
            ('arena:zone:0','arena:zone:1'))
        self.assertEqual(difficult_terrain_crossed(current,'pc',before,(),moved=True),('arena:zone:0',))
        self.assertEqual(difficult_terrain_crossed(current,'pc',before,(),moved=False),())
        with self.assertRaises(ValueError):difficult_terrain_crossed(current,'pc',before,('arena:zone:2',),moved=True)
        with self.assertRaises(ValueError):difficult_terrain_crossed(current,'pc',before,('arena:zone:1',),moved=False)

    def test_fly_and_move_carefully_bypass_need_actual_capability_route_or_action(self):
        current=state(zone_features=[dict(index=0,difficult_terrain=True)],flying=True)
        before=current.battlefield
        self.assertEqual(difficult_terrain_crossed(current,'pc',before,
            ('arena:air:0','arena:air:1'),moved=True,flying=True),())
        with self.assertRaises(ValueError):difficult_terrain_crossed(current,'pc',before,
            ('arena:zone:1',),moved=True,flying=True)
        with self.assertRaises(ValueError):difficult_terrain_crossed(current,'pc',before,(),moved=True,move_carefully=True)
        clock=start_combat_turn(CombatTurnStartRequest('features:start',current.round_state,'pc')).state
        clock=reserve_combat_action_slot(CombatActionSlotRequest('features:carefully',clock,'pc',
            CombatActionDeclaration(CombatActionKind.MANOEUVRE,manoeuvre=ManoeuvreKind.MOVE_CAREFULLY),
            ActionSlotGrant.STANDARD)).state
        current=replace(current,round_state=clock)
        self.assertEqual(difficult_terrain_crossed(current,'pc',before,(),moved=True,move_carefully=True),())

