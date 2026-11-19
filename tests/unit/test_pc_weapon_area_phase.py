"""Prepared phase boundaries with genuine completed K1 actions and Tests.

Prepared burning bodies/clocks isolate continuation guards; these snapshots
are not claimed as complete native replay histories. Native coverage lives
with the weapon encounter integration tests.
"""
from copy import copy
from dataclasses import replace
import unittest

from tests.support.pc_bear_scenarios import bear_scene
from tests.support.pc_hochland_scenarios import make_pc_hochland_scenario
from tests.support.pc_magic_scenarios import magic_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_pc_demigryph import reserved,after_primary
from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.pc_aim_models import PcAimProof,build_pc_aim,build_pc_aim_second_action
from towr.domain.pc_demigryph_models import build_pc_demigryph_strike
from towr.domain.pc_magic_models import (
    build_pc_casting_request,complete_pc_casting,guarded_casting_test,project_pc_magic_step,
)
from towr.domain.pc_magic_source_models import ELEMENTALISM_LORE_ID
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcFateDecline,initial_pc_melee_state,build_pc_melee_attack,
)
from towr.domain.pc_npc_extra_attack_models import build_pc_npc_extra_attack_slot
from towr.domain.pc_weapon_area_models import (
    ABLAZE_HAZARD_RULE_ID,PcWeaponHazardRequest,PcWeaponHazardProof,
    _canonical_hazard,expected_ablaze_hazard,weapon_hazard_resolution_request,
)
from towr.domain.pc_weapon_intent_models import build_pc_attack_weapon_intent
from towr.domain.resolution_models import HazardExposureRequest,TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill,TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant,CombatActionDeclaration,CombatActionKind,CombatActionSlotRequest,
    CombatTurnStartRequest,ImproviseKind,
)
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.protection_preparation import prepare_protection
from towr.rules.test_resolution import resolve_test,KeepAllFailures
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot


def prepared_turn(source,actor,declaration):
    state=initial_pc_melee_state(source)
    clock=state.round_state
    if actor in source.enemy_activation_order:
        clock=replace(clock,completed_turn_entity_ids=source.pc_activation_order)
    clock=start_combat_turn(CombatTurnStartRequest('phase:start',clock,actor)).state
    clock=reserve_combat_action_slot(CombatActionSlotRequest('phase:reserve',clock,actor,
        declaration,ActionSlotGrant.STANDARD)).state
    return replace(state,round_state=clock)


def burning(state,actor):
    """Explicit prepared injury boundary; it does not invent a prior Oil hit."""
    if actor in state.source.pc_activation_order:
        return replace(state,party=tuple(replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.ABLAZE)))
            if member.actor_id==actor else member for member in state.party))
    return replace(state,enemies=tuple(replace(enemy,state=replace(enemy.state,
        injury=replace(enemy.state.injury,conditions=enemy.state.injury.conditions.with_condition(Condition.ABLAZE))))
        if enemy.state.actor_id==actor else enemy for enemy in state.enemies))


def after_aim(*,second_action):
    source=make_pc_hochland_scenario(use_second_action=second_action,backup=False)
    actor=source.pc_activation_order[0]
    state=prepared_turn(source,actor,CombatActionDeclaration(CombatActionKind.AIM))
    request=build_pc_aim(state)
    rng=ScriptedD10([1,1,1])
    result=execute_aim_action(request,rng)
    rng.assert_exhausted()
    proof=PcAimProof(request,result,PcFateDecline(actor,request.awareness_test.id,'test',source.participant(actor).fate_policy))
    return burning(replace(state,round_state=result.round_state,history=(*state.history,proof)),actor)


