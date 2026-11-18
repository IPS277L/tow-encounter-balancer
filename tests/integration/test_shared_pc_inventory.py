"""Native PC combat reads physical units instead of primary/backup mirrors."""
from dataclasses import fields, replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.attack_models import ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.pc_combat_equipment_models import PcItemLocation as L, PcWeaponItem
from towr.domain.pc_melee_models import PcMeleeWeapon as W, PcWeaponHand as H
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeParticipantState, PcMeleeState, initial_pc_melee_state,
)
from towr.domain.weapon_inventory_models import WeaponInventoryState
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


def two_sword_source(*, carried=(), strength=3):
    source=automatic_source(pc_count=1,enemy_count=1,rounds=1)
    member=source.party[0]
    member=replace(member,pc=replace(member.pc,weapon=W.SWORD,strength=strength),
        initial_weapon_hand=H.LEFT,
        combat_equipment=(PcWeaponItem('left',W.SWORD,L.HELD,H.LEFT),
            PcWeaponItem('right',W.SWORD,L.HELD,H.RIGHT),
            *(PcWeaponItem('carried:'+str(index),kind,L.CARRIED,None)
                for index,kind in enumerate(carried))))
    enemy=source.enemies[0]
    enemy=replace(enemy,definition=replace(enemy.definition,resilience=ResilienceProfile(100)),
        state=replace(enemy.state,current_resilience=ResilienceProfile(100)))
    return replace(source,party=(member,),enemies=(enemy,))


class SharedPcInventoryNativeTests(unittest.TestCase):
    def test_two_actual_swords_supply_one_defence_test_with_two_dice_and_full_replay(self):
        source=two_sword_source()
        rng=ScriptedD10([1,10,10,10,10,1,10,1,1,10,10,10])
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        incoming=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.target_id=='pc1')
        request=incoming.proof.request.kernel_request.attack.defender_test
        self.assertEqual(tuple(modifier.amount for modifier in request.dice_modifiers),(2,))
        self.assertEqual(incoming.proof.execution.resolution.attack.defender_test.trace.rolled_dice,5)
        inventory=result.state.participant('pc1').weapon_inventory
        self.assertIs(type(inventory),WeaponInventoryState)
        self.assertEqual(tuple(item.location for item in inventory.items),(L.HELD,L.HELD))
        replay=initial_pc_melee_state(source)
        for step in result.steps:
            replay=apply_pc_melee_step(replay,step)
        self.assertEqual(replay,result.state)

    def test_carried_sword_never_supplies_a_defence_trait(self):
        source=two_sword_source()
        member=source.party[0]
        equipment=(member.combat_equipment[0],replace(member.combat_equipment[1],location=L.CARRIED,hand=None))
        source=replace(source,party=(replace(member,combat_equipment=equipment),))
        rng=ScriptedD10([1,10,10,10,10,1,10,1,1,10,10])
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        incoming=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.target_id=='pc1')
        request=incoming.proof.request.kernel_request.attack.defender_test
        self.assertEqual(tuple(mod.amount for mod in request.dice_modifiers),(1,))
        self.assertEqual(incoming.proof.execution.resolution.attack.defender_test.trace.rolled_dice,4)

    def test_runtime_has_one_inventory_and_no_mutable_actor_resource_mirrors(self):
        member_fields={item.name for item in fields(PcMeleeParticipantState)}
        self.assertFalse(member_fields & {'weapon_hand','ranged','using_backup_weapon'})
        self.assertNotIn('npc_ranged_weapons',{item.name for item in fields(PcMeleeState)})

    def test_carried_source_before_primary_does_not_claim_a_backup_draw(self):
        source=two_sword_source(carried=(W.DAGGER,))
        member=source.party[0]
        left,right,back=member.combat_equipment
        source=replace(source,party=(replace(member,combat_equipment=(back,left,right)),))
        member=initial_pc_melee_state(source).participant('pc1')
        self.assertEqual(member.weapon_inventory.active.source_item_id,'left')
        self.assertFalse(member.using_backup_weapon)
        self.assertIs(member.weapon_inventory.items[0].location,L.CARRIED)

    def test_legal_overloaded_source_starts_burdened_without_discarding_items(self):
        source=two_sword_source(carried=(W.STAFF,W.DAGGER),strength=3)
        state=initial_pc_melee_state(source)
        self.assertEqual(len(state.participant('pc1').weapon_inventory.items),4)
        self.assertTrue(state.participant('pc1').injury.conditions.has(Condition.BURDENED))


if __name__=='__main__':
    unittest.main()
