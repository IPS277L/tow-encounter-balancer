"""PG93 actual inventory witnesses and real Stealth/Toil resolution."""
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.test_models import (
    DiceModifier, FATE_GLORIOUS_RULE_ID, FateGloriousProof, InlineProfile,
    QualityModifier, QualityModifierSource, RerollLock, Skill, SuccessModifier,
    TestProfile, TestQuality, TestRequest,
)
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_effect_preparation import (
    DAGGER_CONCEALMENT_RULE_ID, KNUCKLEDUSTERS_CONCEALMENT_RULE_ID,
    PICKAXE_HARVEST_RULE_ID,
)
from towr.domain.weapon_inventory_models import (
    WeaponGrip as G, WeaponItemLocation as L, WeaponItemSource,
    initial_weapon_inventory,
)
from towr.domain.weapon_utility_models import (
    WeaponUtilityKind as K, WeaponUtilityLedger, WeaponUtilityRequest,
    apply_weapon_utility_result,
)
from towr.rules.test_resolution import KeepAllFailures, MissingTestDecisionError, RerollAllFailures
from towr.rules.weapon_utility_resolution import prepare_weapon_utility, execute_weapon_utility


def request(kind=W.DAGGER, *, actor='pc', location=L.CARRIED, test=None, conditions=ConditionState()):
    # A real extra ranged unit proves that utility preserves the complete
    # inventory, including unrelated finite charges and K1 loaded state.
    inventory = initial_weapon_inventory(actor, (
        WeaponItemSource('tool', kind, location, G.BOTH if kind is W.PICKAXE else
            G.LEFT if location is L.HELD else None),
        WeaponItemSource('gun', W.PISTOL, L.CARRIED, None, initially_loaded=True),
        WeaponItemSource('scarab', W.SCARAB_KNIFE, L.CARRIED, None, initial_charges=2),
    ))
    return WeaponUtilityRequest('utility:' + actor, actor, inventory, inventory.items[0].id,
        K.HARVEST if kind is W.PICKAXE else K.CONCEAL_WEAPON,
        Skill.TOIL if kind is W.PICKAXE else Skill.STEALTH,
        TestRequest('test:' + actor, TestProfile(2, 5)) if test is None else test,
        conditions, usable_hands=(G.LEFT, G.RIGHT) if kind is W.PICKAXE else None)


def forged(source, **changes):
    value = replace(source)
    for name, replacement in changes.items():
        object.__setattr__(value, name, replacement)
    return value


