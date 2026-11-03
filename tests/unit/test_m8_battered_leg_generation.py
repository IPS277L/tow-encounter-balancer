"""ADR-0062 complete Endurance profile and early family/source admission."""
from copy import deepcopy
from dataclasses import fields, replace
from fractions import Fraction
from itertools import product
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_candidate_generation_models import request, large_reserve
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_stationary_wound_generation import Unreadable
from tests.unit.test_m8_npc_magic_scenario import scenario
from towr.application import magic_candidate_generation as generation
from towr.application.magic_candidate_generation_models import (
    MagicCandidateGenerationRequest as Request, MagicCandidateGenerationResult as Result,
    MagicCompositionGroup as Group,
)
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage as Stage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as Window
from towr.domain.npc_magic_scenario_models import (
    NpcMagicBatteredLegPolicy as Policy, NpcMagicScenario,
    NpcMagicStationaryWoundPolicy as Stationary, NpcMagicRepeatedLegSpasmPolicy as Repeated,
    NpcMagicCrushedRibPolicy as Crushed,
)
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatSide
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest


POLICY = Policy(InlineProfile(2, 5))


def family(source=None, policy=POLICY, **permissions):
    original = request() if source is None else source
    # Mutation tests model detached transported objects, never the shared
    # authored fixture constant used by later tests in the same discovery run.
    values = dict(permissions, battered_leg_continuation=deepcopy(policy))
    return replace(original, template_scenario=replace(original.template_scenario, **values), **values)


