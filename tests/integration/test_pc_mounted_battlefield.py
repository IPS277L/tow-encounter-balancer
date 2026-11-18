"""Horse components affect actual shared attacks and forced dismounts once."""
from dataclasses import replace
import unittest

from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon,GeneratedAbility
from towr.domain.condition_models import Condition
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_melee_models import PcMeleeWeapon,PcTwoHandedGrip
from towr.domain.pc_melee_result_models import PcAttackProof,PcMeleeStep,initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount,PcDismountProof,pc_is_mounted,HORSE_NOBLE_STEED_RULE_ID
from towr.domain.pc_shield_models import pc_shield_resilience
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario


class Ones:
    def randint(self,low,high):
        if (low,high)!=(1,10):
            raise AssertionError('literal mounted battle uses d10 only')
        return 1


def scene(*,distance=RangedWeaponRange.MEDIUM,rounds=1,billhook=False,pc_spear=False):
    source=automatic_source(pc_count=1,rounds=rounds)
    pc=source.party[0]
    if billhook or pc_spear:
        pc=replace(pc,pc=replace(pc.pc,
            weapon=PcMeleeWeapon.BILLHOOK if billhook else PcMeleeWeapon.FOOT_SPEAR,
            weapon_skill=2 if pc_spear else pc.pc.weapon_skill),initial_weapon_hand=PcTwoHandedGrip.BOTH)
    pc=replace(pc,mount=CombatMount.HORSE)
    npc=GeneratedNpc(3,3,20,2,4,3,GeneratedWeapon.STAFF,False,
        defence=4,shield=False,mount=CombatMount.HORSE)
    return replace(source,party=(pc,),enemies=(npc.participant('minion1'),),
        facts=replace(source.facts,all_opponents_close=False,can_leave_zone=True,unmounted=False),
        battlefield=PcBattlefieldSpec(distance,RangedWeaponRange.LONG))


class MountedBattlefieldTests(unittest.TestCase):
    def execute(self,source):
        result=run_pc_melee_scenario(source,Ones())
        self.assertIsNone(result.unsupported)
        current=initial_pc_melee_state(source)
        for step in result.steps:
            current=apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        return result

    def test_mounted_charge_knocks_npc_prone_and_removes_one_horse_bonus(self):
        result=self.execute(scene())
        dismount,=[step for step in result.steps if type(step.proof) is PcDismountProof]
        self.assertEqual(dismount.proof.actor_id,'minion1')
        self.assertTrue(dismount.proof.source_injury.conditions.has(Condition.PRONE))
        self.assertEqual(dismount.source.enemy('minion1').state.current_resilience.total,21)
        self.assertEqual(dismount.state.enemy('minion1').state.current_resilience.total,20)
        self.assertFalse(dismount.state.enemy('minion1').state.current_resilience.is_armoured)
        self.assertFalse(pc_is_mounted(result.state,'minion1'))
        self.assertTrue(pc_is_mounted(result.state,'pc1'))
        self.assertEqual(result.executed_actions,2)
        self.assertEqual(tuple(actor.actor_id for actor in result.state.mounts),('pc1','minion1'))
        self.assertFalse(result.state.enemy('minion1').state.injury.conditions.has(Condition.PRONE))
        with self.assertRaises(ValueError):
            PcMeleeStep(dismount.state,dismount.proof)

    def test_billhook_bonus_uses_actual_mount_and_stops_after_dismount(self):
        result=self.execute(scene(billhook=True,rounds=2))
        attacks=[step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1']
        self.assertEqual(len(attacks),2)
        before,after=attacks
        modifier='RULE-EQUIPMENT-003:billhook-mounted-target'
        self.assertEqual(sum(item.amount for item in before.request.kernel_request.attack.attacker_test.dice_modifiers
            if item.rule_id==modifier),1)
        self.assertFalse(any(item.rule_id==modifier for item in after.request.kernel_request.attack.attacker_test.dice_modifiers))
        self.assertEqual(len([step for step in result.steps if type(step.proof) is PcDismountProof]),1)

    def test_npc_mounted_charge_uses_pc_spear_defence_and_dismounts_pc(self):
        result=self.execute(scene(distance=RangedWeaponRange.SHORT,pc_spear=True))
        attack=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='minion1')
        defender=attack.proof.request.kernel_request.attack.defender_test
        self.assertEqual(sum(item.amount for item in defender.dice_modifiers
            if item.rule_id=='RULE-EQUIPMENT-003:foot-spear-charge-defence'),1)
        dismount,=[step for step in result.steps if type(step.proof) is PcDismountProof]
        self.assertEqual(dismount.proof.actor_id,'pc1')
        self.assertEqual(pc_shield_resilience(dismount.source,'pc1').total,4)
        self.assertEqual(pc_shield_resilience(dismount.state,'pc1').total,3)
        self.assertFalse(pc_is_mounted(result.state,'pc1'))

    def test_mounted_charge_prone_and_drained_preserve_application_order_and_source(self):
        source=scene(distance=RangedWeaponRange.SHORT,pc_spear=True)
        npc=replace(source.enemies[0].definition.generated_components,
            abilities=(GeneratedAbility.DRAINED_ON_HIT,))
        source=replace(source,enemies=(npc.participant('minion1'),))
        result=self.execute(source)
        attack=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='minion1')
        resolution=attack.proof.execution.resolution
        application,=resolution.condition_applications
        self.assertEqual(resolution.applied_secondary_rule_ids,
            (HORSE_NOBLE_STEED_RULE_ID,application.source_rule_id))
        self.assertEqual(application.request_id,
            attack.proof.request.kernel_request.id+':'+application.source_rule_id+':on-hit-condition')
        self.assertTrue(application.state.has(Condition.PRONE))
        self.assertTrue(application.state.has(Condition.DRAINED))
        self.assertTrue(attack.state.participant('pc1').injury.conditions.has(Condition.DRAINED))
        self.assertFalse(pc_is_mounted(result.state,'pc1'))
        self.assertEqual(len(result.state.participant('pc1').hit_condition_sources),1)


if __name__=='__main__':
    unittest.main()
