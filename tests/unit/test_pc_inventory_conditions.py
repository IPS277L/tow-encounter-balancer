"""Independent Carrying in explicit, read-only preparation snapshots.

The snapshots retain real authored sources and typed runtime facts. They do
not fabricate execution receipts or claim admission as a complete battle journal.
"""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import dataclass,replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.armour_models import ArmourLoadout,BodyArmour,body_resilience_bonus
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import (
    CharacterInjuryState,WoundConditionEffect,WoundEffectDuration,WoundEntryId,WoundRecord,
)
from towr.domain.pc_armour_models import initial_pc_armour_injury,pc_after_armour_enhancement
from towr.domain.pc_briarroot_models import PcBriarrootBinding
from towr.domain.pc_combat_equipment_models import PcItemLocation,PcWeaponItem
from towr.domain.pc_inventory_conditions import (
    external_inventory_conditions,initial_pc_inventory_injury,reconcile_pc_inventory_burden,
)
from towr.domain.pc_magic_miscast_plan import PcMagicTaskKind
from towr.domain.pc_magic_models import PcMagicModifier
from towr.domain.pc_melee_models import PcMeleePolicy,PcMeleeWeapon as W,PcWeaponHand
from towr.domain.pc_melee_result_models import PcMeleeParticipantState
from towr.domain.pc_net_models import PcNetConditionSource
from towr.domain.pc_npc_net_policy_models import NET_RULE_ID
from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import (
    TWO_HANDED_COUNT_BURDEN_RULE_ID,WEAPON_COUNT_BURDEN_RULE_ID,
    WeaponGrip,WeaponItemLocation,WeaponItemSource,carrying_burden_rule_ids,initial_weapon_inventory,
)


@dataclass(frozen=True)
class CarryingView:
    source: object
    party: tuple
    enemies: tuple
    magic_modifiers: tuple=()
    briarroot_bindings: tuple=()

    def participant(self,actor):
        return next(member for member in self.party if member.actor_id==actor)

    def enemy(self,actor):
        return next(enemy for enemy in self.enemies if enemy.state.actor_id==actor)


def carrying_view(*,strength=1,carried=(W.DAGGER,),armour=None):
    scene=make_pc_melee_scenario()
    original=scene.party[0]
    equipment=(PcWeaponItem('primary',W.STAFF,PcItemLocation.HELD,PcWeaponHand.LEFT),
        *(PcWeaponItem('carried:'+str(index),weapon,PcItemLocation.CARRIED,None)
            for index,weapon in enumerate(carried)))
    source=replace(original,pc=replace(original.pc,strength=strength,
        armour_bonus=0 if armour is None else body_resilience_bonus(armour)),
        policy=PcMeleePolicy.AUTOMATIC_COMBAT,combat_equipment=equipment,
        armour=armour,armour_worn=None if armour is None else bool(armour.body))
    scene=replace(scene,party=(source,))
    inventory=initial_pc_weapon_inventory(source)
    injury=initial_pc_inventory_injury(source,inventory,initial_pc_armour_injury(source))
    member=PcMeleeParticipantState('pc',injury,inventory,source.fate,DailyWoundState('day','pc'))
    return CarryingView(scene,(member,),scene.enemies)


def drop_carried(member,index=1):
    item=member.weapon_inventory.items[index]
    inventory=member.weapon_inventory.with_item(replace(item,location=WeaponItemLocation.DROPPED,grip=None))
    return replace(member,weapon_inventory=inventory)


