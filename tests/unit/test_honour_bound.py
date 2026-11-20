"""PG77/111 lawful once-session activation, actual Test witnesses and Fate spend."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.talent_sources import free_talent
from towr.domain.fate_models import (
    FATE_LUCKY_RULE_ID, FateSessionState, FateSpendFunding, FateSpendKind, FateSpendRecord,
)
from towr.domain.honour_bound_models import (
    HONOUR_BOUND_GLORIOUS_RULE_ID, HONOUR_BOUND_UNMITIGATED_RULE_ID,
    HonourBoundGloriousRequest, HonourBoundState, HonourBoundUnmitigatedRequest,
    activate_honour_bound_glorious, activate_honour_bound_unmitigated,
    begin_honour_bound_session, initial_honour_bound_state, record_honour_bound_oath_decision,
)
from towr.domain.lady_blessing_models import LadyOathDecision, OathDecisionKind
from towr.domain.oath_context_models import OathBattleContext
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import (
    AcquiredTalent, OathChoice, TalentAcquisition, TalentAcquisitionPhase, TalentFunding,
)
from towr.domain.test_models import (
    BasicOutcome, DiceModifier, QualityModifier, QualityModifierSource, TestProfile,
    TestQuality, TestRequest,
)
from towr.rules.test_resolution import RerollAllFailures, resolve_test, roll_test_initial


def talent():
    return AcquiredTalent(TalentId.HONOUR_BOUND, (TalentAcquisition(
        TalentAcquisitionPhase.ADVANCEMENT, TalentFunding.XP, OathChoice('vow')),))


def context(**changes):
    return replace(OathBattleContext('gm:scene', True, 'vow', True), **changes)


def state(actor='pc', **context_changes):
    return initial_honour_bound_state(actor, talent(), 'session', context(**context_changes))


def test_request(**changes):
    return replace(TestRequest('actual:test', TestProfile(2, 5)), **changes)


def unmitigated(*, owner=None, fate=None, test=None, final=False, **changes):
    owner = owner if owner is not None else state()
    test = test if test is not None else test_request()
    fate = fate if fate is not None else FateSessionState('session', 'pc', 2, 2)
    initial = roll_test_initial(test, SequenceRandom([10, 10]))
    return replace(HonourBoundUnmitigatedRequest('honour:unmitigated', owner, context(), fate,
        test, 'gm:realistic-scope', initial_roll=None if final else initial,
        final_result=resolve_test(test, SequenceRandom([10, 10])) if final else None), **changes)


class HonourBoundResourceTests(unittest.TestCase):
    def test_complete_acquired_oath_and_explicit_context_are_required(self):
        source = state()
        self.assertTrue(source.available)
        self.assertEqual(source.talent.acquisitions[0].choice.oath_id, 'vow')
        with self.assertRaises(ValueError):
            initial_honour_bound_state('pc', talent(), 'session', context(oath_id='other'))
        with self.assertRaises(TypeError):
            initial_honour_bound_state('pc', talent(), 'session', None)
        with self.assertRaises(ValueError):
            HonourBoundState('pc', free_talent(TalentId.HARDY), 'session')
        malformed = deepcopy(source)
        object.__setattr__(malformed.talent.acquisitions[0].choice, 'oath_id', '')
        with self.assertRaises(TypeError):
            begin_honour_bound_session(malformed, 'next')

    def test_used_session_source_cannot_be_refreshed_by_new_battle_context(self):
        source = state(honour_bound_used_this_session=True)
        self.assertFalse(source.available)
        self.assertEqual(source.activation_id, 'external-use:gm:scene')
        with self.assertRaises(ValueError):
            HonourBoundGloriousRequest('activation', source,
                context(gm_confirmation_id='another-battle'), test_request())
        with self.assertRaises(ValueError):
            HonourBoundGloriousRequest('activation', state(),
                context(honour_bound_used_this_session=True), test_request())

    def test_breach_and_penance_do_not_refresh_the_once_session_resource(self):
        used = activate_honour_bound_glorious(HonourBoundGloriousRequest(
            'activation', state(), context(), test_request())).state
        breach = record_honour_bound_oath_decision(used,
            LadyOathDecision('breach', 'pc', OathDecisionKind.BREACH))
        pardoned = record_honour_bound_oath_decision(breach,
            LadyOathDecision('amends', 'pc', OathDecisionKind.PENANCE_APPROVED))
        self.assertFalse(pardoned.oath_barred)
        self.assertFalse(pardoned.available)
        self.assertEqual(pardoned.activation_id, 'activation')
        barred_unused = state(in_good_standing_confirmed=False)
        self.assertTrue(barred_unused.oath_barred)
        with self.assertRaises(ValueError):
            HonourBoundGloriousRequest('activation', barred_unused, context(), test_request())
        lawful = record_honour_bound_oath_decision(barred_unused,
            LadyOathDecision('amends', 'pc', OathDecisionKind.PENANCE_APPROVED))
        self.assertTrue(lawful.available)

    def test_new_session_refreshes_use_but_not_breach_and_ids_cannot_recycle(self):
        used = activate_honour_bound_glorious(HonourBoundGloriousRequest(
            'activation', state(), context(), test_request())).state
        new = begin_honour_bound_session(used, 'next-session')
        self.assertTrue(new.available)
        self.assertEqual(new.previous_session_ids, ('session',))
        for identifier in ('session', 'next-session'):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                begin_honour_bound_session(new, identifier)
        barred = record_honour_bound_oath_decision(used,
            LadyOathDecision('breach', 'pc', OathDecisionKind.BREACH))
        next_barred = begin_honour_bound_session(barred, 'next-session')
        self.assertIsNone(next_barred.activation_id)
        self.assertTrue(next_barred.oath_barred)
        self.assertFalse(next_barred.available)

    def test_decisions_have_actual_owner_unique_id_and_preceding_breach(self):
        for bad in (LadyOathDecision('foreign', 'npc', OathDecisionKind.BREACH),
                LadyOathDecision('amends', 'pc', OathDecisionKind.PENANCE_APPROVED)):
            with self.subTest(decision=bad), self.assertRaises(ValueError):
                record_honour_bound_oath_decision(state(), bad)
        breach = LadyOathDecision('breach', 'pc', OathDecisionKind.BREACH)
        barred = record_honour_bound_oath_decision(state(), breach)
        with self.assertRaises(ValueError):
            record_honour_bound_oath_decision(barred, breach)
        with self.assertRaises(TypeError):
            replace(state(), oath_decisions=[])
        with self.assertRaises(FrozenInstanceError):
            barred.activation_id = None


class HonourBoundGloriousTests(unittest.TestCase):
    def test_pc_and_npc_receive_real_talent_quality_without_fate_or_a_fabricated_roll(self):
        for actor in ('pc', 'npc'):
            with self.subTest(actor=actor):
                owner = state(actor)
                original = test_request()
                request = HonourBoundGloriousRequest('activate:' + actor, owner, context(), original)
                prepared = activate_honour_bound_glorious(request)
                self.assertEqual(prepared.state.activation_id, 'activate:' + actor)
                self.assertFalse(prepared.state.available)
                self.assertTrue(owner.available)
                self.assertEqual(original.quality_modifiers, ())
                self.assertFalse(hasattr(prepared, 'fate_state'))
                self.assertFalse(hasattr(prepared, 'successes'))
                modifier, = prepared.test.quality_modifiers
                self.assertEqual(modifier.rule_id, HONOUR_BOUND_GLORIOUS_RULE_ID)
                self.assertIs(modifier.source, QualityModifierSource.TALENT)
                self.assertEqual(modifier.source_id, request.id)
                actual = resolve_test(prepared.test, SequenceRandom([10, 1, 2]), decisions=RerollAllFailures())
                self.assertEqual(actual.trace.initial_values, (10, 1))
                self.assertEqual(actual.trace.final_values, (2, 1))
                self.assertEqual(actual.successes, 2)

    def test_glorious_cancels_grim_and_keeps_original_modifiers(self):
        test = test_request(quality_modifiers=(QualityModifier('actual:grim', TestQuality.GRIM),),
            dice_modifiers=(DiceModifier('actual:bonus', 1),))
        prepared = activate_honour_bound_glorious(HonourBoundGloriousRequest(
            'activation', state(), context(), test))
        final = resolve_test(prepared.test, SequenceRandom([1, 10, 10]))
        self.assertIs(final.trace.quality, TestQuality.NORMAL)
        self.assertEqual(final.trace.rerolls, ())
        self.assertEqual(prepared.test.dice_modifiers, test.dice_modifiers)

    def test_activation_needs_unused_state_and_actual_oath_fulfilment(self):
        request = HonourBoundGloriousRequest('activation', state(), context(), test_request())
        prepared = activate_honour_bound_glorious(request)
        with self.assertRaises(ValueError):
            replace(request, state=prepared.state)
        with self.assertRaises(ValueError):
            replace(request, context=context(combat_tests_fulfil_oath_confirmed=False))
        with self.assertRaises(ValueError):
            replace(request, test=prepared.test)
        with self.assertRaises(ValueError):
            replace(prepared, test=request.test)
        with self.assertRaises(ValueError):
            replace(prepared, state=request.state)

    def test_malformed_cached_test_modifiers_and_state_are_readmitted(self):
        test = test_request(dice_modifiers=(DiceModifier('modifier', 1),))
        object.__setattr__(test.dice_modifiers[0], 'amount', True)
        with self.assertRaises(TypeError):
            HonourBoundGloriousRequest('activation', state(), context(), test)
        malformed = state()
        object.__setattr__(malformed, 'previous_session_ids', ['old'])
        with self.assertRaises(TypeError):
            HonourBoundGloriousRequest('activation', malformed, context(), test_request())


class HonourBoundUnmitigatedTests(unittest.TestCase):
    def test_spends_real_session_fate_without_burn_rating_loss_or_invented_successes(self):
        request = unmitigated()
        result = activate_honour_bound_unmitigated(request)
        self.assertEqual(result.fate_state.rating, request.fate_state.rating)
        self.assertEqual(result.fate_state.remaining_spends, request.fate_state.remaining_spends - 1)
        self.assertEqual(result.fate_state.burns, ())
        self.assertEqual(result.fate_state.resource_event_ids, ())
        self.assertIs(result.spend.kind, FateSpendKind.HONOUR_BOUND_UNMITIGATED_SUCCESS)
        self.assertEqual(result.spend.subject_id, request.test.id)
        self.assertEqual(result.spend.rule_id, HONOUR_BOUND_UNMITIGATED_RULE_ID)
        self.assertEqual(result.state.activation_id, request.id)
        self.assertIs(result.effect.minimum_outcome, BasicOutcome.TOTAL_SUCCESS)
        self.assertEqual(result.effect.maximum_wounds_inflicted, 1)
        self.assertTrue(result.effect.may_not_kill_multiple_enemies)
        self.assertTrue(result.effect.requires_realistically_possible_outcome)
        self.assertEqual(result.effect.gm_scope_agreement_id, 'gm:realistic-scope')
        self.assertEqual(result.effect.initial_roll.initial_values, (10, 10))
        self.assertFalse(hasattr(result, 'test_result'))
        self.assertTrue(request.state.available)

    def test_lucky_first_spend_is_free_even_with_empty_session_pool_then_cannot_repeat(self):
        request = unmitigated(fate=FateSessionState('session', 'pc', 0, 0, has_lucky=True))
        result = activate_honour_bound_unmitigated(request)
        self.assertIs(result.spend.funding, FateSpendFunding.LUCKY_FREE)
        self.assertEqual(result.fate_state.remaining_spends, 0)
        self.assertEqual(result.fate_state.rating, 0)
        self.assertIn(FATE_LUCKY_RULE_ID, result.applied_rule_ids)
        self.assertFalse(result.fate_state.can_spend)
        with self.assertRaises(ValueError):
            replace(request, fate_state=result.fate_state)

    def test_real_initial_and_real_completed_witness_are_retained_without_reroll(self):
        for final in (False, True):
            with self.subTest(final=final):
                request = unmitigated(final=final)
                result = activate_honour_bound_unmitigated(request)
                self.assertIs(result.source_request, request)
                self.assertEqual(result.effect.initial_roll, request.initial_roll)
                if final:
                    self.assertEqual(result.source_request.final_result.successes, 0)
        request = unmitigated()
        with self.assertRaises(ValueError):
            replace(request, initial_roll=None)
        with self.assertRaises(ValueError):
            replace(request, final_result=resolve_test(request.test, SequenceRandom([1, 1])))

    def test_foreign_or_altered_test_witness_and_scope_are_rejected(self):
        request = unmitigated()
        with self.assertRaises(ValueError):
            replace(request, initial_roll=roll_test_initial(test_request(id='other'), SequenceRandom([1, 1])))
        with self.assertRaises(TypeError):
            replace(request, gm_scope_agreement_id='')
        completed = unmitigated(final=True)
        for result in (replace(completed.final_result,
                trace=replace(completed.final_result.trace, successes=3)),
                resolve_test(test_request(id='other'), SequenceRandom([10, 10]))):
            with self.subTest(result=result), self.assertRaises(ValueError):
                replace(completed, final_result=result)
        malformed = deepcopy(completed.final_result)
        object.__setattr__(malformed.trace, 'threshold', True)
        with self.assertRaises(TypeError):
            replace(completed, final_result=malformed)

    def test_wrong_fate_actor_or_session_and_no_fate_available_are_rejected(self):
        request = unmitigated()
        for fate in (FateSessionState('other-session', 'pc', 1, 1),
                FateSessionState('session', 'other-actor', 1, 1),
                FateSessionState('session', 'pc', 0, 0)):
            with self.subTest(fate=fate), self.assertRaises(ValueError):
                replace(request, fate_state=fate)
        with self.assertRaises(TypeError):
            replace(request, fate_state=None)

    def test_result_cannot_refund_activation_spend_change_scope_or_weaken_one_wound_limit(self):
        request = unmitigated()
        result = activate_honour_bound_unmitigated(request)
        for changes in ({'state': request.state}, {'fate_state': request.fate_state},
                {'effect': replace(result.effect, gm_scope_agreement_id='other')},
                {'applied_rule_ids': ()}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)
        malformed = deepcopy(result.effect)
        object.__setattr__(malformed, 'maximum_wounds_inflicted', True)
        with self.assertRaises(TypeError):
            replace(result, effect=malformed)

    def test_spend_canonical_rule_and_duplicate_subject_are_enforced(self):
        request = unmitigated()
        result = activate_honour_bound_unmitigated(request)
        with self.assertRaises(ValueError):
            replace(result.spend, rule_id='fake:rule')
        with self.assertRaises(ValueError):
            replace(result.fate_state, spends=(*result.fate_state.spends,
                replace(result.spend, id='alias')))
        with self.assertRaises(ValueError):
            replace(request, state=result.state)


if __name__ == '__main__':
    unittest.main()
