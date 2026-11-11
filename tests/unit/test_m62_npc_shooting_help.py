"""Actual no-Test Shooting Help, Reload fallbacks and exact intended Test receipts."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.npc_shooting_help_scenarios import make_npc_shooting_help_scenario as scene
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_shield_scenarios import shield_loadout
from towr.domain.attack_models import AttackOutcome
from towr.domain.automatic_help_models import AutomaticHelpBonusApplicationRequest
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcGloriousPolicy, PcHelpPolicy, PcHelpTarget,
    PcMeleePolicy, PcNearMissPolicy, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcMeleeStep, PcNpcHelpProof, build_pc_melee_attack,
)
from towr.domain.pc_net_models import PcNpcNetDrawProof, net_stock_and_held
from towr.domain.pc_npc_catalog import PcBookNpcProfile as Npc, create_pc_book_npc
from towr.domain.pc_npc_help_models import pc_npc_help_beneficiary
from towr.domain.pc_npc_pistol_models import PcNpcPistolReloadProof, pc_npc_pistol_weapon
from towr.domain.test_models import Skill, TestQuality
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


HELPERS=(Npc.FREE_COMPANY_MILITIA_BLADES,Npc.GOBLIN_WARRIOR_SPEAR,
    Npc.NIGHT_GOBLIN_SPEAR,Npc.NIGHT_GOBLIN_NET_SPEAR)
PC_MISS=[10]*3+[1]*3


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def steps(result,kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def shots(result):
    return tuple(step for step in steps(result,PcAttackProof) if step.proof.npc_pistol_shot is not None)


def two_pcs(source):
    member=source.party[0]
    second=replace(member,actor_id='pc2',pc=replace(member.pc,id='second-profile'),
        fate=replace(member.fate,actor_id='pc2'),
        defeat_decisions=tuple(replace(item,attacker_id='pc2') for item in member.defeat_decisions))
    return replace(source,party=(member,second),pc_activation_order=('pc','pc2'),
        enemy_target_priority=('pc','pc2'))


class NpcShootingHelpTests(unittest.TestCase):
    def test_four_helpers_both_firearms_bind_real_shooting_and_spend_one_action(self):
        for helper in HELPERS:
            for shooter,base in ((Npc.EMPIRE_OFFICIAL_PISTOL,2),(Npc.IMPERIAL_OGRE_PISTOL,3)):
                with self.subTest(helper=helper,shooter=shooter):
                    result=execute(scene(helpers=(helper,),shooter=shooter,max_rounds=1),
                        PC_MISS+[10]*(base+1)+[1]*3)
                    help,=steps(result,PcNpcHelpProof)
                    shot,=shots(result)
                    self.assertIs(help.proof.request.beneficiary_skill,Skill.SHOOTING)
                    app,=shot.proof.npc_help_applications
                    self.assertIs(app.source_request.beneficiary_skill,Skill.SHOOTING)
                    self.assertEqual(app.source_request.help,help.proof.execution)
                    self.assertEqual(help.proof.request.beneficiary_test_id,
                        shot.proof.execution.resolution.attack.attacker_test.trace.request_id)
                    trace=shot.proof.execution.resolution.attack.attacker_test.trace
                    self.assertEqual((trace.base_dice,trace.cap_bypassing_dice,trace.rolled_dice),
                        (base,1,base+1))
                    self.assertEqual(shot.proof.help_applications,())
                    self.assertFalse(pc_npc_pistol_weapon(result.state,'minion2').loaded)
                    self.assertEqual(result.executed_actions,3)
                    self.assertFalse(hasattr(help.proof.execution,'help_test_result'))

    def test_multiple_distinct_receipts_exceed_cap_and_do_not_spend_net(self):
        result=execute(scene(helpers=HELPERS,max_rounds=1),PC_MISS+[10]*7+[1]*3)
        shot,=shots(result)
        trace=shot.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice,trace.pool_cap,trace.cap_bypassing_dice,trace.rolled_dice),(3,6,4,7))
        helps=steps(result,PcNpcHelpProof)
        apps=shot.proof.npc_help_applications
        self.assertEqual(tuple(app.source_request.help for app in apps),tuple(step.proof.execution for step in helps))
        self.assertEqual(len({app.request_id for app in apps}),4)
        self.assertEqual(net_stock_and_held(result.state,'minion4')[0],1)
        self.assertEqual(steps(result,PcNpcNetDrawProof),())
        self.assertEqual(result.executed_actions,6)

    def test_empty_partial_reload_uses_attack_fallback_then_help_returns_next_round(self):
        source=scene(max_rounds=4)
        values=(PC_MISS+[10]*4+[1]*3
            +PC_MISS+[10]*3+[1]*3+[1,1]
            +PC_MISS+[10]*3+[1]*3+[1,10]
            +PC_MISS+[10]*4+[1]*3)
        result=execute(source,values)
        helps=steps(result,PcNpcHelpProof)
        self.assertEqual(tuple(step.source.round_state.round_number for step in helps),(1,4))
        fallback=tuple(step for step in steps(result,PcAttackProof) if step.proof.request.actor_id=='minion1')
        self.assertEqual(tuple(step.source.round_state.round_number for step in fallback),(2,3))
        reloads=steps(result,PcNpcPistolReloadProof)
        self.assertEqual(tuple(step.proof.result.exacting.test_result.successes for step in reloads),(2,1))
        self.assertEqual(tuple(step.proof.result.state.loaded for step in reloads),(False,True))
        self.assertTrue(all(step.proof.request.dexterity_test.dice_modifiers==() for step in reloads))
        self.assertEqual(tuple(len(step.proof.npc_help_applications) for step in shots(result)),(1,1))
        self.assertEqual(result.executed_actions,12)

    def test_net_helper_preserves_stock_on_help_and_throws_only_during_reload_fallback(self):
        source=scene(helpers=(Npc.NIGHT_GOBLIN_NET_SPEAR,),max_rounds=2)
        result=execute(source,PC_MISS+[10]*4+[1]*3+PC_MISS+[10]*2+[1]*3+[1,1])
        help,=steps(result,PcNpcHelpProof)
        self.assertEqual(net_stock_and_held(help.state,'minion1')[0],1)
        self.assertEqual(net_stock_and_held(result.state,'minion1')[0],0)
        net,=tuple(step for step in steps(result,PcAttackProof) if step.proof.request.actor_id=='minion1')
        self.assertIs(net.proof.protection.source_request.attack_skill,Skill.THROWING)
        self.assertEqual(net.proof.npc_help_applications,())
        self.assertTrue(all(step.source.round_state.round_number==2 for step in steps(result,PcNpcNetDrawProof)))
        self.assertEqual(len(steps(result,PcNpcPistolReloadProof)),1)

    def test_shooting_help_retains_actual_pc_glorious_shield_and_near_miss_prefix(self):
        source=scene(shooter=Npc.EMPIRE_OFFICIAL_PISTOL,max_rounds=1)
        member=source.party[0]
        for shield,skill in ((None,Skill.ATHLETICS),(shield_loadout(PcWeaponHand.RIGHT),Skill.DEFENCE)):
            with self.subTest(skill=skill):
                configured=replace(source,party=(replace(member,shield=shield,fate_policy=PcFatePolicy.CONFIGURED,
                    glorious_policy=PcGloriousPolicy((skill,),0,0)),))
                result=execute(configured,PC_MISS+[10,10,1]+[10]*3+[1]*3)
                shot,=shots(result)
                self.assertEqual(len(shot.proof.npc_help_applications),1)
                self.assertIs(shot.proof.protection.source_request.selected_skill,skill)
                self.assertIs(shot.proof.execution.resolution.attack.defender_test.trace.quality,TestQuality.GLORIOUS)
                self.assertEqual(len(result.state.participant('pc').fate.spends),1)
                self.assertIs(shot.proof.execution.resolution.attack.outcome,AttackOutcome.MISS)
        near=replace(source,party=(replace(member,fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(8,0)),))
        result=execute(near,PC_MISS+[1]*3+[10]*3+[8])
        self.assertEqual(result.state.participant('pc').injury.wounds,())
        self.assertEqual(result.state.participant('pc').fate.rating,2)
        self.assertFalse(pc_npc_pistol_weapon(result.state,'minion2').loaded)

    def test_pc_protection_help_does_not_move_from_first_npc_to_a_later_shooter(self):
        source=two_pcs(scene(shooter=Npc.EMPIRE_OFFICIAL_PISTOL,max_rounds=1))
        first,second=source.party
        first=replace(first,policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2',PcHelpTarget.FIRST_INCOMING_PROTECTION,Skill.DEFENCE))
        second=replace(second,shield=shield_loadout(PcWeaponHand.RIGHT))
        source=replace(source,party=(first,second),enemy_target_priority=('pc2','pc'))
        result=execute(source,[1,10,10]+PC_MISS+[10]*3+[1]*3)
        shot,=shots(result)
        self.assertEqual(len(shot.proof.npc_help_applications),1)
        self.assertEqual(shot.proof.help_applications,())
        attack=shot.proof.execution.resolution.attack
        self.assertEqual((attack.attacker_test.trace.rolled_dice,attack.defender_test.trace.rolled_dice),(3,3))
        from towr.domain.pc_melee_result_models import PcHelpProof
        help,=steps(result,PcHelpProof)
        self.assertTrue(help.proof.execution.bonus.beneficiary_test_id.endswith(':minion1:protection'))
        self.assertNotEqual(help.proof.execution.bonus.beneficiary_test_id,attack.defender_test.trace.request_id)
        self.assertEqual(result.executed_actions,4)

    def test_drained_and_unavailable_eligibility_without_claiming_a_public_injury_source(self):
        result=execute(scene(max_rounds=1),PC_MISS+[10]*4+[1]*3)
        help,=steps(result,PcNpcHelpProof)
        # Focused preparation boundaries use changed Conditions explicitly;
        # these snapshots are not advertised as complete fresh-scene journals.
        def conditioned(state,actor,condition):
            return replace(state,enemies=tuple(replace(enemy,state=replace(enemy.state,
                injury=replace(enemy.state.injury,conditions=enemy.state.injury.conditions.with_condition(condition))))
                if enemy.state.actor_id==actor else enemy for enemy in state.enemies))
        self.assertEqual(pc_npc_help_beneficiary(conditioned(help.source,'minion1',Condition.DRAINED)),'minion2')
        for actor,conditions in (('minion1',(Condition.DEAFENED,Condition.DEFENCELESS,Condition.BROKEN)),
                ('minion2',(Condition.DRAINED,Condition.DEFENCELESS,Condition.BROKEN))):
            for condition in conditions:
                with self.subTest(actor=actor,condition=condition):
                    self.assertIsNone(pc_npc_help_beneficiary(conditioned(help.source,actor,condition)))
        shot,=shots(result)
        altered=conditioned(shot.source,'minion2',Condition.DRAINED)
        request,_=build_pc_melee_attack(altered)
        self.assertFalse(any(modifier.amount>0 for modifier in request.kernel_request.attack.attacker_test.dice_modifiers))
        self.assertEqual(sum(type(proof) is PcNpcHelpProof for proof in altered.history),1)

    def test_help_remains_spent_when_party_dies_before_the_loaded_shooters_turn(self):
        source=scene(helpers=(Npc.FREE_COMPANY_MILITIA_BLADES,)*2,
            shooter=Npc.EMPIRE_OFFICIAL_PISTOL,max_rounds=3)
        source=replace(source,enemies=(source.enemies[0],create_pc_book_npc(Npc.FOOTPAD,'minion2'),
            source.enemies[2]),npc_help_policies=(source.npc_help_policies[0],))
        values=(PC_MISS+[1]*3+[10]*3+[1]+[1]*3+[10]*3+[1,1]
            +PC_MISS+[10]*3+[1]*3+[10]*3+[1]*3+[1]*3
            +PC_MISS+[1]*3+[10]*3+[10]*3)
        result=execute(source,values)
        self.assertEqual(len(steps(result,PcNpcHelpProof)),2)
        self.assertEqual(len(shots(result)),1)
        self.assertEqual(result.executed_actions,11)
        self.assertTrue(pc_npc_pistol_weapon(result.state,'minion3').loaded)
        self.assertTrue(result.state.participant('pc').injury.dead)
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)

    def test_exact_skill_test_actor_and_receipts_cannot_be_forged_or_replayed(self):
        result=execute(scene(max_rounds=1),PC_MISS+[10]*4+[1]*3)
        help,=steps(result,PcNpcHelpProof)
        shot,=shots(result)
        app,=shot.proof.npc_help_applications
        self.assertEqual(apply_pc_melee_step(help.source,help),help.state)
        with self.assertRaises((TypeError,ValueError)):
            apply_pc_melee_step(help.state,help)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(shot.source,replace(shot.proof,npc_help_applications=()))
        with self.assertRaises((TypeError,ValueError)):
            replace(result,steps=tuple(step for step in result.steps if step is not help))
        for skill in (Skill.MELEE,Skill.DEXTERITY):
            with self.subTest(skill=skill),self.assertRaises(ValueError):
                AutomaticHelpBonusApplicationRequest('foreign',app.source_request.help,
                    'minion2',skill,app.source_request.test)
        for actor,test in (('minion2',replace(app.source_request.test,id='later-round:attack')),
                ('foreign',app.source_request.test)):
            with self.assertRaises(ValueError):
                AutomaticHelpBonusApplicationRequest('foreign',app.source_request.help,actor,Skill.SHOOTING,test)
        forged=deepcopy(help.proof)
        object.__setattr__(forged.request,'beneficiary_skill',Skill.MELEE)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(help.source,forged)


if __name__=='__main__':
    unittest.main()
