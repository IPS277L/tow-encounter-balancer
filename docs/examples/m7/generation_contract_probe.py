"""Finite ADR-0033 constructor probe; no production generator or simulation."""

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from random import getstate

from mixed_scenario import build_scenario
from towr.balance.mixed_evaluation_models import MixedBalanceCandidate
from towr.balance.mixed_staged_evaluation_models import MixedBalanceStage, MixedStagedEvaluationRequest
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_mixed_scenario_models import (
    NpcMixedActorPolicy, NpcMixedPairRange, NpcMixedScenario, NpcMixedScenarioFacts,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.turn_models import CombatSide


def _project(
    reserve: NpcMixedScenario, kept: set[str], candidate_id: str,
    facts: NpcMixedScenarioFacts, pairs: tuple[NpcMixedPairRange, ...],
) -> MixedBalanceCandidate:
    """Project only the explicitly listed examples below through public constructors."""
    current = reserve.initial.current
    roster = NpcRoster(tuple(p for p in current.state.roster.participants if p.state.actor_id in kept))
    projected = replace(
        current, id=candidate_id + ":initial", state=NpcRosterAttackState(roster),
        round_state=replace(current.round_state, participants=tuple(
            p for p in current.round_state.participants if p.entity_id in kept)),
        actor_order=tuple(actor for actor in current.actor_order if actor in kept),
    )
    spatial = replace(reserve.initial.spatial_state, placements=tuple(
        p for p in reserve.initial.spatial_state.placements if p.entity_id in kept))
    policies = tuple(replace(
        p, target_actor_ids=tuple(target for target in p.target_actor_ids if target in kept),
        defeat_decisions=tuple(d for d in p.defeat_decisions if d.target_id in kept),
    ) for p in reserve.actor_policies if p.actor_id in kept)
    scenario = replace(
        reserve, initial=replace(reserve.initial, current=projected, spatial_state=spatial),
        facts=facts, pair_ranges=tuple(p for p in pairs if {p.first_actor_id, p.second_actor_id} <= kept),
        actor_policies=policies, objective=NpcDefeatObjective(tuple(
            target for target in reserve.objective.target_actor_ids if target in kept)),
    )
    return MixedBalanceCandidate(candidate_id, scenario)


def main() -> None:
    global_rng = getstate()
    base = build_scenario()
    current = base.initial.current
    bow = current.state.roster.participant("Pbow")
    opposition = CombatSide.OPPOSITION
    # Explicit extra reserve actor: Brigand's Warbow only, no Axe/Craven branch.
    extra = replace(bow, state=replace(bow.state, actor_id="E3", side=opposition))
    roster = NpcRoster((*current.state.roster.participants, extra))
    actor_ids = ("Pbow", "P1", "P2", "E1", "E2", "E3")
    current = replace(current, id="probe:reserve", state=NpcRosterAttackState(roster),
                      round_state=replace(current.round_state, participants=roster.turn_participants),
                      actor_order=actor_ids)
    spatial = replace(base.initial.spatial_state, placements=(
        *base.initial.spatial_state.placements, SpatialEntityPlacement("E3", opposition.value, "far"),
    ))
    policies = []
    for actor in actor_ids:
        targets = ("E3", "E2", "E1") if actor.startswith("P") else ("Pbow", "P1", "P2")
        policies.append(NpcMixedActorPolicy(actor, targets, tuple(
            MinionDefeatDecision(actor, target, NpcDefeatDisposition.KNOCKED_OUT, gm_approved=True)
            for target in targets
        ), outnumbering_bonus_approved=actor != "P2", can_leave_zone=actor == "P2"))
    reserve = replace(
        base, initial=replace(base.initial, current=current, spatial_state=spatial),
        pair_ranges=(*base.pair_ranges, *(NpcMixedPairRange(actor, "E3", Range.MEDIUM)
                                        for actor in ("Pbow", "P1", "P2"))),
        actor_policies=tuple(policies), objective=NpcDefeatObjective(("E3", "E2", "E1")),
    )
    before = deepcopy(reserve)
    # Separately supplied applicability to EVERY subset; no inference from template.
    facts = NpcMixedScenarioFacts(
        targets_aware=True, clear_line_of_sight=True, stationary=True,
        all_zone_combatants_included=True, unmounted_combatants_only=True, no_higher_ground=True,
        no_additional_rules=True, no_other_test_modifiers=True,
        ammunition_sufficient=True, requires_reload_action=False,
    )
    pairs = tuple(replace(p) for p in reserve.pair_ranges)
    assert pairs == reserve.pair_ranges
    groups = (("E2", "E1"), ("E3",))
    vectors = ((1, 0), (1, 1), (2, 0), (2, 1))
    expected_enemies = (("E2",), ("E2", "E3"), ("E1", "E2"), ("E1", "E2", "E3"))
    candidates = []
    for counts, enemies in zip(vectors, expected_enemies, strict=True):
        kept = {"Pbow", "P1", "P2", *groups[0][:counts[0]], *groups[1][:counts[1]]}
        candidate_id = f"family:counts:{counts[0]},{counts[1]}"
        candidate = _project(reserve, kept, candidate_id, facts, pairs)
        candidates.append(candidate)
        scenario = candidate.scenario
        projected = scenario.initial.current
        assert projected.actor_order == ("Pbow", "P1", "P2", *enemies)
        assert projected.id == candidate_id + ":initial"
        assert tuple(p.state.actor_id for p in projected.state.roster.participants) == projected.actor_order
        assert all(p is roster.participant(p.state.actor_id) for p in projected.state.roster.participants)
        assert projected.round_state.participants == tuple(
            p for p in current.round_state.participants if p.entity_id in kept)
        assert projected.state == NpcRosterAttackState(projected.state.roster) and not projected.pending_follow_ups
        assert scenario.initial.spatial_state.graph is spatial.graph and scenario.facts is facts
        assert scenario.initial.spatial_state.placements == tuple(p for p in spatial.placements if p.entity_id in kept)
        assert scenario.initial.max_rounds == reserve.initial.max_rounds
        assert scenario.repeated_stagger_choice is reserve.repeated_stagger_choice
        assert scenario.perspective_side is reserve.perspective_side
        selected_pairs = tuple(p for p in pairs if {p.first_actor_id, p.second_actor_id} <= kept)
        assert all(a is b for a, b in zip(scenario.pair_ranges, selected_pairs, strict=True))
        for policy in scenario.actor_policies:
            original = reserve.policy_for(policy.actor_id)
            assert policy.outnumbering_bonus_approved is original.outnumbering_bonus_approved
            assert policy.can_leave_zone is original.can_leave_zone
            assert policy.defeat_decisions == tuple(d for d in original.defeat_decisions if d.target_id in kept)
        targets = tuple(target for target in ("E3", "E2", "E1") if target in kept)
        assert scenario.policy_for("P1").target_actor_ids == scenario.objective.target_actor_ids == targets
        print(f"{candidate_id}: actor_order={projected.actor_order}; P1 targets={targets}; pairs={len(selected_pairs)}")

    stages = (MixedBalanceStage(10, 2), MixedBalanceStage(100, 1))
    request = MixedStagedEvaluationRequest(tuple(candidates), 42, stages, 240,
                                         ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)))
    assert len(candidates) == 2 * 2 == 4 and request.planned_trials == 4 * 10 + 2 * 100 == 240
    # Arithmetic only, not future generation preflight: cap=3 rejects C=4.
    assert len(candidates) > 3
    # With A.minimum=0, C=5 includes inadmissible (0,1). Do NOT silently retain four.
    assert (3 * 2 - 1) * 10 + 2 * 100 == 250
    opposite = replace(base, perspective_side=opposition, objective=NpcDefeatObjective(("Pbow", "P1", "P2")))
    invalid = (
        ("budget", lambda: replace(request, max_total_trials=239), "exceeds max_total_trials"),
        ("family facts", lambda: replace(facts, all_zone_combatants_included=False), ""),
        ("missing pair", lambda: replace(reserve, pair_ranges=pairs[:-1]), "every enemy pair"),
        ("no Close target", lambda: _project(reserve, {"Pbow", "P1", "P2", "E3"},
                                            "invalid:counts:0,1", facts, pairs), "initially available target"),
        ("no Shooting role", lambda: _project(opposite, {"P1", "P2", "E1", "E2"},
                                             "invalid:role", facts, opposite.pair_ranges), "both"),
    )
    for label, construct, message in invalid:
        try:
            construct()
        except ValueError as exc:
            assert message in str(exc), (label, str(exc))
        else:
            raise AssertionError(f"{label}: inconsistent public input was accepted")
        print(f"constructor rejection: {label}")
    assert reserve == before and getstate() == global_rng
    print("4 admitted candidates; full staged budget=240; widened family C=5/budget=250 includes invalid (0,1)")
    print("5 constructor rejections; source/global RNG unchanged")
    print("contract probe only: no production generation API, runner, random draws or observed probabilities")


if __name__ == "__main__":
    main()
