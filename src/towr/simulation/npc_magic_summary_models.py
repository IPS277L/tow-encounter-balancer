"""Aggregate-only magic observations for future consumers (ADR-0038)."""
from dataclasses import dataclass

from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts, NpcMagicSimulationRequest


@dataclass(frozen=True, slots=True)
class NpcMagicSimulationSummary:
    """Validate necessary arithmetic bounds, without claiming journal provenance."""

    source_request: NpcMagicSimulationRequest
    outcome_counts: NpcMagicOutcomeCounts
    total_action_count: int
    total_started_round_count: int
    total_completed_round_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcMagicSimulationRequest):
            raise TypeError("magic summary requires its typed source request")
        if not isinstance(self.outcome_counts, NpcMagicOutcomeCounts):
            raise TypeError("magic summary requires typed magic outcome counts")
        for name in ("total_action_count", "total_started_round_count", "total_completed_round_count"):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        counts = self.outcome_counts
        terminal = counts.objective_achieved + counts.perspective_defeated
        limited = counts.round_limit_reached
        if terminal + limited + counts.unsupported_path != self.trials:
            raise ValueError("magic summary must account for every requested trial")
        budget = self.source_request.scenario.max_rounds
        actors = len(self.source_request.scenario.activation_order)
        started, completed = self.total_started_round_count, self.total_completed_round_count
        if not limited * budget + self.trials - limited <= started <= self.trials * budget:
            raise ValueError("magic started rounds contradict outcomes or source budget")
        if not limited * budget <= completed <= started or started - completed > self.trials - limited:
            raise ValueError("magic completed rounds contradict outcomes or started rounds")
        if not max(completed, terminal + limited * budget) <= self.total_action_count <= actors * started:
            raise ValueError("magic actions contradict outcomes, completed rounds or available slots")

    @property
    def trials(self) -> int:
        return self.source_request.trials
