"""Complete PG96 sources and exact prepared primary impacts, without battle RNG."""
from dataclasses import replace
import unittest

from towr.domain.armour_models import ArmourLoadout, ShieldKind
from towr.domain.attack_models import ConditionImpactSpec, DamageProfile, HazardImpactSpec, ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import (
    GeneratedAbility, GeneratedNpc, GeneratedRangedFacts, GeneratedWeapon,
    GENERATED_THROWING_WEAPONS, generated_initial_weapon_inventory, generated_npc_profiles,
    generated_weapon_allows_shield, validate_generated_definition,
)
from towr.domain.npc_attack_preparation_models import (
    NpcAttackProfile, NpcAttackPreparationRequest, NpcAttackSelectionSnapshot,
)
from towr.domain.pc_melee_models import PcMeleeDefinition, PC_EXECUTABLE_WEAPONS, PC_THROWING_WEAPONS
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_inventory_models import WeaponGrip as G, WeaponItemLocation as L, WeaponItemSource
from towr.domain.weapon_impact_preparation import (
    ROCK_IMPACT_RULE_ID, NET_IMPACT_RULE_ID, OIL_IMPACT_RULE_ID, BLAST_IMPACT_RULE_ID,
)
from towr.rules.npc_attack_preparation import prepare_npc_attack


KINDS=(W.ROCK,W.THROWING_SPEAR,W.THROWING_AXE,W.WEIGHTED_NET,
    W.THROWING_KNIVES,W.OIL_FLASK,W.BLASTING_CHARGE)


def item(kind, *, quantity=1, carried=False):
    return WeaponItemSource('actual:'+kind.value,kind,L.CARRIED if carried else L.HELD,
        None if carried else G.BOTH if kind is W.WEIGHTED_NET else G.LEFT,quantity=quantity)


def npc(kind=W.ROCK, *, strength=3, throwing=5, ballistic_skill=2, weapons=None,
        ranged=None, abilities=()):
    return GeneratedNpc(4,strength,3,3,4,4,(item(kind),) if weapons is None else weapons,
        ArmourLoadout(),defence=4,throwing=throwing,ballistic_skill=ballistic_skill,
        ranged=ranged,abilities=abilities)


def profile(kind, **kwargs):
    return generated_npc_profiles(npc(kind,**kwargs))[1][0]


