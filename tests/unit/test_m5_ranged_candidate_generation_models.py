from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction as F
import unittest
from unittest.mock import patch

from tests.unit.test_m2_npc_ranged_scenario import scenario
from towr.application.ranged_candidate_generation import generate_ranged_candidates
from towr.application.ranged_candidate_generation_models import (
    RangedCompositionGroup as Group, RangedCandidateGenerationRequest as Request,
    RangedCandidateGenerationResult as Result,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as Window
from towr.balance.ranged_staged_evaluation_models import RangedBalanceStage as Stage
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.simulation.npc_ranged_models import NpcRangedSimulationResult, NpcRangedTrialSummary


def request():
    template = scenario(sizes=(2, 3))
    enemies = template.objective.target_actor_ids
    return Request(template, (Group("A", enemies[:2], 0, 2), Group("B", enemies[2:], 0, 1)),
                   replace(template.facts), "family", 5, 42, (Stage(10, 2), Stage(100, 1)), 250,
                   Window(F(9, 20), F(1, 2), F(11, 20)))


def with_changed_definition(template, actor_id):
    current = template.initial.current
    actors = []
    for actor in current.state.roster.participants:
        if actor.state.actor_id == actor_id:
            definition = replace(actor.definition, id="other-definition")
            actor = replace(actor, definition=definition, state=replace(actor.state, definition_id=definition.id))
        actors.append(actor)
    return replace(template, initial=replace(template.initial, current=replace(
        current, state=NpcRosterAttackState(NpcRoster(tuple(actors))))))


class M5RangedGenerationModelTests(unittest.TestCase):
    def test_counts_caps_and_full_budget_are_checked_before_enumeration_or_projection(self):
        source = request()
        self.assertEqual((source.candidate_count, source.planned_trials), (5, 250))
        with patch("towr.application.ranged_candidate_generation._count_vectors") as enumerate_counts, \
                patch("towr.application.ranged_candidate_generation._project_candidate") as project, \
                patch("towr.application.ranged_candidate_generation.RangedBalanceCandidate") as candidate:
            for changes in ({"max_candidates": 4}, {"max_total_trials": 249},
                            {"groups": tuple(replace(g, maximum_count=0) for g in source.groups)}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    replace(source, **changes)
            enumerate_counts.assert_not_called()
            project.assert_not_called()
            candidate.assert_not_called()
        positive_minimum = replace(source, groups=(replace(source.groups[0], minimum_count=1), source.groups[1]))
        self.assertEqual((positive_minimum.candidate_count, positive_minimum.planned_trials), (4, 240))
        fixed = replace(source, groups=(replace(source.groups[0], minimum_count=1, maximum_count=1),
                                        replace(source.groups[1], maximum_count=0)))
        self.assertEqual((fixed.candidate_count, fixed.planned_trials), (1, 110))

    def test_group_identifiers_reserve_and_exact_integer_bounds(self):
        group = request().groups[0]
        for group_id in (None, True, 1, "", " "):
            with self.subTest(group_id=group_id), self.assertRaises(ValueError):
                replace(group, group_id=group_id)
        for ids in ((), ("",), (None,), (group.actor_ids[0],) * 2):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                replace(group, actor_ids=ids)
        for name in ("minimum_count", "maximum_count"):
            for value in (True, None, "1", 1.5, -1, 3):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replace(group, **{name: value})
        with self.assertRaises(ValueError):
            replace(group, minimum_count=2, maximum_count=1)

    def test_groups_must_partition_all_and_only_opponents_with_unique_ids(self):
        source = request()
        first, last = source.groups
        invalid = ((), (first,), (first, replace(last, group_id=first.group_id)),
                   (first, replace(last, actor_ids=("unknown",))),
                   (first, replace(last, actor_ids=("actor:0:0",))),
                   (first, replace(last, actor_ids=(first.actor_ids[0], *last.actor_ids))))
        for groups in invalid:
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                replace(source, groups=groups)
        with self.assertRaises(TypeError):
            replace(source, groups=(first, None))

    def test_full_definitions_must_match_within_each_group_but_may_differ_between_groups(self):
        source = request()
        mixed = with_changed_definition(source.template_scenario, source.groups[0].actor_ids[0])
        with self.assertRaises(ValueError):
            replace(source, template_scenario=mixed)
        different_groups = with_changed_definition(source.template_scenario, source.groups[1].actor_ids[0])
        accepted = replace(source, template_scenario=different_groups)
        self.assertEqual(accepted.candidate_count, 5)
        self.assertEqual(len(generate_ranged_candidates(accepted).evaluation_request.candidates), 5)

    def test_request_rejects_invalid_source_facts_window_prefix_seed_and_limits(self):
        source = request()
        for name in ("template_scenario", "facts", "window"):
            with self.subTest(name=name), self.assertRaises(TypeError):
                replace(source, **{name: None})
        for prefix in (None, True, "", " "):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                replace(source, candidate_id_prefix=prefix)
        for name in ("max_candidates", "max_total_trials"):
            for value in (None, True, 1.5, "250", 0, -1):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replace(source, **{name: value})
        for seed in (None, True, 1.5, "42", -1, 2**64):
            with self.subTest(seed=seed), self.assertRaises((TypeError, ValueError)):
                replace(source, master_seed=seed)
        self.assertEqual(replace(source, master_seed=2**64-1).master_seed, 2**64-1)

    def test_all_stages_are_preflighted_and_budget_caps_agree_with_staged_input(self):
        source = request()
        for stages in ((), (Stage(10, 2), Stage(10, 1)), (Stage(10, 2), Stage(9, 1))):
            with self.subTest(stages=stages), self.assertRaises(ValueError):
                replace(source, stages=stages)
        with self.assertRaises(TypeError):
            replace(source, stages=(Stage(10, 2), None))
        for stages, total in (((Stage(10, 20),), 50),
                              ((Stage(10, 1), Stage(100, 10), Stage(1000, 20)), 1150)):
            changed = replace(source, stages=stages, max_total_trials=total)
            result = generate_ranged_candidates(changed)
            self.assertEqual(changed.planned_trials, total)
            self.assertEqual(result.evaluation_request.planned_trials, total)

    def test_result_requires_exact_common_parameters_and_complete_ordered_list(self):
        result = generate_ranged_candidates(request())
        evaluation = result.evaluation_request
        for changes in ({"master_seed": 43}, {"stages": (Stage(10, 1),)}, {"max_total_trials": 251},
                        {"window": Window(F(0), F(1, 2), F(1))},
                        {"candidates": evaluation.candidates[:-1]}, {"candidates": evaluation.candidates[::-1]}):
            foreign = replace(evaluation, **changes)
            with self.subTest(changes=tuple(changes)), self.assertRaises(ValueError):
                replace(result, evaluation_request=foreign)
        for name in ("source_request", "evaluation_request"):
            with self.subTest(name=name), self.assertRaises(TypeError):
                replace(result, **{name: None})

    def test_result_rejects_foreign_prefix_definition_policy_objective_round_id_and_position(self):
        result = generate_ranged_candidates(request())
        evaluation = result.evaluation_request
        candidate = evaluation.candidates[-1]
        source = candidate.scenario
        current, spatial = source.initial.current, source.initial.spatial_state
        changed_definition = with_changed_definition(source, "actor:0:0")
        policy = source.actor_policies[0]
        changed_policy = replace(policy, target_actor_ids=policy.target_actor_ids[::-1], defeat_decisions=policy.defeat_decisions[::-1])
        changed_decision = replace(policy.defeat_decisions[0], disposition=NpcDefeatDisposition.KILLED)
        changed_disposition = replace(policy, defeat_decisions=(changed_decision, *policy.defeat_decisions[1:]))
        moved = replace(spatial, placements=tuple(replace(p, zone_id="zone:1" if p.zone_id == "zone:0" else "zone:0")
                                                 for p in spatial.placements))
        changed_scenarios = (
            changed_definition,
            replace(source, actor_policies=(changed_policy, *source.actor_policies[1:])),
            replace(source, actor_policies=(changed_disposition, *source.actor_policies[1:])),
            replace(source, objective=replace(source.objective, target_actor_ids=source.objective.target_actor_ids[::-1])),
            replace(source, initial=replace(source.initial, current=replace(current, id="foreign"))),
            replace(source, initial=replace(source.initial, spatial_state=replace(spatial, placements=spatial.placements[::-1]))),
            replace(source, initial=replace(source.initial, spatial_state=moved)),
        )
        for changed in changed_scenarios:
            foreign = replace(evaluation, candidates=(*evaluation.candidates[:-1], replace(candidate, scenario=changed)))
            with self.assertRaises(ValueError):
                replace(result, evaluation_request=foreign)
        foreign = replace(evaluation, candidates=(*evaluation.candidates[:-1], replace(candidate, candidate_id="foreign")))
        with self.assertRaises(ValueError):
            replace(result, evaluation_request=foreign)

    def test_normalization_frozen_replace_and_derived_properties(self):
        source = request()
        before = deepcopy(source)
        actors = list(source.groups[0].actor_ids)
        group = replace(source.groups[0], actor_ids=actors)
        groups, stages = [group, source.groups[1]], list(source.stages)
        normalized = replace(source, groups=groups, stages=stages)
        actors.clear()
        groups.clear()
        stages.clear()
        self.assertEqual(normalized, before)
        result = generate_ranged_candidates(normalized)
        for obj, name, value in ((group, "minimum_count", 1), (normalized, "max_candidates", 1),
                                 (result, "evaluation_request", None)):
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, name, value)
        for name in ("candidate_count", "planned_trials"):
            with self.assertRaises(TypeError):
                replace(source, **{name: 0})
        self.assertEqual(source, before)

    def test_generation_result_contains_no_simulation_records(self):
        def inspect(value):
            self.assertNotIsInstance(value, (NpcRangedSimulationResult, NpcRangedTrialSummary))
            if is_dataclass(value):
                for field in fields(value):
                    inspect(getattr(value, field.name))
            elif isinstance(value, tuple):
                for item in value:
                    inspect(item)
        inspect(generate_ranged_candidates(request()))
