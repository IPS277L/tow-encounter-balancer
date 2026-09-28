from copy import deepcopy
from dataclasses import dataclass, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_m6_npc_melee_scenario import scenario, with_actor
from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatAcknowledgementRequest, NpcDefeatDisposition
from towr.domain.npc_attack_selection_models import NpcAttackCandidate
from towr.domain.npc_melee_scenario_models import NpcMeleeScenario
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.test_models import DiceModifier
from towr.engine import npc_round_coordinator as coordinator
from towr.engine.npc_rounds_runner import run_npc_rounds
from towr.rules import attack_action_execution as attack_executor
from towr.rules.minion_defeat_resolution import acknowledge_minion_defeat, apply_minion_defeat_acknowledgement
from towr.rules.npc_round_exclusion import exclude_defeated_npc, apply_npc_round_exclusion


@dataclass(frozen=True, slots=True)
class TestOnlyCandidates:
    """Explicit handoff of the admitted scenario, not a production M6 runner.

    PG 1.4 Rules pp118-119: ordinary outnumbering uses the current Zone roster.
    GM 1.1 Allies and Antagonists p97: Footpad, no applicable Lurker in battle.
    """

    source: NpcMeleeScenario

    def get_candidates(self, context, spatial=None):
        spatial = spatial or self.source.initial.spatial_state
        roster = context.state.roster
        actor = roster.participant(context.actor_id)
        policy = self.source.policy_for(context.actor_id)
        zone = spatial.placement_for(context.actor_id).zone_id
        counted = tuple(p for p in roster.participants if not p.state.injury.defeated
                        and not p.state.injury.conditions.has(Condition.DEFENCELESS)
                        and spatial.placement_for(p.state.actor_id).zone_id == zone)
        allies = sum(p.state.side is actor.state.side for p in counted)
        enemies = len(counted) - allies
        modifiers = ((DiceModifier("RULE-COMBAT-009:outnumbering", 1),)
                     if allies > enemies and policy.outnumbering_bonus_approved else ())
        candidates = []
        for target_id in policy.target_actor_ids:
            target = roster.participant(target_id)
            if target.state.injury.defeated:
                continue
            candidates.append(NpcAttackCandidate(
                context.id + ":" + target_id, actor.definition.attacks[0].id, target_id, Range.CLOSE,
                True, False, self.source.facts.targets_aware, target.definition.protection[0].skill,
                target.protection_options(context.id), self.source.facts.can_leave_zone, False, modifiers,
            ))
        return replace(context, candidates=tuple(candidates))

    def get_next_round(self, current, spatial_state):
        participants = tuple(p.turn_participant for p in current.state.roster.participants if not p.state.injury.defeated)
        ids = {p.entity_id for p in participants}
        order = tuple(actor for actor in self.source.initial.current.actor_order if actor in ids)
        return NpcRoundAdvanceRequest(current.id + ":advance", current, spatial_state, participants, order)


def attacks(result):
    return tuple(step for step in result.steps if isinstance(step, NpcRosterAttackExecutionResult))


def acknowledge(source, current, attack):
    decision = next(d for d in source.policy_for(attack.execution.actor_id).defeat_decisions
                    if d.target_id == attack.execution.target_id)
    result = acknowledge_minion_defeat(MinionDefeatAcknowledgementRequest(
        attack.execution.request_id + ":defeat", current, attack, decision))
    current = apply_minion_defeat_acknowledgement(current, result)
    if attack.execution.target_id not in current.round_state.completed_turn_entity_ids:
        exclusion = exclude_defeated_npc(NpcRoundExclusionRequest(
            attack.execution.request_id + ":exclude", current, attack.execution.target_id))
        current = apply_npc_round_exclusion(current, exclusion)
    return current, result


