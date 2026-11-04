"""New weapons keep the same single-weapon source and generation boundary."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
from fractions import Fraction
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_weapon_scenarios import varied_weapon_source
from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceRequest,PcMeleeCompositionGroup,project_pc_melee_candidate,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest


class PcWeaponAdmissionTests(unittest.TestCase):
    def test_all_six_typed_weapons_share_existing_single_weapon_input(self):
        source=make_pc_melee_scenario()
        self.assertEqual({weapon.value for weapon in PcMeleeWeapon},
            {'staff','sword','dagger','axe','warhammer','morning_star'})
        for weapon in PcMeleeWeapon:
            member=replace(source.party[0],pc=replace(source.party[0].pc,weapon=weapon))
            request=PcMeleeSimulationRequest(replace(source,party=(member,)),42,1)
            self.assertIs(request.scenario.party[0].pc.weapon,weapon)

    def test_cached_weapon_enum_alias_and_raw_strings_are_refused_before_trial(self):
        source=varied_weapon_source()
        alias=Enum('ForeignWeapon',{'AXE':'axe'},type=str).AXE
        for value in ('axe',alias,None,True):
            with self.assertRaises(TypeError):
                replace(source.party[0].pc,weapon=value)
        forged=deepcopy(source)
        object.__setattr__(forged.party[0].pc,'weapon',alias)
        self.assertEqual(forged,source)
        with self.assertRaises(TypeError):
            PcMeleeSimulationRequest(forged,42,1)

    def test_generation_fixes_each_weapon_with_fate_and_support_policy(self):
        source=varied_weapon_source()
        request=PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',('minion1',),0,1),
            PcMeleeCompositionGroup('brutes',('brute1',),1,1)),source.facts,42,1,2,2,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        candidate=project_pc_melee_candidate(request,(0,1)).scenario
        self.assertEqual(candidate.enemy_activation_order,('brute1',))
        for actual,original in zip(candidate.party,source.party,strict=True):
            self.assertEqual(actual.pc,original.pc)
            self.assertEqual(actual.fate,original.fate)
            self.assertEqual(actual.policy,original.policy)
            self.assertEqual(actual.ally_recover_policy,original.ally_recover_policy)


if __name__=='__main__':
    unittest.main()
