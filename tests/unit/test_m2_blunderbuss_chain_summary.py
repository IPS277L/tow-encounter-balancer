from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_k1_secondary_target_resolution import TargetDecisions
from tests.unit.test_k1_spatial_resolution import graph
from tests.unit.test_m2_npc_blunderbuss_round import request, Candidates
from tests.unit.test_m2_npc_nearby_stagger import request as secondary_request
from tests.unit.test_m2_npc_nearby_consequences import append, defeat_request, give_ground_request
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_blunderbuss_models import NpcBlunderbussAttackExecutionResult
from towr.domain.npc_blunderbuss_defeat_models import NpcBlunderbussDefeatAcknowledgementRequest, NpcBlunderbussDefeatAcknowledgementResult
from towr.domain.npc_blunderbuss_give_ground_models import NpcBlunderbussGiveGroundExecutionRequest, NpcBlunderbussGiveGroundConsumptionResult
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionRequest, NpcNearbyStaggerExecutionResult
from towr.domain.npc_nearby_consequence_models import NpcNearbyConsequenceChain
from towr.domain.npc_nearby_completion_models import NpcNearbyCompletionRequest, NpcNearbyCompletionResult
from towr.domain.npc_nearby_defeat_models import NpcNearbyDefeatAcknowledgementResult
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest, NpcRoundsResult, NpcRoundsOutcome
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest, NearbyTargetsStaggerRequest
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection
from towr.engine.npc_rounds_runner import run_npc_rounds
from towr.engine.npc_rounds_reporting import summarize_npc_rounds_chain
from towr.rules.npc_nearby_stagger_resolution import execute_npc_nearby_stagger
from towr.rules.npc_nearby_defeat_resolution import acknowledge_npc_nearby_defeat
from towr.rules.npc_nearby_give_ground_resolution import execute_npc_nearby_give_ground
from towr.rules.npc_nearby_completion_resolution import complete_npc_nearby_consequences, apply_npc_nearby_completion
from towr.rules.npc_blunderbuss_defeat_resolution import acknowledge_npc_blunderbuss_defeat, apply_npc_blunderbuss_defeat
from towr.rules.npc_blunderbuss_give_ground_resolution import execute_npc_blunderbuss_give_ground, apply_npc_blunderbuss_give_ground
from towr.rules.npc_round_exclusion import exclude_defeated_npc, apply_npc_round_exclusion


def observe(current, spatial):
    provider = Mock()
    provider.get_candidates.side_effect = lambda context, spatial: context
    return run_npc_rounds(NpcRoundsRequest(current, spatial, 1), provider, Mock(), Mock())


