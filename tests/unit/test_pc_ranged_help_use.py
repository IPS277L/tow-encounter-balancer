"""Shooting Help consumes a selected Repeater Test bonus, never a fake shot."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_ranged_scenarios import make_pc_ranged_scenario
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.help_models import HelpActionExecutionRequest
from towr.domain.exacting_test_models import ExactingTestContributionRequest
from towr.domain.attack_models import ResilienceProfile
from towr.domain.pc_melee_models import PcMeleePolicy, PcMeleeWeapon, PcRepeaterBonusPolicy
from towr.domain.pc_combat_equipment_models import PcWeaponItem, PcItemLocation
from towr.domain.pc_help_models import build_pc_help_action
from towr.domain.pc_tactical_models import PcTacticalChoice, select_pc_tactic
from towr.domain.pc_melee_result_models import initial_pc_melee_state, pc_melee_action_id, _pc_test, PcHelpProof, PcMeleeStep
from towr.domain.pc_ranged_models import complete_pc_ranged_help, PcRangedHelpUseProof, pc_repeater_attack_modifiers, pc_ranged_unsupported
from towr.domain.ranged_weapon_profiles import REPEATER_SHOOTING_BONUS_RULE_ID
from towr.domain.reload_models import begin_reload_cycle
from towr.domain.test_models import InlineProfile, QualityModifier, Skill, TestQuality
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind,
    CombatActionSlotRequest, CombatTurnStartRequest,
)
from towr.rules.help_resolution import execute_help_action
from towr.rules.exacting_test_resolution import resolve_exacting_test_contribution
from towr.rules.test_resolution import RerollAllFailures
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


def prepared_help(weapon, *, bonus=True, drained=False, skill=Skill.SHOOTING):
    """Local prepared boundary; actual Help execution below owns slot and Test."""
    mode = (None if weapon is PcMeleeWeapon.PISTOL else
        PcRepeaterBonusPolicy.WHEN_AVAILABLE if bonus else PcRepeaterBonusPolicy.NEVER)
    source = make_pc_ranged_scenario(weapon=weapon,repeater_bonus_policy=mode,pc_count=2)
    state = initial_pc_melee_state(source)
    if drained:
        helper_state = state.party[0]
        helper_state = replace(helper_state,injury=replace(helper_state.injury,
            conditions=ConditionState(frozenset({Condition.DRAINED}))))
        state = replace(state,party=(helper_state,state.party[1]))
    action = pc_melee_action_id(state,'pc1')
    clock = start_combat_turn(CombatTurnStartRequest(action+':start',state.round_state,'pc1')).state
    clock = reserve_combat_action_slot(CombatActionSlotRequest(action+':reserve',clock,'pc1',
        CombatActionDeclaration(CombatActionKind.HELP),ActionSlotGrant.STANDARD)).state
    state = replace(state,round_state=clock)
    test = _pc_test(state,'pc1',action+':help:test',skill)
    if skill is Skill.SHOOTING:
        test = replace(test,dice_modifiers=(*test.dice_modifiers,*pc_repeater_attack_modifiers(state,'pc1')))
    request = HelpActionExecutionRequest(action+':help:execute',state.round_state,'pc1',
        state.party[0].injury.conditions,'pc2',pc_melee_action_id(state,'pc2')+':attack',
        1,test,skill,skill)
    return state,request


def execute_help(request,values):
    rng = ScriptedD10(values)
    execution = execute_help_action(request,rng,decisions=RerollAllFailures())
    rng.assert_exhausted()
    return execution


def automatic_help_boundary(weapon):
    source = make_pc_ranged_scenario(pc_count=2,max_rounds=1)
    party=[]
    for index,member in enumerate(source.party):
        selected = weapon if index==0 else PcMeleeWeapon.PISTOL
        ranged = replace(member.pc.ranged,ballistic_skill=1 if index==0 else 6,shooting=6,
            has_blackpowder_lore=None if selected is PcMeleeWeapon.REPEATER_HANDBOW else True,
            has_blackpowder_kit=None if selected is PcMeleeWeapon.REPEATER_HANDBOW else True,
            repeater_bonus_policy=None if selected is PcMeleeWeapon.PISTOL else PcRepeaterBonusPolicy.AUTOMATIC)
        party.append(replace(member,pc=replace(member.pc,weapon=selected,ranged=ranged,toughness=20),
            policy=PcMeleePolicy.AUTOMATIC_COMBAT,combat_equipment=(PcWeaponItem(
                'owned:'+str(index),selected,PcItemLocation.HELD,member.initial_weapon_hand),)))
    enemy=source.enemies[0]
    resilience=ResilienceProfile(20)
    enemy=replace(enemy,definition=replace(enemy.definition,resilience=resilience,
        protection=(replace(enemy.definition.protection[0],test_profile=InlineProfile(6,6)),)),
        state=replace(enemy.state,current_resilience=resilience))
    state=initial_pc_melee_state(replace(source,party=tuple(party),enemies=(enemy,)))
    clock=start_combat_turn(CombatTurnStartRequest('prepared:start',state.round_state,'pc1')).state
    return replace(state,round_state=clock)


class PcRangedHelpUseTests(unittest.TestCase):
    def test_native_help_journal_projects_actual_use_and_rejects_missing_receipt(self):
        for weapon,bonus in ((PcMeleeWeapon.PISTOL,False),(PcMeleeWeapon.REPEATER_PISTOL,True),
                (PcMeleeWeapon.REPEATER_HANDBOW,True)):
            with self.subTest(weapon=weapon):
                source=automatic_help_boundary(weapon).source
                # Help, PC2's opposed shot, then NPC's opposed Melee; all fail.
                rng=ScriptedD10([10]*(19 if bonus else 18))
                result=run_pc_melee_scenario(source,rng)
                rng.assert_exhausted()
                step,=tuple(step for step in result.steps if type(step.proof) is PcHelpProof)
                receipt=step.proof.ranged_use
                self.assertEqual(receipt.uses_optional_reload_bonus,bonus)
                self.assertEqual(receipt.weapon_state,step.state.participant('pc1').ranged)
                self.assertEqual(receipt.weapon_state.loaded,not bonus)
                self.assertEqual(receipt.execution.bonus.bonus_dice,0)
                self.assertFalse(step.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
                with self.assertRaises((TypeError,ValueError)):
                    PcMeleeStep(step.source,replace(step.proof,ranged_use=None))
                with self.assertRaises(ValueError):
                    apply_pc_melee_step(step.state,step)

    def test_actual_automatic_plan_and_help_builder_bind_concrete_item_and_mode(self):
        for weapon,bonus in ((PcMeleeWeapon.PISTOL,False),(PcMeleeWeapon.REPEATER_PISTOL,True),
                (PcMeleeWeapon.REPEATER_HANDBOW,True)):
            with self.subTest(weapon=weapon):
                state=automatic_help_boundary(weapon)
                choice=select_pc_tactic(state)
                self.assertIs(choice.action,CombatActionKind.HELP)
                self.assertIs(choice.help_policy.skill,Skill.SHOOTING)
                self.assertEqual(choice.ranged_bonus,bonus)
                clock=reserve_combat_action_slot(CombatActionSlotRequest('prepared:reserve',
                    state.round_state,'pc1',CombatActionDeclaration(CombatActionKind.HELP),ActionSlotGrant.STANDARD)).state
                state=replace(state,round_state=clock)
                request=build_pc_help_action(state)
                # BS1 caps the entire bonus pool at two dice.
                execution=execute_help(request,[10]*(2 if bonus else 1))
                proof=complete_pc_ranged_help(state,request,request,execution)
                self.assertEqual(proof.previous_weapon_state.weapon_instance_id,'pc1:weapon:owned:0')
                self.assertEqual(proof.uses_optional_reload_bonus,bonus)
                self.assertEqual(proof.weapon_state.loaded,not bonus)

    def test_automatic_unsupported_guard_only_inspects_selected_shoot_or_reload(self):
        state=automatic_help_boundary(PcMeleeWeapon.PISTOL)
        def choice(action,**kw):
            return PcTacticalChoice('pc1',action,None,None,0.0,'prepared:guard',**kw)
        for selected in (choice(CombatActionKind.RECOVER),choice(CombatActionKind.IMPROVISE),
                choice(CombatActionKind.HELP),choice(CombatActionKind.ATTACK,weapon_item_id='carried:sword')):
            with self.subTest(selected=selected),patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=selected),\
                    patch('towr.domain.pc_ranged_models.usable_hands',side_effect=AssertionError('premature ranged boundary')):
                self.assertIsNone(pc_ranged_unsupported(state))
        for selected in (choice(CombatActionKind.ATTACK),choice(CombatActionKind.IMPROVISE,ranged_reload=True)):
            with self.subTest(selected=selected),patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=selected),\
                    patch('towr.domain.pc_ranged_models.usable_hands',side_effect=RuntimeError('actual ranged boundary')):
                with self.assertRaisesRegex(RuntimeError,'actual ranged boundary'):
                    pc_ranged_unsupported(state)

    def test_ordinary_help_preserves_charge_for_all_three_weapons(self):
        for weapon in (PcMeleeWeapon.PISTOL,PcMeleeWeapon.REPEATER_PISTOL,PcMeleeWeapon.REPEATER_HANDBOW):
            with self.subTest(weapon=weapon):
                state,request = prepared_help(weapon,bonus=False)
                execution = execute_help(request,[1,10,10])
                proof = complete_pc_ranged_help(state,request,request,execution)
                self.assertIs(type(proof),PcRangedHelpUseProof)
                self.assertEqual(proof.weapon_state,state.party[0].ranged)
                self.assertTrue(proof.weapon_state.loaded)
                self.assertFalse(proof.uses_optional_reload_bonus)
                self.assertIsNone(proof.next_reload_cycle_id)
                self.assertEqual(execution.bonus.bonus_dice,1)
                self.assertIs(execution.slot.declaration.kind,CombatActionKind.HELP)
                self.assertFalse(state.party[0].injury.conditions.has(Condition.STAGGERED))

    def test_bonus_help_opens_reload3_even_with_zero_success_and_no_attack(self):
        for weapon,extra in ((PcMeleeWeapon.REPEATER_PISTOL,2),(PcMeleeWeapon.REPEATER_HANDBOW,1)):
            for successful in (False,True):
                with self.subTest(weapon=weapon,successful=successful):
                    state,request = prepared_help(weapon)
                    execution = execute_help(request,([1] if successful else [10])*(3+extra))
                    proof = complete_pc_ranged_help(state,request,request,execution)
                    self.assertEqual(tuple(mod.amount for mod in proof.source_test.dice_modifiers
                        if mod.rule_id==REPEATER_SHOOTING_BONUS_RULE_ID),(extra,))
                    self.assertFalse(proof.weapon_state.loaded)
                    self.assertEqual(proof.weapon_state.required_successes,3)
                    self.assertEqual(proof.weapon_state.exacting.accumulated_successes,0)
                    self.assertEqual(proof.weapon_state.reload_cycle_ids,(proof.next_reload_cycle_id,))
                    self.assertEqual(proof.previous_weapon_state,state.party[0].ranged)
                    self.assertIs(execution.slot.declaration.kind,CombatActionKind.HELP)
                    self.assertEqual(execution.bonus.bonus_dice,3+extra if successful else 0)
                    self.assertFalse(state.party[0].injury.conditions.has(Condition.STAGGERED))

    def test_drained_does_not_activate_optional_bonus(self):
        state,request = prepared_help(PcMeleeWeapon.REPEATER_PISTOL,drained=True)
        execution = execute_help(request,[1,10,10])
        proof = complete_pc_ranged_help(state,request,request,execution)
        self.assertFalse(proof.uses_optional_reload_bonus)
        self.assertEqual(proof.weapon_state,proof.previous_weapon_state)

    def test_receipt_retains_pre_fate_test_and_actual_reroll_execution(self):
        state,request = prepared_help(PcMeleeWeapon.REPEATER_PISTOL)
        # Fate funding is checked by the outer PC owner; this boundary retains
        # both Tests and consumes the already-selected weapon mode exactly once.
        effective = replace(request,help_test=replace(request.help_test,quality_modifiers=(
            QualityModifier('RULE-FATE-001:glorious',TestQuality.GLORIOUS),)))
        execution = execute_help(effective,[10]*5+[1]*5)
        proof = complete_pc_ranged_help(state,request,effective,execution)
        self.assertEqual(proof.source_test,request.help_test)
        self.assertEqual(proof.execution.source_request,effective)
        self.assertEqual(proof.execution.help_test_result.trace.final_values,(1,)*5)
        self.assertEqual(len(proof.weapon_state.reload_cycle_ids),1)

    def test_receipt_rejects_foreign_mode_cycle_actor_and_weapon(self):
        state,request = prepared_help(PcMeleeWeapon.REPEATER_HANDBOW)
        execution = execute_help(request,[10]*4)
        proof = complete_pc_ranged_help(state,request,request,execution)
        for changes in ({'actor_id':'pc2'},{'uses_optional_reload_bonus':False},
                {'weapon_state':proof.previous_weapon_state},{'next_reload_cycle_id':None}):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(proof,**changes)
        altered = deepcopy(request)
        object.__setattr__(altered.help_test,'dice_modifiers',())
        with self.assertRaises(ValueError):
            complete_pc_ranged_help(state,altered,altered,execution)
        changed_state = deepcopy(state)
        object.__setattr__(changed_state.party[0].ranged,'weapon_instance_id','pc1:weapon:foreign')
        with self.assertRaises(ValueError):
            complete_pc_ranged_help(changed_state,request,request,execution)
        with self.assertRaises(ValueError):
            complete_pc_ranged_help(state,request,replace(request,beneficiary_test_id='foreign'),execution)

    def test_empty_weapon_or_wrong_holding_state_cannot_supply_shooting_help(self):
        state,request = prepared_help(PcMeleeWeapon.REPEATER_PISTOL)
        execution = execute_help(request,[10]*5)
        member = state.party[0]
        for changed in (replace(member,ranged=begin_reload_cycle(member.ranged,'already-used')),
                replace(member,weapon_hand=None)):
            with self.assertRaises(ValueError):
                complete_pc_ranged_help(replace(state,party=(changed,state.party[1])),request,request,execution)

    def test_cycle_primitive_refuses_empty_weapon_and_repeated_identifier(self):
        state,_ = prepared_help(PcMeleeWeapon.REPEATER_PISTOL)
        spent = begin_reload_cycle(state.party[0].ranged,'cycle')
        with self.assertRaises(ValueError):
            begin_reload_cycle(spent,'next')
        rng = ScriptedD10([1,1,1])
        contribution = resolve_exacting_test_contribution(ExactingTestContributionRequest(
            'reload-contribution',spent.exacting,'pc1',_pc_test(state,'pc1','reload-test',Skill.DEXTERITY)),rng)
        rng.assert_exhausted()
        loaded = replace(spent,loaded=True,exacting=contribution.progress)
        with self.assertRaises(ValueError):
            begin_reload_cycle(loaded,'cycle')
        second = begin_reload_cycle(loaded,'second-cycle')
        self.assertEqual(second.reload_cycle_ids,('cycle','second-cycle'))
        self.assertEqual(second.exacting.accumulated_successes,0)


if __name__=='__main__':
    unittest.main()
