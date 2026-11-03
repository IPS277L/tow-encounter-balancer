"""Aggregate-only PC encounter data for the balance boundary."""
from dataclasses import dataclass, replace

from towr.simulation.pc_melee_models import PcMeleeOutcomeCounts, PcMeleeSimulationRequest


@dataclass(frozen=True, slots=True)
class PcMeleeSimulationSummary:
    source_request: PcMeleeSimulationRequest
    outcome_counts: PcMeleeOutcomeCounts
    total_action_count: int
    total_started_round_count: int
    total_completed_round_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, PcMeleeSimulationRequest):
            raise TypeError('summary requires its typed simulation request')
        replace(self.source_request)
        if not isinstance(self.outcome_counts, PcMeleeOutcomeCounts):
            raise TypeError('summary requires typed outcome counts')
        replace(self.outcome_counts)
        for name in ('total_action_count', 'total_started_round_count', 'total_completed_round_count'):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f'{name} must be an integer')
            if value < 0:
                raise ValueError(f'{name} must be nonnegative')
        counts = self.outcome_counts
        if sum(getattr(counts, name) for name in counts.__dataclass_fields__) != self.trials:
            raise ValueError('summary must account for every requested trial')
        limited = counts.round_limit
        budget = self.source_request.scenario.max_rounds
        started, completed = self.total_started_round_count, self.total_completed_round_count
        if not limited*budget + self.trials-limited <= started <= self.trials*budget:
            raise ValueError('started rounds contradict outcomes/budget')
        if not limited*budget <= completed <= started or started-completed > self.trials-limited:
            raise ValueError('completed rounds contradict started rounds')
        terminal = counts.objective_achieved+counts.pc_defeated
        if not max(completed, terminal+limited*budget) <= self.total_action_count <= (1+len(self.source_request.scenario.enemies))*started:
            raise ValueError('actions contradict outcomes/rounds/actor count')

    @property
    def trials(self) -> int:
        return self.source_request.trials
