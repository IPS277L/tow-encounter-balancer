"""ADR-0028 admission and public K1/M2 composition, not a mixed scenario runner.

Authored fixtures assert awareness, LOS, stationary positions, no extra rules,
ordinary outnumbering approved and no available escape. Pair ranges are explicit.
PG1.4 Equipment p94; Rules pp114,118-119; GM1.1 NPC profiles pp91,93,97.
"""
from dataclasses import dataclass, replace

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatAcknowledgementRequest, MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_attack_selection_models import NpcAttackCandidate, NpcAttackSelectionBlock, NpcAttackSelectionRequest, NpcAttackSelectionResult
from towr.domain.npc_mixed_scenario_models import NpcMixedActorPolicy, NpcMixedPairRange, NpcMixedScenario, NpcMixedScenarioFacts
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult, NpcRosterAttackState
from towr.domain.npc_roster_models import NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest
from towr.domain.npc_round_models import NpcRoundOutcome, NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import DiceModifier, InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules.minion_defeat_resolution import acknowledge_minion_defeat, apply_minion_defeat_acknowledgement
from towr.rules.npc_round_exclusion import exclude_defeated_npc, apply_npc_round_exclusion


class FixedDice:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = 0

    def randint(self, low, high):
        value = next(self.values)
        assert low <= value <= high
        self.calls += 1
        return value


def initial(*, blocked=False):
    # Footpad Melee numbers, Brigand Shooting numbers (no Brigand Melee/Craven).
    # These are numeric projections, not a complete named NPC catalogue.
    definitions = {}
    for role, skill, dice, damage, bonus, threshold, minimum, maximum, hands in (
        ('melee', Skill.MELEE, 3, 2, 0, 3, Range.CLOSE, Range.CLOSE, Hands.ONE_HANDED),
        ('bow', Skill.SHOOTING, 3, 3, 1, 2, Range.MEDIUM, Range.LONG, Hands.TWO_HANDED),
    ):
        definitions[role] = NpcDefinition(
            'probe:' + role, 'BOOK-GM-GUIDE:1.1:p97:' + role, TargetInjuryPolicy.MINION, 1,
            ResilienceProfile(3, bonus),
            (NpcAttackProfile(role, 'BOOK-GM-GUIDE:1.1:p97:' + role, skill, InlineProfile(dice, 3),
                              DamageProfile(damage), minimum, maximum, hands),),
            (NpcProtectionProfile('BOOK-GM-GUIDE:1.1:p97:athletics', Skill.ATHLETICS,
                                  InlineProfile(3, threshold)),),
        )
    allies, opposition = CombatSide.PLAYERS_AND_ALLIES, CombatSide.OPPOSITION
    actors = [('Pbow', allies, 'bow', 'rear'), ('P1', allies, 'melee', 'arena')]
    if not blocked:
        actors.append(('P2', allies, 'melee', 'arena'))
    actors += [('E1', opposition, 'melee', 'arena'),
               ('E2', opposition, 'bow' if blocked else 'melee', 'far' if blocked else 'arena')]
    roster = NpcRoster(tuple(NpcParticipantSnapshot(definitions[role], NpcParticipantState(
        actor, definitions[role].id, side, ProfileInjuryState(0, 1), (role,),
        definitions[role].resilience, True, False,
    )) for actor, side, role, zone in actors))
    request = NpcRoundRequest('probe:mixed', NpcRosterAttackState(roster),
                              CombatRoundState(1, roster.turn_participants),
                              tuple(a[0] for a in actors), ())
    spatial = SpatialBattleState(
        ZoneGraph(('rear', 'arena', 'far'), (ZoneConnection('rear', 'arena'),
                  ZoneConnection('arena', 'far'), ZoneConnection('rear', 'far'))),
        tuple(SpatialEntityPlacement(actor, side.value, zone) for actor, side, role, zone in actors),
    )
    pairs = (('Pbow', 'E1', Range.MEDIUM), ('Pbow', 'E2', Range.MEDIUM),
             ('P1', 'E1', Range.CLOSE), ('P1', 'E2', Range.MEDIUM if blocked else Range.CLOSE))
    if not blocked:
        pairs += (('P2', 'E1', Range.CLOSE), ('P2', 'E2', Range.CLOSE))
    return request, FixtureCandidates(spatial, pairs)


def admitted_fixture(*, blocked=False):
    request, provider = initial(blocked=blocked)
    actors = request.state.roster.participants
    policies = tuple(NpcMixedActorPolicy(
        actor.state.actor_id,
        tuple(target.state.actor_id for target in actors if target.state.side is not actor.state.side),
        tuple(MinionDefeatDecision(actor.state.actor_id, target.state.actor_id,
                                  NpcDefeatDisposition.KNOCKED_OUT, True)
              for target in actors if target.state.side is not actor.state.side),
        outnumbering_bonus_approved=True, can_leave_zone=False,
    ) for actor in actors)
    scenario = NpcMixedScenario(
        NpcRoundsRequest(request, provider.spatial, 2),
        NpcMixedScenarioFacts(True, True, True, True, True, True, True, True, True, False),
        tuple(NpcMixedPairRange(*pair) for pair in provider.pairs), policies,
        StaggerChoice.SUFFER_WOUND, CombatSide.PLAYERS_AND_ALLIES,
        NpcDefeatObjective(tuple(actor.state.actor_id for actor in actors
                                if actor.state.side is CombatSide.OPPOSITION)),
    )
    return scenario, provider


