from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_m2_npc_ranged_scenario import scenario, with_actor
from tests.unit.test_m2_npc_blunderbuss_round import request as blunderbuss_round
from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.npc_attack_selection_models import NpcAttackCandidate
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.test_models import Skill
from towr.engine import npc_round_coordinator as coordinator
from towr.rules import attack_action_execution as attack_executor


class ScenarioCandidates:
    """Test-only handoff; production scenario orchestration is a separate slice."""

    def __init__(self, source):
        self.source = source

    def get_candidates(self, context):
        facts = self.source.facts
        actor = context.state.roster.participant(context.actor_id)
        candidates = tuple(NpcAttackCandidate(
            context.id + ":" + target_id, actor.definition.attacks[0].id, target_id,
            facts.target_range, facts.has_enemy_in_close_range, False, facts.targets_aware,
            Skill.ATHLETICS, context.state.roster.participant(target_id).protection_options(context.id),
            True, False,
        ) for target_id in self.source.policy_for(context.actor_id).target_actor_ids)
        return replace(context, candidates=candidates)


class M2NpcRangedScenarioPreflightTests(unittest.TestCase):
    def test_validated_scenario_feeds_existing_round_with_miss_stagger_and_wound_paths(self):
        cases = (
            ("miss", [10] * 24, NpcRoundOutcome.COMPLETE, 4),
            ("stagger_then_miss", [1, 10, 10, 10, 10, 10] + [10] * 18, NpcRoundOutcome.COMPLETE, 4),
            ("repeated_stagger", [1, 10, 10, 10, 10, 10] * 2, NpcRoundOutcome.PENDING_FOLLOW_UPS, 2),
            ("wound", [1, 2, 10, 10, 10, 10], NpcRoundOutcome.PENDING_FOLLOW_UPS, 1),
        )
        for reverse in (False, True):
            for name, dice, outcome, count in cases:
                with self.subTest(reverse=reverse, path=name):
                    source = scenario(reverse=reverse)
                    before = deepcopy(source)
                    rng = Mock(wraps=SequenceRandom(dice))
                    with patch.object(attack_executor, "resolve_kernel_attack",
                                      wraps=attack_executor.resolve_kernel_attack) as kernel:
                        validated = replace(source)
                        rng.randint.assert_not_called()
                        kernel.assert_not_called()
                        result = coordinator.run_npc_round(validated.initial.current, ScenarioCandidates(validated),
                            rng, decisions=FixedKernelDecisions(stagger=validated.repeated_stagger_choice))
                    self.assertIs(result.outcome, outcome)
                    attacks = tuple(step for step in result.steps if isinstance(step, NpcRosterAttackExecutionResult))
                    self.assertEqual(len(attacks), count)
                    self.assertEqual(kernel.call_count, count)
                    self.assertEqual(rng.randint.call_count, len(dice))
                    self.assertEqual(len(result.state.consumed_execution_ids), count)
                    first_actor = source.initial.current.next_actor(source.initial.current.round_state)
                    first_target = source.policy_for(first_actor).target_actor_ids[0]
                    self.assertEqual(attacks[0].execution.target_id, first_target)
                    target = result.state.roster.participant(first_target).state.injury
                    if name == "miss":
                        self.assertTrue(all(a.execution.resolution.attack.outcome is AttackOutcome.MISS for a in attacks))
                        self.assertFalse(target.conditions.conditions)
                    elif name == "stagger_then_miss":
                        self.assertTrue(target.conditions.has(Condition.STAGGERED))
                        self.assertFalse(target.defeated)
                    else:
                        self.assertTrue(target.defeated)
                        self.assertEqual(target.wounds, 1)
                        self.assertEqual(len(result.pending_follow_ups), 1)
                    self.assertEqual(source, before)
                    # Used round/receipt state is never admitted as a new scenario.
                    with self.assertRaisesRegex(ValueError, "fresh first round"):
                        replace(source, initial=replace(source.initial, current=result.continuation))

    def test_ablaze_is_rejected_before_round_execution_or_rng(self):
        source = scenario()
        invalid = with_actor(source, state_changes={
            "injury": ProfileInjuryState(0, 1, ConditionState({Condition.ABLAZE})),
        })
        rng = Mock()
        with patch.object(coordinator, "run_npc_round") as run:
            with self.assertRaisesRegex(ValueError, "without Conditions"):
                admitted = replace(source, initial=invalid)
                coordinator.run_npc_round(admitted.initial.current, ScenarioCandidates(admitted), rng)
            run.assert_not_called()
        rng.randint.assert_not_called()
        self.assertTrue(invalid.current.state.roster.participants[0].state.injury.conditions.has(Condition.ABLAZE))

    def test_weapon_bound_round_is_rejected_without_consuming_reload_or_rng(self):
        source = scenario()
        current = blunderbuss_round()
        spatial = replace(source.initial.spatial_state, placements=tuple(
            replace(placement, entity_id=member.entity_id, side_id=member.side.value)
            for placement, member in zip(source.initial.spatial_state.placements, current.round_state.participants)))
        before = deepcopy(current)
        rng = Mock()
        with patch.object(coordinator, "run_npc_round") as run:
            with self.assertRaisesRegex(ValueError, "fresh first round"):
                admitted = replace(source, initial=NpcRoundsRequest(current, spatial, 3))
                coordinator.run_npc_round(admitted.initial.current, ScenarioCandidates(admitted), rng)
            run.assert_not_called()
        rng.randint.assert_not_called()
        self.assertEqual(current, before)
