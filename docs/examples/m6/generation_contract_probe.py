"""Finite ADR-0026 constructor probe; no production generator or simulations."""

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction

from melee_scenario import build_scenario
from towr.balance.melee_evaluation_models import MeleeBalanceCandidate
from towr.balance.melee_staged_evaluation_models import MeleeBalanceStage, MeleeStagedEvaluationRequest
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_melee_scenario_models import NpcMeleeActorPolicy, NpcMeleeScenarioFacts
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcParticipantSnapshot, NpcParticipantState, NpcRoster
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneGraph


def main() -> None:
    base = build_scenario()
    definition = base.initial.current.state.roster.participants[0].definition
    enemy_side = base.initial.current.state.roster.participants[-1].state.side
    # Explicitly author the full reserve, including E3. Candidate construction
    # below only selects existing actors; it never creates extra combatants.
    extra = NpcParticipantSnapshot(definition, NpcParticipantState(
        "E3", definition.id, enemy_side, ProfileInjuryState(0, 1), ("dagger",),
        definition.resilience, True, False,
    ))
    roster = NpcRoster((*base.initial.current.state.roster.participants, extra))
    actor_ids = ("P1", "P2", "E1", "E2", "E3")
    combat = replace(base.initial.current.round_state, participants=roster.turn_participants)
    current = replace(base.initial.current, id="probe:reserve", state=NpcRosterAttackState(roster),
                      round_state=combat, actor_order=actor_ids)
    spatial = replace(base.initial.spatial_state, placements=(
        *base.initial.spatial_state.placements, SpatialEntityPlacement("E3", enemy_side.value, "arena"),
    ))
    policies = []
    for actor in actor_ids:
        targets = ("E3", "E2", "E1") if actor in ("P1", "P2") else ("P1", "P2")
        # Authored GM choices for this entire family, including False for P2.
        policies.append(NpcMeleeActorPolicy(actor, targets, tuple(
            MinionDefeatDecision(actor, target, NpcDefeatDisposition.KNOCKED_OUT, gm_approved=True)
            for target in targets
        ), outnumbering_bonus_approved=actor != "P2"))
    reserve = replace(base, initial=replace(base.initial, current=current, spatial_state=spatial),
                      actor_policies=tuple(policies), objective=NpcDefeatObjective(("E3", "E2", "E1")))
    before = deepcopy(reserve)
    # Separately authored applicability to EVERY candidate, not inferred from
    # the full reserve. Omitted actors are absent from each candidate's battle.
    facts = NpcMeleeScenarioFacts(
        zone_id="arena", all_opponents_in_close_range=True, targets_aware=True, clear_line_of_sight=True,
        stationary=True, all_zone_combatants_included=True, unmounted_combatants_only=True,
        no_higher_ground=True, no_additional_rules=True, no_other_test_modifiers=True, can_leave_zone=True,
    )
    groups = (("E2", "E1"), ("E3",))
    vectors = ((0, 1), (1, 0), (1, 1), (2, 0), (2, 1))
    expected_enemies = (("E3",), ("E2",), ("E2", "E3"), ("E1", "E2"), ("E1", "E2", "E3"))
    candidates = []
    for counts, enemies in zip(vectors, expected_enemies, strict=True):
        kept = {"P1", "P2", *groups[0][:counts[0]], *groups[1][:counts[1]]}
        candidate_id = f"family:counts:{counts[0]},{counts[1]}"
        chosen = NpcRoster(tuple(actor for actor in roster.participants if actor.state.actor_id in kept))
        projected = replace(current, id=candidate_id + ":initial", state=NpcRosterAttackState(chosen),
                            round_state=replace(combat, participants=tuple(
                                actor for actor in combat.participants if actor.entity_id in kept)),
                            actor_order=tuple(actor for actor in current.actor_order if actor in kept))
        placement = replace(spatial, placements=tuple(item for item in spatial.placements if item.entity_id in kept))
        filtered_policies = tuple(replace(
            policy, target_actor_ids=tuple(target for target in policy.target_actor_ids if target in kept),
            defeat_decisions=tuple(decision for decision in policy.defeat_decisions if decision.target_id in kept),
        ) for policy in reserve.actor_policies if policy.actor_id in kept)
        scenario = replace(reserve, initial=replace(reserve.initial, current=projected, spatial_state=placement),
                           facts=facts, actor_policies=filtered_policies, objective=NpcDefeatObjective(tuple(
                               target for target in reserve.objective.target_actor_ids if target in kept)))
        candidate = MeleeBalanceCandidate(candidate_id, scenario)
        candidates.append(candidate)
        assert projected.actor_order == ("P1", "P2", *enemies)
        assert tuple(actor.state.actor_id for actor in chosen.participants) == projected.actor_order
        assert all(actor is roster.participants[actor_ids.index(actor.state.actor_id)] for actor in chosen.participants)
        assert projected.state == NpcRosterAttackState(chosen) and not projected.pending_follow_ups
        assert placement.graph is spatial.graph and scenario.facts is facts
        assert scenario.initial.max_rounds == reserve.initial.max_rounds
        assert scenario.repeated_stagger_choice is reserve.repeated_stagger_choice
        for policy in scenario.actor_policies:
            original = next(item for item in reserve.actor_policies if item.actor_id == policy.actor_id)
            assert policy.outnumbering_bonus_approved is original.outnumbering_bonus_approved
            assert policy.defeat_decisions == tuple(item for item in original.defeat_decisions if item.target_id in kept)
        assert scenario.actor_policies[0].target_actor_ids == tuple(target for target in ("E3", "E2", "E1") if target in kept)
        print(f"{candidate_id}: actor_order={projected.actor_order}; P1 targets={scenario.actor_policies[0].target_actor_ids}")

    stages = (MeleeBalanceStage(10, 2), MeleeBalanceStage(100, 1))
    request = MeleeStagedEvaluationRequest(tuple(candidates), 42, stages, 250,
                                         ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)))
    assert len(candidates) == (2 + 1) * (1 + 1) - 1 == 5
    assert request.planned_trials == 5 * 10 + 2 * 100 == 250
    # Arithmetic examples only; production request caps have separate unit tests.
    assert len(candidates) > 4 and len(candidates) <= 5
    assert (2 * 2) * 10 + 2 * 100 == 240
    assert (1 * 1) - 1 == 0
    # Existing public constructors must reject inconsistent facts/spatial state/budget.
    invalid = (
        lambda: replace(request, max_total_trials=249),
        lambda: replace(facts, all_zone_combatants_included=False),
        lambda: replace(reserve, facts=replace(facts, zone_id="exit")),
        lambda: replace(reserve, initial=replace(reserve.initial, spatial_state=SpatialBattleState(
            ZoneGraph(("arena",), ()), spatial.placements))),
    )
    for construct in invalid:
        try:
            construct()
        except ValueError:
            pass
        else:
            raise AssertionError("inconsistent public input was accepted")
    assert reserve == before
    print("5 admitted candidates; full staged budget=250; 4 constructor rejections; source unchanged")
    print("contract probe only: no production generation API, runner, RNG or observed probabilities")


if __name__ == "__main__":
    main()
