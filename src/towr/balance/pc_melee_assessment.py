"""Source-bound point estimates over all PC encounter trials (ADR-0065)."""
from dataclasses import dataclass, replace
from enum import Enum
from fractions import Fraction

from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_summary_models import PcMeleeSimulationSummary


class PcMeleeAssessmentStatus(str, Enum):
    ELIGIBLE = 'eligible'
    UNSUPPORTED_OBSERVATIONS = 'unsupported_observations'


@dataclass(frozen=True, slots=True)
class PcMeleeCandidateAssessment:
    """Observed rates, not confidence bounds or a claim of optimal PC play."""

    source_request: PcMeleeSimulationRequest
    summary: PcMeleeSimulationSummary
    window: ObjectiveRateWindow

    def __post_init__(self) -> None:
        if type(self.source_request) is not PcMeleeSimulationRequest:
            raise TypeError('assessment requires its typed PC simulation request')
        if type(self.summary) is not PcMeleeSimulationSummary:
            raise TypeError('assessment requires a PC aggregate summary')
        if type(self.window) is not ObjectiveRateWindow:
            raise TypeError('assessment requires an explicit objective window')
        replace(self.source_request)
        replace(self.summary)
        replace(self.window)
        if self.summary.source_request != self.source_request:
            raise ValueError('summary belongs to another complete simulation request')

    @property
    def objective_achieved_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.objective_achieved, self.summary.trials)

    @property
    def party_defeated_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.party_defeated, self.summary.trials)

    @property
    def round_limit_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.round_limit, self.summary.trials)

    @property
    def unsupported_path_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.unsupported_path, self.summary.trials)

    @property
    def status(self) -> PcMeleeAssessmentStatus:
        return (PcMeleeAssessmentStatus.UNSUPPORTED_OBSERVATIONS
                if self.summary.outcome_counts.unsupported_path else PcMeleeAssessmentStatus.ELIGIBLE)

    @property
    def window_match(self) -> bool | None:
        if self.status is PcMeleeAssessmentStatus.UNSUPPORTED_OBSERVATIONS:
            return None
        return self.window.minimum <= self.objective_achieved_rate <= self.window.maximum
