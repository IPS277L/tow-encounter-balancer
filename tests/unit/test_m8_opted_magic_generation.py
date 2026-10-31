"""ADR-0047 native family admission and lossless opted subset projections."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_candidate_generation import (
    collapse_request, invalid_broken_request,
)
from tests.unit.test_m8_magic_candidate_generation_models import request
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario import scenario
from towr.application import magic_candidate_generation as generation
from towr.application.magic_candidate_generation_models import (
    MagicCandidateGenerationRequest as Request,
    MagicCandidateGenerationResult as Result,
    MagicCompositionGroup as Group,
)
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.turn_models import CombatSide
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest


def opted_request(source=None):
    source = request() if source is None else source
    policy = continuation_policy()
    return replace(source, template_scenario=replace(
        source.template_scenario, miscast_continuation=policy),
        miscast_continuation=policy)


class OptedMagicGenerationTests(unittest.TestCase):
    def test_append_last_default_none_preserves_old_positional_calls_and_output(self):
        source = request()
        names = tuple(field.name for field in fields(source))
        self.assertEqual(names[-1], 'miscast_continuation')
        self.assertIsNone(fields(source)[-1].default)
        arguments = tuple(getattr(source, name) for name in names[:-1])
        implicit, explicit = Request(*arguments), Request(*arguments, None)
        self.assertEqual(implicit, explicit)
        self.assertEqual(implicit, source)
        self.assertEqual(generation.generate_magic_candidates(implicit),
                         generation.generate_magic_candidates(explicit))
        self.assertTrue(all(candidate.scenario.miscast_continuation is None
                            for candidate in generation.generate_magic_candidates(source)
                            .evaluation_request.candidates))

    def test_type_and_template_equality_fail_before_collections_or_projection(self):
        legacy = request()
        policy = continuation_policy()
        opted = replace(legacy.template_scenario, miscast_continuation=policy)

        class UnreadableList(list):
            def __iter__(self):
                raise AssertionError('family policy must be checked first')

        forbidden = ('_count_vectors', '_project_candidate', '_project_frames')
        with ExitStack() as stack:
            spies = [stack.enter_context(patch.object(generation, name,
                     side_effect=AssertionError('no projection in preflight')))
                     for name in forbidden]
            for template, value, error in (
                (opted, None, ValueError),
                (legacy.template_scenario, policy, ValueError),
                *((template, value, TypeError)
                  for template in (legacy.template_scenario, opted)
                  for value in (True, False, 'decline_cast_before_miscast', {},
                                policy.facts, legacy.facts, policy.choice,
                                policy.prone_policy)),
            ):
                with self.subTest(template=template.miscast_continuation, value=value):
                    with self.assertRaises(error):
                        replace(legacy, template_scenario=template,
                                miscast_continuation=value,
                                groups=UnreadableList(legacy.groups),
                                scene_frames=UnreadableList(legacy.scene_frames),
                                stages=UnreadableList(legacy.stages))
            for spy in spies:
                spy.assert_not_called()

    def test_omitted_family_policy_does_not_inherit_opted_template(self):
        source = request()
        names = tuple(field.name for field in fields(source))[:-1]
        values = {name: getattr(source, name) for name in names}
        values['template_scenario'] = replace(source.template_scenario,
                                             miscast_continuation=continuation_policy())
        with self.assertRaises(ValueError):
            Request(**values)

    def test_equal_independent_policy_copy_is_used_for_every_generated_source(self):
        source = opted_request()
        family = replace(source.miscast_continuation,
                         facts=replace(source.miscast_continuation.facts))
        source = replace(source, miscast_continuation=family)
        self.assertIsNot(family, source.template_scenario.miscast_continuation)
        self.assertIsNot(family.facts, source.template_scenario.miscast_continuation.facts)
        self.assertEqual(family, source.template_scenario.miscast_continuation)
        result = generation.generate_magic_candidates(source)
        for candidate in result.evaluation_request.candidates:
            self.assertIs(candidate.scenario.miscast_continuation, family)
        self.assertEqual(Result(deepcopy(source), deepcopy(result.evaluation_request)), result)

    def test_four_vectors_are_exact_legacy_sources_plus_full_policy_with_same_seeds(self):
        legacy = request()
        source = opted_request(legacy)
        before = deepcopy(source)
        old = generation.generate_magic_candidates(legacy)
        result = generation.generate_magic_candidates(source)
        self.assertEqual((source.candidate_count, source.planned_trials), (4, 240))
        self.assertEqual(tuple(c.candidate_id for c in result.evaluation_request.candidates),
                         tuple('family:counts:' + counts for counts in ('1,0', '1,1', '2,0', '2,1')))
        self.assertEqual(replace(result.evaluation_request, candidates=old.evaluation_request.candidates),
                         old.evaluation_request)
        for previous, candidate in zip(old.evaluation_request.candidates,
                                       result.evaluation_request.candidates, strict=True):
            self.assertEqual(replace(candidate.scenario, miscast_continuation=None), previous.scenario)
            self.assertEqual(candidate.scenario.miscast_continuation, source.miscast_continuation)
            self.assertEqual(len(fields(candidate.scenario.miscast_continuation.facts)), 5)
            first = NpcMagicSimulationRequest(previous.scenario, source.master_seed, 3)
            second = NpcMagicSimulationRequest(candidate.scenario, source.master_seed, 3)
            self.assertEqual(tuple(first.seed_for(i) for i in range(3)),
                             tuple(second.seed_for(i) for i in range(3)))
            self.assertIsNone(candidate.scenario.initial.pending_miscast)
            self.assertEqual(candidate.scenario.initial.wizard.magic_state.miscast_dice, 0)
        self.assertEqual(source, before)

    def test_both_wizard_sides_and_perspectives_keep_policy_and_fixed_wizard(self):
        for wizard_side in CombatSide:
            for perspective in CombatSide:
                with self.subTest(wizard_side=wizard_side, perspective=perspective):
                    template = scenario(wizard_side=wizard_side, perspective=perspective)
                    variable = 'enemy' if wizard_side is perspective else 'ally'
                    legacy = Request(template, (Group('variable', (variable,), 0, 1),),
                        replace(template.facts), template.scene_frames, 'mirror', 1, 42,
                        (MagicBalanceStage(1, 1),), 1,
                        ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)))
                    source = opted_request(legacy)
                    result = generation.generate_magic_candidates(source)
                    projected = result.evaluation_request.candidates[0].scenario
                    self.assertIs(projected.initial.wizard, template.initial.wizard)
                    self.assertEqual(projected.perspective_side, perspective)
                    self.assertEqual(projected.objective, template.objective)
                    self.assertIs(projected.miscast_continuation, source.miscast_continuation)
                    expected = generation.generate_magic_candidates(legacy).evaluation_request.candidates[0].scenario
                    self.assertEqual(replace(projected, miscast_continuation=None), expected)

    def test_request_and_result_are_frozen_slotted_replace_and_pickle_safe(self):
        source = opted_request()
        result = generation.generate_magic_candidates(source)
        for value, attribute in ((source, 'miscast_continuation'), (result, 'source_request')):
            with self.subTest(type=type(value)):
                self.assertFalse(hasattr(value, '__dict__'))
                self.assertEqual(replace(value), value)
                self.assertEqual(deepcopy(value), value)
                self.assertEqual(pickle.loads(pickle.dumps(value)), value)
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, attribute, None)

    def test_same_id_none_candidate_substitution_rejected_at_every_position(self):
        result = generation.generate_magic_candidates(opted_request())
        evaluation = result.evaluation_request
        for index, candidate in enumerate(evaluation.candidates):
            substitute = replace(candidate, scenario=replace(candidate.scenario, miscast_continuation=None))
            changed = replace(evaluation, candidates=tuple(
                substitute if n == index else old for n, old in enumerate(evaluation.candidates)))
            self.assertEqual(substitute.candidate_id, candidate.candidate_id)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'exact source projection'):
                replace(result, evaluation_request=changed)

    def test_same_id_source_substitution_is_rejected_in_both_directions(self):
        legacy = request()
        opted = opted_request(legacy)
        legacy_result = generation.generate_magic_candidates(legacy)
        opted_result = generation.generate_magic_candidates(opted)
        for result, foreign in ((opted_result, legacy), (legacy_result, opted)):
            with self.subTest(opted=result.source_request.miscast_continuation is not None):
                with self.assertRaisesRegex(ValueError, 'exact source projection'):
                    replace(result, source_request=foreign)

    def test_equal_projected_frames_still_collapse_with_full_policy(self):
        source = opted_request(collapse_request())
        candidates = generation.generate_magic_candidates(source).evaluation_request.candidates
        self.assertEqual(tuple(len(c.scenario.scene_frames) for c in candidates), (1, 1, 2, 2))
        self.assertTrue(all(c.scenario.miscast_continuation == source.miscast_continuation
                            for c in candidates))

    def test_early_and_late_conflicts_fail_without_skipping_opted_candidates(self):
        for actor, counts, calls in (('blocker', (1, 0), 1), ('far-blocker', (1, 1), 2)):
            source = opted_request(collapse_request(conflict_actor=actor))
            with self.subTest(actor=actor), patch.object(generation, '_project_candidate',
                    wraps=generation._project_candidate) as project:
                with self.assertRaises(MagicCandidateGenerationError) as caught:
                    generation.generate_magic_candidates(source)
            self.assertEqual(caught.exception.counts, counts)
            self.assertEqual(caught.exception.candidate_id, 'family:counts:' + ','.join(map(str, counts)))
            self.assertIs(type(caught.exception.__cause__), ValueError)
            self.assertIn('conflicting', str(caught.exception.__cause__))
            self.assertEqual(project.call_count, calls)

    def test_invalid_broken_route_is_not_repaired_by_opt_in(self):
        source = opted_request(invalid_broken_request())
        before = deepcopy(source)
        with self.assertRaises(MagicCandidateGenerationError) as caught:
            generation.generate_magic_candidates(source)
        self.assertEqual(caught.exception.counts, (1, 0))
        self.assertIs(type(caught.exception.__cause__), ValueError)
        self.assertIn('already safe', str(caught.exception.__cause__))
        self.assertEqual(source, before)

    def test_late_admission_failure_preserves_cause_notes_counts_and_policy(self):
        source = opted_request()
        original = generation.NpcMagicScenario
        error = OSError('late opted admission')
        error.add_note('authored failure note')
        calls = []

        def admit(*args, **kwargs):
            calls.append((kwargs['id'], kwargs['miscast_continuation']))
            if len(calls) == 2:
                raise error
            return original(*args, **kwargs)

        with patch.object(generation, 'NpcMagicScenario', side_effect=admit):
            with self.assertRaises(MagicCandidateGenerationError) as caught:
                generation.generate_magic_candidates(source)
        self.assertEqual(caught.exception.counts, (1, 1))
        self.assertEqual(caught.exception.candidate_id, 'family:counts:1,1')
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(error.__notes__, ['authored failure note'])
        self.assertEqual(calls, [('family:counts:1,0', source.miscast_continuation),
                                 ('family:counts:1,1', source.miscast_continuation)])

    def test_preflight_never_enumerates_and_generation_never_runs_rng_or_pool(self):
        source = opted_request()
        before, rng_before = deepcopy(source), getstate()
        with (patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')),
              patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection'))):
            self.assertEqual(replace(source), source)
        forbidden = ('random.Random', 'random.randint',
            'towr.engine.npc_magic_scenario_runner.run_npc_magic_scenario',
            'towr.simulation.npc_magic_simulation.run_npc_magic_simulation',
            'towr.application.magic_evaluation_service.evaluate_magic_candidates',
            'towr.application.magic_staged_evaluation_service.evaluate_magic_candidates_staged',
            'concurrent.futures.ProcessPoolExecutor', 'builtins.open')
        with ExitStack() as stack:
            for target in forbidden:
                stack.enter_context(patch(target, side_effect=AssertionError('forbidden: ' + target)))
            result = generation.generate_magic_candidates(source)
            self.assertEqual(Result(source, result.evaluation_request), result)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), rng_before)


if __name__ == '__main__':
    unittest.main()
