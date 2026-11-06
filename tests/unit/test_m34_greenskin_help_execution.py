"""Real Horde/Power actions, mixed receipts and Drained tactics in PC melee."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m12_pc_heavy_wounds import heavy_prefix
from towr.domain.automatic_help_models import AutomaticHelpEffectKind,expected_automatic_help_action
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_result_models import PcAttackProof,PcNpcHelpProof,PcMeleeStep,PcMeleeOutcome
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy,HORDE_HELP_RULE_ID,WAAAGH_HELP_RULE_ID
from towr.domain.pc_npc_catalog import PcBookNpcProfile,create_pc_book_npc
from towr.domain.test_models import DiceModifier,SuccessModifier
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def scene(*,helpers,recipient,order=None,rounds=1,**counts):
    source=book_pc_scenario(footpads=0,townsfolk=0,pc_count=1,max_rounds=rounds,**counts)
    priority=(recipient,)+tuple(e.state.actor_id for e in source.enemies if e.state.actor_id!=recipient)
    member=source.party[0]
    return replace(source,enemy_activation_order=order or (*helpers,recipient),
        party=(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)),),
        npc_help_policies=tuple(PcNpcHelpPolicy(actor,recipient) for actor in helpers))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def incoming(result,actor):
    return next(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id==actor)


class GreenskinHelpExecutionTests(unittest.TestCase):
    def test_mixed_horde_and_waaagh_keep_distinct_modifiers_and_normal_dice_pool(self):
        source=scene(goblins=1,night_goblins=1,orcs=1,big_uns=1,
            helpers=('goblin1','night_goblin1','orc1'),recipient='big_un1')
        result=execute(source,[10]*3+[1]*3+[10]*6+[1]*3)
        helps=tuple(s.proof for s in result.steps if type(s.proof) is PcNpcHelpProof)
        self.assertEqual(tuple(p.execution.bonus.rule_id for p in helps),
            (HORDE_HELP_RULE_ID,HORDE_HELP_RULE_ID,WAAAGH_HELP_RULE_ID))
        self.assertEqual(tuple(p.request.effect_kind for p in helps),
            (AutomaticHelpEffectKind.BONUS_DIE_BEYOND_CAP,)*2+(AutomaticHelpEffectKind.FREE_SUCCESS,))
        attack=incoming(result,'big_un1').proof
        self.assertEqual(tuple(type(a.modifier) for a in attack.npc_help_applications),
            (DiceModifier,DiceModifier,SuccessModifier))
        test=attack.request.kernel_request.attack.attacker_test
        self.assertEqual(test.success_modifiers,(SuccessModifier(WAAAGH_HELP_RULE_ID,1),))
        trace=attack.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice,trace.cap_bypassing_dice,trace.rolled_dice),(3,2,6))
        self.assertEqual(attack.execution.resolution.attack.attacker_test.successes,1)
        self.assertEqual(result.executed_actions,5)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertFalse(any(hasattr(p.execution,'help_test_result') for p in helps))

    def test_two_free_successes_stack_and_attacker_tie_hits_without_rolled_success(self):
        source=scene(orcs=2,watch=1,helpers=('orc1','orc2'),recipient='watch1')
        result=execute(source,[10]*3+[1]*3+[10]*4+[1,1,10]+[1])
        attack=incoming(result,'watch1').proof
        self.assertEqual(attack.execution.resolution.attack.attacker_test.successes,2)
        self.assertEqual(attack.execution.resolution.attack.defender_test.successes,2)
        self.assertEqual(attack.request.kernel_request.attack.attacker_test.success_modifiers,
            (SuccessModifier(WAAAGH_HELP_RULE_ID,1),)*2)
        self.assertEqual(attack.execution.resolution.attack.attacker_test.trace.cap_bypassing_dice,0)
        self.assertEqual(len(result.state.party[0].injury.wounds),1)

    def test_horde_bypasses_only_its_dice_after_ordinary_bonuses_reach_cap(self):
        source=scene(goblins=2,night_goblins=1,orcs=1,watch=1,
            helpers=('goblin1','night_goblin1','orc1'),recipient='goblin2',
            order=('watch1','goblin1','night_goblin1','orc1','goblin2'))
        # Watch Wound9 puts the PC Prone, adding higher-ground to outnumbering.
        result=execute(source,[10]*3+[1]*3+[1]*4+[10]*3+[9]+[10]*6+[1]*3)
        attack=incoming(result,'goblin2')
        self.assertTrue(attack.source.party[0].injury.conditions.has(Condition.PRONE))
        trace=attack.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.regular_dice_delta,trace.pool_cap,trace.cap_bypassing_dice,trace.rolled_dice),
            (2,4,2,6))
        self.assertEqual(trace.success_delta,1)

    def test_orc_helps_drained_recipient_while_goblin_attacks(self):
        source=scene(goblins=1,orcs=1,big_uns=1,helpers=('goblin1','orc1'),recipient='big_un1')
        # The actual PC attack wounds Big 'Un before either helper activates.
        result=execute(source,[1]*3+[10]*3+[10]*3+[1]*3+[10]*3+[1]*3)
        helps=tuple(s for s in result.steps if type(s.proof) is PcNpcHelpProof)
        self.assertEqual(tuple(s.proof.request.actor_id for s in helps),('orc1',))
        self.assertTrue(helps[0].source.enemy('big_un1').state.injury.conditions.has(Condition.DRAINED))
        self.assertIsInstance(incoming(result,'goblin1').proof,PcAttackProof)
        attack=incoming(result,'big_un1').proof
        self.assertEqual(attack.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(attack.request.kernel_request.attack.attacker_test.success_modifiers,
            (SuccessModifier(WAAAGH_HELP_RULE_ID,1),))
        trace=attack.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.rolled_dice,trace.cap_bypassing_dice),(3,0))
        self.assertEqual(attack.execution.resolution.attack.attacker_test.successes,1)
        self.assertEqual(result.state.enemy('big_un1').state.injury.wounds,1)

    def test_wounded_drained_big_un_still_helps_without_own_test(self):
        source=scene(big_uns=1,watch=1,helpers=('big_un1',),recipient='watch1')
        member=source.party[0]
        priority=('big_un1','watch1')
        source=replace(source,party=(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)),))
        result=execute(source,[1]*3+[10]*3+[10]*4+[1]*3)
        help_step=next(s for s in result.steps if type(s.proof) is PcNpcHelpProof)
        self.assertTrue(help_step.proof.request.actor_conditions.has(Condition.DRAINED))
        self.assertEqual(help_step.state.enemy('big_un1').state.injury.wounds,1)
        self.assertEqual(help_step.proof.execution.bonus.bonus_successes,1)
        self.assertEqual(incoming(result,'watch1').proof.execution.resolution.attack.attacker_test.successes,1)

    def test_orc_can_help_non_orc_and_skulker_cannot_supply_horde(self):
        source=scene(orcs=1,watch=1,helpers=('orc1',),recipient='watch1')
        self.assertEqual(source.npc_help_policies,(PcNpcHelpPolicy('orc1','watch1'),))
        source=book_pc_scenario(skulkers=1,goblins=1,footpads=0,townsfolk=0)
        with self.assertRaises(ValueError):
            replace(source,enemy_activation_order=('skulker1','goblin1'),
                npc_help_policies=(PcNpcHelpPolicy('skulker1','goblin1'),))

    def test_free_successes_against_actual_defenceless_pc_cause_only_one_wound(self):
        source=make_pc_melee_scenario(enemy_count=6,max_rounds=1)
        source=replace(source,enemies=(*source.enemies[:3],
            create_pc_book_npc(PcBookNpcProfile.ORC_BOY_CHOPPAS,'minion4'),
            create_pc_book_npc(PcBookNpcProfile.ORC_BOY_CHOPPAS,'minion5'),
            create_pc_book_npc(PcBookNpcProfile.NASTY_SKULKER,'minion6')),
            npc_help_policies=(PcNpcHelpPolicy('minion4','minion6'),PcNpcHelpPolicy('minion5','minion6')))
        result=execute(source,heavy_prefix(22)+[10]*5+[10]*4)
        step=incoming(result,'minion6')
        self.assertTrue(step.source.party[0].injury.conditions.has(Condition.DEFENCELESS))
        attack=step.proof.execution.resolution.attack
        self.assertIsNone(attack.defender_test)
        self.assertEqual((attack.attacker_test.trace.rolled_successes,attack.attacker_test.successes),(0,2))
        self.assertEqual((attack.impact_spec.damage.success_multiplier,attack.damage),(2,7))
        self.assertEqual(len(result.state.party[0].injury.wounds),len(step.source.party[0].injury.wounds)+1)
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)

    def test_kind_source_and_success_applications_cannot_be_forged_or_replayed(self):
        source=scene(orcs=1,watch=1,helpers=('orc1',),recipient='watch1')
        result=execute(source,[10]*3+[1]*3+[10]*4+[1]*3)
        help_step=next(s for s in result.steps if type(s.proof) is PcNpcHelpProof)
        # Generic die Help is valid, but not canonical for this actual Orc.
        forged_request=replace(help_step.proof.request,effect_kind=AutomaticHelpEffectKind.BONUS_DIE_BEYOND_CAP)
        with self.assertRaises(ValueError):
            PcMeleeStep(help_step.source,PcNpcHelpProof(forged_request,expected_automatic_help_action(forged_request)))
        attack=incoming(result,'watch1')
        apps=attack.proof.npc_help_applications
        for forged_apps in ((),apps+apps):
            with self.subTest(applications=forged_apps),self.assertRaises(ValueError):
                PcMeleeStep(attack.source,replace(attack.proof,npc_help_applications=forged_apps))
        forged=deepcopy(result)
        proof=next(s.proof for s in forged.steps if type(s.proof) is PcNpcHelpProof)
        object.__setattr__(proof.execution.bonus,'effect_kind',AutomaticHelpEffectKind.BONUS_DIE_BEYOND_CAP)
        with self.assertRaises(ValueError):
            replace(forged)
        forged_attack=deepcopy(attack.proof)
        trace=forged_attack.execution.resolution.attack.attacker_test.trace
        object.__setattr__(trace,'success_delta',0)
        object.__setattr__(trace,'successes',0)
        with self.assertRaises(ValueError):
            PcMeleeStep(attack.source,forged_attack)


if __name__=='__main__':
    unittest.main()
