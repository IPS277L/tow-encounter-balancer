"""ADR-0051 explicit family permission survives every full subset projection."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_candidate_generation import collapse_request, invalid_broken_request
from tests.unit.test_m8_magic_candidate_generation_models import request
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario import scenario
from towr.application import magic_candidate_generation as generation
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
from towr.application.magic_candidate_generation_models import (
    MagicCandidateGenerationRequest as Request, MagicCandidateGenerationResult as Result,
    MagicCompositionGroup as Group,
)
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.npc_magic_scenario_models import NpcMagicStationaryWoundPolicy as Policy
from towr.domain.turn_models import CombatSide
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest


POLICY = Policy.LEG_SPASM_STAND_AND_CONTINUE


def family(source=None, *, miscast=None, stationary=POLICY):
    source = request() if source is None else source
    return replace(source, template_scenario=replace(source.template_scenario,
        miscast_continuation=miscast, stationary_wound_continuation=stationary),
        miscast_continuation=miscast, stationary_wound_continuation=stationary)


class Unreadable(list):
    def __iter__(self):
        raise AssertionError('permission preflight must precede collection materialization')


def tampered_nested_source(source, case):
    """Model a transported frozen object whose nested constructors were bypassed."""
    corrupted = deepcopy(source)
    if case == 'family facts':
        object.__setattr__(corrupted.facts, 'no_external_condition_sources', False)
    elif case == 'template facts':
        object.__setattr__(corrupted.template_scenario.facts, 'no_external_condition_sources', False)
    elif case == 'group bool':
        object.__setattr__(corrupted.groups[0], 'minimum_count', True)
    elif case == 'stage bool':
        object.__setattr__(corrupted.stages[0], 'keep', True)
    elif case == 'window float':
        object.__setattr__(corrupted.window, 'target', 0.5)
    else:
        raise AssertionError('unknown authored corruption')
    return corrupted


class StationaryWoundGenerationTests(unittest.TestCase):
    def test_all_four_combinations_preserve_every_ordered_source_and_seed(self):
        legacy = request()
        baseline = generation.generate_magic_candidates(legacy)
        rng_before = getstate()
        with patch('random.Random', side_effect=AssertionError('generation must not use RNG')):
            for miscast in (None, continuation_policy()):
                for stationary in (None, POLICY):
                    source = family(legacy, miscast=miscast, stationary=stationary)
                    before = deepcopy(source)
                    actual = generation.generate_magic_candidates(source)
                    self.assertIs(actual.source_request, source)
                    self.assertEqual((source.candidate_count, source.planned_trials), (4, 240))
                    self.assertEqual(tuple(c.candidate_id for c in actual.evaluation_request.candidates),
                        tuple(f'family:counts:{v}' for v in ('1,0', '1,1', '2,0', '2,1')))
                    self.assertEqual(replace(actual.evaluation_request,
                        candidates=baseline.evaluation_request.candidates), baseline.evaluation_request)
                    for expected, candidate in zip(baseline.evaluation_request.candidates,
                                                    actual.evaluation_request.candidates, strict=True):
                        with self.subTest(miscast=miscast is not None, stationary=stationary,
                                          candidate=candidate.candidate_id):
                            self.assertEqual(candidate.scenario, replace(expected.scenario,
                                miscast_continuation=miscast, stationary_wound_continuation=stationary))
                            self.assertIs(candidate.scenario.stationary_wound_continuation, stationary)
                            self.assertIs(candidate.scenario.miscast_continuation, source.miscast_continuation)
                            a = NpcMagicSimulationRequest(expected.scenario, source.master_seed, 3)
                            b = NpcMagicSimulationRequest(candidate.scenario, source.master_seed, 3)
                            self.assertEqual(tuple(a.seed_for(i) for i in range(3)),
                                             tuple(b.seed_for(i) for i in range(3)))
                    self.assertEqual(source, before)
        self.assertEqual(getstate(), rng_before)

    def test_both_wizard_sides_and_perspectives_keep_fixed_wizard_and_family_permissions(self):
        for wizard_side in CombatSide:
            for perspective in CombatSide:
                template = scenario(wizard_side=wizard_side, perspective=perspective)
                variable = 'enemy' if wizard_side is perspective else 'ally'
                legacy = Request(template, (Group('variable', (variable,), 0, 1),),
                    replace(template.facts), template.scene_frames, 'mirror', 1, 42,
                    (MagicBalanceStage(1, 1),), 1,
                    ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)))
                baseline = generation.generate_magic_candidates(legacy).evaluation_request.candidates[0]
                for miscast in (None, continuation_policy()):
                    for stationary in (None, POLICY):
                        source = family(legacy, miscast=miscast, stationary=stationary)
                        projected = generation.generate_magic_candidates(source).evaluation_request.candidates[0]
                        with self.subTest(wizard=wizard_side, perspective=perspective,
                                          miscast=miscast is not None, stationary=stationary):
                            self.assertEqual(source.candidate_count, 1)
                            self.assertIs(projected.scenario.initial.wizard, template.initial.wizard)
                            self.assertEqual(projected.scenario.perspective_side, perspective)
                            self.assertEqual(projected.scenario.objective, template.objective)
                            self.assertEqual(projected.scenario, replace(baseline.scenario,
                                miscast_continuation=miscast, stationary_wound_continuation=stationary))

    def test_append_last_none_preserves_both_old_positional_forms(self):
        source = request()
        names = tuple(f.name for f in fields(source))
        self.assertEqual(names[-2:], ('miscast_continuation', 'stationary_wound_continuation'))
        self.assertIsNone(fields(source)[-1].default)
        original = tuple(getattr(source, name) for name in names[:-2])
        values = (Request(*original), Request(*original, None), Request(*original, None, None))
        baseline = generation.generate_magic_candidates(source)
        for value in values:
            self.assertEqual(value, source)
            self.assertEqual(generation.generate_magic_candidates(value), baseline)
        miscast = continuation_policy()
        template = replace(source.template_scenario, miscast_continuation=miscast)
        old_opted = Request(template, *original[1:], miscast)
        self.assertIsNone(old_opted.stationary_wound_continuation)
        self.assertEqual(old_opted, family(source, miscast=miscast, stationary=None))

    def test_omitted_family_permission_never_inherits_opted_template(self):
        source = request()
        values = {f.name: getattr(source, f.name) for f in fields(source)
                  if f.name != 'stationary_wound_continuation'}
        values['template_scenario'] = replace(source.template_scenario,
                                              stationary_wound_continuation=POLICY)
        with self.assertRaises(ValueError): Request(**values)

    def test_mismatch_both_directions_fails_before_collections_or_projection(self):
        legacy = request()
        with ExitStack() as stack:
            spies = [stack.enter_context(patch.object(generation, name,
                side_effect=AssertionError('no enumeration or projection'))) for name in
                ('_count_vectors', '_project_candidate', '_project_frames')]
            for template_value, family_value in ((None, POLICY), (POLICY, None)):
                template = replace(legacy.template_scenario, stationary_wound_continuation=template_value)
                with self.subTest(template=template_value, family=family_value), self.assertRaises(ValueError):
                    replace(legacy, template_scenario=template, stationary_wound_continuation=family_value,
                        groups=Unreadable(legacy.groups), scene_frames=Unreadable(legacy.scene_frames),
                        stages=Unreadable(legacy.stages))
            for spy in spies: spy.assert_not_called()

    def test_raw_stationary_family_and_template_types_cannot_pass_enum_equality(self):
        source = family()
        for value in (POLICY.value, True, False, 1, 0, {}, continuation_policy(),
                      continuation_policy().prone_policy):
            with self.subTest(role='family', value=value), self.assertRaises(TypeError):
                replace(source, stationary_wound_continuation=value)
            template = deepcopy(source.template_scenario)
            object.__setattr__(template, 'stationary_wound_continuation', value)
            with self.subTest(role='template', value=value), self.assertRaises(TypeError):
                replace(source, template_scenario=template)

    def test_nested_miscast_choice_fact_and_prone_policy_are_revalidated_before_equality(self):
        source = family(miscast=continuation_policy())
        for name, raw in (('choice', source.miscast_continuation.choice.value),
                          ('prone_policy', source.miscast_continuation.prone_policy.value),
                          ('facts', None)):
            corrupted = deepcopy(source.miscast_continuation)
            if name == 'facts':
                object.__setattr__(corrupted.facts, 'all_combatants_in_roster', 1)
            else:
                object.__setattr__(corrupted, name, raw)
            self.assertEqual(corrupted, source.miscast_continuation)
            with self.subTest(role='family', field=name), self.assertRaises(TypeError):
                replace(source, miscast_continuation=corrupted)
            template = replace(source.template_scenario)
            object.__setattr__(template, 'miscast_continuation', corrupted)
            with self.subTest(role='template', field=name), self.assertRaises(TypeError):
                replace(source, template_scenario=template)

    def test_factory_revalidates_pickled_forged_source_before_count_vectors(self):
        source = family()
        variants = []
        for family_value in (None, POLICY.value):
            bad = deepcopy(source)
            object.__setattr__(bad, 'stationary_wound_continuation', family_value)
            variants.append((bad, ValueError if family_value is None else TypeError))
        bad = deepcopy(source)
        object.__setattr__(bad.template_scenario, 'stationary_wound_continuation', POLICY.value)
        variants.append((bad, TypeError))
        bad = deepcopy(source)
        object.__setattr__(bad, 'max_candidates', True)
        variants.append((bad, TypeError))
        for bad, error in variants:
            bad = pickle.loads(pickle.dumps(bad))
            with (self.subTest(error=error.__name__),
                  patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as counts,
                  patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project):
                with self.assertRaises(error): generation.generate_magic_candidates(bad)
                counts.assert_not_called()
                project.assert_not_called()

    def test_source_rebuild_rejects_normalization_without_mutating_original(self):
        for role, attribute in (('request', 'groups'), ('template', 'actors')):
            source = deepcopy(family())
            owner = source if role == 'request' else source.template_scenario
            object.__setattr__(owner, attribute, list(getattr(owner, attribute)))
            before = deepcopy(source)
            with (self.subTest(role=role),
                  patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration'))):
                with self.assertRaises(ValueError): generation.generate_magic_candidates(source)
            self.assertEqual(source, before)
            self.assertIs(type(getattr(owner, attribute)), list)

    def test_frozen_nested_source_models_are_readmitted_before_factory_enumeration(self):
        source = family()
        rng_before = getstate()
        for case, error in (('family facts', ValueError), ('template facts', ValueError),
                            ('group bool', TypeError), ('stage bool', TypeError),
                            ('window float', TypeError)):
            corrupted = pickle.loads(pickle.dumps(tampered_nested_source(source, case)))
            before = deepcopy(corrupted)
            with (self.subTest(case=case),
                  patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as counts,
                  patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project):
                with self.assertRaises(error): replace(corrupted)
                with self.assertRaises(error): generation.generate_magic_candidates(corrupted)
                counts.assert_not_called()
                project.assert_not_called()
            self.assertEqual(corrupted, before)
        self.assertEqual(source, family())
        self.assertEqual(getstate(), rng_before)

    def test_result_source_rebuild_rejects_tampered_nested_models_before_reconstruction(self):
        result = generation.generate_magic_candidates(family())
        for case, error in (('family facts', ValueError), ('template facts', ValueError),
                            ('group bool', TypeError), ('stage bool', TypeError),
                            ('window float', TypeError)):
            corrupted = tampered_nested_source(result.source_request, case)
            before = deepcopy(corrupted)
            with (self.subTest(case=case),
                  patch.object(generation, '_count_vectors', side_effect=AssertionError('no reconstruction')) as counts):
                with self.assertRaises(error): Result(corrupted, result.evaluation_request)
                counts.assert_not_called()
            self.assertEqual(corrupted, before)

    def test_result_revalidates_source_before_expected_projection(self):
        result = generation.generate_magic_candidates(family())
        for name, raw, error in (('stationary_wound_continuation', POLICY.value, TypeError),
                                 ('stationary_wound_continuation', None, ValueError),
                                 ('groups', list(result.source_request.groups), ValueError)):
            source = deepcopy(result.source_request)
            object.__setattr__(source, name, raw)
            with (self.subTest(field=name, raw=raw),
                  patch.object(generation, '_count_vectors', side_effect=AssertionError('no reconstruction')) as counts):
                with self.assertRaises(error): Result(source, result.evaluation_request)
                counts.assert_not_called()

    def test_candidate_raw_enum_is_rejected_before_equality_with_canonical_projection(self):
        result = generation.generate_magic_candidates(family())
        first = result.evaluation_request.candidates[0]
        corrupted = deepcopy(first)
        object.__setattr__(corrupted.scenario, 'stationary_wound_continuation', POLICY.value)
        self.assertEqual(corrupted, first)
        with patch.object(generation, '_project_candidate', side_effect=AssertionError('reject before comparison')) as project:
            with self.assertRaises(TypeError):
                evaluation = replace(result.evaluation_request,
                    candidates=(corrupted, *result.evaluation_request.candidates[1:]))
                Result(result.source_request, evaluation)
            project.assert_not_called()

    def test_same_id_policy_substitution_fails_at_every_candidate_position(self):
        for opted in (False, True):
            result = generation.generate_magic_candidates(family(stationary=POLICY if opted else None))
            for index, candidate in enumerate(result.evaluation_request.candidates):
                substitute = replace(candidate, scenario=replace(candidate.scenario,
                    stationary_wound_continuation=None if opted else POLICY))
                self.assertEqual(substitute.candidate_id, candidate.candidate_id)
                evaluation = replace(result.evaluation_request, candidates=tuple(
                    substitute if n == index else c for n, c in enumerate(result.evaluation_request.candidates)))
                with self.subTest(opted=opted, index=index), self.assertRaises(ValueError):
                    Result(result.source_request, evaluation)

    def test_same_id_full_source_substitution_is_rejected_both_directions(self):
        legacy, opted = family(stationary=None), family()
        a, b = generation.generate_magic_candidates(legacy), generation.generate_magic_candidates(opted)
        for source, evaluation in ((legacy, b.evaluation_request), (opted, a.evaluation_request)):
            with self.subTest(opted=source.stationary_wound_continuation is not None), self.assertRaises(ValueError):
                Result(source, evaluation)

    def test_equal_distinct_full_miscast_family_copy_is_used_and_models_are_immutable(self):
        source = family(miscast=continuation_policy())
        miscast = replace(source.miscast_continuation, facts=replace(source.miscast_continuation.facts))
        source = replace(source, miscast_continuation=miscast)
        self.assertIsNot(source.miscast_continuation, source.template_scenario.miscast_continuation)
        result = generation.generate_magic_candidates(source)
        self.assertTrue(all(c.scenario.miscast_continuation is miscast
                            for c in result.evaluation_request.candidates))
        self.assertEqual(Result(deepcopy(source), deepcopy(result.evaluation_request)), result)
        for value, field in ((source, 'stationary_wound_continuation'), (result, 'source_request')):
            self.assertFalse(hasattr(value, '__dict__'))
            self.assertEqual(replace(value), value)
            self.assertEqual(pickle.loads(pickle.dumps(value)), value)
            with self.assertRaises(FrozenInstanceError): setattr(value, field, None)

    def test_frame_collapse_and_late_conflicts_preserve_all_or_error_behavior(self):
        source = family(collapse_request())
        result = generation.generate_magic_candidates(source)
        self.assertEqual(tuple(len(c.scenario.scene_frames) for c in result.evaluation_request.candidates), (1, 1, 2, 2))
        for actor, counts, calls in (('blocker', (1, 0), 1), ('far-blocker', (1, 1), 2)):
            source = family(collapse_request(conflict_actor=actor))
            before = deepcopy(source)
            with (self.subTest(actor=actor), patch.object(generation, '_project_candidate',
                    wraps=generation._project_candidate) as project):
                with self.assertRaises(MagicCandidateGenerationError) as caught:
                    generation.generate_magic_candidates(source)
                self.assertEqual(caught.exception.counts, counts)
                self.assertIs(type(caught.exception.__cause__), ValueError)
                self.assertIn('conflicting', str(caught.exception.__cause__))
                self.assertEqual(project.call_count, calls)
            self.assertEqual(source, before)

    def test_invalid_broken_projection_is_not_repaired_by_both_permissions(self):
        source = family(invalid_broken_request(), miscast=continuation_policy())
        before = deepcopy(source)
        with self.assertRaises(MagicCandidateGenerationError) as caught:
            generation.generate_magic_candidates(source)
        self.assertEqual(caught.exception.counts, (1, 0))
        self.assertIn('already safe', str(caught.exception.__cause__))
        self.assertEqual(source, before)

    def test_late_admission_failure_preserves_exact_cause_counts_and_both_policies_without_rng(self):
        source = family(miscast=continuation_policy())
        before, rng_before = deepcopy(source), getstate()
        original = generation.NpcMagicScenario
        failure = OSError('late stationary admission')
        failure.add_note('authored failure evidence')
        calls = []

        def admit(*args, **kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise failure
            return original(*args, **kwargs)

        with (patch.object(generation, 'NpcMagicScenario', side_effect=admit),
              patch('random.Random', side_effect=AssertionError('no RNG'))):
            with self.assertRaises(MagicCandidateGenerationError) as caught:
                generation.generate_magic_candidates(source)
        self.assertEqual(caught.exception.candidate_id, 'family:counts:1,1')
        self.assertEqual(caught.exception.counts, (1, 1))
        self.assertIs(caught.exception.__cause__, failure)
        self.assertEqual(failure.__notes__, ['authored failure evidence'])
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(c['stationary_wound_continuation'] is POLICY for c in calls))
        self.assertTrue(all(c['miscast_continuation'] is source.miscast_continuation for c in calls))
        self.assertEqual(source, before)
        self.assertEqual(getstate(), rng_before)


if __name__ == '__main__':
    unittest.main()
