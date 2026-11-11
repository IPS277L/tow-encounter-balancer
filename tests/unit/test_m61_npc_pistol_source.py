"""GM98/103: complete firearm loadouts, derived Reload and fresh scene facts."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from enum import Enum
import pickle
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileInjuryState, ProfileNpcType, ProfileStateChangeRequest
from towr.domain.pc_melee_models import PcMeleeScenario, validate_pc_melee_scenario_admission
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, create_pc_book_npc, get_pc_book_npc_entry, validate_pc_book_npc_definition,
)
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.pc_npc_pistol_source_models import (
    PC_NPC_PISTOL_DEFINITION_IDS, PcNpcPistolPolicy, PcNpcPistolReloadHandPolicy,
    pc_npc_pistol_profile,
)
from towr.domain.pc_npc_wound_models import official_profile_wound_state
from towr.domain.ranged_weapon_profiles import (
    RANGED_WEAPON_COMBAT_PROFILES, RANGED_WEAPON_RELOAD_PROFILES, RangedWeaponHands,
    RangedWeaponId, RangedWeaponRange, ranged_weapon_combat_profile, ranged_weapon_reload_profile,
)
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill


OFFICIAL = PcBookNpcProfile.EMPIRE_OFFICIAL_PISTOL
OGRE = PcBookNpcProfile.IMPERIAL_OGRE_PISTOL


def policy(actor):
    return PcNpcPistolPolicy(actor,True,True,True,True,
        PcNpcPistolReloadHandPolicy.TWO_AVAILABLE_HANDS)


def scenario(profiles=(OFFICIAL,OGRE)):
    source = make_pc_melee_scenario(enemy_count=len(profiles))
    enemies = tuple(create_pc_book_npc(profile,old.state.actor_id)
        for profile,old in zip(profiles,source.enemies))
    return replace(source,enemies=enemies,npc_pistol_policies=tuple(policy(e.state.actor_id)
        for e in enemies if e.definition.id in PC_NPC_PISTOL_DEFINITION_IDS))


class NpcPistolSourceTests(unittest.TestCase):
    def test_canonical_printed_attack_protection_reload_and_carry(self):
        for profile,page,dice,rating,maximum,toughness,bonus,wounds,dexterity,strength,weapon in (
                (OFFICIAL,98,2,3,RangedWeaponRange.SHORT,3,0,2,InlineProfile(3,3),3,RangedWeaponId.PISTOL),
                (OGRE,103,3,2,RangedWeaponRange.MEDIUM,5,1,3,InlineProfile(2,2),5,RangedWeaponId.OGRE_PISTOL)):
            with self.subTest(profile=profile):
                npc = create_pc_book_npc(profile,'shooter')
                entry = get_pc_book_npc_entry(profile)
                definition = npc.definition
                self.assertEqual(entry.page,page)
                self.assertEqual(definition.id,'pc-book-npc:'+profile.value)
                self.assertIs(definition.injury_policy,TargetInjuryPolicy.BRUTE)
                self.assertEqual(definition.wound_limit,wounds)
                self.assertEqual((definition.resilience.toughness,definition.resilience.bonus),(toughness,bonus))
                attack, = definition.attacks
                self.assertIs(attack.skill,Skill.SHOOTING)
                self.assertEqual(attack.test_profile,InlineProfile(dice,rating))
                self.assertEqual(attack.test_profile.maximum_dice,2*dice)
                self.assertEqual((attack.range_min,attack.range_max),(RangedWeaponRange.CLOSE,maximum))
                self.assertIs(attack.hands,RangedWeaponHands.ONE_HANDED)
                self.assertTrue(attack.ignores_armour)
                self.assertEqual(attack.damage.base,5)
                protection, = definition.protection
                self.assertEqual((protection.skill,protection.test_profile),(Skill.ATHLETICS,InlineProfile(3,3)))
                derived = pc_npc_pistol_profile(definition)
                self.assertEqual((derived.weapon_id,derived.dexterity_profile,derived.strength),(weapon,dexterity,strength))
                self.assertEqual(derived.dexterity_profile.maximum_dice,2*dexterity.dice)
                self.assertTrue(npc.state.wields_weapon)
                self.assertFalse(npc.state.holds_shield)
                self.assertEqual(npc.state.available_attack_ids,(attack.id,))
                self.assertEqual(pickle.loads(pickle.dumps(derived)),derived)
                self.assertEqual(pickle.loads(pickle.dumps(policy('shooter'))),policy('shooter'))
                with self.assertRaises(FrozenInstanceError):
                    derived.strength = 9

    def test_gm_ogre_weapon_preserves_thirteen_player_weapon_rows(self):
        for catalog in (RANGED_WEAPON_COMBAT_PROFILES,RANGED_WEAPON_RELOAD_PROFILES):
            self.assertEqual(len(catalog),14)
            self.assertEqual(len(tuple(p for p in catalog if p.weapon_id is not RangedWeaponId.OGRE_PISTOL)),13)
        pistol = ranged_weapon_combat_profile(RangedWeaponId.PISTOL)
        ogre = ranged_weapon_combat_profile(RangedWeaponId.OGRE_PISTOL)
        self.assertIs(pistol.optimum_range_max,RangedWeaponRange.SHORT)
        self.assertIs(ogre.optimum_range_max,RangedWeaponRange.MEDIUM)
        self.assertEqual(ogre.damage_value,5)
        self.assertIs(ogre.maximum_range,RangedWeaponRange.LONG)
        self.assertTrue(ogre.ignores_armour)
        self.assertTrue(ogre.requires_blackpowder_lore)
        self.assertEqual(ranged_weapon_reload_profile(RangedWeaponId.OGRE_PISTOL).required_successes,3)

    def test_metadata_keeps_unselected_attacks_abilities_and_wound_bands(self):
        official = get_pc_book_npc_entry(OFFICIAL)
        self.assertEqual(official.unselected_attack_names,('Dagger',))
        self.assertEqual(tuple(a.name for a in official.inactive_abilities),('Heard It All Before',))
        self.assertEqual(tuple(b.effect for b in official.wound_bands),('No effect','Broken','Defeated'))
        ogre = get_pc_book_npc_entry(OGRE)
        self.assertEqual(ogre.unselected_attack_names,('Greathammer','Rough Shove'))
        self.assertEqual(tuple(a.name for a in ogre.inactive_abilities),('Ogre Charge','Fearsome','Mighty Throw'))
        self.assertEqual(tuple(b.effect for b in ogre.wound_bands),
            ('Fast Speed','Speed reduced to Normal','Speed reduced to Normal','Defeated'))
        for profile in (OFFICIAL,OGRE):
            first = create_pc_book_npc(profile,'one')
            second = create_pc_book_npc(profile,'two')
            self.assertIsNot(first.definition,second.definition)
            self.assertIsNot(first.definition.attacks[0],second.definition.attacks[0])

    def test_default_empty_keyword_policy_preserves_existing_source(self):
        field = next(item for item in fields(PcMeleeScenario) if item.name=='npc_pistol_policies')
        self.assertTrue(field.kw_only)
        self.assertEqual(field.default,())
        old = make_pc_melee_scenario()
        self.assertEqual(old.npc_pistol_policies,())
        validate_pc_melee_scenario_admission(old)
        source = scenario()
        validate_pc_melee_scenario_admission(source)
        self.assertEqual(tuple(e.definition.id for e in source.enemies),PC_NPC_PISTOL_DEFINITION_IDS)

    def test_policies_require_exact_true_facts_and_hand_enum(self):
        class Alias(str,Enum):
            HANDS='two_available_hands'
        complete = policy('npc')
        for name in ('initially_loaded','has_blackpowder_lore','has_blackpowder_kit','ammunition_supply_confirmed'):
            for value in (False,1,'true',None):
                with self.subTest(name=name,value=value),self.assertRaises((TypeError,ValueError)):
                    replace(complete,**{name:value})
        for value in ('two_available_hands',Alias.HANDS,True,None):
            with self.subTest(value=value),self.assertRaises(TypeError):
                replace(complete,reload_hand_policy=value)
        for value in ('',None,1):
            with self.assertRaises(TypeError):
                replace(complete,actor_id=value)

    def test_policies_are_complete_ordered_unique_and_exclusive_to_real_shooters(self):
        source = scenario()
        invalid = ((),source.npc_pistol_policies[:1],source.npc_pistol_policies[::-1],
            source.npc_pistol_policies*2,(*source.npc_pistol_policies,policy('pc')),
            tuple(replace(p,actor_id='other') for p in source.npc_pistol_policies),
            list(source.npc_pistol_policies))
        for policies in invalid:
            with self.subTest(policies=policies),self.assertRaises((TypeError,ValueError)):
                replace(source,npc_pistol_policies=policies)
        with self.assertRaises(ValueError):
            replace(make_pc_melee_scenario(),npc_pistol_policies=(policy('minion1'),))
        with self.assertRaises(ValueError):
            pc_npc_pistol_profile(create_pc_book_npc(PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER,'npc').definition)

    def test_arbitrary_shooting_numeric_copies_source_aliases_and_mutations_rejected(self):
        source = scenario((OGRE,))
        enemy = source.enemies[0]
        original = enemy.definition
        attack = original.attacks[0]
        changed = (replace(original,attacks=(replace(attack,test_profile=InlineProfile(3,3)),)),
            replace(original,attacks=(replace(attack,test_profile=InlineProfile(3,2,6)),)),
            replace(original,attacks=(replace(attack,range_max=RangedWeaponRange.SHORT),)),
            replace(original,attacks=(replace(attack,ignores_armour=False),)),
            replace(original,attacks=(replace(attack,hands=RangedWeaponHands.TWO_HANDED),)),
            replace(original,id='authored:ogre-copy'),
            replace(original,source_rule_id='authored:ogre-source'),
            replace(original,attacks=(replace(attack,source_rule_id='authored:pistol'),)))
        for definition in changed:
            with self.subTest(definition=definition),self.assertRaises((TypeError,ValueError)):
                pc_npc_pistol_profile(definition)
        authored = make_pc_melee_scenario().enemies[0]
        forged = replace(authored.definition,attacks=(replace(authored.definition.attacks[0],
            skill=Skill.SHOOTING,ignores_armour=True,range_max=RangedWeaponRange.SHORT),))
        with self.assertRaises(ValueError):
            replace(make_pc_melee_scenario(),enemies=(replace(authored,definition=forged),))
        for path in ('skill','pool_cap','ignores_armour'):
            definition = deepcopy(original)
            nested = definition.attacks[0]
            object.__setattr__(nested.test_profile if path=='pool_cap' else nested,path,
                'shooting' if path=='skill' else True if path=='pool_cap' else 1)
            with self.subTest(path=path),self.assertRaises((TypeError,ValueError)):
                pc_npc_pistol_profile(definition)
        validate_pc_book_npc_definition(original)

    def test_fresh_armed_no_shield_and_help_beneficiary_guards(self):
        source = scenario((OFFICIAL,))
        enemy = source.enemies[0]
        for state in (replace(enemy.state,holds_shield=True),replace(enemy.state,wields_weapon=False),
                replace(enemy.state,injury=replace(enemy.state.injury,wounds=1)),
                replace(enemy.state,available_attack_ids=())):
            with self.subTest(state=state),self.assertRaises(ValueError):
                replace(source,enemies=(replace(enemy,state=state),))
        mixed = scenario((PcBookNpcProfile.EMPIRE_PEASANT,OFFICIAL))
        with self.assertRaises(ValueError):
            replace(mixed,npc_help_policies=(PcNpcHelpPolicy('minion1','minion2'),))

    def test_official_first_wound_broken_uses_the_new_canonical_definition(self):
        definition = create_pc_book_npc(OFFICIAL,'official').definition
        change = ProfileStateChangeRequest(ProfileNpcType.BRUTE,0,1,False)
        actual = official_profile_wound_state(definition,ProfileInjuryState(1,2),change)
        self.assertTrue(actual.conditions.has(Condition.BROKEN))
        self.assertEqual(actual.wounds,1)
        unchanged = official_profile_wound_state(definition,actual,
            ProfileStateChangeRequest(ProfileNpcType.BRUTE,1,2,True))
        self.assertIs(unchanged,actual)


if __name__ == '__main__':
    unittest.main()
