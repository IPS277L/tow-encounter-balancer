"""An incidental Recover interaction must have an actually available pickup."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_tactics_fixtures import tactical_snapshot
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundRecord,WoundEntryId,WoundRestrictionEffect,WoundRestriction,WoundEffectDuration,
)
from towr.domain.pc_ally_recover_models import expected_pc_standard_recover,pc_after_standard_recover
from towr.domain.pc_combat_equipment_models import PcItemLocation,PcWeaponItem
from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind
from towr.domain.pc_melee_models import (
    PcMeleePolicy,PcMeleeWeapon,PcWeaponHand,PcBackupWeaponPolicy,PcShieldLoadout,
    PcShieldHandConflictPolicy,PcShieldRecoveryPolicy,
)
from towr.domain.pc_melee_result_models import build_pc_melee_recover
from towr.domain.pc_tactical_models import PcTacticalChoice
from towr.domain.pc_weapon_inventory import sync_pc_weapon_inventory,pc_weapon_pickup_member
from towr.domain.recover_models import RecoverObjectInteractionFollowUp
from towr.domain.turn_models import (
    CombatActionKind,CombatActionSlotRequest,CombatActionDeclaration,ActionSlotGrant,
)
from towr.rules.turn_resolution import reserve_combat_action_slot


def recover_state(*,injured=True):
    source=make_pc_pistol_scenario(pc_count=1)
    member=source.party[0]
    items=(PcWeaponItem('gun:owned',PcMeleeWeapon.PISTOL,PcItemLocation.HELD,PcWeaponHand.LEFT),
        PcWeaponItem('sword:owned',PcMeleeWeapon.SWORD,PcItemLocation.CARRIED,None))
    member=replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT,combat_equipment=items,
        backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.SWORD,PcWeaponHand.LEFT),
        shield=PcShieldLoadout(PcWeaponHand.RIGHT,PcShieldHandConflictPolicy.WEAPON_FIRST,
            PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK))
    source=replace(source,party=(member,))
    state=tactical_snapshot(source,'pc1')
    member=state.party[0]
    injury=replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.STAGGERED)
        .with_condition(Condition.DRAINED))
    body=()
    if injured:
        injury=replace(injury,
            wounds=(WoundRecord(1,WoundEntryId.SMASHED_HAND,12,(2,10),effect_resolved=True),),
            active_wound_effects=(WoundRestrictionEffect(1,
                WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL,WoundEffectDuration.UNTIL_TREATED),))
        body=(PcBodyFact(PcBodyFactKind.INJURED_HAND,1,PcWeaponHand.LEFT),)
    dropped=sync_pc_weapon_inventory(member,replace(member,injury=injury,body_facts=body,
        weapon_hand=None),source.party[0])
    clock=reserve_combat_action_slot(CombatActionSlotRequest('pure:reserve',state.round_state,'pc1',
        CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
    return replace(state,party=(dropped,),round_state=clock)


def self_recover(*,pickup=None):
    return PcTacticalChoice('pc1',CombatActionKind.RECOVER,'pc1',None,1.,
        'prepared:remove-stagger',pickup_item_id=pickup)


class PcRecoverIncidentalPickupTests(unittest.TestCase):
    def test_injured_hand_and_held_shield_do_not_invent_incidental_pickup(self):
        state=recover_state();before=state.party[0]
        self.assertIsNone(pc_weapon_pickup_member(state,'pc1','gun:owned'))
        with patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=self_recover()):
            request=build_pc_melee_recover(state)
            self.assertIsNone(request.choice.object_interaction)
            after,=pc_after_standard_recover(state,request,expected_pc_standard_recover(request))
        self.assertFalse(after.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(after.injury.conditions.has(Condition.DRAINED))
        self.assertFalse(after.injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertEqual(after.weapon_inventory,before.weapon_inventory)
        self.assertEqual(after.shield,before.shield)
        self.assertEqual(after.ranged,before.ranged)
        self.assertIsNone(after.weapon_hand)
        self.assertEqual(after.injury.wounds,before.injury.wounds)

    def test_unblocked_incidental_pickup_still_restores_the_exact_dropped_item(self):
        state=recover_state(injured=False)
        with patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=self_recover()):
            request=build_pc_melee_recover(state)
            self.assertEqual(request.choice.object_interaction.object_id,'gun:owned')
            after,=pc_after_standard_recover(state,request,expected_pc_standard_recover(request))
        self.assertEqual(after.weapon_inventory.active.id,'gun:owned')
        self.assertIs(after.weapon_inventory.active.location,PcItemLocation.HELD)
        self.assertIs(after.weapon_hand,PcWeaponHand.LEFT)
        self.assertEqual(after.weapon_inventory.items[1],state.party[0].weapon_inventory.items[1])
        self.assertEqual(after.shield,state.party[0].shield)

    def test_explicit_unavailable_pickup_remains_rejected(self):
        state=recover_state()
        with patch('towr.domain.pc_tactical_models.select_pc_tactic',
                return_value=self_recover(pickup='gun:owned')):
            with self.assertRaisesRegex(ValueError,'actual available pickup hand'):
                build_pc_melee_recover(state)

    def test_projection_guard_still_rejects_a_forged_blocked_interaction(self):
        state=recover_state()
        with patch('towr.domain.pc_tactical_models.select_pc_tactic',return_value=self_recover()):
            request=build_pc_melee_recover(state)
        forged=replace(request,choice=replace(request.choice,object_interaction=
            RecoverObjectInteractionFollowUp('forged:pickup','pc1','gun:owned',True)))
        with self.assertRaisesRegex(ValueError,'actually dropped item'):
            pc_after_standard_recover(state,forged,expected_pc_standard_recover(forged))


if __name__=='__main__':
    unittest.main()
