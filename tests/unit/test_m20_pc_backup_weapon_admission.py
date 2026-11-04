"""Explicit two-item source, carrying boundary and fixed-party generation."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
from fractions import Fraction
import unittest

from tests.support.pc_weapon_scenarios import backup_weapon_source
from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceRequest,PcMeleeCompositionGroup,project_pc_melee_candidate,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_models import (
    PcBackupWeaponPolicy,PcMeleeWeapon,PcWeaponHand,PcTwoHandedGrip,
)
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest


class PcBackupAdmissionTests(unittest.TestCase):
    def test_six_explicit_one_handed_backups_and_both_preferred_sides(self):
        source=backup_weapon_source()
        for weapon in (PcMeleeWeapon.STAFF,PcMeleeWeapon.SWORD,PcMeleeWeapon.DAGGER,
                PcMeleeWeapon.AXE,PcMeleeWeapon.WARHAMMER,PcMeleeWeapon.MORNING_STAR):
            for side in PcWeaponHand:
                policy=PcBackupWeaponPolicy(weapon,side)
                member=replace(source.party[0],backup_weapon_policy=policy)
                accepted=PcMeleeSimulationRequest(replace(source,party=(member,*source.party[1:])),42,1)
                self.assertEqual(accepted.scenario.party[0].backup_weapon_policy,policy)

    def test_two_weapons_require_carry_capacity_and_two_handed_primary(self):
        member=backup_weapon_source().party[0]
        with self.assertRaises(ValueError):
            replace(member,pc=replace(member.pc,strength=1))
        with self.assertRaises(ValueError):
            replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.STAFF),initial_weapon_hand=PcWeaponHand.LEFT)
        for value in (PcMeleeWeapon.PICKAXE,PcMeleeWeapon.FLAIL,PcMeleeWeapon.GREATHAMMER):
            with self.assertRaises(ValueError):
                PcBackupWeaponPolicy(value,PcWeaponHand.LEFT)

    def test_policy_and_cached_source_keep_exact_types(self):
        for weapon,hand in (('sword',PcWeaponHand.LEFT),(PcMeleeWeapon.SWORD,'left'),
                (PcMeleeWeapon.SWORD,PcTwoHandedGrip.BOTH),(True,PcWeaponHand.LEFT)):
            with self.assertRaises(TypeError):
                PcBackupWeaponPolicy(weapon,hand)
        source=backup_weapon_source()
        forged=deepcopy(source)
        policy=forged.party[0].backup_weapon_policy
        alias=Enum('OtherHand',{'RIGHT':'right'},type=str).RIGHT
        object.__setattr__(policy,'preferred_hand',alias)
        self.assertEqual(forged,source)
        with self.assertRaises(TypeError):
            PcMeleeSimulationRequest(forged,42,1)

    def test_count_projection_fixes_both_items_hand_and_support_resources(self):
        source=backup_weapon_source()
        request=PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',('minion1',),0,1),
            PcMeleeCompositionGroup('brutes',('brute1',),1,1)),source.facts,42,1,2,2,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        candidate=project_pc_melee_candidate(request,(0,1)).scenario
        for actual,original in zip(candidate.party,source.party,strict=True):
            self.assertEqual(actual.pc,original.pc)
            self.assertEqual(actual.backup_weapon_policy,original.backup_weapon_policy)
            self.assertEqual(actual.fate,original.fate)
            self.assertEqual(actual.policy,original.policy)


if __name__=='__main__':
    unittest.main()
