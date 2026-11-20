"""Real immediate strikes retain Wound, weapon and armour consequence owners."""
from dataclasses import replace
import unittest

from tests.unit.test_bash_attack_execution import pc_source,npc_source
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.armour_fixtures import light_loadout
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.talent_sources import paid_talent
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.pc_immediate_attack_models import PcImmediateStrikeProof
from towr.domain.pc_melee_result_models import PcWoundCompletionProof,initial_pc_melee_state
from towr.domain.pc_armour_bane_models import armour_bane_applications
from towr.domain.talent_catalog import TalentId
from towr.domain.weapon_catalog import WeaponKind as W
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    replay=initial_pc_melee_state(source)
    for step in result.steps:replay=apply_pc_melee_step(replay,step)
    if replay!=result.state:raise AssertionError('complete immediate consequence replay changed')
    return result


class BashAttackConsequenceTests(unittest.TestCase):
    def test_prepared_live_defenceless_target_keeps_the_granted_strike_without_protection_test(self):
        # This is an explicitly prepared consequence boundary on a real native
        # Brawn prefix, not a claim of how this extra Condition was obtained.
        source=npc_source()
        result=execute(source,[1,10,10]+[1]*5+[10]*20+[1,10,1])
        from towr.domain.pc_immediate_attack_models import PcBashDecisionProof
        from towr.domain.pc_bash_attack_models import expected_bash_decision,build_pc_bash_strike
        from towr.domain.pc_melee_result_models import PcMeleeStep
        from towr.domain.pc_weapon_inventory import replace_pc_member
        step=next(step for step in result.steps if type(step.proof) is PcBashDecisionProof)
        before=step.source
        member=before.party[0]
        injury=replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.DEFENCELESS))
        prepared=replace(before,party=(replace_pc_member(member,injury=injury),))
        decision=expected_bash_decision(prepared)
        self.assertIsNotNone(decision.selection)
        state=PcMeleeStep(prepared,decision).state
        request,_=build_pc_bash_strike(state)
        self.assertIsNone(request.kernel_request.attack.defender_test)
        self.assertEqual(request.target_id,'pc')

    def test_npc_free_sword_completes_an_actual_player_wound(self):
        source=npc_source()
        row=replace(source.party[0],pc=replace(source.party[0].pc,toughness=6))
        result=execute(replace(source,party=(row,)),
            [1,10,10]+[1,10,10,10,10]+[10]*6+[1,10,1])
        strike,=tuple(step.proof for step in result.steps if type(step.proof) is PcImmediateStrikeProof)
        wound,=tuple(step.proof for step in result.steps if type(step.proof) is PcWoundCompletionProof)
        self.assertEqual(wound.completion.source_request.roll.source_request.wound.id,
            strike.request.kernel_request.id+':wound')
        self.assertEqual(result.state.party[0].injury.wounds[0].table_total,1)
        self.assertEqual(result.executed_actions,2)
        self.assertEqual(strike.execution.state,strike.execution.previous_state)

    def test_scarab_hit_keeps_its_actual_secondary_condition_source(self):
        source=npc_source()
        row=replace(source.party[0],pc=replace(source.party[0].pc,toughness=6))
        npc=source.enemies[0].definition.generated_components
        npc=replace(npc,weapons=(npc.weapons[0],replace(npc.weapons[1],kind=W.SCARAB_KNIFE)))
        result=execute(replace(source,party=(row,),enemies=(npc.participant('minion1'),)),
            [1,10]+[1,10,10,10,10]+[10]*6+[1,10,1])
        strike,=tuple(step.proof for step in result.steps if type(step.proof) is PcImmediateStrikeProof)
        self.assertTrue(result.state.party[0].injury.conditions.has(Condition.DRAINED))
        self.assertEqual(len(result.state.party[0].hit_condition_sources),2)
        self.assertIsNotNone(strike.magic_weapon)
        from towr.domain.pc_magic_weapon_models import PcScarabChargeProof
        charge,=tuple(step.proof for step in result.steps if type(step.proof) is PcScarabChargeProof)
        self.assertEqual(charge.action_id,strike.request.id)
        self.assertEqual(result.state.party[0].hit_condition_sources[-1].attack_id,
            strike.request.id)

    def test_magic_hammer_keeps_the_actual_receipt_and_physical_inventory(self):
        source=pc_source(carried=True)
        row=source.party[0]
        row=replace(row,combat_equipment=(row.combat_equipment[0],
            replace(row.combat_equipment[1],weapon=W.GROTARGGS_HAMMER)))
        result=execute(replace(source,party=(row,)),[1]*5+[10]*2+[1]*3+[10]*2)
        strike,=tuple(step.proof for step in result.steps if type(step.proof) is PcImmediateStrikeProof)
        self.assertIsNotNone(strike.magic_weapon)
        self.assertEqual(strike.magic_weapon.action_id,strike.request.id)
        self.assertIs(strike.weapon_intent.attack_use.primary.kind,W.GROTARGGS_HAMMER)
        self.assertEqual(result.state.party[0].weapon_inventory,strike.magic_weapon.after_inventory)

    def test_armour_bane_from_the_free_strike_is_atomic_and_retained_for_later_turns(self):
        source=pc_source(carried=True)
        row=source.party[0]
        row=replace(row,talents=(*row.talents,paid_talent(TalentId.ARMOUR_BANE)),
            combat_equipment=(row.combat_equipment[0],replace(row.combat_equipment[1],weapon=W.GREATAXE)))
        npc=GeneratedNpc(2,3,20,2,4,4,initial_generated_weapons(GeneratedWeapon.STAFF),
            light_loadout(light=True,shield=True),defence=4)
        source=replace(source,party=(row,),enemies=(npc.participant('minion1'),))
        result=execute(source,[1]*5+[10]*2+[1]*2+[10]*7)
        strike,=tuple(step.proof for step in result.steps if type(step.proof) is PcImmediateStrikeProof)
        self.assertEqual(strike.armour_bane.reduction,1)
        self.assertEqual(strike.resolution.attack.effective_resilience,strike.armour_bane.before.total)
        self.assertEqual(armour_bane_applications(result.state,'minion1'),(strike.armour_bane,))
        self.assertEqual(result.state.enemy('minion1').state.current_resilience.total,
            strike.armour_bane.after.total)


if __name__=='__main__':unittest.main()
