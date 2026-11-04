"""Literal Brigand outnumbering receipts and explicitly authored preparation boundaries."""
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_result_models import PcAttackProof,PcMeleeStep,build_pc_melee_attack
from towr.domain.pc_npc_ability_models import CRAVEN_OPPORTUNIST_RULE_ID,pc_npc_outnumbering_modifier
from towr.domain.pc_npc_catalog import PcBookNpcProfile,get_pc_book_npc_entry
from towr.domain.test_models import DiceModifier
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def scene(*,brigands=2,footpads=0,pc_count=1,rounds=1,approved=True):
    source=book_pc_scenario(brigands=brigands,footpads=footpads,townsfolk=0,pc_count=pc_count,max_rounds=rounds)
    return replace(source,facts=replace(source.facts,outnumbering_bonus_approved=approved))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def attacks(result,actor):
    return tuple(s for s in result.steps if isinstance(s.proof,PcAttackProof) and s.proof.request.actor_id==actor)


class CravenOpportunistTests(unittest.TestCase):
    def test_native_replacement_rolls_five_dice_without_stacking_ordinary_bonus(self):
        result=execute(scene(),[10]*3+[1]*3+([10]*5+[1]*3)*2)
        for actor in ('brigand1','brigand2'):
            step,=attacks(result,actor)
            test=step.proof.request.kernel_request.attack.attacker_test
            self.assertEqual(test.dice_modifiers,(DiceModifier(CRAVEN_OPPORTUNIST_RULE_ID,2),))
            self.assertEqual(step.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,5)

    def test_native_mixed_allies_count_but_ability_belongs_only_to_brigand(self):
        result=execute(scene(brigands=1,footpads=1),[10]*3+[1]*3+[10]*5+[1]*3+[10]*4+[1]*3)
        brigand,=attacks(result,'brigand1')
        footpad,=attacks(result,'footpad1')
        self.assertEqual(brigand.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(CRAVEN_OPPORTUNIST_RULE_ID,2),))
        self.assertEqual(footpad.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier('RULE-COMBAT-007:outnumbering',1),))

    def test_native_gm_withholding_removes_the_entire_modifier(self):
        result=execute(scene(approved=False),[10]*3+[1]*3+([10]*3+[1]*3)*2)
        for actor in ('brigand1','brigand2'):
            step,=attacks(result,actor)
            self.assertEqual(step.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
            self.assertEqual(step.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,3)

    def test_native_equal_counts_and_pc_superiority_keep_their_ordinary_rules(self):
        equal=execute(scene(brigands=1),[10]*3+[1]*3+[10]*3+[1]*3)
        self.assertEqual(attacks(equal,'brigand1')[0].proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        pc_superiority=execute(scene(brigands=1,pc_count=2),([10]*4+[1]*3)*2+[10]*3+[1]*3)
        for actor in ('pc1','pc2'):
            self.assertEqual(attacks(pc_superiority,actor)[0].proof.request.kernel_request.attack.attacker_test.dice_modifiers,
                (DiceModifier('RULE-COMBAT-007:outnumbering',1),))
        self.assertEqual(attacks(pc_superiority,'brigand1')[0].proof.request.kernel_request.attack.attacker_test.dice_modifiers,())

    def test_native_superiority_recomputed_after_an_ally_is_defeated(self):
        source=scene(brigands=1,footpads=1,rounds=2)
        member=source.party[0]
        priority=('footpad1','brigand1')
        source=replace(source,party=(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)),))
        values=[10]*3+[1]*3+[10]*5+[1]*3+[10]*4+[1]*3
        values += [1]*3+[10]*3+[10]*3+[1]*3
        result=execute(source,values)
        first,second=attacks(result,'brigand1')
        self.assertEqual(tuple(s.proof.execution.resolution.attack.attacker_test.trace.rolled_dice
            for s in (first,second)),(5,3))
        self.assertTrue(second.source.enemy('footpad1').state.injury.defeated)
        self.assertEqual(second.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())

    def test_native_npc_axe_does_not_gain_pc_armour_damage_trait(self):
        source=scene()
        member=source.party[0]
        source=replace(source,party=(replace(member,pc=replace(member.pc,armour_bonus=1)),))
        result=execute(source,[1,10,10]+[1,10,10]+[1,10,10,10,10]+[10]*3+[10]*5+[1]*3)
        attack=attacks(result,'brigand1')[0].proof.execution.resolution.attack
        self.assertEqual((attack.impact_spec.damage.base,attack.damage,attack.effective_resilience),(3,4,4))
        self.assertEqual(attack.impact_spec.damage_modifiers,())

    def test_pure_drained_boundary_removes_positive_replacement_and_higher_ground(self):
        result=execute(scene(),[10]*3+[1]*3+([10]*5+[1]*3)*2)
        state=attacks(result,'brigand1')[0].source
        enemy=state.enemy('brigand1')
        enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.with_condition(Condition.DRAINED))))
        member=state.party[0]
        member=replace(member,injury=replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.PRONE)))
        boundary=replace(state,party=(member,),enemies=(enemy,*state.enemies[1:]))
        request,_=build_pc_melee_attack(boundary)
        self.assertEqual(request.kernel_request.attack.attacker_test.dice_modifiers,())

    def test_pure_defenceless_count_boundary_excludes_only_ineligible_fighters(self):
        # Authored preparation snapshot, not an alleged reachable fresh encounter prefix.
        source=scene(brigands=2,pc_count=2)
        from towr.domain.pc_melee_result_models import initial_pc_melee_state
        from towr.domain.turn_models import CombatTurnStartRequest
        from towr.rules.turn_resolution import start_combat_turn
        state=initial_pc_melee_state(source)
        first=replace(state.party[0],injury=replace(state.party[0].injury,
            conditions=state.party[0].injury.conditions.with_condition(Condition.DEFENCELESS)))
        clock=replace(state.round_state,completed_turn_entity_ids=source.pc_activation_order)
        clock=start_combat_turn(CombatTurnStartRequest('pure:brigand',clock,'brigand1')).state
        boundary=replace(state,party=(first,state.party[1]),round_state=clock)
        request,_=build_pc_melee_attack(boundary)
        self.assertEqual(request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(CRAVEN_OPPORTUNIST_RULE_ID,2),))
        second=boundary.enemy('brigand2')
        second=replace(second,state=replace(second.state,injury=replace(second.state.injury,
            conditions=second.state.injury.conditions.with_condition(Condition.DEFENCELESS))))
        request,_=build_pc_melee_attack(replace(boundary,enemies=(boundary.enemies[0],second)))
        self.assertEqual(request.kernel_request.attack.attacker_test.dice_modifiers,())

    def test_canonical_request_rejects_reduced_stacked_or_forged_ability_bonus(self):
        result=execute(scene(),[10]*3+[1]*3+([10]*5+[1]*3)*2)
        step=attacks(result,'brigand1')[0]
        request=step.proof.request
        for modifiers in ((DiceModifier(CRAVEN_OPPORTUNIST_RULE_ID,1),),
                (DiceModifier(CRAVEN_OPPORTUNIST_RULE_ID,2),DiceModifier('RULE-COMBAT-007:outnumbering',1)),
                (DiceModifier('authored:fake',2),)):
            attack=replace(request.kernel_request.attack,attacker_test=replace(
                request.kernel_request.attack.attacker_test,dice_modifiers=modifiers))
            forged=replace(request,kernel_request=replace(request.kernel_request,attack=attack))
            with self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(step.source,replace(step.proof,request=forged))

    def test_helper_does_not_give_the_ability_to_custom_authored_copies(self):
        definition=get_pc_book_npc_entry(PcBookNpcProfile.BRIGAND_AXE).definition
        custom=replace(definition,id='authored:brigand',source_rule_id='authored:brigand',
            attacks=(replace(definition.attacks[0],source_rule_id='authored:axe'),),
            protection=(replace(definition.protection[0],source_rule_id='authored:protection'),))
        self.assertEqual(pc_npc_outnumbering_modifier(custom),DiceModifier('RULE-COMBAT-007:outnumbering',1))


if __name__=='__main__':
    unittest.main()