class PcWeaponAreaPhaseTests(unittest.TestCase):
    def test_mantle_bonus_is_for_ablaze_not_direct_blast_and_drained_suppresses_it(self):
        from tests.unit.test_pc_extinguish import prepared
        from towr.domain.armour_models import ArmourLoadout,BodyArmour,ITHILMAR_ENVIRONMENT_RULE_ID
        from towr.domain.pc_weapon_area_models import _hazard_request,BLAST_IMPACT_RULE_ID
        mantle=BodyArmour.ITHILMAR
        armour=ArmourLoadout((mantle,),mantle)
        for npc in (False,True):
            for drained in (False,True):
                with self.subTest(npc=npc,drained=drained):
                    conditions=(Condition.ABLAZE,Condition.DRAINED) if drained else (Condition.ABLAZE,)
                    state,actor=prepared(npc=npc,armour=armour,conditions=conditions)
                    fire=_hazard_request(state,actor,'fire',2,ABLAZE_HAZARD_RULE_ID)
                    blast=_hazard_request(state,actor,'blast',3,BLAST_IMPACT_RULE_ID)
                    bonus=lambda request:tuple(mod.amount for mod in request.avoidance_test.dice_modifiers
                        if mod.rule_id==ITHILMAR_ENVIRONMENT_RULE_ID)
                    self.assertEqual(bonus(fire),() if drained else (1,))
                    self.assertEqual(bonus(blast),())
    def test_ablaze_waits_for_real_funded_aim_second_action(self):
        state=after_aim(second_action=True)
        self.assertIsNotNone(build_pc_aim_second_action(state))
        self.assertIsNone(expected_ablaze_hazard(state))

    def test_finished_single_action_exposes_fire_once_without_another_action(self):
        state=after_aim(second_action=False)
        request=expected_ablaze_hazard(state)
        self.assertIsNotNone(request)
        self.assertEqual(request.exposure.rating,2)
        self.assertEqual(request.exposure.rule_id,ABLAZE_HAZARD_RULE_ID)
        rng=ScriptedD10([1,1,1])
        test=resolve_test(request.avoidance_test,rng)
        result=resolve_hazard(weapon_hazard_resolution_request(request,test),rng)
        rng.assert_exhausted()
        self.assertTrue(result.avoided)
        proof=PcWeaponHazardProof(request,test,result,PcFateDecline(request.actor_id,
            request.avoidance_test.id,'test',state.source.participant(request.actor_id).fate_policy))
        after=replace(state,history=(*state.history,proof))
        self.assertEqual(after.round_state,state.round_state)
        self.assertIsNone(expected_ablaze_hazard(after))

    def test_ablaze_waits_for_actual_demigryph_same_action_second_strike(self):
        state,_,_=after_primary(reserved())
        self.assertFalse(state.pending)
        self.assertIsNone(state.pending_wound)
        state=burning(state,state.source.pc_activation_order[0])
        self.assertIsNotNone(build_pc_demigryph_strike(state))
        self.assertIsNone(expected_ablaze_hazard(state))

    def test_ablaze_waits_for_bear_second_action_from_a_real_first_hit(self):
        source=bear_scene()
        source=replace(source,party=tuple(replace(member,pc=replace(member.pc,toughness=20))
            for member in source.party))
        actor=source.enemy_activation_order[0]
        state=prepared_turn(source,actor,CombatActionDeclaration(CombatActionKind.ATTACK))
        request,preparation=build_pc_melee_attack(state)
        rng=ScriptedD10([1,1,1,1,10,10,10])
        execution=execute_attack_action(request,rng,decisions=KeepAllFailures())
        rng.assert_exhausted()
        target=request.target_id
        proof=PcAttackProof(request,prepare_protection(preparation),execution,
            PcFateDecline(target,request.kernel_request.attack.defender_test.id,'test',source.participant(target).fate_policy),
            weapon_intent=build_pc_attack_weapon_intent(state))
        state=replace(state,round_state=execution.state,history=(*state.history,proof),
            party=tuple(replace(member,injury=execution.resolution.target_state)
                if member.actor_id==target else member for member in state.party))
        state=burning(state,actor)
        self.assertIsNotNone(build_pc_npc_extra_attack_slot(state))
        self.assertIsNone(expected_ablaze_hazard(state))

    def test_ablaze_waits_for_actual_casting_effect_cleanup(self):
        source=magic_scenario(reason=2,willpower=4,level=4,enemies=1)
        actor=source.pc_activation_order[0]
        state=prepared_turn(source,actor,CombatActionDeclaration(CombatActionKind.IMPROVISE,
            improvise_kind=ImproviseKind.SPELL,improvise_approach_id=ELEMENTALISM_LORE_ID))
        request=build_pc_casting_request(state)
        rng=ScriptedD10([1,1])
        test=resolve_test(guarded_casting_test(request.casting_request),rng,decisions=KeepAllFailures())
        rng.assert_exhausted()
        proof=complete_pc_casting(state,test,PcFateDecline(actor,request.casting_request.test.id,
            'test',source.participant(actor).fate_policy),None)
        state=project_pc_magic_step(state,proof)
        self.assertIsNotNone(state.magic_pending)
        state=burning(state,actor)
        self.assertIsNone(expected_ablaze_hazard(state))

    def test_hazard_rejects_tampered_near_miss_provenance(self):
        body=CharacterInjuryState()
        exposure=HazardExposureRequest('phase:hazard','phase:hazard:test',2,Skill.ENDURANCE,
            ABLAZE_HAZARD_RULE_ID,True,())
        source=TestRequest(exposure.test_id,InlineProfile(1,2))
        request=PcWeaponHazardRequest('phase:hazard','phase:event','pc',exposure,source,body,body,TargetInjuryPolicy.PLAYER)
        rng=ScriptedD10([10,1,1])
        test=resolve_test(source,rng)
        result=resolve_hazard(weapon_hazard_resolution_request(request,test),rng)
        rng.assert_exhausted()
        _canonical_hazard(request,test,result)
        self.assertTrue(result.pending_character_wound.near_miss_eligible)
        pending=copy(result.pending_character_wound)
        object.__setattr__(pending,'near_miss_eligible',False)
        with self.assertRaises(ValueError):
            _canonical_hazard(request,test,replace(result,pending_character_wound=pending))
