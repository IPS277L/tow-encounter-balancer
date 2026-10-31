"""ADR-0046 closed journal: complete origin evidence and mandatory phase order.

Fixtures use real bound transitions, including distinct Recover traces with the
same post-state. They do not claim fresh-runner reachability for authored wounds.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import pickle
import unittest

from tests.helpers import SequenceRandom
from tests.integration.test_m8_npc_broken_recover import wounded_broken_wizard, wizard_recovery
from tests.integration.test_m8_npc_broken_run import from_owner
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario_result import miscast
from tests.unit.test_m8_npc_roster_prone_stand import request as stand_request
from towr.domain.npc_magic_miscast_journal_policy import validate_magic_miscast_predecessor as validate
from towr.domain.npc_magic_scenario_result_models import (
    NpcMagicScenarioResult, diagnose_npc_magic_unsupported,
)
from towr.domain.npc_magic_step_models import NpcMagicStep as Step, NpcMagicUnsupportedReason
from towr.domain.npc_roster_miscast_models import (
    NpcRosterMiscastPreparationRequest, NpcRosterMiscastRollRequest,
    NpcRosterUnnaturalWindRequest,
)
from towr.domain.npc_roster_prone_models import NpcRosterProneTurnEndRequest
from towr.engine.npc_broken_recover import execute_npc_broken_recover
from towr.engine.npc_broken_run import execute_npc_broken_run
from towr.rules.npc_roster_miscast_resolution import (
    prepare_npc_roster_miscast, roll_npc_roster_miscast, resolve_npc_roster_unnatural_wind,
)
from towr.rules.npc_roster_prone_resolution import stand_npc_roster_prone, end_npc_roster_prone_turn


def casting_chain(values=(7, 7, 7), *, identifier=None):
    journal, diagnosis = miscast()
    scenario = replace(journal.source, miscast_continuation=continuation_policy())
    origin = journal.steps[-1]
    prepared = preparation(origin.result, identifier or scenario.id + ':prepare')
    rolled = Step(roll_npc_roster_miscast(NpcRosterMiscastRollRequest(
        prepared.result.roll_request.resolution_id, prepared.after), SequenceRandom(values)))
    return scenario, journal, diagnosis, origin, prepared, rolled


def preparation(origin, identifier='journal:prepare'):
    policy = continuation_policy()
    result = prepare_npc_roster_miscast(NpcRosterMiscastPreparationRequest(
        identifier, origin.state, policy.choice, policy.facts))
    return Step(result, origin_witness=origin)


def wind(rolled):
    return Step(resolve_npc_roster_unnatural_wind(NpcRosterUnnaturalWindRequest(
        rolled.result.effect_request.resolution_id + ':apply', rolled.after)))


class MiscastJournalTests(unittest.TestCase):
    def test_casting_preparation_keeps_full_typed_witness_and_owner(self):
        source, _, _, origin, prepared, _ = casting_chain()
        self.assertIs(prepared.origin_witness, origin.result)
        self.assertEqual(prepared.before, origin.after)
        self.assertEqual(prepared.after.pending_miscast_continuation, prepared.result)
        self.assertEqual(prepared.actor_id, origin.actor_id)
        self.assertEqual(prepared.id, prepared.result.source.id)
        validate(source, origin, prepared)

    def test_preparation_requires_typed_origin_not_raw_proof_or_step(self):
        _, _, _, origin, prepared, _ = casting_chain()
        for witness in (None, origin, origin.after.pending_miscast, origin.result.source, object()):
            with self.subTest(witness=type(witness)), self.assertRaises(TypeError):
                Step(prepared.result, origin_witness=witness)

    def test_nonpreparation_steps_cannot_carry_origin_witness(self):
        _, journal, _, origin, prepared, rolled = casting_chain()
        effect = wind(rolled)
        ended = Step(end_npc_roster_prone_turn(NpcRosterProneTurnEndRequest(
            journal.source.id + ':end', effect.after, 'wizard', ())))
        stood = Step(stand_npc_roster_prone(stand_request()))
        for step in (journal.steps[0], origin, rolled, effect, ended, stood):
            with self.subTest(result=type(step.result)), self.assertRaises(ValueError):
                replace(step, origin_witness=prepared.origin_witness)

    def test_origin_must_match_complete_preparation_owner(self):
        _, _, _, origin, prepared, _ = casting_chain()
        _, _, owner = wounded_broken_wizard(2)
        other = execute_npc_broken_recover(wizard_recovery(owner), SequenceRandom((10, 10, 10)))
        with self.assertRaises(ValueError):
            replace(prepared, origin_witness=other)
        with self.assertRaises(ValueError):
            Step(preparation(other).result, origin_witness=origin.result)

    def test_recover_and_run_are_real_accepted_interruption_witnesses(self):
        source, *_ = casting_chain()
        _, _, owner = wounded_broken_wizard(2)
        results = (
            execute_npc_broken_recover(wizard_recovery(owner), SequenceRandom((10, 10, 10))),
            execute_npc_broken_run(from_owner(owner, owner.wizard.actor_id)),
        )
        for result in results:
            with self.subTest(origin=type(result)):
                step = preparation(result)
                self.assertEqual(step.before.pending_interruption, result.interruption)
                self.assertEqual(step.before, result.state)
                validate(source, Step(result), step)

    def test_equal_poststate_recover_substitution_fails_immediate_witness_guard(self):
        source, *_ = casting_chain()
        _, _, owner = wounded_broken_wizard(2)
        request = wizard_recovery(owner)
        first = execute_npc_broken_recover(request, SequenceRandom((10, 10, 10)))
        second = execute_npc_broken_recover(request, SequenceRandom((9, 9, 9)))
        self.assertNotEqual(first, second)
        self.assertEqual(first.state, second.state)
        self.assertEqual(first.interruption, second.interruption)
        prepared = preparation(first)
        # Standalone evidence is valid; only the predecessor knows which real
        # Recover trace the journal actually published.
        substituted = replace(prepared, origin_witness=second)
        validate(source, Step(first), prepared)
        with self.assertRaises(ValueError):
            validate(source, Step(first), substituted)

    def test_all_three_mandatory_phases_require_immediate_matching_predecessor(self):
        source, journal, _, origin, prepared, rolled = casting_chain()
        effect = wind(rolled)
        for previous, step in ((origin, prepared), (prepared, rolled), (rolled, effect)):
            validate(source, previous, step)
            for wrong in (None, journal.steps[0], effect):
                with self.subTest(step=type(step.result), previous=type(wrong)), self.assertRaises(ValueError):
                    validate(source, wrong, step)

    def test_supported_mandatory_phases_cannot_be_skipped_or_end_journal(self):
        source, journal, _, origin, prepared, rolled = casting_chain()
        for previous in (origin, prepared, rolled):
            with self.subTest(previous=type(previous.result)):
                with self.assertRaises(ValueError):
                    validate(source, previous, None)
                with self.assertRaises(ValueError):
                    validate(source, previous, journal.steps[0])

    def test_legacy_allows_raw_tail_but_rejects_new_phases(self):
        _, journal, diagnosis, origin, prepared, rolled = casting_chain()
        legacy = journal.source
        validate(legacy, origin, None)
        self.assertEqual(journal.result(diagnosis).current, origin.after)
        for previous, step in ((origin, prepared), (prepared, rolled), (rolled, wind(rolled))):
            with self.subTest(phase=type(step.result)), self.assertRaises(ValueError):
                validate(legacy, previous, step)

    def test_other_table_row_is_a_complete_exact_stop_without_pool_cleanup(self):
        source, journal, _, origin, prepared, rolled = casting_chain((10, 10, 10))
        validate(source, prepared, rolled)
        validate(source, rolled, None)
        stop = diagnose_npc_magic_unsupported(source, rolled.after, rolled.id)
        self.assertIs(stop.reason, NpcMagicUnsupportedReason.MISCAST_EFFECT)
        self.assertEqual(stop.source_id, rolled.result.effect_request.resolution_id)
        result = NpcMagicScenarioResult(source, (*journal.steps, prepared, rolled), stop)
        self.assertEqual(result.current.wizard.magic_state.miscast_dice, 3)
        self.assertEqual(result.current.pending_miscast_continuation, rolled.result)
        self.assertEqual(result.executed_actions, 1)

    def test_result_validator_rejects_opted_raw_and_prepared_tails(self):
        source, journal, diagnosis, _, prepared, _ = casting_chain()
        with self.assertRaises(ValueError):
            NpcMagicScenarioResult(source, journal.steps, diagnosis)
        stop = diagnose_npc_magic_unsupported(source, prepared.after, prepared.id)
        with self.assertRaises(ValueError):
            NpcMagicScenarioResult(source, (*journal.steps, prepared), stop)

    def test_result_validator_rejects_legacy_prepared_and_rolled_journal(self):
        _, journal, _, _, prepared, rolled = casting_chain((10, 10, 10))
        for suffix in ((prepared,), (prepared, rolled)):
            current = suffix[-1]
            stop = diagnose_npc_magic_unsupported(journal.source, current.after, current.id)
            with self.subTest(length=len(suffix)), self.assertRaises(ValueError):
                NpcMagicScenarioResult(journal.source, (*journal.steps, *suffix), stop)

    def test_roll_and_effect_canonical_ids_and_receipts_are_preserved(self):
        source, _, _, origin, prepared, rolled = casting_chain()
        effect = wind(rolled)
        self.assertEqual(rolled.id, prepared.result.roll_request.resolution_id)
        self.assertEqual(effect.id, rolled.result.effect_request.resolution_id + ':apply')
        for step in (prepared, rolled, effect):
            self.assertEqual(step.after.consumed_execution_ids, origin.after.consumed_execution_ids)
            self.assertEqual(step.after.round_state, origin.after.round_state)
        for step in (rolled, effect):
            with self.assertRaises(ValueError):
                replace(step.result.source, id=source.id + ':wrong')

    def test_full_journal_rejects_foreign_and_colliding_preparation_ids(self):
        source, journal, _, _, _, _ = casting_chain()
        for identifier in ('foreign:prepare', journal.steps[0].id, journal.steps[0].id + ':slot'):
            _, _, _, _, prepared, rolled = casting_chain((10, 10, 10), identifier=identifier)
            stop = diagnose_npc_magic_unsupported(source, rolled.after, rolled.id)
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                NpcMagicScenarioResult(source, (*journal.steps, prepared, rolled), stop)

    def test_full_journal_rejects_skipped_source_chain(self):
        source, journal, _, _, _, rolled = casting_chain((10, 10, 10))
        stop = diagnose_npc_magic_unsupported(source, rolled.after, rolled.id)
        with self.assertRaises(ValueError):
            NpcMagicScenarioResult(source, (*journal.steps, rolled), stop)

    def test_steps_are_frozen_slotted_and_pickle_preserves_full_witness(self):
        _, _, _, origin, prepared, rolled = casting_chain()
        for step in (origin, prepared, rolled, wind(rolled)):
            self.assertFalse(hasattr(step, '__dict__'))
            self.assertEqual(deepcopy(step), step)
            self.assertEqual(pickle.loads(pickle.dumps(step)), step)
            self.assertEqual(replace(step), step)
            with self.assertRaises(FrozenInstanceError):
                step.origin_witness = None


if __name__ == '__main__':
    unittest.main()
