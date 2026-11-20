"""Automatic Charge/Run use one actual slot and the shared Attack owner."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from dataclasses import replace
import unittest

from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_battlefield_manoeuvre_models import PcBattlefieldChargeProof,PcBattlefieldRunProof
from towr.domain.pc_battlefield_movement_models import PcBattlefieldMoveProof
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
from towr.domain.pc_melee_models import PcMeleeWeapon,PcRangedProfile,PcTwoHandedGrip
from towr.domain.pc_melee_result_models import PcAttackProof,PcMeleeStep,initial_pc_melee_state
from towr.domain.ranged_weapon_profiles import RangedWeaponRange,RangedWeaponHands
from towr.domain.turn_models import CombatActionKind,ManoeuvreKind
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


class Misses:
    def randint(self,low,high):
        if (low,high)!=(1,10):
            raise AssertionError('literal native battle uses d10 only')
        return 10


def scene(distance=RangedWeaponRange.MEDIUM):
    source=automatic_source(pc_count=1,rounds=1)
    npc=GeneratedNpc(3,3,4,3,4,4,initial_generated_weapons(GeneratedWeapon.STAFF),light_loadout(light=False, shield=False),defence=4)
    return replace(source,enemies=(npc.participant('minion1'),),
        facts=replace(source.facts,all_opponents_close=False,can_leave_zone=True),
        battlefield=PcBattlefieldSpec(distance,RangedWeaponRange.LONG))


class NativeBattlefieldManoeuvreTests(unittest.TestCase):
    def execute(self,source):
        result=run_pc_melee_scenario(source,Misses())
        self.assertIsNone(result.unsupported)
        current=initial_pc_melee_state(source)
        for step in result.steps:
            current=apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        return result

    def test_medium_charge_precedes_one_attack_with_one_bonus_and_no_free_move(self):
        result=self.execute(scene())
        charge,=[step for step in result.steps if type(step.proof) is PcBattlefieldChargeProof]
        attack=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1')
        self.assertTrue(charge.proof.result.attack_allowed)
        self.assertFalse(charge.proof.result.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(attack.proof.request.charge_movement,charge.proof.result)
        self.assertEqual(attack.proof.request.target_id,charge.proof.request.target_id)
        self.assertEqual(sum(mod.amount for mod in attack.proof.request.kernel_request.attack.attacker_test.dice_modifiers
            if mod.rule_id=='RULE-COMBAT-009:charge-melee-bonus'),1)
        self.assertEqual(attack.proof.execution.slot.declaration.kind,CombatActionKind.MANOEUVRE)
        self.assertEqual(attack.proof.execution.slot.declaration.manoeuvre,ManoeuvreKind.CHARGE)
        self.assertFalse(any(type(step.proof) is PcBattlefieldMoveProof for step in result.steps))
        self.assertEqual(result.executed_actions,2)
        with self.assertRaises(ValueError):
            PcMeleeStep(attack.state,charge.proof)

    def test_failed_long_charge_executes_one_action_and_never_attack(self):
        result=self.execute(scene(RangedWeaponRange.EXTREME))
        charge=next(step for step in result.steps if type(step.proof) is PcBattlefieldChargeProof
            and step.proof.actor_id=='pc1')
        self.assertFalse(charge.proof.result.attack_allowed)
        self.assertTrue(charge.proof.result.round_state.active_turn.action_slots[0].executed)
        self.assertTrue(charge.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(any(type(step.proof) is PcAttackProof and step.proof.request.actor_id=='pc1'
            for step in result.steps))
        self.assertEqual(result.executed_actions,2)
        self.assertEqual(len([step for step in result.steps if type(step.proof) is PcBattlefieldMoveProof]),1)

    def test_ranged_actor_runs_toward_explicit_maximum_and_does_not_shoot_same_action(self):
        source=scene(RangedWeaponRange.EXTREME)
        member=source.party[0]
        ranged=PcRangedProfile(3, 4, ammunition_supply_confirmed=True)
        member=replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.WARBOW,ranged=ranged, initiative=3, awareness=4),
            initial_weapon_hand=PcTwoHandedGrip.BOTH,
            combat_equipment=(PcWeaponItem('bow:held',PcMeleeWeapon.WARBOW,
                PcItemLocation.HELD,PcTwoHandedGrip.BOTH),))
        source=replace(source,party=(member,),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.EXTREME,RangedWeaponRange.SHORT))
        result=self.execute(source)
        run,=[step for step in result.steps if type(step.proof) is PcBattlefieldRunProof]
        self.assertEqual(run.proof.actor_id,'pc1')
        self.assertIsNotNone(run.proof.extension_request)
        self.assertFalse(run.proof.extension_result.athletics_test_result.succeeded)
        self.assertTrue(run.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(any(type(step.proof) is PcAttackProof and step.proof.request.actor_id=='pc1'
            for step in result.steps))
        self.assertEqual(result.executed_actions,2)

    def test_generated_foot_spear_defence_receives_actual_charge_context(self):
        source=scene()
        npc=GeneratedNpc(3,3,4,2,4,3,initial_generated_weapons(GeneratedWeapon.FOOT_SPEAR, grip=RangedWeaponHands.TWO_HANDED),light_loadout(light=False, shield=False),
            defence=5)
        result=self.execute(replace(source,enemies=(npc.participant('minion1'),)))
        attack=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1')
        defender=attack.request.kernel_request.attack.defender_test
        self.assertEqual(sum(mod.amount for mod in defender.dice_modifiers
            if mod.rule_id=='RULE-EQUIPMENT-003:foot-spear-charge-defence'),1)


if __name__=='__main__':
    unittest.main()
