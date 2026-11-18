"""Deterministic Manoeuvre phases and source-bound use of the ordinary Attack."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source, tactical_snapshot
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import AttackRequest, DamageImpactSpec, DamageProfile, ResilienceProfile
from towr.domain.charge_models import ChargeActionExecutionRequest, ChargeMovementRequest
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.movement_models import (
    MovementSpeed, RunActionExecutionRequest, RunAthleticsExtensionRequest,
)
from towr.domain.pc_battlefield_models import PcBattlefieldSpec, battlefield_range
from towr.domain.pc_battlefield_manoeuvre_models import (
    PcBattlefieldChargeProof, battlefield_after_manoeuvre, build_pc_battlefield_charge,
    current_pc_charge, pc_charge_attack_modifiers, proposed_pc_battlefield_manoeuvre,
    project_pc_battlefield_manoeuvre,
)
from towr.domain.pc_battlefield_movement_models import expected_pc_battlefield_move
from towr.domain.pc_melee_models import PcFatePolicy, PcGloriousPolicy
from towr.domain.pc_melee_result_models import PcMeleeStep
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import KernelAttackRequest, TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import DiceModifier, InlineProfile, Skill, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnStartRequest, ManoeuvreKind,
)
from towr.rules.attack_action_execution import execute_attack_action, _validate_attack_action_slot
from towr.rules.charge_action_execution import (
    execute_charge_action,execute_charge_movement,_complete_charge_movement_after_test,
)
from towr.rules.run_action_execution import (
    execute_run_action, resolve_run_athletics_extension, _complete_run_athletics_extension_after_test,
)
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


R = RangedWeaponRange


class NoRoll:
    def randint(self,a,b):
        raise AssertionError('this phase must reject or complete before RNG')


def clock(kind=ManoeuvreKind.CHARGE):
    initial = CombatRoundState(1,(CombatTurnParticipant('hero',CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant('enemy',CombatSide.OPPOSITION)))
    active = start_combat_turn(CombatTurnStartRequest('start',initial,'hero')).state
    return reserve_combat_action_slot(CombatActionSlotRequest('reserve',active,'hero',
        CombatActionDeclaration(CombatActionKind.MANOEUVRE,manoeuvre=kind),ActionSlotGrant.STANDARD)).state


def spatial(offset,*,used=True):
    graph = ZoneGraph(tuple(f'z{i}' for i in range(4)),
        tuple(ZoneConnection(f'z{i}',f'z{i+1}') for i in range(3)))
    return SpatialBattleState(graph,(SpatialEntityPlacement('hero','party','z0'),
        SpatialEntityPlacement('enemy','opposition',f'z{offset}')),
        free_move_used_entity_ids=('hero',) if used else ())


def charge(distance=R.MEDIUM,*,conditions=ConditionState()):
    offset = {R.SHORT:0,R.MEDIUM:1,R.LONG:2}[distance]
    return ChargeMovementRequest('charge',clock(),spatial(offset),'hero','enemy',1,
        MovementSpeed.NORMAL,conditions,distance,False,
        TestRequest('athletics',InlineProfile(1,3)) if distance is R.LONG else None,
        'z1' if distance is R.LONG else None)


def kernel():
    return KernelAttackRequest('kernel','enemy',AttackRequest('attack',
        TestRequest('attack:test',InlineProfile(1,3)),None,
        DamageImpactSpec(DamageProfile(1),ResilienceProfile(3)),True,False),
        TargetInjuryPolicy.MINION,ProfileInjuryState(0,1),False,False)


def native_source(distance=R.MEDIUM,*,configured=False):
    original = automatic_source(pc_count=1,rounds=3)
    npc = GeneratedNpc(3,3,4,3,4,4,GeneratedWeapon.STAFF,False,defence=4,shield=False)
    member = original.party[0]
    if configured:
        member = replace(member,fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.ATHLETICS,),0,0))
    return replace(original,party=(member,),enemies=(npc.participant('minion1'),),
        facts=replace(original.facts,all_opponents_close=distance is R.CLOSE,can_leave_zone=True),
        battlefield=PcBattlefieldSpec(distance,R.LONG))


def reserve_native(state,kind=ManoeuvreKind.CHARGE):
    actor = state.round_state.active_turn.actor_id
    clock = reserve_combat_action_slot(CombatActionSlotRequest('pure:reserve',state.round_state,actor,
        CombatActionDeclaration(CombatActionKind.MANOEUVRE,manoeuvre=kind),ActionSlotGrant.STANDARD)).state
    return replace(state,round_state=clock)


class ChargeMovementPhaseTests(unittest.TestCase):
    def test_short_and_medium_movement_have_no_roll_and_leave_the_one_slot_for_attack(self):
        for distance in (R.SHORT,R.MEDIUM):
            with self.subTest(distance=distance):
                request = charge(distance)
                before = deepcopy(request)
                result = execute_charge_movement(request,NoRoll())
                self.assertTrue(result.attack_allowed)
                self.assertEqual(result.round_state,request.round_state)
                self.assertFalse(result.round_state.active_turn.action_slots[0].executed)
                self.assertEqual(result.spatial_state.placement_for('hero').zone_id,
                    result.spatial_state.placement_for('enemy').zone_id)
                self.assertEqual(result.spatial_state.free_move_used_entity_ids,('hero',))
                self.assertIsNone(result.athletics_test_result)
                self.assertEqual(request,before)

    def test_existing_direct_charge_executor_also_accepts_short_in_the_same_zone(self):
        source = charge(R.SHORT)
        request = ChargeActionExecutionRequest('direct',source.round_state,source.spatial_state,
            'hero','enemy',1,MovementSpeed.NORMAL,ConditionState(),Skill.MELEE,kernel(),False,True)
        rng = ScriptedD10([10,10])
        result = execute_charge_action(request,rng)
        rng.assert_exhausted()
        self.assertEqual((result.origin_zone_id,result.destination_zone_id),('z0','z0'))
        self.assertTrue(result.slot.executed)

    def test_successful_charge_uses_actual_manoeuvre_slot_through_the_ordinary_attack_executor(self):
        request = charge()
        movement = execute_charge_movement(request,NoRoll())
        source_kernel = kernel()
        boosted = replace(source_kernel,attack=replace(source_kernel.attack,
            attacker_test=replace(source_kernel.attack.attacker_test,
                dice_modifiers=(DiceModifier('RULE-COMBAT-009:charge-melee-bonus',1),))))
        attack = AttackActionExecutionRequest('execute',movement.round_state,'hero','enemy',1,
            boosted,charge_movement=movement)
        _validate_attack_action_slot(attack)
        rng = ScriptedD10([10,10])
        result = execute_attack_action(attack,rng)
        rng.assert_exhausted()
        self.assertEqual(len(result.state.active_turn.action_slots),1)
        self.assertTrue(result.slot.executed)
        self.assertIs(result.slot.declaration.kind,CombatActionKind.MANOEUVRE)
        self.assertIs(result.slot.declaration.manoeuvre,ManoeuvreKind.CHARGE)
        self.assertEqual(result.resolution.request_id,'kernel')
        self.assertEqual(result.resolution.attack.attacker_test.trace.rolled_dice,2)

    def test_long_success_and_failure_roll_athletics_once_and_failure_never_opens_an_attack(self):
        for die,succeeded in ((1,True),(10,False)):
            with self.subTest(die=die):
                request = charge(R.LONG)
                rng = ScriptedD10([die])
                result = execute_charge_movement(request,rng)
                rng.assert_exhausted()
                self.assertIs(result.attack_allowed,succeeded)
                self.assertEqual(result.spatial_state.placement_for('hero').zone_id,'z2' if succeeded else 'z1')
                self.assertIs(result.round_state.active_turn.action_slots[0].executed,not succeeded)
                self.assertIs(result.conditions.has(Condition.STAGGERED),not succeeded)
                if not succeeded:
                    with self.assertRaises(ValueError):
                        AttackActionExecutionRequest('forbidden',result.round_state,'hero','enemy',1,
                            kernel(),charge_movement=result)

    def test_failed_long_charge_preserves_one_existing_stagger_without_wound_or_second_application(self):
        request = charge(R.LONG,conditions=ConditionState(frozenset((Condition.STAGGERED,))))
        rng = ScriptedD10([10])
        result = execute_charge_movement(request,rng)
        rng.assert_exhausted()
        self.assertEqual(result.conditions,request.actor_conditions)
        self.assertTrue(result.stagger_application.was_already_present)
        self.assertFalse(result.attack_allowed)

    def test_invalid_conditions_beginning_close_range_and_forged_grant_fail_before_rng(self):
        request = charge()
        for condition in (Condition.BURDENED,Condition.PRONE,Condition.DEFENCELESS):
            with self.subTest(condition=condition),self.assertRaises(ValueError):
                replace(request,actor_conditions=ConditionState(frozenset((condition,))))
        for changes in (dict(speed=MovementSpeed.SLOW),dict(actor_began_turn_in_enemy_close_range=True),
                dict(target_range=R.EXTREME),dict(crosses_obstacle=True)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                execute_charge_movement(replace(request,**changes),NoRoll())
        movement = execute_charge_movement(request,NoRoll())
        valid = AttackActionExecutionRequest('valid',request.round_state,'hero','enemy',1,
            kernel(),charge_movement=movement)
        for changes in (dict(actor_id='enemy'),dict(target_id='hero'),dict(charge_movement=True)):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(valid,**changes)


class RunMovementPhaseTests(unittest.TestCase):
    def test_base_run_and_optional_extension_share_one_action_and_preserve_free_move_usage(self):
        base_request = RunActionExecutionRequest('run',clock(ManoeuvreKind.RUN),spatial(3),
            'hero',1,MovementSpeed.NORMAL,ConditionState(),'z1')
        base = execute_run_action(base_request)
        extension = RunAthleticsExtensionRequest('extension',base,
            TestRequest('extension:test',InlineProfile(1,3)),ConditionState(),'z2')
        for die,succeeded in ((1,True),(10,False)):
            rng = ScriptedD10([die])
            actual = resolve_run_athletics_extension(extension,rng)
            rng.assert_exhausted()
            self.assertEqual(actual.spatial_state.placement_for('hero').zone_id,'z2' if succeeded else 'z1')
            self.assertEqual(actual.spatial_state.free_move_used_entity_ids,('hero',))
            self.assertEqual(len(base.round_state.active_turn.action_slots),1)
            self.assertTrue(base.slot.executed)
            self.assertIs(actual.conditions.has(Condition.STAGGERED),not succeeded)
            self.assertEqual(_complete_run_athletics_extension_after_test(extension,
                actual.athletics_test_result),actual)


class NativeBattlefieldManoeuvreTests(unittest.TestCase):
    def test_medium_charge_is_proposed_before_free_approach_but_close_attack_has_priority(self):
        state = tactical_snapshot(native_source())
        proposal = proposed_pc_battlefield_manoeuvre(state)
        self.assertIs(proposal.kind,ManoeuvreKind.CHARGE)
        self.assertEqual((proposal.actor_id,proposal.target_id),('pc1','minion1'))
        self.assertIsNone(proposed_pc_battlefield_manoeuvre(tactical_snapshot(native_source(R.CLOSE))))
        self.assertIsNone(proposed_pc_battlefield_manoeuvre(tactical_snapshot(native_source(R.LONG))))

    def test_native_charge_phase_binds_target_close_links_and_once_only_bonus(self):
        state = reserve_native(tactical_snapshot(native_source()))
        request = build_pc_battlefield_charge(state,'minion1')
        result = _complete_charge_movement_after_test(request)
        after = battlefield_after_manoeuvre(state,result,'minion1')
        proof = PcBattlefieldChargeProof(request,result,state.battlefield,after)
        updates = project_pc_battlefield_manoeuvre(state,proof)
        self.assertEqual(updates['battlefield'],after)
        self.assertEqual(battlefield_range(after,'pc1','minion1'),R.CLOSE)
        current = replace(state,history=(*state.history,proof),**updates)
        self.assertEqual(current_pc_charge(current,'pc1'),result)
        modifiers = pc_charge_attack_modifiers(current,'pc1','minion1')
        self.assertEqual(tuple(item.amount for item in modifiers),(1,))
        self.assertEqual(pc_charge_attack_modifiers(current,'pc1','other'),())
        with self.assertRaises(ValueError):
            project_pc_battlefield_manoeuvre(current,proof)

    def test_long_after_real_free_move_preserves_configured_pc_fate_for_athletics(self):
        from towr.engine.pc_melee_runner import _resolve_pc_test, _Decisions
        state = tactical_snapshot(native_source(R.EXTREME,configured=True))
        movement = expected_pc_battlefield_move(state)
        self.assertIsNotNone(movement)
        state = PcMeleeStep(state,movement).state
        self.assertIs(proposed_pc_battlefield_manoeuvre(state).kind,ManoeuvreKind.CHARGE)
        state = reserve_native(state)
        request = build_pc_battlefield_charge(state,'minion1')
        self.assertIs(request.target_range,R.LONG)
        rng = ScriptedD10([10,10,10,1,1,1])
        test,decline,glorious,effective = _resolve_pc_test(state,'pc1',Skill.ATHLETICS,
            request.athletics_test,rng,_Decisions())
        rng.assert_exhausted()
        self.assertIsNotNone(glorious)
        result = _complete_charge_movement_after_test(replace(request,athletics_test=effective),test)
        proof = PcBattlefieldChargeProof(request,result,state.battlefield,
            battlefield_after_manoeuvre(state,result,'minion1'),decline,glorious)
        updates = project_pc_battlefield_manoeuvre(state,proof)
        member, = updates['party']
        self.assertEqual(member.fate.remaining_spends,state.participant('pc1').fate.remaining_spends-1)
        with self.assertRaises((TypeError,ValueError)):
            project_pc_battlefield_manoeuvre(state,replace(proof,glorious=None))


if __name__ == '__main__':
    unittest.main()
