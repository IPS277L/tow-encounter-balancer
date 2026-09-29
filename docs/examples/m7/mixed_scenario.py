"""Public ADR-0028 runner example; execute with PYTHONPATH=src.

Numeric Footpad Dagger / Brigand Warbow projections: GM1.1, Allies and
Antagonists, pp91,93,97. PG1.4 Equipment p94; Rules pp114,118-119,123.
Fixed positions, explicit distances and authored GM decisions, no catalogue.
"""
from copy import deepcopy
from dataclasses import fields, replace
from random import Random, getstate

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock
from towr.domain.npc_mixed_scenario_models import (
    NpcMixedActorPolicy, NpcMixedPairRange, NpcMixedScenario, NpcMixedScenarioFacts,
)
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome as Outcome, NpcMixedScenarioResult
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult, NpcRosterAttackState
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster,
)
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest, NpcRoundsResult
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.engine.npc_mixed_scenario_runner import run_npc_mixed_scenario


class ScriptedDice:
    """Finite teaching rolls; exhaustion reveals unexpected extra execution."""

    def __init__(self, values: tuple[int, ...]) -> None:
        self.values = values
        self.calls = 0

    def randint(self, low: int, high: int) -> int:
        value = self.values[self.calls]
        assert low <= value <= high
        self.calls += 1
        return value


def build_scenario(*, two_archers: bool = False) -> NpcMixedScenario:
    # Only the bow profile is used for Brigand: no Axe/Craven Opportunist path.
    melee = NpcDefinition(
        "footpad:dagger", "BOOK-GM-GUIDE:1.1:p97:footpad", TargetInjuryPolicy.MINION, 1,
        ResilienceProfile(3),
        (NpcAttackProfile("dagger", "BOOK-GM-GUIDE:1.1:p97:dagger", Skill.MELEE,
                          InlineProfile(3, 3), DamageProfile(2), Range.CLOSE, Range.CLOSE, Hands.ONE_HANDED),),
        (NpcProtectionProfile("BOOK-GM-GUIDE:1.1:p97:footpad:athletics", Skill.ATHLETICS, InlineProfile(3, 3)),),
    )
    bow = NpcDefinition(
        "brigand:warbow", "BOOK-GM-GUIDE:1.1:p97:brigand", TargetInjuryPolicy.MINION, 1,
        ResilienceProfile(3, 1),
        (NpcAttackProfile("warbow", "BOOK-GM-GUIDE:1.1:p97:warbow", Skill.SHOOTING,
                          InlineProfile(3, 3), DamageProfile(3), Range.MEDIUM, Range.LONG, Hands.TWO_HANDED),),
        (NpcProtectionProfile("BOOK-GM-GUIDE:1.1:p97:brigand:athletics", Skill.ATHLETICS, InlineProfile(3, 2)),),
    )
    allies, opposition = CombatSide.PLAYERS_AND_ALLIES, CombatSide.OPPOSITION
    # Both sides contain Minions, including the side called players_and_allies.
    actors = [("Pbow", allies, bow, "rear"), ("P1", allies, melee, "arena")]
    if not two_archers:
        actors.append(("P2", allies, melee, "arena"))
    actors += [("E1", opposition, melee, "arena"),
               ("E2", opposition, bow if two_archers else melee, "far" if two_archers else "arena")]
    roster = NpcRoster(tuple(NpcParticipantSnapshot(profile, NpcParticipantState(
        actor_id, profile.id, side, ProfileInjuryState(0, 1), (profile.attacks[0].id,),
        profile.resilience, True, False,
    )) for actor_id, side, profile, _ in actors))
    current = NpcRoundRequest("example:mixed", NpcRosterAttackState(roster),
                              CombatRoundState(1, roster.turn_participants),
                              tuple(actor_id for actor_id, _, _, _ in actors), ())
    spatial = SpatialBattleState(
        ZoneGraph(("rear", "arena", "far"), (ZoneConnection("rear", "arena"),
                  ZoneConnection("arena", "far"), ZoneConnection("rear", "far"))),
        tuple(SpatialEntityPlacement(actor_id, side.value, zone) for actor_id, side, _, zone in actors),
    )
    # Authored reach facts: sharing a Zone alone does not establish Close.
    pairs = [("Pbow", "E1", Range.MEDIUM), ("Pbow", "E2", Range.MEDIUM),
             ("P1", "E1", Range.CLOSE), ("P1", "E2", Range.MEDIUM if two_archers else Range.CLOSE)]
    if not two_archers:
        pairs += [("P2", "E1", Range.CLOSE), ("P2", "E2", Range.CLOSE)]
    facts = NpcMixedScenarioFacts(
        targets_aware=True, clear_line_of_sight=True, stationary=True,
        all_zone_combatants_included=True, unmounted_combatants_only=True, no_higher_ground=True,
        no_additional_rules=True, no_other_test_modifiers=True,
        ammunition_sufficient=True, requires_reload_action=False,
    )
    policies = tuple(NpcMixedActorPolicy(
        actor_id, tuple(target for target, target_side, _, _ in actors if target_side is not side),
        tuple(MinionDefeatDecision(actor_id, target, NpcDefeatDisposition.KNOCKED_OUT, gm_approved=True)
              for target, target_side, _, _ in actors if target_side is not side),
        outnumbering_bonus_approved=True, can_leave_zone=False,
    ) for actor_id, side, _, _ in actors)
    return NpcMixedScenario(
        NpcRoundsRequest(current, spatial, 2), facts, tuple(NpcMixedPairRange(*pair) for pair in pairs), policies,
        StaggerChoice.SUFFER_WOUND, allies,
        NpcDefeatObjective(tuple(actor_id for actor_id, side, _, _ in actors if side is opposition)),
    )


