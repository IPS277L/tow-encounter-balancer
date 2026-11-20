"""Actual rolled NPC Help and source-bound application to the upcoming Attack."""
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.talent_sources import paid_talent,free_talent
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.armour_models import ArmourLoadout,BodyArmour
from towr.domain.condition_models import Condition
from towr.domain.talent_models import TalentOwnerFacts
from towr.domain.talent_catalog import TalentId
from towr.domain.pc_melee_result_models import PcHelpProof,PcAttackProof,PcMeleeStep,initial_pc_melee_state
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.domain.test_models import Skill,TestQuality


def npc_source(*,rounds=1):
    source=make_pc_melee_scenario(enemy_count=2,max_rounds=rounds)
    member=replace(source.party[0],pc=replace(source.party[0].pc,
        weapon_skill=6,melee=6,strength=1,toughness=20,defence=6))
    def npc(ws,melee,allies=False):
        return GeneratedNpc(ws,1,20,1,melee,2,initial_generated_weapons(GeneratedWeapon.STAFF),
            ArmourLoadout(),defence=2,talents=(paid_talent(TalentId.ALLIES_IN_ARMS),) if allies else (),
            talent_facts=TalentOwnerFacts(fellowship=4) if allies else None)
    return replace(source,party=(member,),enemies=(npc(1,2,True).participant('minion1'),
        npc(4,6).participant('minion2')),enemy_activation_order=('minion1','minion2'),
        facts=replace(source.facts,outnumbering_bonus_approved=False))


class NpcAlliesInArmsExecutionTests(unittest.TestCase):
    def execute(self,values):
        source=npc_source()
        rng=ScriptedD10(values)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        state=initial_pc_melee_state(source)
        for step in result.steps:state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)
        return result

    def test_zero_success_ordinary_help_removes_own_actual_staggered(self):
        result=self.execute([1]*6+[10]*12)
        helped,=tuple(step for step in result.steps if type(step.proof) is PcHelpProof)
        self.assertEqual(helped.proof.request.actor_id,'minion1')
        self.assertEqual(helped.proof.execution.help_test_result.successes,0)
        self.assertTrue(helped.source.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(helped.state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(helped.proof.allies_in_arms.target_id,'minion1')
        self.assertIsNone(helped.proof.fate_decline)
        self.assertIsNone(helped.proof.glorious)
        self.assertEqual(result.executed_actions,3)
        for bad in (replace(helped.proof,allies_in_arms=None),
                replace(helped.proof,allies_in_arms=replace(helped.proof.allies_in_arms,
                    talent=free_talent(TalentId.ALLIES_IN_ARMS)))):
            with self.assertRaises((TypeError,ValueError)):PcMeleeStep(helped.source,bad)

    def test_real_success_is_applied_only_to_the_named_upcoming_attack(self):
        result=self.execute([1]*6+[10]+[1]+[10]*11)
        helped,=tuple(step for step in result.steps if type(step.proof) is PcHelpProof)
        self.assertEqual(helped.proof.execution.help_test_result.successes,1)
        attack,=tuple(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='minion2')
        self.assertEqual(len(attack.help_applications),1)
        self.assertEqual(attack.help_applications[0].source_request.help,helped.proof.execution)
        self.assertEqual(attack.request.kernel_request.attack.attacker_test.id,
            helped.proof.execution.bonus.beneficiary_test_id)

    def test_protection_help_is_bound_to_the_exact_next_round_incoming_test(self):
        source=npc_source(rounds=2)
        defender=replace(source.enemies[1].definition.generated_components,melee=2,defence=6)
        source=replace(source,enemies=(source.enemies[0],defender.participant('minion2')))
        rng=ScriptedD10([1]*6+[10]*8+[1]*4+[10]*6+[1]*2+[10]*11)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        protection,=tuple(step.proof for step in result.steps if type(step.proof) is PcHelpProof
            and step.proof.request.actor_id=='minion2')
        self.assertTrue(protection.request.beneficiary_test_id.endswith(':r2:pc:protection'))
        protected_step,=tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc' and step.proof.request.state.round_number==2)
        protected=protected_step.proof
        self.assertEqual(len(protected.help_applications),1)
        self.assertEqual(protected.help_applications[0].source_request.help,protection.execution)
        self.assertEqual(len(protected.execution.resolution.attack.defender_test.trace.final_values),2)
        # Prepared death boundary, retaining the genuine pending next-round
        # Help journal; no complete history of that death is claimed.
        from towr.domain.pc_npc_weapon_inventory import _NpcInventoryView
        from towr.domain.pc_single_combat_models import single_combat_active
        before=protected_step.source
        helper=before.enemy('minion2')
        removed=replace(helper,state=replace(helper.state,injury=replace(helper.state.injury,wounds=1,defeated=True)))
        view=_NpcInventoryView(before,(before.enemy('minion1'),removed))
        self.assertFalse(single_combat_active(view,'pc','minion1'))

    def test_prepared_npc_help_keeps_penalties_and_sight_conditions_without_bonus_dice(self):
        from towr.domain.pc_npc_weapon_inventory import _NpcInventoryView
        from towr.domain.pc_npc_normal_help_models import npc_help_test,npc_normal_help_choice
        source=npc_source()
        npc=replace(source.enemies[0].definition.generated_components,endurance=4,
            armour=ArmourLoadout((BodyArmour.FULL_PLATE,),BodyArmour.FULL_PLATE))
        source=replace(source,enemies=(npc.participant('minion1'),source.enemies[1]))
        initial=initial_pc_melee_state(source)
        enemy=initial.enemy('minion1')
        conditions=enemy.state.injury.conditions.with_condition(Condition.DRAINED).with_condition(Condition.BLINDED)
        changed=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,conditions=conditions)))
        view=_NpcInventoryView(initial,(changed,initial.enemy('minion2')))
        test=npc_help_test(view,'minion1','prepared:help:athletics',Skill.ATHLETICS)
        self.assertTrue(any(mod.amount<0 for mod in test.dice_modifiers))
        self.assertFalse(any(mod.amount>0 for mod in test.dice_modifiers))
        self.assertTrue(any(mod.quality is TestQuality.GRIM for mod in test.quality_modifiers))
        endurance=npc_help_test(view,'minion1','prepared:help:endurance',Skill.ENDURANCE)
        self.assertFalse(any(mod.quality is TestQuality.GRIM for mod in endurance.quality_modifiers))
        deafened=replace(changed,state=replace(changed.state,injury=replace(changed.state.injury,
            conditions=conditions.with_condition(Condition.DEAFENED))))
        self.assertIsNone(npc_normal_help_choice(_NpcInventoryView(initial,(deafened,initial.enemy('minion2'))),'minion1'))

    def test_completed_help_consumes_only_the_next_test_penalty_in_its_actual_trace(self):
        from tests.unit.test_talent_allies_in_arms_sources import execution
        from towr.domain.pc_magic_models import PcMagicModifier,PcMagicTaskKind,consume_magic_modifiers
        from towr.domain.test_models import DiceModifier,TestRequest,TestProfile
        modifier=PcMagicModifier('spell:next-test','helper',PcMagicTaskKind.NEXT_TEST_PENALTY)
        other=replace(modifier,source_id='spell:unused')
        completed=execution(values=(10,10),test=TestRequest('help:test',TestProfile(3,5),
            (DiceModifier(modifier.source_id,-1),)))
        proof=PcHelpProof(completed.source_request,completed,None,weapon_use=None)
        self.assertEqual(consume_magic_modifiers((modifier,other),proof),(other,))


if __name__=='__main__':unittest.main()