class ThrowingWeaponSourceTests(unittest.TestCase):
    def test_complete_pg96_set_is_admitted_for_both_roles(self):
        self.assertEqual(tuple(kind.value for kind in GENERATED_THROWING_WEAPONS),
            tuple(kind.value for kind in KINDS))
        self.assertEqual(PC_THROWING_WEAPONS,KINDS)
        for kind in KINDS:
            with self.subTest(kind=kind):
                self.assertIn(kind,PC_EXECUTABLE_WEAPONS)
                self.assertIs(npc(kind).weapon,GeneratedWeapon(kind.value))

    def test_all_profiles_use_actual_bs_throwing_not_strength_or_melee(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                attack=profile(kind)
                self.assertIs(attack.skill,Skill.THROWING)
                self.assertEqual(attack.test_profile,InlineProfile(2,5))
                self.assertIs(attack.hands,Hands.TWO_HANDED if kind is W.WEIGHTED_NET else Hands.ONE_HANDED)
                self.assertFalse(attack.ignores_armour)

    def test_ranges_are_literal_printed_bands_with_one_strength_extension(self):
        # PG96 literal table, independent of production range calculation.
        printed={W.ROCK:(Range.SHORT,Range.MEDIUM),W.THROWING_SPEAR:(Range.CLOSE,Range.MEDIUM),
            W.THROWING_AXE:(Range.SHORT,Range.SHORT),W.WEIGHTED_NET:(Range.CLOSE,Range.SHORT),
            W.THROWING_KNIVES:(Range.SHORT,Range.SHORT),W.OIL_FLASK:(Range.SHORT,Range.MEDIUM),
            W.BLASTING_CHARGE:(Range.SHORT,Range.MEDIUM)}
        extended={Range.SHORT:Range.MEDIUM,Range.MEDIUM:Range.LONG}
        for kind,(low,high) in printed.items():
            for strength in (3,4,8):
                with self.subTest(kind=kind,strength=strength):
                    attack=profile(kind,strength=strength)
                    self.assertEqual((attack.range_min,attack.range_max),
                        (low,high if strength==3 else extended[high]))

    def test_special_impacts_have_no_dummy_damage_or_secondary_effect(self):
        for kind,condition,rule in ((W.ROCK,Condition.STAGGERED,ROCK_IMPACT_RULE_ID),
                (W.WEIGHTED_NET,Condition.BURDENED,NET_IMPACT_RULE_ID),
                (W.OIL_FLASK,Condition.ABLAZE,OIL_IMPACT_RULE_ID)):
            with self.subTest(kind=kind):
                attack=profile(kind)
                self.assertIsNone(attack.damage)
                self.assertIsNone(attack.hazard_impact)
                self.assertEqual(attack.condition_impact,ConditionImpactSpec(condition,rule))
                self.assertEqual(attack.secondary_effects,())
        blast=profile(W.BLASTING_CHARGE)
        self.assertIsNone(blast.damage)
        self.assertIsNone(blast.condition_impact)
        self.assertEqual(blast.hazard_impact,HazardImpactSpec(3,Skill.ENDURANCE,BLAST_IMPACT_RULE_ID))
        self.assertEqual(blast.secondary_effects,())

    def test_numeric_damage_and_authored_on_hit_effects_remain_source_bound(self):
        for kind,base in ((W.THROWING_SPEAR,3),(W.THROWING_AXE,4),(W.THROWING_KNIVES,3)):
            with self.subTest(kind=kind):
                attack=profile(kind,abilities=(GeneratedAbility.DRAINED_ON_HIT,))
                self.assertEqual(attack.damage,DamageProfile(base))
                self.assertIsNone(attack.condition_impact)
                self.assertIsNone(attack.hazard_impact)
                self.assertEqual(len(attack.secondary_effects),1)
                self.assertIs(attack.secondary_effects[0].condition,Condition.DRAINED)
        for kind in (W.ROCK,W.WEIGHTED_NET,W.OIL_FLASK,W.BLASTING_CHARGE):
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                npc(kind,abilities=(GeneratedAbility.DRAINED_ON_HIT,))
        mixed=npc(weapons=(item(W.ROCK),WeaponItemSource('carried-spear',W.THROWING_SPEAR,L.CARRIED,None)),
            abilities=(GeneratedAbility.DRAINED_ON_HIT,))
        attacks=generated_npc_profiles(mixed)[1]
        self.assertTrue(all(not attack.secondary_effects for attack in attacks if attack.condition_impact is not None))
        self.assertTrue(all(attack.secondary_effects for attack in attacks if attack.damage is not None))

    def test_missing_or_detached_throwing_facts_are_rejected(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):npc(kind,throwing=None)
                with self.assertRaises(ValueError):npc(kind,ballistic_skill=None)
                with self.assertRaises(ValueError):npc(kind,throwing=True)
        with self.assertRaises(ValueError):npc(weapons=(item(W.SWORD),))

    def test_mixed_shooting_throwing_uses_one_actual_ballistic_skill(self):
        ranged=GeneratedRangedFacts(4,3,3,4,True,True,True)
        weapons=(item(W.THROWING_AXE),WeaponItemSource('pistol',W.PISTOL,L.CARRIED,None,initially_loaded=True))
        source=npc(weapons=weapons,ballistic_skill=None,ranged=ranged)
        attacks=generated_npc_profiles(source)[1]
        self.assertTrue(all(attack.test_profile==InlineProfile(4,5 if attack.skill is Skill.THROWING else 3)
            for attack in attacks))
        with self.assertRaises(ValueError):npc(weapons=weapons,ballistic_skill=2,ranged=ranged)

    def test_rock_uses_one_real_hand_with_optional_shield_without_changing_printed_hands(self):
        from towr.domain.weapon_catalog import weapon_profile
        self.assertIsNone(weapon_profile(W.ROCK).hands)
        self.assertTrue(generated_weapon_allows_shield(GeneratedWeapon.ROCK))
        source=replace(npc(),armour=ArmourLoadout(shield=ShieldKind.SHIELD))
        inventory=generated_initial_weapon_inventory(source,'npc')
        self.assertIs(inventory.active.grip,G.LEFT)
        self.assertIs(inventory.shield_hand,G.RIGHT)
        with self.assertRaises(ValueError):WeaponItemSource('rock',W.ROCK,L.HELD,G.BOTH)

    def test_quantity_expands_distinct_finite_source_units_not_an_infinite_weapon(self):
        for kind in (W.ROCK,W.THROWING_SPEAR,W.THROWING_AXE,W.OIL_FLASK,W.BLASTING_CHARGE):
            with self.subTest(kind=kind):
                source=npc(weapons=(item(kind,quantity=3),))
                inventory=generated_initial_weapon_inventory(source,'npc')
                self.assertEqual(len(inventory.items),3)
                self.assertEqual(len({unit.id for unit in inventory.items}),3)
                self.assertEqual(tuple(unit.location for unit in inventory.items),(L.HELD,L.CARRIED,L.CARRIED))
                self.assertTrue(all(unit.source==source.weapons[0] for unit in inventory.items))

    def test_all_pc_primary_throwing_weapons_need_real_bs_and_throwing(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                args=('pc',3,3,3,3,4,4,4,4,kind,0)
                source=PcMeleeDefinition(*args,throwing=5,ballistic_skill=2)
                self.assertEqual(source.throwing_profile.characteristic,2)
                self.assertEqual(source.throwing_profile.skill,5)
                with self.assertRaises(ValueError):PcMeleeDefinition(*args)
                with self.assertRaises(ValueError):PcMeleeDefinition(*args,throwing=5)

    def test_hazard_profile_requires_one_exact_primary_impact(self):
        attack=profile(W.BLASTING_CHARGE)
        for changes in (dict(damage=DamageProfile(0)),dict(condition_impact=ConditionImpactSpec(Condition.ABLAZE,'fake')),
                dict(hazard_impact=None),dict(ignores_armour=True),dict(hazard_impact='hazard')):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(attack,**changes)
        malformed=HazardImpactSpec(3,Skill.ENDURANCE,BLAST_IMPACT_RULE_ID)
        object.__setattr__(malformed,'rating',3.0)
        with self.assertRaises(TypeError):replace(attack,hazard_impact=malformed)

    def test_real_npc_preparation_keeps_hazard_rating_skill_rule_without_damage(self):
        attack=profile(W.BLASTING_CHARGE)
        snapshot=NpcAttackSelectionSnapshot('snapshot','npc',(attack,),(attack.id,))
        source=NpcAttackPreparationRequest('prepare','attack','attacker-test',snapshot,attack.id,'target',
            Range.MEDIUM,ResilienceProfile(3),False,False,False)
        prepared=prepare_npc_attack(source)
        self.assertEqual(prepared.attack.impact_spec,HazardImpactSpec(3,Skill.ENDURANCE,BLAST_IMPACT_RULE_ID))
        self.assertEqual(prepared.attack.attacker_test.profile,InlineProfile(2,5))
        self.assertEqual(prepared.applied_rule_ids.count(BLAST_IMPACT_RULE_ID),1)
        with self.assertRaises(ValueError):replace(prepared,attack=replace(prepared.attack,
            impact_spec=HazardImpactSpec(4,Skill.ENDURANCE,BLAST_IMPACT_RULE_ID)))

    def test_complete_generated_rederive_rejects_tampered_impacts_damage_and_ranges(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                definition=npc(kind).participant('npc').definition
                validate_generated_definition(definition)
                primary=definition.attacks[0]
                corrupted=replace(primary,test_profile=InlineProfile(3,5))
                with self.assertRaises(ValueError):
                    replace(definition,attacks=(corrupted,*definition.attacks[1:]))