class WeaponUtilityTests(unittest.TestCase):
    def test_real_concealment_for_pc_and_npc_preserves_complete_source(self):
        for actor, profile in (('pc', TestProfile(3, 5)), ('npc', InlineProfile(3, 5, 8))):
            for kind, rule in ((W.DAGGER, DAGGER_CONCEALMENT_RULE_ID),
                    (W.KNUCKLEDUSTERS, KNUCKLEDUSTERS_CONCEALMENT_RULE_ID)):
                for location in (L.HELD, L.CARRIED):
                    with self.subTest(actor=actor, kind=kind, location=location):
                        test = TestRequest('full:' + actor, profile,
                            (DiceModifier('scene:penalty', -1), DiceModifier('other:bonus', 1)),
                            (QualityModifier('scene:grim', TestQuality.GRIM),
                                QualityModifier('other:glorious', TestQuality.GLORIOUS)),
                            (SuccessModifier('other:success', 1),), (RerollLock('other:lock', 9),))
                        source = request(kind, actor=actor, location=location, test=test)
                        prepared = prepare_weapon_utility(source)
                        self.assertEqual(prepared.test, replace(test,
                            dice_modifiers=(*test.dice_modifiers, DiceModifier(rule, 1))))
                        self.assertIs(prepared.source_request, source)
                        self.assertEqual(prepared.item, source.inventory.item(source.item_id))
                        rng = ScriptedD10((1, 9, 6, 4))
                        result = execute_weapon_utility(prepared, rng)
                        rng.assert_exhausted()
                        self.assertEqual(result.test.successes, 3)
                        self.assertEqual(result.test.trace.applied_rule_ids.count(rule), 1)
                        self.assertEqual(result.source_request.inventory, source.inventory)
                        self.assertEqual(result.source_request.test, test)
                        self.assertEqual(result.source_request.conditions, ConditionState())
                        self.assertEqual(source.inventory.items[1].reload.loaded, True)
                        self.assertEqual(source.inventory.items[2].charges, 2)

    def test_pickaxe_uses_actual_toil_and_two_usable_held_hands(self):
        for actor, profile in (('pc', TestProfile(2, 4)), ('npc', InlineProfile(2, 4, 10))):
            with self.subTest(actor=actor):
                source = request(W.PICKAXE, actor=actor, location=L.HELD,
                    test=TestRequest('harvest:' + actor, profile))
                prepared = prepare_weapon_utility(source)
                self.assertIs(prepared.source_request.skill, Skill.TOIL)
                self.assertIs(prepared.item.grip, G.BOTH)
                self.assertEqual(prepared.test.dice_modifiers, (DiceModifier(PICKAXE_HARVEST_RULE_ID, 1),))
                rng = ScriptedD10((1, 6, 10))
                result = execute_weapon_utility(prepared, rng)
                rng.assert_exhausted()
                self.assertEqual(result.test.successes, 1)
                for hands in (None, (), (G.LEFT,), (G.RIGHT,)):
                    with self.assertRaises(ValueError):
                        replace(source, usable_hands=hands)
                for hands in ((G.BOTH,), (G.LEFT, G.LEFT), (G.LEFT, G.RIGHT, G.BOTH)):
                    with self.assertRaises(ValueError):
                        replace(source, usable_hands=hands)
                with self.assertRaises(TypeError):
                    replace(source, usable_hands=('left', 'right'))
                with self.assertRaises(ValueError):
                    replace(source, skill=Skill.MELEE)

    def test_drained_is_final_preparation_for_dice_and_non_fate_glorious(self):
        test = TestRequest('drained', TestProfile(2, 5),
            (DiceModifier('other:bonus', 2), DiceModifier('scene:penalty', -1)),
            (QualityModifier('scene:grim', TestQuality.GRIM),
                QualityModifier('other:glorious', TestQuality.GLORIOUS)))
        source = request(test=test, conditions=ConditionState(frozenset((Condition.DRAINED,))))
        prepared = prepare_weapon_utility(source)
        self.assertEqual(prepared.test.dice_modifiers, (DiceModifier('scene:penalty', -1),))
        self.assertEqual(prepared.drained.removed_bonus_modifiers,
            (DiceModifier('other:bonus', 2), DiceModifier(DAGGER_CONCEALMENT_RULE_ID, 1)))
        self.assertEqual(prepared.test.quality_modifiers, (QualityModifier('scene:grim', TestQuality.GRIM),))
        self.assertEqual(source.test, test)
        rng = ScriptedD10((1, 10))
        result = execute_weapon_utility(prepared, rng)
        rng.assert_exhausted()
        self.assertEqual(result.test.trace.rolled_dice, 1)
        self.assertIs(result.test.trace.quality, TestQuality.GRIM)
        self.assertEqual(result.test.successes, 0)
        self.assertNotIn(DAGGER_CONCEALMENT_RULE_ID, result.test.trace.applied_rule_ids)

    def test_drained_preserves_real_fate_and_explicit_reroll_decisions(self):
        proof = FateGloriousProof('fate:proof', 'session', 'pc', 'fate:test', 'fate:spend')
        test = TestRequest('fate:test', TestProfile(1, 5),
            quality_modifiers=(QualityModifier(FATE_GLORIOUS_RULE_ID, TestQuality.GLORIOUS,
                QualityModifierSource.FATE, proof.id),))
        source = request(conditions=ConditionState(frozenset((Condition.DRAINED,))))
        with self.assertRaises(ValueError):
            replace(source, test=test)
        source = replace(source, test=test, fate_glorious_proofs=(proof,))
        prepared = prepare_weapon_utility(source)
        self.assertEqual(prepared.test.quality_modifiers, test.quality_modifiers)
        rng = ScriptedD10((10,))
        with self.assertRaises(MissingTestDecisionError):
            execute_weapon_utility(prepared, rng)
        self.assertEqual(rng.index, 0)
        kept = execute_weapon_utility(prepared, rng, decisions=KeepAllFailures())
        rng.assert_exhausted()
        self.assertEqual(kept.test.successes, 0)
        rng = ScriptedD10((10, 1))
        rerolled = execute_weapon_utility(prepared, rng, decisions=RerollAllFailures())
        rng.assert_exhausted()
        self.assertEqual(rerolled.test.successes, 1)
        self.assertEqual(len(rerolled.test.trace.rerolls), 1)

    def test_item_context_skill_and_initial_origin_are_distinct(self):
        source = request()
        for changes in ({'skill': Skill.MELEE}, {'kind': K.HARVEST},
                {'skill': 'stealth'}, {'kind': 'conceal_weapon'}):
            with self.assertRaises((ValueError, TypeError)):
                replace(source, **changes)
        with self.assertRaises(KeyError):
            replace(source, item_id='absent')
        for location in (L.DROPPED, L.DEPLOYED, L.STUCK, L.SPENT):
            item = replace(source.inventory.items[0], location=location)
            inventory = replace(source.inventory, items=(item, *source.inventory.items[1:]))
            with self.assertRaises(ValueError):
                replace(source, inventory=inventory)
        other = initial_weapon_inventory('former-owner', (
            WeaponItemSource('tool', W.DAGGER, L.CARRIED, None),))
        # Its immutable origin cannot forbid its new owner's actual inventory.
        adopted = replace(source, inventory=other, item_id=other.items[0].id)
        self.assertEqual(prepare_weapon_utility(adopted).item.initial_actor_id, 'former-owner')
        sword = initial_weapon_inventory('pc', (WeaponItemSource('sword', W.SWORD, L.CARRIED, None),))
        with self.assertRaises(ValueError):
            replace(source, inventory=sword, item_id=sword.items[0].id)
        pickaxe = request(W.PICKAXE, location=L.HELD)
        carried = replace(pickaxe.inventory.items[0], location=L.CARRIED, grip=None)
        with self.assertRaises(ValueError):
            replace(pickaxe, inventory=replace(pickaxe.inventory,
                items=(carried, *pickaxe.inventory.items[1:])))

    def test_prepared_modifier_cannot_be_applied_twice(self):
        source = request()
        prepared = prepare_weapon_utility(source)
        self.assertEqual(prepare_weapon_utility(source), prepared)
        with self.assertRaises(ValueError):
            replace(source, test=prepared.test)
        for rule in (DAGGER_CONCEALMENT_RULE_ID, KNUCKLEDUSTERS_CONCEALMENT_RULE_ID, PICKAXE_HARVEST_RULE_ID):
            with self.assertRaises(ValueError):
                replace(source, test=replace(source.test, dice_modifiers=(DiceModifier(rule, 1),)))
        rng = ScriptedD10((1, 10, 10))
        result = execute_weapon_utility(prepared, rng)
        rng.assert_exhausted()
        ledger = WeaponUtilityLedger(source.actor_id)
        applied = apply_weapon_utility_result(ledger, result)
        self.assertEqual(ledger.resolved_ids, ())
        self.assertEqual(applied.resolved_ids, (source.id,))
        with self.assertRaises(ValueError):
            apply_weapon_utility_result(applied, result)
        with self.assertRaises(ValueError):
            apply_weapon_utility_result(WeaponUtilityLedger('other'), result)

    def test_malformed_source_is_rejected_before_rng(self):
        source = request()
        bad_modifier = forged(DiceModifier('other', 1), amount=True)
        bad_test = forged(source.test, dice_modifiers=(bad_modifier,))
        bad_item = forged(source.inventory.items[0], location='carried')
        bad_inventory = forged(source.inventory, items=(bad_item, *source.inventory.items[1:]))
        for invalid in (forged(source, inventory=bad_inventory),
                forged(source, test=bad_test), forged(source, skill='stealth')):
            rng = ScriptedD10(())
            with self.assertRaises((ValueError, TypeError)):
                prepare_weapon_utility(invalid)
            self.assertEqual(rng.index, 0)
        prepared = prepare_weapon_utility(source)
        invalid = forged(prepared, item=source.inventory.items[1])
        rng = ScriptedD10(())
        with self.assertRaises(ValueError):
            execute_weapon_utility(invalid, rng)
        self.assertEqual(rng.index, 0)

    def test_result_rejects_stale_source_forged_trace_and_replay(self):
        source = request()
        prepared = prepare_weapon_utility(source)
        rng = ScriptedD10((1, 10, 10))
        result = execute_weapon_utility(prepared, rng)
        rng.assert_exhausted()
        ledger = WeaponUtilityLedger(source.actor_id)
        bad_traces = (
            replace(result.test.trace, successes=3),
            replace(result.test.trace, threshold=6),
            replace(result.test.trace, request_id='foreign'),
            replace(result.test.trace, rolled_dice=True),
            replace(result.test.trace, applied_rule_ids=()),
            replace(result.test.trace, final_values=(1, 1, 1)),
        )
        for trace in bad_traces:
            with self.subTest(trace=trace):
                invalid = forged(result, test=replace(result.test, trace=trace))
                with self.assertRaises((ValueError, TypeError)):
                    apply_weapon_utility_result(ledger, invalid)
        different = prepare_weapon_utility(replace(source,
            test=replace(source.test, success_modifiers=(SuccessModifier('actual:success', 1),))))
        with self.assertRaises(ValueError):
            replace(result, preparation=different)


if __name__ == '__main__':
    unittest.main()
