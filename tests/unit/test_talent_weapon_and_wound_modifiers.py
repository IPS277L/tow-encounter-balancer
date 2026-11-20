"""Actual item sources and real character Wounds Table rolls, PG76/79."""
from copy import deepcopy
from dataclasses import replace
import pickle
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import paid_talent
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    CharacterInjuryState, CharacterWoundRequest, CharacterWoundType,
    FixedWoundSelection, ProfileInjuryState, ProfileNpcType, ProfileWoundRequest,
    WoundDiceModifier, WoundEntryId, WoundNegationOption, WoundRecord,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_injury_models import (
    HARDY_RULE_ID, hardy_wound_dice_modifiers, prepare_hardy_wound,
)
from towr.domain.test_models import DiceModifier, Skill, TestProfile, TestRequest
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_effect_preparation import (
    FLAIL_STAGGERED_RULE_ID, GREATAXE_MELEE_RULE_ID, GREATHAMMER_MELEE_RULE_ID,
    GREATHAMMER_STAGGERED_RULE_ID, GREATSWORD_DEFENCE_RULE_ID,
    MORNING_STAR_STAGGERED_RULE_ID, FRACASSE_STAGGERED_RULE_ID,
    SHORT_RANGE_SHOOTING_BONUS_RULE_ID, WARHAMMER_STAGGERED_RULE_ID,
    weapon_test_modifiers,
)
from towr.domain.weapon_inventory_models import (
    WeaponGrip as G, WeaponItemLocation as L, WeaponItemSource,
    initial_weapon_inventory, weapon_reload_target,
)
from towr.domain.weapon_use_models import WeaponUse, WeaponProtectionUse
from towr.rules.injury_resolution import resolve_character_wound
from towr.rules.test_resolution import resolve_test


READY = ConditionState()
STAGGERED = ConditionState(frozenset((Condition.STAGGERED,)))
MIGHTY = (paid_talent(TalentId.MIGHTY_BLOW),)
HARDY = (paid_talent(TalentId.HARDY),)


def held(id, kind, grip):
    return WeaponItemSource(id, kind, L.HELD, grip,
        initially_loaded=True if weapon_reload_target(kind) is not None else None)


def actual_use(*sources):
    inventory = initial_weapon_inventory('physical:owner', sources)
    return WeaponUse('actor', inventory, inventory.items[0].id,
        tuple(item.id for item in inventory.items[1:]))


def old_wound(sequence, *, treated=False):
    return WoundRecord(sequence, WoundEntryId.SUPERFICIAL_INJURY, 1, (1,), treated=treated)


