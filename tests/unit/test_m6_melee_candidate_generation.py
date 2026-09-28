from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction as F
import unittest
from unittest.mock import patch

from tests.unit.test_m6_melee_candidate_generation_models import request, Group, changed_definition
from tests.unit.test_m5_ranged_candidate_generation_models import request as ranged_request
from towr.application import melee_candidate_generation as generation
from towr.application.melee_candidate_generation_errors import MeleeCandidateGenerationError
from towr.application.melee_candidate_generation_models import MeleeCandidateGenerationResult
from towr.application.ranged_candidate_generation import generate_ranged_candidates
from towr.balance.melee_staged_evaluation_models import MeleeBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.simulation.npc_melee_models import NpcMeleeSimulationResult, NpcMeleeTrialSummary
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.spatial_models import ZoneGraph, ZoneConnection
from towr.domain.turn_models import CombatSide


class M6MeleeGenerationTests(unittest.TestCase):
    def test_lexicographic_vectors_prefixes_and_identical_profiles_do_not_deduplicate(self):
        source = request()
        result = generation.generate_melee_candidates(source)
        candidates = result.evaluation_request.candidates
        self.assertEqual([c.candidate_id for c in candidates], [
            "family:counts:0,1", "family:counts:1,0", "family:counts:1,1", "family:counts:2,0", "family:counts:2,1",
        ])
        self.assertEqual([c.scenario.objective.target_actor_ids for c in candidates], [
            ("actor:1:2",), ("actor:1:1",), ("actor:1:1", "actor:1:2"),
            ("actor:1:0", "actor:1:1"), ("actor:1:0", "actor:1:1", "actor:1:2"),
        ])
        self.assertEqual(result.evaluation_request.planned_trials, 250)
        self.assertEqual(generation.generate_melee_candidates(source), result)
        restricted = replace(source, groups=(replace(source.groups[0], minimum_count=1), source.groups[1]))
        reduced = generation.generate_melee_candidates(restricted)
        self.assertEqual(reduced.evaluation_request.candidates, candidates[1:])

    def test_projection_preserves_all_independent_orders_snapshots_and_family_facts(self):
        source = request()
        template = source.template_scenario
        current, spatial = template.initial.current, template.initial.spatial_state
        roster = NpcRoster(current.state.roster.participants[::-1])
        combat = replace(current.round_state, participants=current.round_state.participants[2:] + current.round_state.participants[:2])
        graph = ZoneGraph((*spatial.graph.zone_ids, "unused"), (*spatial.graph.connections, ZoneConnection("arena", "unused")))
        spatial = replace(spatial, graph=graph, placements=spatial.placements[::-1])
        current = replace(current, state=NpcRosterAttackState(roster), round_state=combat,
                          actor_order=current.actor_order[1:] + current.actor_order[:1])
        policies = tuple(replace(p, target_actor_ids=p.target_actor_ids[::-1],
                                 defeat_decisions=tuple(replace(d, disposition=NpcDefeatDisposition.KILLED)
                                                        for d in p.defeat_decisions[::-1]),
                                 outnumbering_bonus_approved=index % 2 == 0)
                         for index, p in enumerate(template.actor_policies[::-1]))
        template = replace(template, initial=replace(template.initial, current=current, spatial_state=spatial),
                           actor_policies=policies, objective=replace(template.objective, target_actor_ids=template.objective.target_actor_ids[::-1]))
        source = replace(source, template_scenario=template, facts=replace(source.facts, can_leave_zone=False))
        before = deepcopy(source)
        for candidate in generation.generate_melee_candidates(source).evaluation_request.candidates:
            scenario = candidate.scenario
            actors = {p.state.actor_id for p in scenario.initial.current.state.roster.participants}
            self.assertTrue({"actor:0:0", "actor:0:1"} <= actors)
            self.assertEqual(scenario.initial.current.state.roster.participants,
                             tuple(p for p in roster.participants if p.state.actor_id in actors))
            for actor in scenario.initial.current.state.roster.participants:
                self.assertTrue(any(actor is original for original in roster.participants))
            self.assertEqual(scenario.initial.current.round_state.participants,
                             tuple(p for p in combat.participants if p.entity_id in actors))
            self.assertEqual(scenario.initial.current.actor_order, tuple(a for a in current.actor_order if a in actors))
            self.assertEqual(scenario.initial.current.round_state.side_order, combat.side_order)
            self.assertEqual(scenario.initial.spatial_state.placements, tuple(p for p in spatial.placements if p.entity_id in actors))
            self.assertIs(scenario.initial.spatial_state.graph, graph)
            self.assertEqual(tuple(p.actor_id for p in scenario.actor_policies), tuple(p.actor_id for p in policies if p.actor_id in actors))
            for policy in scenario.actor_policies:
                original = template.policy_for(policy.actor_id)
                self.assertIs(policy.outnumbering_bonus_approved, original.outnumbering_bonus_approved)
                self.assertEqual(policy.target_actor_ids, tuple(a for a in original.target_actor_ids if a in actors))
                self.assertEqual(policy.defeat_decisions, tuple(d for d in original.defeat_decisions if d.target_id in actors))
                for decision in policy.defeat_decisions:
                    self.assertTrue(any(decision is old for old in original.defeat_decisions))
            self.assertEqual(scenario.objective.target_actor_ids, tuple(a for a in template.objective.target_actor_ids if a in actors))
            self.assertIs(scenario.facts, source.facts)
            self.assertIsNot(source.facts, template.facts)
            self.assertFalse(scenario.facts.can_leave_zone)
            self.assertIs(scenario.repeated_stagger_choice, template.repeated_stagger_choice)
            self.assertIs(scenario.perspective_side, template.perspective_side)
            self.assertEqual(scenario.initial.current.id, candidate.candidate_id + ":initial")
            self.assertEqual(scenario.initial.max_rounds, template.initial.max_rounds)
            self.assertEqual(replace(scenario), scenario)  # Re-admission accepts the fresh output.
            self.assertEqual(scenario.initial.current.state, NpcRosterAttackState(scenario.initial.current.state.roster))
        self.assertEqual(source, before)

    def test_group_reserve_order_controls_prefix_membership_but_not_turn_order(self):
        source = request()
        candidates = generation.generate_melee_candidates(source).evaluation_request.candidates
        self.assertEqual(candidates[1].scenario.objective.target_actor_ids, ("actor:1:1",))
        self.assertEqual(candidates[-1].scenario.initial.current.actor_order, source.template_scenario.initial.current.actor_order)
        reversed_groups = generation.generate_melee_candidates(replace(source, groups=source.groups[::-1]))
        self.assertEqual(reversed_groups.evaluation_request.candidates[0].scenario.objective.target_actor_ids, ("actor:1:1",))

    def test_either_side_can_be_fixed_and_reserve_may_exceed_selected_maximum(self):
        source = request()
        template = replace(source.template_scenario, perspective_side=CombatSide.OPPOSITION,
                           objective=replace(source.template_scenario.objective, target_actor_ids=("actor:0:0", "actor:0:1")))
        source = replace(source, template_scenario=template, groups=(Group("allies", ("actor:0:0", "actor:0:1"), 1, 1),))
        candidates = generation.generate_melee_candidates(source).evaluation_request.candidates
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].scenario.objective.target_actor_ids, ("actor:0:0",))
        actors = {p.state.actor_id for p in candidates[0].scenario.initial.current.state.roster.participants}
        self.assertEqual(actors, {"actor:0:0", "actor:1:0", "actor:1:1", "actor:1:2"})

    def test_generation_never_calls_runner_rng_or_pool_and_requires_typed_input(self):
        with patch("towr.application.melee_staged_evaluation_service.evaluate_melee_candidates") as evaluate, \
                patch("towr.simulation.npc_melee_simulation.run_npc_melee_scenario") as runner, \
                patch("towr.simulation.npc_melee_parallel.ProcessPoolExecutor") as pool, \
                patch("random.Random") as rng:
            generation.generate_melee_candidates(request())
            evaluate.assert_not_called()
            runner.assert_not_called()
            pool.assert_not_called()
            rng.assert_not_called()
        with patch.object(generation, "_project_candidate") as project:
            for invalid in (None, ranged_request()):
                with self.assertRaises(TypeError):
                    generation.generate_melee_candidates(invalid)
            project.assert_not_called()

    def test_second_admission_failure_retains_counts_id_cause_and_stops_without_partial_output(self):
        source = request()
        before = deepcopy(source)
        constructor = generation.NpcMeleeScenario
        cause = ValueError("projection admission failed")
        cause.add_note("candidate context")
        calls = []
        def admit(*args):
            calls.append(args)
            if len(calls) == 2:
                raise cause
            return constructor(*args)
        with patch.object(generation, "NpcMeleeScenario", side_effect=admit):
            with self.assertRaises(MeleeCandidateGenerationError) as caught:
                generation.generate_melee_candidates(source)
            self.assertEqual(len(calls), 2)
            self.assertEqual(caught.exception.candidate_id, "family:counts:1,0")
            self.assertEqual(caught.exception.counts, (1, 0))
            self.assertIs(caught.exception.__cause__, cause)
            self.assertEqual(cause.__notes__, ["candidate context"])
            self.assertFalse(hasattr(caught.exception, "partial_result"))
        self.assertEqual(source, before)

    def test_interrupts_are_not_wrapped_as_generation_errors(self):
        for interruption in (KeyboardInterrupt(), SystemExit(2)):
            with patch.object(generation, "NpcMeleeScenario", side_effect=interruption) as admit:
                with self.assertRaises(type(interruption)) as caught:
                    generation.generate_melee_candidates(request())
                self.assertIs(caught.exception, interruption)
                self.assertEqual(admit.call_count, 1)

    def test_preflight_rejects_caps_before_enumeration_and_projection(self):
        source = request()
        with patch.object(generation, "_count_vectors") as vectors, \
                patch.object(generation, "_project_candidate") as project:
            for change in ({"max_candidates": 4}, {"max_total_trials": 249}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    generation.generate_melee_candidates(replace(source, **change))
            vectors.assert_not_called()
            project.assert_not_called()

    def test_final_construction_errors_have_no_invented_candidate_context(self):
        source = request()
        for name in ("MeleeStagedEvaluationRequest", "MeleeCandidateGenerationResult"):
            cause = ValueError("final constructor failed")
            with self.subTest(name=name), patch.object(generation, name, side_effect=cause):
                with self.assertRaises(ValueError) as caught:
                    generation.generate_melee_candidates(source)
                self.assertIs(caught.exception, cause)
                self.assertFalse(hasattr(caught.exception, "candidate_id"))

    def test_result_requires_exact_staged_parameters_and_complete_ordered_list(self):
        result = generation.generate_melee_candidates(request())
        evaluation = result.evaluation_request
        for change in ({"master_seed": 43}, {"stages": (MeleeBalanceStage(10, 1),)},
                       {"max_total_trials": 251}, {"window": ObjectiveRateWindow(F(0), F(1, 2), F(1))},
                       {"candidates": evaluation.candidates[:-1]}, {"candidates": evaluation.candidates[::-1]}):
            with self.subTest(change=tuple(change)), self.assertRaises(ValueError):
                replace(result, evaluation_request=replace(evaluation, **change))
        self.assertEqual(evaluation.planned_trials, result.source_request.planned_trials)

    def test_result_requires_melee_sources_and_rechecks_changed_generation_source(self):
        result = generation.generate_melee_candidates(request())
        for change in ({"source_request": None}, {"source_request": ranged_request()},
                       {"evaluation_request": None}, {"evaluation_request": result.source_request},
                       {"evaluation_request": generate_ranged_candidates(ranged_request()).evaluation_request}):
            with self.subTest(change=tuple(change)), self.assertRaises(TypeError):
                replace(result, **change)
        source = result.source_request
        for change in ({"candidate_id_prefix": "other"}, {"groups": source.groups[::-1]},
                       {"facts": replace(source.facts, can_leave_zone=False)}):
            with self.subTest(change=tuple(change)), self.assertRaises(ValueError):
                replace(result, source_request=replace(source, **change))

    def test_result_rejects_admitted_scenario_substitutions_including_gm_flags_and_facts(self):
        result = generation.generate_melee_candidates(request())
        evaluation = result.evaluation_request
        candidate = evaluation.candidates[-1]
        source = candidate.scenario
        current, spatial = source.initial.current, source.initial.spatial_state
        policy = source.actor_policies[0]
        reordered = replace(policy, target_actor_ids=policy.target_actor_ids[::-1],
                            defeat_decisions=policy.defeat_decisions[::-1])
        disposition = replace(policy.defeat_decisions[0], disposition=NpcDefeatDisposition.KILLED)
        changed_policies = (
            reordered, replace(policy, outnumbering_bonus_approved=not policy.outnumbering_bonus_approved),
            replace(policy, defeat_decisions=(disposition, *policy.defeat_decisions[1:])),
        )
        moved = replace(spatial, placements=tuple(replace(p, zone_id="exit") for p in spatial.placements))
        changed = (
            changed_definition(source, "actor:0:0"),
            *(replace(source, actor_policies=(p, *source.actor_policies[1:])) for p in changed_policies),
            replace(source, facts=replace(source.facts, can_leave_zone=False)),
            replace(source, objective=replace(source.objective, target_actor_ids=source.objective.target_actor_ids[::-1])),
            replace(source, initial=replace(source.initial, current=replace(current, id="foreign"))),
            replace(source, initial=replace(source.initial, current=replace(current, actor_order=current.actor_order[::-1]))),
            replace(source, initial=replace(source.initial, spatial_state=replace(spatial, placements=spatial.placements[::-1]))),
            replace(source, initial=replace(source.initial, spatial_state=moved), facts=replace(source.facts, zone_id="exit")),
            replace(source, initial=replace(source.initial, spatial_state=replace(
                spatial, graph=ZoneGraph((*spatial.graph.zone_ids, "unused"), spatial.graph.connections)))),
        )
        for index, scenario in enumerate(changed):
            foreign = replace(evaluation, candidates=(*evaluation.candidates[:-1], replace(candidate, scenario=scenario)))
            with self.subTest(index=index), self.assertRaises(ValueError):
                replace(result, evaluation_request=foreign)

    def test_result_rejects_changed_ids_and_duplicate_compositions_with_distinct_ids(self):
        result = generation.generate_melee_candidates(request())
        evaluation = result.evaluation_request
        first, second, *rest = evaluation.candidates
        alternatives = (
            (replace(first, candidate_id="foreign"), second, *rest),
            (first, replace(second, scenario=first.scenario), *rest),
        )
        for candidates in alternatives:
            with self.subTest(candidates=tuple(c.candidate_id for c in candidates)), self.assertRaises(ValueError):
                replace(result, evaluation_request=replace(evaluation, candidates=candidates))

    def test_result_is_frozen_source_bound_and_contains_no_simulation_records(self):
        source = request()
        before = deepcopy(source)
        result = generation.generate_melee_candidates(source)
        self.assertIs(result.source_request, source)
        self.assertEqual(generation.generate_melee_candidates(source), result)
        self.assertEqual(MeleeCandidateGenerationResult(deepcopy(source), deepcopy(result.evaluation_request)), result)
        self.assertEqual(source, before)
        self.assertFalse(hasattr(result, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            result.evaluation_request = None
        self.assertEqual(tuple(f.name for f in fields(result)), ("source_request", "evaluation_request"))

        def inspect(value):
            self.assertNotIsInstance(value, (NpcMeleeSimulationResult, NpcMeleeTrialSummary))
            if is_dataclass(value):
                for field in fields(value):
                    inspect(getattr(value, field.name))
            elif isinstance(value, tuple):
                for item in value:
                    inspect(item)
        inspect(result)
