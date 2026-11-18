"""Actual multi-gun choices, per-item K1 resources and native journal replay."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
from towr.domain.pc_melee_models import PcMeleePolicy,PcMeleeWeapon,PcWeaponHand,PcRepeaterBonusPolicy
from towr.domain.pc_melee_result_models import PcAttackProof,initial_pc_melee_state
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.weapon_inventory_models import weapon_unit_id
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario


def scene(*,second=PcMeleeWeapon.PISTOL,rounds=2,second_carried=False,loaded=(True,True)):
    source=make_pc_pistol_scenario(max_rounds=rounds,ballistic_skill=4,shooting=5,
        initiative=3,dexterity=5)
    member=source.party[0]
    profile=member.pc.ranged
    if second in (PcMeleeWeapon.REPEATER_PISTOL,PcMeleeWeapon.REPEATER_HANDBOW):
        profile=replace(profile,repeater_bonus_policy=PcRepeaterBonusPolicy.AUTOMATIC)
    member=replace(member,pc=replace(member.pc,toughness=20,strength=4,ranged=profile),
        policy=PcMeleePolicy.AUTOMATIC_COMBAT,combat_equipment=(
            PcWeaponItem('left-gun',PcMeleeWeapon.PISTOL,PcItemLocation.HELD,PcWeaponHand.LEFT,
                initially_loaded=loaded[0]),
            PcWeaponItem('right-gun',second,PcItemLocation.CARRIED if second_carried else PcItemLocation.HELD,
                None if second_carried else PcWeaponHand.RIGHT,initially_loaded=loaded[1])))
    source=replace(source,party=(member,))
    return source


class ConstantTen:
    def randint(self,low,high):
        if (low,high)!=(1,10):raise AssertionError('unexpected die range')
        return 10


class SharedPcRangedInventoryTests(unittest.TestCase):
    def assert_replays(self,result):
        state=initial_pc_melee_state(result.source)
        for step in result.steps:
            state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)

    def test_two_loaded_pistols_fire_as_distinct_units_before_any_reload(self):
        for carried in (False,True):
            with self.subTest(second_carried=carried):
                source=scene(second_carried=carried)
                result=run_pc_melee_scenario(source,ConstantTen())
                self.assertIsNone(result.unsupported)
                shots=[(index,step) for index,step in enumerate(result.steps)
                    if type(step.proof) is PcAttackProof and step.proof.request.actor_id=='pc1']
                self.assertEqual(len(shots),2)
                first,second=shots
                a=first[1].proof.ranged_shot.execution.weapon_state
                b=second[1].proof.ranged_shot.execution.weapon_state
                self.assertNotEqual(a.weapon_instance_id,b.weapon_instance_id)
                self.assertEqual({a.weapon_instance_id,b.weapon_instance_id},
                    {weapon_unit_id('pc1','left-gun',0),weapon_unit_id('pc1','right-gun',0)})
                self.assertFalse(any(type(step.proof) is PcRangedReloadProof for step in result.steps[first[0]:second[0]+1]))
                self.assertTrue(all(not item.reload.loaded for item in result.state.participant('pc1').weapon_inventory.items))
                self.assertTrue(all(item.initially_loaded for item in source.party[0].combat_equipment))
                if carried:
                    self.assertTrue(any(type(step.proof) is PcWeaponSwapProof and step.proof.changes_equipment
                        for step in result.steps[first[0]+1:second[0]]))
                self.assert_replays(result)

    def test_actual_reload_frees_second_hand_and_charges_only_its_selected_unit(self):
        source=scene(rounds=1,loaded=(False,False))
        rng=ScriptedD10([1,1,1]+[10]*5)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        reload, = (step for step in result.steps if type(step.proof) is PcRangedReloadProof)
        weapon=reload.proof.result.state
        inventory=reload.state.participant('pc1').weapon_inventory
        self.assertTrue(inventory.item(weapon.weapon_instance_id).reload.loaded)
        other, = (item for item in inventory.items if item.id!=weapon.weapon_instance_id)
        self.assertFalse(other.reload.loaded)
        self.assertEqual(other.reload.exacting.contributions,())
        self.assertIs(other.location,PcItemLocation.CARRIED)
        self.assertEqual(reload.proof.result.state,inventory.item(weapon.weapon_instance_id).reload)
        self.assertEqual(len(weapon.exacting.contributions),1)
        swaps=[step.proof for step in result.steps if type(step.proof) is PcWeaponSwapProof]
        self.assertEqual(len(swaps),1)
        self.assertTrue(swaps[0].changes_equipment)
        self.assertTrue(swaps[0].intent.ranged_reload)
        self.assertTrue(all(item.location is PcItemLocation.HELD for item in swaps[0].previous.items))
        with self.assertRaises(ValueError):
            apply_pc_melee_step(reload.state,reload)
        # The actual journal/result owner, rather than a scalar loaded flag,
        # rejects receipt removal when its final state is readmitted.
        forged_step=deepcopy(reload)
        erased=tuple(proof for proof in forged_step.state.history if type(proof) is not PcRangedReloadProof)
        self.assertEqual(len(erased),len(forged_step.state.history)-1)
        object.__setattr__(forged_step.state,'history',erased)
        with self.assertRaises(ValueError):
            replace(result,steps=tuple(forged_step if step is reload else step for step in result.steps))
        self.assert_replays(result)

    def test_mixed_pistol_and_handbow_keep_kinds_and_distinct_reload_cycles(self):
        source=scene(second=PcMeleeWeapon.REPEATER_HANDBOW)
        result=run_pc_melee_scenario(source,ConstantTen())
        self.assertIsNone(result.unsupported)
        shots=[step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc1']
        self.assertEqual(len(shots),2)
        weapons=[step.proof.ranged_shot.execution.weapon_state for step in shots]
        self.assertEqual({weapon.weapon_id for weapon in weapons},
            {RangedWeaponId.PISTOL,RangedWeaponId.REPEATER_HANDBOW})
        self.assertNotEqual(weapons[0].weapon_instance_id,weapons[1].weapon_instance_id)
        self.assertTrue(all(not weapon.loaded for weapon in weapons))
        self.assertTrue(all(len(weapon.reload_cycle_ids)==1 for weapon in weapons))
        self.assertFalse(any(type(step.proof) is PcRangedReloadProof for step in result.steps))
        self.assert_replays(result)

    def test_secondary_empty_pistol_cannot_restore_shield_before_reload(self):
        from tests.support.pc_shield_scenarios import shield_loadout
        from towr.domain.pc_shield_models import PcShieldState,PcShieldLocation,pc_shield_recover_hand
        from towr.domain.pc_weapon_inventory import replace_pc_member
        source=scene(second_carried=True,rounds=2)
        source=replace(source,party=(replace(source.party[0],shield=shield_loadout(PcWeaponHand.RIGHT)),))
        result=run_pc_melee_scenario(source,ConstantTen())
        self.assertIsNone(result.unsupported)
        member=result.state.participant('pc1')
        self.assertTrue(member.using_backup_weapon)
        self.assertEqual(member.weapon_inventory.active.source_item_id,'right-gun')
        self.assertFalse(member.ranged.loaded)
        # Focused physical preparation from a genuinely fired secondary unit;
        # no claim that this view paid for dropping or recovering the Shield.
        dropped=replace_pc_member(member,shield=PcShieldState(PcShieldLocation.DROPPED,None))
        self.assertIsNone(pc_shield_recover_hand(dropped))
        self.assert_replays(result)


if __name__=='__main__':unittest.main()