class MightyBlowPreparationTests(unittest.TestCase):
    def test_actual_two_handed_weapon_penalties_are_removed_from_melee_only(self):
        for kind, conditions, rule, amount in (
                (W.GREATAXE, READY, GREATAXE_MELEE_RULE_ID, -1),
                (W.FLAIL, STAGGERED, FLAIL_STAGGERED_RULE_ID, -2),
                (W.GREATHAMMER, READY, GREATHAMMER_MELEE_RULE_ID, -1)):
            with self.subTest(kind=kind):
                use = actual_use(held('weapon', kind, G.BOTH))
                ordinary = weapon_test_modifiers(use, conditions)
                prepared = weapon_test_modifiers(use, conditions, talents=MIGHTY)
                self.assertEqual(ordinary.modifiers, (DiceModifier(rule, amount),))
                self.assertEqual(prepared.modifiers, ())
                self.assertEqual(prepared.contributions, ())
                self.assertIs(prepared.use, use)
                self.assertEqual(prepared.talents, MIGHTY)
                self.assertEqual(prepared.use.inventory, ordinary.use.inventory)
                self.assertEqual(weapon_test_modifiers(use, conditions, talents=HARDY).modifiers,
                    ordinary.modifiers)

    def test_one_handed_and_dual_one_handed_penalties_are_not_cancelled(self):
        use = actual_use(held('star', W.MORNING_STAR, G.LEFT))
        self.assertEqual(weapon_test_modifiers(use, STAGGERED, talents=MIGHTY).modifiers,
            (DiceModifier(MORNING_STAR_STAGGERED_RULE_ID, -1),))
        dual = actual_use(held('hammer', W.WARHAMMER, G.LEFT),
            held('fracasse', W.MORNING_STAR_OF_FRACASSE, G.RIGHT))
        prepared = weapon_test_modifiers(dual, STAGGERED, target_conditions=STAGGERED, talents=MIGHTY)
        self.assertEqual(prepared.modifiers, (DiceModifier(WARHAMMER_STAGGERED_RULE_ID, 1),
            DiceModifier(FRACASSE_STAGGERED_RULE_ID, -1)))
        self.assertEqual(tuple(item.item_id for item in prepared.contributions), dual.item_ids)

    def test_variable_grips_and_positive_defence_traits_keep_their_real_sources(self):
        for kind in (W.FOOT_SPEAR, W.POLEARM):
            for grip in (G.LEFT, G.BOTH):
                with self.subTest(kind=kind, grip=grip):
                    use = actual_use(held('variable', kind, grip))
                    prepared = weapon_test_modifiers(use, READY, talents=MIGHTY)
                    self.assertEqual(prepared.modifiers, ())
                    self.assertIs(prepared.use.primary_grip, grip)
                    self.assertEqual(prepared.use.inventory, use.inventory)
        use = actual_use(held('greatsword', W.GREATSWORD, G.BOTH))
        defence = WeaponProtectionUse('actor', use.inventory, Skill.DEFENCE, use.item_ids)
        self.assertEqual(weapon_test_modifiers(defence, READY, talents=MIGHTY).modifiers,
            (DiceModifier(GREATSWORD_DEFENCE_RULE_ID, 1),))
        self.assertEqual(weapon_test_modifiers(defence, STAGGERED, talents=MIGHTY).modifiers, ())

    def test_melee_protection_gets_the_talent_but_shooting_keeps_its_own_bonuses(self):
        use = actual_use(held('axe', W.GREATAXE, G.BOTH))
        counter = WeaponProtectionUse('actor', use.inventory, Skill.MELEE, use.item_ids)
        self.assertEqual(weapon_test_modifiers(counter, READY).modifiers,
            (DiceModifier(GREATAXE_MELEE_RULE_ID, -1),))
        self.assertEqual(weapon_test_modifiers(counter, READY, talents=MIGHTY).modifiers, ())
        bow = actual_use(held('shortbow', W.SHORTBOW, G.BOTH))
        prepared = weapon_test_modifiers(bow, READY, target_range=RangedWeaponRange.SHORT,
            talents=MIGHTY)
        self.assertIs(prepared.skill, Skill.SHOOTING)
        self.assertEqual(prepared.modifiers, (DiceModifier(SHORT_RANGE_SHOOTING_BONUS_RULE_ID, 1),))

    def test_target_bonus_and_external_wound_and_condition_penalties_are_preserved(self):
        use = actual_use(held('hammer', W.GREATHAMMER, G.BOTH))
        prepared = weapon_test_modifiers(use, STAGGERED, target_conditions=STAGGERED, talents=MIGHTY)
        self.assertEqual(prepared.modifiers, (DiceModifier(GREATHAMMER_STAGGERED_RULE_ID, 1),))
        self.assertEqual(prepared.contributions[0].item_id, use.primary_item_id)
        wound = DiceModifier('external:wound-penalty', -2)
        condition = DiceModifier('external:distracted-penalty', -1)
        request = TestRequest('prepared:external-sources', TestProfile(5, 5),
            dice_modifiers=(wound, *prepared.modifiers, condition))
        rng = ScriptedD10([1, 1, 1])
        result = resolve_test(request, rng)
        rng.assert_exhausted()
        self.assertEqual(result.trace.rolled_dice, 3)
        self.assertEqual(request.dice_modifiers, (wound,
            DiceModifier(GREATHAMMER_STAGGERED_RULE_ID, 1), condition))
        self.assertEqual(prepared.conditions, STAGGERED)

    def test_preparation_rejects_missing_ownership_stale_contributions_and_foreign_items(self):
        use = actual_use(held('axe', W.GREATAXE, G.BOTH))
        ordinary = weapon_test_modifiers(use, READY)
        mighty = weapon_test_modifiers(use, READY, talents=MIGHTY)
        with self.assertRaises(ValueError):
            replace(ordinary, talents=MIGHTY)
        with self.assertRaises(ValueError):
            replace(mighty, talents=())
        use = actual_use(held('hammer', W.GREATHAMMER, G.BOTH))
        positive = weapon_test_modifiers(use, READY, target_conditions=STAGGERED, talents=MIGHTY)
        with self.assertRaises(ValueError):
            replace(positive, contributions=(replace(positive.contributions[0], item_id='foreign:item'),))
        forged = deepcopy(mighty)
        object.__setattr__(forged.talents[0].acquisitions[0], 'phase', 'creation')
        with self.assertRaises(TypeError):
            replace(forged)
        self.assertEqual(pickle.loads(pickle.dumps(mighty)), mighty)


