from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction as F
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m2_npc_ranged_scenario import scenario as ranged_scenario
from tests.unit.test_m6_npc_melee_scenario import scenario as melee_scenario
from tests.unit.test_m7_npc_mixed_scenario import scenario
from towr.application.melee_candidate_generation_models import MeleeCompositionGroup
from towr.application.mixed_candidate_generation_models import (
    MixedCompositionGroup as Group, MixedCandidateGenerationRequest as Request,
)
from towr.application.ranged_candidate_generation_models import RangedCompositionGroup
from towr.balance.melee_staged_evaluation_models import MeleeBalanceStage
from towr.balance.mixed_staged_evaluation_models import MixedBalanceStage as Stage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as Window
from towr.balance.ranged_staged_evaluation_models import RangedBalanceStage
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.simulation.npc_mixed_models import NpcMixedSimulationRequest


def request():
    template = scenario(sizes=(3, 3), enemy_bow=True, approved=False)
    enemies = template.objective.target_actor_ids
    return Request(template, (Group("A", enemies[1:][::-1], 1, 2), Group("B", enemies[:1], 0, 1)),
                   replace(template.facts), tuple(replace(p) for p in template.pair_ranges),
                   "family", 4, 42, (Stage(10, 2), Stage(100, 1)), 240,
                   Window(F(1, 4), F(1, 2), F(3, 4)))


def changed_definition(template, actor_id):
    # Roster already forbids conflicting definitions with the same ID.
    # Keep numeric capabilities equal while changing the admitted source.
    actors = []
    for actor in template.initial.current.state.roster.participants:
        if actor.state.actor_id == actor_id:
            definition = replace(actor.definition, id="other-definition", source_rule_id="other-source")
            actor = replace(actor, definition=definition, state=replace(actor.state, definition_id=definition.id))
        actors.append(actor)
    current = replace(template.initial.current, state=NpcRosterAttackState(NpcRoster(tuple(actors))))
    return replace(template, initial=replace(template.initial, current=current))