def journal(*, primary="wound", empty=False, enemy=False, movement_first=True, mixed=False, outside=False,
            disposition=NpcDefeatDisposition.KNOCKED_OUT, primary_disposition=NpcDefeatDisposition.KNOCKED_OUT, rng=None):
    secondary = secondary_request(states=((1, (Condition.STAGGERED,)),
        (2, (Condition.STAGGERED,) if primary == "move" else ()), (3, (Condition.STAGGERED, Condition.PRONE))),
        targets=() if empty else ("brigand:1", "brigand:3"))
    if outside:
        template = secondary.state.roster.participant("brigand:3")
        extra = replace(template, state=replace(template.state, actor_id="brigand:4"))
        state = replace(secondary.state, roster=replace(secondary.state.roster, participants=(*secondary.state.roster.participants, extra)))
        template_target = secondary.resolution.targets[-1]
        target = replace(template_target, target_id="brigand:4", impact=replace(template_target.impact,
            id="impact:brigand:4", target_id="brigand:4"))
        secondary = replace(secondary, state=state, resolution=replace(secondary.resolution, targets=(*secondary.resolution.targets, target)))
    initial = request(roster=secondary.state.roster)
    initial = replace(initial, state=replace(secondary.state, roster=initial.state.roster),
        round_state=replace(initial.round_state, participants=tuple(p for p in initial.round_state.participants if p.entity_id != "brigand:4")),
        actor_order=("brigand:1", "brigand:0", "brigand:2", "brigand:3") if mixed else tuple(f"brigand:{i}" for i in range(4)))
    zone_graph = graph()
    spatial = SpatialBattleState(replace(zone_graph, zone_ids=(*zone_graph.zone_ids, "zone:d"),
        connections=(*zone_graph.connections, ZoneConnection("zone:b", "zone:d"))),
        tuple(SpatialEntityPlacement(p.state.actor_id, p.state.side.value,
            "zone:a" if p.state.actor_id == "brigand:0" else "zone:b") for p in initial.state.roster.participants),
        free_move_used_entity_ids=("brigand:0",))
    if enemy:
        spatial = replace(spatial, placements=(*spatial.placements,
            SpatialEntityPlacement("extra:enemy", spatial.placement_for("brigand:0").side_id, "zone:d")))
    dice = [1, 2, 10, 10, 10, 10, 10, 10] if primary == "wound" else [1, 10, 10, 10, 10, 1, 10, 10]
    rng = rng if rng is not None else SequenceRandom(([10] * 6 if mixed else []) + dice)
    provider = Candidates(ordinary=mixed)
    adapter = Mock()
    adapter.get_candidates.side_effect = lambda current, spatial: provider.get_candidates(current)
    first = run_npc_rounds(NpcRoundsRequest(initial, spatial, 1), adapter, Mock(), rng,
        decisions=FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND))
    attack, = (step for result in first.rounds for step in result.steps if isinstance(step, NpcBlunderbussAttackExecutionResult))
    current = first.current
    steps = [first]
    trigger, = (f for f in current.pending_follow_ups if isinstance(f, NearbyTargetsStaggerRequest))
    batch = execute_npc_nearby_stagger(NpcNearbyStaggerExecutionRequest(current.state,
        replace(secondary.resolution, source=trigger), attack.primary_attack), rng,
        decisions=TargetDecisions(stagger_choices={"impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND}))
    steps.append(batch)
    chain = NpcNearbyConsequenceChain(batch, spatial)
    if not empty:
        for kind in (("move", "defeat") if movement_first else ("defeat", "move")):
            step = (execute_npc_nearby_give_ground(give_ground_request(chain)) if kind == "move"
                    else acknowledge_npc_nearby_defeat(defeat_request(chain, disposition=disposition)))
            chain = append(chain, step)
            steps.append(step)
        if outside:
            step = acknowledge_npc_nearby_defeat(defeat_request(chain, target="brigand:4", disposition=disposition))
            chain = append(chain, step)
            steps.append(step)
    completion = complete_npc_nearby_consequences(NpcNearbyCompletionRequest("complete",
        replace(current, state=chain.state), chain.spatial_state, chain))
    steps.append(completion)
    current, spatial = apply_npc_nearby_completion(completion.source_request.current, completion.spatial_state, completion)
    if primary == "wound":
        consequence = acknowledge_npc_blunderbuss_defeat(NpcBlunderbussDefeatAcknowledgementRequest("primary:ack",
            current, spatial, attack, completion, MinionDefeatDecision("brigand:0", "brigand:2", primary_disposition, True)))
        current, spatial = apply_npc_blunderbuss_defeat(current, spatial, consequence)
        steps.append(consequence)
    elif primary == "move":
        follow_up, = (f for f in current.pending_follow_ups if isinstance(f, GiveGroundRequest))
        movement = GiveGroundResolutionRequest(follow_up, spatial, "brigand:2", "zone:d",
            current.state.roster.participant("brigand:2").state.injury.conditions, "brigand:0")
        consequence = execute_npc_blunderbuss_give_ground(NpcBlunderbussGiveGroundExecutionRequest("primary:move",
            current, spatial, attack, completion, movement))
        current, spatial = apply_npc_blunderbuss_give_ground(current, spatial, consequence)
        steps.append(consequence)
    for actor in ("brigand:2", "brigand:3"):
        if current.state.roster.participant(actor).state.injury.defeated:
            excluded = exclude_defeated_npc(NpcRoundExclusionRequest("exclude:" + actor, current, actor))
            current = apply_npc_round_exclusion(current, excluded)
            steps.append(excluded)
    steps.append(observe(current, spatial))
    return tuple(steps)


class M2BlunderbussChainSummaryTests(unittest.TestCase):
    def test_both_primary_branches_preserve_full_decisions_sources_and_final_snapshots(self):
        for primary, enemy, order, disposition in product(("wound", "move"), (False, True), (False, True), NpcDefeatDisposition):
            with self.subTest(primary=primary, enemy=enemy, order=order, disposition=disposition):
                steps = journal(primary=primary, enemy=enemy, movement_first=order, disposition=disposition,
                    primary_disposition=NpcDefeatDisposition.DISARMED_AND_SURRENDERED)
                before = deepcopy(steps)
                report = summarize_npc_rounds_chain(steps)
                self.assertEqual((report.executed_attack_count, report.visited_round_count, report.newly_completed_round_count), (1, 1, 0))
                self.assertEqual(tuple(s.executed_attack_count for s in report.call_summaries), (1, 0))
                self.assertEqual(report.current, steps[-1].current)
                self.assertIs(report.spatial_state, steps[-1].spatial_state)
                self.assertEqual(report.pending_follow_up_count, 0)
                self.assertEqual(report.participants, report.final_summary.participants)
                self.assertFalse(report.current.weapons[0].weapon_state.loaded)
                decisions = report.defeat_acknowledgements
                self.assertEqual(decisions[0].source_request.decision.disposition, disposition)
                self.assertEqual(len(decisions), 2 if primary == "wound" else 1)
                if primary == "wound":
                    self.assertEqual(decisions[1].source_request.decision.disposition, NpcDefeatDisposition.DISARMED_AND_SURRENDERED)
                for source, retained in zip(steps, report.source_steps):
                    self.assertIs(source, retained)
                self.assertEqual(steps, before)

    def test_empty_batches_still_require_explicit_batch_and_completion_without_fake_steps(self):
        for primary in ("wound", "move", "stagger"):
            steps = journal(primary=primary, empty=True)
            report = summarize_npc_rounds_chain(steps)
            completion = next(s for s in steps if isinstance(s, NpcNearbyCompletionResult))
            self.assertEqual(completion.source_request.chain.steps, ())
            self.assertEqual(report.executed_attack_count, 1)
            self.assertEqual(len(report.defeat_acknowledgements), int(primary == "wound"))
            for missing in (1, 2):
                with self.assertRaises(ValueError):
                    summarize_npc_rounds_chain(steps[:missing] + steps[missing + 1:])

    def test_each_missing_replayed_or_reordered_external_transition_is_rejected(self):
        steps = journal()
        for index in range(1, len(steps) - 1):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    summarize_npc_rounds_chain(steps[:index] + steps[index + 1:])
                with self.assertRaises(ValueError):
                    summarize_npc_rounds_chain(steps[:index] + (steps[index],) + steps[index:])
                with self.assertRaises(ValueError):
                    summarize_npc_rounds_chain(steps[:index] + (steps[index + 1], steps[index]) + steps[index + 2:])

    def test_equal_snapshots_do_not_allow_substituting_secondary_decisions_or_nested_completion(self):
        for order in (False, True):
            original = journal(movement_first=order)
            changed = journal(movement_first=order, disposition=NpcDefeatDisposition.KILLED)
            self.assertEqual(original[-1].current, changed[-1].current)
            for index, step in enumerate(original):
                if isinstance(step, (NpcNearbyDefeatAcknowledgementResult, NpcNearbyCompletionResult,
                                     NpcBlunderbussDefeatAcknowledgementResult)):
                    with self.subTest(order=order, index=index), self.assertRaises(ValueError):
                        summarize_npc_rounds_chain(original[:index] + (changed[index],) + original[index + 1:])

    def test_stale_weapons_spatial_roster_and_missing_primary_journal_are_rejected(self):
        steps = journal(primary="move")
        first, last = steps[0], steps[-1]
        stale_weapon = replace(last.current, weapons=first.source_request.current.weapons)
        participants = tuple(replace(p, state=replace(p.state, injury=replace(p.state.injury,
            conditions=p.state.injury.conditions.with_condition(Condition.BROKEN))))
            if p.state.actor_id == "brigand:2" else p for p in last.current.state.roster.participants)
        stale_roster = replace(last.current, state=replace(last.current.state,
            roster=replace(last.current.state.roster, participants=participants)))
        for current, spatial in ((stale_weapon, last.spatial_state), (stale_roster, last.spatial_state),
                                 (last.current, first.spatial_state), (replace(last.current, id="foreign"), last.spatial_state)):
            with self.subTest(current=current.id), self.assertRaises(ValueError):
                summarize_npc_rounds_chain((*steps[:-1], observe(current, spatial)))
        no_primary = observe(first.current, first.spatial_state)
        with self.assertRaisesRegex(ValueError, "primary Attack"):
            summarize_npc_rounds_chain((no_primary, *steps[1:]))

    def test_partial_observations_preserve_pending_and_can_resume_with_the_full_prefix(self):
        steps = journal()
        first, batch = steps[:2]
        current = replace(first.current, state=batch.state)
        partial = observe(current, first.spatial_state)
        report = summarize_npc_rounds_chain((first, batch, partial, partial))
        self.assertIs(report.outcome, NpcRoundsOutcome.PENDING_FOLLOW_UPS)
        self.assertEqual(report.executed_attack_count, 1)
        self.assertEqual(report.defeat_acknowledgements, ())
        resumed = summarize_npc_rounds_chain((first, batch, partial, *steps[2:]))
        self.assertEqual(resumed.current, steps[-1].current)
        self.assertEqual(resumed.executed_attack_count, 1)

    def test_secondary_targets_outside_round_are_included_in_first_seen_order(self):
        steps = journal(outside=True)
        report = summarize_npc_rounds_chain(steps)
        self.assertEqual(tuple(p.actor_id for p in report.participants), tuple(f"brigand:{i}" for i in range(5)))
        self.assertEqual(len(report.final_summary.participants), 4)
        self.assertTrue(report.participants[-1].defeated)
        self.assertEqual(report.participants[-1].wounds, 1)
        self.assertEqual(len(report.defeat_acknowledgements), 3)

    def test_report_is_immutable_and_does_not_execute_rules_or_count_nested_sources(self):
        from contextlib import ExitStack

        steps = journal(primary="move", mixed=True)
        operations = (
            "towr.rules.npc_nearby_stagger_resolution.execute_npc_nearby_stagger",
            "towr.rules.npc_nearby_consequence_resolution.apply_npc_nearby_consequence",
            "towr.rules.npc_nearby_completion_resolution.apply_npc_nearby_completion",
            "towr.rules.npc_blunderbuss_give_ground_resolution.apply_npc_blunderbuss_give_ground",
            "towr.rules.npc_blunderbuss_defeat_resolution.apply_npc_blunderbuss_defeat",
            "towr.rules.spatial_resolution.resolve_give_ground",
            "towr.rules.attack_action_execution.resolve_kernel_attack",
            "towr.engine.npc_rounds_runner.run_npc_rounds",
        )
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch(name, side_effect=AssertionError("report executed rules"))) for name in operations]
            report = summarize_npc_rounds_chain(list(steps))
            self.assertEqual(report.executed_attack_count, 2)
            self.assertEqual(summarize_npc_rounds_chain(steps), report)
            for mock in mocks:
                mock.assert_not_called()
        with self.assertRaises(FrozenInstanceError):
            report.source_steps = ()
        with self.assertRaises(TypeError):
            summarize_npc_rounds_chain((steps[0], next(s for s in steps if isinstance(s, NpcNearbyCompletionResult)).source_request.chain, steps[-1]))
