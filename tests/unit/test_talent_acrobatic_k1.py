"""Real K1 movement/fall sources; native encounter planning is checked separately."""
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, replace
import pickle
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import paid_talent
from tests.unit.test_k1_free_movement_resolution import request as free_request, spatial_state
from tests.unit.test_k1_run_action_execution import request as run_request
from tests.unit.test_k1_run_athletics_extension import request as extension_request
from tests.unit.test_k1_charge_action_execution import request as charge_request
from tests.unit.test_k1_long_charge_action_execution import request as long_charge_request
from tests.unit.test_k1_difficult_terrain_resolution import request as terrain_request
from tests.unit.test_k1_move_carefully_resolution import request as careful_request
from tests.unit.test_k1_spatial_resolution import state as ground_state, request as ground_request
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.movement_models import (
    MovementSpeed, DifficultTerrainFreeMovementRequest, DifficultTerrainRunActionExecutionRequest,
)
from towr.domain.charge_models import DifficultTerrainChargeActionExecutionRequest
from towr.domain.resolution_models import HazardExposureRequest, HazardResolutionRequest, TargetInjuryPolicy
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.talent_acrobatic_models import (
    ACROBATIC_RULE_ID, AcrobaticSource, AcrobaticFallReduction,
    acrobatic_fall_rating, validate_acrobatic_source,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.domain.turn_models import CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnStartRequest
from towr.rules.charge_action_execution import execute_charge_action, execute_long_charge_action, execute_difficult_terrain_charge_action
from towr.rules.difficult_terrain_resolution import resolve_difficult_terrain_traversal
from towr.rules.free_movement_resolution import resolve_free_movement, resolve_difficult_terrain_free_movement
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.move_carefully_resolution import execute_move_carefully_action
from towr.rules.run_action_execution import execute_run_action, resolve_run_athletics_extension, execute_difficult_terrain_run_action
from towr.rules.spatial_resolution import resolve_give_ground
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import start_combat_turn


def acrobatic(actor='hero'):
    return AcrobaticSource(actor,paid_talent(TalentId.ACROBATIC))


class NoRolls:
    def randint(self,low,high):
        raise AssertionError('invalid source or avoided fall must not roll a Wound')


class AcrobaticSourceTests(unittest.TestCase):
    def test_exact_source_is_immutable_and_other_talent_actor_or_alias_cannot_grant_it(self):
        source = acrobatic()
        self.assertTrue(validate_acrobatic_source(source,'hero'))
        self.assertFalse(validate_acrobatic_source(None,'hero'))
        self.assertEqual(pickle.loads(pickle.dumps(source)),source)
        with self.assertRaises((FrozenInstanceError,TypeError)):
            source.actor_id = 'enemy'
        for bad in (True,{},source.talent):
            with self.subTest(bad=bad),self.assertRaises(TypeError):
                validate_acrobatic_source(bad,'hero')
        with self.assertRaises(ValueError):
            validate_acrobatic_source(source,'enemy')
        with self.assertRaises(ValueError):
            AcrobaticSource('hero',paid_talent(TalentId.WILD_ATTACK))
        forged = deepcopy(source)
        object.__setattr__(forged,'talent',paid_talent(TalentId.WILD_ATTACK))
        with self.assertRaises(ValueError):
            validate_acrobatic_source(forged,'hero')

    def test_fall_retains_positive_gm_base_and_halves_once_with_floor(self):
        for base,expected in ((1,0),(2,1),(3,1),(5,2)):
            reduction = AcrobaticFallReduction(acrobatic(),base)
            self.assertEqual(reduction.base_rating,base)
            self.assertEqual(reduction.rating,expected)
            self.assertEqual(acrobatic_fall_rating(reduction.source,'hero',base),expected)
        for base in (True,0,-1,1.5,AcrobaticFallReduction(acrobatic(),3)):
            with self.subTest(base=base),self.assertRaises((TypeError,ValueError)):
                AcrobaticFallReduction(acrobatic(),base)

    def test_zero_fall_still_uses_a_real_failed_athletics_test_for_both_body_types(self):
        for policy,injury in ((TargetInjuryPolicy.PLAYER,CharacterInjuryState()),
                (TargetInjuryPolicy.CHAMPION,CharacterInjuryState()),
                (TargetInjuryPolicy.MINION,ProfileInjuryState(0,1))):
            actor = policy.value
            reduction = AcrobaticFallReduction(acrobatic(actor),1)
            exposure = HazardExposureRequest('fall','fall:athletics',0,Skill.ATHLETICS,
                'declared:fall',True,(Condition.PRONE,),acrobatic_fall=reduction)
            rng = ScriptedD10([10])
            test = resolve_test(TestRequest(exposure.test_id,TestProfile(1,5)),rng)
            rng.assert_exhausted()
            self.assertEqual(test.successes,0)
            request = HazardResolutionRequest('avoid',actor,exposure,test,policy,injury)
            result = resolve_hazard(request,NoRolls())
            self.assertTrue(result.avoided)
            self.assertEqual((result.rating,result.shortfall,result.state),(0,0,injury))
            with self.assertRaises(ValueError):
                replace(request,target_id='foreign')
            forged = copy(request)
            object.__setattr__(forged,'target_id','foreign')
            with self.assertRaises(ValueError):
                resolve_hazard(forged,NoRolls())

    def test_unrelated_hazard_does_not_accept_zero_or_an_implicitly_inferred_reduction(self):
        ordinary = HazardExposureRequest('fire','test',3,Skill.ENDURANCE,'fire',True,())
        self.assertEqual(ordinary.rating,3)
        with self.assertRaises(ValueError):
            replace(ordinary,rating=0)
        reduction = AcrobaticFallReduction(acrobatic(),3)
        for changes in (dict(acrobatic_fall=reduction),
                dict(rating=2,avoidance_skill=Skill.ATHLETICS,acrobatic_fall=reduction)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                replace(ordinary,**changes)


class AcrobaticMovementTests(unittest.TestCase):
    def assert_source(self,result,actor='hero'):
        self.assertEqual(result.acrobatic,acrobatic(actor))
        self.assertEqual(result.applied_rule_ids.count(ACROBATIC_RULE_ID),1)
        with self.assertRaises(ValueError):
            replace(result,acrobatic=None)
        with self.assertRaises(ValueError):
            replace(result,applied_rule_ids=(*result.applied_rule_ids,ACROBATIC_RULE_ID))

    def test_both_combat_sides_cross_real_enemy_ids_without_erasing_path_or_snapshot(self):
        for actor,path in (('hero',('enemy',)),('enemy',('hero',))):
            if actor == 'enemy':
                clock = CombatRoundState(1,(
                    CombatTurnParticipant('hero',CombatSide.PLAYERS_AND_ALLIES),
                    CombatTurnParticipant('enemy',CombatSide.OPPOSITION)),
                    side_order=(CombatSide.OPPOSITION,CombatSide.PLAYERS_AND_ALLIES))
                clock = start_combat_turn(CombatTurnStartRequest('start:enemy',clock,actor)).state
                base = free_request(actor_id=actor,round_state=clock,path_entity_ids=path)
            else:
                base = free_request(path_entity_ids=path)
            with self.assertRaises(ValueError):
                resolve_free_movement(base)
            request = replace(base,acrobatic=acrobatic(actor))
            result = resolve_free_movement(request)
            self.assert_source(result,actor)
            self.assertEqual(result.path_entity_ids,path)
            self.assertEqual(result.previous_state,request.state)
            self.assertEqual(result.state.free_move_used_entity_ids,(actor,))
            with self.assertRaises(ValueError):
                replace(request,acrobatic=acrobatic('foreign'))
            forged = copy(request)
            object.__setattr__(forged,'acrobatic',acrobatic('foreign'))
            with self.assertRaises(ValueError):
                resolve_free_movement(forged)

    def test_free_movement_still_obeys_obstacle_terrain_prone_defenceless_and_budget(self):
        source = replace(free_request(path_entity_ids=('enemy',)),acrobatic=acrobatic())
        for changes in (dict(crosses_obstacle=True),dict(crosses_difficult_terrain=True),
                dict(actor_conditions=ConditionState(frozenset({Condition.PRONE}))),
                dict(actor_conditions=ConditionState(frozenset({Condition.DEFENCELESS}))),
                dict(state=spatial_state(free_move_used=('hero',)))):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                resolve_free_movement(replace(source,**changes))

    def test_run_and_athletics_extension_retain_each_real_crossed_path(self):
        request = replace(run_request(path_entity_ids=('enemy',)),acrobatic=acrobatic())
        result = execute_run_action(request)
        self.assert_source(result)
        self.assertEqual(result.path_entity_ids,('enemy',))
        extension = replace(extension_request(path_entity_ids=('enemy',)),acrobatic=acrobatic())
        rng = ScriptedD10([1])
        continued = resolve_run_athletics_extension(extension,rng)
        rng.assert_exhausted()
        self.assert_source(continued)
        self.assertEqual(continued.path_entity_ids,('enemy',))
        for changes in (dict(crosses_obstacle=True),dict(crosses_difficult_terrain=True),
                dict(actor_conditions=ConditionState(frozenset({Condition.BURDENED}))),dict(speed=MovementSpeed.SLOW)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                execute_run_action(replace(request,**changes))

    def test_medium_and_long_charge_keep_path_sources_and_begin_close_restriction(self):
        for factory,execute,values in ((charge_request,execute_charge_action,[1,10]),
                (long_charge_request,execute_long_charge_action,[1,1,10])):
            request = replace(factory(path_entity_ids=('blocker',)),acrobatic=acrobatic())
            rng = ScriptedD10(values)
            result = execute(request,rng)
            rng.assert_exhausted()
            self.assert_source(result)
            self.assertEqual(result.path_entity_ids,('blocker',))
            for changes in (dict(actor_began_turn_in_enemy_close_range=True),dict(crosses_obstacle=True),
                    dict(crosses_difficult_terrain=True),dict(speed=MovementSpeed.SLOW),
                    dict(actor_conditions=ConditionState(frozenset({Condition.BURDENED})))):
                with self.subTest(changes=changes),self.assertRaises(ValueError):
                    execute(replace(request,**changes),NoRolls())

    def test_terrain_crossing_keeps_athletics_failure_and_move_carefully_does_not_ignore_obstacles(self):
        request = replace(terrain_request(path_entity_ids=('enemy',)),acrobatic=acrobatic())
        rng = ScriptedD10([10])
        result = resolve_difficult_terrain_traversal(request,rng)
        rng.assert_exhausted()
        self.assert_source(result)
        self.assertTrue(result.conditions.has(Condition.PRONE))
        self.assertEqual(result.path_entity_ids,('enemy',))
        original = careful_request(path_entity_ids=('enemy',))
        careful = replace(original,free_movement=replace(original.free_movement,acrobatic=acrobatic()))
        crossed = execute_move_carefully_action(careful,NoRolls())
        self.assertEqual(crossed.source_request.free_movement.path_entity_ids,('enemy',))
        self.assertEqual(crossed.applied_rule_ids.count(ACROBATIC_RULE_ID),1)
        with self.assertRaises(ValueError):
            execute_move_carefully_action(replace(careful,
                free_movement=replace(careful.free_movement,crosses_obstacle=True)),NoRolls())

    def test_give_ground_bypasses_enemy_path_but_still_applies_broken_in_enemy_destination(self):
        state = ground_state(SpatialEntityPlacement('mover','heroes','zone:a'),
            SpatialEntityPlacement('attacker','enemies','zone:a'),
            SpatialEntityPlacement('blocker','enemies','zone:a'),
            SpatialEntityPlacement('destination-enemy','enemies','zone:b'))
        request = replace(ground_request(state,path_entity_ids=('blocker',)),acrobatic=acrobatic('mover'))
        result = resolve_give_ground(request)
        self.assert_source(result,'mover')
        self.assertEqual(result.source_request.path_entity_ids,('blocker',))
        self.assertTrue(result.conditions.has(Condition.BROKEN))
        for changes in (dict(crosses_obstacle=True),dict(crosses_difficult_terrain=True),
                dict(mover_conditions=ConditionState(frozenset({Condition.PRONE}))),
                dict(state=replace(state,gave_ground_entity_ids=('mover',)))):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                resolve_give_ground(replace(request,**changes))

    def test_terrain_composites_require_the_same_actual_talent_and_path_in_both_phases(self):
        for kind in ('free','run','charge'):
            factory = {'free':free_request,'run':run_request,'charge':charge_request}[kind]
            path = ('blocker',) if kind == 'charge' else ('enemy',)
            movement = replace(factory(path_entity_ids=path,crosses_difficult_terrain=True),acrobatic=acrobatic())
            previous = movement.state if kind == 'free' else movement.spatial_state
            terrain = replace(terrain_request(),round_state=movement.round_state,state=previous,
                path_entity_ids=path,acrobatic=acrobatic())
            rng = ScriptedD10([1])
            traversal = resolve_difficult_terrain_traversal(terrain,rng)
            rng.assert_exhausted()
            if kind == 'free':
                request = DifficultTerrainFreeMovementRequest('compound',movement,traversal,traversal.state)
                result = resolve_difficult_terrain_free_movement(request)
                self.assertEqual(result.free_movement_request.path_entity_ids,path)
            elif kind == 'run':
                request = DifficultTerrainRunActionExecutionRequest('compound',movement,traversal,
                    movement.round_state,traversal.state)
                result = execute_difficult_terrain_run_action(request)
                self.assertEqual(result.run_action_request.path_entity_ids,path)
            else:
                request = DifficultTerrainChargeActionExecutionRequest('compound',movement,traversal,
                    movement.round_state,traversal.state)
                rng = ScriptedD10([1,10])
                result = execute_difficult_terrain_charge_action(request,rng)
                rng.assert_exhausted()
                self.assertEqual(result.charge_action_request.path_entity_ids,path)
            self.assertEqual(result.terrain_traversal.acrobatic,acrobatic())
            self.assertEqual(result.applied_rule_ids.count(ACROBATIC_RULE_ID),1)
            broken = replace(movement,acrobatic=None)
            with self.assertRaises(ValueError):
                replace(request,**{{'free':'free_movement','run':'run_action','charge':'charge_action'}[kind]:broken})


if __name__=='__main__':
    unittest.main()
