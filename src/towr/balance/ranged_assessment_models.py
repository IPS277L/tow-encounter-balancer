from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from towr.simulation.npc_ranged_models import NpcRangedSimulationRequest
from towr.simulation.npc_ranged_summary_models import NpcRangedSimulationSummary


@dataclass(frozen=True, slots=True)
class ObjectiveRateWindow:
    minimum: Fraction
    target: Fraction
    maximum: Fraction

    def __post_init__(self) -> None:
        if not all(isinstance(value, Fraction) for value in (self.minimum, self.target, self.maximum)):
            raise TypeError("objective window requires explicit Fraction bounds and target")
        if not Fraction(0) <= self.minimum <= self.target <= self.maximum <= Fraction(1):
            raise ValueError("objective window requires 0 <= minimum <= target <= maximum <= 1")


class RangedAssessmentStatus(str, Enum):
    ELIGIBLE = "eligible"
    UNSUPPORTED_OBSERVATIONS = "unsupported_observations"


@dataclass(frozen=True, slots=True)
class RangedCandidateAssessment:
    """Source-bound point estimates; unsupported observations prevent window assessment.

    Eligibility is not a confidence guarantee or a claim of player-side victory.
    """

    source_request: NpcRangedSimulationRequest
    summary: NpcRangedSimulationSummary
    window: ObjectiveRateWindow

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcRangedSimulationRequest):
            raise TypeError("assessment requires a typed simulation request")
        if not isinstance(self.summary, NpcRangedSimulationSummary):
            raise TypeError("assessment requires an aggregate simulation summary")
        if not isinstance(self.window, ObjectiveRateWindow):
            raise TypeError("assessment requires a typed objective window")
        if self.summary.source_request != self.source_request:
            raise ValueError("assessment summary must belong to the exact simulation request")

    @property
    def objective_achieved_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.objective_achieved, self.summary.trials)

    @property
    def side_defeated_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.side_defeated, self.summary.trials)

    @property
    def round_limit_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.round_limit, self.summary.trials)

    @property
    def unsupported_path_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.unsupported_path, self.summary.trials)

    @property
    def status(self) -> RangedAssessmentStatus:
        return (RangedAssessmentStatus.UNSUPPORTED_OBSERVATIONS if self.summary.outcome_counts.unsupported_path
                else RangedAssessmentStatus.ELIGIBLE)

    @property
    def window_match(self) -> bool | None:
        if self.status is RangedAssessmentStatus.UNSUPPORTED_OBSERVATIONS:
            return None
        return self.window.minimum <= self.objective_achieved_rate <= self.window.maximum
