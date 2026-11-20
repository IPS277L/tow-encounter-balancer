"""Generated ranged facts, legal conditional proposals and full-source derivation."""
from tests.support.talent_sources import paid_talent
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from towr.domain.armour_models import BodyArmour, ShieldKind
from copy import deepcopy
from dataclasses import replace
from random import Random
import unittest

from tests.support.pc_tactics_fixtures import automatic_source
from towr.application.dynamic_encounter import NpcSearchSpace, automatic_npc_search_space
from towr.domain.generated_npc_models import (
    GeneratedNpc, GeneratedWeapon, GeneratedRangedFacts, GeneratedAbility,
    TalentId, GENERATED_RANGED_WEAPONS, validate_generated_definition,
)
from towr.domain.test_models import Skill, InlineProfile
from towr.domain.ranged_weapon_profiles import RangedWeaponRange


def ranged_facts(weapon=GeneratedWeapon.PISTOL, **changes):
    blackpowder=weapon is not GeneratedWeapon.REPEATER_HANDBOW
    values=dict(ballistic_skill=4,shooting=5,initiative=2,dexterity=3,
        ammunition_supply_confirmed=True,
        has_blackpowder_lore=True if blackpowder else None,
        has_blackpowder_kit=True if blackpowder else None)
    values.update(changes)
    return GeneratedRangedFacts(**values)


def npc(weapon=GeneratedWeapon.PISTOL, **changes):
    values=dict(weapon_skill=2,strength=3,toughness=4,agility=3,melee=4,athletics=3,
        weapon=weapon,light_armour=False,defence=5,shield=False,
        ranged=ranged_facts(weapon) if weapon in GENERATED_RANGED_WEAPONS else None)
    values.update(changes)
    values['armour'] = light_loadout(light=values.pop('light_armour'), shield=values.pop('shield'))
    values['weapons'] = initial_generated_weapons(values.pop('weapon'), values.pop('weapon_grip', None))
    return GeneratedNpc(**values)


def space(**changes):
    values=dict(weapon_skill=(2,),strength=(3,),toughness=(4,),agility=(3,),melee=(4,),
        athletics=(3,),defence=(5,),brawn=(4,),weapon=(GeneratedWeapon.STAFF,GeneratedWeapon.PISTOL,
            GeneratedWeapon.REPEATER_PISTOL,GeneratedWeapon.REPEATER_HANDBOW),
        armour=(None,BodyArmour.LIGHT),shield=(None,ShieldKind.SHIELD),abilities=((),),allowed_talents=(),
        ballistic_skill=(1,4),shooting=(2,5),initiative=(2,5),dexterity=(3,6))
    values.update(changes)
    return NpcSearchSpace(weapon_count=(1,), **values)


class GeneratedRangedFactsTests(unittest.TestCase):
    def test_three_weapon_profiles_derive_from_components_without_actor_identity(self):
        for weapon in (GeneratedWeapon.PISTOL,GeneratedWeapon.REPEATER_PISTOL,GeneratedWeapon.REPEATER_HANDBOW):
            with self.subTest(weapon=weapon):
                source=npc(weapon,abilities=(GeneratedAbility.DRAINED_ON_HIT,))
                first,other=source.participant('one'),source.participant('renamed')
                attack=first.definition.attacks[0]
                self.assertEqual(attack,other.definition.attacks[0])
                self.assertIs(attack.skill,Skill.SHOOTING)
                self.assertEqual(attack.test_profile,InlineProfile(4,5))
                self.assertEqual((attack.range_min,attack.range_max),
                    (RangedWeaponRange.CLOSE,RangedWeaponRange.SHORT))
                self.assertEqual(attack.damage.base,4 if weapon is GeneratedWeapon.REPEATER_HANDBOW else 5)
                self.assertIs(attack.ignores_armour,weapon is not GeneratedWeapon.REPEATER_HANDBOW)
                self.assertEqual(len(attack.secondary_effects),1)
                self.assertEqual([p.skill for p in first.definition.protection],
                    [Skill.DEFENCE,Skill.ATHLETICS])
                self.assertEqual(first.definition.generated_components,source)
                validate_generated_definition(first.definition)

    def test_complete_facts_are_required_only_for_ranged_and_shield_is_not_discarded(self):
        for weapon in (GeneratedWeapon.PISTOL,GeneratedWeapon.REPEATER_PISTOL,GeneratedWeapon.REPEATER_HANDBOW):
            with self.subTest(weapon=weapon):
                for changes in (dict(ranged=None),dict(ranged={})):
                    with self.assertRaises((TypeError,ValueError)):
                        npc(weapon,**changes)
                shielded = npc(weapon,shield=True)
                self.assertIs(shielded.armour.shield,ShieldKind.SHIELD)
                self.assertTrue(shielded.participant('shielded-shooter').state.holds_shield)
        self.assertIsNone(npc(GeneratedWeapon.SWORD,shield=True).ranged)
        with self.assertRaises(ValueError):
            npc(GeneratedWeapon.SWORD,ranged=ranged_facts())

    def test_strict_characteristics_skills_and_confirmation_types(self):
        for name,values in {'ballistic_skill':(True,0,-1,2.0),
                'initiative':(False,0,2.0),'shooting':(True,1,7,4.0),
                'dexterity':(False,1,7,4.0),
                'ammunition_supply_confirmed':(1,False,None),
                'has_blackpowder_lore':(1,'true'),'has_blackpowder_kit':(1,'true')}.items():
            for value in values:
                with self.subTest(name=name,value=value),self.assertRaises((TypeError,ValueError)):
                    ranged_facts(**{name:value})

    def test_firearm_access_is_explicit_and_handbow_has_no_invented_lore_or_kit(self):
        for field in ('has_blackpowder_lore','has_blackpowder_kit'):
            for value in (None,False):
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    npc(ranged=ranged_facts(**{field:value}))
            for value in (True,False):
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    npc(GeneratedWeapon.REPEATER_HANDBOW,
                        ranged=ranged_facts(GeneratedWeapon.REPEATER_HANDBOW,**{field:value}))

    def test_readmission_rejects_forged_facts_and_derived_attack(self):
        source=npc()
        forged=deepcopy(source)
        object.__setattr__(forged.ranged,'has_blackpowder_lore',False)
        with self.assertRaises(ValueError):
            forged.participant('forged')
        definition=source.participant('original').definition
        for changed in (replace(definition.attacks[0],test_profile=InlineProfile(3,5)),
                replace(definition.attacks[0],ignores_armour=False)):
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                replace(definition,attacks=(changed,*definition.attacks[1:]))


