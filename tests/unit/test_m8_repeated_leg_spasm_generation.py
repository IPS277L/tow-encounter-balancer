"""ADR-0054 third family assertion, arithmetic admission and source preflight."""
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
    MagicCandidateGenerationRequest as Request, MagicCandidateGenerationResult as Result, MagicCompositionGroup as Group,
)
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage as Stage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as Window
from towr.domain.npc_magic_scenario_models import (
    NpcMagicScenario, NpcMagicRepeatedLegSpasmPolicy as Repeated, NpcMagicStationaryWoundPolicy as Stationary,
)
from towr.domain.turn_models import CombatSide, CombatRoundState
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest


POLICY = Repeated.STAND_ONCE_WITH_JOURNAL_WITNESSES
BASE = Stationary.LEG_SPASM_STAND_AND_CONTINUE


def family(source=None, *, miscast=None, stationary=BASE, repeated=POLICY):
    original = request() if source is None else source
    return replace(original, template_scenario=replace(original.template_scenario,
        miscast_continuation=miscast, stationary_wound_continuation=stationary,
        repeated_leg_spasm_continuation=repeated), miscast_continuation=miscast,
        stationary_wound_continuation=stationary, repeated_leg_spasm_continuation=repeated)


class RepeatedLegSpasmGenerationTests(unittest.TestCase):
    def test_mirrored_opposition_perspective_keeps_all_four_vectors_for_six_combinations(self):
        original = request()
        template = original.template_scenario
        opposite = {CombatSide.PLAYERS_AND_ALLIES: CombatSide.OPPOSITION,
                    CombatSide.OPPOSITION: CombatSide.PLAYERS_AND_ALLIES}
        roster = replace(template.initial.roster, participants=tuple(replace(p,
            state=replace(p.state, side=opposite[p.state.side])) for p in template.initial.roster.participants))
        combat = CombatRoundState(1, roster.turn_participants)
        def placements(values):
            return tuple(replace(p, side_id=opposite[CombatSide(p.side_id)].value) for p in values)
        spatial = replace(template.initial.spatial_state, placements=placements(template.initial.spatial_state.placements))
        initial = replace(template.initial, roster=roster, round_state=combat, spatial_state=spatial,
            champion_attack=replace(template.initial.champion_attack, roster=roster, round_state=combat))
        frames = tuple(replace(frame, key=replace(frame.key, placements=placements(frame.key.placements)))
                       for frame in template.scene_frames)
        mirror = replace(original, template_scenario=replace(template, initial=initial,
                         perspective_side=opposite[template.perspective_side], scene_frames=frames), scene_frames=frames)
        baseline = generation.generate_magic_candidates(mirror)
        self.assertIs(mirror.template_scenario.perspective_side, CombatSide.OPPOSITION)
        for m, s, r in product((False, True), repeat=3):
            if r and not s: continue
            source = family(mirror, miscast=continuation_policy() if m else None,
                            stationary=BASE if s else None, repeated=POLICY if r else None)
            generated = generation.generate_magic_candidates(source)
            self.assertEqual((source.candidate_count, source.planned_trials), (4, 240))
            for old, actual in zip(baseline.evaluation_request.candidates, generated.evaluation_request.candidates, strict=True):
                self.assertEqual(actual, replace(old, scenario=replace(old.scenario,
                    miscast_continuation=source.miscast_continuation,
                    stationary_wound_continuation=source.stationary_wound_continuation,
                    repeated_leg_spasm_continuation=source.repeated_leg_spasm_continuation)))

    def test_six_combinations_preserve_full_ordered_projection_and_seeds(self):
        original = request()
        baseline = generation.generate_magic_candidates(original)
        before_rng = getstate()
        with patch('random.Random', side_effect=AssertionError('pure generation')):
            for m, s, r in product((False, True), repeat=3):
                if r and not s:
                    with self.assertRaises(ValueError):
                        family(original, miscast=continuation_policy() if m else None, stationary=None)
                    continue
                source = family(original, miscast=continuation_policy() if m else None,
                                stationary=BASE if s else None, repeated=POLICY if r else None)
                before = deepcopy(source)
                generated = generation.generate_magic_candidates(source)
                self.assertEqual((source.candidate_count, source.planned_trials), (4, 240))
                self.assertIs(generated.source_request, source)
                for old, actual in zip(baseline.evaluation_request.candidates, generated.evaluation_request.candidates, strict=True):
                    with self.subTest(miscast=m, stationary=s, repeated=r, id=actual.candidate_id):
                        self.assertEqual(actual, replace(old, scenario=replace(old.scenario,
                            miscast_continuation=source.miscast_continuation,
                            stationary_wound_continuation=source.stationary_wound_continuation,
                            repeated_leg_spasm_continuation=source.repeated_leg_spasm_continuation)))
                        self.assertIs(actual.scenario.repeated_leg_spasm_continuation, source.repeated_leg_spasm_continuation)
                        left = NpcMagicSimulationRequest(old.scenario, source.master_seed, 3)
                        right = NpcMagicSimulationRequest(actual.scenario, source.master_seed, 3)
                        self.assertEqual(tuple(left.seed_for(i) for i in range(3)), tuple(right.seed_for(i) for i in range(3)))
                self.assertEqual(source, before)
        self.assertEqual(getstate(), before_rng)

    def test_both_perspectives_and_wizard_sides_preserve_explicit_permission(self):
        for wizard_side, perspective in product(CombatSide, repeat=2):
            template = scenario(wizard_side=wizard_side, perspective=perspective)
            variable = 'enemy' if wizard_side is perspective else 'ally'
            old = Request(template, (Group('variable', (variable,), 0, 1),), template.facts,
                          template.scene_frames, 'mirror', 1, 42, (Stage(1, 1),), 1,
                          Window(Fraction(0), Fraction(1, 2), Fraction(1)))
            for miscast in (None, continuation_policy()):
                source = family(old, miscast=miscast)
                generated = generation.generate_magic_candidates(source)
                projected = generated.evaluation_request.candidates[0].scenario
                self.assertEqual(source.candidate_count, 1)
                self.assertIs(projected.initial.wizard, template.initial.wizard)
                self.assertIs(projected.repeated_leg_spasm_continuation, POLICY)
                self.assertEqual(projected.perspective_side, perspective)

    def test_new_field_is_last_and_all_old_positional_forms_remain_none(self):
        source = request()
        names = tuple(f.name for f in fields(source))
        self.assertEqual(names[-3:], ('miscast_continuation', 'stationary_wound_continuation',
                                      'repeated_leg_spasm_continuation'))
        self.assertIsNone(fields(source)[-1].default)
        positional = tuple(getattr(source, name) for name in names[:-3])
        baseline = generation.generate_magic_candidates(source)
        for extra in ((), (None,), (None, None), (None, None, None)):
            value = Request(*positional, *extra)
            self.assertEqual(value, source)
            self.assertEqual(generation.generate_magic_candidates(value), baseline)

    def test_omission_and_bidirectional_mismatch_precede_collection_materialization(self):
        old = family(repeated=None)
        selected = family()
        for source, template, value in ((old, selected.template_scenario, None),
                                        (selected, old.template_scenario, POLICY)):
            with self.assertRaisesRegex(ValueError, 'explicit family'):
                replace(source, template_scenario=template, repeated_leg_spasm_continuation=value,
                    groups=Unreadable(source.groups), stages=Unreadable(source.stages),
                    scene_frames=Unreadable(source.scene_frames))
        data = {f.name: getattr(selected, f.name) for f in fields(selected) if f.name != 'repeated_leg_spasm_continuation'}
        with self.assertRaises(ValueError): Request(**data)
        with self.assertRaises(ValueError): replace(selected, stationary_wound_continuation=None)

    def test_original_template_and_family_types_are_checked_before_equal_values(self):
        source = family(miscast=continuation_policy())
        for value in (POLICY.value, BASE, True, False, 1, 0, {}):
            with self.subTest(role='family', value=value), self.assertRaises(TypeError):
                replace(source, repeated_leg_spasm_continuation=value)
            bad = deepcopy(source.template_scenario)
            object.__setattr__(bad, 'repeated_leg_spasm_continuation', value)
            if value == POLICY.value: self.assertEqual(bad, source.template_scenario)
            with self.subTest(role='template', value=value), self.assertRaises(TypeError):
                replace(source, template_scenario=bad)
        bad = deepcopy(source)
        object.__setattr__(bad.miscast_continuation.facts, 'all_combatants_in_roster', 1)
        self.assertEqual(bad, source)
        with self.assertRaises(TypeError): replace(bad)

    def test_arithmetic_request_does_not_construct_scenario_but_factory_readmits_full_source(self):
        selected = family()
        with patch.object(NpcMagicScenario, '__post_init__', side_effect=AssertionError('no full Scenario admission')):
            self.assertEqual(replace(selected), selected)
        bad = deepcopy(selected)
        object.__setattr__(bad.template_scenario, 'activation_order', ())
        # Arithmetic collection/count admission does not traverse executable slots.
        self.assertEqual(replace(bad), bad)
        with patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as vectors:
            with self.assertRaises(ValueError): generation.generate_magic_candidates(bad)
            vectors.assert_not_called()

    def test_large_count_request_is_arithmetic_with_new_permission(self):
        template = replace(large_reserve(40), stationary_wound_continuation=BASE,
                           repeated_leg_spasm_continuation=POLICY)
        count = 2 ** 40 - 1
        groups = tuple(Group(f'g{i}', (f'enemy:{i}',), 0, 1) for i in range(40))
        with (patch.object(NpcMagicScenario, '__post_init__', side_effect=AssertionError('no subset admission')),
              patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')),
              patch('random.Random', side_effect=AssertionError('no RNG'))):
            source = Request(template, groups, template.facts, template.scene_frames, 'huge', count, 42,
                             (Stage(1, 1),), count, Window(Fraction(0), Fraction(1, 2), Fraction(1)),
                             None, BASE, POLICY)
            self.assertEqual((source.candidate_count, source.planned_trials), (count, count))
            with self.assertRaises(ValueError): replace(source, max_candidates=count - 1)
            with self.assertRaises(ValueError): replace(source, max_total_trials=count - 1)

    def test_unpickled_family_source_fails_before_enumeration_without_normalization(self):
        source = family()
        for field, value, error in (('repeated_leg_spasm_continuation', None, ValueError),
                                    ('repeated_leg_spasm_continuation', POLICY.value, TypeError),
                                    ('groups', list(source.groups), ValueError)):
            bad = deepcopy(source)
            object.__setattr__(bad, field, value)
            bad = pickle.loads(pickle.dumps(bad))
            before = deepcopy(bad)
            with patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as vectors:
                with self.assertRaises(error): generation.generate_magic_candidates(bad)
                vectors.assert_not_called()
            self.assertEqual(bad, before)

    def test_first_and_last_detached_candidates_fail_before_any_vector_or_projection(self):
        good = generation.generate_magic_candidates(family(miscast=continuation_policy()))
        for index in (0, len(good.evaluation_request.candidates) - 1):
            for field, value, error in (('repeated_leg_spasm_continuation', None, ValueError),
                ('repeated_leg_spasm_continuation', POLICY.value, TypeError),
                ('miscast_continuation', None, ValueError), ('activation_order', (), ValueError),
                ('facts', 'integer-true', TypeError)):
                bad = deepcopy(good)
                candidate = bad.evaluation_request.candidates[index]
                if field == 'facts':
                    value = deepcopy(candidate.scenario.facts)
                    object.__setattr__(value, 'no_external_condition_sources', 1)
                object.__setattr__(candidate.scenario, field, value)
                before = deepcopy(bad)
                with (self.subTest(index=index, field=field),
                      patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as counts,
                      patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project):
                    with self.assertRaises(error): Result(bad.source_request, bad.evaluation_request)
                    counts.assert_not_called()
                    project.assert_not_called()
                self.assertEqual(bad, before)

    def test_same_id_opposite_permission_source_is_not_equal_to_generated_family(self):
        old, selected = family(repeated=None), family()
        a, b = generation.generate_magic_candidates(old), generation.generate_magic_candidates(selected)
        for source, evaluation in ((old, b.evaluation_request), (selected, a.evaluation_request)):
            with patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')):
                with self.assertRaises(ValueError): Result(source, evaluation)


if __name__ == '__main__':
    unittest.main()
