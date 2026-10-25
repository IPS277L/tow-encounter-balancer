"""Bind Curse completion to the full roster/Champion owner (ADR-0036).

PG1.4 Rules / Giving Ground p119, Broken p122; Battle Magic / Curse p162.
Only recorded target Conditions and live spatial transitions are applied here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.cowardly_flight_casting_completion_models import (
    CowardlyFlightCastingCompletionRequest, CowardlyFlightCastingCompletionResult,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_models import NpcRoster


@dataclass(frozen=True, slots=True)
class NpcRosterCastingCompletionRequest:
    """Capture the complete current owner before completion's Willpower RNG."""

    state: NpcRosterCastingState
    completion: CowardlyFlightCastingCompletionRequest

    def __post_init__(self) -> None:
        if not isinstance(self.state, NpcRosterCastingState):
            raise TypeError("state must be an NpcRosterCastingState")
        if not isinstance(self.completion, CowardlyFlightCastingCompletionRequest):
            raise TypeError("completion must be a CowardlyFlightCastingCompletionRequest")
        if self.state.pending_movement is None:
            raise ValueError("roster completion requires pending movement")
        if self.completion.pending != self.state.pending_movement:
            raise ValueError("completion differs from the current pending movement")


@dataclass(frozen=True, slots=True)
class NpcRosterCastingCompletionResult:
    source: NpcRosterCastingCompletionRequest
    completion: CowardlyFlightCastingCompletionResult

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcRosterCastingCompletionRequest):
            raise TypeError("source must be an NpcRosterCastingCompletionRequest")
        if not isinstance(self.completion, CowardlyFlightCastingCompletionResult):
            raise TypeError("completion must be a CowardlyFlightCastingCompletionResult")
        if self.completion.source != self.source.completion:
            raise ValueError("completion result differs from the complete bound request")

    @property
    def state(self) -> NpcRosterCastingState:
        previous, casting = self.source.state, self.completion.casting
        injuries = {t.actor_id: t.injury for t in casting.targets}
        roster = NpcRoster(tuple(
            replace(p, state=replace(p.state, injury=injuries[p.state.actor_id]))
            if p.state.actor_id in injuries else p for p in previous.roster.participants
        ))
        # Low-level completion proves the unchanged graph/round/free-move/terrain
        # history and ordered Give Ground suffix. Restore archived entries in
        # their original order; they never participate in the live movement.
        live = casting.spatial_state
        placements = {p.entity_id: p for p in live.placements}
        before = self.source.completion.pending.spatial_state
        spatial = replace(
            previous.spatial_state,
            placements=tuple(placements.get(p.entity_id, p) for p in previous.spatial_state.placements),
            gave_ground_entity_ids=(
                *previous.spatial_state.gave_ground_entity_ids,
                *live.gave_ground_entity_ids[len(before.gave_ground_entity_ids):],
            ),
        )
        champion = previous.champion_attack
        if champion is not None:
            champion = replace(champion, roster=roster)
        return replace(previous, roster=roster, spatial_state=spatial,
                       champion_attack=champion, pending_movement=None)