class PcInventoryConditionTests(unittest.TestCase):
    def test_initial_carrying_is_present_for_count_or_two_printed_two_handed_weapons(self):
        count=carrying_view()
        self.assertTrue(count.party[0].injury.conditions.has(Condition.BURDENED))
        self.assertEqual(external_inventory_conditions(count,'pc'),frozenset((Condition.BURDENED,)))
        two_handed=carrying_view(strength=10,carried=(W.GLAIVE,W.GREATSWORD))
        self.assertEqual(carrying_burden_rule_ids(two_handed.party[0].weapon_inventory,10),
            (TWO_HANDED_COUNT_BURDEN_RULE_ID,))
        self.assertTrue(two_handed.party[0].injury.conditions.has(Condition.BURDENED))
        both=carrying_view(strength=1,carried=(W.GLAIVE,W.GREATSWORD))
        self.assertEqual(carrying_burden_rule_ids(both.party[0].weapon_inventory,1),
            (WEAPON_COUNT_BURDEN_RULE_ID,TWO_HANDED_COUNT_BURDEN_RULE_ID))

    def test_initial_helper_adds_only_carrying_and_preserves_other_injury_sources(self):
        view=carrying_view()
        source=view.source.party[0]
        injury=CharacterInjuryState(conditions=ConditionState(frozenset((Condition.PRONE,Condition.DRAINED))))
        result=initial_pc_inventory_injury(source,view.party[0].weapon_inventory,injury)
        self.assertEqual(result.conditions,ConditionState(frozenset((Condition.PRONE,Condition.DRAINED,Condition.BURDENED))))
        self.assertEqual(result.wounds,injury.wounds)
        light=carrying_view(strength=3)
        burden=replace(injury,conditions=injury.conditions.with_condition(Condition.BURDENED))
        self.assertIs(initial_pc_inventory_injury(light.source.party[0],light.party[0].weapon_inventory,burden),burden)
        self.assertFalse(injury.conditions.has(Condition.BURDENED))

    def test_drop_removes_only_last_carrying_cause_and_never_changes_source_inventory(self):
        view=carrying_view()
        before=view.party[0]
        after=reconcile_pc_inventory_burden(view,drop_carried(before))
        self.assertFalse(after.injury.conditions.has(Condition.BURDENED))
        self.assertTrue(before.injury.conditions.has(Condition.BURDENED))
        self.assertIs(before.weapon_inventory.items[1].location,WeaponItemLocation.CARRIED)
        self.assertIs(after.weapon_inventory.items[1].location,WeaponItemLocation.DROPPED)
        two=carrying_view(strength=1,carried=(W.GLAIVE,W.GREATSWORD))
        # Losing one printed 2H item still leaves two carried weapons for S1.
        self.assertTrue(reconcile_pc_inventory_burden(two,drop_carried(two.party[0])).injury.conditions.has(Condition.BURDENED))

    def test_strength_enhancement_uses_proposed_member_before_deciding_to_remove_carrying(self):
        view=carrying_view()
        before=view.party[0]
        proposal=replace(before,enhancements=('strength',))
        after=reconcile_pc_inventory_burden(view,proposal)
        self.assertFalse(after.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(after.enhancements,('strength',))
        self.assertEqual(view.party[0].enhancements,())
        self.assertEqual(view.source.party[0].pc.strength,1)
        self.assertTrue(external_inventory_conditions(view,'pc'))
        improved=replace(view,party=(after,))
        self.assertFalse(external_inventory_conditions(improved,'pc'))

    def test_strength_enhancement_does_not_remove_the_two_printed_two_handed_cause(self):
        view=carrying_view(strength=3,carried=(W.GLAIVE,W.GREATSWORD))
        after=reconcile_pc_inventory_burden(view,replace(view.party[0],enhancements=('strength',)))
        self.assertTrue(after.injury.conditions.has(Condition.BURDENED))

    def test_net_condition_survives_removal_of_the_last_carrying_cause(self):
        view=carrying_view()
        member=view.party[0]
        net=PcNetConditionSource('net:attack','minion1','pc','net:application',NET_RULE_ID)
        member=replace(member,net_condition_sources=(net,))
        view=replace(view,party=(member,))
        after=reconcile_pc_inventory_burden(view,drop_carried(member))
        self.assertTrue(after.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(after.net_condition_sources,(net,))

    def test_ongoing_wound_burden_survives_removal_of_the_last_carrying_cause(self):
        view=carrying_view()
        member=view.party[0]
        wound=WoundRecord(1,WoundEntryId.SHATTERED_KNEE,17,(10,7),treated=True,effect_resolved=True)
        effect=WoundConditionEffect(1,Condition.BURDENED,WoundEffectDuration.UNTIL_HEALED)
        member=replace(member,injury=replace(member.injury,wounds=(wound,),active_wound_effects=(effect,)))
        view=replace(view,party=(member,))
        after=reconcile_pc_inventory_burden(view,drop_carried(member))
        self.assertTrue(after.injury.conditions.has(Condition.BURDENED))
        self.assertIs(after.injury.active_wound_effects,member.injury.active_wound_effects)
        self.assertEqual(after.injury.wounds,(wound,))

    def test_independent_heavy_armour_cause_uses_proposed_enhancement_strength(self):
        armour=ArmourLoadout((BodyArmour.HEAVY,),BodyArmour.HEAVY)
        view=carrying_view(strength=1,armour=armour)
        member=view.party[0]
        after=reconcile_pc_inventory_burden(view,drop_carried(member))
        self.assertTrue(after.injury.conditions.has(Condition.BURDENED))
        # S1→2 resolves Carrying of two weapons but not Heavy Armour's S3.
        after=reconcile_pc_inventory_burden(view,replace(member,enhancements=('strength',)))
        self.assertTrue(after.injury.conditions.has(Condition.BURDENED))

    def test_armour_enhancement_owner_keeps_actual_carrying_after_armour_ceases_to_burden(self):
        armour=ArmourLoadout((BodyArmour.HEAVY,),BodyArmour.HEAVY)
        view=carrying_view(strength=2,carried=(W.DAGGER,W.SWORD,W.AXE),armour=armour)
        proposal=replace(view.party[0],enhancements=('strength',))
        actual=pc_after_armour_enhancement(view,'pc',proposal)
        self.assertTrue(actual.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(carrying_burden_rule_ids(actual.weapon_inventory,3),(WEAPON_COUNT_BURDEN_RULE_ID,))
        self.assertEqual(actual.enhancements,('strength',))

    def test_armour_enhancement_owner_does_not_keep_carrying_from_the_old_strength(self):
        armour=ArmourLoadout((BodyArmour.HEAVY,),BodyArmour.HEAVY)
        view=carrying_view(strength=2,carried=(W.DAGGER,W.SWORD),armour=armour)
        proposal=replace(view.party[0],enhancements=('strength',))
        actual=pc_after_armour_enhancement(view,'pc',proposal)
        self.assertFalse(actual.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(view.source.party[0].pc.strength,2)

    def test_briarroot_and_magic_sources_remain_independent_without_new_receipts(self):
        view=carrying_view()
        member=view.party[0]
        binding=PcBriarrootBinding('vines','minion1','pc',member.weapon_inventory.active.id,
            'actual:attack',0)
        modifier=PcMagicModifier('magic:prone','pc',PcMagicTaskKind.PRONE)
        member=replace(member,injury=replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.PRONE)))
        view=replace(view,party=(member,),briarroot_bindings=(binding,),magic_modifiers=(modifier,))
        after=reconcile_pc_inventory_burden(view,drop_carried(member))
        self.assertTrue(after.injury.conditions.has(Condition.BURDENED))
        self.assertTrue(after.injury.conditions.has(Condition.PRONE))
        self.assertEqual(view.briarroot_bindings,(binding,))
        self.assertEqual(view.magic_modifiers,(modifier,))
        without_vines=replace(view,briarroot_bindings=())
        after=reconcile_pc_inventory_burden(without_vines,drop_carried(member))
        self.assertFalse(after.injury.conditions.has(Condition.BURDENED))
        self.assertTrue(after.injury.conditions.has(Condition.PRONE))

    def test_carrying_can_be_added_after_pickup_but_absent_previous_carrying_removes_nothing(self):
        view=carrying_view(strength=2)
        original=view.party[0]
        dropped=drop_carried(original)
        view=replace(view,party=(dropped,))
        self.assertIs(reconcile_pc_inventory_burden(view,dropped),dropped)
        unknown=replace(dropped,injury=replace(dropped.injury,
            conditions=dropped.injury.conditions.with_condition(Condition.BURDENED)))
        self.assertIs(reconcile_pc_inventory_burden(view,unknown),unknown)
        weak=carrying_view(strength=1)
        weak_dropped=drop_carried(weak.party[0])
        weak_dropped=replace(weak_dropped,injury=CharacterInjuryState())
        weak=replace(weak,party=(weak_dropped,))
        item=weak_dropped.weapon_inventory.items[1]
        picked=replace(weak_dropped,weapon_inventory=weak_dropped.weapon_inventory.with_item(
            replace(item,location=WeaponItemLocation.CARRIED)))
        self.assertTrue(reconcile_pc_inventory_burden(weak,picked).injury.conditions.has(Condition.BURDENED))

    def test_generated_npc_uses_actual_units_and_strength_without_inventing_ithilmar_bonus(self):
        base=carrying_view(strength=3)
        components=GeneratedNpc(3,1,3,3,4,4,initial_generated_weapons(GeneratedWeapon.STAFF),
            ArmourLoadout((BodyArmour.ITHILMAR,),BodyArmour.ITHILMAR),defence=4)
        npc=components.participant('minion1')
        absent=replace(base,enemies=(npc,))
        self.assertFalse(external_inventory_conditions(absent,'minion1'))
        inventory=initial_weapon_inventory('minion1',(
            WeaponItemSource('staff',WeaponKind.STAFF,WeaponItemLocation.HELD,WeaponGrip.LEFT),
            WeaponItemSource('spare',WeaponKind.DAGGER,WeaponItemLocation.CARRIED,None)))
        current=replace(npc,state=replace(npc.state,weapon_inventory=inventory))
        view=replace(base,enemies=(current,))
        self.assertEqual(external_inventory_conditions(view,'minion1'),frozenset((Condition.BURDENED,)))
        spare=inventory.items[1]
        lighter=inventory.with_item(replace(spare,location=WeaponItemLocation.DROPPED))
        current=replace(current,state=replace(current.state,weapon_inventory=lighter))
        self.assertFalse(external_inventory_conditions(replace(view,enemies=(current,)),'minion1'))
        self.assertEqual(components.strength,1)

    def test_one_throwing_knife_set_counts_as_one_physical_carried_unit(self):
        view=carrying_view(strength=2)
        source=view.source.party[0]
        inventory=initial_weapon_inventory('pc',(
            WeaponItemSource('staff',WeaponKind.STAFF,WeaponItemLocation.HELD,WeaponGrip.LEFT),
            WeaponItemSource('knife-set',WeaponKind.THROWING_KNIVES,WeaponItemLocation.CARRIED,None)))
        self.assertEqual(len(inventory.items),2)
        self.assertFalse(initial_pc_inventory_injury(source,inventory,CharacterInjuryState()).conditions.has(Condition.BURDENED))

    def test_invalid_actor_inventory_or_injury_facts_are_rejected(self):
        view=carrying_view()
        with self.assertRaises(ValueError):external_inventory_conditions(view,'missing')
        with self.assertRaises(TypeError):external_inventory_conditions(view,True)
        with self.assertRaises(TypeError):initial_pc_inventory_injury(view.source.party[0],{},CharacterInjuryState())
        with self.assertRaises(TypeError):initial_pc_inventory_injury(view.source.party[0],view.party[0].weapon_inventory,{})
        with self.assertRaises(TypeError):reconcile_pc_inventory_burden(view,{})


if __name__=='__main__':unittest.main()
