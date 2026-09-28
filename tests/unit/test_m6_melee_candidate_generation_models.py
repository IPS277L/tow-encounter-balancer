from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction as F
import unittest
from unittest.mock import patch

from tests.unit.test_m6_npc_melee_scenario import scenario
from tests.unit.test_m2_npc_ranged_scenario import scenario as ranged_scenario
from towr.application.melee_candidate_generation_models import (
    MeleeCompositionGroup as Group, MeleeCandidateGenerationRequest as Request,
)
from towr.application.ranged_candidate_generation_models import RangedCompositionGroup
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as Window
from towr.balance.melee_staged_evaluation_models import MeleeBalanceStage as Stage
from towr.balance.ranged_staged_evaluation_models import RangedBalanceStage
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.spatial_models import ZoneGraph
from towr.simulation.npc_melee_models import NpcMeleeSimulationRequest


def request():
    template = scenario(sizes=(2, 3), approved=False)
    enemies = template.objective.target_actor_ids
    return Request(template, (Group("A", enemies[:2][::-1], 0, 2), Group("B", enemies[2:], 0, 1)),
                   replace(template.facts), "family", 5, 42, (Stage(10, 2), Stage(100, 1)), 250,
                   Window(F(1, 4), F(1, 2), F(3, 4)))


def changed_definition(template, actor_id):
    actors = []
    for actor in template.initial.current.state.roster.participants:
        if actor.state.actor_id == actor_id:
            definition = replace(actor.definition, id="other-definition")
            actor = replace(actor, definition=definition, state=replace(actor.state, definition_id=definition.id))
        actors.append(actor)
    current = replace(template.initial.current, state=NpcRosterAttackState(NpcRoster(tuple(actors))))
    return replace(template, initial=replace(template.initial, current=current))


