"""ADR-0021 feasibility probe using existing public K1/M2 constructors.

This is NOT the future Melee scenario admission or autonomous runner.
The fixture explicitly supplies Close, awareness, equal ground, no extra rules,
inability to leave the Zone, and GM approval of ordinary outnumbering bonuses.
Sources: PG 1.4 Rules pp114,118-119; GM 1.1 Allies and Antagonists pp91,93,97.
"""
from dataclasses import dataclass, replace

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatAcknowledgementRequest, MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_attack_selection_models import NpcAttackCandidate, NpcAttackSelectionRequest
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult, NpcRosterAttackState
from towr.domain.npc_roster_models import NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneGraph
from towr.domain.test_models import DiceModifier, InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules.minion_defeat_resolution import acknowledge_minion_defeat, apply_minion_defeat_acknowledgement
from towr.rules.npc_round_exclusion import exclude_defeated_npc, apply_npc_round_exclusion


class FixedDice:
    def __init__(self, values: tuple[int, ...]):
        self.values = iter(values)
        self.calls = 0

    def randint(self, low: int, high: int) -> int:
        value = next(self.values)
        assert low <= value <= high
        self.calls += 1
        return value


def initial() -> NpcRoundsRequest:
    # Footpad's Lurker applies outside battle. Dagger does not inherit PC traits.
    profile = NpcDefinition(
        "footpad", "RULE-PROFILE-TALABEC-005", TargetInjuryPolicy.MINION, 1, ResilienceProfile(3),
        (NpcAttackProfile("dagger", "RULE-PROFILE-TALABEC-005:dagger", Skill.MELEE,
                         InlineProfile(3, 3), DamageProfile(2), Range.CLOSE, Range.CLOSE, Hands.ONE_HANDED),),
        (NpcProtectionProfile("RULE-PROFILE-TALABEC-005:protection", Skill.ATHLETICS, InlineProfile(3, 3)),),
    )
    roster = NpcRoster(tuple(NpcParticipantSnapshot(profile, NpcParticipantState(
        actor, profile.id, side, ProfileInjuryState(0, 1), ("dagger",), profile.resilience, True, False,
    )) for actor, side in (("p1", CombatSide.PLAYERS_AND_ALLIES), ("p2", CombatSide.PLAYERS_AND_ALLIES),
                          ("e1", CombatSide.OPPOSITION), ("e2", CombatSide.OPPOSITION))))
    current = NpcRoundRequest("probe:melee", NpcRosterAttackState(roster),
                              CombatRoundState(1, roster.turn_participants), ("p1", "p2", "e1", "e2"), ())
    spatial = SpatialBattleState(ZoneGraph(("arena",)), tuple(
        SpatialEntityPlacement(p.state.actor_id, p.state.side.value, "arena") for p in roster.participants))
    # Movement is never executed; the graph itself does not establish Close.
    return NpcRoundsRequest(current, spatial, 2)


@dataclass(frozen=True)
class FixtureCandidates:
    """Only this explicit all-Close Footpad fixture; no general admission."""

    def get_candidates(self, context: NpcAttackSelectionRequest) -> NpcAttackSelectionRequest:
        roster = context.state.roster
        actor = roster.participant(context.actor_id)
        counted = tuple(p for p in roster.participants if not p.state.injury.defeated
                        and not p.state.injury.conditions.has(Condition.DEFENCELESS))
        allies = sum(p.state.side is actor.state.side for p in counted)
        enemies = len(counted) - allies
        mods = (DiceModifier("RULE-COMBAT-009:outnumbering", 1),) if allies > enemies else ()
        targets = tuple(p for p in counted if p.state.side is not actor.state.side)
        return replace(context, candidates=tuple(NpcAttackCandidate(
            context.id + ":" + p.state.actor_id, "dagger", p.state.actor_id, Range.CLOSE,
            True, False, True, Skill.ATHLETICS, p.protection_options(context.id), False, False, mods,
        ) for p in targets))


def acknowledge(current: NpcRoundRequest, attack: NpcRosterAttackExecutionResult) -> NpcRoundRequest:
    result = acknowledge_minion_defeat(MinionDefeatAcknowledgementRequest(
        attack.execution.request_id + ":defeat", current, attack,
        MinionDefeatDecision(attack.execution.actor_id, attack.execution.target_id,
                            NpcDefeatDisposition.KNOCKED_OUT, True),
    ))
    current = apply_minion_defeat_acknowledgement(current, result)
    exclusion = exclude_defeated_npc(NpcRoundExclusionRequest(
        attack.execution.request_id + ":exclude", current, attack.execution.target_id))
    return apply_npc_round_exclusion(current, exclusion)


def main() -> None:
    source = initial()
    rng = FixedDice((1, 2, 3, 10, 10, 10, 1, 2, 3, 10, 10, 10, 10))
    first = run_npc_round(source.current, FixtureCandidates(), rng)
    attack1, = (step for step in first.steps if isinstance(step, NpcRosterAttackExecutionResult))
    current = acknowledge(first.continuation, attack1)
    second = run_npc_round(current, FixtureCandidates(), rng)
    attack2, = (step for step in second.steps if isinstance(step, NpcRosterAttackExecutionResult))
    final = acknowledge(second.continuation, attack2)
    rolls = tuple(len(a.execution.resolution.attack.attacker_test.trace.initial_values) for a in (attack1, attack2))
    assert rolls == (3, 4), rolls
    assert rng.calls == 13
    assert len(final.state.consumed_execution_ids) == 2
    assert not final.pending_follow_ups
    assert all(final.state.roster.participant(actor).state.injury.defeated for actor in ("e1", "e2"))
    assert all(not p.state.injury.defeated for p in source.current.state.roster.participants)
    # Existing source/replay and budget constructors reject these inputs.
    for rejected in (
        lambda: acknowledge(first.continuation, attack2),
        lambda: acknowledge(final, attack2),
        lambda: replace(source, max_rounds=0),
        lambda: replace(source, max_rounds=True),
    ):
        try:
            rejected()
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError("invalid constructor input accepted")
    print("Footpad 2x2: attack dice 3 -> 4 after defeat; 2 attacks, 13 RNG calls; 4 rejections OK")


if __name__ == "__main__":
    main()
