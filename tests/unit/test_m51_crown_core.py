"""Crown has a distinct same-target clock grant and real Brawn opposition."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import AttackRequest, DamageImpactSpec, DamageProfile, ResilienceProfile
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.npc_attack_preparation_models import (
    NpcAttackProfile, NpcAttackPreparationRequest, NpcAttackSelectionSnapshot,
)
from towr.domain.protection_models import ProtectionPreparationRequest, ProtectionTestOption
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange as Range
from towr.domain.resolution_models import KernelAttackRequest, TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill, TestRequest
from towr.domain.turn_models import (
    CROWN_OF_ANTLERS_RULE_ID, ENDURING_STRENGTH_RULE_ID, ActionExecutionReceipt, ActionSlotGrant,
    CombatActionDeclaration, CombatActionKind, CombatActionSlot, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnState,
    CrownOfAntlersGrant, EnduringStrengthGrant,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.npc_attack_preparation import prepare_npc_attack
from towr.rules.protection_preparation import prepare_protection
from towr.rules.turn_resolution import reserve_combat_action_slot


def crown_request():
    declaration = CombatActionDeclaration(CombatActionKind.ATTACK)
    receipt = ActionExecutionReceipt('first:execute','RULE-COMBAT-004:attack-action-execution',
        'first:kernel','first:kernel','stag',1,1,declaration)
    first = CombatActionSlot(1,declaration,ActionSlotGrant.STANDARD,execution=receipt)
    state = CombatRoundState(1,(CombatTurnParticipant('victim',CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant('stag',CombatSide.OPPOSITION)),completed_turn_entity_ids=('victim',),
        active_turn=CombatTurnState('stag',CombatSide.OPPOSITION,(first,)))
    grant = CrownOfAntlersGrant('stag',1,'reserve2',receipt,'victim','victim','trample')
    return CombatActionSlotRequest('reserve2',state,'stag',declaration,ActionSlotGrant.ABILITY,
        CROWN_OF_ANTLERS_RULE_ID,crown_of_antlers=grant)


def attack_request(state,target='victim'):
    attack = AttackRequest('second:test',TestRequest('second:attacker',InlineProfile(5,3)),None,
        DamageImpactSpec(DamageProfile(5),ResilienceProfile(3)),True,False)
    kernel = KernelAttackRequest('second:kernel',target,attack,TargetInjuryPolicy.MINION,
        ProfileInjuryState(0,1),False,False)
    return AttackActionExecutionRequest('second:execute',state,'stag',target,2,kernel)


def brawn_profile():
    return NpcAttackProfile('trample','book:trample',Skill.BRAWN,InlineProfile(5,3),
        DamageProfile(5),Range.CLOSE,Range.CLOSE,None)


def prepare_brawn(**changes):
    profile = brawn_profile()
    values = dict(id='prepare',attack_id='attack',attacker_test_id='attacker',
        snapshot=NpcAttackSelectionSnapshot('source','stag',(profile,),('trample',)),
        selected_attack_id='trample',target_id='victim',target_range=Range.CLOSE,
        target_resilience=ResilienceProfile(3),has_enemy_in_close_range=True,
        attacker_is_staggered=False,range_approved_by_gm=False)
    values.update(changes)
    return prepare_npc_attack(NpcAttackPreparationRequest(**values))


class CrownCoreTests(unittest.TestCase):
    def test_actual_second_slot_preserves_receipt_and_same_target(self):
        request = crown_request()
        result = reserve_combat_action_slot(request)
        self.assertEqual(result.slot.index,2)
        self.assertEqual(result.slot.crown_of_antlers,request.crown_of_antlers)
        self.assertIsNone(result.slot.enduring_strength)
        self.assertEqual(result.slot.crown_of_antlers.first_target_id,result.slot.crown_of_antlers.target_id)
        self.assertEqual(result.state.active_turn.action_slots[0],request.state.active_turn.action_slots[0])
        self.assertEqual(result.applied_rule_ids,('RULE-COMBAT-002:action-budget',CROWN_OF_ANTLERS_RULE_ID))

    def test_rule_id_without_grant_never_authorizes_an_attack(self):
        request = crown_request()
        with self.assertRaises(ValueError):
            replace(request,crown_of_antlers=None)
        with self.assertRaises(ValueError):
            CombatActionSlot(2,request.declaration,ActionSlotGrant.ABILITY,CROWN_OF_ANTLERS_RULE_ID)

    def test_crown_cannot_borrow_bear_rule_or_fate_budget(self):
        request = crown_request()
        for changes in (dict(grant_rule_id=ENDURING_STRENGTH_RULE_ID),
                dict(grant=ActionSlotGrant.FATE,grant_rule_id=None),
                dict(declaration=CombatActionDeclaration(CombatActionKind.RECOVER))):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(request,**changes)

    def test_crown_and_bear_grants_cannot_coexist(self):
        request = crown_request()
        bear = EnduringStrengthGrant('stag',1,'reserve2',request.crown_of_antlers.first_execution,
            'victim','other')
        with self.assertRaises(ValueError):
            replace(request,enduring_strength=bear)
        with self.assertRaises(ValueError):
            CombatActionSlot(2,request.declaration,ActionSlotGrant.ABILITY,CROWN_OF_ANTLERS_RULE_ID,
                enduring_strength=bear,crown_of_antlers=request.crown_of_antlers)

    def test_wrong_actor_round_reservation_target_or_attack_is_rejected(self):
        request = crown_request()
        for changes in (dict(actor_id='other'),dict(round_number=2),dict(slot_request_id='other'),
                dict(target_id='other'),dict(attack_id='mighty_antlers')):
            with self.subTest(changes=changes),self.assertRaises((ValueError,TypeError)):
                replace(request,crown_of_antlers=replace(request.crown_of_antlers,**changes))

    def test_foreign_or_unexecuted_first_receipt_cannot_be_reserved(self):
        request = crown_request()
        first = request.state.active_turn.action_slots[0]
        for replacement in (replace(first,execution=None),
                replace(first,execution=replace(first.execution,id='foreign'))):
            state = replace(request.state,active_turn=replace(request.state.active_turn,action_slots=(replacement,)))
            with self.assertRaises(ValueError):
                replace(request,state=state)

    def test_third_action_is_rejected_even_with_the_original_grant(self):
        request = crown_request()
        result = reserve_combat_action_slot(request)
        with self.assertRaises(ValueError):
            reserve_combat_action_slot(replace(request,state=result.state))

    def test_ready_round_readmits_nested_crown_sources(self):
        state = reserve_combat_action_slot(crown_request()).state
        for field,value in (('round_number',2),('first_target_id','other'),('attack_id','antlers')):
            changed = deepcopy(state)
            object.__setattr__(changed.active_turn.action_slots[1].crown_of_antlers,field,value)
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                replace(changed)

    def test_equal_cached_aliases_are_not_clock_proofs(self):
        state = reserve_combat_action_slot(crown_request()).state
        for subject,field,value in (('grant','round_number',1.0),('receipt','slot_index',True),
                ('declaration','improvise_produces_attack',0)):
            changed = deepcopy(state)
            grant = changed.active_turn.action_slots[1].crown_of_antlers
            item = grant if subject=='grant' else grant.first_execution if subject=='receipt' else changed.active_turn.action_slots[1].declaration
            object.__setattr__(item,field,value)
            self.assertEqual(changed,state)
            with self.subTest(subject=subject),self.assertRaises(TypeError):
                replace(changed)

    def test_executor_rejects_another_target_before_rng(self):
        state = reserve_combat_action_slot(crown_request()).state
        rng = Mock(side_effect=AssertionError('wrong Crown target must not roll'))
        with self.assertRaises(ValueError):
            execute_attack_action(attack_request(state,'other'),rng)
        rng.randint.assert_not_called()

    def test_real_executor_receipt_and_ready_result_bind_same_target_once(self):
        state = reserve_combat_action_slot(crown_request()).state
        result = execute_attack_action(attack_request(state),SequenceRandom((1,1,1,1,1)))
        self.assertEqual((result.slot_index,result.target_id,result.slot.crown_of_antlers.attack_id),
            (2,'victim','trample'))
        self.assertTrue(result.slot.executed)
        self.assertEqual(len(result.state.active_turn.action_slots),2)
        with self.assertRaises(ValueError):
            replace(result,target_id='other')
        with self.assertRaises(ValueError):
            execute_attack_action(attack_request(result.state),Mock())


class BrawnPreparationTests(unittest.TestCase):
    def test_natural_brawn_uses_printed_pool_damage_close_and_no_ranged_penalty(self):
        result = prepare_brawn()
        self.assertIs(result.selected_profile.skill,Skill.BRAWN)
        self.assertEqual((result.attack.attacker_test.profile.base_dice,
            result.attack.attacker_test.profile.maximum_dice),(5,10))
        self.assertEqual(result.attack.impact_spec.damage,DamageProfile(5))
        self.assertFalse(result.attack.attacker_test.dice_modifiers)
        self.assertTrue(result.attack.is_close_range)

    def test_brawn_rejects_weapon_hands_and_non_close_profile_or_target(self):
        for hands in (RangedWeaponHands.ONE_HANDED,RangedWeaponHands.TWO_HANDED):
            with self.subTest(hands=hands),self.assertRaises(ValueError):
                replace(brawn_profile(),hands=hands)
        for changes in (dict(range_min=Range.SHORT,range_max=Range.SHORT),dict(range_max=Range.SHORT)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                replace(brawn_profile(),**changes)
        with self.assertRaises(ValueError):
            prepare_brawn(target_range=Range.SHORT)
        with self.assertRaises(ValueError):
            prepare_brawn(range_approved_by_gm=True)

    def test_brawn_endurance_or_athletics_are_eligible_even_when_armed(self):
        attack = prepare_brawn().attack
        for skill in (Skill.ENDURANCE,Skill.ATHLETICS):
            option = ProtectionTestOption('victim',skill,TestRequest('protection',InlineProfile(3,4)))
            source = ProtectionPreparationRequest('opposed','victim',attack,Skill.BRAWN,
                True,False,True,True,skill,(option,))
            result = prepare_protection(source)
            self.assertEqual(result.eligible_skills,(Skill.ATHLETICS,Skill.ENDURANCE))
            self.assertEqual(result.attack.defender_test,option.test)

    def test_brawn_never_uses_weapon_or_shield_defence(self):
        attack = prepare_brawn().attack
        option = ProtectionTestOption('victim',Skill.DEFENCE,TestRequest('protection',InlineProfile(3,4)))
        for weapon,shield in ((False,False),(True,False),(False,True),(True,True)):
            with self.subTest(weapon=weapon,shield=shield),self.assertRaises(ValueError):
                ProtectionPreparationRequest('opposed','victim',attack,Skill.BRAWN,
                    True,False,weapon,shield,Skill.DEFENCE,(option,))

    def test_endurance_cannot_oppose_melee_and_defenceless_brawn_is_unopposed(self):
        attack = prepare_brawn().attack
        option = ProtectionTestOption('victim',Skill.ENDURANCE,TestRequest('protection',InlineProfile(3,4)))
        with self.assertRaises(ValueError):
            ProtectionPreparationRequest('opposed','victim',attack,Skill.MELEE,
                True,False,True,False,Skill.ENDURANCE,(option,))
        result = prepare_protection(ProtectionPreparationRequest('unopposed','victim',attack,
            Skill.BRAWN,True,True,True,False,None,()))
        self.assertFalse(result.eligible_skills)
        self.assertIsNone(result.attack.defender_test)