class HardyPreparationTests(unittest.TestCase):
    def test_first_wound_still_rolls_one_die_for_pc_and_champion(self):
        for subject in CharacterWoundType:
            with self.subTest(subject=subject):
                request = CharacterWoundRequest('hardy:first', CharacterInjuryState(), subject)
                prepared = prepare_hardy_wound(request, HARDY)
                self.assertEqual(prepared.dice_modifiers, (WoundDiceModifier(HARDY_RULE_ID, -1),))
                rng = ScriptedD10([2])
                result = resolve_character_wound(prepared, rng)
                rng.assert_exhausted()
                self.assertEqual(result.table_roll.dice, 1)
                self.assertEqual(result.table_roll.values, (2,))
                self.assertIn(HARDY_RULE_ID, result.applied_rule_ids)
                self.assertEqual(request.state.wounds, ())
                self.assertIs(prepared.state, request.state)
                self.assertIs(result.subject_type, subject)

    def test_existing_wounds_base_dice_and_external_weapon_modifier_keep_exact_sources(self):
        state = CharacterInjuryState(wounds=(old_wound(1), old_wound(2), old_wound(3, treated=True)))
        weapon = WoundDiceModifier('external:weapon-wound-die', 1)
        request = CharacterWoundRequest('hardy:later', state, base_dice=3,
            dice_modifiers=(weapon,))
        prepared = prepare_hardy_wound(request, HARDY)
        rng = ScriptedD10([1, 1, 1, 1, 1])
        result = resolve_character_wound(prepared, rng)
        rng.assert_exhausted()
        self.assertEqual(result.table_roll.dice, 5)
        self.assertEqual(result.applied_rule_ids, ('external:weapon-wound-die', HARDY_RULE_ID))
        self.assertEqual(prepared, replace(request,
            dice_modifiers=(weapon, WoundDiceModifier(HARDY_RULE_ID, -1))))
        self.assertEqual(request.dice_modifiers, (weapon,))
        self.assertEqual(len(state.wounds), 3)
        self.assertEqual(len(result.state.wounds), 4)

    def test_request_identity_and_negation_facts_are_preserved_without_runtime_changes(self):
        request = CharacterWoundRequest('hardy:preserve', CharacterInjuryState(),
            CharacterWoundType.CHAMPION, negation_options=(WoundNegationOption('source:near-miss'),),
            base_dice=4)
        prepared = prepare_hardy_wound(request, HARDY)
        self.assertEqual(prepared.id, request.id)
        self.assertEqual(prepared.subject_type, request.subject_type)
        self.assertEqual(prepared.base_dice, request.base_dice)
        self.assertIs(prepared.state, request.state)
        self.assertEqual(prepared.negation_options, request.negation_options)
        self.assertIs(prepare_hardy_wound(request, ()), request)
        self.assertEqual(hardy_wound_dice_modifiers(()), ())
        self.assertEqual(hardy_wound_dice_modifiers(MIGHTY), ())
        self.assertEqual(hardy_wound_dice_modifiers(HARDY), (WoundDiceModifier(HARDY_RULE_ID, -1),))
        self.assertEqual(pickle.loads(pickle.dumps(prepared)), prepared)

    def test_preparation_cannot_apply_hardy_twice_or_accept_an_unowned_marker(self):
        request = CharacterWoundRequest('hardy:once', CharacterInjuryState())
        prepared = prepare_hardy_wound(request, HARDY)
        with self.assertRaisesRegex(ValueError, 'Hardy source'):
            prepare_hardy_wound(prepared, HARDY)
        for amount in (-1, -2, 1):
            for talents in ((), HARDY):
                with self.subTest(amount=amount, talents=talents):
                    marked = replace(request, dice_modifiers=(WoundDiceModifier(HARDY_RULE_ID, amount),))
                    with self.assertRaises(ValueError):
                        prepare_hardy_wound(marked, talents)

    def test_fixed_entry_rolls_no_dice_and_is_not_changed_by_hardy(self):
        request = CharacterWoundRequest('hardy:fixed', CharacterInjuryState(),
            fixed_entry=FixedWoundSelection(WoundEntryId.DECAPITATION, 27, 'source:headsman'))
        self.assertIs(prepare_hardy_wound(request, HARDY), request)
        rng = ScriptedD10([])
        result = resolve_character_wound(request, rng)
        rng.assert_exhausted()
        self.assertEqual(result.table_roll.dice, 0)
        self.assertEqual(result.table_roll.values, ())
        self.assertNotIn(HARDY_RULE_ID, result.applied_rule_ids)
        self.assertTrue(result.state.dead)

    def test_profile_wounds_never_gain_character_dice_and_malformed_sources_are_rejected(self):
        profile = ProfileWoundRequest('minion:no-table', ProfileNpcType.MINION, ProfileInjuryState(0, 1))
        with self.assertRaises(TypeError):
            prepare_hardy_wound(profile, HARDY)
        request = CharacterWoundRequest('hardy:typed', CharacterInjuryState(),
            dice_modifiers=(WoundDiceModifier('external:weapon', 1),))
        forged = deepcopy(request)
        object.__setattr__(forged.dice_modifiers[0], 'amount', True)
        with self.assertRaises(TypeError):
            prepare_hardy_wound(forged, HARDY)
        use = actual_use(held('axe', W.GREATAXE, G.BOTH))
        for malformed in ([HARDY[0]], (TalentId.HARDY,), (True,), HARDY * 2):
            with self.subTest(malformed=malformed):
                with self.assertRaises((TypeError, ValueError)):
                    hardy_wound_dice_modifiers(malformed)
                with self.assertRaises((TypeError, ValueError)):
                    weapon_test_modifiers(use, READY, talents=malformed)


if __name__ == '__main__':
    unittest.main()
