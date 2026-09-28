from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.simulation.npc_melee_models import NpcMeleeSimulationRequest
from towr.simulation.npc_melee_summary_models import NpcMeleeSimulationSummary


class MeleeAssessmentStatus(str, Enum):
    ELIGIBLE = "eligible"
    UNSUPPORTED_OBSERVATIONS = "unsupported_observations"


@dataclass(frozen=True, slots=True)
class MeleeCandidateAssessment:
    """Source-bound point estimates; unsupported observations prevent window assessment.

    Eligibility is not a confidence guarantee or a claim of player-side victory.
    """

    source_request: NpcMeleeSimulationRequest
    summary: NpcMeleeSimulationSummary
    window: ObjectiveRateWindow

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcMeleeSimulationRequest):
            raise TypeError("assessment requires a typed simulation request")
        if not isinstance(self.summary, NpcMeleeSimulationSummary):
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
    def status(self) -> MeleeAssessmentStatus:
        return (MeleeAssessmentStatus.UNSUPPORTED_OBSERVATIONS if self.summary.outcome_counts.unsupported_path
                else MeleeAssessmentStatus.ELIGIBLE)

    @property
    def window_match(self) -> bool | None:
        if self.status is MeleeAssessmentStatus.UNSUPPORTED_OBSERVATIONS:
            return None
        return self.window.minimum <= self.objective_achieved_rate <= self.window.maximum
