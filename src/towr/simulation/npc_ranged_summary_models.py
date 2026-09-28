from dataclasses import dataclass

from towr.simulation.npc_ranged_models import NpcRangedOutcomeCounts, NpcRangedSimulationRequest


@dataclass(frozen=True, slots=True)
class NpcRangedSimulationSummary:
    """Aggregate-only observation bound to the simulator input, without trial records.

    Validation checks aggregate consistency, not the provenance of observations.
    """

    source_request: NpcRangedSimulationRequest
    outcome_counts: NpcRangedOutcomeCounts
    total_attack_count: int
    total_visited_round_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcRangedSimulationRequest):
            raise TypeError("simulation summary requires its typed source request")
        if not isinstance(self.outcome_counts, NpcRangedOutcomeCounts):
            raise TypeError("simulation summary requires typed outcome counts")
        for value in (self.total_attack_count, self.total_visited_round_count):
            if type(value) is not int or value < 0:
                raise ValueError("simulation summary totals must be non-negative integers")
        counts = self.outcome_counts
        if (counts.objective_achieved + counts.side_defeated
                + counts.round_limit + counts.unsupported_path != self.trials):
            raise ValueError("simulation summary must account for every requested trial")
        budget = self.source_request.scenario.initial.max_rounds
        minimum_rounds = counts.round_limit * budget + self.trials - counts.round_limit
        if not minimum_rounds <= self.total_visited_round_count <= self.trials * budget:
            raise ValueError("simulation summary rounds contradict outcomes or source budget")
        actors = len(self.source_request.scenario.initial.current.actor_order)
        terminal_count = counts.objective_achieved + counts.side_defeated
        if not terminal_count <= self.total_attack_count <= actors * self.total_visited_round_count:
            raise ValueError("simulation summary attacks contradict outcomes or available slots")

    @property
    def trials(self) -> int:
        return self.source_request.trials

    @property
    def mean_attack_count(self) -> float:
        return self.total_attack_count / self.trials

    @property
    def mean_visited_round_count(self) -> float:
        return self.total_visited_round_count / self.trials
