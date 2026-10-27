"""ADR-0042 complete source-bound construction; no simulator execution."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction as F
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_candidate_generation_models import request
from tests.unit.test_m8_npc_magic_scenario import scenario, frame, transform_actor, OPPOSITION
from towr.application import magic_candidate_generation as generation
from towr.application.magic_candidate_generation import generate_magic_candidates as generate
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError as Error
from towr.application.magic_candidate_generation_models import (
    MagicCandidateGenerationRequest as Request, MagicCandidateGenerationResult as Result,
    MagicCompositionGroup as Group,
)
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage as Stage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as Window
from towr.domain.npc_magic_scene_models import (
    NpcMagicBrokenPlan, NpcMagicBrokenPlanKind as Broken, NpcMagicRouteFacts,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.test_models import InlineProfile
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest


def with_frames(source, frames):
    template = replace(source.template_scenario, scene_frames=frames)
    return replace(source, template_scenario=template, scene_frames=template.scene_frames)


def collapse_request(*, conflict_actor=None):
    source = request()
    initial = source.template_scenario.initial_frame
    positions = tuple(replace(p, zone_id='middle') if p.entity_id == 'enemy' else p
                      for p in initial.key.placements)
    later = frame(source.template_scenario.initial, placements=positions)
    later = replace(later, attack_departures=tuple(
        replace(d, can_leave_zone=not d.can_leave_zone) if d.actor_id == conflict_actor else d
        for d in initial.attack_departures))
    return with_frames(source, (initial, later))


def invalid_broken_request():
    source = request()
    positions = tuple(replace(p, zone_id='shelter') if p.entity_id in ('blocker', 'far-blocker') else p
                      for p in source.template_scenario.initial.spatial_state.placements)
    moving = NpcMagicBrokenPlan('ally', Broken.FREE_MOVE_RECOVER, ('middle',),
                               NpcMagicRouteFacts((), False, False), None, None, True)
    future = replace(frame(source.template_scenario.initial, placements=positions), broken_plans=(moving,))
    return with_frames(source, (*source.scene_frames, future))


def rebuild_initial(source, *, scenario_changes=None, **changes):
    """Author a different admitted scenario, preserving its fresh owner links."""
    initial = source.initial
    roster = changes.pop('roster', initial.roster)
    combat = changes.pop('round_state', initial.round_state)
    spatial = changes.pop('spatial_state', initial.spatial_state)
    champion = replace(initial.champion_attack, roster=roster, round_state=combat,
                       daily_wounds=changes.pop('daily_wounds', initial.champion_attack.daily_wounds))
    return replace(source, initial=replace(initial, roster=roster, round_state=combat,
                                          spatial_state=spatial, champion_attack=champion, **changes),
                   **(scenario_changes or {}))


def replace_last(evaluation, scenario):
    return replace(evaluation, candidates=(*evaluation.candidates[:-1],
        replace(evaluation.candidates[-1], scenario=scenario)))


class MagicCandidateGenerationTests(unittest.TestCase):
    def test_four_vectors_retain_independent_orders_full_snapshots_and_policies(self):
        source = request()
        before, rng_before = deepcopy(source), getstate()
        result = generate(source)
        self.assertIs(result.source_request, source)
        evaluation = result.evaluation_request
        self.assertEqual((evaluation.master_seed, evaluation.stages, evaluation.window,
                          evaluation.max_total_trials, evaluation.planned_trials),
                         (42, source.stages, source.window, 240, 240))
        expected = ((1, 0, ('wizard', 'ally', 'blocker')),
                    (1, 1, ('wizard', 'ally', 'blocker', 'far-blocker')),
                    (2, 0, ('wizard', 'ally', 'enemy', 'blocker')),
                    (2, 1, ('wizard', 'ally', 'enemy', 'blocker', 'far-blocker')))
        template = source.template_scenario
        for candidate, (a, b, ids) in zip(evaluation.candidates, expected, strict=True):
            actual = candidate.scenario
            keep = set(ids)
            self.assertEqual(candidate.candidate_id, f'family:counts:{a},{b}')
            self.assertEqual(actual.id, candidate.candidate_id)
            self.assertEqual(actual.initial.roster.participants,
                tuple(p for p in template.initial.roster.participants if p.state.actor_id in keep))
            self.assertEqual(actual.activation_order, tuple(i for i in template.activation_order if i in keep))
            self.assertEqual(actual.initial.spatial_state.placements,
                tuple(p for p in template.initial.spatial_state.placements if p.entity_id in keep))
            self.assertIs(actual.initial.spatial_state.graph, template.initial.spatial_state.graph)
            self.assertIs(actual.initial.wizard, template.initial.wizard)
            self.assertIs(actual.spell, template.spell)
            self.assertIs(actual.facts, source.facts)
            self.assertEqual(actual.objective.target_actor_ids,
                tuple(i for i in template.objective.target_actor_ids if i in keep))
            for policy in actual.actors:
                old = template.policy_for(policy.actor_id)
                self.assertEqual(policy, replace(old,
                    target_actor_ids=tuple(i for i in old.target_actor_ids if i in keep),
                    defeat_decisions=tuple(d for d in old.defeat_decisions if d.target_id in keep)))
            for new_frame, old_frame in zip(actual.scene_frames, source.scene_frames, strict=True):
                self.assertEqual(new_frame.key.live_actor_ids,
                    tuple(i for i in old_frame.key.live_actor_ids if i in keep))
                self.assertEqual(new_frame.zone_ranges, old_frame.zone_ranges)
                self.assertEqual(new_frame.pair_ranges,
                    tuple(p for p in old_frame.pair_ranges if p.first_actor_id in keep and p.second_actor_id in keep))
                self.assertEqual(new_frame.attack_departures,
                    tuple(p for p in old_frame.attack_departures if p.actor_id in keep))
        self.assertEqual(source, before)
        self.assertEqual(getstate(), rng_before)

    def test_initial_owners_are_fresh_with_same_day_caster_and_no_pending_history(self):
        source = request()
        for candidate in generate(source).evaluation_request.candidates:
            owner = candidate.scenario.initial
            self.assertIsNot(owner, source.template_scenario.initial)
            self.assertEqual(owner.round_state.round_number, 1)
            self.assertEqual(owner.round_state.participants, owner.roster.turn_participants)
            self.assertEqual(owner.champion_attack.roster, owner.roster)
            self.assertEqual(owner.champion_attack.round_state, owner.round_state)
            self.assertEqual(owner.champion_attack.daily_wounds,
                             source.template_scenario.initial.champion_attack.daily_wounds)
            self.assertIsNot(owner.champion_attack, source.template_scenario.initial.champion_attack)
            self.assertEqual(owner.consumed_execution_ids, ())
            self.assertIsNone(owner.minion_attack)
            self.assertIsNone(owner.pending_miscast)
            self.assertIsNone(owner.pending_movement)
            self.assertIsNone(owner.pending_interruption)
            self.assertIsNone(owner.pending_minion_attack)
            self.assertEqual(owner.wound_expiries, ())
            self.assertEqual(owner.wound_turn_end_receipts, ())

    def test_all_zero_is_excluded_and_equal_definition_groups_are_not_deduplicated(self):
        source = request()
        ids = source.template_scenario.objective.target_actor_ids
        groups = tuple(Group(i, (i,), 0, 1) for i in ids)
        source = replace(source, groups=groups, max_candidates=7, max_total_trials=270)
        result = generate(source)
        self.assertEqual(len(result.evaluation_request.candidates), 7)
        self.assertEqual(tuple(c.candidate_id for c in result.evaluation_request.candidates),
            tuple('family:counts:' + counts for counts in ('0,0,1', '0,1,0', '0,1,1', '1,0,0', '1,0,1', '1,1,0', '1,1,1')))
        self.assertEqual(len({c.scenario.initial.roster.participants for c in result.evaluation_request.candidates}), 7)
        fixed = request()
        fixed = replace(fixed, groups=(replace(fixed.groups[0], maximum_count=1),
                                      replace(fixed.groups[1], maximum_count=0)))
        self.assertEqual(tuple(c.candidate_id for c in generate(fixed).evaluation_request.candidates), ('family:counts:1,0',))

    def test_both_perspectives_and_wizard_sides_keep_wizard_outside_variable_groups(self):
        for wizard_side in type(OPPOSITION):
            for perspective in type(OPPOSITION):
                template = scenario(wizard_side=wizard_side, perspective=perspective)
                actor = 'enemy' if wizard_side is perspective else 'ally'
                source = Request(template, (Group('variable', (actor,), 0, 1),), replace(template.facts),
                    template.scene_frames, 'mirror', 1, 42, (Stage(1, 1),), 1,
                    Window(F(0), F(1, 2), F(1)))
                result = generate(source)
                projected = result.evaluation_request.candidates[0].scenario
                self.assertEqual(len(projected.initial.roster.participants), 3)
                self.assertIs(projected.initial.wizard, template.initial.wizard)
                self.assertEqual(projected.objective, template.objective)
                self.assertEqual(projected.perspective_side, perspective)

    def test_repeat_and_renamed_prefix_preserve_all_inputs_except_local_ids_and_seeds(self):
        source = request()
        first = generate(source)
        self.assertEqual(generate(source), first)
        renamed = generate(replace(source, candidate_id_prefix='other'))
        for old, new in zip(first.evaluation_request.candidates, renamed.evaluation_request.candidates, strict=True):
            self.assertNotEqual(old.candidate_id, new.candidate_id)
            self.assertEqual(replace(new.scenario, id=old.scenario.id), old.scenario)
            a = NpcMagicSimulationRequest(old.scenario, source.master_seed, 10)
            b = NpcMagicSimulationRequest(new.scenario, source.master_seed, 100)
            self.assertEqual(tuple(a.seed_for(i) for i in range(10)), tuple(b.seed_for(i) for i in range(10)))

    def test_equal_projected_frames_collapse_stably_and_other_frames_are_kept(self):
        source = collapse_request()
        projected = generate(source).evaluation_request.candidates
        self.assertEqual(tuple(len(c.scenario.scene_frames) for c in projected), (1, 1, 2, 2))
        for candidate in projected[:2]:
            self.assertEqual(candidate.scenario.scene_frames[0], candidate.scenario.initial_frame)
        self.assertEqual(len(source.scene_frames), 2)

    def test_conflicting_key_fails_first_or_later_without_skipping_or_partial_result(self):
        for actor, expected, expected_calls in (('blocker', (1, 0), 1), ('far-blocker', (1, 1), 2)):
            source = collapse_request(conflict_actor=actor)
            with self.subTest(actor=actor), patch.object(generation, '_project_candidate',
                    wraps=generation._project_candidate) as project:
                with self.assertRaises(Error) as caught:
                    generate(source)
            self.assertEqual(caught.exception.counts, expected)
            self.assertEqual(caught.exception.candidate_id, 'family:counts:' + ','.join(map(str, expected)))
            self.assertIs(type(caught.exception.__cause__), ValueError)
            self.assertIn('conflicting', str(caught.exception.__cause__))
            self.assertEqual(project.call_count, expected_calls)

    def test_invalid_broken_route_is_readmitted_and_not_auto_repaired(self):
        source = invalid_broken_request()
        with self.assertRaises(Error) as caught:
            generate(source)
        self.assertEqual(caught.exception.counts, (1, 0))
        self.assertIs(type(caught.exception.__cause__), ValueError)
        self.assertIn('already safe', str(caught.exception.__cause__))
        self.assertEqual(source.scene_frames[-1].broken_plans[0].kind, Broken.FREE_MOVE_RECOVER)

    def test_removing_last_initial_shooting_target_fails_full_subset_admission(self):
        source = request()
        def short_only(participant):
            definition = participant.definition
            definition = replace(definition, id='short-only-ally',
                attacks=(replace(definition.attacks[0], range_max=Range.SHORT),))
            return replace(participant, definition=definition,
                           state=replace(participant.state, definition_id=definition.id))
        initial = transform_actor(source.template_scenario.initial, 'ally', short_only)
        template = replace(source.template_scenario, initial=initial)
        source = replace(source, template_scenario=template)
        # Full reserve includes enemy@arena within Short. Prefix count1 retains
        # blocker@middle only: do not invent a new target, GM approval or move.
        with self.assertRaises(Error) as caught:
            generate(source)
        self.assertEqual(caught.exception.counts, (1, 0))
        self.assertIs(type(caught.exception.__cause__), ValueError)
        self.assertIn('initially available Shooting target', str(caught.exception.__cause__))

    def test_archived_and_empty_live_frames_retain_all_kept_placements_without_pruning(self):
        source = request()
        empty = frame(source.template_scenario.initial, live=())
        source = with_frames(source, (*source.scene_frames, empty))
        result = generate(source)
        for candidate in result.evaluation_request.candidates:
            actual = candidate.scenario
            self.assertEqual(len(actual.scene_frames), 3)
            self.assertNotIn('ally', actual.scene_frames[1].key.live_actor_ids)
            self.assertIn('ally', tuple(p.entity_id for p in actual.scene_frames[1].key.placements))
            self.assertEqual(actual.scene_frames[2].key.live_actor_ids, ())
            self.assertEqual(actual.scene_frames[2].key.placements, actual.initial.spatial_state.placements)
            self.assertEqual(actual.scene_frames[2].pair_ranges, ())
            self.assertEqual(actual.scene_frames[2].zone_ranges, empty.zone_ranges)

    def test_give_ground_and_both_broken_routes_filter_removed_friendly_path_entities(self):
        source = request()
        positions = tuple(replace(p, zone_id='middle') if p.entity_id == 'ally' else p
                          for p in source.template_scenario.initial.spatial_state.placements)
        run = NpcMagicBrokenPlan('enemy', Broken.FREE_MOVE_RUN, ('middle',),
            NpcMagicRouteFacts(('far-blocker',), False, False), 'shelter',
            NpcMagicRouteFacts(('blocker',), False, False), True)
        future = replace(frame(source.template_scenario.initial, placements=positions), broken_plans=(run,))
        source = with_frames(source, (*source.scene_frames, future))
        source = replace(source, groups=(replace(source.groups[0], actor_ids=('enemy', 'blocker')), source.groups[1]))
        candidates = generate(source).evaluation_request.candidates
        first = candidates[0].scenario
        give = next(p for p in first.initial_frame.give_ground_plans if p.actor_id == 'enemy')
        self.assertEqual(give.route.path_entity_ids, ())
        plan = first.scene_frames[-1].broken_plans[0]
        self.assertEqual((plan.free_move_route.path_entity_ids, plan.run_route.path_entity_ids), ((), ()))
        self.assertEqual(plan.free_move_zone_ids, run.free_move_zone_ids)
        self.assertEqual(plan.run_destination_zone_id, run.run_destination_zone_id)
        self.assertTrue(plan.fastest_route_confirmed)
        complete = candidates[-1].scenario.scene_frames[-1].broken_plans[0]
        self.assertEqual(complete, run)

    def test_result_requires_typed_complete_ordered_family_and_common_metadata(self):
        result = generate(request())
        source, evaluation = result.source_request, result.evaluation_request
        for changes in ({'source_request': None}, {'source_request': evaluation},
                        {'evaluation_request': None}, {'evaluation_request': source}):
            with self.subTest(changes=changes), self.assertRaises(TypeError):
                replace(result, **changes)
        changes = ({'master_seed': 43}, {'stages': (Stage(10, 1), Stage(100, 1))},
                   {'max_total_trials': 241}, {'window': Window(F(0), F(1, 2), F(1))},
                   {'candidates': evaluation.candidates[:-1]}, {'candidates': evaluation.candidates[::-1]},
                   {'candidates': (replace(evaluation.candidates[0], candidate_id='renamed'), *evaluation.candidates[1:])},
                   {'candidates': (*evaluation.candidates[:-1], replace(evaluation.candidates[0], candidate_id='duplicate-source'))})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(result, evaluation_request=replace(evaluation, **change))

    def test_result_binds_same_id_wizard_caster_profile_day_and_objective(self):
        result = generate(request())
        scenario = result.evaluation_request.candidates[-1].scenario
        wizard = scenario.initial.wizard
        level = rebuild_initial(scenario, wizard=replace(wizard, caster=replace(wizard.caster, wizard_level=3)))
        willpower = InlineProfile(4, 3)
        caster = rebuild_initial(scenario,
            wizard=replace(wizard, caster=replace(wizard.caster, casting_profile=willpower)),
            scenario_changes={'actors': tuple(replace(p, willpower_profile=willpower)
                if p.actor_id == 'wizard' else p for p in scenario.actors)})
        daily = rebuild_initial(scenario, daily_wounds=replace(scenario.initial.champion_attack.daily_wounds, day_id='another-day'))
        def changed(participant):
            definition = replace(participant.definition, id='different-definition', source_rule_id='different-source')
            return replace(participant, definition=definition, state=replace(participant.state, definition_id=definition.id))
        profile = replace(scenario, initial=transform_actor(scenario.initial, 'blocker', changed))
        objective = replace(scenario, objective=replace(scenario.objective,
                                                       target_actor_ids=scenario.objective.target_actor_ids[::-1]))
        for foreign in (level, caster, daily, profile, objective, replace(scenario, id='different-id')):
            with self.subTest(foreign=foreign), self.assertRaises(ValueError):
                replace(result, evaluation_request=replace_last(result.evaluation_request, foreign))

    def test_result_binds_frames_routes_pairs_flags_graph_and_independent_orders(self):
        result = generate(request())
        source = result.evaluation_request.candidates[-1].scenario
        first, archive = source.scene_frames
        pair = first.pair_ranges[0]
        oriented = replace(first, pair_ranges=(replace(pair, first_actor_id=pair.second_actor_id,
            second_actor_id=pair.first_actor_id), *first.pair_ranges[1:]))
        plan = first.give_ground_plans[0]
        routed = replace(first, give_ground_plans=(replace(plan, route=replace(plan.route, path_entity_ids=())),
                                                  *first.give_ground_plans[1:]))
        flags = replace(first, attack_departures=tuple(replace(p, can_leave_zone=not p.can_leave_zone)
                                                      for p in first.attack_departures))
        archived = replace(archive, key=replace(archive.key, placements=tuple(
            replace(p, zone_id='middle') if p.entity_id == 'ally' else p for p in archive.key.placements)))
        graph = source.initial.spatial_state.graph
        graph = replace(graph, zone_ids=graph.zone_ids[::-1])
        spatial = SpatialBattleState(graph, source.initial.spatial_state.placements)
        graphed = rebuild_initial(source, spatial_state=spatial, scenario_changes={
            'scene_frames': tuple(replace(f, zone_ranges=f.zone_ranges[::-1]) for f in source.scene_frames)})
        alternatives = (replace(source, scene_frames=(oriented, archive)),
                        replace(source, scene_frames=(routed, archive)),
                        replace(source, scene_frames=(flags, archive)),
                        replace(source, scene_frames=(first, archived)),
                        replace(source, scene_frames=source.scene_frames[::-1]),
                        replace(source, activation_order=source.activation_order[::-1]), graphed)
        for foreign in alternatives:
            with self.subTest(foreign=foreign), self.assertRaises(ValueError):
                replace(result, evaluation_request=replace_last(result.evaluation_request, foreign))

    def test_equal_source_copies_frozen_replace_pickle_and_input_only_graph(self):
        source = request()
        result = generate(source)
        copied_source, copied_evaluation = deepcopy(source), deepcopy(result.evaluation_request)
        accepted = Result(copied_source, copied_evaluation)
        self.assertEqual(accepted, result)
        self.assertIs(accepted.source_request, copied_source)
        self.assertIs(accepted.evaluation_request, copied_evaluation)
        self.assertFalse(hasattr(result, '__dict__'))
        with self.assertRaises(FrozenInstanceError):
            result.evaluation_request = copied_evaluation
        self.assertEqual(pickle.loads(pickle.dumps(result)), result)
        visited = set()
        def check(value):
            if id(value) in visited:
                return
            visited.add(id(value))
            self.assertNotIn(type(value).__name__, ('NpcMagicTrialRecord', 'NpcMagicSimulationResult',
                'NpcMagicScenarioResult', 'SimulationExecutionOptions', 'Random'))
            if is_dataclass(value):
                for item in fields(value):
                    check(getattr(value, item.name))
            elif isinstance(value, (tuple, list, frozenset)):
                for item in value:
                    check(item)
        check(result)

    def test_second_admission_error_retains_candidate_counts_original_cause_notes_and_stops(self):
        source = request()
        original = generation.NpcMagicScenario
        error = OSError('late scenario admission')
        error.add_note('original admission note')
        calls = []
        def admit(*args, **kwargs):
            calls.append(kwargs['id'])
            if len(calls) == 2:
                raise error
            return original(*args, **kwargs)
        with patch.object(generation, 'NpcMagicScenario', side_effect=admit):
            with self.assertRaises(Error) as caught:
                generate(source)
        self.assertEqual(caught.exception.candidate_id, 'family:counts:1,1')
        self.assertEqual(caught.exception.counts, (1, 1))
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(error.__notes__, ['original admission note'])
        self.assertEqual(calls, ['family:counts:1,0', 'family:counts:1,1'])

    def test_interrupts_and_final_constructor_failures_pass_without_generation_context(self):
        source = request()
        for interruption in (KeyboardInterrupt('stop'), SystemExit(7)):
            with self.subTest(interruption=interruption), patch.object(generation, 'NpcMagicScenario', side_effect=interruption):
                with self.assertRaises(type(interruption)) as caught:
                    generate(source)
                self.assertIs(caught.exception, interruption)
        for target in ('MagicStagedEvaluationRequest', 'MagicCandidateGenerationResult'):
            error = ValueError('final assembly failure')
            with self.subTest(target=target), patch.object(generation, target, side_effect=error):
                with self.assertRaises(ValueError) as caught:
                    generate(source)
                self.assertIs(caught.exception, error)
                self.assertIsNone(error.__cause__)

    def test_wrong_root_type_fails_before_any_construction(self):
        with patch.object(generation, '_count_vectors', side_effect=AssertionError('must not enumerate')):
            for source in (None, object(), request().template_scenario):
                with self.subTest(source=source), self.assertRaises(TypeError):
                    generate(source)

    def test_generation_and_result_guards_do_not_execute_rng_runner_evaluator_pool_or_io(self):
        source = request()
        before, rng_before = deepcopy(source), getstate()
        targets = ('random.Random', 'random.randint', 'towr.engine.npc_magic_scenario_runner.run_npc_magic_scenario',
            'towr.simulation.npc_magic_simulation.run_npc_magic_simulation',
            'towr.application.magic_evaluation_service.evaluate_magic_candidates',
            'towr.application.magic_staged_evaluation_service.evaluate_magic_candidates_staged',
            'concurrent.futures.ProcessPoolExecutor', 'builtins.open')
        with ExitStack() as stack:
            for target in targets:
                stack.enter_context(patch(target, side_effect=AssertionError('forbidden: ' + target)))
            result = generate(source)
            self.assertEqual(Result(source, result.evaluation_request), result)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), rng_before)


if __name__ == '__main__':
    unittest.main()
