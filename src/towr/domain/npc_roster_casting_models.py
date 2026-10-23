"""Actor-bound application of an ADR-0035 result; no battle loop (ADR-0036)."""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_models import (
    CastingCasterDefinition, CowardlyFlightCastingRequest,
)
from towr.domain.cowardly_flight_casting_result_models import CowardlyFlightCastingResult
from towr.domain.injury_models import WoundConditionEffect
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_champion_attack_models import NpcChampionAttackState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.turn_models import CombatRoundState
from towr.domain.test_models import InlineProfile


@dataclass(frozen=True, slots=True)
class NpcRosterCastingTargetContext:
    """Caller supplies Willpower and movement facts; injury comes from roster."""

    actor_id: str
    willpower_profile: InlineProfile
    can_give_ground: bool

    def __post_init__(self) -> None:
        _identifier(self.actor_id)
        _typed(self.willpower_profile, InlineProfile)
        if not isinstance(self.can_give_ground, bool):
            raise TypeError('can_give_ground must be an explicit boolean')


@dataclass(frozen=True, slots=True)
class NpcCastingWizardState:
    actor_id: str
    caster: CastingCasterDefinition
    magic_state: WizardMagicState

    def __post_init__(self) -> None:
        _identifier(self.actor_id)
        _typed(self.caster, CastingCasterDefinition)
        _typed(self.magic_state, WizardMagicState)


@dataclass(frozen=True, slots=True)
class NpcRosterCastingState:
    """Current Champion/Minion snapshots; storage does not authorize Casting.

    Pending retains the entire Casting result, including traces and the
    pre-preparation Miscast state. Only the current state prevents replay;
    deliberately restoring an old snapshot is outside this pure API.
    """

    roster: NpcRoster
    wizard: NpcCastingWizardState
    round_state: CombatRoundState
    spatial_state: SpatialBattleState
    consumed_execution_ids: tuple[str, ...] = ()
    pending_miscast: CowardlyFlightCastingResult | None = None
    champion_attack: NpcChampionAttackState | None = None

    def __post_init__(self) -> None:
        for value, kind in (
            (self.roster, NpcRoster), (self.wizard, NpcCastingWizardState),
            (self.round_state, CombatRoundState), (self.spatial_state, SpatialBattleState),
        ):
            _typed(value, kind)
        if not isinstance(self.consumed_execution_ids, (tuple, list)):
            raise TypeError("consumed execution IDs must be an ordered tuple or list")
        consumed = tuple(self.consumed_execution_ids)
        for identifier in consumed:
            _identifier(identifier)
        if len(set(consumed)) != len(consumed):
            raise ValueError("consumed execution IDs must be unique")
        object.__setattr__(self, "consumed_execution_ids", consumed)
        actor = self.roster.participant(self.wizard.actor_id)
        if actor.definition.injury_policy is not TargetInjuryPolicy.CHAMPION:
            raise ValueError("caster must be a Champion")
        for participant in self.roster.participants:
            if participant is actor:
                continue
            if participant.definition.injury_policy is not TargetInjuryPolicy.MINION:
                raise ValueError("other Casting roster actors must be Minions")
        if self.roster.turn_participants != self.round_state.participants:
            raise ValueError("roster must match ordered round participants")
        spatial = self.spatial_state
        if spatial.round_number != self.round_state.round_number:
            raise ValueError("spatial state belongs to another round")
        placements = {p.entity_id: p for p in spatial.placements}
        if set(placements) != {p.entity_id for p in self.round_state.participants}:
            raise ValueError("spatial placements must match roster participants")
        if any(placements[p.entity_id].side_id != p.side.value
               for p in self.round_state.participants):
            raise ValueError("spatial sides must match roster participants")
        if self.champion_attack is not None:
            _typed(self.champion_attack, NpcChampionAttackState)
            if (self.champion_attack.roster != self.roster
                    or self.champion_attack.round_state != self.round_state
                    or self.champion_attack.daily_wounds.target_id != self.wizard.actor_id):
                raise ValueError("Champion attack owner must match the current caster/roster/round")
            if not set(self.champion_attack.consumed_execution_ids) <= set(consumed):
                raise ValueError("Casting history must retain all bound Champion attack executions")
        pending = self.pending_miscast
        if pending is None:
            if self.wizard.magic_state.miscast_dice > self.wizard.caster.wizard_level:
                raise ValueError("mandatory Miscast requires its pending Casting result")
        else:
            _typed(pending, CowardlyFlightCastingResult)
            if pending.pending_miscast is None:
                raise ValueError("pending Casting result must require Miscast")
            if (pending.source.actor_id != self.wizard.actor_id
                    or pending.source.caster != self.wizard.caster
                    or pending.magic_state != self.wizard.magic_state
                    or pending.round_state != self.casting_round_state
                    or pending.spatial_state != self.casting_spatial_state
                    or pending.source.id not in consumed):
                raise ValueError("pending Miscast must match the applied Casting state")
            for target in pending.targets:
                if self.roster.participant(target.actor_id).state.injury != target.injury:
                    raise ValueError("pending Miscast target snapshot differs from roster")

    @property
    def casting_round_state(self) -> CombatRoundState:
        """Live projection only; keep the full roster/round for the caller."""
        live = {p.state.actor_id for p in self.roster.participants
                if not (p.state.injury.dead if p.state.actor_id == self.wizard.actor_id
                        else p.state.injury.defeated)}
        return replace(self.round_state,
                       participants=tuple(p for p in self.round_state.participants if p.entity_id in live),
                       completed_turn_entity_ids=tuple(i for i in self.round_state.completed_turn_entity_ids if i in live),
                       excluded_turn_entity_ids=tuple(i for i in self.round_state.excluded_turn_entity_ids if i in live))

    @property
    def casting_spatial_state(self) -> SpatialBattleState:
        live = {p.entity_id for p in self.casting_round_state.participants}
        return replace(self.spatial_state, placements=tuple(
            p for p in self.spatial_state.placements if p.entity_id in live))