def attacks(result: NpcMixedScenarioResult) -> tuple[NpcRosterAttackExecutionResult, ...]:
    return tuple(action for step in result.runner_report.source_steps if isinstance(step, NpcRoundsResult)
                 for combat in step.rounds for action in combat.steps if isinstance(action, NpcRosterAttackExecutionResult))


def run_script(name: str, source: NpcMixedScenario, values: tuple[int, ...], expected: Outcome) -> NpcMixedScenarioResult:
    before, global_rng = deepcopy(source), getstate()
    rng = ScriptedDice(values)
    result = run_npc_mixed_scenario(source, rng)
    report = result.runner_report
    assert result.source_scenario == source == before and getstate() == global_rng
    assert result.outcome is expected and rng.calls == len(values)
    assert not result.current.pending_follow_ups
    assert report.spatial_state.placements == source.initial.spatial_state.placements
    assert len(result.current.state.consumed_execution_ids) == report.executed_attack_count == len(attacks(result))
    print(f"{name}: {result.outcome.value}; attacks={report.executed_attack_count}; "
          f"rounds={report.visited_round_count}/{report.newly_completed_round_count} visited/completed; rng={rng.calls}")
    print(f"  defeats={len(result.defeat_acknowledgements)}; terminal_suffix={result.terminal_acknowledgement is not None}; "
          f"last_runner_stop={report.outcome.value}; pending={report.pending_follow_up_count}->0")
    return result


def main() -> None:
    source = build_scenario()
    print("ADR-0028: stationary mixed Minions; explicit Close/Medium pairs; round_budget=2")
    print("sources: PG1.4 Equipment p94; Rules pp114,118-119,123; GM1.1 Allies and Antagonists pp91,93,97")
    print("profiles: Dagger Close 3d/3 Dam2 RES3 Athletics 3d/3; Warbow Medium-Long 3d/3 Dam3 RES4 Athletics 3d/2")
    print("facts: " + "; ".join(f"{field.name}={getattr(source.facts, field.name)}" for field in fields(source.facts)))
    print("policy: first living reachable enemy; all defeats knocked_out/GM-approved; outnumbering approved; "
          "can_leave_zone=False; repeated_stagger=suffer_wound")
    print("formation A: Pbow@rear,P1/P2/E1/E2@arena; formation B: Pbow@rear,P1/E1@arena,E2@far")
    wound = (1, 2, 10, 10, 10, 10)
    miss = (10,) * 6
    victory = run_script("shot_then_melee", source, wound + (1, 2, 10, 10, 10, 10, 10), Outcome.OBJECTIVE_ACHIEVED)
    rolled = tuple(len(a.execution.resolution.attack.attacker_test.trace.initial_values) for a in attacks(victory))
    assert rolled == (3, 4)
    print("  Medium shot Pbow->E1; Close attack P1->E2; pools=3/4 after local 2:2->2:1")

    limited = run_script("all_misses", source, miss * 10, Outcome.ROUND_LIMIT)
    assert limited.runner_report.visited_round_count == limited.runner_report.newly_completed_round_count == 2
    assert all(p.state.injury.wounds == 0 and p.state.injury.conditions.has(Condition.STAGGERED) ==
               (p.state.actor_id != "Pbow") for p in limited.current.state.roster.participants)
    print("  Remote ally gives no local bonus; only Close attackers Staggered; repeated misses do not escalate")

    other = build_scenario(two_archers=True)
    lost = run_script("opposition_wins", other, miss * 2 + wound * 2, Outcome.SIDE_DEFEATED)
    assert lost.terminal_exclusion is None and not lost.current.round_state.excluded_turn_entity_ids
    print("  Defeated allies had completed their turns: no exclusions required")

    blocked = run_script("close_targets_exhausted", other, wound, Outcome.UNSUPPORTED_PATH)
    assert blocked.runner_report.blocked_reason is NpcAttackSelectionBlock.NO_CANDIDATE
    turn = blocked.current.round_state.active_turn
    assert turn.actor_id == "P1" and not turn.action_slots[0].executed
    assert not blocked.current.state.roster.participant("E2").state.injury.defeated
    print("  E2 is alive at Medium; P1 has no Close target; slot unexecuted; no automatic wait/move")

    # Full target policy retains the remote first target; only selection skips it.
    first = other.policy_for("P1")
    reachable = replace(other, actor_policies=tuple(
        replace(p, target_actor_ids=first.target_actor_ids[::-1], defeat_decisions=first.defeat_decisions[::-1])
        if p.actor_id == "P1" else p for p in other.actor_policies),
        initial=replace(other.initial, current=replace(other.initial.current, actor_order=("P1", "Pbow", "E1", "E2"))))
    selected = run_script("reachable_priority", reachable, wound * 2, Outcome.OBJECTIVE_ACHIEVED)
    assert tuple((a.execution.actor_id, a.execution.target_id) for a in attacks(selected)) == (("P1", "E1"), ("Pbow", "E2"))
    print("  P1 skips remote E2, defeats E1; Pbow then defeats E2")

    before, global_rng = deepcopy(other), getstate()
    repeated = run_npc_mixed_scenario(other, Random(42))
    assert repeated == run_npc_mixed_scenario(other, Random(42))
    assert other == before and getstate() == global_rng
    assert repeated.runner_report.executed_attack_count <= 4 * other.initial.max_rounds
    print("seed=42: full results repeat with separate RNGs; bounded execution; no fixed random winner required")
    print("All sources/global RNG unchanged; five scripted cases and seeded replay passed")


if __name__ == "__main__":
    main()