class M6MeleeGenerationModelTests(unittest.TestCase):
    def test_counts_and_budget_caps_include_complete_repeated_batches(self):
        source = request()
        self.assertEqual((source.candidate_count, source.planned_trials), (5, 250))
        for changes in ({"max_candidates": 4}, {"max_total_trials": 249},
                        {"groups": tuple(replace(g, maximum_count=0) for g in source.groups)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, **changes)
        positive = replace(source, groups=(replace(source.groups[0], minimum_count=1), source.groups[1]))
        self.assertEqual((positive.candidate_count, positive.planned_trials), (4, 240))
        fixed = replace(source, groups=(replace(source.groups[0], minimum_count=1, maximum_count=1),
                                       replace(source.groups[1], maximum_count=0)))
        self.assertEqual((fixed.candidate_count, fixed.planned_trials), (1, 110))

    def test_group_requires_unique_nonempty_exact_ids_and_integer_bounds(self):
        group = request().groups[0]
        for value in (None, True, 1, "", " "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(group, group_id=value)
        for ids in ((), ("",), (" ",), (None,), (1,), (group.actor_ids[0],) * 2):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                replace(group, actor_ids=ids)
        for name in ("minimum_count", "maximum_count"):
            for value in (None, True, "1", 1.5, -1, 3):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replace(group, **{name: value})
        with self.assertRaises(ValueError):
            replace(group, minimum_count=2, maximum_count=1)
        exact = Group(" A ", (" x ", "x"), 0, 2)
        self.assertEqual((exact.group_id, exact.actor_ids), (" A ", (" x ", "x")))

    def test_partition_rejects_missing_unknown_friendly_overlap_and_duplicate_group_ids(self):
        source = request()
        first, last = source.groups
        invalid = ((), (first,), (first, replace(last, group_id=first.group_id)),
                   (first, replace(last, actor_ids=("unknown",))),
                   (first, replace(last, actor_ids=("actor:0:0",))),
                   (first, replace(last, actor_ids=(first.actor_ids[0], *last.actor_ids))))
        for groups in invalid:
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                replace(source, groups=groups)

    def test_full_definition_identity_is_required_only_within_each_group(self):
        source = request()
        with self.assertRaises(ValueError):
            replace(source, template_scenario=changed_definition(source.template_scenario, source.groups[0].actor_ids[0]))
        changed = changed_definition(source.template_scenario, source.groups[1].actor_ids[0])
        accepted = replace(source, template_scenario=changed)
        self.assertIs(accepted.template_scenario, changed)
        self.assertEqual(accepted.candidate_count, 5)

    def test_partition_follows_explicit_perspective_in_both_directions(self):
        source = request()
        template = source.template_scenario
        roster = template.initial.current.state.roster
        other_side = roster.participants[-1].state.side
        targets = tuple(actor.state.actor_id for actor in roster.participants if actor.state.side is not other_side)
        flipped = replace(template, perspective_side=other_side, objective=replace(template.objective, target_actor_ids=targets))
        with self.assertRaises(ValueError):
            replace(source, template_scenario=flipped)
        accepted = replace(source, template_scenario=flipped, groups=(Group("other", targets, 0, 2),))
        self.assertEqual((accepted.candidate_count, accepted.planned_trials), (2, 220))

    def test_rejects_ranged_and_untyped_inputs(self):
        source = request()
        ranged = ranged_scenario()
        changes = ({"template_scenario": ranged}, {"facts": ranged.facts},
                   {"groups": (RangedCompositionGroup("A", source.groups[0].actor_ids, 0, 2),)},
                   {"stages": (Stage(10, 1), RangedBalanceStage(100, 1))},
                   {"groups": (None,)}, {"stages": (None,)})
        for change in (*changes, *({name: None} for name in ("template_scenario", "facts", "window"))):
            with self.subTest(change=change), self.assertRaises(TypeError):
                replace(source, **change)

    def test_prefix_caps_and_seed_admission(self):
        source = request()
        for prefix in (None, True, "", " "):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                replace(source, candidate_id_prefix=prefix)
        self.assertEqual(replace(source, candidate_id_prefix=" family ").candidate_id_prefix, " family ")
        for name in ("max_candidates", "max_total_trials"):
            for value in (None, True, 1.5, "250", 0, -1):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replace(source, **{name: value})
        for seed in (None, True, 1.5, "42"):
            with self.subTest(seed=seed), self.assertRaises(TypeError):
                replace(source, master_seed=seed)
        for seed in (-1, 2**64):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                replace(source, master_seed=seed)
        for seed in (0, 2**64 - 1):
            self.assertEqual(replace(source, master_seed=seed).master_seed, seed)

    def test_all_stages_checked_and_keep_cannot_regrow_family(self):
        source = request()
        for stages in ((), (Stage(10, 2), Stage(10, 1)), (Stage(10, 2), Stage(9, 1))):
            with self.subTest(stages=stages), self.assertRaises(ValueError):
                replace(source, stages=stages)
        with self.assertRaises(TypeError):
            replace(source, stages=(Stage(10, 1), Stage(100, 1), None))
        for stages, total in (((Stage(10, 20),), 50),
                              ((Stage(10, 1), Stage(100, 10), Stage(1000, 20)), 1150)):
            accepted = replace(source, stages=stages, max_total_trials=total)
            self.assertEqual(accepted.planned_trials, total)
            with self.assertRaises(ValueError):
                replace(accepted, max_total_trials=total-1)

    def test_family_facts_are_required_and_zone_must_match_even_if_present_in_graph(self):
        source = request()
        self.assertIsNot(source.facts, source.template_scenario.facts)
        with self.assertRaisesRegex(ValueError, "Zone"):
            replace(source, facts=replace(source.facts, zone_id="exit"))
        with self.assertRaisesRegex(TypeError, "facts"):
            Request(template_scenario=source.template_scenario, groups=source.groups,
                    candidate_id_prefix="family", max_candidates=5, master_seed=42,
                    stages=source.stages, max_total_trials=250, window=source.window)

    def test_family_escape_path_checked_without_inferring_false_from_geometry(self):
        source = request()
        closed_facts = replace(source.facts, can_leave_zone=False)
        accepted = replace(source, facts=closed_facts)
        self.assertIs(accepted.facts, closed_facts)
        self.assertTrue(accepted.template_scenario.facts.can_leave_zone)
        template = source.template_scenario
        spatial = replace(template.initial.spatial_state, graph=ZoneGraph(("arena", "exit"), ()))
        closed = replace(template, facts=closed_facts, initial=replace(template.initial, spatial_state=spatial))
        with self.assertRaisesRegex(ValueError, "adjacent Zone"):
            replace(source, template_scenario=closed)
        accepted = replace(source, template_scenario=closed, facts=closed_facts)
        self.assertEqual(accepted.planned_trials, 250)

    def test_keeps_both_gm_flags_full_decisions_and_independent_input_orders(self):
        source = request()
        template = source.template_scenario
        first = template.actor_policies[0]
        changed = replace(first, outnumbering_bonus_approved=True,
                          target_actor_ids=first.target_actor_ids[::-1], defeat_decisions=first.defeat_decisions[::-1])
        template = replace(template, actor_policies=(changed, *template.actor_policies[1:]))
        before = deepcopy(template)
        accepted = replace(source, template_scenario=template, groups=source.groups[::-1])
        self.assertIs(accepted.template_scenario, template)
        self.assertEqual(template, before)
        self.assertTrue(template.actor_policies[0].outnumbering_bonus_approved)
        self.assertFalse(template.actor_policies[1].outnumbering_bonus_approved)
        self.assertEqual(accepted.groups, source.groups[::-1])
        self.assertEqual(accepted.planned_trials, 250)

    def test_tuple_copies_frozen_slots_replace_and_derived_fields(self):
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
        for obj, name in ((group, "minimum_count"), (normalized, "max_candidates")):
            self.assertFalse(hasattr(obj, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, name, 0)
        for name in ("candidate_count", "planned_trials"):
            with self.assertRaises(TypeError):
                replace(source, **{name: 0})
        self.assertEqual(source, before)

    def test_huge_family_uses_arithmetic_and_one_seed_admission_without_execution(self):
        template = scenario(sizes=(1, 40))
        groups = tuple(Group(actor, (actor,), 0, 1) for actor in template.objective.target_actor_ids)
        count = 2**40 - 1
        with patch("itertools.product", side_effect=AssertionError("enumeration")), \
                patch("random.Random", side_effect=AssertionError("RNG")), \
                patch("towr.balance.melee_evaluation_models.MeleeBalanceCandidate", side_effect=AssertionError("candidate")), \
                patch("towr.engine.npc_melee_scenario_runner.run_npc_melee_scenario", side_effect=AssertionError("runner")), \
                patch("concurrent.futures.ProcessPoolExecutor", side_effect=AssertionError("pool")), \
                patch("towr.application.melee_candidate_generation_models.NpcMeleeSimulationRequest",
                      wraps=NpcMeleeSimulationRequest) as admission:
            source = Request(template, groups, replace(template.facts), "huge", count, 42,
                             (Stage(1, 1), Stage(2, 1)), count + 2,
                             Window(F(0), F(1, 2), F(1)))
            admission.assert_called_once_with(template, 42, 1)
            self.assertEqual((source.candidate_count, source.planned_trials), (count, count + 2))
            for change in ({"max_candidates": count - 1}, {"max_total_trials": count + 1}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    replace(source, **change)


if __name__ == "__main__":
    unittest.main()
