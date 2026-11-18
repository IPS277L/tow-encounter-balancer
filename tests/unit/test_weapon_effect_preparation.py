"""Scalar Traits retain committed item sources without executing Abilities."""
from dataclasses import replace
import unittest

from towr.domain.attack_models import DamageImpactSpec,DamageModifier,ResilienceProfile,effective_damage_modifiers
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.test_models import DiceModifier,Skill
from towr.domain.weapon_catalog import WeaponKind,weapon_profile
from towr.domain.weapon_inventory_models import (
    WeaponGrip,WeaponItemLocation,WeaponItemSource,initial_weapon_inventory,weapon_reload_target,
)
from towr.domain.weapon_use_models import WeaponUse,WeaponProtectionUse
from towr.domain.weapon_effect_preparation import (
    weapon_kind_test_modifiers,weapon_kind_target_test_modifiers,weapon_kind_damage_modifiers,
    weapon_test_modifiers,weapon_damage_preparation,WeaponDiceContribution,WeaponDamageContribution,
    _aggregate_damage,SWORD_DEFENCE_RULE_ID,AXE_ARMOUR_RULE_ID,FRACASSE_STAGGERED_RULE_ID,
    WARHAMMER_STAGGERED_RULE_ID,SHORT_RANGE_SHOOTING_BONUS_RULE_ID,
)


W=WeaponKind
READY=ConditionState()
STAGGERED=ConditionState(frozenset((Condition.STAGGERED,)))
ARMOURED=ResilienceProfile(3,3)


def source_item(kind,index,location,grip):
    return WeaponItemSource('item:'+str(index),kind,location,grip,
        initially_loaded=True if weapon_reload_target(kind) is not None else None,
        gm_fit_confirmed=True if kind is W.OGRE_PISTOL else None)


def attack_use(*kinds,primary_index=0,grip=None,carried=(),actor='actor'):
    if kinds==(W.UNARMED,):
        return WeaponUse(actor,initial_weapon_inventory('initial:owner',()),None,usable_hands=())
    sources=[]
    for index,kind in enumerate(kinds):
        actual=(grip if grip is not None else WeaponGrip.BOTH
            if weapon_profile(kind).hands is RangedWeaponHands.TWO_HANDED else
            WeaponGrip.LEFT if index==0 else WeaponGrip.RIGHT)
        sources.append(source_item(kind,index,WeaponItemLocation.HELD,actual))
    for index,kind in enumerate(carried,start=len(sources)):
        sources.append(source_item(kind,index,WeaponItemLocation.CARRIED,None))
    inventory=initial_weapon_inventory('initial:owner',tuple(sources))
    return WeaponUse(actor,inventory,inventory.items[primary_index].id,
        tuple(item.id for index,item in enumerate(inventory.items[:len(kinds)]) if index!=primary_index))