class M6NpcMeleeScenarioPreflightTests(unittest.TestCase):
    def test_close_misses_in_two_rounds_stagger_each_actor_without_escalating(self):
        source = scenario(sizes=(1, 1))
        source = replace(source, initial=replace(source.initial, max_rounds=2))
        before = deepcopy(source)
        rng = Mock(wraps=SequenceRandom([10, 10, 10, 1, 10, 10] * 4))
        decisions = Mock(wraps=FixedKernelDecisions(stagger=source.repeated_stagger_choice))
        provider = TestOnlyCandidates(source)
        with patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel:
            replace(source)
            rng.randint.assert_not_called()
            kernel.assert_not_called()
            result = run_npc_rounds(source.initial, provider, provider, rng, decisions=decisions)
        self.assertEqual(kernel.call_count, 4)
        self.assertEqual(rng.randint.call_count, 24)
        decisions.choose_repeated_stagger.assert_not_called()
        self.assertEqual(len(result.current.state.consumed_execution_ids), 4)
        self.assertEqual(result.current.round_state.round_number, 2)
        for round_result in result.rounds:
            self.assertIs(round_result.outcome, NpcRoundOutcome.COMPLETE)
            self.assertTrue(all(a.execution.resolution.attack.outcome is AttackOutcome.MISS for a in attacks(round_result)))
        for actor in result.current.state.roster.participants:
            self.assertTrue(actor.state.injury.conditions.has(Condition.STAGGERED))
            self.assertFalse(actor.state.injury.defeated)
            self.assertEqual(actor.state.injury.wounds, 0)
        self.assertEqual(source, before)
        with self.assertRaisesRegex(ValueError, "fresh first round"):
            replace(source, initial=replace(source.initial, current=result.current, spatial_state=result.spatial_state))

    def test_successful_weak_hit_after_close_miss_uses_explicit_wound_choice(self):
        # PG 1.4 p119: miss adds Staggered; the enemy's subsequent Dam 2 hit
        # escalates against that Staggered actor even though Damage <= RES 3.
        for can_leave in (True, False):
            source = scenario(sizes=(1, 1))
            source = replace(source, facts=replace(source.facts, can_leave_zone=can_leave))
            rng = Mock(wraps=SequenceRandom([10, 10, 10, 1, 10, 10, 1, 10, 10, 1, 10, 10]))
            decisions = Mock(wraps=FixedKernelDecisions(stagger=source.repeated_stagger_choice))
            result = coordinator.run_npc_round(source.initial.current, TestOnlyCandidates(source), rng, decisions=decisions)
            first, second = attacks(result)
            self.assertIs(first.execution.resolution.attack.outcome, AttackOutcome.MISS)
            self.assertTrue(first.state.roster.participant("actor:0:0").state.injury.conditions.has(Condition.STAGGERED))
            self.assertEqual(second.execution.resolution.attack.damage, 2)
            self.assertTrue(second.state.roster.participant("actor:0:0").state.injury.defeated)
            self.assertEqual(decisions.choose_repeated_stagger.call_count, 1)
            self.assertEqual(second.source_request.execution.kernel_request.can_target_leave_zone, can_leave)
            self.assertIs(result.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
            self.assertEqual(rng.randint.call_count, 12)
            current, ack = acknowledge(source, result.continuation, second)
            self.assertFalse(current.pending_follow_ups)
            # The defeated player already completed their turn; no exclusion is needed.
            self.assertEqual(current.round_state.completed_turn_entity_ids, ("actor:0:0",))
            self.assertFalse(current.round_state.excluded_turn_entity_ids)
            with self.assertRaises(ValueError):
                apply_minion_defeat_acknowledgement(current, ack)

    def test_first_and_repeated_stagger_count_completed_allies_for_bonus(self):
        source = scenario(sizes=(2, 1))
        rng = Mock(wraps=SequenceRandom([1, 10, 10, 10, 1, 10, 10] * 2))
        decisions = Mock(wraps=FixedKernelDecisions(stagger=source.repeated_stagger_choice))
        result = coordinator.run_npc_round(source.initial.current, TestOnlyCandidates(source), rng, decisions=decisions)
        first, second = attacks(result)
        self.assertFalse(first.state.roster.participant("actor:1:0").state.injury.defeated)
        self.assertTrue(first.state.roster.participant("actor:1:0").state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(second.state.roster.participant("actor:1:0").state.injury.defeated)
        self.assertEqual(second.source_request.execution.state.completed_turn_entity_ids, ("actor:0:0",))
        for attack in (first, second):
            trace = attack.execution.resolution.attack
            self.assertEqual(len(trace.attacker_test.trace.initial_values), 4)
            self.assertEqual(len(trace.defender_test.trace.initial_values), 3)
        self.assertEqual(rng.randint.call_count, 14)
        self.assertEqual(decisions.choose_repeated_stagger.call_count, 1)

    def test_bonus_recalculated_after_defeat_and_withholding_is_preserved(self):
        for approved in (True, False):
            for disposition in NpcDefeatDisposition:
                with self.subTest(approved=approved, disposition=disposition):
                    source = scenario(approved=approved, disposition=disposition)
                    policy = source.actor_policies[0]
                    policy = replace(policy, target_actor_ids=policy.target_actor_ids[::-1],
                                     defeat_decisions=policy.defeat_decisions[::-1])
                    source = replace(source, actor_policies=(policy, *source.actor_policies[1:]))
                    before = deepcopy(source)
                    dice = [1, 2, 10, 10, 10, 10] + [1, 2, 10] + ([10] if approved else []) + [10] * 3
                    rng = Mock(wraps=SequenceRandom(dice))
                    provider = TestOnlyCandidates(source)
                    with patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel:
                        first = coordinator.run_npc_round(source.initial.current, provider, rng)
                        attack1, = attacks(first)
                        blocked = coordinator.run_npc_round(first.continuation, provider, rng)
                        self.assertEqual(rng.randint.call_count, 6)
                        self.assertFalse(attacks(blocked))
                        current, ack1 = acknowledge(source, first.continuation, attack1)
                        second = coordinator.run_npc_round(current, provider, rng)
                        attack2, = attacks(second)
                        final, ack2 = acknowledge(source, second.continuation, attack2)
                    self.assertEqual(kernel.call_count, 2)
                    self.assertEqual(rng.randint.call_count, 13 if approved else 12)
                    self.assertEqual(attack1.execution.target_id, "actor:1:1")
                    self.assertEqual(attack2.execution.target_id, "actor:1:0")
                    mods1 = attack1.source_request.execution.kernel_request.attack.attacker_test.dice_modifiers
                    mods2 = attack2.source_request.execution.kernel_request.attack.attacker_test.dice_modifiers
                    self.assertEqual(mods1, ())
                    self.assertEqual(mods2, (DiceModifier("RULE-COMBAT-009:outnumbering", 1),) if approved else ())
                    self.assertFalse(attack2.source_request.execution.kernel_request.attack.defender_test.dice_modifiers)
                    self.assertEqual(len(final.state.consumed_execution_ids), 2)
                    self.assertFalse(final.pending_follow_ups)
                    self.assertEqual(ack1.source_request.decision.disposition, disposition)
                    self.assertEqual(ack2.source_request.decision.disposition, disposition)
                    self.assertEqual(source, before)

    def test_invalid_admission_stops_before_runner_and_rng(self):
        source = scenario()
        invalid = with_actor(source, state_changes={"injury": ProfileInjuryState(0, 1, ConditionState({Condition.ABLAZE}))})
        rng = Mock()
        with patch.object(coordinator, "run_npc_round") as run:
            with self.assertRaisesRegex(ValueError, "without Conditions"):
                admitted = replace(source, initial=invalid)
                coordinator.run_npc_round(admitted.initial.current, TestOnlyCandidates(admitted), rng)
            run.assert_not_called()
        rng.randint.assert_not_called()

    def test_weapon_bound_round_is_rejected_before_execution(self):
        from tests.unit.test_m2_npc_blunderbuss_round import request as weapon_round
        source = scenario()
        current = weapon_round()
        spatial = replace(source.initial.spatial_state, placements=tuple(
            replace(placement, entity_id=member.entity_id, side_id=member.side.value)
            for placement, member in zip(source.initial.spatial_state.placements, current.round_state.participants)))
        initial = replace(source.initial, current=current, spatial_state=spatial)
        before = deepcopy(initial)
        rng = Mock()
        with patch.object(coordinator, "run_npc_round") as run:
            with self.assertRaisesRegex(ValueError, "fresh first round"):
                admitted = replace(source, initial=initial)
                coordinator.run_npc_round(admitted.initial.current, TestOnlyCandidates(admitted), rng)
            run.assert_not_called()
        rng.randint.assert_not_called()
        self.assertEqual(initial, before)