class M7MixedGenerationModelTests(unittest.TestCase):
    def test_counts_and_full_repeated_budget_caps(self):
        source = request()
        self.assertEqual((source.candidate_count, source.planned_trials), (4, 240))
        for changes in ({"max_candidates": 3}, {"max_total_trials": 239},
                        {"groups": tuple(replace(g, minimum_count=0, maximum_count=0) for g in source.groups)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, **changes)
        fixed = replace(source, groups=(replace(source.groups[0], maximum_count=1),
                                       replace(source.groups[1], maximum_count=0)))
        self.assertEqual((fixed.candidate_count, fixed.planned_trials), (1, 110))
        # The entire reserve is partitioned even when maximum_count is smaller.
        self.assertEqual(fixed.groups[0].actor_ids, source.groups[0].actor_ids)

    def test_preflight_counts_inadmissible_subsets_without_filtering_or_materializing(self):
        source = request()
        widened = replace(source, groups=(replace(source.groups[0], minimum_count=0), source.groups[1]),
                          max_candidates=5, max_total_trials=250)
        # (0,1) leaves only the opposing bow: fixed Melee actors lack Close targets.
        # C deliberately counts that vector; future construction must reject it.
        self.assertEqual((widened.candidate_count, widened.planned_trials), (5, 250))
        for changes in ({"max_candidates": 4}, {"max_total_trials": 249}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(widened, **changes)
        bow_only = replace(source, groups=(replace(source.groups[0], minimum_count=0, maximum_count=0),
                                          replace(source.groups[1], minimum_count=1)))
        self.assertEqual((bow_only.candidate_count, bow_only.planned_trials), (1, 110))

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

    def test_ordered_sequences_reject_sets_mappings_strings_and_iterators(self):
        source = request()
        for value in (None, "ab", {"a", "b"}, {"a": 1}, iter(("a", "b"))):
            with self.subTest(value=value), self.assertRaises(TypeError):
                replace(source.groups[0], actor_ids=value)
        for name in ("groups", "pair_ranges", "stages"):
            original = getattr(source, name)
            for value in (None, "ab", set(original), {0: original[0]}, iter(original)):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    replace(source, **{name: value})

    def test_exact_partition_rejects_missing_unknown_friendly_overlap_and_duplicate_groups(self):
        source = request()
        first, last = source.groups
        friendly = source.template_scenario.initial.current.actor_order[0]
        invalid = ((), (first,), (first, replace(last, group_id=first.group_id)),
                   (first, replace(last, actor_ids=("unknown",))),
                   (first, replace(last, actor_ids=(friendly,))),
                   (first, replace(last, actor_ids=(first.actor_ids[0], *last.actor_ids))))
        for groups in invalid:
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                replace(source, groups=groups)

    def test_full_definition_required_within_groups_but_equal_groups_allowed(self):
        source = request()
        with self.assertRaisesRegex(ValueError, "exact NPC definition"):
            replace(source, template_scenario=changed_definition(source.template_scenario, source.groups[0].actor_ids[0]))
        changed = changed_definition(source.template_scenario, source.groups[1].actor_ids[0])
        self.assertIs(replace(source, template_scenario=changed).template_scenario, changed)
        with self.assertRaisesRegex(ValueError, "exact NPC definition"):
            replace(source, groups=(Group("all", source.template_scenario.objective.target_actor_ids, 1, 1),))
        # Identical Melee definitions in different groups are not deduplicated.
        a, b = source.groups[0].actor_ids
        split = replace(source, groups=(Group("one", (a,), 1, 1), Group("two", (b,), 0, 1), source.groups[1]))
        self.assertEqual((split.candidate_count, split.planned_trials), (4, 240))

    def test_partition_follows_explicit_perspective_in_both_directions(self):
        source = request()
        template = source.template_scenario
        roster = template.initial.current.state.roster
        other_side = roster.participants[-1].state.side
        targets = tuple(p.state.actor_id for p in roster.participants if p.state.side is not other_side)
        flipped = replace(template, perspective_side=other_side, objective=replace(template.objective, target_actor_ids=targets))
        with self.assertRaisesRegex(ValueError, "partition"):
            replace(source, template_scenario=flipped)
        accepted = replace(source, template_scenario=flipped,
                           groups=(Group("melee", targets[1:], 1, 2), Group("bow", targets[:1], 0, 1)))
        self.assertEqual((accepted.candidate_count, accepted.planned_trials), (4, 240))
        self.assertIs(accepted.template_scenario, flipped)
        self.assertEqual(accepted.pair_ranges, source.pair_ranges)

    def test_rejects_other_scenario_families_and_untyped_inputs(self):
        source = request()
        for other, group_type, stage_type in ((melee_scenario(), MeleeCompositionGroup, MeleeBalanceStage),
                                               (ranged_scenario(), RangedCompositionGroup, RangedBalanceStage)):
            changes = ({"template_scenario": other}, {"facts": other.facts},
                       {"groups": (group_type("A", source.groups[0].actor_ids, 1, 2),)},
                       {"stages": (Stage(10, 1), stage_type(100, 1))})
            for change in changes:
                with self.subTest(change=change), self.assertRaises(TypeError):
                    replace(source, **change)
        changes = ({name: None} for name in ("template_scenario", "facts", "window"))
        for change in (*changes, {"groups": (None,)}, {"stages": (None,)}, {"pair_ranges": (None,)}):
            with self.subTest(change=change), self.assertRaises(TypeError):
                replace(source, **change)

    def test_family_facts_and_pairs_are_required_explicitly(self):
        source = request()
        self.assertIsNot(source.facts, source.template_scenario.facts)
        self.assertTrue(all(a is not b for a, b in zip(source.pair_ranges, source.template_scenario.pair_ranges)))
        self.assertEqual(replace(source, facts=replace(source.facts),
                                 pair_ranges=tuple(replace(p) for p in source.pair_ranges)), source)
        kwargs = {field.name: getattr(source, field.name) for field in fields(source)}
        for name in ("facts", "pair_ranges"):
            with self.subTest(name=name), self.assertRaisesRegex(TypeError, name):
                Request(**{key: value for key, value in kwargs.items() if key != name})

    def test_pair_ranges_must_match_exact_values_order_and_orientation(self):
        source = request()
        pairs = source.pair_ranges
        first = pairs[0]
        invalid = ((), pairs[:-1], (*pairs, first), (first, *pairs[2:], first), pairs[::-1],
                   (replace(first, first_actor_id="foreign"), *pairs[1:]),
                   (replace(first, target_range=Range.CLOSE), *pairs[1:]),
                   (replace(first, first_actor_id=first.second_actor_id,
                            second_actor_id=first.first_actor_id), *pairs[1:]))
        for value in invalid:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "exact ordered"):
                replace(source, pair_ranges=value)
        # Reorientation and reordering remain legal in a separately authored
        # template, provided the explicit family source matches it exactly.
        reoriented = invalid[-1][::-1]
        template = replace(source.template_scenario, pair_ranges=reoriented)
        accepted = replace(source, template_scenario=template, pair_ranges=reoriented)
        self.assertEqual(accepted.pair_ranges, reoriented)
        with self.assertRaises(TypeError):
            replace(source, pair_ranges=tuple((p.first_actor_id, p.second_actor_id, p.target_range) for p in pairs))

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

    def test_all_stages_validated_and_keep_cannot_regrow_family(self):
        source = request()
        for stages in ((), (Stage(10, 2), Stage(10, 1)), (Stage(10, 2), Stage(9, 1))):
            with self.subTest(stages=stages), self.assertRaises(ValueError):
                replace(source, stages=stages)
        with self.assertRaises(TypeError):
            replace(source, stages=(Stage(10, 1), Stage(100, 1), None))
        for stages, total in (((Stage(10, 20),), 40),
                              ((Stage(10, 1), Stage(100, 10), Stage(1000, 20)), 1140)):
            accepted = replace(source, stages=stages, max_total_trials=total)
            self.assertEqual(accepted.planned_trials, total)
            with self.assertRaises(ValueError):
                replace(accepted, max_total_trials=total - 1)
        for trial_count in (True, 0, -1, 1.5, 2**64):
            with self.subTest(trial_count=trial_count), self.assertRaises(ValueError):
                Stage(trial_count, 1)

    def test_full_template_policies_gm_flags_escape_facts_and_orders_preserved(self):
        source = request()
        template = source.template_scenario
        first = template.actor_policies[0]
        changed = replace(first, outnumbering_bonus_approved=True, can_leave_zone=True,
                          target_actor_ids=first.target_actor_ids[::-1], defeat_decisions=first.defeat_decisions[::-1])
        template = replace(template, actor_policies=(changed, *template.actor_policies[1:]))
        before, rng_before = deepcopy(template), getstate()
        accepted = replace(source, template_scenario=template, groups=source.groups[::-1])
        self.assertIs(accepted.template_scenario, template)
        self.assertEqual(template, before)
        self.assertEqual(getstate(), rng_before)
        self.assertTrue(template.actor_policies[0].outnumbering_bonus_approved)
        self.assertTrue(template.actor_policies[0].can_leave_zone)
        self.assertFalse(template.actor_policies[1].outnumbering_bonus_approved)
        self.assertFalse(template.actor_policies[1].can_leave_zone)
        self.assertEqual(accepted.groups, source.groups[::-1])
        self.assertEqual(accepted.planned_trials, 240)

    def test_tuple_copies_frozen_slots_replace_and_derived_fields(self):
        source = request()
        before = deepcopy(source)
        actors = list(source.groups[0].actor_ids)
        group = replace(source.groups[0], actor_ids=actors)
        groups, pairs, stages = [group, source.groups[1]], list(source.pair_ranges), list(source.stages)
        normalized = replace(source, groups=groups, pair_ranges=pairs, stages=stages)
        for items in (actors, groups, pairs, stages):
            items.clear()
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
        template = scenario(sizes=(3, 40), enemy_bow=True)
        groups = tuple(Group(actor, (actor,), 0, 1) for actor in template.objective.target_actor_ids)
        count = 2**40 - 1
        before, rng_before = deepcopy(template), getstate()
        with patch("itertools.product", side_effect=AssertionError("enumeration")), \
                patch("random.Random", side_effect=AssertionError("RNG")), \
                patch("towr.balance.mixed_evaluation_models.MixedBalanceCandidate", side_effect=AssertionError("candidate")), \
                patch("towr.domain.npc_mixed_scenario_models.NpcMixedScenario.__post_init__",
                      side_effect=AssertionError("projection")), \
                patch("towr.engine.npc_mixed_scenario_runner.run_npc_mixed_scenario", side_effect=AssertionError("runner")), \
                patch("concurrent.futures.ProcessPoolExecutor", side_effect=AssertionError("pool")), \
                patch("towr.application.mixed_candidate_generation_models.NpcMixedSimulationRequest",
                      wraps=NpcMixedSimulationRequest) as admission:
            source = Request(template, groups, replace(template.facts), template.pair_ranges, "huge", count, 42,
                             (Stage(1, 1), Stage(2, 1)), count + 2, Window(F(0), F(1, 2), F(1)))
            admission.assert_called_once_with(template, 42, 1)
            self.assertEqual((source.candidate_count, source.planned_trials), (count, count + 2))
            for change in ({"max_candidates": count - 1}, {"max_total_trials": count + 1}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    replace(source, **change)
        self.assertEqual(template, before)
        self.assertEqual(getstate(), rng_before)


if __name__ == "__main__":
    unittest.main()
