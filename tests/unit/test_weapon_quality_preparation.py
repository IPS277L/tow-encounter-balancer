from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.weapon_fixtures import weapon_use as use_weapon
from towr.domain.test_models import (
    DiceModifier, FATE_GLORIOUS_RULE_ID, QualityModifier, QualityModifierSource,
    RerollLock, Skill, SuccessModifier, TestProfile, TestQuality, TestRequest,
)
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_quality_preparation import (
    DRAGON_BOW_RULE_ID, DUELLIST_GRIM_RULE_ID, DUELLIST_GLORIOUS_RULE_ID,
    GROTARGG_HIGHER_GROUND_RULE_ID, HEADSMAN_EXECUTION_RULE_ID,
    JUSTICE_SINGLE_COMBAT_RULE_ID, UNWAVERING_GIVEN_GROUND_RULE_ID,
    WeaponAttackQualityContext as Context, prepare_weapon_attack_quality,
)
from towr.rules.test_resolution import RerollAllFailures, resolve_test


def basic_test():
    return TestRequest('attack', TestProfile(3, 5))


class WeaponAttackQualityTests(unittest.TestCase):
    def test_dragon_removes_penalties_and_grim_without_losing_rule_nine_or_fate(self):
        request = TestRequest('dragon', TestProfile(2, 5),
            (DiceModifier('wound', -2), DiceModifier('help', 1)),
            (QualityModifier('armour', TestQuality.GRIM),
             QualityModifier(FATE_GLORIOUS_RULE_ID, TestQuality.GLORIOUS,
                 QualityModifierSource.FATE, 'actual-fate-spend')),
            (SuccessModifier('spell', 1),), (RerollLock('miscast-nine', 9),))
        prepared = prepare_weapon_attack_quality(use_weapon(WeaponKind.DRAGON_BOW), request, Context())
        self.assertEqual(prepared.test.dice_modifiers, (DiceModifier('help', 1),))
        self.assertEqual(prepared.test.quality_modifiers, (request.quality_modifiers[1],))
        self.assertEqual(prepared.test.success_modifiers, request.success_modifiers)
        self.assertEqual(prepared.test.reroll_locks, request.reroll_locks)
        self.assertEqual(prepared.applied_rule_ids, (DRAGON_BOW_RULE_ID,))
        rng = ScriptedD10([9, 10, 1, 1])
        result = resolve_test(prepared.test, rng, decisions=RerollAllFailures())
        rng.assert_exhausted()
        self.assertEqual(result.trace.initial_values, (9, 10, 1))
        self.assertEqual(result.trace.final_values, (9, 1, 1))
        self.assertEqual(result.successes, 3)
        self.assertEqual(request.dice_modifiers[0].amount, -2)

    def test_dragon_rejects_unseen_target_before_any_test(self):
        with self.assertRaisesRegex(ValueError, 'unseen'):
            prepare_weapon_attack_quality(use_weapon(WeaponKind.DRAGON_BOW), basic_test(),
                Context(target_visible=False))

    def test_an_ordinary_bow_retains_its_penalties_and_grim(self):
        request = replace(basic_test(), dice_modifiers=(DiceModifier('range', -1),),
            quality_modifiers=(QualityModifier('armour', TestQuality.GRIM),))
        prepared = prepare_weapon_attack_quality(use_weapon(WeaponKind.WARBOW), request, Context())
        self.assertEqual(prepared.test, request)
        self.assertEqual(prepared.applied_rule_ids, ())

    def test_duellist_committed_order_and_drained_does_not_remove_grim_price(self):
        use = use_weapon(WeaponKind.DUELLIST_BLADES)
        first = prepare_weapon_attack_quality(use, basic_test(), Context(duellist_action_index=1))
        second = prepare_weapon_attack_quality(use, basic_test(), Context(duellist_action_index=2))
        self.assertEqual(first.test.quality_modifiers,
            (QualityModifier(DUELLIST_GRIM_RULE_ID, TestQuality.GRIM),))
        self.assertEqual(second.test.quality_modifiers,
            (QualityModifier(DUELLIST_GLORIOUS_RULE_ID, TestQuality.GLORIOUS),))
        drained_first = prepare_weapon_attack_quality(use, basic_test(),
            Context(duellist_action_index=1, drained=True))
        drained_second = prepare_weapon_attack_quality(use, basic_test(),
            Context(duellist_action_index=2, drained=True))
        self.assertEqual(drained_first.test, first.test)
        self.assertEqual(drained_second.test.quality_modifiers, ())

    def test_single_duellist_attack_does_not_invent_second_action_plan(self):
        prepared = prepare_weapon_attack_quality(use_weapon(WeaponKind.DUELLIST_BLADES),
            basic_test(), Context())
        self.assertEqual(prepared.test, basic_test())

    def test_grotargg_requires_actual_higher_ground_and_retains_source_when_drained(self):
        use = use_weapon(WeaponKind.GROTARGGS_HAMMER)
        high = prepare_weapon_attack_quality(use, basic_test(), Context(higher_ground=True))
        low = prepare_weapon_attack_quality(use, basic_test(), Context())
        drained = prepare_weapon_attack_quality(use, basic_test(), Context(higher_ground=True, drained=True))
        self.assertEqual(high.applied_rule_ids, (GROTARGG_HIGHER_GROUND_RULE_ID,))
        self.assertEqual(low.test.quality_modifiers, ())
        self.assertEqual(drained.test.quality_modifiers, ())
        # The eventual stuck-on-miss owner uses actual higher-ground context,
        # not the presence of Glorious after Drained has suppressed it.
        self.assertTrue(drained.context.higher_ground)

    def test_headsman_execution_is_opt_in_and_requires_actual_prone_target(self):
        use = use_weapon(WeaponKind.HEADSMANS_AXE)
        ordinary = prepare_weapon_attack_quality(use, basic_test(), Context(target_prone=True))
        execution = prepare_weapon_attack_quality(use, basic_test(),
            Context(target_prone=True, headsman_execution=True))
        self.assertEqual(ordinary.test.quality_modifiers, ())
        self.assertEqual(execution.applied_rule_ids, (HEADSMAN_EXECUTION_RULE_ID,))
        with self.assertRaises(ValueError):
            prepare_weapon_attack_quality(use, basic_test(), Context(headsman_execution=True))
        with self.assertRaises(ValueError):
            prepare_weapon_attack_quality(use_weapon(WeaponKind.SWORD), basic_test(),
                Context(target_prone=True, headsman_execution=True))

    def test_prone_target_is_book_higher_ground_for_grotargg(self):
        prepared = prepare_weapon_attack_quality(use_weapon(WeaponKind.GROTARGGS_HAMMER),
            basic_test(), Context(target_prone=True))
        self.assertTrue(prepared.context.effective_higher_ground)
        self.assertEqual(prepared.applied_rule_ids, (GROTARGG_HIGHER_GROUND_RULE_ID,))

    def test_unwavering_requires_given_ground_in_current_round(self):
        use = use_weapon(WeaponKind.UNWAVERING_SPEAR)
        self.assertEqual(prepare_weapon_attack_quality(use, basic_test(), Context()).contributions, ())
        prepared = prepare_weapon_attack_quality(use, basic_test(), Context(target_given_ground_this_round=True))
        self.assertEqual(prepared.applied_rule_ids, (UNWAVERING_GIVEN_GROUND_RULE_ID,))

    def test_justice_requires_both_single_combat_and_pc_or_champion(self):
        use = use_weapon(WeaponKind.SWORD_OF_JUSTICE)
        for duel, target, expected in ((False, False, False), (False, True, False),
                (True, False, False), (True, True, True)):
            with self.subTest(duel=duel, target=target):
                prepared = prepare_weapon_attack_quality(use, basic_test(),
                    Context(single_combat=duel, target_is_pc_or_champion=target))
                self.assertEqual(bool(prepared.contributions), expected)
                if expected:
                    self.assertEqual(prepared.applied_rule_ids, (JUSTICE_SINGLE_COMBAT_RULE_ID,))

    def test_only_selected_actual_justice_contributor_grants_its_quality(self):
        selected = use_weapon(WeaponKind.SWORD, offhand=WeaponKind.SWORD_OF_JUSTICE)
        context = Context(single_combat=True, target_is_pc_or_champion=True)
        prepared = prepare_weapon_attack_quality(selected, basic_test(), context)
        self.assertEqual(prepared.contributions[0].item_id, selected.contributor_item_ids[0])
        unselected = replace(selected, contributor_item_ids=())
        self.assertEqual(prepare_weapon_attack_quality(unselected, basic_test(), context).contributions, ())

    def test_two_justice_sources_retain_two_items_but_one_nonstacking_quality(self):
        use = use_weapon(WeaponKind.SWORD_OF_JUSTICE, offhand=WeaponKind.SWORD_OF_JUSTICE)
        prepared = prepare_weapon_attack_quality(use, basic_test(),
            Context(single_combat=True, target_is_pc_or_champion=True))
        self.assertEqual(tuple(item.item_id for item in prepared.contributions), use.item_ids)
        self.assertEqual(len(prepared.test.quality_modifiers), 1)

    def test_prepare_does_not_erase_an_invalid_extra_fate_glorious_spend(self):
        request = replace(basic_test(), quality_modifiers=(QualityModifier(
            FATE_GLORIOUS_RULE_ID, TestQuality.GLORIOUS, QualityModifierSource.FATE, 'spent'),))
        with self.assertRaisesRegex(ValueError, 'already Glorious'):
            prepare_weapon_attack_quality(use_weapon(WeaponKind.SWORD_OF_JUSTICE), request,
                Context(single_combat=True, target_is_pc_or_champion=True))

    def test_prepared_source_rejects_changed_result_and_duplicate_application(self):
        use = use_weapon(WeaponKind.SWORD_OF_JUSTICE)
        prepared = prepare_weapon_attack_quality(use, basic_test(),
            Context(single_combat=True, target_is_pc_or_champion=True))
        with self.assertRaises(ValueError):
            replace(prepared, test=basic_test())
        with self.assertRaises(ValueError):
            replace(prepared, contributions=())
        with self.assertRaises(ValueError):
            prepare_weapon_attack_quality(use, prepared.test, prepared.context)

    def test_context_rejects_bool_action_and_coerced_flags(self):
        with self.assertRaises(ValueError):
            Context(duellist_action_index=True)
        with self.assertRaises(TypeError):
            Context(single_combat=1)
        with self.assertRaises(ValueError):
            prepare_weapon_attack_quality(use_weapon(WeaponKind.SWORD), basic_test(),
                Context(duellist_action_index=1))


if __name__ == '__main__':
    unittest.main()