class BatteredLegGenerationTests(unittest.TestCase):
    def test_24_independent_permission_combinations_preserve_complete_projection_and_seed(self):
        original = request()
        baseline = generation.generate_magic_candidates(original)
        before_rng = getstate()
        valid = invalid = 0
        with patch('random.Random', side_effect=AssertionError('pure generation')):
            for m, s, r, c, b in product((False, True), repeat=5):
                values = dict(miscast_continuation=continuation_policy() if m else None,
                    stationary_wound_continuation=Stationary.LEG_SPASM_STAND_AND_CONTINUE if s else None,
                    repeated_leg_spasm_continuation=Repeated.STAND_ONCE_WITH_JOURNAL_WITNESSES if r else None,
                    crushed_rib_continuation=Crushed.NEXT_TEST_WITH_JOURNAL_WITNESSES if c else None)
                if r and not s:
                    with self.assertRaises(ValueError): family(original, POLICY if b else None, **values)
                    invalid += 1
                    continue
                source = family(original, POLICY if b else None, **values)
                snapshot = deepcopy(source)
                generated = generation.generate_magic_candidates(source)
                for old, actual in zip(baseline.evaluation_request.candidates, generated.evaluation_request.candidates, strict=True):
                    expected = replace(old.scenario, **values, battered_leg_continuation=POLICY if b else None)
                    self.assertEqual(actual.scenario, expected)
                    self.assertEqual(NpcMagicSimulationRequest(actual.scenario, 42, 3).seed_for(2),
                                     NpcMagicSimulationRequest(old.scenario, 42, 3).seed_for(2))
                self.assertEqual((source.candidate_count, source.planned_trials), (4, 240))
                self.assertEqual(source, snapshot)
                valid += 1
        self.assertEqual((valid, invalid), (24, 8))
        self.assertEqual(getstate(), before_rng)

    def test_append_last_field_preserves_every_older_positional_form(self):
        source = request()
        names = tuple(item.name for item in fields(source))
        self.assertEqual(names[-5:], ('miscast_continuation', 'stationary_wound_continuation',
            'repeated_leg_spasm_continuation', 'crushed_rib_continuation', 'battered_leg_continuation'))
        original = tuple(getattr(source, name) for name in names[:-5])
        for count in range(6):
            self.assertEqual(Request(*original, *((None,) * count)), source)
        self.assertIsNone(fields(source)[-1].default)

    def test_full_profile_mismatch_and_omission_precede_collection_reads(self):
        legacy, opted = request(), family()
        for template, policy in ((opted.template_scenario, None), (legacy.template_scenario, POLICY),
                                 (opted.template_scenario, Policy(InlineProfile(2, 4))),
                                 (opted.template_scenario, Policy(InlineProfile(3, 5)))):
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, 'explicit family'):
                replace(legacy, template_scenario=template, battered_leg_continuation=policy,
                    groups=Unreadable(legacy.groups), stages=Unreadable(legacy.stages),
                    scene_frames=Unreadable(legacy.scene_frames))
        values = {item.name: getattr(opted, item.name) for item in fields(opted)
                  if item.name != 'battered_leg_continuation'}
        with self.assertRaises(ValueError): Request(**values)

    def test_profile_policy_and_original_nested_aliases_are_typed_before_equality(self):
        legacy = request()
        for value in (True, False, 1, {}, 'endurance', InlineProfile(2, 5)):
            with self.subTest(value=value), self.assertRaises(TypeError):
                replace(legacy, battered_leg_continuation=value)
            template = deepcopy(legacy.template_scenario)
            object.__setattr__(template, 'battered_leg_continuation', value)
            with self.assertRaises(TypeError): replace(legacy, template_scenario=template)
        for position in ('template', 'family'):
            source = family()
            policy = deepcopy(POLICY)
            object.__setattr__(policy.endurance_profile, 'dice', 2.0)
            self.assertEqual(policy, POLICY)
            if position == 'template':
                template = deepcopy(source.template_scenario)
                object.__setattr__(template, 'battered_leg_continuation', policy)
                values = {'template_scenario': template}
            else:
                values = {'battered_leg_continuation': policy}
            with self.subTest(position=position), self.assertRaises(TypeError): replace(source, **values)

    def test_profile_has_no_prototype_maximum_and_family_is_a_value_assertion(self):
        for dice, threshold in ((1, 5), (11, 5), (2, 10)):
            policy = Policy(InlineProfile(dice, threshold))
            source = family(policy=policy)
            detached = replace(source, battered_leg_continuation=deepcopy(policy))
            self.assertEqual(detached, source)
            actual = generation.generate_magic_candidates(detached)
            self.assertTrue(all(c.scenario.battered_leg_continuation == policy
                for c in actual.evaluation_request.candidates))
            self.assertEqual(pickle.loads(pickle.dumps(actual)), actual)

    def test_huge_count_and_request_readmission_stay_arithmetic(self):
        template = replace(large_reserve(40), battered_leg_continuation=POLICY)
        count = 2 ** 40 - 1
        groups = tuple(Group(f'g{i}', (f'enemy:{i}',), 0, 1) for i in range(40))
        with (patch.object(NpcMagicScenario, '__post_init__', side_effect=AssertionError('no full Scene')),
              patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')),
              patch('random.Random', side_effect=AssertionError('no RNG'))):
            source = Request(template, groups, template.facts, template.scene_frames, 'huge', count, 42,
                (Stage(1, 1),), count, Window(Fraction(0), Fraction(1, 2), Fraction(1)),
                battered_leg_continuation=POLICY)
            self.assertEqual((source.candidate_count, source.planned_trials), (count, count))
            self.assertEqual(replace(source), source)
        malformed = deepcopy(family())
        object.__setattr__(malformed.template_scenario, 'activation_order', ())
        self.assertEqual(replace(malformed), malformed)
        with patch.object(generation, '_count_vectors', side_effect=AssertionError('no vectors')) as vectors:
            with self.assertRaises(ValueError): generation.generate_magic_candidates(malformed)
            vectors.assert_not_called()

    def test_unpickled_source_mismatch_and_nested_corruption_fail_before_vectors(self):
        for corrupt in ('missing', 'float'):
            source = deepcopy(family())
            if corrupt == 'missing': object.__setattr__(source, 'battered_leg_continuation', None)
            else: object.__setattr__(source.battered_leg_continuation.endurance_profile, 'threshold', 5.0)
            source = pickle.loads(pickle.dumps(source))
            snapshot = deepcopy(source)
            with patch.object(generation, '_count_vectors', side_effect=AssertionError('no vectors')) as vectors:
                with self.assertRaises((TypeError, ValueError)): generation.generate_magic_candidates(source)
                vectors.assert_not_called()
            self.assertEqual(source, snapshot)

    def test_first_and_last_candidate_profile_is_read_before_any_vector_or_projection(self):
        original = generation.generate_magic_candidates(family())
        for index in (0, len(original.evaluation_request.candidates) - 1):
            for corruption in ('missing', 'other profile', 'float'):
                result = deepcopy(original)
                scenario = result.evaluation_request.candidates[index].scenario
                if corruption == 'missing': object.__setattr__(scenario, 'battered_leg_continuation', None)
                elif corruption == 'other profile':
                    object.__setattr__(scenario, 'battered_leg_continuation', Policy(InlineProfile(2, 4)))
                else:
                    policy = deepcopy(scenario.battered_leg_continuation)
                    object.__setattr__(policy.endurance_profile, 'dice', 2.0)
                    object.__setattr__(scenario, 'battered_leg_continuation', policy)
                with (self.subTest(index=index, corruption=corruption),
                      patch.object(generation, '_count_vectors', side_effect=AssertionError('no vectors')) as vectors,
                      patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as projection):
                    with self.assertRaises((TypeError, ValueError)): replace(result)
                    vectors.assert_not_called()
                    projection.assert_not_called()

    def test_both_wizard_positions_and_perspectives_preserve_family_profile(self):
        for wizard_side, perspective in product(CombatSide, repeat=2):
            template = scenario(wizard_side=wizard_side, perspective=perspective)
            variable = 'enemy' if wizard_side is perspective else 'ally'
            source = Request(replace(template, battered_leg_continuation=POLICY),
                (Group('variable', (variable,), 0, 1),), template.facts, template.scene_frames,
                'mirror', 1, 42, (Stage(1, 1),), 1, Window(Fraction(0), Fraction(1, 2), Fraction(1)),
                battered_leg_continuation=deepcopy(POLICY))
            actual = generation.generate_magic_candidates(source).evaluation_request.candidates[0].scenario
            self.assertEqual(actual.battered_leg_continuation, POLICY)
            self.assertEqual(actual.initial.wizard, template.initial.wizard)
            self.assertEqual(actual.perspective_side, perspective)
            self.assertEqual(len(actual.initial.roster.participants), 3)


if __name__ == '__main__':
    unittest.main()
