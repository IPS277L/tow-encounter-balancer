"""ADR-0038 pure admission, compact observations and versioned seeds."""
from dataclasses import FrozenInstanceError, fields, replace
from hashlib import sha256
from struct import pack
import unittest

from tests.unit.test_m8_npc_magic_scenario_runner import admitted
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.simulation.npc_magic_models import (
    SEED_SCHEME, NpcMagicOutcomeCounts, NpcMagicSimulationRequest,
    NpcMagicSimulationResult, NpcMagicTrialRecord, npc_magic_trial_seed,
)


def request(trials=4, budget=3):
    return NpcMagicSimulationRequest(replace(admitted(), max_rounds=budget), 42, trials)


def observations(source):
    budget = source.scenario.max_rounds
    rows = ((Outcome.OBJECTIVE_ACHIEVED, 1, 1, 0),
            (Outcome.PERSPECTIVE_DEFEATED, 2, 1, 1),
            (Outcome.ROUND_LIMIT_REACHED, budget, budget, budget),
            (Outcome.UNSUPPORTED_PATH, 0, 1, 0))
    return tuple(NpcMagicTrialRecord(source.scenario, index, source.seed_for(index), *row)
                 for index, row in enumerate(rows))


class MagicSimulationModelTests(unittest.TestCase):
    def test_seed_vectors_independent_struct_encoding_and_family_separation(self):
        from towr.simulation.npc_ranged_models import npc_ranged_trial_seed
        from towr.simulation.npc_melee_models import npc_melee_trial_seed
        from towr.simulation.npc_mixed_models import npc_mixed_trial_seed
        self.assertEqual(SEED_SCHEME, 'towr:npc-magic-trial:v1')
        for master, index, expected in (
            (0, 0, 'fd32be1af91a33565dc651e426c0293ce371728db87f9147b0ea927de35fa60e'),
            (42, 7, '0b95a33629128179ab8ff2862038f7c1331078d98dcb552fce2037bf90581dac'),
            (2**64-1, 2**64-1, 'ce26ddf15185ed7cbff2fb2e86929fe80c7eb0f531eacc02a59430860ceebb34'),
        ):
            with self.subTest(master=master, index=index):
                value = npc_magic_trial_seed(master, index)
                self.assertEqual(value, int(expected, 16))
                self.assertEqual(sha256(SEED_SCHEME.encode('ascii') + b'\0' + pack('>QQ', master, index)).hexdigest(), expected)
                self.assertNotIn(value, tuple(fn(master, index) for fn in (
                    npc_ranged_trial_seed, npc_melee_trial_seed, npc_mixed_trial_seed)))

    def test_seed_rejects_types_separately_from_uint64_ranges(self):
        for name in ('master_seed', 'trial_index'):
            for value in (True, False, 1.0, '1', None, object()):
                args = {'master_seed': 0, 'trial_index': 0, name: value}
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    npc_magic_trial_seed(**args)
            for value in (-1, 2**64):
                args = {'master_seed': 0, 'trial_index': 0, name: value}
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    npc_magic_trial_seed(**args)

    def test_request_preserves_full_source_and_seed_has_no_size_or_id_dependency(self):
        scenario = admitted()
        source = NpcMagicSimulationRequest(scenario, 42, 4)
        self.assertIs(source.scenario, scenario)
        expanded = replace(source, trials=9)
        renamed = replace(source, scenario=replace(source.scenario, id='other:id'))
        self.assertEqual(tuple(source.seed_for(i) for i in range(4)),
                         tuple(expanded.seed_for(i) for i in range(4)))
        self.assertEqual(source.seed_for(2), renamed.seed_for(2))
        self.assertNotEqual(source.seed_for(0), source.seed_for(1))
        self.assertNotEqual(source.seed_for(0), replace(source, master_seed=43).seed_for(0))
        huge = replace(source, trials=2**64-1, master_seed=2**64-1)
        self.assertEqual(huge.seed_for(2**64-2), npc_magic_trial_seed(2**64-1, 2**64-2))

    def test_request_and_index_reject_coercion_wrong_family_and_out_of_range(self):
        from tests.unit.test_m7_npc_mixed_simulation import request as mixed_request
        source = request()
        for value in (None, {}, 'scenario', source.scenario.initial, mixed_request().scenario):
            with self.subTest(value=type(value)), self.assertRaises(TypeError):
                replace(source, scenario=value)
        for name in ('master_seed', 'trials'):
            for value in (True, False, 1.0, '1', None):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    replace(source, **{name: value})
            for value in (-1, 2**64):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replace(source, **{name: value})
        with self.assertRaises(ValueError): replace(source, trials=0)
        self.assertEqual(replace(source, master_seed=0).master_seed, 0)
        for index in (True, False, 1.0, '1', None):
            with self.subTest(index=index), self.assertRaises(TypeError): source.seed_for(index)
        for index in (-1, source.trials, 2**64):
            with self.subTest(index=index), self.assertRaises(ValueError): source.seed_for(index)

    def test_record_keeps_input_and_scalars_only_with_equal_copy_source_allowed(self):
        source = request()
        record = observations(source)[0]
        self.assertIs(record.source_scenario, source.scenario)
        self.assertEqual(replace(record, source_scenario=replace(source.scenario)), record)
        self.assertEqual(tuple(f.name for f in fields(record)), (
            'source_scenario', 'trial_index', 'seed', 'outcome', 'executed_action_count',
            'started_round_count', 'completed_round_count'))

    def test_record_requires_magic_source_and_enum_even_when_enum_strings_equal(self):
        from tests.unit.test_m7_npc_mixed_simulation import request as mixed_request
        from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome
        record = observations(request())[0]
        self.assertEqual(record.outcome, NpcMixedScenarioOutcome.OBJECTIVE_ACHIEVED)
        for value in (None, {}, mixed_request().scenario):
            with self.subTest(source=type(value)), self.assertRaises(TypeError):
                replace(record, source_scenario=value)
        for value in (record.outcome.value, NpcMixedScenarioOutcome.OBJECTIVE_ACHIEVED, None):
            with self.subTest(outcome=value), self.assertRaises(TypeError): replace(record, outcome=value)

    def test_record_integer_types_do_not_coerce_bool_float_string_or_null(self):
        record = observations(request())[0]
        for name in ('trial_index', 'seed', 'executed_action_count', 'started_round_count', 'completed_round_count'):
            for value in (True, False, 1.0, '1', None):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    replace(record, **{name: value})

    def test_record_index_seed_ranges_and_all_counter_bounds(self):
        record = observations(request())[0]
        for changes in ({'trial_index': -1}, {'trial_index': 2**64}, {'seed': -1}, {'seed': 2**256},
                        {'executed_action_count': -1}, {'started_round_count': 0},
                        {'started_round_count': 4}, {'completed_round_count': -1},
                        {'completed_round_count': 2}, {'started_round_count': 3},
                        {'executed_action_count': 4},
                        {'executed_action_count': 1, 'started_round_count': 2, 'completed_round_count': 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): replace(record, **changes)
        self.assertEqual(replace(record, trial_index=2**64-1, seed=2**256-1).seed, 2**256-1)

    def test_terminal_outcomes_require_action_but_unsupported_allows_zero(self):
        records = observations(request())
        for record in records[:2]:
            with self.subTest(outcome=record.outcome), self.assertRaises(ValueError):
                replace(record, executed_action_count=0, completed_round_count=0)
        zero = records[3]
        self.assertEqual((zero.executed_action_count, zero.started_round_count, zero.completed_round_count), (0, 1, 0))
        with self.assertRaises(ValueError): replace(zero, completed_round_count=1)

    def test_round_limit_requires_full_started_and_completed_budget(self):
        limit = observations(request())[2]
        for changes in ({'started_round_count': 2, 'completed_round_count': 2},
                        {'completed_round_count': 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): replace(limit, **changes)
        self.assertEqual(limit.started_round_count, limit.source_scenario.max_rounds)

    def test_result_copies_list_sorts_records_and_preserves_all_four_outcomes(self):
        source = request()
        records = list(reversed(observations(source)))
        result = NpcMagicSimulationResult(source, records)
        records.clear()
        self.assertIs(result.source_request, source)
        self.assertEqual(result.trials, observations(source))
        self.assertIsInstance(result.trials, tuple)
        self.assertEqual(result.outcome_counts, NpcMagicOutcomeCounts(1, 1, 1, 1))
        self.assertEqual((result.total_action_count, result.total_started_round_count,
                          result.total_completed_round_count), (6, 6, 4))

    def test_result_accepts_equal_copies_but_rejects_same_id_different_full_source(self):
        source = request()
        records = observations(source)
        copies = tuple(replace(r, source_scenario=replace(source.scenario)) for r in records)
        self.assertEqual(NpcMagicSimulationResult(source, copies).trials, records)
        foreign = replace(source.scenario, max_rounds=4)
        self.assertEqual(foreign.id, source.scenario.id)
        with self.assertRaises(ValueError):
            NpcMagicSimulationResult(source, (replace(records[0], source_scenario=foreign), *records[1:]))

    def test_result_rejects_missing_duplicate_outside_indices_and_foreign_seeds(self):
        source = request()
        records = observations(source)
        for invalid in (records[:-1], (*records, records[0]), (records[0], *records[:-1]),
                        (replace(records[0], trial_index=4), *records[1:]),
                        (replace(records[0], seed=source.seed_for(1)), *records[1:])):
            with self.subTest(records=len(invalid)), self.assertRaises(ValueError):
                NpcMagicSimulationResult(source, invalid)
        with self.assertRaises(ValueError):
            NpcMagicSimulationResult(replace(source, master_seed=43), records)

    def test_result_rejects_unordered_or_streaming_containers_and_wrong_families(self):
        from tests.unit.test_m7_npc_mixed_simulation import request as mixed_request, observations as mixed_observations
        source = request()
        records = observations(source)
        for value in (None, {}, {0}, 'records', iter(records), (r for r in records)):
            with self.subTest(container=type(value)), self.assertRaises(TypeError):
                NpcMagicSimulationResult(source, value)
        for src, rows in ((None, records), (mixed_request(), records),
                          (source, (None,) * 4), (source, mixed_observations(mixed_request()))):
            with self.subTest(source=type(src)), self.assertRaises(TypeError):
                NpcMagicSimulationResult(src, rows)

    def test_counts_are_nonnegative_integers_and_never_merge_unsupported(self):
        counts = NpcMagicOutcomeCounts(0, 0, 0, 4)
        self.assertEqual(counts.unsupported_path, 4)
        for field in fields(counts):
            for value in (True, False, 1.0, '1', None):
                with self.subTest(field=field.name, value=value), self.assertRaises(TypeError):
                    replace(counts, **{field.name: value})
            with self.assertRaises(ValueError): replace(counts, **{field.name: -1})

    def test_all_models_frozen_and_slotted(self):
        source = request()
        result = NpcMagicSimulationResult(source, observations(source))
        for value in (source, result, result.trials[0], result.outcome_counts):
            self.assertFalse(hasattr(value, '__dict__'))
            field = fields(value)[0].name
            with self.assertRaises(FrozenInstanceError): setattr(value, field, getattr(value, field))
