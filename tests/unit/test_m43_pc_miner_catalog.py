"""Full GM105 Miner loadout and conditional abilities; no inherited PC pickaxe Traits."""
from copy import deepcopy
from dataclasses import replace
import unittest

from towr.domain.attack_models import DamageProfile,ResilienceProfile
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile,create_pc_book_npc,get_pc_book_npc_entry,validate_pc_book_npc_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill


PROFILE=PcBookNpcProfile.DWARF_MINER_PICKAXE
SOURCE='BOOK-GM-GUIDE:1.1:p105:dwarf_miner_pickaxe'


class PcMinerCatalogTests(unittest.TestCase):
    def test_exact_printed_pickaxe_defence_resilience_and_full_source_identity(self):
        entry=get_pc_book_npc_entry(PROFILE)
        definition=entry.definition
        self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page),
            (PROFILE,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',105))
        self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
            definition.wound_limit,definition.resilience),
            ('pc-book-npc:dwarf_miner_pickaxe',SOURCE,TargetInjuryPolicy.MINION,1,ResilienceProfile(4,2)))
        attack,=definition.attacks
        self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,attack.damage,
            attack.range_min,attack.range_max,attack.hands,attack.ignores_armour,attack.secondary_effects),
            ('mining_pickaxe',SOURCE+':mining_pickaxe',Skill.MELEE,InlineProfile(4,3),DamageProfile(4),
             RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,RangedWeaponHands.TWO_HANDED,False,()))
        protection,=definition.protection
        self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
            (SOURCE+':defence',Skill.DEFENCE,InlineProfile(4,3)))
        self.assertEqual((attack.test_profile.maximum_dice,protection.test_profile.maximum_dice),(8,8))
        self.assertIsNone(attack.test_profile.pool_cap)
        self.assertIsNone(protection.test_profile.pool_cap)
        validate_pc_book_npc_definition(definition)

    def test_fresh_armed_heavy_armoured_miner_has_no_shield_or_initial_grudge_condition(self):
        snapshot=create_pc_book_npc(PROFILE,'miner')
        self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
            snapshot.state.wields_weapon,snapshot.state.holds_shield,snapshot.state.current_resilience,
            snapshot.state.available_attack_ids),
            ('miner','pc-book-npc:dwarf_miner_pickaxe',True,False,ResilienceProfile(4,2),('mining_pickaxe',)))
        self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
            snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,1,False,None))
        self.assertFalse(snapshot.state.injury.conditions.conditions)

    def test_grudges_are_explicit_encounter_relationship_with_target_specific_melee_bonus(self):
        entry=get_pc_book_npc_entry(PROFILE)
        grudge,higher=entry.active_abilities
        self.assertEqual(grudge.name,'Grudges to Settle')
        self.assertIn('Encountering an enemy',grudge.scope)
        self.assertIn('known grudge',grudge.scope)
        for detail in ('Distracted focused on that enemy','+1d Melee only when fighting that enemy',
                'explicitly configured','never inferred from ancestry'):
            self.assertIn(detail,grudge.effect)
        self.assertEqual(entry.wound_bands,())

    def test_higher_ground_bonus_denial_is_active_and_underground_terrain_is_separate(self):
        entry=get_pc_book_npc_entry(PROFILE)
        _,higher=entry.active_abilities
        terrain,_=entry.inactive_abilities
        self.assertEqual((higher.name,higher.scope,higher.effect),
            ('Down in the Dark (higher ground)','An enemy attacks the Miner from higher ground',
             'That enemy does not gain bonus dice for attacking from higher ground'))
        self.assertEqual((terrain.name,terrain.scope,terrain.effect),
            ('Down in the Dark (underground terrain)',
             'Movement through underground obstacles that are Difficult Terrain',
             'Ignore Difficult Terrain from underground obstacles'))

    def test_blasting_charge_is_unselected_zone_hazard_and_athletics_is_not_selected_defence(self):
        entry=get_pc_book_npc_entry(PROFILE)
        _,blasting=entry.inactive_abilities
        self.assertEqual((blasting.name,blasting.scope),
            ('Unselected Blasting Charge','A separately selected ranged attack: Short to Medium Range, 3d/3'))
        self.assertEqual(blasting.effect,
            "All creatures in the target Zone suffer Hazard (3) resisted with Endurance; "
            "a failed attack explodes in the Miner's Zone instead")
        self.assertEqual(entry.unselected_attack_names,('Blasting Charge',))
        self.assertEqual(entry.unselected_variant_names,())
        alternate,=entry.unselected_protection
        self.assertEqual((alternate.source_rule_id,alternate.skill,alternate.test_profile),
            (SOURCE+':athletics',Skill.ATHLETICS,InlineProfile(1,3,4)))
        self.assertEqual(alternate.test_profile.maximum_dice,4)
        with self.assertRaises((TypeError,ValueError)):
            validate_pc_book_npc_definition(replace(entry.definition,protection=(alternate,)))

    def test_changed_stats_traits_or_partial_book_identity_cannot_claim_canonical_miner(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        attack,=definition.attacks
        protection,=definition.protection
        alternate,=get_pc_book_npc_entry(PROFILE).unselected_protection
        candidates=(
            replace(definition,attacks=(replace(attack,damage=DamageProfile(5)),)),
            replace(definition,attacks=(replace(attack,hands=RangedWeaponHands.ONE_HANDED),)),
            replace(definition,attacks=(replace(attack,ignores_armour=True),)),
            replace(definition,resilience=ResilienceProfile(4,1)),
            replace(definition,id='authored:root',source_rule_id='authored:source'),
            replace(definition,id='authored:root',source_rule_id='authored:source',
                attacks=(replace(attack,source_rule_id='authored:attack'),)),
            replace(definition,id='authored:root',source_rule_id='authored:source',
                attacks=(replace(attack,source_rule_id='authored:attack'),),
                protection=(replace(protection,source_rule_id=alternate.source_rule_id),)),
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate),self.assertRaises((TypeError,ValueError)):
                validate_pc_book_npc_definition(candidate)

    def test_equal_string_enums_float_dice_and_boolean_multiplier_aliases_are_rejected(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        for target,name,value in (('definition','injury_policy','minion'),('attack','skill','melee'),
                ('attack','hands','2h'),('attack','range_max','close'),('profile','dice',4.0),
                ('damage','success_multiplier',True)):
            forged=deepcopy(definition)
            subject={'definition':forged,'attack':forged.attacks[0],
                'profile':forged.attacks[0].test_profile,'damage':forged.attacks[0].damage}[target]
            object.__setattr__(subject,name,value)
            self.assertEqual(forged,definition)
            with self.subTest(target=target,name=name),self.assertRaises(TypeError):
                validate_pc_book_npc_definition(forged)
        with self.assertRaises(TypeError):
            get_pc_book_npc_entry(PROFILE.value)

    def test_every_definition_injury_and_unused_protection_graph_is_fresh(self):
        first=create_pc_book_npc(PROFILE,'first')
        second=create_pc_book_npc(PROFILE,'second')
        expected=deepcopy(second.definition)
        self.assertIsNot(first.definition,second.definition)
        self.assertIsNot(first.state.injury,second.state.injury)
        object.__setattr__(first.definition.attacks[0].damage,'base',99)
        self.assertEqual(second.definition,expected)
        self.assertEqual(get_pc_book_npc_entry(PROFILE).definition,expected)
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(first.definition)
        entry=get_pc_book_npc_entry(PROFILE)
        object.__setattr__(entry.unselected_protection[0].test_profile,'dice',9)
        self.assertNotEqual(get_pc_book_npc_entry(PROFILE).unselected_protection,entry.unselected_protection)


if __name__=='__main__':
    unittest.main()