@dataclass(frozen=True)
class FixtureCandidates:
    spatial: SpatialBattleState
    pairs: tuple[tuple[str, str, Range], ...]

    def distance(self, actor, target):
        return next(distance for first, second, distance in self.pairs
                    if {first, second} == {actor, target})

    def get_candidates(self, context: NpcAttackSelectionRequest):
        roster = context.state.roster
        actor = roster.participant(context.actor_id)
        profile = actor.definition.attacks[0]
        alive = tuple(p for p in roster.participants if not p.state.injury.defeated)
        targets = tuple(p for p in alive if p.state.side is not actor.state.side)
        close_enemy = any(self.distance(context.actor_id, p.state.actor_id) is Range.CLOSE for p in targets)
        zone = self.spatial.placement_for(context.actor_id).zone_id
        counted = tuple(p for p in alive if self.spatial.placement_for(p.state.actor_id).zone_id == zone
                        and not p.state.injury.conditions.has(Condition.DEFENCELESS))
        allies = sum(p.state.side is actor.state.side for p in counted)
        mods = (DiceModifier('RULE-COMBAT-009:outnumbering', 1),) if (
            profile.skill is Skill.MELEE and allies > len(counted) - allies) else ()
        candidates = []
        for target in targets:
            distance = self.distance(context.actor_id, target.state.actor_id)
            if profile.skill is Skill.MELEE and distance is not Range.CLOSE:
                continue
            if profile.skill is Skill.SHOOTING and (close_enemy or distance is not Range.MEDIUM):
                continue
            candidates.append(NpcAttackCandidate(
                context.id + ':' + target.state.actor_id, profile.id, target.state.actor_id, distance,
                close_enemy, False, True, Skill.ATHLETICS, target.protection_options(context.id),
                False, False, mods,
            ))
        return replace(context, candidates=tuple(candidates))


def acknowledge(current, attack):
    result = acknowledge_minion_defeat(MinionDefeatAcknowledgementRequest(
        attack.execution.request_id + ':defeat', current, attack,
        MinionDefeatDecision(attack.execution.actor_id, attack.execution.target_id,
                            NpcDefeatDisposition.KNOCKED_OUT, True),
    ))
    current = apply_minion_defeat_acknowledgement(current, result)
    exclusion = exclude_defeated_npc(NpcRoundExclusionRequest(
        attack.execution.request_id + ':exclude', current, attack.execution.target_id))
    return apply_npc_round_exclusion(current, exclusion)


def attacks(report):
    return tuple(s for s in report.steps if isinstance(s, NpcRosterAttackExecutionResult))


def main():
    admitted, provider = admitted_fixture()
    source = admitted.initial.current
    rng = FixedDice((1, 2, 3, 10, 10, 10, 1, 2, 3, 10, 10, 10, 10))
    shot = run_npc_round(source, provider, rng)
    first, = attacks(shot)
    current = acknowledge(shot.continuation, first)
    melee = run_npc_round(current, provider, rng)
    second, = attacks(melee)
    final = acknowledge(melee.continuation, second)
    rolls = tuple(len(a.execution.resolution.attack.attacker_test.trace.initial_values) for a in (first, second))
    assert rolls == (3, 4) and rng.calls == 13
    assert first.execution.actor_id == 'Pbow' and second.execution.actor_id == 'P1'
    assert len(final.state.consumed_execution_ids) == 2 and not final.pending_follow_ups
    assert all(final.state.roster.participant(a).state.injury.defeated for a in ('E1', 'E2'))
    assert all(not p.state.injury.wounds and not p.state.injury.defeated for p in source.state.roster.participants)
    print('Medium shot -> Close attack: pools 3/4; 13 RNG calls; 2 receipts/defeats; sources unchanged')

    rng = FixedDice((10, 10, 10, 1, 1, 1) * 5)
    missed = run_npc_round(source, provider, rng)
    assert missed.outcome is NpcRoundOutcome.COMPLETE and rng.calls == 30
    assert len(attacks(missed)) == 5
    for participant in missed.state.roster.participants:
        assert participant.state.injury.conditions.has(Condition.STAGGERED) == (participant.state.actor_id != 'Pbow')
    assert all(not p.state.injury.conditions.conditions for p in source.state.roster.participants)
    print('Five misses: only four Close attackers Staggered; remote ally does not give local outnumbering')

    admitted, provider = admitted_fixture(blocked=True)
    source = admitted.initial.current
    rng = FixedDice((1, 2, 3, 10, 10, 10))
    shot = run_npc_round(source, provider, rng)
    first, = attacks(shot)
    current = acknowledge(shot.continuation, first)
    stopped = run_npc_round(current, provider, rng)
    assert stopped.outcome is NpcRoundOutcome.SELECTION_BLOCKED and not attacks(stopped)
    selection, = (s for s in stopped.steps if isinstance(s, NpcAttackSelectionResult))
    assert selection.blocked_reason is NpcAttackSelectionBlock.NO_CANDIDATE
    assert rng.calls == 6 and not stopped.round_state.active_turn.action_slots[0].executed
    print('After the only Close enemy falls: NO_CANDIDATE; slot unexecuted; no wait/move/extra RNG')
    print('Both fixtures passed mixed admission; this composition probe does not exercise the full mixed runner')


if __name__ == '__main__':
    main()
