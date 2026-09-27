from __future__ import annotations

from dataclasses import dataclass

from towr.domain.npc_rounds_chain_summary_models import NpcRoundsChainSummary


@dataclass(frozen=True, slots=True)
class NpcDefeatObjective:
    """Explicit scenario objective: every named participant must be defeated."""

    target_actor_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.target_actor_ids, (tuple, list)):
            raise TypeError("defeat objective requires an ordered sequence of target actor IDs")
        targets = tuple(self.target_actor_ids)
        if not all(isinstance(actor_id, str) for actor_id in targets):
            raise TypeError("defeat objective target actor IDs must be strings")
        if not targets or any(not actor_id.strip() for actor_id in targets):
            raise ValueError("defeat objective requires non-empty target actor IDs")
        if len(set(targets)) != len(targets):
            raise ValueError("defeat objective target actor IDs must be unique")
        object.__setattr__(self, "target_actor_ids", targets)


@dataclass(frozen=True, slots=True)
class NpcDefeatObjectiveAssessment:
    """Read-only assessment of a supplied objective, independent of runner stops."""

    source_report: NpcRoundsChainSummary
    objective: NpcDefeatObjective

    def __post_init__(self) -> None:
        if not isinstance(self.source_report, NpcRoundsChainSummary):
            raise TypeError("defeat objective assessment requires a typed chain report")
        if not isinstance(self.objective, NpcDefeatObjective):
            raise TypeError("defeat objective assessment requires a typed objective")
        participants = {record.actor_id for record in self.source_report.participants}
        if any(actor_id not in participants for actor_id in self.objective.target_actor_ids):
            raise ValueError("defeat objective target must have participated in the reported chain")

    @property
    def remaining_target_actor_ids(self) -> tuple[str, ...]:
        roster = self.source_report.current.state.roster
        return tuple(actor_id for actor_id in self.objective.target_actor_ids
                     if not roster.participant(actor_id).state.injury.defeated)

    @property
    def achieved(self) -> bool:
        return not self.remaining_target_actor_ids
