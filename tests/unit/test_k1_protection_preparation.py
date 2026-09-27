from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_attack_resolution import attack_request
from towr.domain.attack_models import AttackOutcome, ConditionImpactSpec
from towr.domain.condition_models import Condition
from towr.domain.protection_models import (
    CLOSE_RANGED_MELEE_RULE_ID,
    PROTECTION_ELIGIBILITY_RULE_ID,
    PROTECTION_PREPARATION_RULE_ID,
    ProtectionPreparationRequest,
    ProtectionTestOption,
    UnopposedReason,
)
from towr.domain.test_models import DiceModifier, InlineProfile, Skill, TestProfile, TestRequest
from towr.rules.attack_resolution import resolve_attack
from towr.rules.protection_preparation import prepare_protection


def request(**changes):
    values = dict(
        id="prepare:protection", defender_id="target", attack=attack_request(),
        attack_skill=Skill.MELEE, defender_is_aware=True, defender_is_defenceless=False,
        defender_wields_weapon=False, defender_holds_shield=False,
        selected_skill=Skill.ATHLETICS,
        options=tuple(ProtectionTestOption("target", skill, TestRequest(
            f"defender:{skill.value}", InlineProfile(2, 5),
        )) for skill in (Skill.ATHLETICS, Skill.DEFENCE, Skill.MELEE)),
    )
    values.update(changes)
    return ProtectionPreparationRequest(**values)


