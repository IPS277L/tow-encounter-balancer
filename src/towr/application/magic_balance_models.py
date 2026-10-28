"""Immutable magic balance boundary inputs and aggregate source chain (ADR-0043)."""
from dataclasses import dataclass

from towr.application.magic_candidate_generation_models import (
    MagicCandidateGenerationRequest, MagicCandidateGenerationResult,
)
from towr.application.ranged_simulation_models import SimulationExecutionOptions
from towr.balance.magic_staged_evaluation_models import MagicStagedEvaluationResult


@dataclass(frozen=True, slots=True)
class MagicBalanceCommand:
    request_id: str
    generation_request: MagicCandidateGenerationRequest
    execution: SimulationExecutionOptions
    definition_order: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str):
            raise TypeError('magic balance request ID must be a string')
        if not self.request_id.strip():
            raise ValueError('magic balance request ID must not be blank')
        if not isinstance(self.generation_request, MagicCandidateGenerationRequest):
            raise TypeError('balance command requires a typed magic generation request')
        if not isinstance(self.execution, SimulationExecutionOptions):
            raise TypeError('balance command requires typed execution options')
        if not isinstance(self.definition_order, (tuple, list)):
            raise TypeError('definition order requires an ordered tuple or list')
        order = tuple(self.definition_order)
        if not all(isinstance(item, str) and item.strip() for item in order):
            raise ValueError('definition order requires non-empty IDs')
        roster = self.generation_request.template_scenario.initial.roster
        if len(set(order)) != len(order) or set(order) != {p.definition.id for p in roster.participants}:
            raise ValueError('definition order must contain every used definition exactly once')
        object.__setattr__(self, 'definition_order', order)


@dataclass(frozen=True, slots=True)
class MagicBalanceResult:
    generation_result: MagicCandidateGenerationResult
    evaluation_result: MagicStagedEvaluationResult

    def __post_init__(self) -> None:
        if not isinstance(self.generation_result, MagicCandidateGenerationResult):
            raise TypeError('balance result requires a typed magic generation result')
        if not isinstance(self.evaluation_result, MagicStagedEvaluationResult):
            raise TypeError('balance result requires a typed magic staged evaluation result')
        if self.evaluation_result.source_request != self.generation_result.evaluation_request:
            raise ValueError('balance evaluation must belong to the exact generated request')
