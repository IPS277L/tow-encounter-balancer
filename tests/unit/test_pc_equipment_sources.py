"""PC authoring sources compile all items to one common runtime inventory."""
from dataclasses import FrozenInstanceError,replace
from types import SimpleNamespace
import unittest

from tests.support.weapon_reload import execute_scripted_weapon_reload
from towr.application.encounter_inventory import (
    ArmourItem,ArmourItemKind,EncounterEquipment,ItemLocation,WeaponItem,
)
from towr.domain.armour_models import BodyArmour,HelmetKind,ShieldKind
from towr.domain.fate_models import FateSessionState
from towr.domain.minion_defeat_models import MinionDefeatDecision,NpcDefeatDisposition
from towr.domain.pc_combat_equipment_models import (
    PcItemLocation as L,PcWeaponItem,validate_pc_combat_equipment,validate_pc_weapon_inventory,
)
from towr.domain.pc_melee_models import (
    PcFatePolicy,PcHeavyWoundPolicy,PcMeleeDefinition,PcMeleeParticipant,PcMeleePolicy,
    PcMeleeWeapon as W,PcRandomSidePolicy,PcRangedProfile,PcRangedReloadHandPolicy,
    PcShieldHandConflictPolicy,PcShieldLoadout,PcShieldRecoveryPolicy,
    PcTwoHandedGrip as Both,PcWeaponHand as H,
)
from towr.domain.pc_shield_models import PcShieldLocation,PcShieldState,initial_pc_shield
from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import (
    TWO_HANDED_COUNT_BURDEN_RULE_ID,WEAPON_COUNT_BURDEN_RULE_ID,WeaponGrip as G,
    WeaponInventoryState,WeaponItemLocation,carrying_burden_rule_ids,weapon_unit_id,
)
from towr.domain.weapon_use_models import build_weapon_use


def shield(hand=H.RIGHT):
    return PcShieldLoadout(hand,PcShieldHandConflictPolicy.WEAPON_FIRST,
        PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK)


def participant(*,equipment=None,weapon=W.SWORD,hand=H.LEFT,strength=3,
        policy=PcMeleePolicy.AUTOMATIC_COMBAT,ranged=None,held_shield=None,initiative=3,awareness=None,dexterity=None):
    pc=PcMeleeDefinition('pc-profile',3,strength,3,3,5,5,4,4,weapon,0,ranged=ranged,initiative=initiative,awareness=awareness,dexterity=dexterity)
    return PcMeleeParticipant('pc',pc,FateSessionState('session','pc',0,0),policy,
        PcFatePolicy.DECLINE_OPTIONAL_FATE,PcRandomSidePolicy.D10_LOW_LEFT_HIGH_RIGHT,
        PcHeavyWoundPolicy.CONTINUE_FIGHTING,hand,('enemy',),
        (MinionDefeatDecision('pc','enemy',NpcDefeatDisposition.KNOCKED_OUT,True),),
        None,None,None,None,None,shield=held_shield,combat_equipment=equipment)


def pistol_profile():
    return PcRangedProfile(3, 5,  True, True, True, PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS)


def member(source,inventory=None,held_shield=None):
    return SimpleNamespace(actor_id=source.actor_id,
        weapon_inventory=initial_pc_weapon_inventory(source) if inventory is None else inventory,
        shield=initial_pc_shield(source.shield) if held_shield is None else held_shield)