class WeaponScalarPreparationTests(unittest.TestCase):
    def test_all_fifty_primary_damage_rows_preserve_printed_sources(self):
        # Independent printed expectations at Strength4; no bonus Trait is
        # folded into these values other than the actual variable grip below.
        expected={W.UNARMED:None,W.KNUCKLEDUSTERS:3,W.DAGGER:3,W.STAFF:4,W.FOOT_SPEAR:4,
            W.CAVALRY_SPEAR:4,W.AXE:4,W.PICKAXE:5,W.SWORD:4,W.WARHAMMER:4,W.MORNING_STAR:5,
            W.POLEARM:4,W.FLAIL:7,W.BILLHOOK:6,W.HALBERD:6,W.GLAIVE:6,W.GREATAXE:7,
            W.GREATSWORD:7,W.GREATHAMMER:7,W.LANCE:5,W.SLING:4,W.SHORTBOW:3,W.WARBOW:3,
            W.LONGBOW:4,W.CROSSBOW:4,W.PISTOL:5,W.HANDGUN:5,W.BLUNDERBUSS:4,
            W.HOCHLAND_LONG_RIFLE:6,W.REPEATER_HANDBOW:4,W.REPEATER_CROSSBOW:4,
            W.REPEATER_PISTOL:5,W.REPEATER_HANDGUN:5,W.ROCK:None,W.THROWING_SPEAR:4,
            W.THROWING_AXE:5,W.WEIGHTED_NET:None,W.THROWING_KNIVES:4,W.OIL_FLASK:None,
            W.BLASTING_CHARGE:None,W.DRAGON_BOW:6,W.DUELLIST_BLADES:6,W.GROTARGGS_HAMMER:7,
            W.HEADSMANS_AXE:7,W.MORNING_STAR_OF_FRACASSE:7,W.SCARAB_KNIFE:5,
            W.TRICKSTER_BLADE:5,W.UNWAVERING_SPEAR:5,W.SWORD_OF_JUSTICE:5,W.OGRE_PISTOL:5}
        self.assertEqual(set(expected),set(W))
        self.assertEqual(len(expected),50)
        for kind,amount in expected.items():
            with self.subTest(kind=kind):
                use=attack_use(kind)
                prepared=weapon_damage_preparation(use,4,ARMOURED)
                self.assertEqual(None if prepared.damage is None else prepared.damage.base,amount)
                self.assertIs(prepared.use,use)
                self.assertIs(prepared.magical_source,weapon_profile(kind).magical)
                self.assertEqual(prepared.use.inventory,use.inventory)

    def test_two_handed_variable_grip_adds_its_damage_exactly_once(self):
        for kind,expected in ((W.FOOT_SPEAR,5),(W.POLEARM,6)):
            with self.subTest(kind=kind):
                result=weapon_damage_preparation(attack_use(kind,grip=WeaponGrip.BOTH),4,ARMOURED)
                self.assertEqual(result.damage.base,expected)
                self.assertEqual(result.modifiers,())

    def test_two_swords_stack_defence_and_retain_both_item_sources(self):
        attack=attack_use(W.SWORD,W.SWORD)
        defence=WeaponProtectionUse('actor',attack.inventory,Skill.DEFENCE,attack.item_ids)
        result=weapon_test_modifiers(defence,READY)
        self.assertEqual(result.modifiers,(DiceModifier(SWORD_DEFENCE_RULE_ID,2),))
        self.assertEqual(tuple(source.item_id for source in result.contributions),attack.item_ids)
        self.assertEqual(tuple(source.modifier.amount for source in result.contributions),(1,1))
        self.assertEqual(weapon_test_modifiers(defence,STAGGERED).modifiers,())
        with self.assertRaises(ValueError):
            replace(result,contributions=result.contributions[:1])
        with self.assertRaises(ValueError):
            replace(result,contributions=tuple(replace(item,item_id='unselected') for item in result.contributions))

    def test_primary_alone_sets_damage_skill_and_magical_origin(self):
        use=attack_use(W.KNUCKLEDUSTERS,W.SCARAB_KNIFE)
        first=weapon_damage_preparation(use,4,ARMOURED)
        second=weapon_damage_preparation(replace(use,primary_item_id=use.contributor_item_ids[0],
            contributor_item_ids=(use.primary_item_id,)),4,ARMOURED)
        self.assertEqual((use.skill,first.damage.base,first.magical_source),(Skill.BRAWN,3,False))
        self.assertEqual((second.use.skill,second.damage.base,second.magical_source),(Skill.MELEE,5,True))

    def test_contributor_penalty_is_mandatory_even_when_it_is_not_the_primary(self):
        use=attack_use(W.WARHAMMER,W.MORNING_STAR_OF_FRACASSE)
        drained=ConditionState(frozenset((Condition.STAGGERED,Condition.DRAINED)))
        result=weapon_test_modifiers(use,drained,target_conditions=STAGGERED)
        self.assertEqual(result.modifiers,(DiceModifier(WARHAMMER_STAGGERED_RULE_ID,1),
            DiceModifier(FRACASSE_STAGGERED_RULE_ID,-1)))
        self.assertEqual(tuple(row.item_id for row in result.contributions),use.item_ids)
        self.assertEqual(weapon_test_modifiers(use,drained).modifiers,
            (DiceModifier(FRACASSE_STAGGERED_RULE_ID,-1),))

    def test_each_mandatory_melee_penalty_survives_own_test_preparation(self):
        for kind,conditions,amount in ((W.MORNING_STAR,STAGGERED,-1),
                (W.MORNING_STAR_OF_FRACASSE,STAGGERED,-1),(W.FLAIL,STAGGERED,-2),
                (W.GREATAXE,READY,-1),(W.GREATSWORD,READY,-1),(W.GREATHAMMER,READY,-1)):
            with self.subTest(kind=kind):
                result=weapon_test_modifiers(attack_use(kind),conditions)
                self.assertEqual(sum(item.amount for item in result.modifiers),amount)
                self.assertEqual(weapon_kind_test_modifiers(kind,Skill.BRAWN,conditions),())
        use=attack_use(W.MORNING_STAR_OF_FRACASSE,W.MORNING_STAR_OF_FRACASSE)
        result=weapon_test_modifiers(use,STAGGERED)
        self.assertEqual(result.modifiers,(DiceModifier(FRACASSE_STAGGERED_RULE_ID,-2),))
        self.assertEqual(tuple(row.item_id for row in result.contributions),use.item_ids)

    def test_help_without_target_never_gains_target_traits(self):
        for kind in (W.WARHAMMER,W.BILLHOOK,W.GREATHAMMER):
            with self.subTest(kind=kind):
                own=weapon_kind_test_modifiers(kind,Skill.MELEE,READY,target_mounted=True)
                target=weapon_kind_target_test_modifiers(kind,Skill.MELEE,None,target_mounted=True)
                self.assertEqual(target,())
                self.assertEqual(sum(modifier.amount for modifier in own),-1 if kind is W.GREATHAMMER else 0)
                self.assertEqual(weapon_kind_target_test_modifiers(kind,Skill.BRAWN,STAGGERED,
                    target_mounted=True),())

    def test_carried_and_unselected_items_never_contribute_traits(self):
        use=attack_use(W.SCARAB_KNIFE,W.AXE,carried=(W.GREATAXE,))
        single=replace(use,contributor_item_ids=())
        result=weapon_damage_preparation(single,4,ARMOURED)
        self.assertEqual(result.modifiers,())
        self.assertEqual(result.damage.base,5)
        self.assertEqual(len(result.use.inventory.items),3)

    def test_duplicate_axe_rule_is_aggregated_without_losing_item_witnesses(self):
        use=attack_use(W.AXE,W.AXE)
        result=weapon_damage_preparation(use,4,ARMOURED)
        self.assertEqual(result.damage.base,4)
        self.assertEqual(result.modifiers,(DamageModifier(AXE_ARMOUR_RULE_ID,2,armour_specific=True),))
        self.assertEqual(tuple(source.item_id for source in result.contributions),use.item_ids)
        with self.assertRaises(ValueError):
            replace(result,contributions=result.contributions*2)

    def test_magic_primary_does_not_enchant_the_mundane_armour_contributor(self):
        use=attack_use(W.SCARAB_KNIFE,W.AXE)
        resilience=replace(ARMOURED,mundane_armour_ward=True)
        result=weapon_damage_preparation(use,4,resilience)
        self.assertTrue(result.magical_source)
        self.assertEqual(result.modifiers,(DamageModifier(AXE_ARMOUR_RULE_ID,1,armour_specific=True),))
        self.assertEqual(result.contributions[0].item_id,use.contributor_item_ids[0])
        impact=DamageImpactSpec(result.damage,resilience,damage_modifiers=result.modifiers,
            magical_source=result.magical_source)
        self.assertEqual(effective_damage_modifiers(impact),())
        self.assertEqual(result.modifiers,impact.damage_modifiers)

    def test_damage_aggregation_keeps_distinct_origins_and_armour_metadata(self):
        # Pure aggregation boundary for future explicit magical bonuses: it
        # never claims these arbitrary contributions are a prepared item use.
        contributions=(WeaponDamageContribution('one',DamageModifier('same',1,armour_specific=True)),
            WeaponDamageContribution('two',DamageModifier('same',2,armour_specific=True,magical_source=True)),
            WeaponDamageContribution('three',DamageModifier('same',3)))
        self.assertEqual(_aggregate_damage(contributions),tuple(item.modifier for item in contributions))

    def test_ready_defence_traits_use_their_own_magic_and_mundane_rule_sources(self):
        for kind,amount in ((W.SWORD,1),(W.GLAIVE,1),(W.GREATSWORD,1),(W.DUELLIST_BLADES,2),(W.TRICKSTER_BLADE,1)):
            with self.subTest(kind=kind):
                attack=attack_use(kind)
                use=WeaponProtectionUse('actor',attack.inventory,Skill.DEFENCE,attack.item_ids)
                result=weapon_test_modifiers(use,READY)
                self.assertEqual(sum(item.amount for item in result.modifiers),amount)
                self.assertEqual(weapon_test_modifiers(use,STAGGERED).modifiers,())

    def test_mounted_charge_and_opposed_charge_are_separate_actual_contexts(self):
        for kind in (W.CAVALRY_SPEAR,W.LANCE):
            for mounted in (False,True):
                for charging in (False,True):
                    with self.subTest(kind=kind,mounted=mounted,charging=charging):
                        result=weapon_test_modifiers(attack_use(kind),READY,actor_mounted=mounted,charging=charging)
                        self.assertEqual(sum(item.amount for item in result.modifiers),int(mounted and charging))
                        damage=weapon_damage_preparation(attack_use(kind),4,ARMOURED,
                            actor_mounted=mounted,charging=charging)
                        self.assertEqual(sum(item.amount for item in damage.modifiers),
                            int(kind is W.LANCE and mounted and charging))
        spear=attack_use(W.FOOT_SPEAR)
        protection=WeaponProtectionUse('actor',spear.inventory,Skill.DEFENCE,spear.item_ids)
        self.assertEqual(weapon_test_modifiers(protection,READY).modifiers,())
        self.assertEqual(sum(item.amount for item in weapon_test_modifiers(protection,READY,
            against_charge=True).modifiers),1)

    def test_armour_modifiers_follow_actual_armoured_flag_without_applying_ward(self):
        for kind in (W.AXE,W.THROWING_AXE,W.HALBERD,W.GREATAXE,W.CROSSBOW):
            with self.subTest(kind=kind):
                modifiers=weapon_kind_damage_modifiers(kind,replace(ARMOURED,mundane_armour_ward=True))
                self.assertEqual(len(modifiers),1)
                self.assertTrue(modifiers[0].armour_specific)
                self.assertFalse(modifiers[0].magical_source)
                self.assertEqual(weapon_kind_damage_modifiers(kind,replace(ARMOURED,armoured=False)),())

    def test_short_range_shooting_is_exact_and_does_not_consume_repeater_bonus(self):
        for kind,amount in ((W.SHORTBOW,1),(W.BLUNDERBUSS,2),(W.REPEATER_PISTOL,0)):
            with self.subTest(kind=kind):
                use=attack_use(kind)
                result=weapon_test_modifiers(use,READY,target_range=RangedWeaponRange.SHORT)
                self.assertEqual(result.modifiers,() if not amount else
                    (DiceModifier(SHORT_RANGE_SHOOTING_BONUS_RULE_ID,amount),))
                self.assertEqual(weapon_test_modifiers(use,READY,target_range=RangedWeaponRange.MEDIUM).modifiers,())
                self.assertEqual(result.use.inventory,use.inventory)

    def test_utility_traits_require_the_exact_selected_item_and_context(self):
        for kind,skill,context in ((W.DAGGER,Skill.STEALTH,'concealing_weapon'),
                (W.KNUCKLEDUSTERS,Skill.STEALTH,'concealing_weapon'),
                (W.STAFF,Skill.ATHLETICS,'crossing_difficult_terrain'),
                (W.PICKAXE,Skill.TOIL,'harvesting_resources')):
            with self.subTest(kind=kind):
                self.assertEqual(weapon_kind_test_modifiers(kind,skill,READY),())
                modifiers=weapon_kind_test_modifiers(kind,skill,READY,**{context:True})
                self.assertEqual(sum(item.amount for item in modifiers),1)
                self.assertEqual(weapon_kind_test_modifiers(kind,Skill.WILLPOWER,READY,**{context:True}),())
                with self.assertRaises(ValueError):
                    weapon_test_modifiers(attack_use(kind),READY,skill=skill,**{context:True})

    def test_typed_source_and_context_reject_loose_values(self):
        for flag in ('against_charge','actor_mounted','charging','target_mounted','concealing_weapon',
                'crossing_difficult_terrain','harvesting_resources'):
            with self.subTest(flag=flag),self.assertRaises(TypeError):
                weapon_test_modifiers(attack_use(W.SWORD),READY,**{flag:1})
        for kind,skill,conditions in (('sword',Skill.MELEE,READY),(W.SWORD,'melee',READY),(W.SWORD,Skill.MELEE,())):
            with self.subTest(kind=kind,skill=skill),self.assertRaises(TypeError):
                weapon_kind_test_modifiers(kind,skill,conditions)
        for strength in (None,True,0):
            with self.subTest(strength=strength),self.assertRaises((TypeError,ValueError)):
                weapon_damage_preparation(attack_use(W.SWORD),strength,ARMOURED)
            with self.subTest(unarmed_strength=strength),self.assertRaises((TypeError,ValueError)):
                weapon_damage_preparation(attack_use(W.UNARMED),strength,ARMOURED)
        with self.assertRaises(TypeError):
            WeaponDiceContribution('item',DamageModifier('wrong',1))
        with self.assertRaises(TypeError):
            WeaponDamageContribution('item',DiceModifier('wrong',1))


if __name__=='__main__':
    unittest.main()
