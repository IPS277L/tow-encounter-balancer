from dataclasses import dataclass
from enum import Enum

from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.balance.ranged_evaluation_models import (
    RangedBalanceCandidate, RangedBalanceEvaluationRequest, RangedBalanceEvaluationResult,
)
from towr.balance.ranged_staged_evaluation import ranged_continuation_candidate_ids
from towr.simulation.npc_ranged_models import SEED_SCHEME


@dataclass(frozen=True, slots=True)
class RangedBalanceStage:
    trials_per_candidate: int
    keep: int

    def __post_init__(self) -> None:
        if type(self.trials_per_candidate) is not int or not 1 <= self.trials_per_candidate < 2**64:
            raise ValueError("stage trials must be a positive uint64 integer")
        if type(self.keep) is not int or self.keep < 1:
            raise ValueError("stage keep must be a positive integer")


def _validate_stages(stages: tuple[RangedBalanceStage, ...]) -> None:
    if not stages:
        raise ValueError("staged evaluation requires at least one stage")
    if not all(isinstance(stage, RangedBalanceStage) for stage in stages):
        raise TypeError("staged evaluation requires typed stages")
    if any(right.trials_per_candidate <= left.trials_per_candidate for left, right in zip(stages, stages[1:])):
        raise ValueError("stage trials must strictly increase")


def _planned_trials(candidate_count: int, stages: tuple[RangedBalanceStage, ...]) -> int:
    """Count complete reruns for an already validated non-empty candidate family."""
    total = 0
    for stage in stages:
        total += candidate_count * stage.trials_per_candidate
        candidate_count = min(candidate_count, stage.keep)
    return total


@dataclass(frozen=True, slots=True)
class RangedStagedEvaluationRequest:
    candidates: tuple[RangedBalanceCandidate, ...]
    master_seed: int
    stages: tuple[RangedBalanceStage, ...]
    max_total_trials: int
    window: ObjectiveRateWindow

    def __post_init__(self) -> None:
        candidates = tuple(self.candidates)
        stages = tuple(self.stages)
        _validate_stages(stages)
        if type(self.max_total_trials) is not int or self.max_total_trials < 1:
            raise ValueError("max_total_trials must be a positive integer")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "stages", stages)
        # Reuse admission for all candidates, common fields and seed; no runner is called.
        _stage_request(self, 0, candidates)
        if self.planned_trials > self.max_total_trials:
            raise ValueError("staged evaluation exceeds max_total_trials")

    @property
    def planned_trials(self) -> int:
        return _planned_trials(len(self.candidates), self.stages)


def _stage_request(
    source: RangedStagedEvaluationRequest, stage_index: int, candidates: tuple[RangedBalanceCandidate, ...],
) -> RangedBalanceEvaluationRequest:
    """Build the same exact local request for execution and report validation."""
    stage = source.stages[stage_index]
    return RangedBalanceEvaluationRequest(
        candidates, source.master_seed, stage.trials_per_candidate,
        len(candidates) * stage.trials_per_candidate, source.window, stage.keep,
    )


class RangedStagedEvaluationStatus(str, Enum):
    COMPLETED = "completed"
    NO_ELIGIBLE_CANDIDATES = "no_eligible_candidates"


@dataclass(frozen=True, slots=True)
class RangedStagedEvaluationResult:
    source_request: RangedStagedEvaluationRequest
    stage_reports: tuple[RangedBalanceEvaluationResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, RangedStagedEvaluationRequest):
            raise TypeError("staged result requires its typed request")
        reports = tuple(self.stage_reports)
        source = self.source_request
        if not reports or len(reports) > len(source.stages):
            raise ValueError("staged result requires a non-empty bounded chain of reports")
        if not all(isinstance(report, RangedBalanceEvaluationResult) for report in reports):
            raise TypeError("staged result requires typed evaluation reports")
        candidates = source.candidates
        for index, report in enumerate(reports):
            if not candidates:
                raise ValueError("stage report follows an exhausted candidate list")
            if report.source_request != _stage_request(source, index, candidates):
                raise ValueError("stage report has a foreign source or incorrect continuation")
            kept = set(ranged_continuation_candidate_ids(report))
            candidates = tuple(candidate for candidate in candidates if candidate.candidate_id in kept)
        if len(reports) < len(source.stages) and candidates:
            raise ValueError("staged result stopped before the final stage with eligible candidates")
        object.__setattr__(self, "stage_reports", reports)

    @property
    def status(self) -> RangedStagedEvaluationStatus:
        return (RangedStagedEvaluationStatus.COMPLETED
                if len(self.stage_reports) == len(self.source_request.stages)
                else RangedStagedEvaluationStatus.NO_ELIGIBLE_CANDIDATES)

    @property
    def selected_candidate_ids(self) -> tuple[str, ...]:
        if self.status is RangedStagedEvaluationStatus.NO_ELIGIBLE_CANDIDATES:
            return ()
        return self.stage_reports[-1].selected_candidate_ids

    @property
    def planned_trials(self) -> int:
        return self.source_request.planned_trials

    @property
    def total_trials(self) -> int:
        return sum(report.total_trials for report in self.stage_reports)

    @property
    def seed_scheme(self) -> str:
        return SEED_SCHEME