class K1ProtectionPreparationTests(unittest.TestCase):
    def test_athletics_is_eligible_for_all_attack_skills_without_equipment(self):
        for skill, close in product((Skill.MELEE, Skill.BRAWN, Skill.SHOOTING, Skill.THROWING), (False, True)):
            with self.subTest(skill=skill, close=close):
                source = request(attack_skill=skill, attack=attack_request(close=close))
                result = prepare_protection(source)
                self.assertIs(result.attack.defender_test, source.options[0].test)
                self.assertEqual(result.unopposed_reasons, ())
                self.assertEqual(result.applied_rule_ids, (
                    PROTECTION_PREPARATION_RULE_ID, PROTECTION_ELIGIBILITY_RULE_ID,
                ))

    def test_close_combat_defence_requires_weapon_or_shield_not_close_range(self):
        for skill, close, weapon, shield in product((Skill.MELEE, Skill.BRAWN), (False, True), (False, True), (False, True)):
            with self.subTest(skill=skill, close=close, weapon=weapon, shield=shield):
                args = dict(attack_skill=skill, attack=attack_request(close=close),
                            defender_wields_weapon=weapon, defender_holds_shield=shield,
                            selected_skill=Skill.DEFENCE)
                if weapon or shield:
                    source = request(**args)
                    result = prepare_protection(source)
                    self.assertIs(result.attack.defender_test, source.options[1].test)
                    self.assertEqual(result.eligible_skills, (Skill.ATHLETICS, Skill.DEFENCE))
                else:
                    with self.assertRaisesRegex(ValueError, "not eligible"):
                        request(**args)

    def test_ranged_defence_requires_shield_even_in_close_with_weapon(self):
        for skill, close, weapon, shield in product((Skill.SHOOTING, Skill.THROWING), (False, True), (False, True), (False, True)):
            with self.subTest(skill=skill, close=close, weapon=weapon, shield=shield):
                args = dict(attack_skill=skill, attack=attack_request(close=close),
                            defender_wields_weapon=weapon, defender_holds_shield=shield,
                            selected_skill=Skill.DEFENCE)
                if shield:
                    source = request(**args)
                    result = prepare_protection(source)
                    self.assertIs(result.attack.defender_test, source.options[1].test)
                else:
                    with self.assertRaisesRegex(ValueError, "not eligible"):
                        request(**args)

    def test_close_ranged_melee_is_explicit_and_not_an_inferred_weapon_bonus(self):
        for skill in (Skill.SHOOTING, Skill.THROWING):
            source = request(attack_skill=skill, selected_skill=Skill.MELEE)
            result = prepare_protection(source)
            self.assertEqual(result.eligible_skills, (Skill.ATHLETICS, Skill.MELEE))
            self.assertIs(result.attack.defender_test, source.options[2].test)
            self.assertEqual(result.attack.defender_test.dice_modifiers, ())
            self.assertEqual(result.applied_rule_ids[-1], CLOSE_RANGED_MELEE_RULE_ID)
        for skill, close in ((Skill.MELEE, True), (Skill.BRAWN, True),
                             (Skill.SHOOTING, False), (Skill.THROWING, False)):
            with self.assertRaisesRegex(ValueError, "not eligible"):
                request(attack_skill=skill, attack=attack_request(close=close), selected_skill=Skill.MELEE)

    def test_unaware_defenceless_and_both_remove_opposition_without_profiles(self):
        for aware, defenceless, reasons in (
            (False, False, (UnopposedReason.UNAWARE,)),
            (True, True, (UnopposedReason.DEFENCELESS,)),
            (False, True, (UnopposedReason.UNAWARE, UnopposedReason.DEFENCELESS)),
        ):
            source = request(defender_is_aware=aware, defender_is_defenceless=defenceless,
                             selected_skill=None, options=())
            result = prepare_protection(source)
            self.assertIsNone(result.attack.defender_test)
            self.assertEqual(result.unopposed_reasons, reasons)
            self.assertEqual(result.eligible_skills, ())
            self.assertIsNotNone(source.attack.defender_test)

    def test_no_silent_choice_or_voluntary_unopposed_policy(self):
        with self.assertRaisesRegex(ValueError, "not eligible"):
            request(selected_skill=None)
        for skill in (Skill.ATHLETICS, Skill.DEFENCE, Skill.MELEE):
            with self.assertRaisesRegex(ValueError, "cannot select opposition"):
                request(defender_is_aware=False, selected_skill=skill)

    def test_only_selected_profile_is_required_and_no_best_profile_is_chosen(self):
        source = request(defender_holds_shield=True, attack_skill=Skill.SHOOTING)
        low = replace(source.options[0], test=replace(source.options[0].test, profile=TestProfile(1, 1)))
        better = replace(source.options[1], test=replace(source.options[1].test, profile=InlineProfile(6, 9)))
        result = prepare_protection(replace(source, options=(low, better)))
        self.assertIs(result.attack.defender_test, low.test)
        self.assertEqual(result.eligible_skills, (Skill.ATHLETICS, Skill.DEFENCE, Skill.MELEE))
        self.assertIs(prepare_protection(replace(source, options=(low,))).attack.defender_test, low.test)
        with self.assertRaisesRegex(ValueError, "requires a supplied Test"):
            replace(source, options=(better,))

    def test_preserves_all_other_attack_fields_and_selected_modifiers_without_rng(self):
        source = request(attack=attack_request(impact_spec=ConditionImpactSpec(
            Condition.PRONE, "profile:prone",
        )))
        option = replace(source.options[0], test=replace(source.options[0].test,
            dice_modifiers=(DiceModifier("profile:penalty", -1),)))
        source = replace(source, options=(option,))
        before = deepcopy(source)
        with patch("towr.rules.attack_resolution.resolve_test") as roll:
            result = prepare_protection(source)
        roll.assert_not_called()
        self.assertIs(result.source_request, source)
        self.assertIs(result.attack.defender_test, option.test)
        self.assertEqual(result.attack, replace(source.attack, defender_test=option.test))
        self.assertIs(result.attack.attacker_test, source.attack.attacker_test)
        self.assertIs(result.attack.impact_spec, source.attack.impact_spec)
        self.assertEqual(source, before)
        with self.assertRaises(FrozenInstanceError):
            result.attack = source.attack

    def test_foreign_actor_duplicate_skills_and_duplicate_test_ids_rejected(self):
        source = request()
        for options in (
            (replace(source.options[0], defender_id="other"),),
            (source.options[0], source.options[0]),
            (source.options[0], replace(source.options[1], test=source.options[0].test)),
            (replace(source.options[0], test=source.attack.attacker_test),),
        ):
            with self.assertRaises(ValueError):
                replace(source, options=options)

    def test_invalid_types_ids_and_canonical_rule_rejected(self):
        source = request()
        for changes in (
            {"id": " "}, {"defender_id": ""}, {"attack": None},
            {"attack_skill": "melee"}, {"attack_skill": Skill.AWARENESS},
            {"selected_skill": "athletics"}, {"selected_skill": Skill.BRAWN},
            {"options": (None,)}, {"rule_id": "foreign"},
            *({name: value} for name in ("defender_is_aware", "defender_is_defenceless",
                "defender_wields_weapon", "defender_holds_shield") for value in (1, None, "true")),
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)
        for changes in ({"skill": Skill.SHOOTING}, {"skill": "defence"}, {"test": None}, {"defender_id": ""}):
            with self.assertRaises((TypeError, ValueError)):
                replace(source.options[0], **changes)
        with self.assertRaises(TypeError):
            prepare_protection(None)

    def test_result_rejects_stale_attack_profile_actor_choice_and_trace(self):
        source = request(attack_skill=Skill.SHOOTING)
        result = prepare_protection(source)
        changed_option = replace(source.options[0], test=replace(source.options[0].test, profile=InlineProfile(4, 9)))
        for changes in (
            {"request_id": "other"}, {"rule_id": "foreign"}, {"defender_id": "other"},
            {"source_request": None}, {"source_request": replace(source, id="other")},
            {"source_request": replace(source, selected_skill=Skill.MELEE)},
            {"source_request": replace(source, options=(changed_option,))},
            {"attack": replace(result.attack, id="other")},
            {"attack": replace(result.attack, attacker_is_staggered=True)},
            {"attack": replace(result.attack, defender_test=source.attack.defender_test)},
            {"eligible_skills": ()}, {"unopposed_reasons": (UnopposedReason.UNAWARE,)},
            {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "foreign")},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(result, **changes)

    def test_opposed_composition_rolls_each_test_once_and_retains_both_traces(self):
        for values, outcome, tie in (
            ([1, 1], AttackOutcome.HIT, True),
            ([10, 10], AttackOutcome.MISS, False),
            ([10, 1], AttackOutcome.MISS, False),
            ([1, 10], AttackOutcome.HIT, False),
        ):
            source = request()
            source = replace(source, attack=replace(source.attack,
                attacker_test=TestRequest("attacker", TestProfile(1, 5))),
                options=(replace(source.options[0], test=replace(source.options[0].test, profile=InlineProfile(1, 5))),))
            rng = SequenceRandom([*values, 7])
            before = deepcopy(source)
            prepared = prepare_protection(source)
            decisions = Mock()
            result = resolve_attack(prepared.attack, rng, decisions=decisions)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertEqual(decisions.mock_calls, [])
            self.assertIs(result.outcome, outcome)
            self.assertEqual(result.tie_break_applied, tie)
            self.assertEqual(result.defender_test.trace.request_id, prepared.attack.defender_test.id)
            self.assertEqual(result.attacker_test.trace.rolled_dice, 1)
            self.assertEqual(result.defender_test.trace.rolled_dice, 1)
            self.assertIn(PROTECTION_ELIGIBILITY_RULE_ID, prepared.applied_rule_ids)
            if tie:
                self.assertIn("RULE-COMBAT-006:attack-tie", result.applied_rule_ids)
            self.assertEqual(source, before)

    def test_unopposed_composition_needs_success_and_never_rolls_defence(self):
        for value in (1, 10):
            source = request(defender_is_aware=False, selected_skill=None, options=())
            source = replace(source, attack=replace(source.attack,
                attacker_test=TestRequest("attacker", TestProfile(1, 5))))
            rng = SequenceRandom([value, 7])
            prepared = prepare_protection(source)
            result = resolve_attack(prepared.attack, rng)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertIsNone(result.defender_test)
            self.assertIs(result.outcome, AttackOutcome.HIT if value == 1 else AttackOutcome.MISS)
            self.assertEqual(prepared.unopposed_reasons, (UnopposedReason.UNAWARE,))


if __name__ == "__main__":
    unittest.main()
