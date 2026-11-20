"""PC counter capability follows concrete initial items, not a selected label."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_combat_equipment_models import PcItemLocation, PcWeaponItem
from towr.domain.pc_melee_models import (
    PcMeleePolicy, PcRangedProfile, PcRangedReloadHandPolicy, PcRepeaterBonusPolicy,
    PcTwoHandedGrip, PcWeaponHand,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.weapon_capability_models import weapon_ranged_requirements
from towr.domain.weapon_catalog import WeaponKind, weapon_profile
from towr.domain.weapon_inventory_models import weapon_reload_target
from towr.simulation.pc_melee_models import PcHelpActionCount
from towr.simulation.pc_ranged_statistics import PcRangedCount, validate_pc_ranged_counts


REPEATERS = (WeaponKind.REPEATER_PISTOL, WeaponKind.REPEATER_HANDBOW,
    WeaponKind.REPEATER_CROSSBOW, WeaponKind.REPEATER_HANDGUN)


def scenario(*inventories):
    base = make_pc_pistol_scenario(pc_count=len(inventories), max_rounds=3)
    party = []
    for member, kinds in zip(base.party, inventories, strict=True):
        requirements = weapon_ranged_requirements(tuple(kinds))
        grip = (PcTwoHandedGrip.BOTH if weapon_profile(kinds[0]).hands is
            RangedWeaponHands.TWO_HANDED else PcWeaponHand.LEFT)
        items = tuple(PcWeaponItem('item:' + str(index + 1), kind,
            PcItemLocation.HELD if index == 0 else PcItemLocation.CARRIED,
            grip if index == 0 else None,
            initially_loaded=True if weapon_reload_target(kind) is not None else None)
            for index, kind in enumerate(kinds))
        profile = PcRangedProfile(3, 4,  True if requirements.firearm else None, True if requirements.firearm else None, True, PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS if requirements.exacting else None, repeater_bonus_policy=PcRepeaterBonusPolicy.AUTOMATIC if requirements.repeater else None)
        party.append(replace(member, policy=PcMeleePolicy.AUTOMATIC_COMBAT,
            pc=replace(member.pc, weapon=kinds[0], strength=4, ranged=profile, initiative=3, awareness=4,dexterity=4 if requirements.exacting else None),
            initial_weapon_hand=grip, combat_equipment=items))
    return replace(base, party=tuple(party),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT, RangedWeaponRange.LONG),
        facts=replace(base.facts, all_opponents_close=False, can_leave_zone=True))


def zeros(actor):
    return PcRangedCount(actor, 0, 0, 0, 0, 0, 0)


class PcRangedCountInventoryTests(unittest.TestCase):
    def test_repeater_capability_is_independent_of_the_initial_primary_item(self):
        for repeater in REPEATERS:
            for kinds in ((WeaponKind.PISTOL, repeater), (repeater, WeaponKind.PISTOL)):
                with self.subTest(kinds=kinds):
                    source = scenario(kinds)
                    before = deepcopy(source)
                    swaps = int(kinds[0] is WeaponKind.PISTOL)
                    row = PcRangedCount('pc1', 1, 1, 0, 0, 0, swaps)
                    validate_pc_ranged_counts((row,), source,
                        started_rounds=1, actions=1, help_counts=())
                    self.assertEqual(source, before)
                    self.assertTrue(all(item.initially_loaded for item in source.party[0].combat_equipment))

    def test_bonus_shooting_help_uses_its_actor_full_inventory_and_real_help_budget(self):
        source = scenario((WeaponKind.PISTOL, WeaponKind.REPEATER_PISTOL), (WeaponKind.PISTOL,))
        counts = (PcRangedCount('pc1', 0, 0, 1, 1, 0, 1), zeros('pc2'))
        help_counts = (PcHelpActionCount('pc1', 1), PcHelpActionCount('pc2', 0))
        validate_pc_ranged_counts(counts, source, started_rounds=1, actions=1, help_counts=help_counts)
        with self.assertRaises(ValueError):
            validate_pc_ranged_counts(counts, source, started_rounds=1, actions=1, help_counts=())

    def test_single_non_repeater_weapons_cannot_invent_bonus_shots_or_help(self):
        for kind in (WeaponKind.PISTOL, WeaponKind.SLING, WeaponKind.SHORTBOW, WeaponKind.HANDGUN):
            source = scenario((kind,))
            for row in (PcRangedCount('pc1', 1, 1, 0, 0, 0, 0),
                    PcRangedCount('pc1', 0, 0, 1, 1, 0, 0)):
                with self.subTest(kind=kind, row=row), self.assertRaises(ValueError):
                    validate_pc_ranged_counts((row,), source, started_rounds=1, actions=1,
                        help_counts=(PcHelpActionCount('pc1', 1),))
            validate_pc_ranged_counts((PcRangedCount('pc1', 1, 0, 0, 0, 0, 0),), source,
                started_rounds=1, actions=1, help_counts=())

    def test_another_pc_repeater_does_not_authorise_an_ordinary_actor(self):
        source = scenario((WeaponKind.PISTOL,), (WeaponKind.REPEATER_PISTOL,))
        with self.assertRaises(ValueError):
            validate_pc_ranged_counts((PcRangedCount('pc1', 1, 1, 0, 0, 0, 0), zeros('pc2')),
                source, started_rounds=1, actions=1, help_counts=())

    def test_source_order_missing_zero_rows_and_foreign_actors_stay_invalid(self):
        source = scenario((WeaponKind.PISTOL, WeaponKind.REPEATER_PISTOL), (WeaponKind.PISTOL,))
        counts = (zeros('pc1'), zeros('pc2'))
        validate_pc_ranged_counts(counts, source, started_rounds=1, actions=0, help_counts=())
        for bad in (None, (), [], counts[:1], counts[::-1],
                (replace(counts[0], actor_id='foreign'), counts[1])):
            with self.subTest(counts=bad), self.assertRaises(ValueError):
                validate_pc_ranged_counts(bad, source, started_rounds=1, actions=0, help_counts=())

    def test_turn_action_swap_and_cached_zero_shot_guards_survive(self):
        source = scenario((WeaponKind.PISTOL, WeaponKind.REPEATER_PISTOL))
        cases = ((PcRangedCount('pc1', 1, 1, 0, 0, 1, 1), 1, 2),
            (PcRangedCount('pc1', 1, 1, 0, 0, 1, 1), 2, 1),
            (PcRangedCount('pc1', 1, 1, 0, 0, 0, 2), 1, 1))
        for row, rounds, actions in cases:
            with self.subTest(row=row, rounds=rounds), self.assertRaises(ValueError):
                validate_pc_ranged_counts((row,), source, started_rounds=rounds,
                    actions=actions, help_counts=())
        for field, value in (('bonus_shots', 1), ('bonus_help_tests', 1), ('shots', True)):
            row = zeros('pc1')
            object.__setattr__(row, field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_pc_ranged_counts((row,), source, started_rounds=1, actions=1, help_counts=())

    def test_a_non_ranged_source_does_not_gain_counter_rows(self):
        source = automatic_source(pc_count=1)
        validate_pc_ranged_counts(None, source, started_rounds=1, actions=0, help_counts=())
        with self.assertRaises(ValueError):
            validate_pc_ranged_counts((), source, started_rounds=1, actions=0, help_counts=())