class PcEquipmentSourceTests(unittest.TestCase):
    def test_pc_item_is_initial_source_and_has_no_runtime_drop_or_reload_state(self):
        sword=PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT)
        self.assertFalse(hasattr(sword,'reload'))
        with self.assertRaises(FrozenInstanceError):sword.location=L.CARRIED
        for location in (L.DROPPED,L.DEPLOYED):
            with self.subTest(location=location),self.assertRaises(ValueError):
                PcWeaponItem('source',W.SWORD,location,None)
        for fields in ({'initially_loaded':1},{'initially_loaded':True},{'hand':'left'}):
            with self.subTest(fields=fields),self.assertRaises((TypeError,ValueError)):
                replace(sword,**fields)
        self.assertFalse(PcWeaponItem('gun',W.PISTOL,L.CARRIED,None,initially_loaded=False).initially_loaded)
        with self.assertRaises(ValueError):PcWeaponItem('carried',W.SWORD,L.CARRIED,H.LEFT)

    def test_arbitrary_equipment_and_two_held_weapons_need_no_backup_policy(self):
        items=(PcWeaponItem('left',W.SWORD,L.HELD,H.LEFT),
            PcWeaponItem('right',W.WARHAMMER,L.HELD,H.RIGHT),
            PcWeaponItem('back',W.GLAIVE,L.CARRIED,None),
            PcWeaponItem('spare',W.GREATSWORD,L.CARRIED,None),
            PcWeaponItem('knife',W.DAGGER,L.CARRIED,None))
        source=participant(equipment=items,strength=1)
        inventory=initial_pc_weapon_inventory(source)
        self.assertIs(type(inventory),WeaponInventoryState)
        self.assertEqual(tuple(i.source_item_id for i in inventory.items),tuple(i.id for i in items))
        self.assertEqual(tuple(i.grip for i in inventory.items),(G.LEFT,G.RIGHT,None,None,None))
        self.assertIsNone(source.backup_weapon_policy)
        self.assertEqual(carrying_burden_rule_ids(inventory,1),
            (WEAPON_COUNT_BURDEN_RULE_ID,TWO_HANDED_COUNT_BURDEN_RULE_ID))
        validate_pc_weapon_inventory(member(source,inventory),source)

    def test_first_held_source_is_primary_even_when_a_carried_item_precedes_it(self):
        items=(PcWeaponItem('back',W.GLAIVE,L.CARRIED,None),
            PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT),
            PcWeaponItem('axe',W.AXE,L.HELD,H.RIGHT))
        source=participant(equipment=items)
        self.assertEqual(initial_pc_weapon_inventory(source).active.source_item_id,'sword')
        with self.assertRaises(ValueError):participant(equipment=items,weapon=W.AXE,hand=H.RIGHT)
        with self.assertRaises(ValueError):participant(equipment=items,hand=H.RIGHT)
        with self.assertRaises(ValueError):participant(equipment=(items[0],))

    def test_additional_exacting_items_have_independent_explicit_initial_readiness(self):
        items=(PcWeaponItem('left',W.PISTOL,L.HELD,H.LEFT,initially_loaded=True),
            PcWeaponItem('right',W.PISTOL,L.HELD,H.RIGHT,initially_loaded=False),
            PcWeaponItem('spare',W.CROSSBOW,L.CARRIED,None,initially_loaded=True))
        source=participant(equipment=items,weapon=W.PISTOL,ranged=pistol_profile(),dexterity=4)
        inventory=initial_pc_weapon_inventory(source)
        self.assertEqual(tuple(i.reload.loaded for i in inventory.items),(True,False,True))
        self.assertEqual(tuple(i.reload.weapon_instance_id for i in inventory.items),tuple(i.id for i in inventory.items))
        self.assertEqual(tuple(i.reload.weapon_id.value for i in inventory.items),('pistol','pistol','crossbow'))
        self.assertEqual(inventory.items[1].reload.exacting.contributions,())
        with self.assertRaises(ValueError):
            participant(equipment=(items[0],replace(items[1],initially_loaded=None)),
                weapon=W.PISTOL,ranged=pistol_profile(),dexterity=4)

    def test_hand_conflicts_remain_illegal_independent_of_capacity(self):
        left=PcWeaponItem('left',W.SWORD,L.HELD,H.LEFT)
        for items in ((left,replace(left,id='other')),
                (left,PcWeaponItem('glaive',W.GLAIVE,L.HELD,Both.BOTH)),
                (left,replace(left))):
            with self.subTest(items=items),self.assertRaises(ValueError):participant(equipment=items)
        with self.assertRaises(ValueError):participant(equipment=(left,
            PcWeaponItem('right',W.AXE,L.HELD,H.RIGHT)),held_shield=shield(H.RIGHT))
        allowed=participant(equipment=(left,PcWeaponItem('back',W.GLAIVE,L.CARRIED,None)),
            held_shield=shield(H.RIGHT),strength=1)
        self.assertIs(initial_pc_weapon_inventory(allowed).shield_hand,G.RIGHT)

    def test_carried_weapons_require_their_actual_skills_and_preparation(self):
        gun=PcWeaponItem('gun',W.PISTOL,L.HELD,H.LEFT,initially_loaded=True)
        rifle=PcWeaponItem('rifle',W.HOCHLAND_LONG_RIFLE,L.CARRIED,None,initially_loaded=True)
        with self.assertRaises(ValueError):
            participant(equipment=(gun,rifle),weapon=W.PISTOL,ranged=pistol_profile(),dexterity=4)
        source=participant(equipment=(gun,rifle),weapon=W.PISTOL,
            ranged=pistol_profile(),awareness=4,dexterity=4)
        self.assertEqual(len(initial_pc_weapon_inventory(source).items),2)
        with self.assertRaises(ValueError):
            participant(equipment=(gun,PcWeaponItem('net',W.WEIGHTED_NET,L.CARRIED,None)),
                weapon=W.PISTOL,ranged=pistol_profile(),dexterity=4)

    def test_compact_manual_source_compiles_once_without_explicit_equipment(self):
        source=participant(policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF)
        self.assertIsNone(source.combat_equipment)
        validate_pc_combat_equipment(source)
        inventory=initial_pc_weapon_inventory(source)
        self.assertIs(type(inventory),WeaponInventoryState)
        self.assertEqual(inventory.active.id,weapon_unit_id('pc','weapon',0))
        self.assertIs(inventory.active.kind,WeaponKind.SWORD)
        validate_pc_weapon_inventory(member(source,inventory),source)

    def test_runtime_retains_full_source_and_selection_without_backup_or_hand_mirrors(self):
        source=participant(equipment=(PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT),
            PcWeaponItem('axe',W.AXE,L.HELD,H.RIGHT)))
        inventory=initial_pc_weapon_inventory(source)
        first,second=inventory.items
        changed=inventory.with_item(replace(first,location=WeaponItemLocation.DROPPED,grip=None))
        self.assertEqual(changed.active_item_id,first.id)
        validate_pc_weapon_inventory(member(source,changed),source)
        with self.assertRaises(ValueError):build_weapon_use('pc',changed,first.id)
        self.assertIs(build_weapon_use('pc',changed,second.id).kind,WeaponKind.AXE)
        selected=replace(changed,active_item_id=second.id)
        validate_pc_weapon_inventory(member(source,selected),source)
        with self.assertRaises(ValueError):validate_pc_weapon_inventory(
            SimpleNamespace(actor_id='other',weapon_inventory=selected,shield=None),source)
        for forged in (replace(inventory,items=inventory.items[:1]),
                replace(inventory,items=tuple(reversed(inventory.items))),
                replace(inventory,items=(replace(first,source=replace(first.source,kind=WeaponKind.AXE)),second))):
            with self.subTest(forged=forged),self.assertRaises(ValueError):
                validate_pc_weapon_inventory(member(source,forged),source)

    def test_runtime_reload_membership_retains_the_actual_k1_state_without_scalar_mirrors(self):
        source=participant(equipment=(PcWeaponItem('gun',W.PISTOL,L.HELD,H.LEFT,initially_loaded=False),),
            weapon=W.PISTOL,ranged=pistol_profile(),dexterity=4)
        inventory=initial_pc_weapon_inventory(source)
        gun=inventory.active
        actual=execute_scripted_weapon_reload(gun.reload,(1,10))
        changed=inventory.with_item(replace(gun,reload=actual.state))
        validate_pc_weapon_inventory(member(source,changed),source)
        self.assertIs(changed.active.reload,actual.state)
        self.assertEqual(changed.active.reload.exacting.contributions,(actual.exacting.contribution,))

    def test_runtime_shield_hand_follows_physical_state_including_unavailable(self):
        source=participant(equipment=(PcWeaponItem('sword',W.SWORD,L.HELD,H.LEFT),),held_shield=shield())
        inventory=initial_pc_weapon_inventory(source)
        validate_pc_weapon_inventory(member(source,inventory),source)
        unavailable=PcShieldState(PcShieldLocation.UNAVAILABLE,H.RIGHT)
        validate_pc_weapon_inventory(member(source,inventory,unavailable),source)
        dropped=PcShieldState(PcShieldLocation.DROPPED,None)
        with self.assertRaises(ValueError):validate_pc_weapon_inventory(member(source,inventory,dropped),source)
        freed=replace(inventory,shield_hand=None)
        validate_pc_weapon_inventory(member(source,freed,dropped),source)
        with self.assertRaises(ValueError):validate_pc_weapon_inventory(member(source,freed),source)

    def test_app_loadout_keeps_every_item_primary_first_and_allows_legal_burden(self):
        equipment=EncounterEquipment((WeaponItem('back',W.GLAIVE,ItemLocation.CARRIED),
            WeaponItem('left',W.SWORD,ItemLocation.LEFT),
            WeaponItem('right',W.SWORD,ItemLocation.RIGHT),
            WeaponItem('hammer',W.GREATHAMMER,ItemLocation.CARRIED)),())
        loadout=equipment.combat_loadout(1)
        self.assertEqual(tuple(item.id for item in loadout['combat_equipment']),('left','back','right','hammer'))
        self.assertIs(loadout['weapon'],W.SWORD)
        self.assertIs(loadout['weapon_hand'],H.LEFT)
        self.assertIsNone(loadout['backup_weapon_policy'])
        source=participant(equipment=loadout['combat_equipment'],strength=1)
        self.assertEqual(carrying_burden_rule_ids(initial_pc_weapon_inventory(source),1),
            (WEAPON_COUNT_BURDEN_RULE_ID,TWO_HANDED_COUNT_BURDEN_RULE_ID))

    def test_app_loadout_transfers_independent_charge_and_keeps_armour_rules(self):
        equipment=EncounterEquipment((WeaponItem('gun',W.PISTOL,ItemLocation.LEFT,initially_loaded=False),
            WeaponItem('spare',W.PISTOL,ItemLocation.CARRIED,initially_loaded=True)),(
            ArmourItem('body',ArmourItemKind.LIGHT,ItemLocation.WORN),
            ArmourItem('helmet',ArmourItemKind.HELMET,ItemLocation.WORN),
            ArmourItem('shield',ArmourItemKind.SHIELD,ItemLocation.RIGHT)))
        loadout=equipment.combat_loadout(1)
        self.assertEqual(tuple(item.initially_loaded for item in loadout['combat_equipment']),(False,True))
        self.assertEqual(loadout['armour'].body,(BodyArmour.LIGHT,))
        self.assertIs(loadout['armour'].helmet,HelmetKind.HELMET)
        self.assertIs(loadout['armour'].shield,ShieldKind.SHIELD)
        with self.assertRaises(ValueError):replace(equipment,weapons=(equipment.weapons[0],
            replace(equipment.weapons[1],initially_loaded=None))).combat_loadout(3)
        with self.assertRaises(ValueError):WeaponItem('bow',W.SHORTBOW,ItemLocation.BOTH,initially_loaded=True)

    def test_app_rejects_actual_hand_conflicts_and_keeps_carried_only_inventory(self):
        sword=WeaponItem('sword',W.SWORD,ItemLocation.LEFT)
        for equipment in (EncounterEquipment((sword,replace(sword,id='other')),()),
                EncounterEquipment((sword,WeaponItem('glaive',W.GLAIVE,ItemLocation.BOTH)),()),
                EncounterEquipment((sword,),(ArmourItem('shield',ArmourItemKind.SHIELD,ItemLocation.LEFT),))):
            with self.subTest(equipment=equipment),self.assertRaises((TypeError,ValueError)):
                equipment.combat_loadout(3)
        with self.assertRaises(ValueError):
            replace(sword,weapon=W.GLAIVE)
        carried=EncounterEquipment((replace(sword,location=ItemLocation.CARRIED),),()).combat_loadout(3)
        self.assertIs(carried['weapon'],W.UNARMED)
        self.assertIsNone(carried['weapon_hand'])
        self.assertEqual(len(carried['combat_equipment']),1)


if __name__=='__main__':unittest.main()
