"""PG74/77 blessing expenditure and losses, independent of prayer permission.

The resource owner still authenticates prayer timing and actual Wound receipts.
These tests do not confer native Talent admission or manufacture PC/NPC Fate.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import pickle
import unittest

from tests.support.talent_sources import free_talent
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.lady_blessing_models import (
    LadyBlessingLoss, LadyBlessingState, LadyOathDecision, OathDecisionKind,
    begin_lady_blessing_battle, record_lady_broken_gain,
    record_lady_oath_decision, record_lady_prayer, record_lady_wound_negation,
)
from towr.domain.talent_catalog import TalentId


def initial(actor='knight'):
    return LadyBlessingState(actor, free_talent(TalentId.BLESSINGS_OF_THE_LADY), 'battle:1')


def decision(kind, identifier, actor='knight'):
    return LadyOathDecision(identifier, actor, kind)


class LadyBlessingResourceTests(unittest.TestCase):
    def test_unprayed_resource_cannot_negate_a_wound(self):
        state = initial()
        self.assertFalse(state.available)
        self.assertFalse(state.oath_barred)
        with self.assertRaises(ValueError):
            record_lady_wound_negation(state, 'wound:1')
        with self.assertRaises(ValueError):
            replace(state, negated_wound_id='wound:1')
        with self.assertRaises(ValueError):
            replace(state, loss=LadyBlessingLoss.BROKEN)

    def test_once_per_battle_applies_to_cancellation_not_number_of_prayers(self):
        state = initial()
        prayed = record_lady_prayer(state, 'prayer:1')
        prayed_twice = record_lady_prayer(prayed, 'prayer:2')
        spent = record_lady_wound_negation(prayed_twice, 'wound:actual')
        prayed_again = record_lady_prayer(spent, 'prayer:3')
        self.assertEqual(prayed_again.prayers, ('prayer:1', 'prayer:2', 'prayer:3'))
        self.assertEqual(prayed_again.negated_wound_id, 'wound:actual')
        self.assertFalse(prayed_again.available)
        for next_wound in ('wound:actual', 'wound:other'):
            with self.subTest(wound=next_wound), self.assertRaises(ValueError):
                record_lady_wound_negation(prayed_again, next_wound)
        self.assertTrue(prayed.available)
        self.assertFalse(state.available)

    def test_no_shared_actor_name_or_pc_resource_is_required(self):
        pc = record_lady_prayer(initial('pc:1'), 'pc:prayer')
        npc = record_lady_prayer(initial('npc:1'), 'npc:prayer')
        spent = record_lady_wound_negation(npc, 'npc:wound')
        self.assertTrue(pc.available)
        self.assertFalse(spent.available)
        self.assertEqual(spent.actor_id, 'npc:1')
        self.assertEqual(spent.talent, npc.talent)
        self.assertFalse(hasattr(spent, 'fate'))
        self.assertFalse(hasattr(spent, 'injury'))

    def test_source_requires_complete_exact_blessing_talent(self):
        state = initial()
        for wrong in (None, TalentId.BLESSINGS_OF_THE_LADY, 'blessings_of_the_lady'):
            with self.subTest(source=wrong), self.assertRaises(TypeError):
                replace(state, talent=wrong)
        with self.assertRaises(ValueError):
            replace(state, talent=free_talent(TalentId.HARDY))
        corrupted = deepcopy(state)
        object.__setattr__(corrupted.talent, 'acquisitions', ())
        with self.assertRaises(TypeError):
            record_lady_prayer(corrupted, 'prayer:1')
        corrupted = deepcopy(state)
        object.__setattr__(corrupted.talent, 'id', 'blessings_of_the_lady')
        with self.assertRaises(TypeError):
            record_lady_prayer(corrupted, 'prayer:1')

    def test_identifiers_and_history_are_exact_and_not_duplicate(self):
        state = initial()
        for invalid in ('', '  ', None, 1, True):
            for field in ('actor_id', 'battle_id'):
                with self.subTest(value=invalid, field=field), self.assertRaises(TypeError):
                    replace(state, **{field: invalid})
            with self.subTest(receipt=invalid), self.assertRaises(TypeError):
                record_lady_prayer(state, invalid)
            with self.subTest(wound=invalid), self.assertRaises(TypeError):
                record_lady_wound_negation(record_lady_prayer(state, 'prayer'), invalid)
        for field in ('prayers', 'previous_battle_ids', 'oath_decisions'):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(state, **{field: []})
        with self.assertRaises(ValueError):
            replace(state, prayers=('prayer', 'prayer'))
        with self.assertRaises(ValueError):
            replace(state, previous_battle_ids=('old', 'old'))
        with self.assertRaises(TypeError):
            replace(state, prayers=('valid', 1))
        prayed = record_lady_prayer(state, 'prayer')
        with self.assertRaises(ValueError):
            record_lady_prayer(prayed, 'prayer')
        with self.assertRaises(TypeError):
            replace(prayed, loss='broken')

    def test_broken_requires_a_new_actual_transition_owned_by_actor(self):
        state = record_lady_prayer(initial(), 'prayer')
        before = ConditionState(frozenset({Condition.STAGGERED, Condition.DRAINED}))
        after = before.with_condition(Condition.BROKEN)
        lost = record_lady_broken_gain(state, 'knight', before, after)
        self.assertIs(lost.loss, LadyBlessingLoss.BROKEN)
        self.assertFalse(lost.available)
        self.assertFalse(lost.oath_barred)
        self.assertEqual(lost.oath_decisions, ())
        self.assertEqual(before.conditions, frozenset({Condition.STAGGERED, Condition.DRAINED}))
        self.assertEqual(after.conditions, frozenset({Condition.STAGGERED, Condition.DRAINED, Condition.BROKEN}))
        for old, new in ((before, before), (after, after), (after, before)):
            with self.subTest(old=old, new=new), self.assertRaises(ValueError):
                record_lady_broken_gain(state, 'knight', old, new)
        with self.assertRaises(ValueError):
            record_lady_broken_gain(state, 'other', before, after)
        for old, new in (((), after), (before, 'broken')):
            with self.subTest(old=old, new=new), self.assertRaises(TypeError):
                record_lady_broken_gain(state, 'knight', old, new)

    def test_broken_before_receiving_blessing_cannot_lose_unreceived_resource(self):
        state = initial()
        before = ConditionState()
        after = before.with_condition(Condition.BROKEN)
        self.assertEqual(record_lady_broken_gain(state, 'knight', before, after), state)

    def test_removing_broken_alone_does_not_reactivate_lost_blessing(self):
        prayed = record_lady_prayer(initial(), 'prayer')
        before = ConditionState()
        broken = before.with_condition(Condition.BROKEN)
        lost = record_lady_broken_gain(prayed, 'knight', before, broken)
        cleared = broken.without_condition(Condition.BROKEN)
        self.assertFalse(cleared.has(Condition.BROKEN))
        self.assertFalse(lost.available)
        renewed = record_lady_prayer(lost, 'new-authorised-prayer')
        self.assertTrue(renewed.available)
        self.assertIsNone(renewed.loss)

    def test_renewal_after_broken_never_restores_spent_cancellation(self):
        spent = record_lady_wound_negation(record_lady_prayer(initial(), 'prayer'), 'wound')
        lost = record_lady_broken_gain(spent, 'knight', ConditionState(),
            ConditionState(frozenset({Condition.BROKEN})))
        renewed = record_lady_prayer(lost, 'new-authorised-prayer')
        self.assertIsNone(renewed.loss)
        self.assertEqual(renewed.negated_wound_id, 'wound')
        self.assertFalse(renewed.available)

    def test_breach_before_prayer_bars_seeking_until_explicit_gm_penance(self):
        breached = record_lady_oath_decision(initial(), decision(OathDecisionKind.BREACH, 'breach'))
        self.assertTrue(breached.oath_barred)
        self.assertIsNone(breached.loss)
        with self.assertRaises(ValueError):
            record_lady_prayer(breached, 'prayer')
        pardoned = record_lady_oath_decision(breached,
            decision(OathDecisionKind.PENANCE_APPROVED, 'amends'))
        self.assertFalse(pardoned.oath_barred)
        self.assertFalse(pardoned.available)
        self.assertTrue(record_lady_prayer(pardoned, 'prayer').available)

    def test_penance_does_not_resurrect_lost_blessing_or_restore_spent_use(self):
        for spend in (False, True):
            with self.subTest(spend=spend):
                state = record_lady_prayer(initial(), 'prayer')
                if spend:
                    state = record_lady_wound_negation(state, 'wound')
                breached = record_lady_oath_decision(state, decision(OathDecisionKind.BREACH, 'breach'))
                self.assertIs(breached.loss, LadyBlessingLoss.OATH_BREACH)
                self.assertFalse(breached.available)
                pardoned = record_lady_oath_decision(breached,
                    decision(OathDecisionKind.PENANCE_APPROVED, 'amends'))
                self.assertIs(pardoned.loss, LadyBlessingLoss.OATH_BREACH)
                self.assertFalse(pardoned.available)
                renewed = record_lady_prayer(pardoned, 'new-prayer')
                self.assertEqual(renewed.available, not spend)
                self.assertEqual(renewed.negated_wound_id, 'wound' if spend else None)

    def test_gm_decisions_cannot_change_owner_repeat_or_approve_nonexistent_penance(self):
        state = initial()
        breach = decision(OathDecisionKind.BREACH, 'breach')
        breached = record_lady_oath_decision(state, breach)
        with self.assertRaises(ValueError):
            record_lady_oath_decision(breached, breach)
        with self.assertRaises(ValueError):
            record_lady_oath_decision(state, decision(OathDecisionKind.BREACH, 'foreign', 'other'))
        with self.assertRaises(ValueError):
            record_lady_oath_decision(state, decision(OathDecisionKind.PENANCE_APPROVED, 'amends'))
        pardoned = record_lady_oath_decision(breached,
            decision(OathDecisionKind.PENANCE_APPROVED, 'amends'))
        with self.assertRaises(ValueError):
            record_lady_oath_decision(pardoned,
                decision(OathDecisionKind.PENANCE_APPROVED, 'amends-again'))
        with self.assertRaises(TypeError):
            record_lady_oath_decision(state, {'id': 'breach', 'actor_id': 'knight', 'kind': 'breach'})
        with self.assertRaises(TypeError):
            LadyOathDecision('breach', 'knight', 'breach')
        with self.assertRaises(ValueError):
            replace(record_lady_prayer(state, 'prayer'), loss=LadyBlessingLoss.OATH_BREACH)

    def test_cached_malformed_sources_are_readmitted_before_transition(self):
        corrupted = initial()
        object.__setattr__(corrupted, 'prayers', ('duplicate', 'duplicate'))
        for transition in (
            lambda: record_lady_prayer(corrupted, 'new'),
            lambda: record_lady_wound_negation(corrupted, 'wound'),
            lambda: begin_lady_blessing_battle(corrupted, 'next'),
            lambda: record_lady_oath_decision(corrupted, decision(OathDecisionKind.BREACH, 'breach')),
            lambda: record_lady_broken_gain(corrupted, 'knight', ConditionState(),
                ConditionState(frozenset({Condition.BROKEN}))),
        ):
            with self.assertRaises(ValueError):
                transition()
        malformed = decision(OathDecisionKind.BREACH, 'breach')
        object.__setattr__(malformed, 'kind', 'breach')
        with self.assertRaises(TypeError):
            record_lady_oath_decision(initial(), malformed)

    def test_new_battle_refreshes_battle_expenditure_but_retains_unresolved_oath_breach(self):
        spent = record_lady_wound_negation(record_lady_prayer(initial(), 'prayer'), 'wound')
        breached = record_lady_oath_decision(spent, decision(OathDecisionKind.BREACH, 'breach'))
        new = begin_lady_blessing_battle(breached, 'battle:2')
        self.assertEqual(new.prayers, ())
        self.assertIsNone(new.negated_wound_id)
        self.assertIsNone(new.loss)
        self.assertEqual(new.previous_battle_ids, ('battle:1',))
        self.assertEqual(new.oath_decisions, breached.oath_decisions)
        self.assertTrue(new.oath_barred)
        with self.assertRaises(ValueError):
            record_lady_prayer(new, 'new-prayer')
        pardoned = record_lady_oath_decision(new,
            decision(OathDecisionKind.PENANCE_APPROVED, 'amends'))
        renewed = record_lady_prayer(pardoned, 'new-prayer')
        self.assertTrue(renewed.available)
        self.assertFalse(record_lady_wound_negation(renewed, 'new-wound').available)

    def test_battle_identity_cannot_be_recycled_to_refresh_a_use(self):
        first = record_lady_wound_negation(record_lady_prayer(initial(), 'prayer'), 'wound')
        with self.assertRaises(ValueError):
            begin_lady_blessing_battle(first, 'battle:1')
        second = begin_lady_blessing_battle(first, 'battle:2')
        third = begin_lady_blessing_battle(second, 'battle:3')
        for identifier in ('battle:1', 'battle:2', 'battle:3'):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                begin_lady_blessing_battle(third, identifier)
        self.assertTrue(record_lady_prayer(second, 'new-prayer').available)

    def test_state_is_immutable_and_roundtrips_without_resource_refill(self):
        state = record_lady_wound_negation(record_lady_prayer(initial(), 'prayer'), 'wound')
        with self.assertRaises(FrozenInstanceError):
            state.negated_wound_id = None
        for copied in (deepcopy(state), pickle.loads(pickle.dumps(state)), replace(state)):
            with self.subTest(copy=copied):
                self.assertEqual(copied, state)
                self.assertFalse(copied.available)
                with self.assertRaises(ValueError):
                    record_lady_wound_negation(copied, 'other-wound')


if __name__ == '__main__':
    unittest.main()
