"""Immutable magic stage specifications and complete report chains (ADR-0041)."""
from dataclasses import dataclass
from enum import Enum

from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.balance.magic_evaluation_models import (
    MagicBalanceCandidate, MagicBalanceEvaluationRequest, MagicBalanceEvaluationResult,
)
from towr.balance.magic_staged_evaluation import magic_continuation_candidate_ids
from towr.simulation.npc_magic_models import SEED_SCHEME


@dataclass(frozen=True, slots=True)
class MagicBalanceStage:
    trials_per_candidate: int
    keep: int

    def __post_init__(self) -> None:
        for name in ("trials_per_candidate", "keep"):
            if type(getattr(self, name)) is not int:
                raise TypeError(f"stage {name} must be an integer")
        if not 1 <= self.trials_per_candidate < 2**64:
            raise ValueError("magic stage trials must be a positive uint64 integer")
        if self.keep < 1:
            raise ValueError("magic stage keep must be positive")


def _validate_stages(stages: tuple[MagicBalanceStage, ...]) -> None:
    if not stages:
        raise ValueError("magic staged evaluation requires at least one stage")
    if not all(isinstance(stage, MagicBalanceStage) for stage in stages):
        raise TypeError("magic staged evaluation requires typed magic stages")
    if any(right.trials_per_candidate <= left.trials_per_candidate for left, right in zip(stages, stages[1:])):
        raise ValueError("magic stage trials must strictly increase")


def _planned_trials(candidate_count: int, stages: tuple[MagicBalanceStage, ...]) -> int:
    total = 0
    for stage in stages:
        total += candidate_count * stage.trials_per_candidate
        candidate_count = min(candidate_count, stage.keep)
    return total


@dataclass(frozen=True, slots=True)
class MagicStagedEvaluationRequest:
    candidates: tuple[MagicBalanceCandidate, ...]
    master_seed: int
    stages: tuple[MagicBalanceStage, ...]
    max_total_trials: int
    window: ObjectiveRateWindow

    def __post_init__(self) -> None:
        if not isinstance(self.candidates, (tuple, list)):
            raise TypeError("magic staged candidates must be an ordered tuple or list")
        if not isinstance(self.stages, (tuple, list)):
            raise TypeError("magic stages must be an ordered tuple or list")
        candidates, stages = tuple(self.candidates), tuple(self.stages)
        _validate_stages(stages)
        if type(self.max_total_trials) is not int:
            raise TypeError("max_total_trials must be an integer")
        if self.max_total_trials < 1:
            raise ValueError("max_total_trials must be positive")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "stages", stages)
        # Existing bounded admission checks all candidates, common fields and seed.
        _stage_request(self, 0, candidates)
        if self.planned_trials > self.max_total_trials:
            raise ValueError("magic staged evaluation exceeds max_total_trials")

    @property
    def planned_trials(self) -> int:
        return _planned_trials(len(self.candidates), self.stages)


def _stage_request(
    source: MagicStagedEvaluationRequest, stage_index: int, candidates: tuple[MagicBalanceCandidate, ...],
) -> MagicBalanceEvaluationRequest:
    """Use the same exact local request for execution and report validation."""
    stage = source.stages[stage_index]
    return MagicBalanceEvaluationRequest(
        candidates, source.master_seed, stage.trials_per_candidate,
        len(candidates) * stage.trials_per_candidate, source.window, stage.keep,
    )


class MagicStagedEvaluationStatus(str, Enum):
    COMPLETED = "completed"
    NO_ELIGIBLE_CANDIDATES = "no_eligible_candidates"


@dataclass(frozen=True, slots=True)
class MagicStagedEvaluationResult:
    source_request: MagicStagedEvaluationRequest
    stage_reports: tuple[MagicBalanceEvaluationResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, MagicStagedEvaluationRequest):
            raise TypeError("magic staged result requires its typed source request")
        if not isinstance(self.stage_reports, (tuple, list)):
            raise TypeError("magic stage reports must be an ordered tuple or list")
        reports = tuple(self.stage_reports)
        if not all(isinstance(report, MagicBalanceEvaluationResult) for report in reports):
            raise TypeError("magic staged result requires typed magic evaluation reports")
        source = self.source_request
        if not reports or len(reports) > len(source.stages):
            raise ValueError("magic staged result requires a non-empty bounded report chain")
        candidates = source.candidates
        for index, report in enumerate(reports):
            if not candidates:
                raise ValueError("magic stage report follows an exhausted candidate list")
            if report.source_request != _stage_request(source, index, candidates):
                raise ValueError("magic stage report has a foreign source or incorrect continuation")
            kept = set(magic_continuation_candidate_ids(report))
            candidates = tuple(candidate for candidate in candidates if candidate.candidate_id in kept)
        if len(reports) < len(source.stages) and candidates:
            raise ValueError("magic staged result stopped with eligible candidates before the final stage")
        object.__setattr__(self, "stage_reports", reports)

    @property
    def status(self) -> MagicStagedEvaluationStatus:
        return (MagicStagedEvaluationStatus.COMPLETED
                if len(self.stage_reports) == len(self.source_request.stages)
                else MagicStagedEvaluationStatus.NO_ELIGIBLE_CANDIDATES)

    @property
    def selected_candidate_ids(self) -> tuple[str, ...]:
        if self.status is MagicStagedEvaluationStatus.NO_ELIGIBLE_CANDIDATES:
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