class GeneratedRangedSearchTests(unittest.TestCase):
    def test_sampling_has_both_weapon_families_and_uses_only_admitted_ranges(self):
        source=space()
        proposals=[source.sample(Random(seed)) for seed in range(80)]
        self.assertEqual({p.weapon for p in proposals},set(source.weapon))
        self.assertTrue(any(p.shield for p in proposals))
        self.assertTrue(all(source.contains(p) for p in proposals))
        for proposal in proposals:
            if proposal.ranged is not None:
                self.assertEqual(proposal.participant('source-mirror').state.holds_shield,proposal.shield)
                for name in source._ranged_names():
                    self.assertIn(getattr(proposal.ranged,name),getattr(source,name))
            else:
                self.assertIs(proposal.weapon,GeneratedWeapon.STAFF)

    def test_unreachable_weapon_or_shield_choices_are_rejected_not_repaired(self):
        for changes in (dict(weapon=(GeneratedWeapon.HANDGUN,),shield=(ShieldKind.SHIELD,)),
                dict(weapon=(GeneratedWeapon.HANDGUN,),shield=(None,ShieldKind.SHIELD)),
                dict(weapon=(GeneratedWeapon.HANDGUN,GeneratedWeapon.STAFF),shield=(ShieldKind.SHIELD,))):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                space(**changes)
        self.assertIs(space(weapon=(GeneratedWeapon.PISTOL,),shield=(None,))
            .sample(Random(1)).weapon,GeneratedWeapon.PISTOL)

    def test_mutation_preserves_constraints_and_reaches_new_ranged_numbers(self):
        source=space()
        current=source.sample(Random(1))
        rng=Random(42)
        proposals=[]
        for _ in range(120):
            current=source.mutate(current,rng)
            proposals.append(current)
        self.assertTrue(all(source.contains(p) for p in proposals))
        self.assertGreater(len({p.weapon for p in proposals}),1)
        self.assertGreater(len({p.ranged for p in proposals if p.ranged is not None}),1)
        self.assertTrue(all(p.participant('source-mirror').state.holds_shield == p.shield for p in proposals))

    def test_melee_only_space_does_not_mutate_inactive_ranged_dimensions(self):
        source=space(weapon=(GeneratedWeapon.STAFF,),shield=(None,),armour=(None,))
        initial=source.sample(Random(2))
        self.assertEqual(source.mutate(initial,Random(3)),initial)
        self.assertIsNone(initial.ranged)

    def test_retained_talent_requirement_and_complete_source_are_not_repaired(self):
        source=space(strength=(3,4),allowed_talents=(TalentId.WILD_ATTACK,))
        initial=replace(source.sample(Random(2)),strength=4,talents=(paid_talent(TalentId.WILD_ATTACK),))
        rng=Random(24)
        for _ in range(60):
            initial=source.mutate(initial,rng)
            self.assertTrue(source.contains(initial))
            if TalentId.WILD_ATTACK in initial.talents:
                self.assertGreaterEqual(initial.strength,4)
        forged=deepcopy(npc())
        object.__setattr__(forged.ranged,'shooting',True)
        self.assertFalse(source.contains(forged))
        with self.assertRaises(ValueError):
            source.mutate(forged,Random(1))

    def test_automatic_ranges_do_not_invent_pc_bs_or_initiative(self):
        party=automatic_source().party
        source=automatic_npc_search_space(party)
        self.assertEqual(source.ballistic_skill,(2,3,4))
        self.assertEqual(source.initiative,(2,3,4))
        self.assertEqual(source.shooting,(3,4,5))
        self.assertEqual(source.dexterity,(3,4,5))
        self.assertTrue({GeneratedWeapon.PISTOL,GeneratedWeapon.REPEATER_PISTOL,GeneratedWeapon.REPEATER_HANDBOW}<=set(source.weapon))


if __name__=='__main__':
    unittest.main()
