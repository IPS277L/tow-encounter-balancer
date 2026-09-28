from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.unit.test_m5_ranged_candidate_generation_models import request, Group
from towr.application import ranged_candidate_generation as generation
from towr.application.ranged_candidate_generation_errors import RangedCandidateGenerationError
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.spatial_models import ZoneGraph, ZoneConnection
from towr.domain.turn_models import CombatSide


class M5RangedGenerationTests(unittest.TestCase):
    def test_lexicographic_vectors_prefixes_and_identical_profiles_do_not_deduplicate(self):
        source = request()
        result = generation.generate_ranged_candidates(source)
        candidates = result.evaluation_request.candidates
        self.assertEqual([c.candidate_id for c in candidates], [
            "family:counts:0,1", "family:counts:1,0", "family:counts:1,1", "family:counts:2,0", "family:counts:2,1",
        ])
        self.assertEqual([c.scenario.objective.target_actor_ids for c in candidates], [
            ("actor:1:2",), ("actor:1:0",), ("actor:1:0", "actor:1:2"),
            ("actor:1:0", "actor:1:1"), ("actor:1:0", "actor:1:1", "actor:1:2"),
        ])
        self.assertEqual(result.evaluation_request.planned_trials, 250)
        self.assertEqual(generation.generate_ranged_candidates(source), result)
        restricted = replace(source, groups=(replace(source.groups[0], minimum_count=1), source.groups[1]))
        reduced = generation.generate_ranged_candidates(restricted)
        self.assertEqual(reduced.evaluation_request.candidates, candidates[1:])

    def test_projection_preserves_all_independent_orders_snapshots_and_family_facts(self):
        source = request()
        template = source.template_scenario
        current, spatial = template.initial.current, template.initial.spatial_state
        roster = NpcRoster(current.state.roster.participants[::-1])
        combat = replace(current.round_state, participants=current.round_state.participants[2:] + current.round_state.participants[:2],
                         side_order=current.round_state.side_order[::-1])
        graph = ZoneGraph((*spatial.graph.zone_ids, "unused"), (*spatial.graph.connections, ZoneConnection("zone:0", "unused")))
        spatial = replace(spatial, graph=graph, placements=spatial.placements[::-1])
        current = replace(current, state=NpcRosterAttackState(roster), round_state=combat,
                          actor_order=current.actor_order[1:] + current.actor_order[:1])
        policies = tuple(replace(p, target_actor_ids=p.target_actor_ids[::-1], defeat_decisions=p.defeat_decisions[::-1])
                         for p in template.actor_policies[::-1])
        template = replace(template, initial=replace(template.initial, current=current, spatial_state=spatial),
                           actor_policies=policies, objective=replace(template.objective, target_actor_ids=template.objective.target_actor_ids[::-1]))
        source = replace(source, template_scenario=template)
        before = deepcopy(source)
        for candidate in generation.generate_ranged_candidates(source).evaluation_request.candidates:
            scenario = candidate.scenario
            actors = {p.state.actor_id for p in scenario.initial.current.state.roster.participants}
            self.assertTrue({"actor:0:0", "actor:0:1"} <= actors)
            self.assertEqual(scenario.initial.current.state.roster.participants,
                             tuple(p for p in roster.participants if p.state.actor_id in actors))
            self.assertEqual(scenario.initial.current.round_state.participants,
                             tuple(p for p in combat.participants if p.entity_id in actors))
            self.assertEqual(scenario.initial.current.actor_order, tuple(a for a in current.actor_order if a in actors))
            self.assertEqual(scenario.initial.current.round_state.side_order, combat.side_order)
            self.assertEqual(scenario.initial.spatial_state.placements, tuple(p for p in spatial.placements if p.entity_id in actors))
            self.assertIs(scenario.initial.spatial_state.graph, graph)
            self.assertEqual(tuple(p.actor_id for p in scenario.actor_policies), tuple(p.actor_id for p in policies if p.actor_id in actors))
            for policy in scenario.actor_policies:
                original = template.policy_for(policy.actor_id)
                self.assertEqual(policy.target_actor_ids, tuple(a for a in original.target_actor_ids if a in actors))
                self.assertEqual(policy.defeat_decisions, tuple(d for d in original.defeat_decisions if d.target_id in actors))
                for decision in policy.defeat_decisions:
                    self.assertTrue(any(decision is old for old in original.defeat_decisions))
            self.assertEqual(scenario.objective.target_actor_ids, tuple(a for a in template.objective.target_actor_ids if a in actors))
            self.assertIs(scenario.facts, source.facts)
            self.assertIsNot(source.facts, template.facts)
            self.assertEqual(scenario.initial.current.id, candidate.candidate_id + ":initial")
            self.assertEqual(scenario.initial.max_rounds, template.initial.max_rounds)
            self.assertEqual(replace(scenario), scenario)  # Re-admission accepts the fresh output.
            self.assertEqual(scenario.initial.current.state, NpcRosterAttackState(scenario.initial.current.state.roster))
        self.assertEqual(source, before)

    def test_group_reserve_order_controls_prefix_membership_but_not_turn_order(self):
        source = request()
        source = replace(source, groups=(replace(source.groups[0], actor_ids=source.groups[0].actor_ids[::-1]), source.groups[1]))
        candidates = generation.generate_ranged_candidates(source).evaluation_request.candidates
        self.assertEqual(candidates[1].scenario.objective.target_actor_ids, ("actor:1:1",))
        self.assertEqual(candidates[-1].scenario.initial.current.actor_order, source.template_scenario.initial.current.actor_order)
        reversed_groups = generation.generate_ranged_candidates(replace(source, groups=source.groups[::-1]))
        self.assertEqual(reversed_groups.evaluation_request.candidates[0].scenario.objective.target_actor_ids, ("actor:1:1",))

    def test_either_side_can_be_fixed_and_reserve_may_exceed_selected_maximum(self):
        source = request()
        template = replace(source.template_scenario, perspective_side=CombatSide.OPPOSITION,
                           objective=replace(source.template_scenario.objective, target_actor_ids=("actor:0:0", "actor:0:1")))
        source = replace(source, template_scenario=template, groups=(Group("allies", ("actor:0:0", "actor:0:1"), 1, 1),))
        candidates = generation.generate_ranged_candidates(source).evaluation_request.candidates
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].scenario.objective.target_actor_ids, ("actor:0:0",))
        actors = {p.state.actor_id for p in candidates[0].scenario.initial.current.state.roster.participants}
        self.assertEqual(actors, {"actor:0:0", "actor:1:0", "actor:1:1", "actor:1:2"})

    def test_generation_never_calls_runner_rng_or_pool_and_requires_typed_input(self):
        with patch("towr.application.ranged_staged_evaluation_service.evaluate_ranged_candidates") as evaluate, \
                patch("towr.simulation.npc_ranged_simulation.run_npc_ranged_scenario") as runner, \
                patch("towr.simulation.npc_ranged_parallel.ProcessPoolExecutor") as pool, \
                patch("random.Random") as rng:
            generation.generate_ranged_candidates(request())
            evaluate.assert_not_called()
            runner.assert_not_called()
            pool.assert_not_called()
            rng.assert_not_called()
        with patch.object(generation, "_project_candidate") as project:
            with self.assertRaises(TypeError):
                generation.generate_ranged_candidates(None)
            project.assert_not_called()

    def test_second_admission_failure_retains_counts_id_cause_and_stops_without_partial_output(self):
        source = request()
        constructor = generation.NpcRangedScenario
        cause = ValueError("projection admission failed")
        cause.add_note("candidate context")
        calls = []
        def admit(*args):
            calls.append(args)
            if len(calls) == 2:
                raise cause
            return constructor(*args)
        with patch.object(generation, "NpcRangedScenario", side_effect=admit):
            with self.assertRaises(RangedCandidateGenerationError) as caught:
                generation.generate_ranged_candidates(source)
            self.assertEqual(len(calls), 2)
            self.assertEqual(caught.exception.candidate_id, "family:counts:1,0")
            self.assertEqual(caught.exception.counts, (1, 0))
            self.assertIs(caught.exception.__cause__, cause)
            self.assertEqual(cause.__notes__, ["candidate context"])
            self.assertFalse(hasattr(caught.exception, "partial_result"))

    def test_interrupts_are_not_wrapped_as_generation_errors(self):
        for interruption in (KeyboardInterrupt(), SystemExit(2)):
            with patch.object(generation, "NpcRangedScenario", side_effect=interruption) as admit:
                with self.assertRaises(type(interruption)) as caught:
                    generation.generate_ranged_candidates(request())
                self.assertIs(caught.exception, interruption)
                self.assertEqual(admit.call_count, 1)
