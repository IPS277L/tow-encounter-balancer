"""Source-bound count admission over complete NPC items, not a battle replay."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_tactics_fixtures import automatic_source
from tests.support.talent_sources import paid_talent
from towr.domain.talent_catalog import TalentId
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedRangedFacts
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_npc_ranged_source_models import (
    pc_npc_ranged_policy_for_generated, pc_npc_ranged_profile,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.weapon_capability_models import weapon_ranged_requirements
from towr.domain.weapon_catalog import WeaponKind, weapon_profile
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponItemLocation, WeaponItemSource, weapon_reload_target,
)
from towr.simulation.pc_npc_ranged_statistics import PcNpcRangedCount, validate_npc_ranged_counts
from towr.simulation.pc_rapid_reload_statistics import PcRapidReloadCount


REPEATERS = (WeaponKind.REPEATER_PISTOL, WeaponKind.REPEATER_HANDBOW,
    WeaponKind.REPEATER_CROSSBOW, WeaponKind.REPEATER_HANDGUN)


def scenario(*inventories):
    base = automatic_source(pc_count=1, enemy_count=len(inventories), rounds=3)
    enemies, policies = [], []
    for actor, kinds in zip(base.enemy_activation_order, inventories, strict=True):
        requirements = weapon_ranged_requirements(tuple(kinds))
        items = tuple(WeaponItemSource('item:' + str(index + 1), kind,
            WeaponItemLocation.HELD if index == 0 else WeaponItemLocation.CARRIED,
            (WeaponGrip.BOTH if weapon_profile(kind).hands is RangedWeaponHands.TWO_HANDED
                else WeaponGrip.LEFT) if index == 0 else None,
            initially_loaded=True if weapon_reload_target(kind) is not None else None)
            for index, kind in enumerate(kinds))
        facts = GeneratedRangedFacts(3, 4,  True, True if requirements.firearm else None, True if requirements.firearm else None)
        npc = GeneratedNpc(3, 4, 3, 3, 4, 4, items, ArmourLoadout(), defence=4, ranged=facts, initiative=3, awareness=4,dexterity=4 if requirements.exacting else None)
        enemies.append(npc.participant(actor))
        policies.append(pc_npc_ranged_policy_for_generated(npc, actor))
    return replace(base, enemies=tuple(enemies), npc_ranged_policies=tuple(policies),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.SHORT, RangedWeaponRange.LONG),
        facts=replace(base.facts, all_opponents_close=False, can_leave_zone=True))


class NpcRangedCountInventoryTests(unittest.TestCase):
    def test_rapid_reload_budget_requires_the_actual_actor_and_paired_actions(self):
        base=scenario((WeaponKind.PISTOL,))
        npc=base.enemies[0].definition.generated_components
        npc=replace(npc,ranged=replace(npc.ranged,ballistic_skill=4),
            talents=(paid_talent(TalentId.RAPID_RELOAD),))
        source=replace(base,enemies=(npc.participant('minion1'),),
            npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc,'minion1'),))
        paired=(PcNpcRangedCount('minion1',1,0,1),)
        witness=(PcRapidReloadCount('minion1',1),)
        validate_npc_ranged_counts(paired,source,started_rounds=1,actions=2,rapid_reload_counts=witness)
        with self.assertRaises(ValueError):
            validate_npc_ranged_counts(paired,source,started_rounds=1,actions=2)
        with self.assertRaises(ValueError):
            validate_npc_ranged_counts(paired,base,started_rounds=1,actions=2)
        with self.assertRaises(ValueError):
            validate_npc_ranged_counts(paired,source,started_rounds=1,actions=1,rapid_reload_counts=witness)
        for shots,reloads in ((2,0),(0,2),(2,2)):
            with self.subTest(shots=shots,reloads=reloads),self.assertRaises(ValueError):
                validate_npc_ranged_counts((PcNpcRangedCount('minion1',shots,0,reloads),),
                    source,started_rounds=1,actions=shots+reloads,rapid_reload_counts=witness)

    def test_a_carried_repeater_supplies_bonus_capability_independently_of_the_first_item(self):
        for repeater in REPEATERS:
            for kinds in ((WeaponKind.PISTOL, repeater), (repeater, WeaponKind.PISTOL)):
                with self.subTest(kinds=kinds):
                    source = scenario(kinds)
                    before = deepcopy(source)
                    first = pc_npc_ranged_profile(source.enemies[0].definition)
                    self.assertEqual(first.weapon_id.value, kinds[0].value)
                    validate_npc_ranged_counts((PcNpcRangedCount('minion1', 1, 1, 0),),
                        source, started_rounds=1, actions=1)
                    self.assertEqual(source, before)
                    self.assertTrue(all(item.initially_loaded for item in
                        source.enemies[0].definition.generated_components.weapons))

    def test_non_repeaters_cannot_claim_bonus_shots(self):
        for kind in (WeaponKind.PISTOL, WeaponKind.SLING, WeaponKind.SHORTBOW,
                WeaponKind.HANDGUN):
            with self.subTest(kind=kind):
                source = scenario((kind,))
                with self.assertRaises(ValueError):
                    validate_npc_ranged_counts((PcNpcRangedCount('minion1', 1, 1, 0),),
                        source, started_rounds=1, actions=1)
                validate_npc_ranged_counts((PcNpcRangedCount('minion1', 1, 0, 0),),
                    source, started_rounds=1, actions=1)

    def test_another_actor_repeater_does_not_grant_capability(self):
        source = scenario((WeaponKind.PISTOL,), (WeaponKind.REPEATER_PISTOL,))
        with self.assertRaises(ValueError):
            validate_npc_ranged_counts((PcNpcRangedCount('minion1', 1, 1, 0),
                PcNpcRangedCount('minion2', 0, 0, 0)), source, started_rounds=1, actions=1)

    def test_complete_actor_order_and_zero_rows_are_still_required(self):
        source = scenario((WeaponKind.PISTOL, WeaponKind.REPEATER_PISTOL),
            (WeaponKind.REPEATER_HANDBOW,))
        counts = (PcNpcRangedCount('minion1', 0, 0, 0), PcNpcRangedCount('minion2', 0, 0, 0))
        validate_npc_ranged_counts(counts, source, started_rounds=1, actions=0)
        for bad in (None, (), [], counts[:1], counts[::-1],
                (replace(counts[0], actor_id='foreign'), counts[1])):
            with self.subTest(counts=bad), self.assertRaises(ValueError):
                validate_npc_ranged_counts(bad, source, started_rounds=1, actions=0)

    def test_turn_total_action_and_cached_zero_shot_guards_survive(self):
        source = scenario((WeaponKind.PISTOL, WeaponKind.REPEATER_PISTOL))
        for row, rounds, actions in ((PcNpcRangedCount('minion1', 1, 1, 1), 1, 2),
                (PcNpcRangedCount('minion1', 1, 1, 1), 2, 1)):
            with self.subTest(row=row, rounds=rounds), self.assertRaises(ValueError):
                validate_npc_ranged_counts((row,), source, started_rounds=rounds, actions=actions)
        for field, value in (('bonus_shots', 1), ('shots', True), ('reload_actions', -1)):
            row = PcNpcRangedCount('minion1', 0, 0, 0)
            object.__setattr__(row, field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_npc_ranged_counts((row,), source, started_rounds=1, actions=1)

    def test_ranged_policies_cannot_hide_or_invent_the_source_actors(self):
        source = scenario((WeaponKind.PISTOL, WeaponKind.REPEATER_PISTOL))
        forged = deepcopy(source)
        object.__setattr__(forged, 'npc_ranged_policies', ())
        with self.assertRaises(ValueError):
            validate_npc_ranged_counts(None, forged, started_rounds=1, actions=0)
        forged = deepcopy(source)
        object.__setattr__(forged.npc_ranged_policies[0], 'actor_id', 'foreign')
        with self.assertRaises(ValueError):
            validate_npc_ranged_counts((PcNpcRangedCount('foreign', 0, 0, 0),),
                forged, started_rounds=1, actions=0)

    def test_a_melee_only_source_does_not_acquire_ranged_rows(self):
        source = automatic_source(pc_count=1)
        validate_npc_ranged_counts(None, source, started_rounds=1, actions=0)
        with self.assertRaises(ValueError):
            validate_npc_ranged_counts((), source, started_rounds=1, actions=0)
