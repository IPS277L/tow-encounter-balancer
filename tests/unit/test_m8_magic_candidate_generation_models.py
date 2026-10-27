"""ADR-0042 arithmetic admission, without materialization or battle execution."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction as F
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m2_npc_ranged_scenario import scenario as ranged_scenario
from tests.unit.test_m6_npc_melee_scenario import scenario as melee_scenario
from tests.unit.test_m7_npc_mixed_scenario import scenario as mixed_scenario
from tests.unit.test_m8_npc_magic_scenario import scenario, frame, transform_actor, OPPOSITION
from towr.application.magic_candidate_generation_models import (
    MagicCompositionGroup as Group, MagicCandidateGenerationRequest as Request,
)
from towr.application.mixed_candidate_generation_models import MixedCompositionGroup
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage as Stage
from towr.balance.melee_staged_evaluation_models import MeleeBalanceStage
from towr.balance.mixed_staged_evaluation_models import MixedBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as Window
from towr.balance.ranged_staged_evaluation_models import RangedBalanceStage
from towr.domain.npc_champion_attack_models import NpcChampionAttackState
from towr.domain.npc_magic_scene_models import (
    NpcMagicAttackDeparture, NpcMagicBrokenPlan, NpcMagicBrokenPlanKind, NpcMagicRouteFacts,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.turn_models import CombatRoundState
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest


def request():
    template = scenario(blocker=True, fast_blocker=True)
    initial = template.initial_frame
    initial = replace(initial, attack_departures=tuple(
        NpcMagicAttackDeparture(policy.actor_id, policy.actor_id in ('ally', 'blocker'))
        for policy in template.actors), give_ground_plans=tuple(
            replace(plan, route=NpcMagicRouteFacts(('blocker',), False, False))
            if plan.actor_id == 'enemy' else plan for plan in initial.give_ground_plans))
    archive = frame(template.initial, live=('wizard', 'enemy', 'blocker', 'far-blocker'))
    template = replace(template, activation_order=template.activation_order[::-1],
                       scene_frames=(initial, archive))
    return Request(template, (Group('A', ('blocker', 'enemy'), 1, 2),
                              Group('B', ('far-blocker',), 0, 1)),
                   replace(template.facts), tuple(replace(f) for f in template.scene_frames),
                   'family', 4, 42, (Stage(10, 2), Stage(100, 1)), 240,
                   Window(F(1, 4), F(1, 2), F(3, 4)))


def large_reserve(count):
    """Authored numeric reserve before no-projection/RNG guards are installed."""
    source = scenario()
    prototype = source.initial.roster.participant('enemy')
    ids = tuple(f'enemy:{index}' for index in range(count))
    roster = NpcRoster((*source.initial.roster.participants[:2], *(replace(prototype,
        state=replace(prototype.state, actor_id=actor)) for actor in ids)))
    combat = CombatRoundState(1, roster.turn_participants)
    position = source.initial.spatial_state.placement_for('enemy')
    spatial = SpatialBattleState(source.initial.spatial_state.graph,
        (*source.initial.spatial_state.placements[:2], *(replace(position, entity_id=actor) for actor in ids)))
    state = NpcRosterCastingState(roster, source.initial.wizard, combat, spatial,
        champion_attack=NpcChampionAttackState(roster, combat, source.initial.champion_attack.daily_wounds))
    ally = source.policy_for('ally')
    policies = (source.policy_for('wizard'), replace(ally, target_actor_ids=ids,
        defeat_decisions=tuple(replace(ally.defeat_decisions[0], target_id=actor) for actor in ids)),
        *(replace(source.policy_for('enemy'), actor_id=actor,
          defeat_decisions=tuple(replace(d, attacker_id=actor) for d in source.policy_for('enemy').defeat_decisions))
          for actor in ids))
    return replace(source, initial=state, actors=policies,
        activation_order=('wizard', 'ally', *ids), objective=NpcDefeatObjective(ids),
        scene_frames=(frame(state),))


class MagicGenerationModelTests(unittest.TestCase):
    def test_counts_full_repeated_budget_caps_and_fixed_bounds(self):
        source = request()
        self.assertEqual((source.candidate_count, source.planned_trials), (4, 240))
        for changes in ({'max_candidates': 3}, {'max_total_trials': 239},
                        {'groups': tuple(replace(g, minimum_count=0, maximum_count=0) for g in source.groups)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, **changes)
        fixed = replace(source, groups=(replace(source.groups[0], maximum_count=1),
                                        replace(source.groups[1], maximum_count=0)))
        self.assertEqual((fixed.candidate_count, fixed.planned_trials), (1, 110))
        self.assertEqual(fixed.groups[0].actor_ids, ('blocker', 'enemy'))
        widened = replace(source, groups=tuple(replace(g, minimum_count=0) for g in source.groups),
                           max_candidates=5, max_total_trials=250)
        self.assertEqual((widened.candidate_count, widened.planned_trials), (5, 250))

    def test_group_ids_bounds_and_numeric_types_are_strict(self):
        group = request().groups[0]
        for name in ('group_id',):
            for value in (None, True, 1):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    replace(group, **{name: value})
            for value in ('', ' '):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    replace(group, **{name: value})
        for ids in ((None,), (1,), (True,)):
            with self.subTest(ids=ids), self.assertRaises(TypeError):
                replace(group, actor_ids=ids)
        for ids in ((), ('',), (' ',), ('enemy', 'enemy')):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                replace(group, actor_ids=ids)
        for name in ('minimum_count', 'maximum_count'):
            for value in (None, True, 1.5, '1'):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    replace(group, **{name: value})
            for value in (-1, 3):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replace(group, **{name: value})
        with self.assertRaises(ValueError):
            replace(group, minimum_count=2, maximum_count=1)
        exact = Group(' A ', (' x ', 'x'), 0, 2)
        self.assertEqual((exact.group_id, exact.actor_ids), (' A ', (' x ', 'x')))

    def test_ordered_containers_reject_without_consuming_generators(self):
        source = request()
        consumed = []
        def values(items):
            consumed.append('consumed')
            yield from items
        for obj, name in ((source.groups[0], 'actor_ids'), (source, 'groups'),
                          (source, 'scene_frames'), (source, 'stages')):
            original = getattr(obj, name)
            for value in (None, 'ab', set(original), {0: original[0]}, values(original)):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    replace(obj, **{name: value})
        self.assertEqual(consumed, [])

    def test_partition_excludes_fixed_actors_and_wizard_with_no_missing_or_overlap(self):
        source = request()
        first, last = source.groups
        bad = ((), (first,), (first, replace(last, group_id='A')),
               (first, replace(last, actor_ids=('unknown',))),
               (first, replace(last, actor_ids=('ally',))),
               (first, replace(last, actor_ids=('wizard',))),
               (first, replace(last, actor_ids=('blocker', 'far-blocker'))))
        for groups in bad:
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                replace(source, groups=groups)

    def test_wizard_is_fixed_independently_of_both_perspective_directions(self):
        for wizard_side in type(OPPOSITION):
            for perspective in type(OPPOSITION):
                template = scenario(wizard_side=wizard_side, perspective=perspective)
                expected = 'enemy' if wizard_side is perspective else 'ally'
                accepted = Request(template, (Group('variable', (expected,), 0, 1),),
                    replace(template.facts), template.scene_frames, 'mirror', 1, 0,
                    (Stage(1, 1), Stage(2, 1)), 3, Window(F(0), F(1, 2), F(1)))
                self.assertEqual((accepted.candidate_count, accepted.planned_trials), (1, 3))
                self.assertIs(accepted.template_scenario.initial.wizard, template.initial.wizard)
                if wizard_side is not perspective:
                    self.assertIn('wizard', template.objective.target_actor_ids)
                with self.assertRaises(ValueError):
                    replace(accepted, groups=(Group('variable', (expected, 'wizard'), 0, 1),))
                with self.assertRaises(ValueError):
                    replace(accepted, groups=(Group('variable', (expected,), 0, 0),))

    def test_exact_full_definitions_within_groups_and_equal_groups_are_not_deduplicated(self):
        source = request()
        def changed(participant):
            definition = replace(participant.definition, id='different', source_rule_id='different-source')
            return replace(participant, definition=definition, state=replace(participant.state, definition_id=definition.id))
        state = transform_actor(source.template_scenario.initial, 'blocker', changed)
        template = replace(source.template_scenario, initial=state)
        with self.assertRaises(ValueError):
            replace(source, template_scenario=template)
        # The changed definition alone in its group is valid; other groups may
        # have equal definitions and still represent separate reserve positions.
        groups = (Group('one', ('blocker',), 1, 1), Group('two', ('enemy',), 0, 1), source.groups[1])
        self.assertEqual(replace(source, template_scenario=template, groups=groups).candidate_count, 4)
        self.assertEqual(replace(source, groups=groups).candidate_count, 4)

    def test_family_facts_frames_are_explicit_and_equal_copies_preserve_sources(self):
        source = request()
        self.assertIsNot(source.facts, source.template_scenario.facts)
        self.assertTrue(all(a is not b for a, b in zip(source.scene_frames, source.template_scenario.scene_frames)))
        accepted = replace(source, facts=replace(source.facts),
                           scene_frames=tuple(replace(f) for f in source.scene_frames))
        self.assertEqual(accepted, source)
        self.assertIs(accepted.template_scenario, source.template_scenario)
        kwargs = {f.name: getattr(source, f.name) for f in fields(source)}
        for name in ('facts', 'scene_frames'):
            with self.subTest(name=name), self.assertRaisesRegex(TypeError, name):
                Request(**{key: value for key, value in kwargs.items() if key != name})

    def test_family_frame_equality_includes_key_pair_order_orientation_routes_and_flags(self):
        source = request()
        first, second = source.scene_frames
        pair = first.pair_ranges[0]
        plan = first.give_ground_plans[0]
        changes = (
            (), (first,), (first, first), source.scene_frames[::-1],
            (replace(first, key=replace(first.key, live_actor_ids=first.key.live_actor_ids[:-1])), second),
            (replace(first, pair_ranges=first.pair_ranges[::-1]), second),
            (replace(first, pair_ranges=(replace(pair, first_actor_id=pair.second_actor_id,
                 second_actor_id=pair.first_actor_id), *first.pair_ranges[1:])), second),
            (replace(first, pair_ranges=(replace(pair, first_range_approved_by_gm=True), *first.pair_ranges[1:])), second),
            (replace(first, give_ground_plans=(replace(plan, route=replace(plan.route, path_entity_ids=())),
                                               *first.give_ground_plans[1:])), second),
            (replace(first, attack_departures=tuple(replace(d, can_leave_zone=not d.can_leave_zone)
                for d in first.attack_departures)), second),
            (replace(first, key=replace(first.key, placements=first.key.placements[::-1])), second),
        )
        for frames in changes:
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                replace(source, scene_frames=frames)
        # A separately authored order is accepted when family source matches.
        template = replace(source.template_scenario, scene_frames=source.scene_frames[::-1])
        self.assertEqual(replace(source, template_scenario=template, scene_frames=template.scene_frames).scene_frames,
                         template.scene_frames)

    def test_foreign_families_and_untyped_fields_are_rejected(self):
        source = request()
        for other in (ranged_scenario(), melee_scenario(), mixed_scenario()):
            for changes in ({'template_scenario': other}, {'facts': other.facts}):
                with self.subTest(changes=changes), self.assertRaises(TypeError):
                    replace(source, **changes)
        for stages in ((MeleeBalanceStage(10, 1),), (MixedBalanceStage(10, 1),), (RangedBalanceStage(10, 1),)):
            with self.subTest(stages=stages), self.assertRaises(TypeError):
                replace(source, stages=stages)
        for changes in ({'groups': (MixedCompositionGroup('A', ('enemy',), 1, 1),)},
                        {'groups': (None,)}, {'scene_frames': (None,)}, {'stages': (None,)},
                        *({name: None} for name in ('template_scenario', 'facts', 'window'))):
            with self.subTest(changes=changes), self.assertRaises(TypeError):
                replace(source, **changes)

    def test_prefix_caps_and_seed_use_strict_types_and_boundaries(self):
        source = request()
        for value in (None, True, 1):
            with self.subTest(value=value), self.assertRaises(TypeError):
                replace(source, candidate_id_prefix=value)
        for value in ('', ' '):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(source, candidate_id_prefix=value)
        self.assertEqual(replace(source, candidate_id_prefix=' family ').candidate_id_prefix, ' family ')
        for name in ('max_candidates', 'max_total_trials', 'master_seed'):
            for value in (None, True, 1.5, '240'):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    replace(source, **{name: value})
        for name in ('max_candidates', 'max_total_trials'):
            for value in (0, -1):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replace(source, **{name: value})
        for value in (-1, 2**64):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(source, master_seed=value)
        for value in (0, 2**64 - 1):
            self.assertEqual(replace(source, master_seed=value).master_seed, value)

    def test_all_stages_preflighted_and_keep_growth_never_regrows_family(self):
        source = request()
        for stages in ((), (Stage(10, 2), Stage(10, 1)), (Stage(10, 2), Stage(9, 1))):
            with self.subTest(stages=stages), self.assertRaises(ValueError):
                replace(source, stages=stages)
        with self.assertRaises(TypeError):
            replace(source, stages=(Stage(10, 1), Stage(100, 1), None))
        for stages, planned in (((Stage(10, 20),), 40),
                                ((Stage(10, 1), Stage(100, 20), Stage(1000, 40)), 1140)):
            accepted = replace(source, stages=stages, max_total_trials=planned)
            self.assertEqual(accepted.planned_trials, planned)
            with self.assertRaises(ValueError):
                replace(accepted, max_total_trials=planned - 1)
        huge_n = 2**64 - 1
        unlimited = replace(source, stages=(Stage(huge_n, 1),), max_total_trials=4 * huge_n)
        self.assertEqual(unlimited.planned_trials, 4 * huge_n)

    def test_preflight_preserves_complete_template_and_independent_orders_without_subset_admission(self):
        source = request()
        before, rng_before = deepcopy(source), getstate()
        template = source.template_scenario
        changed = replace(source, groups=source.groups[::-1])
        self.assertEqual(changed.candidate_count, 4)
        self.assertIs(changed.template_scenario, template)
        self.assertEqual(template, before.template_scenario)
        self.assertIs(changed.template_scenario.initial.wizard, template.initial.wizard)
        self.assertIs(changed.template_scenario.initial.champion_attack, template.initial.champion_attack)
        self.assertTrue(template.initial_frame.attack_departures[1].can_leave_zone)
        self.assertFalse(template.initial_frame.attack_departures[0].can_leave_zone)
        self.assertEqual(template.activation_order, tuple(reversed(tuple(p.state.actor_id for p in template.initial.roster.participants))))
        self.assertEqual(source, before)
        self.assertEqual(getstate(), rng_before)

    def test_preflight_counts_vectors_that_will_invalidate_a_broken_route_without_projecting(self):
        source = request()
        positions = tuple(replace(p, zone_id='shelter') if p.entity_id in ('blocker', 'far-blocker') else p
                          for p in source.template_scenario.initial.spatial_state.placements)
        moving = NpcMagicBrokenPlan('ally', NpcMagicBrokenPlanKind.FREE_MOVE_RECOVER, ('middle',),
                                   NpcMagicRouteFacts((), False, False), None, None, True)
        future = replace(frame(source.template_scenario.initial, placements=positions), broken_plans=(moving,))
        template = replace(source.template_scenario, scene_frames=(*source.scene_frames, future))
        # Source enemy@arena makes moving Recover valid. Prefix count1 retains
        # blocker@shelter and removes enemy: ally is already safe, so the same
        # moving plan must later fail construction. Preflight still counts it.
        with patch('towr.domain.npc_magic_scenario_models.NpcMagicScenario.__post_init__',
                   side_effect=AssertionError('subset projection must wait for construction')):
            accepted = replace(source, template_scenario=template, scene_frames=template.scene_frames)
        self.assertEqual((accepted.candidate_count, accepted.planned_trials), (4, 240))
        self.assertIs(accepted.template_scenario, template)
        self.assertEqual(accepted.scene_frames[-1].broken_plans, (moving,))

    def test_tuple_copies_frozen_slots_derived_replace_and_pickle(self):
        source = request()
        before = deepcopy(source)
        actor_ids = list(source.groups[0].actor_ids)
        group = replace(source.groups[0], actor_ids=actor_ids)
        groups, frames, stages = [group, source.groups[1]], list(source.scene_frames), list(source.stages)
        normalized = replace(source, groups=groups, scene_frames=frames, stages=stages)
        for items in (actor_ids, groups, frames, stages):
            items.clear()
        self.assertEqual(normalized, before)
        for obj, name in ((group, 'minimum_count'), (normalized, 'max_candidates')):
            self.assertFalse(hasattr(obj, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, name, 0)
        for name in ('candidate_count', 'planned_trials'):
            with self.assertRaises(TypeError):
                replace(source, **{name: 0})
        restored = pickle.loads(pickle.dumps(source))
        self.assertEqual(restored, source)
        self.assertIs(type(restored.window), Window)
        self.assertIs(type(restored.stages[0]), Stage)
        self.assertEqual(source, before)

    def test_huge_family_is_arithmetic_with_one_seed_admission_and_no_execution(self):
        template = large_reserve(40)
        groups = tuple(Group(p.state.actor_id, (p.state.actor_id,), 0, 1)
                       for p in template.initial.roster.participants[2:])
        count = 2**40 - 1
        facts, frames = replace(template.facts), template.scene_frames
        stages, window = (Stage(1, 1), Stage(2, 1)), Window(F(0), F(1, 2), F(1))
        before, rng_before = deepcopy(template), getstate()
        targets = (
            'itertools.product', 'random.Random',
            'towr.balance.magic_evaluation_models.MagicBalanceCandidate',
            'towr.balance.magic_staged_evaluation_models.MagicStagedEvaluationRequest',
            'towr.domain.npc_magic_scenario_models.NpcMagicScenario.__post_init__',
            'towr.engine.npc_magic_scenario_runner.run_npc_magic_scenario',
            'towr.simulation.npc_magic_simulation.run_npc_magic_simulation',
            'concurrent.futures.ProcessPoolExecutor',
        )
        with ExitStack() as stack:
            for target in targets:
                stack.enter_context(patch(target, side_effect=AssertionError('forbidden: ' + target)))
            admission = stack.enter_context(patch(
                'towr.application.magic_candidate_generation_models.NpcMagicSimulationRequest',
                wraps=NpcMagicSimulationRequest))
            source = Request(template, groups, facts, frames, 'huge', count, 42, stages, count + 2, window)
            admission.assert_called_once_with(template, 42, 1)
            self.assertEqual((source.candidate_count, source.planned_trials), (count, count + 2))
            for change in ({'max_candidates': count - 1}, {'max_total_trials': count + 1}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    replace(source, **change)
        self.assertEqual(template, before)
        self.assertEqual(getstate(), rng_before)


if __name__ == '__main__':
    unittest.main()
