"""Adversarial source and completed-witness checks for ADR-0055.

Fixtures roll and resolve real Wounds; corruption deliberately bypasses frozen
constructors to model an untrusted transported snapshot at public boundaries.
"""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import replace
from random import getstate
import pickle
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition
from towr.domain.crushed_rib_test_models import (
    CrushedRibCastingPreparationRequest,
    CrushedRibTestPreparationRequest,
)
from towr.domain.injury_models import (
    CharacterInjuryState, CharacterWoundRequest, CharacterWoundType,
    WoundConditionEffect, WoundEffectDuration, WoundEntryId, WoundRecordOrigin,
    WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.magic_models import CastingTestRequest, WizardMagicState
from towr.domain.test_models import (
    DiceModifier, FATE_GLORIOUS_RULE_ID, InlineProfile, QualityModifier,
    QualityModifierSource, RerollLock, RerollTrace, SuccessModifier, TestProfile,
    TestQuality, TestRequest, TestResult,
)
import towr.rules.crushed_rib_test_resolution as consumer
from towr.rules.casting_test_resolution import resolve_casting_test
from towr.rules.injury_resolution import resolve_character_wound
from towr.rules.test_resolution import resolve_test
from towr.rules.wound_effect_resolution import resolve_wound_effect


RULE = "RULE-WOUND-TABLE:crushed_rib"
ACTOR = "wizard"
LORE = "lore:beasts"
REFUSAL = (TypeError, ValueError)


def corrupt(original, /, **fields):
    result = deepcopy(original)
    for name, replacement in fields.items():
        object.__setattr__(result, name, replacement)
    return result


def rolled_injury(totals=(10,)):
    """Use actual lifecycle, including additional untreated-Wound dice."""
    state = CharacterInjuryState()
    for index, total in enumerate(totals):
        count = 1 + state.untreated_wounds
        values = (1,) * (count - 1) + (total - count + 1,)
        wound = resolve_character_wound(CharacterWoundRequest(
            f"wound:{index}", state, CharacterWoundType.CHAMPION),
            SequenceRandom(values))
        state = resolve_wound_effect(wound.effect_request, wound.state).state
    return state


def ordinary_request():
    return CrushedRibTestPreparationRequest(
        "rib:ordinary", ACTOR, rolled_injury(),
        TestRequest("test:defence", TestProfile(3, 5)))


def casting_request():
    return CrushedRibCastingPreparationRequest(
        "rib:casting", ACTOR, rolled_injury(),
        CastingTestRequest("casting:parent", ACTOR, LORE,
            TestRequest("test:casting", InlineProfile(3, 9)),
            WizardMagicState(miscast_dice=1, casting_successes=1,
                casting_lore_id=LORE, latest_casting_roll_successes=1)))


def ordinary_completed():
    prepared = consumer.prepare_crushed_rib_test(ordinary_request())
    return prepared, resolve_test(prepared.test, SequenceRandom((1, 6, 2, 8, 3)))


def casting_completed():
    prepared = consumer.prepare_crushed_rib_casting(casting_request())
    return prepared, resolve_casting_test(prepared.casting,
        SequenceRandom((9, 1, 10, 9)))


@contextmanager
def forbid_execution():
    """Completion/apply are witness checks, never a second rules execution."""
    with ExitStack() as stack:
        for target in (
            "towr.rules.test_resolution.resolve_test",
            "towr.rules.casting_test_resolution.resolve_casting_test",
            "towr.rules.crushed_rib_test_resolution.resolve_test",
            "towr.rules.crushed_rib_test_resolution.resolve_casting_test",
        ):
            stack.enter_context(patch(target, create=True,
                side_effect=AssertionError("completed witness reran a Test")))
        yield


class CrushedRibSourceRefusalTests(unittest.TestCase):
    def assert_rejected_unchanged(self, action, original):
        before = deepcopy(original)
        typed_before = pickle.dumps(original)
        rng = getstate()
        with self.assertRaises(REFUSAL):
            action()
        self.assertEqual(original, before)
        self.assertEqual(pickle.dumps(original), typed_before)
        self.assertEqual(getstate(), rng)

    def test_real_source_preparation_preserves_pending_effect_without_execution(self):
        source = ordinary_request()
        before = deepcopy(source)
        with forbid_execution():
            prepared = consumer.prepare_crushed_rib_test(source)
        self.assertEqual(source, before)
        self.assertEqual(prepared.source_request, source)
        self.assertIn(prepared.effect, source.state.active_wound_effects)
        self.assertTrue(source.state.conditions.has(Condition.DRAINED))

    def test_original_root_and_nested_collections_are_not_silently_normalized(self):
        source = ordinary_request()
        bad_sources = (
            corrupt(source, state=corrupt(source.state, wounds=list(source.state.wounds))),
            corrupt(source, state=corrupt(source.state,
                active_wound_effects=list(source.state.active_wound_effects))),
            corrupt(source, test=corrupt(source.test, dice_modifiers=[])),
            corrupt(source, test=corrupt(source.test, quality_modifiers=[])),
            corrupt(source, test=corrupt(source.test, success_modifiers=[])),
            corrupt(source, test=corrupt(source.test, reroll_locks=[])),
            corrupt(source, state=corrupt(source.state, conditions=corrupt(
                source.state.conditions, conditions=list(source.state.conditions.conditions)))),
        )
        for bad in bad_sources:
            with self.subTest(source=bad):
                self.assert_rejected_unchanged(
                    lambda: consumer.prepare_crushed_rib_test(bad), bad)

    def test_injury_flags_enums_and_roll_values_revalidated_before_equality(self):
        source = ordinary_request()
        wound = source.state.wounds[0]
        mutations = (
            ("sequence", True), ("effect_resolved", 1), ("treated", 0),
            ("healed", 0), ("entry_id", wound.entry_id.value),
            ("origin", wound.origin.value), ("roll_values", [10]),
            ("table_total", True), ("roll_values", (True, 9)),
        )
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                bad = corrupt(source, state=corrupt(source.state,
                    wounds=(corrupt(wound, **{field: value}),)))
                self.assert_rejected_unchanged(
                    lambda: consumer.prepare_crushed_rib_test(bad), bad)
        bad = corrupt(source, state=corrupt(source.state, dead=0))
        self.assert_rejected_unchanged(lambda: consumer.prepare_crushed_rib_test(bad), bad)

    def test_effect_original_types_and_exact_order_are_required(self):
        source = ordinary_request()
        drained, pending = source.state.active_wound_effects
        effect_sets = (
            (), (drained,), (pending,), (drained, pending, pending),
            (pending, drained),
            (corrupt(drained, wound_sequence=True), pending),
            (corrupt(drained, condition="drained"), pending),
            (corrupt(drained, duration="until_treated"), pending),
            (drained, corrupt(pending, restriction="next_test_is_grim")),
            (drained, corrupt(pending, duration="next_test")),
            (drained, corrupt(pending, wound_sequence=2)),
            (drained, WoundRestrictionEffect(1, WoundRestriction.CANNOT_AIM,
                WoundEffectDuration.UNTIL_TREATED)),
        )
        for effects in effect_sets:
            with self.subTest(effects=effects):
                bad = corrupt(source, state=corrupt(source.state, active_wound_effects=effects))
                self.assert_rejected_unchanged(
                    lambda: consumer.prepare_crushed_rib_test(bad), bad)

    def test_condition_original_raw_enum_alias_and_other_conditions_refused(self):
        source = ordinary_request()
        for active in (frozenset(("drained",)), frozenset(),
                       frozenset((Condition.DRAINED, Condition.STAGGERED))):
            with self.subTest(active=active):
                bad = corrupt(source, state=corrupt(source.state,
                    conditions=corrupt(source.state.conditions, conditions=active)))
                self.assert_rejected_unchanged(
                    lambda: consumer.prepare_crushed_rib_test(bad), bad)

    def test_dead_treated_healed_fixed_unresolved_and_other_wounds_refused(self):
        source = ordinary_request()
        wound = source.state.wounds[0]
        states = (
            corrupt(source.state, dead=True),
            corrupt(source.state, wounds=(corrupt(wound, treated=True),)),
            corrupt(source.state, wounds=(corrupt(wound, treated=True, healed=True),)),
            corrupt(source.state, wounds=(corrupt(wound, effect_resolved=False),)),
            corrupt(source.state, wounds=(corrupt(wound,
                origin=WoundRecordOrigin.FIXED_ENTRY, roll_values=()),)),
            rolled_injury((9,)), rolled_injury((6,)),
            rolled_injury((10, 10)), rolled_injury((10, 2)),
        )
        for state in states:
            with self.subTest(state=state):
                bad = corrupt(source, state=state)
                self.assert_rejected_unchanged(
                    lambda: consumer.prepare_crushed_rib_test(bad), bad)

    def test_first_and_last_prior_superficial_wounds_are_strictly_readmitted(self):
        source = replace(ordinary_request(), state=rolled_injury((1, 2, 10)))
        for index in (0, 1, 2):
            for field, value in (("effect_resolved", 1), ("origin", "table_roll")):
                with self.subTest(index=index, field=field):
                    wounds = list(source.state.wounds)
                    wounds[index] = corrupt(wounds[index], **{field: value})
                    bad = corrupt(source, state=corrupt(source.state, wounds=tuple(wounds)))
                    self.assert_rejected_unchanged(
                        lambda: consumer.prepare_crushed_rib_test(bad), bad)

    def test_test_profiles_modifiers_locks_and_ids_are_not_trusted_frozen_objects(self):
        source = ordinary_request()
        modifier = DiceModifier("example:penalty", -1)
        cases = (
            corrupt(source, id=" "), corrupt(source, actor_id=True),
            corrupt(source, test=corrupt(source.test, id="")),
            corrupt(source, test=corrupt(source.test,
                profile=corrupt(TestProfile(1, 5), characteristic=True))),
            corrupt(source, test=corrupt(source.test,
                profile=corrupt(InlineProfile(1, 5), dice=True))),
            corrupt(source, test=corrupt(source.test,
                dice_modifiers=(corrupt(modifier, bypasses_pool_cap=0),))),
            corrupt(source, test=corrupt(source.test,
                dice_modifiers=(corrupt(modifier, amount=True),))),
            corrupt(source, test=corrupt(source.test,
                success_modifiers=(corrupt(SuccessModifier("example:fixed", 1), amount=True),))),
            corrupt(source, test=corrupt(source.test,
                quality_modifiers=(corrupt(QualityModifier("example:grim", TestQuality.GRIM),
                    quality="grim"),))),
            corrupt(source, test=corrupt(source.test,
                reroll_locks=(corrupt(RerollLock("example:lock", 1), value=True),))),
        )
        for bad in cases:
            with self.subTest(source=bad):
                self.assert_rejected_unchanged(
                    lambda: consumer.prepare_crushed_rib_test(bad), bad)

    def test_reserved_wound_quality_and_unsupported_fate_talent_proofs_refused(self):
        source = ordinary_request()
        qualities = (
            QualityModifier(RULE, TestQuality.GRIM),
            QualityModifier(FATE_GLORIOUS_RULE_ID, TestQuality.GLORIOUS,
                QualityModifierSource.FATE, "fate:proof"),
            QualityModifier("example:talent", TestQuality.GLORIOUS,
                QualityModifierSource.TALENT, "talent:proof"),
        )
        for quality in qualities:
            with self.subTest(quality=quality):
                # Constructor rejection is equally valid; prepare must never
                # accept a transported source that bypassed that constructor.
                bad = corrupt(source, test=replace(source.test, quality_modifiers=(quality,)))
                self.assert_rejected_unchanged(
                    lambda: consumer.prepare_crushed_rib_test(bad), bad)

    def test_first_and_last_modifiers_are_checked_before_drained_can_discard_them(self):
        source = ordinary_request()
        bonuses = (DiceModifier("example:first-bonus", 1),
                   DiceModifier("example:last-bonus", 2))
        glorious = (QualityModifier("example:first-glorious", TestQuality.GLORIOUS),
                    QualityModifier("example:last-glorious", TestQuality.GLORIOUS))
        for index in (0, 1):
            for field in ("dice_modifiers", "quality_modifiers"):
                with self.subTest(index=index, field=field):
                    values = list(bonuses if field == "dice_modifiers" else glorious)
                    values[index] = (corrupt(values[index], bypasses_pool_cap=0)
                        if field == "dice_modifiers" else corrupt(values[index], source="rule"))
                    bad = corrupt(source, test=corrupt(source.test, **{field: tuple(values)}))
                    self.assert_rejected_unchanged(
                        lambda: consumer.prepare_crushed_rib_test(bad), bad)

    def test_casting_source_caster_state_lock_and_nested_original_revalidated(self):
        source = casting_request()
        casting = source.casting
        cases = (
            corrupt(source, actor_id="other"),
            corrupt(source, casting=corrupt(casting, caster_id="other")),
            corrupt(source, casting=corrupt(casting, state=corrupt(casting.state, miscast_dice=True))),
            corrupt(source, casting=corrupt(casting, state=corrupt(casting.state,
                latest_casting_roll_successes=True))),
            corrupt(source, casting=corrupt(casting, lore_id="lore:foreign")),
            corrupt(source, casting=corrupt(casting, test=corrupt(casting.test,
                reroll_locks=(RerollLock("example:preowned-nine", 9),)))),
            corrupt(source, casting=corrupt(casting, test=corrupt(casting.test,
                profile=corrupt(casting.test.profile, pool_cap=True)))),
        )
        for bad in cases:
            with self.subTest(source=bad):
                self.assert_rejected_unchanged(
                    lambda: consumer.prepare_crushed_rib_casting(bad), bad)


class CrushedRibCompletedWitnessRefusalTests(unittest.TestCase):
    def assert_bad_completion(self, prepared, completed, *, casting=False):
        before = deepcopy((prepared, completed))
        typed_before = pickle.dumps((prepared, completed))
        rng = getstate()
        complete = (consumer.complete_crushed_rib_casting if casting
            else consumer.complete_crushed_rib_test)
        with forbid_execution(), self.assertRaises(REFUSAL):
            complete(prepared, completed)
        self.assertEqual((prepared, completed), before)
        self.assertEqual(pickle.dumps((prepared, completed)), typed_before)
        self.assertEqual(getstate(), rng)

    def test_full_grim_trace_pool_quality_values_counts_and_ids_refused(self):
        prepared, completed = ordinary_completed()
        trace = completed.trace
        mutations = (
            ("request_id", "foreign:test"), ("base_dice", True),
            ("pool_cap", 7), ("regular_dice_delta", False),
            ("cap_bypassing_dice", False), ("dice_before_minimum", 4),
            ("rolled_dice", 2), ("threshold", 4),
            ("minimum_die_rule_applied", 0), ("quality", "grim"),
            ("quality", TestQuality.NORMAL),
            ("initial_values", (True, 6, 2)), ("initial_values", [1, 6, 2]),
            ("final_values", (8, 6, 10)), ("final_values", [8, 6, 3]),
            ("rolled_successes", True), ("success_delta", False),
            ("successes", True), ("applied_rule_ids", ("foreign:rule",)),
            ("applied_rule_ids", list(trace.applied_rule_ids)),
        )
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                self.assert_bad_completion(prepared,
                    TestResult(corrupt(trace, **{field: value})))

    def test_grim_rerolls_must_be_exact_all_eligible_indices_in_order_once(self):
        prepared, completed = ordinary_completed()
        a, b = completed.trace.rerolls
        cases = (
            (), (a,), (b, a), (a, a, b), [a, b],
            (corrupt(a, index=False), b), (corrupt(a, original=True), b),
            (corrupt(a, replacement=True), b),
            (RerollTrace(1, 6, 8), b),
            (corrupt(a, index=-1), b), (corrupt(a, replacement=11), b),
        )
        for rerolls in cases:
            with self.subTest(rerolls=rerolls):
                self.assert_bad_completion(prepared,
                    TestResult(corrupt(completed.trace, rerolls=rerolls)))

    def test_matching_test_id_does_not_authorize_foreign_profile_or_modifier_trace(self):
        prepared, _ = ordinary_completed()
        for foreign_test, values in (
            (replace(prepared.test, profile=TestProfile(2, 5)), (1, 9, 8)),
            (replace(prepared.test, success_modifiers=(SuccessModifier("foreign:fixed", 1),)),
                (1, 6, 2, 8, 3)),
            (replace(prepared.test, reroll_locks=(RerollLock("foreign:lock", 1),)),
                (1, 6, 2, 3)),
        ):
            with self.subTest(test=foreign_test):
                result = resolve_test(foreign_test, SequenceRandom(values))
                self.assertEqual(result.trace.request_id, prepared.test.id)
                self.assert_bad_completion(prepared, result)

    def test_completed_branches_and_non_test_objects_are_not_interchangeable(self):
        prepared, ordinary = ordinary_completed()
        cast_prepared, casting = casting_completed()
        self.assert_bad_completion(prepared, casting)
        self.assert_bad_completion(cast_prepared, ordinary, casting=True)
        self.assert_bad_completion(prepared, None)
        self.assert_bad_completion(cast_prepared, None, casting=True)

    def test_preparation_result_and_its_original_drained_sources_are_revalidated(self):
        prepared, completed = ordinary_completed()
        cases = (
            corrupt(prepared, effect=corrupt(prepared.effect, wound_sequence=True)),
            corrupt(prepared, source_request=corrupt(prepared.source_request, actor_id="other")),
            corrupt(prepared, source_request=corrupt(prepared.source_request,
                state=corrupt(prepared.source_request.state, dead=0))),
            corrupt(prepared, drained=corrupt(prepared.drained, drained_active=1)),
            corrupt(prepared, drained=corrupt(prepared.drained,
                source_request=corrupt(prepared.drained.source_request, actor_id="other"))),
            corrupt(prepared, test=corrupt(prepared.test, quality_modifiers=list(prepared.test.quality_modifiers))),
        )
        for bad in cases:
            with self.subTest(preparation=bad):
                self.assert_bad_completion(bad, completed)

    def test_executors_refuse_corrupt_preparations_before_injected_rng(self):
        class ForbiddenDice:
            def randint(self, start, end):
                raise AssertionError("invalid preparation reached RNG")

        ordinary, _ = ordinary_completed()
        casting, _ = casting_completed()
        for preparation, execute in (
            (ordinary, consumer.resolve_crushed_rib_test),
            (casting, consumer.resolve_crushed_rib_casting),
        ):
            bad = corrupt(preparation, source_request=corrupt(preparation.source_request,
                state=corrupt(preparation.source_request.state, dead=0)))
            with self.subTest(execute=execute.__name__):
                before = deepcopy(bad)
                with self.assertRaises(REFUSAL):
                    execute(bad, ForbiddenDice())
                self.assertEqual(bad, before)

    def test_casting_parent_magic_snapshot_and_exact_followups_revalidated(self):
        prepared, completed = casting_completed()
        follow = completed.follow_ups[0]
        cases = (
            corrupt(completed, request_id="foreign:parent"),
            corrupt(completed, caster_id="other"), corrupt(completed, lore_id="lore:foreign"),
            corrupt(completed, previous_casting_successes=True),
            corrupt(completed, latest_roll_successes=1), corrupt(completed, miscast_dice_added=1),
            corrupt(completed, state=corrupt(completed.state, miscast_dice=True)),
            corrupt(completed, state=replace(completed.state, casting_successes=4)),
            corrupt(completed, follow_ups=()), corrupt(completed, follow_ups=(follow, follow)),
            corrupt(completed, follow_ups=[follow]),
            corrupt(completed, follow_ups=(corrupt(follow, source_kind=follow.source_kind.value),)),
            corrupt(completed, follow_ups=(corrupt(follow, target_id="other"),)),
            corrupt(completed, follow_ups=(corrupt(follow, source_id="foreign:test"),)),
            corrupt(completed, follow_ups=(corrupt(follow, resolution_id="foreign:pool"),)),
            corrupt(completed, follow_ups=(corrupt(follow, trigger_rule_id="foreign:casting"),)),
            corrupt(completed, follow_ups=(corrupt(follow, rule_id="foreign:nine"),)),
            corrupt(completed, follow_ups=(corrupt(follow, amount=True),)),
            corrupt(completed, applied_rule_ids=("foreign:parent",)),
        )
        for bad in cases:
            with self.subTest(completed=bad):
                self.assert_bad_completion(prepared, bad, casting=True)

    def test_casting_effective_nine_lock_cannot_be_missing_duplicated_or_foreign(self):
        prepared, completed = casting_completed()
        trace = completed.test.trace
        for ids in ((RULE,), (*trace.applied_rule_ids, trace.applied_rule_ids[-1]),
                    (RULE, "foreign:nine-lock")):
            with self.subTest(ids=ids):
                self.assert_bad_completion(prepared,
                    corrupt(completed, test=TestResult(corrupt(trace, applied_rule_ids=ids))), casting=True)
        # A locked initial nine cannot be rerolled, even if a forged final
        # value/success count superficially agrees with the prepared profile.
        bad_trace = corrupt(trace, rerolls=(RerollTrace(0, 9, 9), *trace.rerolls))
        self.assert_bad_completion(prepared,
            corrupt(completed, test=TestResult(bad_trace)), casting=True)

    def test_apply_rejects_stale_repeated_foreign_actor_and_partial_source_change(self):
        prepared, completed = ordinary_completed()
        with forbid_execution():
            result = consumer.complete_crushed_rib_test(prepared, completed)
            state = prepared.source_request.state
            applied = consumer.apply_crushed_rib_test_result(ACTOR, state, result)
        self.assertEqual(applied, result.state)
        self.assertTrue(applied.conditions.has(Condition.DRAINED))
        self.assertEqual(applied.wounds, state.wounds)
        changed_wound = replace(state.wounds[0], roll_values=(5, 5))
        changed = replace(state, wounds=(changed_wound,))
        for actor, current, witness in (
            ("other", state, result), (ACTOR, applied, result),
            (ACTOR, changed, result), (ACTOR, state, completed),
            (ACTOR, state, None),
            (ACTOR, corrupt(state, dead=0), result),
            (ACTOR, state, corrupt(result, state=state)),
            (ACTOR, state, corrupt(result,
                consumed_effect=corrupt(result.consumed_effect, wound_sequence=True))),
        ):
            with self.subTest(actor=actor, current=current, witness=witness):
                before = deepcopy((current, witness))
                with forbid_execution(), self.assertRaises(REFUSAL):
                    consumer.apply_crushed_rib_test_result(actor, current, witness)
                self.assertEqual((current, witness), before)


if __name__ == "__main__":
    unittest.main()
