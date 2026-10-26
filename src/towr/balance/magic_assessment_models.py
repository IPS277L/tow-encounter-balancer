"""Pure source-bound assessment of magic aggregates (ADR-0040)."""
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary


class MagicAssessmentStatus(str, Enum):
    ELIGIBLE = "eligible"
    UNSUPPORTED_OBSERVATIONS = "unsupported_observations"


@dataclass(frozen=True, slots=True)
class MagicCandidateAssessment:
    """Point estimates over all trials, with unsupported observations kept separate.

    Eligibility does not establish tactical completeness or true probabilities.
    """

    source_request: NpcMagicSimulationRequest
    summary: NpcMagicSimulationSummary
    window: ObjectiveRateWindow

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcMagicSimulationRequest):
            raise TypeError("magic assessment requires a typed simulation request")
        if not isinstance(self.summary, NpcMagicSimulationSummary):
            raise TypeError("magic assessment requires an aggregate simulation summary")
        if not isinstance(self.window, ObjectiveRateWindow):
            raise TypeError("magic assessment requires a typed objective window")
        if self.summary.source_request != self.source_request:
            raise ValueError("magic assessment summary must belong to the exact simulation request")

    @property
    def objective_achieved_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.objective_achieved, self.summary.trials)

    @property
    def perspective_defeated_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.perspective_defeated, self.summary.trials)

    @property
    def round_limit_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.round_limit_reached, self.summary.trials)

    @property
    def unsupported_path_rate(self) -> Fraction:
        return Fraction(self.summary.outcome_counts.unsupported_path, self.summary.trials)

    @property
    def status(self) -> MagicAssessmentStatus:
        return (MagicAssessmentStatus.UNSUPPORTED_OBSERVATIONS if self.summary.outcome_counts.unsupported_path
                else MagicAssessmentStatus.ELIGIBLE)

    @property
    def window_match(self) -> bool | None:
        if self.status is MagicAssessmentStatus.UNSUPPORTED_OBSERVATIONS:
            return None
        return self.window.minimum <= self.objective_achieved_rate <= self.window.maximum
