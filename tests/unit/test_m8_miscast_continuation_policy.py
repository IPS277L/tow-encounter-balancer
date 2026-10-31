"""ADR-0046 first slice: explicit admission and lossless native sources."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario import scenario, frame, transform_actor
from tests.unit.test_m8_magic_candidate_generation_models import request as generation_request
from towr.balance.magic_evaluation_models import MagicBalanceCandidate, MagicBalanceEvaluationRequest
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_scenario_models import (
    NpcMagicMiscastContinuationPolicy, NpcMagicPronePolicy, NpcMagicScenario,
)
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastFacts, NpcRosterMiscastPolicy
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.turn_models import CombatSide
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest


def continuation_policy():
    return NpcMagicMiscastContinuationPolicy(
        NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST,
        NpcRosterMiscastFacts(True, True, True, True, True),
        NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE)


class MiscastContinuationPolicyTests(unittest.TestCase):
    def test_every_policy_argument_is_required_and_typed(self):
        policy = continuation_policy()
        values = {f.name: getattr(policy, f.name) for f in fields(policy)}
        for name in values:
            with self.subTest(missing=name), self.assertRaises(TypeError):
                NpcMagicMiscastContinuationPolicy(**{k: v for k, v in values.items() if k != name})
            for bad in (None, True, {}, 'decline_cast_before_miscast', 'self_stand_when_safe'):
                with self.subTest(name=name, bad=bad), self.assertRaises(TypeError):
                    replace(policy, **{name: bad})
        self.assertEqual(tuple(NpcMagicPronePolicy), (NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE,))
        with self.assertRaises(TypeError):
            replace(policy, facts=scenario().facts)

    def test_all_five_facts_are_separate_required_strict_confirmations(self):
        facts = continuation_policy().facts
        values = {f.name: getattr(facts, f.name) for f in fields(facts)}
        self.assertEqual(len(values), 5)
        for name in values:
            with self.subTest(missing=name), self.assertRaises(TypeError):
                NpcRosterMiscastFacts(**{k: v for k, v in values.items() if k != name})
            with self.subTest(false=name), self.assertRaises(ValueError):
                replace(facts, **{name: False})
            for bad in (None, 1, 0, 'true'):
                with self.subTest(name=name, bad=bad), self.assertRaises(TypeError):
                    replace(facts, **{name: bad})

    def test_frozen_slotted_policy_and_scenario_preserve_full_source(self):
        policy = continuation_policy()
        source = replace(scenario(), miscast_continuation=policy)
        self.assertIs(source.miscast_continuation, policy)
        for value in (policy, policy.facts, source):
            self.assertFalse(hasattr(value, '__dict__'))
            self.assertEqual(deepcopy(value), value)
            self.assertEqual(pickle.loads(pickle.dumps(value)), value)
            self.assertEqual(replace(value), value)
        for value, attribute in ((policy, 'choice'), (policy, 'facts'),
                                 (policy, 'prone_policy'), (source, 'miscast_continuation')):
            with self.assertRaises(FrozenInstanceError):
                setattr(value, attribute, None)

    def test_old_positional_constructor_and_explicit_none_are_identical(self):
        source = scenario()
        names = [f.name for f in fields(source)]
        self.assertEqual(names[-1], 'miscast_continuation')
        positional = tuple(getattr(source, name) for name in names[:-1])
        self.assertEqual(NpcMagicScenario(*positional), source)
        self.assertEqual(NpcMagicScenario(*positional, None), source)
        self.assertEqual(replace(source, miscast_continuation=None), source)
        self.assertIsNone(source.miscast_continuation)
        for bad in (True, {}, 'decline_cast_before_miscast', continuation_policy().facts):
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                replace(source, miscast_continuation=bad)

    def test_all_sides_admit_explicit_policy_without_bootstrap_or_rng(self):
        before = getstate()
        for wizard_side in CombatSide:
            for perspective in CombatSide:
                source = scenario(wizard_side=wizard_side, perspective=perspective)
                saved = deepcopy(source)
                with (patch.object(NpcMagicScenario, 'initial_runtime_state',
                                   new=property(lambda _: self.fail('no bootstrap'))),
                      patch('random.Random', side_effect=AssertionError('no RNG')),
                      patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test'))):
                    opted = replace(source, miscast_continuation=continuation_policy())
                    self.assertEqual(replace(opted, miscast_continuation=None), source)
                self.assertEqual(source, saved)
        self.assertEqual(getstate(), before)

    def test_opt_in_keeps_fresh_healthy_and_no_history_admission(self):
        source = replace(scenario(), miscast_continuation=continuation_policy())
        injured = transform_actor(source.initial, 'ally', lambda p: replace(p,
            state=replace(p.state, injury=replace(p.state.injury,
                conditions=p.state.injury.conditions.with_condition(Condition.PRONE)))))
        with self.assertRaisesRegex(ValueError, 'healthy'):
            replace(source, initial=injured)
        magic = replace(source.initial.wizard.magic_state, miscast_dice=1)
        with self.assertRaisesRegex(ValueError, 'fresh'):
            replace(source, initial=replace(source.initial, wizard=replace(source.initial.wizard, magic_state=magic)))

    def test_future_cross_zone_close_is_rejected_but_same_zone_close_is_not(self):
        source = replace(scenario(), miscast_continuation=continuation_policy())
        # Archive an ally to form a different key: every supplied frame is checked.
        future = frame(source.initial, live=('wizard', 'enemy'))
        close = replace(future, pair_ranges=(replace(future.pair_ranges[0],
            target_range=RangedWeaponRange.CLOSE),))
        admitted = replace(source, scene_frames=(*source.scene_frames, close))
        self.assertEqual(admitted.scene_frames[-1], close)
        placements = tuple(replace(p, zone_id='middle') if p.entity_id == 'enemy' else p
                           for p in source.initial.spatial_state.placements)
        future = frame(source.initial, placements=placements)
        bad = replace(future, pair_ranges=(replace(future.pair_ranges[0],
            target_range=RangedWeaponRange.CLOSE), *future.pair_ranges[1:]))
        with (patch('random.Random', side_effect=AssertionError('no RNG')),
              self.assertRaisesRegex(ValueError, 'Zone geometry')):
            replace(source, scene_frames=(*source.scene_frames, bad))

    def test_native_simulation_and_explicit_candidates_retain_policy(self):
        source = replace(scenario(), miscast_continuation=continuation_policy())
        simulation = NpcMagicSimulationRequest(source, 42, 2)
        self.assertIs(simulation.scenario, source)
        window = generation_request().window
        request = MagicBalanceEvaluationRequest((MagicBalanceCandidate('opted', source),), 42, 2, 2, window, 1)
        self.assertEqual(request.simulation_requests, (simulation,))
        self.assertEqual(pickle.loads(pickle.dumps(request)), request)
        legacy = replace(source, miscast_continuation=None)
        self.assertNotEqual(NpcMagicSimulationRequest(legacy, 42, 2), simulation)
        self.assertEqual(simulation.seed_for(0), NpcMagicSimulationRequest(legacy, 42, 2).seed_for(0))

    def test_generation_requires_family_opt_in_before_inspecting_groups_or_projecting(self):
        request = generation_request()
        template = replace(request.template_scenario, miscast_continuation=continuation_policy())
        def exploding_groups():
            self.fail('generation inspected opt-in groups')
            yield
        with (patch('towr.application.magic_candidate_generation._count_vectors', side_effect=AssertionError('no enumeration')),
              patch('towr.application.magic_candidate_generation._project_candidate', side_effect=AssertionError('no projection'))):
            for groups in (request.groups, exploding_groups(), None):
                with self.subTest(groups=groups), self.assertRaisesRegex(ValueError, 'generation.*Miscast continuation'):
                    replace(request, template_scenario=template, groups=groups)
        self.assertIsNone(request.template_scenario.miscast_continuation)


if __name__ == '__main__':
    unittest.main()