@dataclass(frozen=True, slots=True)
class NpcRosterCastingRequest:
    """Bind the complete pre-action snapshot before executing Casting."""

    state: NpcRosterCastingState
    casting: CowardlyFlightCastingRequest

    def __post_init__(self) -> None:
        _typed(self.state, NpcRosterCastingState)
        _typed(self.casting, CowardlyFlightCastingRequest)
        state, casting = self.state, self.casting
        if any(t.can_give_ground for t in casting.targets):
            raise ValueError("Casting roster does not yet support pending Give Ground")
        if state.pending_miscast is not None:
            raise ValueError("pending Miscast blocks normal Casting")
        if state.champion_attack is not None and state.champion_attack.pending is not None:
            raise ValueError("pending Champion attack blocks normal Casting")
        actor = state.roster.participant(state.wizard.actor_id)
        injury = actor.state.injury
        safe_conditions = {Condition.STAGGERED, Condition.DRAINED}
        if injury.dead or not injury.conditions.conditions <= safe_conditions:
            raise ValueError("caster cannot use this normal Casting boundary in its current condition")
        if any(not w.effect_resolved for w in injury.wounds) or any(
            not isinstance(e, WoundConditionEffect) or e.condition not in safe_conditions
            or not injury.conditions.has(e.condition) for e in injury.active_wound_effects
        ):
            raise ValueError("caster has unresolved or unsupported Wound effects")
        if actor.state.holds_shield or actor.state.current_resilience.is_armoured:
            raise ValueError("normal Casting excludes current armour/shield")
        if casting.id in state.consumed_execution_ids:
            raise ValueError("Casting execution has already been consumed")
        if (casting.actor_id != state.wizard.actor_id
                or casting.caster != state.wizard.caster
                or casting.magic_state != state.wizard.magic_state
                or casting.round_state != state.casting_round_state
                or casting.spatial_state != state.casting_spatial_state):
            raise ValueError("Casting source does not match the actor-bound state")
        for target in casting.targets:
            if state.roster.participant(target.actor_id).state.injury != target.injury:
                raise ValueError("Casting target injury does not match the roster")


@dataclass(frozen=True, slots=True)
class NpcRosterCastingResult:
    source: NpcRosterCastingRequest
    casting: CowardlyFlightCastingResult

    def __post_init__(self) -> None:
        _typed(self.source, NpcRosterCastingRequest)
        _typed(self.casting, CowardlyFlightCastingResult)
        if self.casting.source != self.source.casting:
            raise ValueError("Casting result must match the complete bound request")

    @property
    def state(self) -> NpcRosterCastingState:
        """Derived atomic projection: no separately supplied post-state to forge."""
        previous, casting = self.source.state, self.casting
        injuries = {t.actor_id: t.injury for t in casting.targets}
        participants = tuple(
            replace(p, state=replace(p.state, injury=injuries[p.state.actor_id]))
            if p.state.actor_id in injuries else p
            for p in previous.roster.participants
        )
        roster = NpcRoster(participants)
        # Only the action receipt changes: archive defeated round participants.
        combat = replace(previous.round_state, active_turn=casting.round_state.active_turn)
        champion = previous.champion_attack
        if champion is not None:
            champion = replace(champion, roster=roster, round_state=combat)
        return replace(
            previous, roster=roster,
            wizard=replace(previous.wizard, magic_state=casting.magic_state),
            round_state=combat, champion_attack=champion,
            consumed_execution_ids=(*previous.consumed_execution_ids, casting.source.id),
            pending_miscast=casting if casting.pending_miscast is not None else None,
        )


def _typed(value: object, kind: type) -> None:
    if not isinstance(value, kind):
        raise TypeError(f"Casting roster requires {kind.__name__}")


def _identifier(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("Casting roster identifier must be a string")
    if not value.strip():
        raise ValueError("Casting roster identifier must not be blank")
